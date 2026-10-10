# tests/test_seleccion_n_ejercicios.py
"""seleccionar_ejercicios: elige n ejercicios de la biblioteca (n entre 3 y 6 en la parte principal)
con el mismo arco que antes: empieza sin oposición y termina con oposición igualada."""
import random

import pytest

from ejercicios import (
    _desvio_del_arco, _nivel_oposicion, elegir_fichas, filtrar_ejercicios, nivel_objetivo, seleccionar_ejercicios,
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


def test_elegir_fichas_vive_en_ejercicios_y_sesion_la_reutiliza():
    # así se puede medir cuántos huecos propone la IA sin cargar ChromaDB (tools/huecos_biblioteca.py)
    import ejercicios
    import sesion
    assert callable(ejercicios.elegir_fichas) and sesion._elegir_fichas is ejercicios.elegir_fichas


# ─── Variedad: con `azar` los empates se resuelven al azar, sin perder el arco ni la relevancia ────────

def _niveles(elegidos):
    return [_nivel_oposicion(e) if e else None for e in elegidos]


def test_sin_azar_la_eleccion_es_siempre_la_misma():
    assert [e["nombre"] for e in seleccionar_ejercicios(_pool(), 3)] == \
           [e["nombre"] for e in seleccionar_ejercicios(_pool(), 3)]


def test_con_azar_salen_sesiones_distintas_y_todas_siguen_el_arco():
    base = _niveles(seleccionar_ejercicios(_pool(), 5))
    vistas = set()
    for semilla in range(40):
        elegidos = seleccionar_ejercicios(_pool(), 5, azar=random.Random(semilla))
        vistas.add(tuple(e["nombre"] for e in elegidos))
        assert _niveles(elegidos) == base
        nombres = [e["nombre"] for e in elegidos]
        assert len(nombres) == len(set(nombres))
    assert len(vistas) > 1


def test_con_azar_solo_compiten_las_primeras_fichas_empatadas():
    # compiten las 3 primeras libres por hueco: con dos huecos del mismo nivel puede entrar la 4.ª
    # (la primera ya se usó), pero la 5.ª, la menos relevante (llegan ordenadas), nunca
    pool = [_ej("Pases 3c0 en triángulo", "ANALÍTICO")] + [_ej(f"3c3 variante {i}") for i in range(5)]
    salidas = {e["nombre"] for semilla in range(60)
               for e in seleccionar_ejercicios(pool, 3, azar=random.Random(semilla))[1:]}
    assert salidas
    assert "3c3 variante 4" not in salidas


def test_con_azar_los_huecos_son_los_mismos_que_sin_azar():
    pool = _pool()[:3]
    for semilla in range(10):
        elegidos = seleccionar_ejercicios(pool, 5, azar=random.Random(semilla))
        assert sum(e is None for e in elegidos) == sum(e is None for e in seleccionar_ejercicios(pool, 5))


@pytest.mark.parametrize("edad", EDADES)
@pytest.mark.parametrize("objetivo", OBJETIVOS)
def test_en_la_biblioteca_real_el_azar_no_empeora_huecos_ni_arco(ejercicios, edad, objetivo):
    n = 5
    base = elegir_fichas([dict(e) for e in ejercicios], edad, objetivo, n)
    for semilla in range(6):
        elegidas = elegir_fichas([dict(e) for e in ejercicios], edad, objetivo, n, azar=random.Random(semilla))
        assert _desvio_del_arco(elegidas) <= _desvio_del_arco(base)
        ids = [f["id"] for f in elegidas if f]
        assert len(ids) == len(set(ids))
