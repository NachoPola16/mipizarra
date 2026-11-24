"""Instalable como app: service worker mínimo en /sw.js (público, sin caché) y manifiesto con iconos PNG.
La parte de Django va en un subproceso con base en memoria, como el resto de pruebas de cuentas."""
import json
import os
import subprocess
import sys
import textwrap

import pytest

from conftest import RAIZ

pytest.importorskip("django")
pytest.importorskip("whitenoise")

MARCA = RAIZ / "frontend" / "pizarra" / "static" / "pizarra" / "brand"


def test_manifiesto_con_id_scope_e_iconos_png_y_maskable():
    m = json.loads((MARCA / "site.webmanifest").read_text(encoding="utf-8"))
    assert m["id"] == "/" and m["scope"] == "/" and m["start_url"].startswith(m["scope"])
    combos = {(i["sizes"], i.get("purpose", "any")) for i in m["icons"] if i["type"] == "image/png"}
    assert {("192x192", "any"), ("512x512", "any"), ("192x192", "maskable"), ("512x512", "maskable")} <= combos
    for i in m["icons"]:
        assert (MARCA / i["src"].rsplit("/", 1)[1]).is_file(), i["src"]


GUION = textwrap.dedent('''
    import django
    django.setup()
    from django.test import Client
    H = {"HTTP_HOST": "localhost"}
    c = Client()
    r = c.get("/sw.js", **H)  # sin sesión: debe ser público
    assert r.status_code == 200, r.status_code
    assert "javascript" in r["Content-Type"]
    assert r["Cache-Control"] == "no-cache" and r["Service-Worker-Allowed"] == "/"
    cuerpo = r.content.decode()
    assert "skipWaiting" in cuerpo and "caches." not in cuerpo
    assert b"js/sw-registro" in c.get("/cuenta/entrar/", **H).content
    assert c.get("/", **H).status_code == 302  # el resto sigue exigiendo cuenta
    print("OK")
''')


def test_service_worker_publico_sin_cache_y_registrado_en_la_entrada():
    entorno = {**os.environ, "DJANGO_SETTINGS_MODULE": "mipizarra_cfg.settings", "DJANGO_DB_PATH": ":memory:",
               "DJANGO_DEBUG": "True", "DJANGO_SECRET_KEY": "clave-solo-para-tests", "PYTHONIOENCODING": "utf-8",
               "PYTHONUTF8": "1", "PYTHONPATH": str(RAIZ / "frontend")}
    r = subprocess.run([sys.executable, "-c", GUION], capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=entorno, cwd=str(RAIZ / "frontend"), timeout=120)
    assert r.returncode == 0 and r.stdout.strip().endswith("OK"), r.stdout + r.stderr
