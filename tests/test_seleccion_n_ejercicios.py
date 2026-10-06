# tests/test_seleccion_n_ejercicios.py
"""seleccionar_ejercicios: elige n ejercicios de la biblioteca (n entre 3 y 6 en la parte principal)
con el mismo arco que antes: empieza sin oposición y termina con oposición igualada."""
import pytest

from ejercicios import (
    _nivel_oposicion, filtrar_ejercicios, nivel_objetivo, seleccionar_ejercicios,
    seleccionar_tres_ejercicios,
)

EDADES = ["U8", "U10", "U12", "U14", "U16", "U18", "Senior"]
OBJETIVOS = ["bote", "1c1", "defensa", "tiro", "contraataque", "pase", "transición"]


def _ej(nombre, fase="OBJETIVO"):
    return {"nombre": nombre, "descripcion": "", "objetivos": {"tacticos": []}, "_fase": fase}


# Un ejercicio por nivel de oposición: 3c0 (0), 2c1 (1), 3c3 (2)
def _pool():
    return [
        _ej("Pases 3c0 en triángulo", "ANALÍTICO"), _ej("Pases 4c0 en línea", "ANALÍTICO"),
        _ej("2c1 en transición"), _ej("3c2 por carriles"),
        _ej("3c3 en cuarto de pista"), _ej("5c5 desde el rebote"),
    ]


@pytest.mark.parametrize("n,esperado", [
    (3, [0, 1, 2]), (4, [0, 0, 1, 2]), (5, [0, 0, 1, 1, 2]), (6, [0, 0, 1, 1, 2, 2]),
])
def test_el_arco_de_oposicion_por_posicion(n, esperado):
    assert [nivel_objetivo(i, n) for i in range(n)] == esperado


@pytest.mark.parametrize("n", [3, 4, 5, 6])
def test_devuelve_exactamente_n_sin_repetir(n):
    elegidos = seleccionar_ejercicios(_pool(), n)
    assert len(elegidos) == n
    usados = [e["nombre"] for e in elegidos if e]
    assert len(usados) == len(set(usados))


def test_los_ejercicios_siguen_el_arco_de_oposicion():
    elegidos = seleccionar_ejercicios(_pool(), 6)
    assert [_nivel_oposicion(e) for e in elegidos] == [0, 0, 1, 1, 2, 2]


def test_si_faltan_ejercicios_el_resto_de_huecos_queda_a_none():
    elegidos = seleccionar_ejercicios(_pool()[:2], 5)
    assert len(elegidos) == 5
    assert [e is None for e in elegidos] == [False, False, True, True, True]


def test_sin_candidatos_todo_es_none():
    assert seleccionar_ejercicios([], 4) == [None] * 4


def test_con_tres_se_comporta_como_la_seleccion_antigua_en_la_biblioteca_real(ejercicios):
    # misma elección que seleccionar_tres_ejercicios para cualquier edad y objetivo
    for edad in EDADES:
        for objetivo in OBJETIVOS:
            relevantes = filtrar_ejercicios([dict(e) for e in ejercicios], edad, objetivo)
            antiguo = [e["id"] if e else None for e in seleccionar_tres_ejercicios(relevantes)]
            nuevo = [e["id"] if e else None for e in seleccionar_ejercicios(relevantes, 3)]
            assert nuevo == antiguo, (edad, objetivo)


@pytest.mark.parametrize("edad", EDADES)
@pytest.mark.parametrize("objetivo", OBJETIVOS)
@pytest.mark.parametrize("n", [3, 4, 5, 6])
def test_en_la_biblioteca_real_son_n_sin_repetir_y_de_la_edad(ejercicios, edad, objetivo, n):
    relevantes = filtrar_ejercicios(ejercicios, edad, objetivo)
    elegidos = seleccionar_ejercicios(relevantes, n)
    assert len(elegidos) == n
    ids = [e["id"] for e in elegidos if e]
    assert len(ids) == len(set(ids))
    assert all(e["id"] in {r["id"] for r in relevantes} for e in elegidos if e)
