"""Escolhe o leitor pela variável de ambiente ANZOL_LEITOR.

    ANZOL_LEITOR=desligado   (padrão) só as regras
    ANZOL_LEITOR=falso       resposta fixa, para testes e demonstração

Tempo limite do leitor, em segundos: ANZOL_LEITOR_TEMPO_LIMITE (padrão 10).
"""

import logging
import os

from app.leitor.base import Leitor
from app.leitor.leitores import LeitorDesligado, LeitorFalso, LeitorNaoConfigurado

logger = logging.getLogger("anzol.leitor")

VARIAVEL_LEITOR = "ANZOL_LEITOR"
VARIAVEL_TEMPO_LIMITE = "ANZOL_LEITOR_TEMPO_LIMITE"
TEMPO_LIMITE_PADRAO = 10.0
TEMPO_LIMITE_MINIMO = 0.1
TEMPO_LIMITE_MAXIMO = 60.0


def obter_leitor(nome: str | None = None) -> Leitor:
    """Devolve o leitor configurado. Valor desconhecido vira "leitor indisponível"."""
    if nome is None:
        nome = os.environ.get(VARIAVEL_LEITOR, "desligado")
    nome = nome.strip().lower() or "desligado"

    if nome == "desligado":
        return LeitorDesligado()
    if nome == "falso":
        return LeitorFalso()

    # ------------------------------------------------------------------------
    # PONTO DE LIGAÇÃO DO LEITOR REAL (provedor de IA) — ainda NÃO implementado.
    #
    # Para ligar uma IA de verdade:
    #   1. Crie uma classe em app/leitor/ com `nome`, `ativo = True` e
    #      `ler(pedido) -> str | dict`, que envie `pedido.instrucoes` como
    #      instrução de sistema e `pedido.dados` como mensagem do usuário, e
    #      devolva o texto da resposta SEM interpretá-lo (o Anzol valida).
    #   2. Leia a chave de API de uma variável de ambiente (nunca do código nem
    #      do repositório) e use um tempo limite próprio no cliente HTTP.
    #   3. Registre-a aqui, por exemplo:
    #          if nome == "real":
    #              return LeitorReal(chave=os.environ["ANZOL_LEITOR_CHAVE"])
    # ------------------------------------------------------------------------

    logger.warning("Valor desconhecido em %s; o leitor fica indisponível.", VARIAVEL_LEITOR)
    return LeitorNaoConfigurado()


def tempo_limite() -> float:
    """Tempo limite do leitor, em segundos, limitado a um intervalo seguro."""
    try:
        valor = float(os.environ.get(VARIAVEL_TEMPO_LIMITE, TEMPO_LIMITE_PADRAO))
    except ValueError:
        return TEMPO_LIMITE_PADRAO
    if valor != valor:  # NaN
        return TEMPO_LIMITE_PADRAO
    return min(max(valor, TEMPO_LIMITE_MINIMO), TEMPO_LIMITE_MAXIMO)
