"""Cálculo do nível de risco a partir dos sinais encontrados.

Tabela de decisão (também documentada no README):

    Situação                                                   Nível
    ---------------------------------------------------------  --------
    Nenhum sinal                                               BAIXO
    Só sinais BAIXO, de menos de 3 tipos diferentes            BAIXO
    Só sinais BAIXO, de 3 ou mais tipos diferentes             MÉDIO
    Algum sinal MÉDIO (e nenhum ALTO)                          MÉDIO
    Um sinal ALTO, sem outro MÉDIO/ALTO de tipo diferente      ALTO
    Um sinal ALTO + outro sinal ALTO ou MÉDIO de outro tipo    CRÍTICO

Regras de projeto:
- Cada TIPO de sinal conta uma vez só, com o maior peso que apareceu. Dez links
  enganosos são um único sinal de "link enganoso"; senão um e-mail de marketing
  com muitos links de rastreamento chegaria a CRÍTICO sem motivo.
- CRÍTICO exige a COMBINAÇÃO de evidências diferentes. Nenhum sinal sozinho,
  por mais forte, leva a CRÍTICO.
- Não existe sinal "bom": nada (nem um "pass" de SPF/DKIM/DMARC) reduz o risco.
  Acrescentar sinais nunca baixa o nível.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from app.sinais.base import Peso, Sinal

# ---- Constantes fáceis de ajustar ----

# Quantos TIPOS diferentes de sinais BAIXO bastam para subir o nível para MÉDIO.
TIPOS_BAIXOS_PARA_MEDIO = 3

# Pesos que, somados a um sinal ALTO de outro tipo, levam a CRÍTICO.
PESOS_QUE_COMPLETAM_CRITICO = frozenset({Peso.MEDIO, Peso.ALTO})


class Nivel(StrEnum):
    BAIXO = "BAIXO"
    MEDIO = "MÉDIO"
    ALTO = "ALTO"
    CRITICO = "CRÍTICO"


@dataclass(frozen=True, slots=True)
class SinalConsiderado:
    """Um tipo de sinal, com o maior peso que apareceu e quantas vezes apareceu."""

    nome: str
    descricao: str
    peso: Peso
    ocorrencias: int


@dataclass(frozen=True, slots=True)
class AvaliacaoRisco:
    nivel: Nivel
    motivo: str
    sinais: tuple[SinalConsiderado, ...]


def agrupar_por_tipo(sinais: Iterable[Sinal]) -> list[SinalConsiderado]:
    """Junta os sinais do mesmo tipo, guardando o de maior peso.

    Resultado ordenado do mais pesado para o mais leve (empate: ordem de chegada).
    """
    maiores: dict[str, Sinal] = {}
    contagem: dict[str, int] = {}
    for sinal in sinais:
        contagem[sinal.nome] = contagem.get(sinal.nome, 0) + 1
        atual = maiores.get(sinal.nome)
        if atual is None or sinal.peso > atual.peso:
            maiores[sinal.nome] = sinal
    agrupados = [
        SinalConsiderado(s.nome, s.descricao, s.peso, contagem[s.nome]) for s in maiores.values()
    ]
    return sorted(agrupados, key=lambda s: s.peso, reverse=True)


def calcular_risco(sinais: Iterable[Sinal]) -> AvaliacaoRisco:
    """Aplica a tabela de decisão e explica o motivo em português."""
    tipos = agrupar_por_tipo(sinais)
    altos = [s for s in tipos if s.peso == Peso.ALTO]
    medios = [s for s in tipos if s.peso == Peso.MEDIO]
    baixos = [s for s in tipos if s.peso == Peso.BAIXO]

    def nomes(lista: list[SinalConsiderado]) -> str:
        return ", ".join(s.nome for s in lista)

    completam = [s for s in tipos if s.peso in PESOS_QUE_COMPLETAM_CRITICO]
    if altos and len(completam) >= 2:
        nivel = Nivel.CRITICO
        motivo = (
            f"Há um sinal de peso ALTO ({altos[0].nome}) combinado com outro sinal "
            f"forte de tipo diferente ({nomes([s for s in completam if s is not altos[0]])})."
        )
    elif altos:
        nivel = Nivel.ALTO
        motivo = (
            f"Há um sinal de peso ALTO ({altos[0].nome}), sem outro sinal forte que o confirme."
        )
    elif medios:
        nivel = Nivel.MEDIO
        motivo = f"Há sinal de peso MÉDIO ({nomes(medios)})."
    elif len(baixos) >= TIPOS_BAIXOS_PARA_MEDIO:
        nivel = Nivel.MEDIO
        motivo = f"Há {len(baixos)} tipos diferentes de sinais fracos ({nomes(baixos)})."
    elif baixos:
        nivel = Nivel.BAIXO
        motivo = f"Só há sinais fracos ({nomes(baixos)})."
    else:
        nivel = Nivel.BAIXO
        motivo = "Nenhum sinal de phishing foi encontrado pelas regras."

    return AvaliacaoRisco(nivel=nivel, motivo=motivo, sinais=tuple(tipos))
