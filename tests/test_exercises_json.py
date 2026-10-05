# tests/test_exercises_json.py
"""Invariantes de la biblioteca curada data/exercises.json (ver docs/esquema-ejercicios.md
y docs/coordenadas.md)."""
import json

import pytest

from conftest import EXERCISES_JSON

with open(EXERCISES_JSON, encoding="utf-8") as _f:
    EJERCICIOS = json.load(_f)

CATEGORIAS_PERMITIDAS = {
    "ventaja_numerica", "bloqueo_directo", "bloqueo_indirecto", "tiro",
    "1c1", "juego_equipo", "fisico", "calentamiento",
}
EDADES_PERMITIDAS = {"U8", "U10", "U12", "U14", "U16", "U18", "Senior"}
EDADES_SIN_BLOQUEO = {"U8", "U10", "U12"}
CATEGORIAS_BLOQUEO = {"bloqueo_directo", "bloqueo_indirecto"}
TIPOS_DIAGRAMA = {"media_pista", "pista_completa"}
TIPOS_MOVIMIENTO = {"desplazamiento", "pase", "bote", "tiro", "bloqueo"}
CAMPOS_OBLIGATORIOS = {
    "id", "nombre", "categoria", "edades", "duracion_min",
    "intensidad", "carga_cognitiva", "objetivos", "descripcion",
}


def _diagramas(ej):
    if "diagramas" in ej:
        return ej["diagramas"]
    if "diagrama" in ej:
        return [ej["diagrama"]]
    return []


def _ids(ej):
    return ej["id"]


def test_biblioteca_no_vacia_y_es_lista():
    assert isinstance(EJERCICIOS, list) and EJERCICIOS


def test_ids_unicos():
    ids = [e["id"] for e in EJERCICIOS]
    duplicados = sorted({i for i in ids if ids.count(i) > 1})
    assert not duplicados, f"ids repetidos: {duplicados}"


@pytest.mark.parametrize("ej", EJERCICIOS, ids=_ids)
def test_campos_obligatorios(ej):
    faltan = CAMPOS_OBLIGATORIOS - set(ej)
    assert not faltan, f"faltan campos: {faltan}"
    assert isinstance(ej["nombre"], str) and ej["nombre"].strip()
    assert isinstance(ej["objetivos"].get("tacticos", []), list)
    assert isinstance(ej["duracion_min"], int) and ej["duracion_min"] > 0
    assert 1 <= ej["intensidad"] <= 5
    assert 1 <= ej["carga_cognitiva"] <= 5


@pytest.mark.parametrize("ej", EJERCICIOS, ids=_ids)
def test_categoria_y_edades_permitidas(ej):
    assert ej["categoria"] in CATEGORIAS_PERMITIDAS
    assert ej["edades"], "sin edades"
    assert set(ej["edades"]) <= EDADES_PERMITIDAS, set(ej["edades"]) - EDADES_PERMITIDAS


@pytest.mark.parametrize("ej", EJERCICIOS, ids=_ids)
def test_minibasket_sin_categoria_de_bloqueo(ej):
    if set(ej["edades"]) & EDADES_SIN_BLOQUEO:
        assert ej["categoria"] not in CATEGORIAS_BLOQUEO


@pytest.mark.parametrize("ej", EJERCICIOS, ids=_ids)
def test_bloqueo_directo_solo_desde_u16(ej):
    if ej["categoria"] == "bloqueo_directo":
        assert not set(ej["edades"]) & {"U8", "U10", "U12", "U14"}


def _en_rango(p):
    return 0 <= p["x"] <= 100 and 0 <= p["y"] <= 100


@pytest.mark.parametrize("ej", [e for e in EJERCICIOS if _diagramas(e)], ids=_ids)
def test_coordenadas_entre_0_y_100(ej):
    for d in _diagramas(ej):
        puntos = d.get("jugadores_ataque", []) + d.get("jugadores_defensa", []) + d.get("conos", [])
        puntos += [m["a_pos"] for m in d.get("movimientos", []) if "a_pos" in m]
        fuera = [p for p in puntos if not _en_rango(p)]
        assert not fuera, f"coordenadas fuera de [0, 100]: {fuera}"


@pytest.mark.parametrize("ej", [e for e in EJERCICIOS if _diagramas(e)], ids=_ids)
def test_estructura_del_diagrama(ej):
    for d in _diagramas(ej):
        assert d.get("tipo", "media_pista") in TIPOS_DIAGRAMA
        assert d.get("jugadores_ataque"), "sin atacantes"
        ids = [j["id"] for j in d.get("jugadores_ataque", []) + d.get("jugadores_defensa", [])]
        assert len(ids) == len(set(ids)), f"ids de jugador repetidos: {ids}"
        for j in d.get("jugadores_ataque", []):
            assert j["id"].startswith("A"), j["id"]
        for j in d.get("jugadores_defensa", []):
            assert j["id"].startswith("D"), j["id"]
        if "diagramas" in ej:
            assert d.get("titulo"), "diagrama múltiple sin titulo"


@pytest.mark.parametrize("ej", [e for e in EJERCICIOS if _diagramas(e)], ids=_ids)
def test_referencias_de_movimientos_validas(ej):
    for d in _diagramas(ej):
        ids = {j["id"] for j in d.get("jugadores_ataque", []) + d.get("jugadores_defensa", [])}
        portador = (d.get("balon_inicio") or {}).get("portador")
        if portador:
            assert portador in ids, f"portador '{portador}' no declarado"
        for m in d.get("movimientos", []):
            assert m.get("tipo") in TIPOS_MOVIMIENTO, m
            assert m.get("de") in ids, f"movimiento de jugador no declarado: {m}"
            assert isinstance(m.get("orden"), int) and m["orden"] >= 1, m
            if m["tipo"] == "pase":
                assert m.get("a") in ids, f"pase a jugador no declarado: {m}"
            elif m["tipo"] in ("desplazamiento", "bote", "bloqueo"):
                assert "a_pos" in m, f"'{m['tipo']}' sin a_pos: {m}"


@pytest.mark.parametrize("ej", EJERCICIOS, ids=_ids)
def test_variantes_apuntan_a_ids_existentes(ej):
    todos = {e["id"] for e in EJERCICIOS}
    for v in ej.get("variantes", []):
        assert v in todos, f"variante inexistente: {v}"


@pytest.mark.parametrize("ej", EJERCICIOS, ids=_ids)
def test_terminologia_bloqueo_no_pantalla(ej):
    """docs/coordenadas.md: en los outputs siempre 'bloqueo', nunca 'pantalla'."""
    texto = json.dumps(ej, ensure_ascii=False).lower()
    assert "pantalla" not in texto


# ── Campos opcionales de la Fase 1.2 (ver docs/esquema-ejercicios.md) ─────────

CAMPOS_TEXTO = ("material", "consigna")
CAMPOS_LISTA = ("errores_frecuentes", "que_observar")


@pytest.mark.parametrize("ej", EJERCICIOS, ids=_ids)
def test_campos_nuevos_opcionales_tienen_la_forma_correcta(ej):
    for campo in CAMPOS_TEXTO:
        if campo in ej:
            assert isinstance(ej[campo], str) and ej[campo].strip(), campo
    for campo in CAMPOS_LISTA:
        if campo in ej:
            assert isinstance(ej[campo], list) and ej[campo], campo
            assert all(isinstance(i, str) and i.strip() for i in ej[campo]), campo
    if "progresion" in ej:
        prog = ej["progresion"]
        assert isinstance(prog, dict) and prog, "progresion"
        assert set(prog) <= {"facilitar", "complicar"}, prog
        assert all(isinstance(v, str) and v.strip() for v in prog.values()), prog
