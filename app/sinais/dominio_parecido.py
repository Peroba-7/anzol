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

from collections.abc import Iterable

from app.dominios import eh_do_dominio, separar_dominio
from app.enderecos import extrair_host
from app.marcas import carregar_marcas, nome_da_marca, resolver_marcas
from app.sinais.base import Peso, Sinal

__all__ = ["carregar_marcas", "detectar_dominios_parecidos", "esqueleto"]

NOME_PARECIDO = "dominio_parecido_com_marca"
NOME_PUNYCODE = "dominio_punycode"

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


# ---------------------------------------------------------------- utilidades


def esqueleto(texto: str) -> str:
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


def _forma_unicode(host: str) -> str:
    """Converte xn--... de volta para as letras originais (para comparar e exibir)."""
    try:
        return host.encode("ascii").decode("idna")
    except UnicodeError:
        return host


# ---------------------------------------------------------------- comparação


def _comparar(host: str, marca: str) -> tuple[Peso, str] | None:
    """Compara um host com uma marca. Devolve (peso, motivo) ou None."""
    nome_marca = nome_da_marca(marca)
    esqueleto_marca = esqueleto(nome_marca)

    # Compara a forma ASCII e, se houver punycode, também as letras originais.
    candidatos = {host, _forma_unicode(host)}
    melhor: tuple[Peso, str] | None = None

    for candidato in candidatos:
        corpo, _sufixo = separar_dominio(candidato)
        pedacos = set(corpo.split("."))
        pedacos |= {p for parte in list(pedacos) for p in parte.split("-")}
        pedacos.discard("")

        for pedaco in pedacos:
            if pedaco == nome_marca:
                continue  # nome idêntico: tratado abaixo como "marca dentro"
            forma = esqueleto(pedaco)
            if forma == esqueleto_marca:
                return Peso.ALTO, "troca letras por caracteres parecidos"
            if len(nome_marca) >= TAMANHO_MINIMO_ERRO_DIGITACAO and (
                _distancia(pedaco, nome_marca) == 1 or _distancia(forma, esqueleto_marca) == 1
            ):
                return Peso.ALTO, "tem uma letra a mais, a menos ou trocada"

        if len(nome_marca) >= TAMANHO_MINIMO_CONTIDA:
            if nome_marca in corpo:
                melhor = melhor or (Peso.MEDIO, "usa o nome da marca dentro de outro domínio")
            elif esqueleto_marca in esqueleto(corpo):
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
    lista_marcas = resolver_marcas(marcas)

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
        host = extrair_host(entrada)
        if host is None:
            continue
        # Regra 3: o domínio oficial e seus subdomínios nunca são acusados.
        if any(eh_do_dominio(host, marca) for marca in lista_marcas):
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
