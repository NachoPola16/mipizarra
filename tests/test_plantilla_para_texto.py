# tests/test_plantilla_para_texto.py
"""El calentamiento y la vuelta a la calma estándar usan la plantilla validada; si ninguna
encaja, el diagrama se genera como hasta ahora."""
import pytest

from diagramas import _validar_diagrama
from plantillas import _CLAVES, plantilla_para_texto


@pytest.mark.parametrize("momento, clave", [(m, k) for m, pares in _CLAVES.items() for k, _ in pares])
def test_cada_palabra_clave_da_un_diagrama_valido(momento, clave):
    d = plantilla_para_texto(momento, f"Juego con {clave} para todos")
    assert d is not None
    assert _validar_diagrama(dict(d), "") is None


def test_un_juego_que_no_es_estandar_no_usa_plantilla():
    assert plantilla_para_texto("calentamiento", "Pañuelo con balón en el centro") is None


def test_la_palabra_clave_de_un_momento_no_vale_para_el_otro():
    assert plantilla_para_texto("calentamiento", "Estiramientos en línea") is None
    assert plantilla_para_texto("vuelta_a_la_calma", "Zigzag entre conos") is None


def test_el_numero_de_jugadores_se_ajusta_al_rango_de_la_plantilla():
    d = plantilla_para_texto("calentamiento", "Rondo", n_jugadores=30)
    assert len(d["jugadores_ataque"]) + len(d["jugadores_defensa"]) == 12
