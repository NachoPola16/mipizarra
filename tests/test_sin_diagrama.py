# tests/test_sin_diagrama.py
"""Las fichas de juego libre marcadas «sin_diagrama» muestran un recuadro neutro:
no se intenta dibujar nada y el hueco conserva su posición en la lista de diagramas."""
import pytest
from fastapi.testclient import TestClient

import main

TEXTO = """\
**PARTE PRINCIPAL**

Ejercicio 1: Bote y globo a la vez
Duración: 10 min
Organización: Un balón y un globo por jugador.

Ejercicio 2: Periódico en el pecho: relevos con bote
Duración: 10 min
Organización: Relevos por equipos.
"""


def _ficha(ejercicios, id_):
    return next(e for e in ejercicios if e["id"] == id_)


@pytest.fixture
def cliente(monkeypatch, ejercicios):
    fichas = [_ficha(ejercicios, "ej_068"), _ficha(ejercicios, "ej_067")]
    monkeypatch.setattr(main, "generar_sesion",
                        lambda **k: {"texto": TEXTO, "ejercicios_usados": fichas})
    llamadas = []

    def coordenadas(texto, nombre):
        llamadas.append(nombre)
        return None

    monkeypatch.setattr(main, "generar_coordenadas_ejercicio", coordenadas)
    c = TestClient(main.app)
    c.llamadas = llamadas
    return c


def test_la_ficha_sin_diagrama_no_intenta_dibujar_y_conserva_su_posicion(cliente):
    r = cliente.post("/generar", json={"edad": "U10", "duracion": 60, "objetivo": "bote"})
    assert r.status_code == 200
    diagramas = r.json()["diagramas"]
    assert [d["id"] for d in diagramas[:2]] == ["ej_068", "ej_067"]
    assert "Juego libre" in diagramas[0]["svg"]
    assert "Diagrama no disponible" not in diagramas[0]["svg"]
    assert "Bote y globo a la vez" not in cliente.llamadas


def test_la_ficha_con_diagrama_propio_se_dibuja_con_normalidad(cliente):
    r = cliente.post("/generar", json={"edad": "U10", "duracion": 60, "objetivo": "bote"})
    assert "Juego libre" not in r.json()["diagramas"][1]["svg"]


def test_una_ficha_no_puede_ser_sin_diagrama_y_traer_diagrama(ejercicios):
    for ej in ejercicios:
        if ej.get("sin_diagrama"):
            assert "diagrama" not in ej and "diagramas" not in ej, ej["id"]


def test_el_calentamiento_estandar_se_dibuja_con_su_plantilla(monkeypatch, cliente):
    texto = TEXTO + ("\n**CALENTAMIENTO (10 min)**\nJuego: Zigzag con bote\n"
                     "Reglas: Cada jugador zigzaguea entre conos.\nEspacio: media pista.\n")
    monkeypatch.setattr(main, "generar_sesion", lambda **k: {"texto": texto, "ejercicios_usados": []})
    r = cliente.post("/generar", json={"edad": "U10", "duracion": 60, "objetivo": "bote"})
    d = next(x for x in r.json()["diagramas"] if x["id"] == "calentamiento")
    assert "<svg" in d["svg"] and "no disponible" not in d["svg"]
    assert not any("Zigzag" in n for n in cliente.llamadas)


def test_generar_devuelve_los_avisos_de_la_sesion(monkeypatch):
    main.limiter.reset()      # /generar admite 3 por minuto y este fichero ya las ha gastado
    # sin esto el entrenador nunca se entera de que se hizo algo en línea roja o de que se omitió una pieza
    monkeypatch.setattr(main, "generar_sesion",
                        lambda **k: {"texto": TEXTO, "ejercicios_usados": [], "avisos": ["Has pedido «bloqueo»."]})
    r = TestClient(main.app).post("/generar", json={"objetivo": "bloqueo", "edad": "U12", "duracion": 60,
                                                    "generar_diagramas": False})
    assert r.status_code == 200
    assert r.json()["avisos"] == ["Has pedido «bloqueo»."]
