# tests/test_cobertura_temas.py
"""Cada tema que pide el entrenador («bote» y «bomba sobre un pie» son dos) se trabaja de verdad en la sesión, sin que
uno acapare los huecos; «técnica individual» es el género, no un tema."""
import random

import pytest

from ejercicios import (
    _centrada_en, elegir_calentamiento, elegir_fichas, temas_del_objetivo, temas_sin_cubrir,
)

OBJETIVO = "técnica individual: bote y bomba sobre un pie"


def test_el_objetivo_se_separa_en_temas_y_el_genero_no_cuenta():
    assert temas_del_objetivo(OBJETIVO) == [{"bote"}, {"bomb"}]
    assert temas_del_objetivo("tiro en suspensión y defensa del bloqueo") == [{"tiro", "suspens"}, {"defe", "bloq"}]


@pytest.mark.parametrize("edad,n", [("U10", 7), ("U12", 7), ("U14", 6), ("U16", 5)])
def test_cada_tema_pedido_tiene_una_ficha_centrada(ejercicios, edad, n):
    for semilla in range(5):
        fichas = elegir_fichas(ejercicios, edad, OBJETIVO, n, azar=random.Random(semilla))
        assert temas_sin_cubrir(fichas, OBJETIVO) == [], (edad, semilla)


@pytest.mark.parametrize("edad", ["U10", "U12"])
def test_ningun_tema_acapara_la_sesion(ejercicios, edad):
    for semilla in range(5):
        fichas = [f for f in elegir_fichas(ejercicios, edad, OBJETIVO, 7, azar=random.Random(semilla)) if f]
        bote = sum(_centrada_en(f, {"bote"}, True) for f in fichas)
        bomba = sum(_centrada_en(f, {"bomb"}, True) for f in fichas)
        assert abs(bote - bomba) <= 2 and bote >= 2 and bomba >= 2, (edad, semilla, bote, bomba)


def test_el_calentamiento_prefiere_el_que_trata_el_tema(ejercicios):
    for semilla in range(8):
        cal = elegir_calentamiento(ejercicios, "U10", "bote", azar=random.Random(semilla))
        assert _centrada_en(cal, {"bote"}) or "bote" in cal["descripcion"].lower()
