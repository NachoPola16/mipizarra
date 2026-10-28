# tests/test_cuentas.py
"""Cuentas y jugadas guardadas (frontend/pizarra/cuentas.py). Se ejecutan en un subproceso con una base de datos en
memoria para no mezclar la configuración de Django con el resto de la suite."""
import os
import subprocess
import sys
import textwrap

import pytest

from conftest import RAIZ

pytest.importorskip("django")
pytest.importorskip("whitenoise")

GUION = textwrap.dedent('''
    import json, os
    import django
    django.setup()
    from django.core.management import call_command
    from django.contrib.auth import get_user_model
    from django.test import Client
    call_command("migrate", verbosity=0)
    U = get_user_model()
    U.objects.create_user("alicia", password="clave-de-prueba-1")
    U.objects.create_user("beto", password="clave-de-prueba-2")
    U.objects.create_user("nacho", password="clave-de-prueba-3")
    H = {"HTTP_HOST": "localhost"}

    JUGADA = {"fases": [{"piezas": [{"tipo": "A", "n": 1, "x": 100, "y": 200}, {"tipo": "B", "n": 0, "x": 110, "y": 210}],
                         "flechas": [{"tipo": "corte", "de": "A1", "a": {"x": 300.55, "y": 100}, "curva": 0.2}]}]}

    def post(c, url, cuerpo, **kw):
        return c.post(url, data=json.dumps(cuerpo), content_type="application/json", **H, **kw)

    # sin sesión: 401 en la API y la página del editor carga sin usuario
    anon = Client()
    assert anon.get("/jugadas/guardadas/", **H).status_code == 401
    # toda la web exige cuenta: las páginas redirigen al login y las llamadas del navegador reciben 401 en JSON
    for ruta in ("/", "/jugadas/"):
        r = anon.get(ruta, **H); assert r.status_code == 302 and r["Location"].startswith("/cuenta/entrar/?next="), ruta
    for ruta in ("/generar/", "/pdf/", "/reglamento/", "/reprompt/", "/feedback/"):
        r = anon.post(ruta, data="{}", content_type="application/json", **H)
        assert r.status_code == 401 and "error" in r.json(), ruta
    for ruta in ("/cuenta/entrar/", "/privacidad/", "/aviso-legal/"):      # públicas
        assert anon.get(ruta, **H).status_code == 200, ruta
    assert anon.get("/jugadas/guardadas/1/", **H).status_code == 401

    # el CSRF se exige
    c = Client(enforce_csrf_checks=True)
    assert c.login(username="alicia", password="clave-de-prueba-1")
    assert post(c, "/jugadas/guardadas/", {"nombre": "x", "datos": JUGADA}).status_code == 403

    # con sesión y token: guardar, listar, abrir, actualizar y borrar
    c = Client(); c.login(username="alicia", password="clave-de-prueba-1")
    r = post(c, "/jugadas/guardadas/", {"nombre": "Mi jugada", "datos": JUGADA}); assert r.status_code == 201, r.content
    pk = r.json()["id"]
    assert post(c, "/jugadas/guardadas/", {"nombre": "Mi jugada", "datos": JUGADA}).status_code == 200      # actualiza, no duplica
    assert [j["nombre"] for j in c.get("/jugadas/guardadas/", **H).json()["jugadas"]] == ["Mi jugada"]
    datos = c.get(f"/jugadas/guardadas/{pk}/", **H).json()["datos"]
    assert datos["fases"][0]["flechas"][0]["curva"] == 0.2 and datos["fases"][0]["piezas"][0]["id"] == "A1"
    assert b"alicia" in c.get("/jugadas/", **H).content

    # otra cuenta no ve ni borra las jugadas ajenas
    b = Client(); b.login(username="beto", password="clave-de-prueba-2")
    assert b.get(f"/jugadas/guardadas/{pk}/", **H).status_code == 404
    assert b.delete(f"/jugadas/guardadas/{pk}/", **H).status_code == 404
    assert b.get("/jugadas/guardadas/", **H).json()["jugadas"] == []

    # lo que no tiene la forma esperada se rechaza
    for malo in ({"fases": []}, {"fases": [{"piezas": [{"tipo": "Z", "n": 1, "x": 1, "y": 1}]}]},
                 {"fases": [{"piezas": [{"tipo": "A", "n": 1, "x": "<script>", "y": 1}]}]}, "texto", None):
        assert post(c, "/jugadas/guardadas/", {"nombre": "mala", "datos": malo}).status_code == 400
    assert post(c, "/jugadas/guardadas/", {"nombre": "  ", "datos": JUGADA}).status_code == 400
    assert c.get("/jugadas/guardadas/", **H).json()["jugadas"][0]["nombre"] == "Mi jugada"

    assert c.delete(f"/jugadas/guardadas/{pk}/", **H).status_code == 200
    assert c.get("/jugadas/guardadas/", **H).json()["jugadas"] == []

    # inicio de sesión: error con clave mala y freno tras varios fallos
    f = Client()
    for _ in range(8):
        assert f.post("/cuenta/entrar/", {"username": "alicia", "password": "mala"}, **H).status_code == 200
    r = f.post("/cuenta/entrar/", {"username": "alicia", "password": "clave-de-prueba-1"}, **H)
    assert r.status_code == 429
    # la cabecera de la portada muestra la cuenta y salir vuelve a la misma página (nunca a un sitio de fuera)
    g = Client(); g.login(username="beto", password="clave-de-prueba-2")
    assert b"Salir (beto)" in g.get("/", **H).content
    r = g.post("/cuenta/salir/", {"next": "/jugadas/"}, **H); assert r.status_code == 302 and r["Location"] == "/jugadas/"
    g.login(username="beto", password="clave-de-prueba-2")
    r = g.post("/cuenta/salir/", {"next": "https://sitio-malo.example/"}, **H); assert r.status_code == 302 and r["Location"] == "/"
    # biblioteca: solo el administrador (nacho) la cambia; los demás la ven con los cambios
    base = anon.get("/jugadas/biblioteca.json", **H)
    assert base.status_code == 302                      # como el resto de la web, exige cuenta
    biblio = c.get("/jugadas/biblioteca.json", **H).json(); n0 = len(biblio); jid = biblio[0]["id"]
    assert b'id="btn-bib-guardar"' not in c.get("/jugadas/", **H).content        # el botón no existe para los demás
    cambio = {"nombre": "Cambiada", "fases": [{"piezas": [{"tipo": "A", "n": 1, "x": 10, "y": 20}, {"tipo": "A", "n": 2, "x": 50, "y": 60}],
              "flechas": [{"tipo": "corte", "de": "A1", "a": {"x": 30, "y": 30}}, {"tipo": "bote", "de": "A1", "a": {"x": 40, "y": 40}, "sigue": True}]}], "defensa": True}
    assert post(c, f"/jugadas/biblioteca/{jid}/", {"datos": cambio}).status_code == 403       # alicia no
    assert c.delete(f"/jugadas/biblioteca/{jid}/", **H).status_code == 403
    assert post(c, "/jugadas/biblioteca/nueva/", {"datos": cambio}).status_code == 403
    assert len(c.get("/jugadas/biblioteca.json", **H).json()) == n0
    n = Client(); n.login(username="nacho", password="clave-de-prueba-3")
    assert b'id="btn-bib-guardar"' in n.get("/jugadas/", **H).content
    assert post(n, f"/jugadas/biblioteca/{jid}/", {"datos": cambio}).status_code == 200
    nueva = [j for j in c.get("/jugadas/biblioteca.json", **H).json() if j["id"] == jid][0]      # alicia ve lo que guardó nacho
    assert nueva["nombre"] == "Cambiada" and nueva["fases"][0]["flechas"][1]["sigue"] is True and nueva["defensa"] is True
    assert nueva["edades"] == biblio[0]["edades"] and len(c.get("/jugadas/biblioteca.json", **H).json()) == n0       # conserva la ficha
    r = post(n, "/jugadas/biblioteca/nueva/", {"datos": cambio}); assert r.status_code == 200
    assert len(c.get("/jugadas/biblioteca.json", **H).json()) == n0 + 1 and r.json()["id"] not in [j["id"] for j in biblio]
    assert post(n, "/jugadas/biblioteca/x/", {"datos": cambio}).status_code == 403             # id raro
    assert post(n, f"/jugadas/biblioteca/{jid}/", {"datos": {"fases": []}}).status_code == 400
    assert n.delete(f"/jugadas/biblioteca/{jid}/", **H).status_code == 200                       # restaura la original
    assert n.delete("/jugadas/biblioteca/" + r.json()["id"] + "/", **H).status_code == 200      # y la nueva desaparece
    assert c.get("/jugadas/biblioteca.json", **H).json() == biblio
    print("OK")
''')


def test_cuentas_y_jugadas_guardadas():
    entorno = {**os.environ, "DJANGO_SETTINGS_MODULE": "mipizarra_cfg.settings", "DJANGO_DB_PATH": ":memory:",
               "DJANGO_DEBUG": "True", "DJANGO_SECRET_KEY": "clave-solo-para-tests", "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1", "PYTHONPATH": str(RAIZ / "frontend")}
    r = subprocess.run([sys.executable, "-c", GUION], capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=entorno, cwd=str(RAIZ / "frontend"), timeout=120)
    assert r.returncode == 0 and r.stdout.strip().endswith("OK"), r.stdout + r.stderr
