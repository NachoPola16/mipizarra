# tests/test_biblioteca_jugadas_no_publica.py
"""The play library (jugadas.json) is private: it must never be collected into STATIC_ROOT, where WhiteNoise would serve
it without a login. The login-protected view reads it from the app directory instead."""
import re

from conftest import RAIZ


def test_collectstatic_ignora_la_biblioteca_de_jugadas():
    dockerfile = (RAIZ / "frontend" / "Dockerfile").read_text(encoding="utf-8")
    ordenes = [l for l in dockerfile.splitlines() if re.match(r"\s*RUN .*collectstatic", l)]
    assert ordenes, "the Dockerfile must run collectstatic"
    assert all(re.search(r"--ignore[ =]jugadas\.json|-i jugadas\.json", l) for l in ordenes), ordenes
