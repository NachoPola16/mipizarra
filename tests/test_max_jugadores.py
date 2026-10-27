# tests/test_max_jugadores.py
"""Filtro «máximo de jugadores»: solo entran las fichas cuyo jugadores_minimos cabe en el grupo."""
import ejercicios as ej
from main import SesionRequest
import pytest


def _fichas():
    return [{"id": "a", "jugadores_minimos": 2}, {"id": "b", "jugadores_minimos": 6}, {"id": "c"}, {"id": "d", "jugadores_minimos": 12}]


def test_sin_limite_devuelve_todo():
    assert ej.limitar_por_jugadores(_fichas(), None) == _fichas()


def test_se_descartan_las_que_necesitan_mas_jugadores():
    assert [e["id"] for e in ej.limitar_por_jugadores(_fichas(), 6)] == ["a", "b", "c"]
    assert [e["id"] for e in ej.limitar_por_jugadores(_fichas(), 2)] == ["a", "c"]


def test_la_biblioteca_real_deja_fichas_con_pocos_jugadores():
    biblioteca = ej.cargar_ejercicios()
    reducida = ej.limitar_por_jugadores(biblioteca, 4)
    assert 0 < len(reducida) < len(biblioteca)
    assert all((e.get("jugadores_minimos") or 1) <= 4 for e in reducida)


def test_el_limite_se_valida_en_la_peticion():
    assert SesionRequest(objetivo="bote", max_jugadores=8).max_jugadores == 8
    assert SesionRequest(objetivo="bote").max_jugadores is None
    with pytest.raises(ValueError):
        SesionRequest(objetivo="bote", max_jugadores=1)
