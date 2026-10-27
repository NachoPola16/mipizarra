# tests/test_jugadas.py
"""Editor de jugadas (frontend/pizarra/.../jugadas.*): comprobaciones estáticas. La interacción se probó a mano en el navegador."""
import re
import shutil
import subprocess

import pytest

from conftest import RAIZ

PIZARRA = RAIZ / "frontend" / "pizarra"
JS = PIZARRA / "static" / "pizarra" / "js" / "jugadas.js"
PLANTILLA = PIZARRA / "templates" / "pizarra" / "jugadas.html"


@pytest.mark.skipif(shutil.which("node") is None, reason="Node no está instalado")
def test_el_js_tiene_sintaxis_valida():
    r = subprocess.run(["node", "--check", str(JS)], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr


def test_el_js_no_inyecta_html():
    # Las jugadas importadas son datos de fuera: solo textContent y atributos, nunca HTML.
    js = JS.read_text(encoding="utf-8")
    assert not re.search(r"innerHTML|outerHTML|insertAdjacentHTML|document\.write|eval\(", js)


def test_la_plantilla_es_accesible_y_enlaza_sus_recursos():
    html = PLANTILLA.read_text(encoding="utf-8")
    assert '<html lang="es">' in html
    assert 'role="status"' in html and "aria-live" in html
    assert "<script>" not in html  # sin JS en línea: cabe en una CSP más estricta
    for ruta in ("css/jugadas.css", "js/jugadas.js"):
        assert f"pizarra/{ruta}" in html
        assert (PIZARRA / "static" / "pizarra" / ruta).exists()


def test_la_portada_enlaza_a_jugadas_y_la_url_existe():
    assert "name='jugadas'" in (PIZARRA / "urls.py").read_text(encoding="utf-8")
    assert "{% url 'jugadas' %}" in (PIZARRA / "templates" / "pizarra" / "index.html").read_text(encoding="utf-8")
