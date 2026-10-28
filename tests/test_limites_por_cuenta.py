# tests/test_limites_por_cuenta.py
"""Los límites de la API cuentan por cuenta (cabecera X-Usuario del frontend), no por la IP del contenedor del
frontend, que es la misma para todos."""
from types import SimpleNamespace

import main


def _peticion(usuario=None, ip="172.18.0.5"):
    cabeceras = {"X-Usuario": usuario} if usuario is not None else {}
    return SimpleNamespace(headers=cabeceras, client=SimpleNamespace(host=ip))


def test_con_secreto_cada_cuenta_tiene_su_limite(monkeypatch):
    monkeypatch.setattr(main, "INTERNAL_SECRET", "s")
    assert main._clave_de_limite(_peticion("3")) == "u3"
    assert main._clave_de_limite(_peticion("3")) != main._clave_de_limite(_peticion("4"))


def test_sin_secreto_no_se_fia_de_la_cabecera(monkeypatch):
    monkeypatch.setattr(main, "INTERNAL_SECRET", "")
    assert main._clave_de_limite(_peticion("3")) == "172.18.0.5"


def test_sin_cuenta_o_con_cuenta_rara_cuenta_la_ip(monkeypatch):
    monkeypatch.setattr(main, "INTERNAL_SECRET", "s")
    for usuario in (None, "", "abc", "1; DROP", "12345678901"):
        assert main._clave_de_limite(_peticion(usuario)) == "172.18.0.5"


# ── CSP: sin scripts en línea ─────────────────────────────────────────────────

def test_ninguna_plantilla_lleva_js_en_linea_y_la_csp_no_lo_permite():
    import re
    from conftest import RAIZ
    plantillas = (RAIZ / "frontend" / "pizarra" / "templates").rglob("*.html")
    for ruta in plantillas:
        html = ruta.read_text(encoding="utf-8")
        assert not re.search(r"<script(?![^>]*\bsrc=)[^>]*>", html), f"script en línea en {ruta.name}"
        assert not re.search(r"\son[a-z]+\s*=\s*[\"']", html), f"manejador en línea en {ruta.name}"
    middleware = (RAIZ / "frontend" / "mipizarra_cfg" / "middleware.py").read_text(encoding="utf-8")
    assert "script-src 'self';" in middleware
