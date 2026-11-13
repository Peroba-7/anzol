"""Leitores disponíveis hoje. Nenhum deles acessa a internet nem usa chave de API.

- LeitorDesligado: o padrão. Não faz nada; o resultado é só o das regras.
- LeitorFalso: devolve uma resposta fixa. Serve só para testes e demonstração.
- LeitorNaoConfigurado: usado quando ANZOL_LEITOR tem um valor desconhecido;
  sempre falha, e o Anzol avisa "leitor indisponível".
"""

import time

from app.leitor.base import PedidoLeitor

RESPOSTA_PADRAO_FALSA = {
    "nivel": "ALTO",
    "explicacao": "Resposta fixa do leitor falso, usada só em testes.",
    "indicios": ["resposta de teste"],
}

_PADRAO = object()


class LeitorDesligado:
    nome = "desligado"
    ativo = False

    def ler(self, pedido: PedidoLeitor) -> object:
        return None


class LeitorFalso:
    """Leitor de mentira, com resposta, erro ou demora escolhidos pelo teste."""

    nome = "falso"
    ativo = True

    def __init__(
        self,
        resposta: object = _PADRAO,
        *,
        erro: Exception | None = None,
        demora: float = 0.0,
    ) -> None:
        self.resposta = dict(RESPOSTA_PADRAO_FALSA) if resposta is _PADRAO else resposta
        self.erro = erro
        self.demora = demora
        self.ultimo_pedido: PedidoLeitor | None = None  # para os testes conferirem

    def ler(self, pedido: PedidoLeitor) -> object:
        self.ultimo_pedido = pedido
        if self.demora:
            time.sleep(self.demora)
        if self.erro is not None:
            raise self.erro
        return self.resposta


class LeitorNaoConfigurado:
    nome = "desconhecido"
    ativo = True

    def ler(self, pedido: PedidoLeitor) -> object:
        raise RuntimeError("ANZOL_LEITOR tem um valor desconhecido.")
