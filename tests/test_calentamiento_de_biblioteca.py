# tests/test_calentamiento_de_biblioteca.py
"""El calentamiento sale de una ficha curada de la biblioteca cuando hay una para la edad; el 4B ya no lo
inventa (escribía juegos poco adecuados y repetía material). Sin ficha, lo redacta el modelo como antes."""
import random

import pytest

import sesion
from plan_sesion import PlanDeTiempos
from bloques import bloque_calentamiento
from ejercicios import elegir_calentamiento
from test_sesion_ensamblado import FICHA_A, FICHA_B, FICHA_C, RESPUESTA_BASE, _Resp  # noqa: F401
from test_sesion_ensamblado import sesion_falsa  # noqa: F401  (fixture)

CAL_1 = {
    "id": "c_1", "nombre": "Lluvia de papeles", "categoria": "calentamiento", "edades": ["U8", "U10", "U12"],
    "objetivos": {"tacticos": [], "tecnicos": ["bote con la cabeza alta"]},
    "descripcion": "ORGANIZACIÓN: todos con balón en media pista. SECUENCIA: botan y recogen bolas de papel.",
    "puntos_clave": ["No parar el bote al agacharse."], "material": "Un balón por jugador y bolas de papel.",
    "sin_diagrama": True,
}
CAL_2 = {
    "id": "c_2", "nombre": "Pilla con balón", "categoria": "calentamiento", "edades": ["U8", "U10"],
    "objetivos": {"tacticos": [], "tecnicos": ["control"]},
    "descripcion": "ORGANIZACIÓN: un pillador. SECUENCIA: todos botan huyendo.",
    "puntos_clave": ["Cabeza arriba."],
}
CAL_3 = {**CAL_2, "id": "c_3", "nombre": "Globos en equipo"}
CAL_4 = {**CAL_2, "id": "c_4", "nombre": "Dos pelotas"}
NO_CAL = {"id": "p_1", "nombre": "Bote en zigzag", "categoria": "1c1", "edades": ["U8"],
          "objetivos": {"tacticos": ["bote"]}, "descripcion": "x", "puntos_clave": []}
BIBLIOTECA = [NO_CAL, CAL_1, CAL_2, CAL_3, CAL_4]


# ── elegir_calentamiento ─────────────────────────────────────────────────────

def test_solo_se_eligen_fichas_de_calentamiento_de_la_edad():
    assert elegir_calentamiento(BIBLIOTECA, "U12", "bote")["id"] == "c_1"
    assert elegir_calentamiento(BIBLIOTECA, "U16", "bote") is None
    assert elegir_calentamiento([NO_CAL], "U8", "bote") is None


def test_no_se_repite_una_ficha_ya_usada_en_la_parte_principal():
    assert elegir_calentamiento(BIBLIOTECA, "U12", "bote", excluir={"c_1"}) is None
    assert elegir_calentamiento(BIBLIOTECA, "U10", "bote", excluir={"c_1"})["id"] in {"c_2", "c_3", "c_4"}


def test_prefiere_las_que_encajan_con_el_objetivo():
    assert elegir_calentamiento([CAL_2, CAL_1], "U8", "papel")["id"] == "c_1"    # solo c_1 nombra el papel


def test_sin_azar_es_determinista_y_con_azar_hay_variedad_entre_las_primeras():
    assert elegir_calentamiento(BIBLIOTECA, "U8", "tiro")["id"] == "c_1"
    vistas = {elegir_calentamiento(BIBLIOTECA, "U8", "tiro", azar=random.Random(s))["id"] for s in range(40)}
    assert len(vistas) > 1
    assert "c_4" in vistas       # compiten todas las candidatas


# ── bloque_calentamiento ─────────────────────────────────────────────────────

def test_el_bloque_conserva_el_formato_juego_reglas_para_el_frontend_y_el_diagrama():
    bloque = bloque_calentamiento(CAL_1)
    assert bloque.startswith("Juego: Lluvia de papeles\nReglas:\n")
    assert "SECUENCIA: botan y recogen bolas de papel." in bloque
    assert "Puntos clave:\n- No parar el bote al agacharse." in bloque


# ── generar_sesion ───────────────────────────────────────────────────────────

def test_con_ficha_el_calentamiento_sale_literal_y_el_modelo_no_lo_escribe(sesion_falsa, monkeypatch):
    peticiones = sesion_falsa([FICHA_A, FICHA_B, FICHA_C], [RESPUESTA_BASE])
    monkeypatch.setattr(sesion, "cargar_ejercicios", lambda: [CAL_1])
    r = sesion.generar_sesion("U10", 90, "bote")
    assert "**CALENTAMIENTO (15 min)**\nJuego: Lluvia de papeles\nReglas:" in r["texto"]
    assert "Pañuelo con balón" not in r["texto"]                      # lo que escribió el modelo se descarta
    assert r["calentamiento_ficha"]["id"] == "c_1"
    assert "Lluvia de papeles" not in peticiones[0]["prompt"]          # ni se le pide ni se le enseña
    assert "**CALENTAMIENTO" not in peticiones[0]["prompt"]


def test_sin_ficha_para_la_edad_el_calentamiento_lo_escribe_el_modelo(sesion_falsa, monkeypatch):
    sesion_falsa([FICHA_A, FICHA_B, FICHA_C], [RESPUESTA_BASE])
    monkeypatch.setattr(sesion, "cargar_ejercicios", lambda: [CAL_1])
    r = sesion.generar_sesion("U16", 90, "bote")
    assert "Juego: Pañuelo con balón" in r["texto"]
    assert r["calentamiento_ficha"] is None


def test_la_ficha_de_calentamiento_no_repite_una_de_la_parte_principal(sesion_falsa, monkeypatch):
    sesion_falsa([FICHA_A, FICHA_B, FICHA_C], [RESPUESTA_BASE])
    de_calentamiento = {**FICHA_A, "categoria": "calentamiento", "edades": ["U10"]}
    monkeypatch.setattr(sesion, "cargar_ejercicios", lambda: [de_calentamiento])
    r = sesion.generar_sesion("U10", 90, "bote")
    assert r["calentamiento_ficha"] is None


def test_con_ficha_y_todo_curado_solo_se_pide_al_modelo_lo_que_falta(sesion_falsa, monkeypatch):
    peticiones = sesion_falsa([FICHA_A, FICHA_B, FICHA_C], [" el bote y la protección del balón."])   # continúa el arranque
    monkeypatch.setattr(sesion, "cargar_ejercicios", lambda: [CAL_1])
    monkeypatch.setattr(sesion, "plan_de_tiempos", lambda d, e: PlanDeTiempos(15, 0, 3, (20, 20, 20)))  # sin vuelta
    r = sesion.generar_sesion("U10", 90, "bote")
    assert "Fundamentos**: " in r["texto"]
    assert r["texto"].index("Juego: Lluvia de papeles") < r["texto"].index("**PARTE PRINCIPAL**")
    assert len(peticiones) == 1


# ── los calentamientos no desplazan a las fichas de la parte principal ───────────────────────────────

@pytest.mark.parametrize("edad,objetivo", [("U14", "tiro"), ("U16", "tiro"), ("U16", "rebote"),
                                           ("U18", "contraataque"), ("Senior", "pase")])
def test_en_la_biblioteca_real_la_parte_principal_no_se_llena_de_calentamientos(ejercicios, edad, objetivo):
    from ejercicios import elegir_fichas
    fichas = elegir_fichas([dict(e) for e in ejercicios], edad, objetivo, 5)
    assert not [f["id"] for f in fichas if f and f["categoria"] == "calentamiento"]


def test_el_bote_de_minibasket_sigue_pudiendo_usar_fichas_de_bote_aunque_sean_calentamiento(ejercicios):
    from ejercicios import elegir_fichas
    fichas = elegir_fichas([dict(e) for e in ejercicios], "U8", "bote", 5)
    assert any(f and f["categoria"] == "calentamiento" for f in fichas)


def test_un_calentamiento_sin_id_no_rompe_la_exclusion():
    sin_id = {k: v for k, v in CAL_1.items() if k != "id"}
    assert elegir_calentamiento([sin_id], "U10", "bote", excluir={None}) is sin_id
