"""Leitura de endereços de e-mail, URLs e cabeçalhos, sem acessar a internet.

Cuidado central: o nome de exibição ("Banco Exemplo" em
"Banco Exemplo <x@golpe.example>") é escrito pelo golpista. Ele pode conter
":" , "," ou até algo parecido com um endereço para confundir o leitor
padrão do Python (parseaddr) e esconder o domínio verdadeiro. Por isso o
endereço entre < > no fim do campo sempre tem prioridade.
"""

import re
from email.header import decode_header, make_header
from email.utils import parseaddr
from urllib.parse import urlsplit

from app.dominios import eh_ip, normalizar_host

# Formato aceito para um host já normalizado (ASCII, minúsculas).
_HOST_VALIDO = re.compile(
    r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+$"
)

# Endereço entre sinais de menor e maior: <usuario@dominio>
_ENTRE_SINAIS = re.compile(r"<\s*([^<>\s]*@[^<>\s@]+)\s*>")


def desdobrar(valor: str) -> str:
    """Junta um cabeçalho quebrado em várias linhas numa linha só."""
    return re.sub(r"\r?\n[ \t]+", " ", valor).strip()


def decodificar_cabecalho(valor: str) -> str:
    """Decodifica trechos como =?utf-8?B?...?=; se estiverem quebrados, devolve o original."""
    valor = desdobrar(str(valor))
    try:
        return str(make_header(decode_header(valor)))
    except Exception:  # noqa: BLE001 - cabeçalho malformado não pode derrubar a análise
        return valor


def separar_nome_e_endereco(valor: str) -> tuple[str, str]:
    """Separa "Nome <usuario@dominio>" em (nome, endereço).

    Se não houver endereço reconhecível, devolve o texto como nome e endereço vazio.
    """
    valor = desdobrar(valor)
    encontrados = list(_ENTRE_SINAIS.finditer(valor))
    if encontrados:
        # O último <...> é o endereço real; tudo antes dele é o nome de exibição.
        ultimo = encontrados[-1]
        nome = valor[: ultimo.start()]
        return _limpar_nome(nome), ultimo.group(1)

    nome, endereco = parseaddr(valor)
    if "@" in endereco:
        return _limpar_nome(nome), endereco
    # parseaddr falhou (ex.: nome com ":"): usa a última palavra com "@".
    palavras = valor.split()
    for indice in range(len(palavras) - 1, -1, -1):
        if "@" in palavras[indice]:
            return _limpar_nome(" ".join(palavras[:indice])), palavras[indice].strip("<>,;")
    return _limpar_nome(valor), ""


def enderecos_em(valor: str) -> list[str]:
    """Todos os endereços de um cabeçalho que pode ter vários (ex.: Reply-To)."""
    valor = desdobrar(valor)
    entre_sinais = _ENTRE_SINAIS.findall(valor)
    if entre_sinais:
        return entre_sinais
    return [p.strip("<>,;\"'") for p in re.split(r"[\s,;]+", valor) if "@" in p]


def extrair_host(entrada: str) -> str | None:
    """Aceita domínio, URL ou endereço de e-mail (com ou sem nome) e devolve o host."""
    entrada = desdobrar(entrada)
    if not entrada:
        return None
    if _ENTRE_SINAIS.search(entrada) or ("@" in entrada and "://" not in entrada):
        _nome, endereco = separar_nome_e_endereco(entrada)
        host = endereco.rpartition("@")[2] or None
    elif "://" in entrada:
        try:
            host = urlsplit(entrada).hostname
        except ValueError:
            return None
    else:
        host = re.split(r"[/:?#\s]", entrada, maxsplit=1)[0]
    return validar_host(host) if host else None


def validar_host(host: str) -> str | None:
    """Normaliza o host e devolve None se ele não for um nome de domínio válido."""
    host = normalizar_host(host)
    if eh_ip(host) or not _HOST_VALIDO.match(host):
        return None
    return host


def _limpar_nome(nome: str) -> str:
    """Tira espaços e aspas do nome de exibição e decodifica =?utf-8?...?=."""
    return decodificar_cabecalho(nome.strip().strip("\"'").strip())
