"""Garante que os e-mails da pasta exemplos/ continuam mostrando o que prometem.

Se uma regra mudar e um exemplo passar a dar outro resultado, este teste avisa,
para o README e a demonstração não ficarem desatualizados.
"""

import re
from pathlib import Path

import pytest

from app.analise import analisar_email
from app.risco import Nivel

PASTA = Path(__file__).resolve().parents[1] / "exemplos"

ESPERADO = {
    "01-golpe-obvio.eml": (
        Nivel.CRITICO,
        {
            "dmarc_falhou",
            "dominio_parecido_com_marca",
            "link_enganoso",
            "reply_to_de_outro_dominio",
            "dkim_ausente",
            "return_path_de_outro_dominio",
        },
    ),
    "02-legitimo.eml": (Nivel.BAIXO, set()),
    # Limitação conhecida: golpe com domínio próprio e tudo configurado passa limpo.
    "03-golpe-bem-feito.eml": (Nivel.BAIXO, set()),
    # Falso positivo conhecido: listas de discussão quebram DKIM e DMARC.
    "04-lista-de-discussao.eml": (
        Nivel.CRITICO,
        {
            "dmarc_falhou",
            "dkim_falhou",
            "reply_to_de_outro_dominio",
            "return_path_de_outro_dominio",
        },
    ),
}


def test_todos_os_exemplos_estao_cobertos():
    assert {p.name for p in PASTA.glob("*.eml")} == set(ESPERADO)


@pytest.mark.parametrize("nome", sorted(ESPERADO))
def test_exemplo_da_o_resultado_documentado(nome):
    nivel, sinais = ESPERADO[nome]
    avaliacao = analisar_email((PASTA / nome).read_text(encoding="utf-8"))
    assert avaliacao.nivel == nivel
    assert {s.nome for s in avaliacao.sinais} == sinais


# Domínio que vem depois de @, ://, =, "from ", "by " ou "www.".
_DOMINIO = re.compile(r"(?:@|://|=|\bfrom |\bby |www\.)([a-z0-9-]+(?:\.[a-z0-9-]+)+)")
_TLDS_REAIS = re.compile(r"\.(?:com|net|org|br|io|gov|edu|xyz|info|app|dev)\b")


@pytest.mark.parametrize("nome", sorted(ESPERADO))
def test_exemplo_so_usa_dominios_ficticios(nome):
    texto = (PASTA / nome).read_text(encoding="utf-8").lower()
    for dominio in _DOMINIO.findall(texto):
        e_ip = all(parte.isdigit() for parte in dominio.split("."))
        assert dominio.endswith(".example") or e_ip, dominio
    assert not _TLDS_REAIS.search(texto), "domínio com final real encontrado"
