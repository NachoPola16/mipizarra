# tests/test_validacion_diagrama.py
"""Validador semántico de diagramas (_validar_diagrama) y conteo NcM del nombre."""
import copy

import pytest

from rag_engine import _extraer_conteo_nc_m, _validar_diagrama


# ── _extraer_conteo_nc_m ─────────────────────────────────────────────────────

@pytest.mark.parametrize("nombre, esperado", [
    ("1c1 desde el codo", (1, 1)),
    ("2c1 en transición", (2, 1)),
    ("3C2 con ayuda", (3, 2)),
    ("2 contra 1 desde saque de banda", (2, 1)),
    ("3 contra 3 — inversión de lado", (3, 3)),
    ("Tiro tras 3c0", (3, 0)),
    ("Juego de 5contra4", (5, 4)),
    ("Carrera + finalización 1 c 1", (1, 1)),
])
def test_conteo_nc_m_reconoce_formatos(nombre, esperado):
    assert _extraer_conteo_nc_m(nombre) == esperado


@pytest.mark.parametrize("nombre", [
    "",
    "Tiro tras bote",
    "Bloqueo directo central",
    "Rueda de pases en 3 filas",
    "Contraataque",
])
def test_conteo_nc_m_sin_patron_devuelve_none(nombre):
    assert _extraer_conteo_nc_m(nombre) is None


# ── _validar_diagrama ────────────────────────────────────────────────────────

DIAGRAMA_2C1 = {
    "tipo": "media_pista",
    "jugadores_ataque": [
        {"id": "A1", "x": 50, "y": 65},
        {"id": "A2", "x": 25, "y": 50},
    ],
    "jugadores_defensa": [
        {"id": "D1", "x": 50, "y": 45},
    ],
    "balon_inicio": {"portador": "A1"},
    "movimientos": [
        {"de": "A1", "tipo": "bote", "a_pos": {"x": 50, "y": 45}, "orden": 1},
        {"de": "A1", "tipo": "pase", "a": "A2", "orden": 2},
        {"de": "A2", "tipo": "desplazamiento", "a_pos": {"x": 20, "y": 30}, "orden": 3},
        {"de": "A2", "tipo": "tiro", "orden": 4},
    ],
    "conos": [],
}


def _diagrama():
    return copy.deepcopy(DIAGRAMA_2C1)


def test_diagrama_valido():
    assert _validar_diagrama(_diagrama(), "2c1 en media pista") is None


def test_diagrama_valido_sin_nombre_nc_m():
    # Sin patrón NcM en el nombre no se comprueba el conteo.
    assert _validar_diagrama(_diagrama(), "Pase y finalización") is None


def test_bloqueo_con_a_pos_es_valido():
    d = _diagrama()
    d["movimientos"].append({"de": "A2", "tipo": "bloqueo", "a_pos": {"x": 45, "y": 45}, "orden": 5})
    assert _validar_diagrama(d, "") is None


def test_sin_atacantes_es_invalido():
    d = _diagrama()
    d["jugadores_ataque"] = []
    assert "vacío" in _validar_diagrama(d, "")


def test_ids_repetidos_es_invalido():
    d = _diagrama()
    d["jugadores_defensa"][0]["id"] = "A2"
    assert "repetidos" in _validar_diagrama(d, "")


def test_movimiento_de_jugador_no_declarado():
    d = _diagrama()
    d["movimientos"].append({"de": "A5", "tipo": "tiro", "orden": 5})
    error = _validar_diagrama(d, "")
    assert error and "A5" in error


def test_pase_a_jugador_no_declarado():
    d = _diagrama()
    d["movimientos"][1]["a"] = "A3"
    error = _validar_diagrama(d, "")
    assert error and "pase" in error and "A3" in error


def test_portador_no_declarado():
    d = _diagrama()
    d["balon_inicio"]["portador"] = "A4"
    error = _validar_diagrama(d, "")
    assert error and "portador" in error


@pytest.mark.parametrize("tipo", ["desplazamiento", "bote", "bloqueo"])
def test_movimiento_sin_a_pos(tipo):
    d = _diagrama()
    d["movimientos"].append({"de": "A2", "tipo": tipo, "orden": 5})
    error = _validar_diagrama(d, "")
    assert error == f"movimiento '{tipo}' sin 'a_pos'"


def test_tipo_de_movimiento_desconocido():
    d = _diagrama()
    d["movimientos"].append({"de": "A2", "tipo": "pantalla", "orden": 5})
    assert "desconocido" in _validar_diagrama(d, "")


@pytest.mark.parametrize("nombre", ["1c1 en el ala", "3c2 con ayuda", "2 contra 2 sin bote", "2c0"])
def test_conteo_no_coincide_con_nombre(nombre):
    error = _validar_diagrama(_diagrama(), nombre)
    assert error and "atacante" in error and "defensor" in error


def test_defensores_de_mas_para_el_nombre():
    d = _diagrama()
    d["jugadores_defensa"].append({"id": "D2", "x": 25, "y": 35})
    assert _validar_diagrama(d, "2c1 en media pista") is not None
    assert _validar_diagrama(d, "2c2 en media pista") is None


def test_jugadores_demasiado_cerca():
    d = _diagrama()
    # A1 en (50, 65): D1 a ~5 unidades → por debajo del mínimo de 8.
    d["jugadores_defensa"][0].update({"x": 53, "y": 61})
    error = _validar_diagrama(d, "")
    assert error and "demasiado cerca" in error


def test_atacantes_demasiado_cerca_entre_si():
    d = _diagrama()
    d["jugadores_ataque"][1].update({"x": 47, "y": 60})
    assert "demasiado cerca" in _validar_diagrama(d, "")


def test_distancia_exactamente_en_el_minimo_es_valida():
    d = _diagrama()
    # D1 a exactamente 8 unidades de A1 (y 65 → 57) y lejos de A2.
    d["jugadores_defensa"][0].update({"x": 50, "y": 57})
    assert _validar_diagrama(d, "") is None
