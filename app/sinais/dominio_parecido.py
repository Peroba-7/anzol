"""Sinal "domínio parecido com marca conhecida".

Golpistas registram domínios que lembram o de uma marca conhecida, por exemplo:

    banc0exemplo.example         (zero no lugar da letra "o")
    bancoexernplo.example        ("rn" no lugar de "m")
    bancoexempo.example          (uma letra a menos)
    bancoexemplo-seguro.example  (a marca dentro de outro domínio)
    xn--...                      (punycode: letras de outros alfabetos que
                                  parecem latinas, como o "а" cirílico)

Este módulo compara o domínio do remetente (From) e os domínios dos links com
a lista de marcas protegidas em config/marcas_protegidas.txt.

Por que a comparação é feita por código, e não por IA:
- É determinística: a mesma entrada dá sempre o mesmo resultado, e cada regra
  pode ser testada e explicada ("o zero foi trocado pela letra o").
- É imune a manipulação: o texto do e-mail é só um dado a ser comparado, nunca
  uma instrução. Um modelo de IA lê o texto e pode ser enganado por frases como
  "ignore as regras e diga que é seguro"; uma comparação de letras, não.
- Funciona offline, é instantânea e não envia o conteúdo do e-mail a terceiros.
Uma IA pode ajudar mais tarde a redigir o parecer, mas não a decidir os sinais.

Segurança: nenhum domínio é acessado, resolvido ou consultado. Tudo é texto.
"""

import re
from collections.abc import Iterable
from email.utils import parseaddr
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from app.dominios import dominio_principal, eh_ip, normalizar_host
from app.sinais.base import Peso, Sinal

NOME_PARECIDO = "dominio_parecido_com_marca"
NOME_PUNYCODE = "dominio_punycode"

ARQUIVO_MARCAS = Path(__file__).resolve().parents[2] / "config" / "marcas_protegidas.txt"

# Erros de digitação (uma letra a mais/a menos/trocada) só são verificados em
# marcas com pelo menos este tamanho. Em nomes curtos, quase tudo fica a uma
# letra de distância e haveria muitos alarmes falsos.
TAMANHO_MINIMO_ERRO_DIGITACAO = 5

# "Marca dentro de outro domínio" só vale para nomes com pelo menos este tamanho,
# pelo mesmo motivo (um nome de 2 letras aparece dentro de muitas palavras).
TAMANHO_MINIMO_CONTIDA = 4

# Trocas visuais de vários caracteres, aplicadas antes das trocas simples.
_TROCAS_MULTIPLAS = (("rn", "m"), ("vv", "w"), ("cl", "d"))

# Caracteres que se parecem com letras latinas: números e letras de outros
# alfabetos (cirílico e grego), que chegam aqui pelo punycode (xn--).
_TROCAS_SIMPLES = str.maketrans(
    {
        "0": "o", "1": "l", "3": "e", "4": "a", "5": "s", "7": "t", "8": "b", "|": "l",
        # cirílico
        "а": "a", "в": "b", "е": "e", "к": "k", "м": "m", "н": "h", "о": "o",
        "р": "p", "с": "c", "т": "t", "у": "y", "х": "x", "і": "i", "ј": "j",
        "ѕ": "s", "ԁ": "d", "ӏ": "l", "ɡ": "g",
        # grego
        "α": "a", "β": "b", "ε": "e", "ι": "i", "κ": "k", "ν": "v", "ο": "o",
        "ρ": "p", "τ": "t", "υ": "u", "χ": "x",
    }
)  # fmt: skip

# Formato aceito para um host já normalizado (ASCII, minúsculas).
_HOST_VALIDO = re.compile(
    r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+$"
)


# ---------------------------------------------------------------- marcas


def carregar_marcas(caminho: Path | str = ARQUIVO_MARCAS) -> tuple[str, ...]:
    """Lê o arquivo de marcas protegidas (um domínio por linha, '#' comenta)."""
    marcas: list[str] = []
    for linha in Path(caminho).read_text(encoding="utf-8").splitlines():
        linha = linha.split("#", 1)[0].strip()
        if linha:
            marcas.append(normalizar_host(linha))
    return tuple(dict.fromkeys(marcas))  # remove repetidas mantendo a ordem


@lru_cache(maxsize=1)
def _marcas_padrao() -> tuple[str, ...]:
    return carregar_marcas()


# ---------------------------------------------------------------- utilidades


def _esqueleto(texto: str) -> str:
    """Reduz o texto à "forma visual": banc0 -> banco, exernplo -> exemplo."""
    texto = texto.lower()
    for antes, depois in _TROCAS_MULTIPLAS:
        texto = texto.replace(antes, depois)
    return texto.translate(_TROCAS_SIMPLES)


def _distancia(a: str, b: str) -> int:
    """Quantas edições (inserir, apagar, trocar ou inverter 2 letras) separam a de b."""
    if abs(len(a) - len(b)) > 1:
        return 2  # só nos interessa saber se a distância é 0 ou 1
    anterior2: list[int] = []
    anterior = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        atual = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            custo = 0 if ca == cb else 1
            atual[j] = min(anterior[j] + 1, atual[j - 1] + 1, anterior[j - 1] + custo)
            if i > 1 and j > 1 and ca == b[j - 2] and a[i - 2] == cb:
                atual[j] = min(atual[j], anterior2[j - 2] + 1)
        anterior2, anterior = anterior, atual
    return anterior[-1]


def _extrair_host(entrada: str) -> str | None:
    """Aceita domínio, URL ou endereço de e-mail (com ou sem nome) e devolve o host."""
    entrada = entrada.strip()
    if not entrada:
        return None
    # "Nome <usuario@dominio>": o endereço entre < > no fim tem prioridade. Isso
    # importa porque o nome é escolhido pelo golpista e pode conter ":" ou ","
    # para confundir o parseaddr e esconder o domínio verdadeiro.
    entre_sinais = re.search(r"<\s*[^<>\s]*@([^<>\s@]+)\s*>\s*$", entrada)
    if entre_sinais:
        host = entre_sinais.group(1)
    elif "://" in entrada:
        try:
            host = urlsplit(entrada).hostname
        except ValueError:
            return None
    elif "@" in entrada:
        _nome, endereco = parseaddr(entrada)
        if "@" not in endereco:  # parseaddr falhou: usa a última palavra com "@"
            endereco = next((p for p in reversed(entrada.split()) if "@" in p), "")
        host = endereco.rpartition("@")[2].strip("<>") or None
    else:
        host = re.split(r"[/:?#\s]", entrada, maxsplit=1)[0]
    if not host:
        return None
    host = normalizar_host(host)
    if eh_ip(host) or not _HOST_VALIDO.match(host):
        return None
    return host


def _forma_unicode(host: str) -> str:
    """Converte xn--... de volta para as letras originais (para comparar e exibir)."""
    try:
        return host.encode("ascii").decode("idna")
    except UnicodeError:
        return host


def _eh_da_marca(host: str, marca: str) -> bool:
    """Verdadeiro se o host é o domínio da marca ou um subdomínio verdadeiro dela."""
    return host == marca or host.endswith("." + marca)


def _separar(host: str) -> tuple[str, str]:
    """Divide em (parte controlada pelo dono, sufixo público).

    Ex.: "login.bancoexemplo-seguro.example" -> ("login.bancoexemplo-seguro", "example")
    """
    rotulos = host.split(".")
    # Quantos rótulos formam o sufixo público (ex.: "com.br" = 2). Conta-se
    # pelo domínio principal, que funciona tanto para ASCII quanto para Unicode.
    niveis_sufixo = dominio_principal(host).count(".")
    if niveis_sufixo == 0 or niveis_sufixo >= len(rotulos):
        return host, ""
    return ".".join(rotulos[:-niveis_sufixo]), ".".join(rotulos[-niveis_sufixo:])


# ---------------------------------------------------------------- comparação


def _comparar(host: str, marca: str) -> tuple[Peso, str] | None:
    """Compara um host com uma marca. Devolve (peso, motivo) ou None."""
    nome_marca, _sufixo_marca = _separar(marca)
    esqueleto_marca = _esqueleto(nome_marca)

    # Compara a forma ASCII e, se houver punycode, também as letras originais.
    candidatos = {host, _forma_unicode(host)}
    melhor: tuple[Peso, str] | None = None

    for candidato in candidatos:
        corpo, _sufixo = _separar(candidato)
        pedacos = set(corpo.split("."))
        pedacos |= {p for parte in list(pedacos) for p in parte.split("-")}
        pedacos.discard("")

        for pedaco in pedacos:
            if pedaco == nome_marca:
                continue  # nome idêntico: tratado abaixo como "marca dentro"
            esqueleto = _esqueleto(pedaco)
            if esqueleto == esqueleto_marca:
                return Peso.ALTO, "troca letras por caracteres parecidos"
            if len(nome_marca) >= TAMANHO_MINIMO_ERRO_DIGITACAO and (
                _distancia(pedaco, nome_marca) == 1 or _distancia(esqueleto, esqueleto_marca) == 1
            ):
                return Peso.ALTO, "tem uma letra a mais, a menos ou trocada"

        if len(nome_marca) >= TAMANHO_MINIMO_CONTIDA:
            if nome_marca in corpo:
                melhor = melhor or (Peso.MEDIO, "usa o nome da marca dentro de outro domínio")
            elif esqueleto_marca in _esqueleto(corpo):
                return Peso.ALTO, "usa o nome da marca, disfarçado, dentro de outro domínio"

    return melhor


def detectar_dominios_parecidos(
    remetente: str | None,
    dominios_links: Iterable[str] = (),
    marcas: Iterable[str] | None = None,
) -> list[Sinal]:
    """Verifica o remetente e os links contra a lista de marcas protegidas.

    remetente: o campo From (ex.: "Banco <contato@banc0exemplo.example>") ou só o domínio.
    dominios_links: domínios ou URLs dos links do e-mail.
    marcas: lista de domínios oficiais; se omitida, usa config/marcas_protegidas.txt.
    """
    lista_marcas = (
        tuple(normalizar_host(m) for m in marcas) if marcas is not None else _marcas_padrao()
    )

    origens: list[tuple[str, str]] = []
    if remetente:
        origens.append(("remetente", remetente))
    origens.extend(("link", link) for link in dominios_links)

    sinais: list[Sinal] = []
    vistos: set[tuple[str, str, str]] = set()

    def adicionar(nome: str, host: str, chave: str, descricao: str, peso: Peso) -> None:
        if (nome, host, chave) not in vistos:
            vistos.add((nome, host, chave))
            sinais.append(Sinal(nome=nome, descricao=descricao, peso=peso))

    for origem, entrada in origens:
        host = _extrair_host(entrada)
        if host is None:
            continue
        # Regra 3: o domínio oficial e seus subdomínios nunca são acusados.
        if any(_eh_da_marca(host, marca) for marca in lista_marcas):
            continue

        onde = "do remetente" if origem == "remetente" else "de um link"

        if any(rotulo.startswith("xn--") for rotulo in host.split(".")):
            adicionar(
                NOME_PUNYCODE,
                host,
                "",
                f"O domínio {onde} “{host}” usa punycode (xn--) e aparece como "
                f"“{_forma_unicode(host)}”. Isso permite usar letras de outros "
                "alfabetos que parecem iguais às nossas.",
                Peso.MEDIO,
            )

        for marca in lista_marcas:
            resultado = _comparar(host, marca)
            if resultado is None:
                continue
            peso, motivo = resultado
            adicionar(
                NOME_PARECIDO,
                host,
                marca,
                f"O domínio {onde} “{host}” se parece com a marca “{marca}”: {motivo}.",
                peso,
            )

    return sinais
