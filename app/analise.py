"""Análise completa de um e-mail bruto: roda todos os sinais e calcula o risco.

Tudo é offline. Nenhum link é aberto, nenhum domínio é consultado e o conteúdo
do e-mail não é guardado nem registrado em log: ele só existe na memória
enquanto a análise roda. Qualquer texto do e-mail é tratado como dado.
"""

from collections.abc import Iterable

from app.mensagem import extrair_htmls, ler_cabecalhos, primeiro_cabecalho
from app.risco import AvaliacaoRisco, calcular_risco
from app.sinais import (
    Sinal,
    detectar_dominios_parecidos,
    detectar_links_enganosos,
    detectar_sinais_de_cabecalho,
)
from app.sinais.link_enganoso import extrair_links


class EmailInvalido(ValueError):
    """A entrada não parece um e-mail. A mensagem nunca inclui o conteúdo enviado."""


def analisar_email(email_bruto: str, marcas: Iterable[str] | None = None) -> AvaliacaoRisco:
    """Roda os sinais de link enganoso, domínio parecido e cabeçalhos."""
    remetente = primeiro_cabecalho(ler_cabecalhos(email_bruto), "From")
    if not remetente or not remetente.strip():
        raise EmailInvalido(
            "Não encontrei o cabeçalho From (remetente). Envie o e-mail completo, "
            "com os cabeçalhos (em geral pela opção “Mostrar original”)."
        )
    marcas = tuple(marcas) if marcas is not None else None

    sinais: list[Sinal] = []
    destinos: list[str] = []
    for html in extrair_htmls(email_bruto):
        sinais.extend(detectar_links_enganosos(html))
        destinos.extend(href for href, _texto in extrair_links(html))

    sinais.extend(detectar_dominios_parecidos(remetente, destinos, marcas=marcas))
    sinais.extend(detectar_sinais_de_cabecalho(email_bruto, marcas=marcas))
    return calcular_risco(sinais)
