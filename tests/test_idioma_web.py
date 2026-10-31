# tests/test_idioma_web.py
"""Idioma de la interfaz web (frontend/pizarra/idioma.py y textos_en.py): `?lang=en` guarda una cookie y redirige, la
página sale en inglés o en español según la cookie, el JavaScript recibe sus textos y el catálogo no pierde claves.
Se ejecuta en un subproceso con una base de datos en memoria, como test_cuentas."""
import os
import re
import subprocess
import sys
import textwrap

import pytest

from conftest import RAIZ

pytest.importorskip("django")
pytest.importorskip("whitenoise")

GUION = textwrap.dedent('''
    import django
    django.setup()
    from django.core.management import call_command
    from django.contrib.auth import get_user_model
    from django.test import Client
    call_command("migrate", verbosity=0)
    get_user_model().objects.create_user("alicia", password="clave-de-prueba-1")
    H = {"HTTP_HOST": "localhost"}

    c = Client()
    c.login(username="alicia", password="clave-de-prueba-1")

    # por defecto, español, sin selector roto
    r = c.get("/", **H)
    html = r.content.decode()
    assert '<html lang="es">' in html and "¿Qué quieres trabajar hoy?" in html and "Generar sesión" in html
    assert 'id="ui-t"' in html and 'aria-current="true">ES<' in html

    # ?lang=en: cookie + redirección a la misma página sin el parámetro, conservando el resto
    r = c.get("/?lang=en&otro=1", **H)
    assert r.status_code == 302 and r["Location"] == "/?otro=1", r["Location"]
    assert c.cookies["lang"].value == "en"
    r = c.get("/", **H)
    html = r.content.decode()
    assert '<html lang="en">' in html and "What do you want to work on today?" in html and "Generate session" in html
    assert "Age group: any" in html and "Up to 10" in html and "Sign out" in html
    assert 'aria-current="true">EN<' in html and "?lang=es" in html
    assert "write the goal in Spanish" in html
    assert "Checking the rules" in html         # ...que sí está, con la traducción
    # lo que no está en el catálogo se queda en español en vez de romperse
    assert "Tiro en suspensión" in html

    # una cookie inválida o un parámetro inválido no cambian nada
    c.cookies["lang"] = "fr"
    assert '<html lang="es">' in c.get("/", **H).content.decode()
    r = c.get("/?lang=fr", **H)
    assert r.status_code == 200

    # la pantalla de entrada (pública) también se traduce y su selector conserva ?next
    anon = Client()
    anon.cookies["lang"] = "en"
    html = anon.get("/cuenta/entrar/?next=/jugadas/", **H).content.decode()
    assert "Sign in — MiPizarra" in html and "Username" in html and "Password" in html
    assert "next=%2Fjugadas%2F&amp;lang=es" in html or "next=%2Fjugadas%2F&lang=es" in html, html[html.find("idioma"):][:400]
    r = anon.get("/cuenta/entrar/?next=/jugadas/&lang=es", **H)
    assert r.status_code == 302 and r["Location"] == "/cuenta/entrar/?next=%2Fjugadas%2F"

    # las páginas legales siguen en español y cargan
    for ruta in ("/privacidad/", "/aviso-legal/"):
        assert anon.get(ruta, **H).status_code == 200
    print("OK")
''')


def test_idioma_de_la_interfaz():
    entorno = {**os.environ, "DJANGO_SETTINGS_MODULE": "mipizarra_cfg.settings", "DJANGO_DB_PATH": ":memory:",
               "DJANGO_DEBUG": "True", "DJANGO_SECRET_KEY": "clave-solo-para-tests", "PYTHONIOENCODING": "utf-8",
               "PYTHONUTF8": "1", "PYTHONPATH": str(RAIZ / "frontend")}
    r = subprocess.run([sys.executable, "-c", GUION], capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=entorno, cwd=str(RAIZ / "frontend"), timeout=120)
    assert r.returncode == 0 and "OK" in r.stdout, r.stdout[-1500:] + r.stderr[-2500:]


def _claves(texto, patron):
    return set(re.findall(patron, texto))


def test_el_catalogo_cubre_la_interfaz():
    """Cada `{% t "..." %}` de las plantillas y cada `tr('...')` del JavaScript tiene su traducción al inglés."""
    sys.path.insert(0, str(RAIZ / "frontend"))
    try:
        from pizarra.textos_en import JS_EN, TEXTOS_EN
    finally:
        sys.path.pop(0)
    pizarra = RAIZ / "frontend" / "pizarra"
    faltan = []
    for plantilla in ("index.html", "_cabecera.html", "entrar.html"):
        for clave in _claves((pizarra / "templates" / "pizarra" / plantilla).read_text(encoding="utf-8"), r'\{% t "([^"]+)" %\}'):
            if clave not in TEXTOS_EN:
                faltan.append((plantilla, clave))
    js = (pizarra / "static" / "pizarra" / "js" / "index.js").read_text(encoding="utf-8")
    for clave in _claves(js, r"tr\('((?:[^'\\]|\\.)*)'"):
        if clave not in JS_EN:
            faltan.append(("index.js", clave))
    assert not faltan, faltan
    # los huecos {x} de cada traducción son los mismos que los del texto original
    for catalogo in (TEXTOS_EN, JS_EN):
        for es, en in catalogo.items():
            assert set(re.findall(r"\{(\w+)\}", es)) == set(re.findall(r"\{(\w+)\}", en)), (es, en)
