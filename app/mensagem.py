"""Leitura do e-mail bruto (cabeçalhos e corpo HTML), só com a biblioteca padrão.

Nenhuma função aqui levanta erro por causa de um e-mail malformado: o pior caso
é devolver "nada encontrado". O conteúdo do e-mail é só dado, nunca instrução.
"""

import re
from email import policy
from email.message import Message
from email.parser import BytesParser, Parser
from html.parser import HTMLParser

from app.enderecos import decodificar_cabecalho


def _normalizar(email_bruto: str | None) -> str:
    """Troca as quebras de linha do Windows e tira linhas vazias do início."""
    return (email_bruto or "").replace("\r\n", "\n").lstrip("\n")


def ler_cabecalhos(email_bruto: str | None) -> Message:
    """Lê só os cabeçalhos, sem nunca levantar erro.

    Usa o modo compat32, que devolve os valores como texto puro, sem tentar
    interpretá-los; assim um cabeçalho malformado não derruba a análise.
    """
    return Parser(policy=policy.compat32).parsestr(_normalizar(email_bruto), headersonly=True)


def _ler_mensagem(email_bruto: str | None) -> Message:
    """Lê o e-mail inteiro. Usa bytes para que corpos em UTF-8 sem codificação
    de transferência (8 bits) sejam decodificados corretamente."""
    dados = _normalizar(email_bruto).encode("utf-8", errors="surrogateescape")
    return BytesParser(policy=policy.default).parsebytes(dados)


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
        mensagem = _ler_mensagem(email_bruto)
        for parte in mensagem.walk():
            if parte.get_content_type() != "text/html" or parte.is_attachment():
                continue
            htmls.append(_conteudo_texto(parte))
    except Exception:  # noqa: BLE001 - e-mail malformado não pode derrubar a análise
        pass
    return htmls


def extrair_texto_limpo(email_bruto: str | None) -> str:
    """Remetente, assunto e corpo em texto simples, para o leitor (IA) ler.

    Junta as partes text/plain e o texto visível e escondido das partes
    text/html (sem as tags, sem scripts e estilos). Anexos são ignorados.
    O resultado continua sendo DADO não confiável: quem o envia ao leitor
    deve delimitá-lo e cortar o tamanho (ver app/leitor/base.py).
    """
    cabecalhos = ler_cabecalhos(email_bruto)
    linhas = []
    for rotulo, nome in (("De", "From"), ("Assunto", "Subject")):
        valor = primeiro_cabecalho(cabecalhos, nome)
        if valor:
            linhas.append(f"{rotulo}: {decodificar_cabecalho(valor)}")

    corpos: list[str] = []
    try:
        mensagem = _ler_mensagem(email_bruto)
        for parte in mensagem.walk():
            tipo = parte.get_content_type()
            if tipo not in ("text/plain", "text/html") or parte.is_attachment():
                continue
            texto = _conteudo_texto(parte)
            corpos.append(_html_para_texto(texto) if tipo == "text/html" else texto)
    except Exception:  # noqa: BLE001 - e-mail malformado não pode derrubar a análise
        pass

    vistos: set[str] = set()
    for corpo in corpos:
        corpo = _limpar_espacos(corpo)
        if corpo and corpo not in vistos:
            vistos.add(corpo)
            linhas.append(corpo)
    return "\n\n".join(linhas)


class _SoTexto(HTMLParser):
    _IGNORAR = frozenset({"script", "style"})
    # Tags que ficam dentro da mesma linha de texto.
    _EM_LINHA = frozenset(
        {"a", "abbr", "b", "code", "em", "font", "i", "small", "span", "strong", "sub", "sup", "u"}
    )

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.partes: list[str] = []
        self._ignorando = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._IGNORAR:
            self._ignorando += 1
        self._quebra(tag)

    def handle_endtag(self, tag):
        if tag in self._IGNORAR and self._ignorando:
            self._ignorando -= 1
        self._quebra(tag)

    def _quebra(self, tag: str) -> None:
        self.partes.append(" " if tag in self._EM_LINHA else "\n")

    def handle_data(self, data):
        if not self._ignorando:
            self.partes.append(data)


def _html_para_texto(html: str) -> str:
    leitor = _SoTexto()
    try:
        leitor.feed(html)
        leitor.close()
    except Exception:  # noqa: BLE001 - HTML quebrado: usa o que deu para ler
        pass
    return "".join(leitor.partes)


_CONTROLE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


def _limpar_espacos(texto: str) -> str:
    texto = _CONTROLE.sub(" ", texto)
    linhas = (" ".join(linha.split()) for linha in texto.split("\n"))
    return "\n".join(linha for linha in linhas if linha)


def _conteudo_texto(parte: Message) -> str:
    try:
        return parte.get_content()  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001 - charset desconhecido ou codificação quebrada
        bruto = parte.get_payload(decode=True)
        if isinstance(bruto, bytes):
            return bruto.decode("utf-8", errors="replace")
        return str(parte.get_payload())
