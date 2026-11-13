"""Camada do "leitor" (IA): uma segunda opinião sobre o texto do e-mail.

O leitor pode explicar e SUBIR o risco, mas NUNCA baixar o que as regras já
encontraram. Hoje não há IA real ligada: só LeitorDesligado e LeitorFalso.
"""

from app.leitor.base import Leitor, PedidoLeitor, SugestaoLeitor, montar_pedido
from app.leitor.execucao import EstadoLeitor, ResultadoLeitor, consultar_leitor
from app.leitor.fabrica import obter_leitor, tempo_limite
from app.leitor.leitores import LeitorDesligado, LeitorFalso, LeitorNaoConfigurado
from app.leitor.validacao import validar_resposta

__all__ = [
    "EstadoLeitor",
    "Leitor",
    "LeitorDesligado",
    "LeitorFalso",
    "LeitorNaoConfigurado",
    "PedidoLeitor",
    "ResultadoLeitor",
    "SugestaoLeitor",
    "consultar_leitor",
    "montar_pedido",
    "obter_leitor",
    "tempo_limite",
    "validar_resposta",
]
