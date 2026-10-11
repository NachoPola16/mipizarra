# tests/test_seguridad_web.py
"""Entrada hostil: lo que /pdf/ acepta (frontend/pizarra/entrada_pdf.py) y los ids de jugador que acaban dentro del
SVG que la web inserta con innerHTML (api/diagramas.py y api/diagram_renderer.py)."""
import importlib.util

import pytest

from conftest import RAIZ
from diagram_renderer import render_diagram
from diagramas import _validar_diagrama

_spec = importlib.util.spec_from_file_location("entrada_pdf", RAIZ / "frontend" / "pizarra" / "entrada_pdf.py")
entrada = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(entrada)

SVG_OK = ('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="50">'
          '<rect width="100" height="50" fill="red"/><text x="1" y="2">A1</text></svg>')
BASE = {"sesion": "**CALENTAMIENTO (10 min)**\nJuego: pilla", "edad": "U12", "objetivo": "bote", "duracion": 60,
        "diagramas": [{"id": "ej_1", "nombre": "Bote", "svg": SVG_OK}]}


def test_entrada_normal_pasa():
    sesion, edad, objetivo, duracion, diagramas = entrada.limpiar_entrada_pdf(BASE)
    assert (edad, objetivo, duracion) == ("U12", "bote", 60)
    assert len(diagramas) == 1 and sesion.startswith("**CALENT")


@pytest.mark.parametrize("campo,valor", [
    pytest.param("edad", 12, id="edad-numero"), pytest.param("edad", ["a"], id="edad-lista"),
    pytest.param("sesion", 5, id="sesion-numero"), pytest.param("objetivo", {"a": 1}, id="objetivo-objeto"),
    pytest.param("diagramas", "x", id="diagramas-texto"), pytest.param("diagramas", [1, 2], id="diagramas-no-dict"),
    pytest.param("sesion", "x" * (entrada.MAX_SESION + 1), id="sesion-larga"),
    pytest.param("objetivo", "x" * (entrada.MAX_CAMPO + 1), id="objetivo-largo"),
    pytest.param("diagramas", [{"svg": SVG_OK}] * (entrada.MAX_DIAGRAMAS + 1), id="muchos-diagramas"),
])
def test_entrada_mal_formada_se_rechaza(campo, valor):
    with pytest.raises(ValueError):
        entrada.limpiar_entrada_pdf({**BASE, campo: valor})


def test_cuerpo_que_no_es_objeto():
    with pytest.raises(ValueError):
        entrada.limpiar_entrada_pdf([1, 2])


def test_duracion_se_acota():
    assert entrada.limpiar_entrada_pdf({**BASE, "duracion": "abc"})[3] == 0
    assert entrada.limpiar_entrada_pdf({**BASE, "duracion": 10**9})[3] == 300
    assert entrada.limpiar_entrada_pdf({**BASE, "duracion": -5})[3] == 0


XXE = ('<?xml version="1.0"?><!DOCTYPE s [<!ENTITY x SYSTEM "file:///etc/passwd">]>'
       '<svg xmlns="http://www.w3.org/2000/svg" width="300" height="50"><text>&x;</text></svg>')
IMAGEN = ('<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="10" height="10">'
          '<image xlink:href="http://169.254.169.254/" width="10" height="10"/></svg>')
USE = ('<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><defs><g id="a"><rect width="1" height="1"/></g>'
       '</defs><use href="#a"/></svg>')
SCRIPT = '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><script>alert(1)</script></svg>'
EVENTO = '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><rect onload="alert(1)"/></svg>'
ENORME = '<svg xmlns="http://www.w3.org/2000/svg" width="100000" height="100000"><rect/></svg>'
MUCHOS = '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">' + "<rect/>" * 2000 + "</svg>"


@pytest.mark.parametrize("svg", [
    pytest.param(XXE, id="xxe"), pytest.param(IMAGEN, id="imagen-externa"), pytest.param(USE, id="use"),
    pytest.param(SCRIPT, id="script"), pytest.param(EVENTO, id="evento"), pytest.param(ENORME, id="enorme"),
    pytest.param(MUCHOS, id="muchos-elementos"), pytest.param("no es xml", id="no-xml"), pytest.param("", id="vacio"),
    pytest.param(None, id="none"), pytest.param(5, id="numero"),
    pytest.param(SVG_OK + "x" * entrada.MAX_SVG, id="demasiado-largo"),
])
def test_svg_peligroso_se_descarta(svg):
    assert entrada.svg_permitido(svg) is False
    sesion, *_, diagramas = entrada.limpiar_entrada_pdf({**BASE, "diagramas": [{"id": "e", "svg": svg}]})
    assert diagramas == []


def test_svg_propio_pasa():
    assert entrada.svg_permitido(SVG_OK) is True


def test_el_renderizador_genera_svg_que_pasa_el_filtro():
    d = {"tipo": "media_pista",
         "jugadores_ataque": [{"id": "A1", "x": 50, "y": 65}, {"id": "A2", "x": 25, "y": 50}],
         "jugadores_defensa": [{"id": "D1", "x": 48, "y": 62}], "conos": [{"x": 10, "y": 10}],
         "balon_inicio": {"portador": "A1"},
         "movimientos": [{"de": "A1", "a": "A2", "tipo": "pase", "orden": 1},
                         {"de": "A2", "a_pos": {"x": 40, "y": 40}, "tipo": "desplazamiento", "orden": 2},
                         {"de": "A1", "a_pos": {"x": 60, "y": 50}, "tipo": "bote", "curva": -40, "orden": 3}]}
    assert _validar_diagrama(d, "") is None
    assert entrada.svg_permitido(render_diagram(d, "U12")) is True


def test_id_de_jugador_con_html_se_rechaza_y_se_escapa():
    d = {"tipo": "media_pista", "jugadores_ataque": [{"id": "<img src=x onerror=alert(1)>", "x": 50, "y": 50}],
         "jugadores_defensa": [], "movimientos": []}
    assert "no válido" in _validar_diagrama(dict(d), "")
    assert "<img" not in render_diagram(d, "U12")
