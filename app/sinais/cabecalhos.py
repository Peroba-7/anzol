"""Sinais de cabeçalho do e-mail: autenticação (SPF, DKIM, DMARC) e remetente.

Entrada: o e-mail bruto (cabeçalhos + corpo), lido só com a biblioteca padrão.

Sinais e pesos:
    dmarc=fail                                         -> ALTO
    nome de exibição cita marca, mas o domínio não é dela -> ALTO
    spf=fail ou dkim=fail                              -> MÉDIO
    Reply-To de outro domínio principal                -> MÉDIO
    Return-Path de outro domínio principal             -> BAIXO
    spf=softfail ou dkim=none (assinatura ausente)     -> BAIXO

Regras de projeto:
- "pass" NUNCA reduz o risco nem apaga sinais. Um golpista pode registrar um
  domínio parecido e configurar SPF, DKIM e DMARC corretamente nele; o "pass"
  só prova de qual domínio a mensagem veio, não que ele seja honesto.
- Sem Authentication-Results não há sinal de autenticação: um e-mail colado à
  mão pode não ter esse cabeçalho, e a ausência não é culpa do remetente.
- Nada escrito no e-mail é tratado como ordem; tudo é só dado comparado por código.

LIMITAÇÃO CONHECIDA (registrada também no README):
Só usamos o Authentication-Results MAIS ACIMA, que é o último a ser adicionado,
ou seja, o do servidor que recebeu a mensagem. Os de baixo podem ter sido
escritos pelo próprio golpista dentro do e-mail para fingir "dmarc=pass".
Mesmo o de cima só é confiável se o e-mail veio direto da caixa postal: se
alguém montar o e-mail à mão, pode escrever um Authentication-Results falso no
topo, e o Anzol não tem como saber. Por isso o "pass" nunca reduz o risco.
"""

import re
import unicodedata
from collections.abc import Iterable
from email import policy
from email.message import Message
from email.parser import Parser

from app.dominios import dominio_principal, eh_do_dominio
from app.enderecos import desdobrar, enderecos_em, separar_nome_e_endereco, validar_host
from app.marcas import nome_da_marca, resolver_marcas
from app.sinais.base import Peso, Sinal
from app.sinais.dominio_parecido import TAMANHO_MINIMO_CONTIDA, esqueleto

NOME_DMARC_FALHOU = "dmarc_falhou"
NOME_SPF_FALHOU = "spf_falhou"
NOME_SPF_SOFTFAIL = "spf_softfail"
NOME_DKIM_FALHOU = "dkim_falhou"
NOME_DKIM_AUSENTE = "dkim_ausente"
NOME_MARCA_NO_NOME = "nome_de_marca_com_dominio_estranho"
NOME_REPLY_TO = "reply_to_de_outro_dominio"
NOME_RETURN_PATH = "return_path_de_outro_dominio"

# (método, resultado) -> (nome do sinal, peso, descrição)
# Só resultados ruins estão aqui. "pass" e qualquer outro valor não geram nada.
_RESULTADOS_RUINS: dict[tuple[str, str], tuple[str, Peso, str]] = {
    ("dmarc", "fail"): (
        NOME_DMARC_FALHOU,
        Peso.ALTO,
        "O DMARC falhou: o domínio que aparece como remetente não é o mesmo que foi "
        "verificado pelo servidor. É o sinal mais comum de remetente falsificado.",
    ),
    ("spf", "fail"): (
        NOME_SPF_FALHOU,
        Peso.MEDIO,
        "O SPF falhou: o servidor que enviou a mensagem NÃO tem permissão para enviar "
        "e-mails em nome desse domínio.",
    ),
    ("spf", "softfail"): (
        NOME_SPF_SOFTFAIL,
        Peso.BAIXO,
        "O SPF deu “softfail”: o domínio indica que esse servidor provavelmente não "
        "deveria enviar por ele, mas pede só cautela, não rejeição.",
    ),
    ("dkim", "fail"): (
        NOME_DKIM_FALHOU,
        Peso.MEDIO,
        "O DKIM falhou: a mensagem tinha assinatura, mas ela não confere. A mensagem "
        "pode ter sido alterada no caminho ou a assinatura não é do domínio.",
    ),
    ("dkim", "none"): (
        NOME_DKIM_AUSENTE,
        Peso.BAIXO,
        "O DKIM está ausente: a mensagem não tinha assinatura digital nenhuma. "
        "Não prova golpe, mas tira uma garantia de origem.",
    ),
}

_METODO_RESULTADO = re.compile(r"^\s*(spf|dkim|dmarc)\s*=\s*([a-z]+)", re.IGNORECASE)


# ---------------------------------------------------------------- leitura


def _ler_cabecalhos(email_bruto: str) -> Message:
    """Lê só os cabeçalhos do e-mail bruto, sem nunca levantar erro."""
    texto = (email_bruto or "").replace("\r\n", "\n").lstrip("\n")
    # compat32 devolve os valores como texto puro, sem tentar interpretá-los,
    # o que evita erros com cabeçalhos malformados.
    return Parser(policy=policy.compat32).parsestr(texto, headersonly=True)


def _primeiro(mensagem: Message, nome: str) -> str | None:
    """Primeira ocorrência (a mais acima) de um cabeçalho, ignorando maiúsculas."""
    valores = mensagem.get_all(nome) or []
    return str(valores[0]) if valores else None


def _resultados_autenticacao(cabecalho: str) -> list[tuple[str, str]]:
    """Extrai pares (método, resultado) de um Authentication-Results."""
    texto = desdobrar(cabecalho)
    # Remove comentários entre parênteses (podem ser aninhados).
    anterior = None
    while anterior != texto:
        anterior, texto = texto, re.sub(r"\([^()]*\)", " ", texto)
    # A primeira parte, antes do ";", é o nome do servidor que verificou.
    _servidor, _, resto = texto.partition(";")
    pares = []
    for parte in resto.split(";"):
        encontrado = _METODO_RESULTADO.match(parte)
        if encontrado:
            pares.append((encontrado.group(1).lower(), encontrado.group(2).lower()))
    return pares


def _host_do_endereco(endereco: str) -> str | None:
    return validar_host(endereco.rpartition("@")[2]) if "@" in endereco else None


def _texto_comparavel(texto: str) -> str:
    """Tira acentos, espaços e pontuação e aplica a forma visual.

    Ex.: "Bânc0 Exemplo" -> "bancoexemplo".
    """
    sem_acentos = "".join(
        c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)
    )
    return re.sub(r"[^a-z]", "", esqueleto(sem_acentos))


# ---------------------------------------------------------------- análise


def _sinais_de_autenticacao(mensagem: Message) -> list[Sinal]:
    # Só o MAIS ACIMA vale (ver "LIMITAÇÃO CONHECIDA" no topo do arquivo).
    cabecalho = _primeiro(mensagem, "Authentication-Results")
    if cabecalho is None:
        return []  # ausência do cabeçalho não é punida

    sinais = []
    vistos: set[str] = set()
    for metodo, resultado in _resultados_autenticacao(cabecalho):
        ruim = _RESULTADOS_RUINS.get((metodo, resultado))
        if ruim and ruim[0] not in vistos:
            vistos.add(ruim[0])
            sinais.append(Sinal(nome=ruim[0], peso=ruim[1], descricao=ruim[2]))
    return sinais


def _sinal_nome_de_marca(
    nome_exibicao: str, host_from: str | None, marcas: tuple[str, ...]
) -> list[Sinal]:
    if not nome_exibicao or host_from is None:
        return []
    nome = _texto_comparavel(nome_exibicao)
    for marca in marcas:
        nome_marca = _texto_comparavel(nome_da_marca(marca))
        if len(nome_marca) < TAMANHO_MINIMO_CONTIDA or nome_marca not in nome:
            continue
        if eh_do_dominio(host_from, marca):
            continue  # a marca citada é a dona do domínio: tudo certo
        return [
            Sinal(
                nome=NOME_MARCA_NO_NOME,
                peso=Peso.ALTO,
                descricao=(
                    f"O nome do remetente cita a marca “{marca}”, mas o endereço é do "
                    f"domínio “{host_from}”, que não pertence a ela. Muitos aplicativos "
                    "mostram só o nome e escondem o endereço."
                ),
            )
        ]
    return []


def _sinais_de_dominio_diferente(mensagem: Message, host_from: str | None) -> list[Sinal]:
    if host_from is None:
        return []
    dominio_from = dominio_principal(host_from)
    sinais = []

    regras = (
        ("Reply-To", NOME_REPLY_TO, Peso.MEDIO, "as respostas iriam para outro lugar"),
        ("Return-Path", NOME_RETURN_PATH, Peso.BAIXO, "a entrega veio de outro endereço"),
    )
    for cabecalho, nome, peso, consequencia in regras:
        # Todas as ocorrências contam: um golpista pode repetir o cabeçalho para
        # esconder o endereço dele no segundo. Mais ocorrências nunca apagam sinais.
        valores = [str(v) for v in mensagem.get_all(cabecalho) or []]
        diferentes = []
        for endereco in (e for valor in valores for e in enderecos_em(valor)):
            host = _host_do_endereco(endereco)
            if host and dominio_principal(host) != dominio_from:
                diferentes.append(dominio_principal(host))
        if diferentes:
            lista = ", ".join(f"“{d}”" for d in dict.fromkeys(diferentes))
            sinais.append(
                Sinal(
                    nome=nome,
                    peso=peso,
                    descricao=(
                        f"O {cabecalho} usa o domínio {lista}, diferente do remetente "
                        f"“{dominio_from}”: {consequencia}. Pode ser golpe, mas também "
                        "acontece com serviços de envio contratados pela empresa."
                    ),
                )
            )
    return sinais


def detectar_sinais_de_cabecalho(
    email_bruto: str, marcas: Iterable[str] | None = None
) -> list[Sinal]:
    """Analisa os cabeçalhos de um e-mail bruto e devolve os sinais encontrados.

    marcas: domínios oficiais protegidos; se omitida, usa config/marcas_protegidas.txt.
    """
    mensagem = _ler_cabecalhos(email_bruto)
    lista_marcas = resolver_marcas(marcas)

    nome_exibicao, endereco_from = separar_nome_e_endereco(_primeiro(mensagem, "From") or "")
    host_from = _host_do_endereco(endereco_from)

    return [
        *_sinais_de_autenticacao(mensagem),
        *_sinal_nome_de_marca(nome_exibicao, host_from, lista_marcas),
        *_sinais_de_dominio_diferente(mensagem, host_from),
    ]
