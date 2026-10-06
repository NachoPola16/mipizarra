# tests/test_plantillas.py
"""Plantillas de calentamiento y vuelta a la calma (api/plantillas.py): diagramas
válidos sin modelo, bien formados en SVG y sin marcadores solapados."""
import copy
import math
import re
import xml.etree.ElementTree as ET

import pytest

from conftest import RAIZ
from diagram_renderer import render_diagram
from plantillas import PLANTILLAS, generar_plantilla
from posiciones import posicion_de
from rag_engine import _validar_diagrama
from solapes import DISTANCIA_MINIMA, separar_puntos

SVG_NS = "{http://www.w3.org/2000/svg}"
NOMBRES = sorted(PLANTILLAS)
JUGADORES = [4, 6, 8, 10]


def test_entre_10_y_15_plantillas():
    assert 10 <= len(PLANTILLAS) <= 15


def test_hay_de_calentamiento_y_de_vuelta_a_la_calma():
    momentos = {p.momento for p in PLANTILLAS.values()}
    assert momentos == {"calentamiento", "vuelta_a_la_calma"}


@pytest.mark.parametrize("nombre", [
    "filas_esquinas", "circuito_conos", "rondo_circular", "cuatro_esquinas",
    "dos_filas_enfrentadas", "zigzag_conos",
])
def test_estan_las_pedidas(nombre):
    assert nombre in PLANTILLAS


@pytest.mark.parametrize("nombre", NOMBRES)
def test_cada_plantilla_tiene_descripcion_y_rangos_coherentes(nombre):
    p = PLANTILLAS[nombre]
    assert p.descripcion.strip()
    assert p.jugadores_min <= 4 and p.jugadores_max >= 10
    assert p.conos_min <= p.conos_defecto <= p.conos_max


def _todos(d):
    return d["jugadores_ataque"] + d["jugadores_defensa"]


@pytest.mark.parametrize("n", JUGADORES)
@pytest.mark.parametrize("nombre", NOMBRES)
def test_plantilla_pasa_el_validador_sin_reparaciones(nombre, n):
    d = generar_plantilla(nombre, n)
    antes = copy.deepcopy(d)
    assert _validar_diagrama(d, "") is None
    assert d == antes, "la plantilla no debe necesitar reparaciones del validador"
    assert len(_todos(d)) == n


@pytest.mark.parametrize("n", JUGADORES)
@pytest.mark.parametrize("nombre", NOMBRES)
def test_plantilla_renderiza_svg_bien_formado(nombre, n):
    d = generar_plantilla(nombre, n)
    raiz = ET.fromstring(render_diagram(d, edad="U12"))
    assert raiz.tag == f"{SVG_NS}svg"
    circulos = [c for c in raiz.iter(f"{SVG_NS}circle") if c.get("fill") == "#ffffff"]
    defensores = [r for r in raiz.iter(f"{SVG_NS}rect") if r.get("fill") == "#1a202c" and r.get("rx")]
    assert len(circulos) == len(d["jugadores_ataque"])
    assert len(defensores) == len(d["jugadores_defensa"])
    assert len(list(raiz.iter(f"{SVG_NS}polygon"))) == len(d["conos"])


@pytest.mark.parametrize("n", JUGADORES)
@pytest.mark.parametrize("nombre", NOMBRES)
def test_plantilla_sin_solapes_ni_con_conos(nombre, n):
    """Nada que separar al dibujar: jugadores y conos ya a 8 unidades o más."""
    d = generar_plantilla(nombre, n)
    puntos = [posicion_de(p) for p in _todos(d) + d["conos"]]
    es_cono = [False] * len(_todos(d)) + [True] * len(d["conos"])
    nuevos, sin_sitio = separar_puntos(puntos, es_cono)
    assert sin_sitio == [] and nuevos == puntos


@pytest.mark.parametrize("n", JUGADORES)
@pytest.mark.parametrize("nombre", NOMBRES)
def test_plantilla_dentro_de_la_media_pista(nombre, n):
    d = generar_plantilla(nombre, n)
    assert d["tipo"] == "media_pista"
    puntos = _todos(d) + d["conos"] + [m["a_pos"] for m in d["movimientos"] if "a_pos" in m]
    for p in puntos:
        x, y = posicion_de(p)
        assert 0 <= x <= 100 and 0 <= y <= 100


@pytest.mark.parametrize("nombre", NOMBRES)
def test_extremos_de_jugadores(nombre):
    p = PLANTILLAS[nombre]
    for n in (p.jugadores_min, p.jugadores_max):
        d = generar_plantilla(nombre, n)
        assert _validar_diagrama(copy.deepcopy(d), "") is None
        assert len(_todos(d)) == n
        ET.fromstring(render_diagram(d))


@pytest.mark.parametrize("nombre", NOMBRES)
def test_numero_de_conos(nombre):
    p = PLANTILLAS[nombre]
    assert len(generar_plantilla(nombre, 6)["conos"]) == p.conos_defecto
    for c in range(p.conos_min, p.conos_max + 1):
        d = generar_plantilla(nombre, 8, n_conos=c)
        assert len(d["conos"]) == c
        assert _validar_diagrama(copy.deepcopy(d), "") is None
        puntos = [posicion_de(q) for q in _todos(d) + d["conos"]]
        es_cono = [False] * len(_todos(d)) + [True] * len(d["conos"])
        assert separar_puntos(puntos, es_cono)[0] == puntos


@pytest.mark.parametrize("nombre", NOMBRES)
def test_determinista_y_copia_nueva(nombre):
    d1 = generar_plantilla(nombre, 8)
    d1["jugadores_ataque"][0]["x"] = -1
    assert generar_plantilla(nombre, 8) == generar_plantilla(nombre, 8)
    assert generar_plantilla(nombre, 8)["jugadores_ataque"][0]["x"] != -1


@pytest.mark.parametrize("nombre", NOMBRES)
def test_ids_unicos_y_sin_inventar(nombre):
    d = generar_plantilla(nombre, 10)
    ids = [j["id"] for j in _todos(d)]
    assert len(ids) == len(set(ids))
    assert all(i.startswith(("A", "D")) for i in ids)
    for m in d["movimientos"]:
        assert m["de"] in ids
        if m["tipo"] == "pase":
            assert m["a"] in ids


@pytest.mark.parametrize("nombre", NOMBRES)
def test_jugadores_razonablemente_separados(nombre):
    """Además del mínimo de 8, ningún par queda exactamente pegado al límite por redondeo."""
    d = generar_plantilla(nombre, 10)
    pts = [posicion_de(p) for p in _todos(d)]
    for i in range(len(pts)):
        for k in range(i + 1, len(pts)):
            assert math.dist(pts[i], pts[k]) >= DISTANCIA_MINIMA


def test_plantilla_desconocida():
    with pytest.raises(ValueError, match="plantilla desconocida"):
        generar_plantilla("baile", 6)


@pytest.mark.parametrize("n", [0, 1, 13])
def test_jugadores_fuera_de_rango(n):
    with pytest.raises(ValueError, match="jugadores"):
        generar_plantilla("rondo_circular", n)


def test_conos_fuera_de_rango():
    p = PLANTILLAS["zigzag_conos"]
    with pytest.raises(ValueError, match="conos"):
        generar_plantilla("zigzag_conos", 6, n_conos=p.conos_max + 1)


def test_tabla_de_la_documentacion_coincide():
    texto = (RAIZ / "docs" / "coordenadas.md").read_text(encoding="utf-8")
    filas = re.findall(r"^\| `([a-z_]+)`\s*\| ([a-z ]+?)\s*\| (\d+)-(\d+)\s*\| (\d+)(?:-(\d+))? \((\d+)\)", texto, re.M)
    assert {f[0] for f in filas} == set(PLANTILLAS)
    for nombre, momento, jmin, jmax, cmin, cmax, cdef in filas:
        p = PLANTILLAS[nombre]
        assert momento.replace(" ", "_") == p.momento
        assert (int(jmin), int(jmax)) == (p.jugadores_min, p.jugadores_max)
        assert (int(cmin), int(cmax or cmin), int(cdef)) == (p.conos_min, p.conos_max, p.conos_defecto)
