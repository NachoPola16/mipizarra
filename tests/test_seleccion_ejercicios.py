# tests/test_seleccion_ejercicios.py
"""filtrar_ejercicios y seleccionar_tres_ejercicios sobre la biblioteca real."""
import pytest

from rag_engine import EDAD_A_CATEGORIA, filtrar_ejercicios, seleccionar_tres_ejercicios

EDADES = ["U8", "U10", "U12", "U14", "U16", "U18", "Senior"]
OBJETIVOS = [
    "bote", "1c1", "defensa", "bloqueo directo", "tiro", "transición",
    "contraataque", "pase", "rebote", "juego interior", "objetivo sin coincidencias xyz",
]
CATEGORIAS_BLOQUEO = {"bloqueo_directo", "bloqueo_indirecto"}


def _admite_edad(ej, edad):
    edades = ej.get("edades", [])
    return edad in edades or EDAD_A_CATEGORIA.get(edad, edad) in edades


# ── filtrar_ejercicios ───────────────────────────────────────────────────────

@pytest.mark.parametrize("edad", EDADES)
@pytest.mark.parametrize("objetivo", OBJETIVOS)
def test_filtrar_respeta_la_edad(ejercicios, edad, objetivo):
    relevantes = filtrar_ejercicios(ejercicios, edad, objetivo)
    assert relevantes, f"sin ejercicios para {edad} / {objetivo}"
    for ej in relevantes:
        assert _admite_edad(ej, edad), f"{ej['id']} no admite {edad}"


@pytest.mark.parametrize("edad", EDADES)
@pytest.mark.parametrize("objetivo", OBJETIVOS)
def test_filtrar_sin_duplicados_y_con_fase(ejercicios, edad, objetivo):
    relevantes = filtrar_ejercicios(ejercicios, edad, objetivo)
    ids = [e["id"] for e in relevantes]
    assert len(ids) == len(set(ids))
    assert all(e.get("_fase") in ("ANALÍTICO", "OBJETIVO") for e in relevantes)


@pytest.mark.parametrize("edad", ["U8", "U10", "U12"])
def test_filtrar_minibasket_sin_bloqueos(ejercicios, edad):
    for objetivo in ("bloqueo directo", "bloqueo indirecto", "bloqueo"):
        for ej in filtrar_ejercicios(ejercicios, edad, objetivo):
            assert ej["categoria"] not in CATEGORIAS_BLOQUEO, ej["id"]


def test_filtrar_u14_sin_bloqueo_directo(ejercicios):
    for ej in filtrar_ejercicios(ejercicios, "U14", "bloqueo directo"):
        assert ej["categoria"] != "bloqueo_directo", ej["id"]


def test_filtrar_objetivo_directo_va_primero_entre_directos(ejercicios):
    relevantes = filtrar_ejercicios(ejercicios, "U16", "bloqueo directo")
    directos = [e for e in relevantes if e["_fase"] == "OBJETIVO"]
    assert directos
    texto = f"{directos[0]['nombre']} {directos[0].get('descripcion', '')}".lower()
    assert "bloqueo" in texto or "directo" in texto


def test_filtrar_analiticos_como_maximo_cuatro(ejercicios):
    for edad in EDADES:
        for objetivo in OBJETIVOS:
            relevantes = filtrar_ejercicios([dict(e) for e in ejercicios], edad, objetivo)
            assert sum(1 for e in relevantes if e["_fase"] == "ANALÍTICO") <= 4


def test_filtrar_completa_hasta_tres_con_pocos_directos():
    """Con menos de 3 coincidencias directas se completa con el resto de la categoría."""
    base = {"edades": ["U14"], "objetivos": {"tacticos": []}, "descripcion": ""}
    ejs = [
        {**base, "id": "x1", "nombre": "Rueda de tiro"},
        {**base, "id": "x2", "nombre": "Juego de persecución"},
        {**base, "id": "x3", "nombre": "Pañuelo con balón"},
        {**base, "id": "x4", "nombre": "Relevos"},
        {**base, "id": "x5", "nombre": "Ejercicio de otra edad", "edades": ["U18"]},
    ]
    relevantes = filtrar_ejercicios(ejs, "U14", "tiro")
    directos = [e["id"] for e in relevantes if e["_fase"] == "OBJETIVO"]
    assert directos[0] == "x1"
    assert len(directos) >= 3
    assert "x5" not in [e["id"] for e in relevantes]


# ── seleccionar_tres_ejercicios ──────────────────────────────────────────────

@pytest.mark.parametrize("edad", EDADES)
@pytest.mark.parametrize("objetivo", OBJETIVOS)
def test_seleccion_siempre_tres_distintos(ejercicios, edad, objetivo):
    tres = seleccionar_tres_ejercicios(filtrar_ejercicios(ejercicios, edad, objetivo))
    assert len(tres) == 3
    assert all(e is not None for e in tres), f"{edad} / {objetivo}: {tres}"
    ids = [e["id"] for e in tres]
    assert len(set(ids)) == 3, f"{edad} / {objetivo}: duplicados {ids}"
    for ej in tres:
        assert _admite_edad(ej, edad)


@pytest.mark.parametrize("edad", ["U8", "U10", "U12"])
@pytest.mark.parametrize("objetivo", OBJETIVOS)
def test_seleccion_minibasket_sin_bloqueos(ejercicios, edad, objetivo):
    for ej in seleccionar_tres_ejercicios(filtrar_ejercicios(ejercicios, edad, objetivo)):
        assert ej["categoria"] not in CATEGORIAS_BLOQUEO, ej["id"]


def test_seleccion_progresion_de_oposicion():
    """Ej. 1 analítico (sin oposición), ej. 2 en superioridad, ej. 3 con oposición igualada."""
    relevantes = [
        {"id": "a", "nombre": "Rueda de pases", "_fase": "ANALÍTICO"},
        {"id": "b", "nombre": "3c3 en media pista", "_fase": "OBJETIVO"},
        {"id": "c", "nombre": "2c1 tras bote", "_fase": "OBJETIVO"},
        {"id": "d", "nombre": "Tiro tras 2c0", "_fase": "OBJETIVO"},
    ]
    ej1, ej2, ej3 = seleccionar_tres_ejercicios(relevantes)
    assert (ej1["id"], ej2["id"], ej3["id"]) == ("a", "c", "b")


def test_seleccion_sin_analiticos_usa_directo_sin_oposicion():
    relevantes = [
        {"id": "b", "nombre": "2c2 cerrado", "_fase": "OBJETIVO"},
        {"id": "c", "nombre": "Tiro en estático 1c0", "_fase": "OBJETIVO"},
        {"id": "d", "nombre": "3c2 continuo", "_fase": "OBJETIVO"},
    ]
    ej1, ej2, ej3 = seleccionar_tres_ejercicios(relevantes)
    assert ej1["id"] == "c"
    assert len({ej1["id"], ej2["id"], ej3["id"]}) == 3
