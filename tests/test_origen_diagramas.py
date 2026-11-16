# tests/test_origen_diagramas.py
"""DIA-02: cada diagrama de /generar dice de dónde sale, para medir cuántos diagramas del modelo son válidos."""
import pytest
from fastapi.testclient import TestClient

import main


@pytest.fixture(autouse=True)
def _limites_limpios():
    # /generar admite 3 por minuto: que estos tests no gasten el cupo de los que van después
    main.limiter.reset()
    yield
    main.limiter.reset()


def _dibujo(titulo=None):
    d = {"tipo": "media_pista", "jugadores_ataque": [{"id": "A1", "x": 50, "y": 60}], "jugadores_defensa": [],
         "balon_inicio": {"portador": "A1"}, "movimientos": []}
    return {**d, "titulo": titulo} if titulo else d


def _sesion(monkeypatch, fichas, coordenadas):
    main.limiter.reset()
    texto = "**PARTE PRINCIPAL**\n\n" + "".join(
        f"Ejercicio {i}: {f['nombre']}\nDuración: 10 min\nOrganización: x.\n\n" for i, f in enumerate(fichas, 1))
    texto += "Ejercicio 9: Juego inventado por la IA\nDuración: 10 min\nOrganización: tres jugadores pasan y tiran.\n"
    monkeypatch.setattr(main, "generar_sesion", lambda **k: {"texto": texto, "ejercicios_usados": fichas})
    monkeypatch.setattr(main, "generar_coordenadas_ejercicio", lambda t, n: coordenadas)
    r = TestClient(main.app).post("/generar", json={"edad": "U14", "duracion": 60, "objetivo": "pase"})
    assert r.status_code == 200
    return {d["nombre"]: [x for x in r.json()["diagramas"] if x["nombre"] == d["nombre"]] for d in r.json()["diagramas"]}


def test_origen_de_cada_diagrama(monkeypatch):
    fichas = [{"id": "ej_a", "nombre": "Una fase", "descripcion": "d", "diagrama": _dibujo()},
              {"id": "ej_b", "nombre": "Dos fases", "descripcion": "d", "diagramas": [_dibujo("F1"), _dibujo("F2")]},
              {"id": "ej_c", "nombre": "Juego libre", "descripcion": "d", "sin_diagrama": True}]
    por_nombre = _sesion(monkeypatch, fichas, _dibujo())
    assert [d["origen"] for d in por_nombre["Una fase"]] == ["biblioteca"]
    assert [d["origen"] for d in por_nombre["Dos fases"]] == ["biblioteca", "biblioteca"]
    assert [d["origen"] for d in por_nombre["Juego libre"]] == ["sin_diagrama"]
    assert [d["origen"] for d in por_nombre["Juego inventado por la IA"]] == ["modelo"]


def test_si_el_modelo_no_dibuja_es_no_disponible(monkeypatch):
    por_nombre = _sesion(monkeypatch, [], None)
    assert [d["origen"] for d in por_nombre["Juego inventado por la IA"]] == ["no_disponible"]
