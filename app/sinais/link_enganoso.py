"""Sinal "link enganoso": o texto do link mostra um site, mas leva a outro.

Exemplo de golpe:

    <a href="https://banc0-seguro.xyz/login">meubanco.com.br</a>

A pessoa lê "meubanco.com.br", mas ao clicar vai para "banc0-seguro.xyz".

Segurança: este módulo só LÊ o texto do HTML. Nenhum link é aberto, baixado
ou consultado, e nada no conteúdo do e-mail é tratado como instrução.

Peso: links de rastreamento de e-mail marketing legítimo também têm texto e
destino diferentes (o clique passa por um servidor de estatísticas antes de
chegar ao site). Por isso este sinal tem peso MÉDIO e, sozinho, NUNCA deve
levar a análise ao nível CRÍTICO. Ele é um indício, não uma prova.
"""

import re
from html.parser import HTMLParser
from urllib.parse import urlsplit

from app.dominios import dominio_principal, eh_ip, normalizar_host
from app.sinais.base import Peso, Sinal

NOME = "link_enganoso"

# Peso fixo e propositalmente moderado (ver explicação no topo do arquivo).
PESO = Peso.MEDIO

# Texto que "parece um endereço": esquema opcional, host com ponto e domínio
# de topo com letras (ou punycode), seguido opcionalmente de porta e caminho.
# Não aceita espaços, então "Clique aqui" ou "Acesse meubanco.com.br" ficam de fora.
_PARECE_ENDERECO = re.compile(
    r"""^
    (?:[a-z][a-z0-9+.-]*://)?                       # esquema opcional (https://)
    (?:[^\s/@]+@)?                                  # usuário opcional (raro)
    (?P<host>
        (?:[\w-]+\.)+(?:[^\W\d_]{2,}|xn--[\w-]+)    # nome.com.br
        |\d{1,3}(?:\.\d{1,3}){3}                     # ou IPv4
    )
    \.?                                             # ponto final opcional
    (?::\d+)?                                       # porta opcional
    (?:[/?\#]\S*)?                                  # caminho opcional
    $""",
    re.IGNORECASE | re.VERBOSE,
)


class _ColetorDeLinks(HTMLParser):
    """Percorre o HTML e junta pares (href, texto visível) de cada <a>."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self._href_atual: str | None = None
        self._texto_atual: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        self._fechar_link()  # <a> sem fechamento antes de outro <a>
        self._href_atual = dict(attrs).get("href") or ""
        self._texto_atual = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "a":
            self._fechar_link()

    def handle_data(self, data: str) -> None:
        if self._href_atual is not None:
            self._texto_atual.append(data)

    def close(self) -> None:
        super().close()
        self._fechar_link()

    def _fechar_link(self) -> None:
        if self._href_atual is not None:
            self.links.append((self._href_atual, "".join(self._texto_atual)))
        self._href_atual = None
        self._texto_atual = []


def _host_do_texto(texto: str) -> str | None:
    """Se o texto visível parece um endereço, devolve o host dele."""
    texto = " ".join(texto.split())  # junta quebras de linha e espaços extras
    correspondencia = _PARECE_ENDERECO.match(texto)
    if not correspondencia:
        return None
    return normalizar_host(correspondencia.group("host"))


def _host_do_href(href: str) -> str | None:
    """Devolve o host de destino de um href http(s), ou None se não houver."""
    try:
        partes = urlsplit(href.strip())
        host = partes.hostname  # já ignora "usuario@" e a porta
    except ValueError:
        return None
    if partes.scheme.lower() not in ("http", "https", "") or not host:
        return None  # mailto:, tel:, javascript:, âncoras e links relativos
    return normalizar_host(host)


def _mesmo_dono(host_a: str, host_b: str) -> bool:
    """Compara dois hosts pelo domínio principal (IPs são comparados inteiros)."""
    if eh_ip(host_a) or eh_ip(host_b):
        return host_a == host_b
    return dominio_principal(host_a) == dominio_principal(host_b)


def detectar_links_enganosos(html: str) -> list[Sinal]:
    """Analisa o HTML de um e-mail e devolve um sinal por link enganoso.

    Links repetidos (mesmo domínio no texto e no destino) geram um só sinal.
    """
    coletor = _ColetorDeLinks()
    coletor.feed(html)
    coletor.close()

    sinais: list[Sinal] = []
    pares_vistos: set[tuple[str, str]] = set()

    for href, texto in coletor.links:
        if href.strip().lower().startswith("mailto:"):
            continue
        host_texto = _host_do_texto(texto)
        host_destino = _host_do_href(href)
        if host_texto is None or host_destino is None:
            continue
        if _mesmo_dono(host_texto, host_destino):
            continue

        par = (dominio_principal(host_texto), dominio_principal(host_destino))
        if par in pares_vistos:
            continue
        pares_vistos.add(par)

        dominio_texto, dominio_destino = par
        sinais.append(
            Sinal(
                nome=NOME,
                descricao=(
                    f"O link mostra o endereço “{dominio_texto}”, mas na verdade "
                    f"leva para “{dominio_destino}”. Isso é comum em golpes, mas "
                    "também acontece em links de rastreamento de e-mail marketing."
                ),
                peso=PESO,
            )
        )

    return sinais
