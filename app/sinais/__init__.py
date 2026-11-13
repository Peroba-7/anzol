"""Sinais de phishing verificados pelo fiscal de regras do Anzol."""

from app.sinais.base import Peso, Sinal
from app.sinais.dominio_parecido import detectar_dominios_parecidos
from app.sinais.link_enganoso import detectar_links_enganosos

__all__ = ["Peso", "Sinal", "detectar_dominios_parecidos", "detectar_links_enganosos"]
