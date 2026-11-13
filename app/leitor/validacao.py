"""Validação da resposta do leitor, que é tratada como dado NÃO CONFIÁVEL.

Uma IA pode ser enganada pelo próprio e-mail (injeção de prompt) ou simplesmente
devolver lixo. Por isso cada campo é conferido contra um esquema fixo:

- nivel: só BAIXO, MÉDIO, ALTO ou CRÍTICO; qualquer outra coisa é ignorada;
- explicacao: texto puro (sem HTML, sem caracteres de controle, sem links),
  com no máximo TAMANHO_MAXIMO_EXPLICACAO caracteres;
- indicios: no máximo MAXIMO_INDICIOS textos curtos.

Campo inválido é ignorado. Se nenhum campo for válido, a resposta inteira é
descartada (validar_resposta devolve None).
"""

import json
import re
from collections.abc import Mapping

from app.leitor.base import SugestaoLeitor
from app.risco import Nivel

TAMANHO_MAXIMO_EXPLICACAO = 500
TAMANHO_MAXIMO_INDICIO = 160
MAXIMO_INDICIOS = 5

# Respostas em texto maiores que isso nem são lidas.
TAMANHO_MAXIMO_RESPOSTA = 50_000

_NIVEIS = {
    "BAIXO": Nivel.BAIXO,
    "MÉDIO": Nivel.MEDIO,
    "MEDIO": Nivel.MEDIO,
    "ALTO": Nivel.ALTO,
    "CRÍTICO": Nivel.CRITICO,
    "CRITICO": Nivel.CRITICO,
}

_TAGS = re.compile(r"<[^<>]{0,500}>")
_LINKS = re.compile(r"(?i)\b(?:[a-z][a-z0-9+.-]*://|www\.|(?:javascript|vbscript|data|file):)\S+")
# Controle ASCII/C1, caracteres invisíveis e de direção de texto.
_CONTROLE = re.compile(r"[\x00-\x1f\x7f-\x9f\u200b-\u200f\u202a-\u202e\u2066-\u2069\ufeff]")


def validar_resposta(bruta: object) -> SugestaoLeitor | None:
    """Converte a resposta bruta numa SugestaoLeitor segura, ou None se for lixo."""
    dados = _como_dicionario(bruta)
    if dados is None:
        return None

    nivel = _validar_nivel(dados.get("nivel"))
    explicacao = texto_puro(dados.get("explicacao"), TAMANHO_MAXIMO_EXPLICACAO)
    indicios = _validar_indicios(dados.get("indicios"))
    if nivel is None and explicacao is None and not indicios:
        return None
    return SugestaoLeitor(nivel=nivel, explicacao=explicacao, indicios=indicios)


def texto_puro(valor: object, limite: int) -> str | None:
    """Deixa só texto simples, numa linha, sem links, cortado em `limite` caracteres."""
    if not isinstance(valor, str):
        return None
    valor = valor[: limite * 4]  # não processa textos gigantes à toa
    valor = _CONTROLE.sub(" ", valor)
    valor = _TAGS.sub(" ", valor)
    valor = _LINKS.sub("[link removido]", valor)
    valor = " ".join(valor.split())
    if len(valor) > limite:
        valor = valor[: limite - 1].rstrip() + "…"
    return valor or None


def _como_dicionario(bruta: object) -> Mapping | None:
    if isinstance(bruta, bytes):
        try:
            bruta = bruta.decode("utf-8")
        except UnicodeDecodeError:
            return None
    if isinstance(bruta, str):
        if len(bruta) > TAMANHO_MAXIMO_RESPOSTA:
            return None
        # IAs costumam embrulhar o JSON em ```json ... ```: pega do primeiro { ao último }.
        inicio, fim = bruta.find("{"), bruta.rfind("}")
        if inicio < 0 or fim <= inicio:
            return None
        try:
            bruta = json.loads(bruta[inicio : fim + 1])
        except (ValueError, RecursionError):
            return None
    return bruta if isinstance(bruta, Mapping) else None


def _validar_nivel(valor: object) -> Nivel | None:
    if not isinstance(valor, str) or len(valor) > 20:
        return None
    return _NIVEIS.get(valor.strip().upper())


def _validar_indicios(valor: object) -> tuple[str, ...]:
    if not isinstance(valor, list | tuple):
        return ()
    indicios: list[str] = []
    for item in valor[:50]:
        texto = texto_puro(item, TAMANHO_MAXIMO_INDICIO)
        if texto and texto not in indicios:
            indicios.append(texto)
        if len(indicios) == MAXIMO_INDICIOS:
            break
    return tuple(indicios)
