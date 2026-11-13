"""Chama o leitor com tempo limite e trata qualquer falha.

Se o leitor der erro, demorar demais ou devolver lixo, o Anzol segue só com as
regras e avisa "leitor indisponível". Os logs nunca recebem o conteúdo do
e-mail nem a mensagem do erro (ela poderia conter trechos do e-mail): só o nome
do leitor e o tipo do erro.
"""

import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from enum import StrEnum

from app.leitor.base import Leitor, PedidoLeitor, SugestaoLeitor
from app.leitor.validacao import validar_resposta

logger = logging.getLogger("anzol.leitor")

# Threads só para o leitor. Se ele travar, a análise segue depois do tempo limite.
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="anzol-leitor")


class EstadoLeitor(StrEnum):
    DESLIGADO = "desligado"
    OK = "ok"
    ERRO = "erro"
    TEMPO_ESGOTADO = "tempo_esgotado"
    RESPOSTA_INVALIDA = "resposta_invalida"


_AVISOS = {
    EstadoLeitor.ERRO: "Leitor indisponível (erro): o resultado usa só as regras.",
    EstadoLeitor.TEMPO_ESGOTADO: (
        "Leitor indisponível (demorou demais): o resultado usa só as regras."
    ),
    EstadoLeitor.RESPOSTA_INVALIDA: (
        "Leitor indisponível (resposta inválida): o resultado usa só as regras."
    ),
}


@dataclass(frozen=True, slots=True)
class ResultadoLeitor:
    nome: str
    estado: EstadoLeitor
    sugestao: SugestaoLeitor | None = None

    @property
    def aviso(self) -> str | None:
        """Aviso "leitor indisponível" quando o leitor estava ligado mas falhou."""
        return _AVISOS.get(self.estado)


def consultar_leitor(leitor: Leitor, pedido: PedidoLeitor, tempo_limite: float) -> ResultadoLeitor:
    """Pede a opinião do leitor. Nunca levanta erro."""
    if not leitor.ativo:
        return ResultadoLeitor(leitor.nome, EstadoLeitor.DESLIGADO)

    futuro = _executor.submit(leitor.ler, pedido)
    try:
        bruta = futuro.result(timeout=tempo_limite)
    except TimeoutError:
        futuro.cancel()
        logger.warning("Leitor %s passou do tempo limite (%.1f s).", leitor.nome, tempo_limite)
        return ResultadoLeitor(leitor.nome, EstadoLeitor.TEMPO_ESGOTADO)
    except Exception as erro:  # noqa: BLE001 - qualquer falha do leitor cai para as regras
        logger.warning("Leitor %s falhou (%s).", leitor.nome, type(erro).__name__)
        return ResultadoLeitor(leitor.nome, EstadoLeitor.ERRO)

    try:
        sugestao = validar_resposta(bruta)
    except Exception as erro:  # noqa: BLE001 - resposta estranha não derruba a análise
        logger.warning(
            "Resposta do leitor %s quebrou a validação (%s).", leitor.nome, type(erro).__name__
        )
        sugestao = None
    if sugestao is None:
        logger.warning("Leitor %s devolveu resposta inválida.", leitor.nome)
        return ResultadoLeitor(leitor.nome, EstadoLeitor.RESPOSTA_INVALIDA)
    return ResultadoLeitor(leitor.nome, EstadoLeitor.OK, sugestao)
