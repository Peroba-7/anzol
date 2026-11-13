"""Testes da tabela de decisão do nível de risco."""

from itertools import combinations

import pytest

from app.risco import TIPOS_BAIXOS_PARA_MEDIO, Nivel, calcular_risco
from app.sinais.base import Peso, Sinal

ORDEM = [Nivel.BAIXO, Nivel.MEDIO, Nivel.ALTO, Nivel.CRITICO]


def s(nome: str, peso: Peso) -> Sinal:
    return Sinal(nome=nome, descricao=f"descrição de {nome}", peso=peso)


def nivel(*sinais: Sinal) -> Nivel:
    return calcular_risco(sinais).nivel


# ---------- Tabela de decisão ----------


def test_nenhum_sinal_e_baixo():
    avaliacao = calcular_risco([])
    assert avaliacao.nivel == Nivel.BAIXO
    assert avaliacao.sinais == ()
    assert avaliacao.motivo


def test_sinais_baixos():
    assert nivel(s("a", Peso.BAIXO)) == Nivel.BAIXO
    assert nivel(s("a", Peso.BAIXO), s("b", Peso.BAIXO)) == Nivel.BAIXO


def test_tres_tipos_baixos_diferentes_viram_medio():
    assert TIPOS_BAIXOS_PARA_MEDIO == 3
    assert nivel(s("a", Peso.BAIXO), s("b", Peso.BAIXO), s("c", Peso.BAIXO)) == Nivel.MEDIO


def test_tres_baixos_do_mesmo_tipo_continuam_baixo():
    assert nivel(*[s("a", Peso.BAIXO)] * 3) == Nivel.BAIXO


def test_sinal_medio():
    assert nivel(s("a", Peso.MEDIO)) == Nivel.MEDIO
    assert nivel(s("a", Peso.MEDIO), s("b", Peso.MEDIO), s("c", Peso.BAIXO)) == Nivel.MEDIO


def test_sinal_alto_sozinho_e_alto():
    assert nivel(s("a", Peso.ALTO)) == Nivel.ALTO
    assert nivel(s("a", Peso.ALTO), s("b", Peso.BAIXO)) == Nivel.ALTO


def test_alto_com_baixos_nao_chega_a_critico():
    """Três BAIXOS valem MÉDIO no nível, mas não completam o CRÍTICO."""
    sinais = [s("a", Peso.ALTO), s("b", Peso.BAIXO), s("c", Peso.BAIXO), s("d", Peso.BAIXO)]
    assert nivel(*sinais) == Nivel.ALTO


def test_critico_so_com_alto_mais_outro_forte_de_tipo_diferente():
    assert nivel(s("a", Peso.ALTO), s("b", Peso.MEDIO)) == Nivel.CRITICO
    assert nivel(s("a", Peso.ALTO), s("b", Peso.ALTO)) == Nivel.CRITICO


def test_mesmo_tipo_repetido_nao_chega_a_critico():
    assert nivel(s("a", Peso.ALTO), s("a", Peso.ALTO)) == Nivel.ALTO
    assert nivel(s("a", Peso.ALTO), s("a", Peso.MEDIO)) == Nivel.ALTO
    assert nivel(*[s("a", Peso.MEDIO)] * 10) == Nivel.MEDIO


def test_dois_medios_sem_alto_nao_chegam_a_critico():
    assert nivel(s("a", Peso.MEDIO), s("b", Peso.MEDIO), s("c", Peso.MEDIO)) == Nivel.MEDIO


# ---------- Agrupamento por tipo ----------


def test_dez_sinais_do_mesmo_tipo_contam_uma_vez():
    avaliacao = calcular_risco([s("link_enganoso", Peso.MEDIO)] * 10)
    assert len(avaliacao.sinais) == 1
    assert avaliacao.sinais[0].ocorrencias == 10
    assert avaliacao.nivel == Nivel.MEDIO


def test_tipo_fica_com_o_maior_peso_e_sua_descricao():
    sinais = [
        Sinal("dominio", "fraco", Peso.MEDIO),
        Sinal("dominio", "forte", Peso.ALTO),
        Sinal("dominio", "fraco de novo", Peso.MEDIO),
    ]
    (unico,) = calcular_risco(sinais).sinais
    assert (unico.peso, unico.descricao, unico.ocorrencias) == (Peso.ALTO, "forte", 3)


def test_sinais_saem_ordenados_do_mais_pesado():
    avaliacao = calcular_risco([s("b", Peso.BAIXO), s("a", Peso.ALTO), s("m", Peso.MEDIO)])
    assert [x.nome for x in avaliacao.sinais] == ["a", "m", "b"]


# ---------- Nada reduz o risco ----------

TODOS = [
    s("a1", Peso.ALTO),
    s("a2", Peso.ALTO),
    s("m1", Peso.MEDIO),
    s("m2", Peso.MEDIO),
    s("b1", Peso.BAIXO),
    s("b2", Peso.BAIXO),
    s("b3", Peso.BAIXO),
    s("a1", Peso.MEDIO),  # mesmo tipo de a1, mais fraco
]


@pytest.mark.parametrize("tamanho", range(len(TODOS)))
def test_acrescentar_sinal_nunca_reduz_o_nivel(tamanho):
    """Para qualquer combinação, somar mais um sinal nunca baixa o nível."""
    for base in combinations(TODOS, tamanho):
        nivel_base = ORDEM.index(nivel(*base))
        for extra in TODOS:
            assert ORDEM.index(nivel(*base, extra)) >= nivel_base, (base, extra)
