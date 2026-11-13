"""Tipos comuns a todos os sinais de phishing."""

from dataclasses import dataclass
from enum import IntEnum


class Peso(IntEnum):
    """Quanto um sinal contribui para o nível de risco final.

    Os valores numéricos servirão para somar pontos quando o classificador
    de risco for criado. Regra de projeto: um sinal de peso BAIXO ou MEDIO,
    sozinho, nunca pode levar o resultado ao nível CRÍTICO; para isso é
    preciso a combinação de vários sinais diferentes ou de um sinal ALTO.
    """

    BAIXO = 10
    MEDIO = 25
    ALTO = 50


@dataclass(frozen=True, slots=True)
class Sinal:
    """Um indício de phishing encontrado na análise."""

    nome: str
    descricao: str
    peso: Peso
