"""Leitura do e-mail bruto (cabeçalhos e corpo HTML), só com a biblioteca padrão.

Nenhuma função aqui levanta erro por causa de um e-mail malformado: o pior caso
é devolver "nada encontrado". O conteúdo do e-mail é só dado, nunca instrução.
"""

from email import policy
from email.message import Message
from email.parser import Parser


def _normalizar(email_bruto: str | None) -> str:
    """Troca as quebras de linha do Windows e tira linhas vazias do início."""
    return (email_bruto or "").replace("\r\n", "\n").lstrip("\n")


def ler_cabecalhos(email_bruto: str | None) -> Message:
    """Lê só os cabeçalhos, sem nunca levantar erro.

    Usa o modo compat32, que devolve os valores como texto puro, sem tentar
    interpretá-los; assim um cabeçalho malformado não derruba a análise.
    """
    return Parser(policy=policy.compat32).parsestr(_normalizar(email_bruto), headersonly=True)


def primeiro_cabecalho(mensagem: Message, nome: str) -> str | None:
    """Primeira ocorrência (a mais acima) de um cabeçalho, ignorando maiúsculas."""
    valores = mensagem.get_all(nome) or []
    return str(valores[0]) if valores else None


def extrair_htmls(email_bruto: str | None) -> list[str]:
    """Devolve o conteúdo de cada parte text/html do corpo (anexos são ignorados).

    Decodifica base64, quoted-printable e o charset declarado. Se uma parte
    estiver quebrada, ela é pulada; se o e-mail inteiro estiver quebrado
    (ex.: aninhamento absurdo de partes), devolve o que conseguiu ler.
    """
    htmls: list[str] = []
    try:
        mensagem = Parser(policy=policy.default).parsestr(_normalizar(email_bruto))
        for parte in mensagem.walk():
            if parte.get_content_type() != "text/html" or parte.is_attachment():
                continue
            htmls.append(_conteudo_texto(parte))
    except Exception:  # noqa: BLE001 - e-mail malformado não pode derrubar a análise
        pass
    return htmls


def _conteudo_texto(parte: Message) -> str:
    try:
        return parte.get_content()  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001 - charset desconhecido ou codificação quebrada
        bruto = parte.get_payload(decode=True)
        if isinstance(bruto, bytes):
            return bruto.decode("utf-8", errors="replace")
        return str(parte.get_payload())
