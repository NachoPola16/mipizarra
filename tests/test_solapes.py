# tests/test_solapes.py
"""Separación de marcadores solapados (api/solapes.py) y su uso al dibujar: mínima,
estable y determinista, sin tocar el JSON guardado, en media pista y pista completa."""
import copy
import json
import math
import re
import xml.etree.ElementTree as ET

import pytest

from conftest import EXERCISES_JSON
from diagram_renderer import render_all_diagrams, render_diagram
from solapes import DISTANCIA_MINIMA, separar_puntos

SVG_NS = "{http://www.w3.org/2000/svg}"
# Los conos se pintan con píxeles enteros (:.0f): al medirlos hay hasta ~0,1 unidades de error.
TOLERANCIA_CONO = 0.15


# ── separar_puntos ───────────────────────────────────────────────────────────

def test_sin_solapes_devuelve_los_mismos_puntos():
    puntos = [(50, 65), (25, 50), (75, 50)]
    nuevos, sin_sitio = separar_puntos(puntos)
    assert nuevos == puntos and sin_sitio == []
    assert all(a is b for a, b in zip(nuevos, puntos))


def test_dos_puntos_cerca_mueve_el_segundo_lo_minimo_en_la_misma_direccion():
    nuevos, sin_sitio = separar_puntos([(50, 50), (55, 50)])
    assert sin_sitio == []
    assert nuevos[0] == (50, 50)
    x, y = nuevos[1]
    assert y == pytest.approx(50)
    assert DISTANCIA_MINIMA <= x - 50 < DISTANCIA_MINIMA + 0.05


def test_distancia_exactamente_en_el_minimo_no_se_toca():
    puntos = [(50, 65), (50, 57)]
    assert separar_puntos(puntos)[0] == puntos


def test_puntos_coincidentes_se_separan_de_forma_determinista():
    puntos = [(40, 40), (40, 40)]
    primero = separar_puntos(puntos)
    assert primero == separar_puntos(list(puntos))
    nuevo = primero[0][1]
    assert DISTANCIA_MINIMA <= math.dist(nuevo, (40, 40)) < DISTANCIA_MINIMA + 0.05


def test_es_estable_con_el_orden_los_anteriores_no_se_mueven():
    puntos = [(30, 30), (33, 30), (36, 30)]
    nuevos, _ = separar_puntos(puntos)
    assert nuevos[0] == (30, 30)
    for i in range(3):
        for k in range(i + 1, 3):
            assert math.dist(nuevos[i], nuevos[k]) >= DISTANCIA_MINIMA


def test_respeta_los_limites_de_la_pista():
    # Empujar el segundo en la dirección natural lo sacaría por la izquierda (x<0).
    nuevos, sin_sitio = separar_puntos([(5, 50), (1, 50)])
    assert sin_sitio == []
    x, y = nuevos[1]
    assert 0 <= x <= 100 and 0 <= y <= 100
    assert math.dist(nuevos[1], (5, 50)) >= DISTANCIA_MINIMA
    # El mínimo exacto está en x=0 a ~6,3 unidades del original.
    assert math.dist(nuevos[1], (1, 50)) < 6.4


def test_entre_dos_vecinos_busca_el_hueco_mas_cercano():
    nuevos, sin_sitio = separar_puntos([(40, 50), (52, 50), (46, 51)])
    assert sin_sitio == []
    for ancla in [(40, 50), (52, 50)]:
        assert math.dist(nuevos[2], ancla) >= DISTANCIA_MINIMA
    # El hueco válido más cercano está sobre la mediatriz, a unos 4,3 unidades.
    assert math.dist(nuevos[2], (46, 51)) < 4.5


def test_conos_entre_si_no_cuentan():
    puntos = [(50, 50), (52, 50)]
    assert separar_puntos(puntos, es_cono=[True, True])[0] == puntos
    assert separar_puntos(puntos, es_cono=[False, True])[0] != puntos


def test_sin_sitio_cerca_se_deja_igual_y_se_informa():
    # Retícula 3x3 con paso 8 y un punto en el centro de una celda: no hay hueco
    # a menos de 8 unidades de desplazamiento.
    reticula = [(x, y) for y in (42, 50, 58) for x in (42, 50, 58)]
    puntos = reticula + [(46, 46)]
    nuevos, sin_sitio = separar_puntos(puntos)
    assert sin_sitio == [9]
    assert nuevos[9] == (46, 46)


def test_coordenadas_redondeadas_a_dos_decimales():
    nuevos, _ = separar_puntos([(50, 50), (53.3, 47.1)])
    x, y = nuevos[1]
    assert round(x, 2) == x and round(y, 2) == y


# ── Renderer: separa al dibujar sin cambiar el JSON ──────────────────────────

def _centros(svg: str, tipo: str) -> dict[str, list[tuple[float, float]]]:
    """Centros de atacantes, defensores y conos en unidades 0-100 (inversa de to_px)."""
    raiz = ET.fromstring(svg)
    if tipo == "pista_completa":
        pad, ancho, alto = 70, 675, 1260
    else:
        pad, ancho, alto = 30, 675, 630
    alto_svg = alto + 2 * pad

    def a_unidades(px, py):
        return (px - pad) / ancho * 100, (alto_svg - pad - py) / alto * 100

    ataque = [a_unidades(float(c.get("cx")), float(c.get("cy")))
              for c in raiz.iter(f"{SVG_NS}circle") if c.get("fill") == "#ffffff"]
    defensa = [a_unidades(float(r.get("x")) + float(r.get("width")) / 2,
                          float(r.get("y")) + float(r.get("height")) / 2)
               for r in raiz.iter(f"{SVG_NS}rect") if r.get("fill") == "#1a202c" and r.get("rx")]
    conos = []
    for p in raiz.iter(f"{SVG_NS}polygon"):
        (x0, y0), *_ = [tuple(map(float, v.split(","))) for v in p.get("points").split()]
        conos.append(a_unidades(x0, y0 + 16))
    return {"ataque": ataque, "defensa": defensa, "conos": conos}


DIAGRAMA_SOLAPADO = {
    "jugadores_ataque": [{"id": "A1", "x": 50, "y": 65}, {"id": "A2", "x": 20, "y": 40}],
    "jugadores_defensa": [{"id": "D1", "x": 50, "y": 60}, {"id": "D2", "x": 22, "y": 36}],
    "balon_inicio": {"portador": "A1"},
    "movimientos": [{"de": "D1", "a_pos": {"x": 40, "y": 40}, "tipo": "desplazamiento", "orden": 1}],
    "conos": [{"x": 80, "y": 30}, {"x": 82, "y": 31}],
}


@pytest.mark.parametrize("tipo", ["media_pista", "pista_completa"])
def test_render_separa_jugadores_solapados(tipo):
    datos = {**copy.deepcopy(DIAGRAMA_SOLAPADO), "tipo": tipo}
    c = _centros(render_diagram(datos), tipo)
    # A1 no se mueve; D1 sale hacia abajo hasta 8 unidades.
    assert c["ataque"][0] == pytest.approx((50, 65), abs=0.05)
    assert c["defensa"][0][0] == pytest.approx(50, abs=0.05)
    assert c["defensa"][0][1] == pytest.approx(57, abs=0.1)
    todos = c["ataque"] + c["defensa"]
    for i in range(len(todos)):
        for k in range(i + 1, len(todos)):
            assert math.dist(todos[i], todos[k]) >= DISTANCIA_MINIMA - 0.05


@pytest.mark.parametrize("tipo", ["media_pista", "pista_completa"])
def test_render_no_cambia_el_json(tipo):
    datos = {**copy.deepcopy(DIAGRAMA_SOLAPADO), "tipo": tipo}
    antes = copy.deepcopy(datos)
    render_diagram(datos)
    assert datos == antes


def test_render_separa_jugador_y_cono():
    datos = {
        "tipo": "media_pista",
        "jugadores_ataque": [{"id": "A1", "x": 30, "y": 30}],
        "jugadores_defensa": [],
        "movimientos": [],
        "conos": [{"x": 33, "y": 30}, {"x": 60, "y": 60}],
    }
    c = _centros(render_diagram(datos), "media_pista")
    assert c["ataque"][0] == pytest.approx((30, 30), abs=0.05)
    assert math.dist(c["ataque"][0], c["conos"][0]) >= DISTANCIA_MINIMA - TOLERANCIA_CONO
    assert c["conos"][1] == pytest.approx((60, 60), abs=0.2)


def test_render_conos_juntos_no_se_separan():
    datos = {"tipo": "media_pista", "jugadores_ataque": [{"id": "A1", "x": 10, "y": 90}],
             "jugadores_defensa": [], "movimientos": [],
             "conos": [{"x": 50, "y": 50}, {"x": 52, "y": 50}]}
    c = _centros(render_diagram(datos), "media_pista")
    assert c["conos"] == [pytest.approx((50, 50), abs=0.2), pytest.approx((52, 50), abs=0.2)]


def test_render_movimiento_sale_de_la_posicion_dibujada():
    datos = {**copy.deepcopy(DIAGRAMA_SOLAPADO), "tipo": "media_pista"}
    raiz = ET.fromstring(render_diagram(datos))
    linea = next(l for l in raiz.iter(f"{SVG_NS}line") if l.get("marker-end") == "url(#arr)")
    # El desplazamiento de D1 empieza junto a su posición dibujada (y=57), no en la del JSON (y=60).
    y_px_57 = 690 - 30 - 57 / 100 * 630
    assert abs(float(linea.get("y1")) - y_px_57) < 30


def test_render_solapes_determinista():
    datos = {**copy.deepcopy(DIAGRAMA_SOLAPADO), "tipo": "media_pista"}
    assert render_diagram(datos) == render_diagram(copy.deepcopy(datos))


# ── Biblioteca: ningún marcador queda solapado al dibujarse ──────────────────

with open(EXERCISES_JSON, encoding="utf-8") as _f:
    _EJERCICIOS = json.load(_f)
_CON_DIAGRAMA = [e for e in _EJERCICIOS if "diagrama" in e or "diagramas" in e]


@pytest.mark.parametrize("ej", _CON_DIAGRAMA, ids=lambda e: e["id"])
def test_biblioteca_sin_marcadores_solapados_al_dibujar(ej):
    diagramas = ej["diagramas"] if "diagramas" in ej else [ej["diagrama"]]
    for d, r in zip(diagramas, render_all_diagrams(ej)):
        c = _centros(r["svg"], d.get("tipo", "media_pista"))
        jugadores = c["ataque"] + c["defensa"]
        for i, p in enumerate(jugadores):
            for q in jugadores[i + 1:]:
                assert math.dist(p, q) >= DISTANCIA_MINIMA - 0.05, (ej["id"], p, q)
            for q in c["conos"]:
                assert math.dist(p, q) >= DISTANCIA_MINIMA - TOLERANCIA_CONO, (ej["id"], p, q)


def test_biblioteca_svg_numeros_validos():
    for ej in _CON_DIAGRAMA:
        for r in render_all_diagrams(ej):
            assert not re.search(r"nan|inf", r["svg"])
