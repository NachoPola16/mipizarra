# tests/test_fichas_admin_web.py
"""Pestaña «Fichas» (frontend/pizarra/fichas_admin.py): solo la cuenta administradora; la web pasa las peticiones a
la API. Subproceso con base en memoria y la API simulada, como test_cuentas.py."""
import os
import subprocess
import sys
import textwrap

import pytest

from conftest import RAIZ

pytest.importorskip("django")
pytest.importorskip("whitenoise")

GUION = textwrap.dedent('''
    import json
    from unittest import mock
    import django
    django.setup()
    from django.core.management import call_command
    from django.contrib.auth import get_user_model
    from django.test import Client
    call_command("migrate", verbosity=0)
    U = get_user_model()
    U.objects.create_user("nacho", password="clave-de-prueba-3")
    U.objects.create_user("beto", password="clave-de-prueba-2")
    H = {"HTTP_HOST": "localhost"}

    class Resp:
        def __init__(self, status, cuerpo): self.status_code, self._c = status, cuerpo
        def json(self): return self._c

    def entra(usuario, clave):
        c = Client(); assert c.login(username=usuario, password=clave); return c

    def put(c, ficha_id, ficha):
        return c.put(f"/fichas/{ficha_id}/", data=json.dumps({"ficha": ficha}), content_type="application/json", **H)

    beto = entra("beto", "clave-de-prueba-2")
    nacho = entra("nacho", "clave-de-prueba-3")
    anon = Client()

    # sin sesión: al login; otra cuenta: 404 en la página y 403 en la API; ni siquiera se llama a la API
    with mock.patch("pizarra.fichas_admin.requests") as rq:
        assert anon.get("/fichas/", **H).status_code == 302
        assert anon.put("/fichas/ej_001/", data="{}", content_type="application/json", **H).status_code == 401
        assert beto.get("/fichas/", **H).status_code == 404
        assert beto.get("/fichas/datos/", **H).status_code == 403
        assert put(beto, "ej_001", {}).status_code == 403
        assert beto.delete("/fichas/ej_001/", **H).status_code == 403
        assert not rq.get.called and not rq.put.called and not rq.delete.called
    # la pestaña solo se ve para el administrador
    assert b"/fichas/" not in beto.get("/", **H).content and b"/fichas/" in nacho.get("/", **H).content
    assert b"/fichas/" not in beto.get("/jugadas/", **H).content and b"/fichas/" in nacho.get("/jugadas/", **H).content

    # administrador: página, lista y guardado pasan por la API con el secreto y la cuenta
    r = nacho.get("/fichas/", **H); assert r.status_code == 200 and b"fichas.js" in r.content and b"<script>" not in r.content
    with mock.patch("pizarra.fichas_admin.requests.get", return_value=Resp(200, {"fichas": [{"id": "ej_001"}], "modificadas": []})) as g:
        r = nacho.get("/fichas/datos/", **H); assert r.status_code == 200 and r.json()["fichas"][0]["id"] == "ej_001"
        assert g.call_args.args[0].endswith("/admin/fichas") and g.call_args.kwargs["headers"]["X-Usuario"]
    with mock.patch("pizarra.fichas_admin.requests.put", return_value=Resp(422, {"detail": "La ficha no es válida", "problemas": ["duracion_min: x"]})):
        r = put(nacho, "ej_001", {"nombre": "x"})
        assert r.status_code == 422 and r.json()["problemas"] == ["duracion_min: x"] and r.json()["error"]
    with mock.patch("pizarra.fichas_admin.requests.put", return_value=Resp(200, {"ok": True, "ficha": {"id": "ej_001"}})) as p:
        assert put(nacho, "ej_001", {"nombre": "x"}).status_code == 200
        assert json.loads(p.call_args.kwargs["data"]) == {"ficha": {"nombre": "x"}}
    with mock.patch("pizarra.fichas_admin.requests.delete", return_value=Resp(200, {"ok": True, "ficha": {}})) as d:
        assert nacho.delete("/fichas/ej_001/", **H).status_code == 200 and d.called
    # API caída
    import requests
    with mock.patch("pizarra.fichas_admin.requests.get", side_effect=requests.ConnectionError()):
        assert nacho.get("/fichas/datos/", **H).status_code == 502
    # el CSRF se exige al guardar
    c = Client(enforce_csrf_checks=True); c.login(username="nacho", password="clave-de-prueba-3")
    assert put(c, "ej_001", {}).status_code == 403
    print("OK")
''')


def test_pestana_de_fichas_solo_para_el_administrador():
    entorno = {**os.environ, "DJANGO_SETTINGS_MODULE": "mipizarra_cfg.settings", "DJANGO_DB_PATH": ":memory:",
               "DJANGO_DEBUG": "True", "DJANGO_SECRET_KEY": "clave-solo-para-tests", "PYTHONIOENCODING": "utf-8",
               "PYTHONUTF8": "1", "PYTHONPATH": str(RAIZ / "frontend"), "JUGADAS_ADMIN": "nacho", "INTERNAL_SECRET": "s"}
    r = subprocess.run([sys.executable, "-c", GUION], capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=entorno, cwd=str(RAIZ / "frontend"), timeout=120)
    assert r.returncode == 0 and r.stdout.strip().endswith("OK"), r.stdout + r.stderr
