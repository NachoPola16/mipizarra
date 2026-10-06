# tests/test_prompt_diagrama.py
"""El generador de diagramas le dice al modelo cuántos jugadores exactos debe dibujar cuando el nombre del
ejercicio lo indica (1c1, 2c1, 3c0...). Con el recuento solo como una regla más entre once, el modelo lo
ignoraba y dibujaba «1 atacante y 0 defensores» para un 1c1."""
import json

import pytest

import diagramas

DIAGRAMA_OK = {"tipo": "media_pista", "jugadores_ataque": [{"id": "A1", "x": 50, "y": 60}],
               "jugadores_defensa": [{"id": "D1", "x": 50, "y": 45}], "balon_inicio": {"portador": "A1"},
               "movimientos": [{"de": "A1", "tipo": "tiro", "orden": 1}], "conos": []}


class _Resp:
    def raise_for_status(self):
        pass

    def json(self):
        return {"response": json.dumps(DIAGRAMA_OK)}


@pytest.fixture
def prompts(monkeypatch):
    enviados = []
    monkeypatch.setattr(diagramas.requests, "post",
                        lambda url, json=None, timeout=None: (enviados.append(json["prompt"]), _Resp())[1])
    return enviados


@pytest.mark.parametrize("nombre,atacantes,defensores", [
    ("1c1 desde el 45°", 1, 1), ("2c1 en media pista", 2, 1), ("3c0 pase y corte", 3, 0), ("3 contra 2 por carriles", 3, 2),
])
def test_el_prompt_fija_el_numero_exacto_de_jugadores_que_indica_el_nombre(prompts, nombre, atacantes, defensores):
    diagramas.generar_coordenadas_ejercicio("Descripción del ejercicio.", nombre)
    prompt = prompts[0]
    assert f"jugadores_ataque debe tener EXACTAMENTE {atacantes}" in prompt
    assert f"jugadores_defensa debe tener EXACTAMENTE {defensores}" in prompt


def test_el_recuento_va_antes_de_las_reglas_generales(prompts):
    diagramas.generar_coordenadas_ejercicio("Descripción.", "1c1 desde el codo")
    prompt = prompts[0]
    assert prompt.index("EXACTAMENTE 1") < prompt.index("SISTEMA DE COORDENADAS")


def test_sin_situacion_numerica_en_el_nombre_no_se_inventa_el_recuento(prompts):
    diagramas.generar_coordenadas_ejercicio("Circuito de bote entre conos.", "Circuito de bote en zigzag")
    assert "EXACTAMENTE" not in prompts[0]
