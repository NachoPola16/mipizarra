# tests/test_diagram_renderer.py
"""Renderer SVG: todos los diagramas de la biblioteca se renderizan y dan SVG bien formado."""
import json
import xml.etree.ElementTree as ET

import pytest

from conftest import EXERCISES_JSON
from diagram_renderer import render_all_diagrams, render_diagram

SVG_NS = "{http://www.w3.org/2000/svg}"

with open(EXERCISES_JSON, encoding="utf-8") as _f:
    _EJERCICIOS = json.load(_f)

CON_DIAGRAMA = [e for e in _EJERCICIOS if "diagrama" in e or "diagramas" in e]


def _parsear_svg(svg: str) -> ET.Element:
    raiz = ET.fromstring(svg)
    assert raiz.tag == f"{SVG_NS}svg"
    assert raiz.get("viewBox")
    return raiz


def _num_diagramas(ej: dict) -> int:
    return len(ej["diagramas"]) if "diagramas" in ej else 1


def test_hay_ejercicios_con_diagrama():
    assert len(CON_DIAGRAMA) > 0


@pytest.mark.parametrize("ej", CON_DIAGRAMA, ids=lambda e: e["id"])
@pytest.mark.parametrize("edad", ["U10", "U16"])
def test_render_biblioteca_svg_bien_formado(ej, edad):
    resultado = render_all_diagrams(ej, edad=edad)
    assert len(resultado) == _num_diagramas(ej)
    for i, d in enumerate(resultado):
        assert set(d) == {"titulo", "svg"}
        raiz = _parsear_svg(d["svg"])
        diagrama = ej["diagramas"][i] if "diagramas" in ej else ej["diagrama"]
        # Un círculo blanco por atacante y un rect negro por defensor.
        circulos = [c for c in raiz.iter(f"{SVG_NS}circle") if c.get("fill") == "#ffffff"]
        defensores = [r for r in raiz.iter(f"{SVG_NS}rect") if r.get("fill") == "#1a202c" and r.get("rx")]
        assert len(circulos) == len(diagrama.get("jugadores_ataque", []))
        assert len(defensores) == len(diagrama.get("jugadores_defensa", []))


def test_diagramas_multiples_conservan_titulo():
    multiples = [e for e in _EJERCICIOS if "diagramas" in e]
    assert multiples
    for ej in multiples:
        titulos = [d["titulo"] for d in render_all_diagrams(ej)]
        assert titulos == [d.get("titulo", "") for d in ej["diagramas"]]


def test_sin_diagrama_devuelve_lista_vacia():
    assert render_all_diagrams({"nombre": "sin diagrama"}) == []


DIAGRAMA_COMPLETO = {
    "tipo": "media_pista",
    "jugadores_ataque": [{"id": "A1", "x": 50, "y": 65}, {"id": "A5", "x": 62, "y": 36}],
    "jugadores_defensa": [{"id": "D1", "x": 48, "y": 55}],
    "balon_inicio": {"portador": "A1"},
    "movimientos": [
        {"de": "A5", "a_pos": {"x": 48, "y": 58}, "tipo": "bloqueo", "orden": 1},
        {"de": "A1", "a_pos": {"x": 65, "y": 50}, "tipo": "bote", "curva": -40, "orden": 2},
        {"de": "A5", "a_pos": {"x": 62, "y": 18}, "tipo": "desplazamiento", "curva": True, "orden": 3},
        {"de": "A1", "a": "A5", "tipo": "pase", "curva": 30, "orden": 4},
        {"de": "A5", "tipo": "tiro", "orden": 5},
    ],
    "conos": [{"x": 10, "y": 22}],
}


@pytest.mark.parametrize("tipo", ["media_pista", "pista_completa"])
@pytest.mark.parametrize("edad", ["U8", "U12", "U14", "Senior"])
def test_render_todos_los_tipos_de_movimiento(tipo, edad):
    svg = render_diagram({**DIAGRAMA_COMPLETO, "tipo": tipo}, edad=edad)
    raiz = _parsear_svg(svg)
    # Bloqueo: línea roja fina + barra gruesa.
    rojas = [l for l in raiz.iter(f"{SVG_NS}line") if l.get("stroke") == "#dc2626"]
    rojas += [p for p in raiz.iter(f"{SVG_NS}path") if p.get("stroke") == "#dc2626"]
    assert len(rojas) == 2
    # Tiro: flecha verde.
    assert any(e.get("marker-end") == "url(#arrs)" for e in raiz.iter())
    # Cono.
    assert len(list(raiz.iter(f"{SVG_NS}polygon"))) == 1


def test_minibasket_dibuja_triple_rectangular():
    """U8-U12 añaden las 3 líneas del triple de minibasket; U14 no."""
    def num_lineas(edad):
        raiz = _parsear_svg(render_diagram(DIAGRAMA_COMPLETO, edad=edad))
        return len(list(raiz.iter(f"{SVG_NS}line")))
    assert num_lineas("U12") == num_lineas("U14") + 3


def test_movimientos_a_jugadores_desconocidos_no_rompen():
    datos = {
        "jugadores_ataque": [{"id": "A1", "x": 50, "y": 65}],
        "jugadores_defensa": [],
        "balon_inicio": {"portador": "A9"},
        "movimientos": [
            {"de": "A9", "tipo": "tiro", "orden": 1},
            {"de": "A1", "a": "A7", "tipo": "pase", "orden": 2},
            {"de": "A1", "tipo": "bote", "orden": 3},
        ],
    }
    _parsear_svg(render_diagram(datos))


def test_render_es_determinista():
    assert render_diagram(DIAGRAMA_COMPLETO) == render_diagram(DIAGRAMA_COMPLETO)
