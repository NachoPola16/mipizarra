# tests/test_gpu_una_a_la_vez.py
"""SEG-02: los endpoints que usan el modelo no bloquean el resto de la API y solo genera una petición a la vez."""
import threading
import time

import pytest
from fastapi.testclient import TestClient

import main


@pytest.fixture(autouse=True)
def _limites_limpios():
    # /generar admite 3 por minuto: que estos tests no gasten el cupo de los que van después
    main.limiter.reset()
    yield
    main.limiter.reset()


def test_la_api_sigue_respondiendo_mientras_se_genera(monkeypatch):
    main.limiter.reset()
    entrada, salida = threading.Event(), threading.Event()

    def lenta(**k):
        entrada.set()
        salida.wait(5)
        return {"texto": "**PARTE PRINCIPAL**\n", "ejercicios_usados": []}

    monkeypatch.setattr(main, "generar_sesion", lenta)
    resultado = {}
    hilo = threading.Thread(target=lambda: resultado.setdefault(
        "r", TestClient(main.app).post("/generar", json={"objetivo": "bote", "generar_diagramas": False})))
    hilo.start()
    assert entrada.wait(5)
    inicio = time.monotonic()
    r = TestClient(main.app).get("/")                       # la portada pide /ambitos_reglamento con 3 s de espera
    assert r.status_code == 200 and time.monotonic() - inicio < 0.5
    assert TestClient(main.app).get("/ambitos_reglamento").status_code == 200
    salida.set()
    hilo.join(5)
    assert resultado["r"].status_code == 200


def test_con_la_gpu_ocupada_se_contesta_503(monkeypatch):
    main.limiter.reset()
    monkeypatch.setattr(main, "GPU_ESPERA_S", 0)
    monkeypatch.setattr(main, "generar_sesion", lambda **k: {"texto": "x", "ejercicios_usados": []})
    assert main._GPU.acquire(timeout=1)
    try:
        r = TestClient(main.app).post("/generar", json={"objetivo": "bote", "generar_diagramas": False})
    finally:
        main._GPU.release()
    assert r.status_code == 503 and r.headers["Retry-After"] == "60"
    # y libre otra vez, responde
    assert TestClient(main.app).post("/generar", json={"objetivo": "bote", "generar_diagramas": False}).status_code == 200
