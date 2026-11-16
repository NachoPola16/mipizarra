# tests/test_pdf_limite_y_admin.py
"""Límite de PDF por cuenta y administrador vacío por defecto. Subproceso con base en memoria, como test_cuentas.py."""
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
    import django
    django.setup()
    from django.core.cache import cache
    from django.core.management import call_command
    from django.contrib.auth import get_user_model
    from django.test import Client
    from pizarra import views, cuentas
    call_command("migrate", verbosity=0)
    U = get_user_model()
    U.objects.create_user("alicia", password="clave-de-prueba-1")
    U.objects.create_user("beto", password="clave-de-prueba-2")
    U.objects.create_user("nacho", password="clave-de-prueba-3")
    H = {"HTTP_HOST": "localhost"}
    views._generar_pdf = lambda *a, **k: b"%PDF-falso"          # el límite no depende del coste real del render
    CUERPO = {"sesion": "**CALENTAMIENTO (10 min)**\\nJuego: pilla", "edad": "U12", "objetivo": "bote", "duracion": 60, "diagramas": []}

    def pdf(c):
        return c.post("/pdf/", data=json.dumps(CUERPO), content_type="application/json", **H)

    cache.clear()
    a = Client(); a.login(username="alicia", password="clave-de-prueba-1")
    b = Client(); b.login(username="beto", password="clave-de-prueba-2")
    for i in range(views.PDF_MAX):
        assert pdf(a).status_code == 200, i
    r = pdf(a)
    assert r.status_code == 429 and r["Retry-After"] == str(views.PDF_VENTANA_S) and r.json()["retry_after"] == views.PDF_VENTANA_S
    assert pdf(b).status_code == 200                      # el cupo es por cuenta, no global

    # administrador: sin JUGADAS_ADMIN nadie lo es, aunque se llame «nacho»
    from django.test import RequestFactory
    from django.contrib.auth.models import AnonymousUser
    rf = RequestFactory().get("/")
    rf.user = U.objects.get(username="nacho")
    assert cuentas._es_admin(rf) is False
    print("OK")
''')


def test_pdf_limitado_por_cuenta_y_sin_admin_por_defecto():
    entorno = {k: v for k, v in os.environ.items() if k != "JUGADAS_ADMIN"}
    entorno.update({"DJANGO_SETTINGS_MODULE": "mipizarra_cfg.settings", "DJANGO_DB_PATH": ":memory:",
                    "DJANGO_DEBUG": "True", "DJANGO_SECRET_KEY": "clave-solo-para-tests",
                    "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1", "PYTHONPATH": str(RAIZ / "frontend")})
    r = subprocess.run([sys.executable, "-c", GUION], capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=entorno, cwd=str(RAIZ / "frontend"), timeout=120)
    assert r.returncode == 0 and r.stdout.strip().endswith("OK"), r.stdout + r.stderr
