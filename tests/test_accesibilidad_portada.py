# tests/test_accesibilidad_portada.py
"""Mínimos de accesibilidad de la portada (index.html): comprobaciones estáticas, la interacción se probó en el navegador."""
import re

from conftest import RAIZ

HTML = (RAIZ / "frontend" / "pizarra" / "templates" / "pizarra" / "index.html").read_text(encoding="utf-8")


def test_hay_enlace_de_salto_al_contenido():
    assert 'href="#contenido"' in HTML and 'id="contenido"' in HTML


def test_el_foco_del_teclado_es_visible():
    assert ":focus-visible" in HTML
    # los campos que quitan el contorno por defecto lo recuperan con una regla propia
    assert ".prompt-box:focus-within" in HTML and ".reprompt-bar textarea:focus-visible" in HTML


def test_las_pestanas_indican_cual_esta_activa():
    assert re.search(r'data-mode="sesion" aria-pressed="true"', HTML)
    assert re.search(r'data-mode="reglamento" aria-pressed="false"', HTML)
    assert "setAttribute('aria-pressed'" in HTML


def test_el_campo_de_correccion_tiene_etiqueta():
    assert re.search(r'<textarea id="reprompt-instruccion"[^>]*aria-label=', HTML)
