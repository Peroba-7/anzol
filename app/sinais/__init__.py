"""Sinais de phishing verificados pelo fiscal de regras do Anzol."""

from app.sinais.base import Peso, Sinal
from app.sinais.link_enganoso import detectar_links_enganosos

__all__ = ["Peso", "Sinal", "detectar_links_enganosos"]
