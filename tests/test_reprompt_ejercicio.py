# tests/test_reprompt_ejercicio.py
"""Reprompt: el entrenador corrige un ejercicio ya generado con un texto libre. Solo viaja ese ejercicio (no la
sesión entera), así que el contexto no crece con el número de ejercicios de la sesión (5-8)."""
import json

import pytest

import ejercicio_unico
from test_ejercicio_unico import DIAGRAMA, EJERCICIO_BUENO, _Resp, json_copia  # noqa: F401

ACTUAL = {
    "edad": "U12", "objetivo": "1c1", "nombre": "1 contra 1 desde el codo",
    "descripcion": "A1 recibe pase del entrenador en el codo derecho. D1 defiende en posición básica. "
                   "A1 decide: tiro, salida en bote interior o salida atrás.",
    "instruccion": "quítale el defensor y añade dos botes con la mano izquierda",
}
CORREGIDO = {
    "nombre": "Recibir y decidir en el codo",
    "descripcion": "A1 recibe en el codo derecho, bota dos veces con la izquierda y decide: tiro o salida.",
    "duracion_min": 10, "puntos_clave": ["Dos botes con la izquierda.", "Decidir con la cabeza arriba."],
}


@pytest.fixture
def modelo_falso(monkeypatch):
    estado = {"peticiones": [], "diagramas": []}

    def preparar(respuestas, diagrama=DIAGRAMA):
        respuestas = list(respuestas)

        def post(url, json=None, timeout=None):
            estado["peticiones"].append(json)
            return _Resp(respuestas.pop(0) if len(respuestas) > 1 else respuestas[0])

        def coordenadas(descripcion, nombre):
            estado["diagramas"].append((descripcion, nombre))
            return json_copia(diagrama)

        monkeypatch.setattr(ejercicio_unico.requests, "post", post)
        monkeypatch.setattr(ejercicio_unico, "generar_coordenadas_ejercicio", coordenadas)
        return estado

    return preparar


def _reprompt(**cambios):
    datos = {**ACTUAL, **cambios}
    return ejercicio_unico.reprompt_ejercicio(
        datos["edad"], datos["objetivo"], datos["nombre"], datos["descripcion"], datos["instruccion"])


def test_el_ejercicio_corregido_trae_texto_y_diagrama_nuevo(modelo_falso):
    estado = modelo_falso([CORREGIDO])
    ej = _reprompt()
    assert ej["nombre"] == CORREGIDO["nombre"] and ej["descripcion"] == CORREGIDO["descripcion"]
    assert ej["puntos_clave"] == CORREGIDO["puntos_clave"] and ej["diagrama"] == DIAGRAMA
    assert estado["diagramas"] == [(CORREGIDO["descripcion"], CORREGIDO["nombre"])]   # el diagrama sale del texto corregido


def test_el_prompt_lleva_el_ejercicio_actual_y_la_instruccion(modelo_falso):
    estado = modelo_falso([CORREGIDO])
    _reprompt()
    prompt = estado["peticiones"][0]["prompt"]
    assert ACTUAL["nombre"] in prompt and ACTUAL["descripcion"] in prompt and ACTUAL["instruccion"] in prompt


def test_el_prompt_no_usa_etiquetas_con_mayuscula_que_el_modelo_copiaba_como_claves(modelo_falso):
    # error visto en agosto: «Nombre:» / «Descripción:» acababan como claves del JSON en lugar del esquema real
    estado = modelo_falso([CORREGIDO])
    _reprompt()
    prompt = estado["peticiones"][0]["prompt"]
    assert "Nombre:" not in prompt and "Descripción:" not in prompt


def test_el_texto_se_pide_con_el_esquema_fijo_y_sin_razonamiento(modelo_falso):
    estado = modelo_falso([CORREGIDO])
    _reprompt()
    peticion = estado["peticiones"][0]
    assert peticion["format"] == ejercicio_unico._ESQUEMA_EJERCICIO and peticion["think"] is False


def test_el_contexto_solo_lleva_ese_ejercicio_y_esta_acotado(modelo_falso):
    # un ejercicio de 2000 caracteres (el máximo que admite la API) y una instrucción de 500: el prompt sigue siendo pequeño
    estado = modelo_falso([CORREGIDO])
    _reprompt(descripcion="x" * 2000, instruccion="y" * 500)
    assert len(estado["peticiones"][0]["prompt"]) < 8000


def test_la_instruccion_pedida_no_depende_del_numero_de_ejercicios_de_la_sesion(modelo_falso):
    estado = modelo_falso([CORREGIDO])
    _reprompt()
    corto = len(estado["peticiones"][0]["prompt"])
    _reprompt(nombre="Otro ejercicio")
    assert abs(len(estado["peticiones"][1]["prompt"]) - corto) < 200


def test_si_el_diagrama_no_se_puede_generar_se_devuelve_el_texto_sin_diagrama(modelo_falso):
    modelo_falso([CORREGIDO], diagrama=None)
    ej = _reprompt()
    assert ej["nombre"] and "diagrama" not in ej


def test_si_la_correccion_incumple_una_linea_roja_se_reintenta_avisando(modelo_falso):
    malo = dict(CORREGIDO, descripcion="A1 hace un bloqueo directo y recibe el pase.")
    estado = modelo_falso([malo, CORREGIDO])
    ej = _reprompt(edad="U10")
    assert len(estado["peticiones"]) == 2 and "CORRECCIÓN" in estado["peticiones"][1]["prompt"]
    assert ej["descripcion"] == CORREGIDO["descripcion"]


def test_si_sigue_incumpliendo_no_se_entrega(modelo_falso):
    malo = dict(CORREGIDO, puntos_clave=["Defensa zonal 2-3."])
    estado = modelo_falso([malo])
    assert _reprompt(edad="U10") == {} and len(estado["peticiones"]) == 2


def test_negar_un_contenido_vetado_no_hace_fallar_la_correccion(modelo_falso):
    sin = dict(CORREGIDO, descripcion="Ejercicio individual, sin bloqueos ni pantallas ni defensa zonal.")
    estado = modelo_falso([sin])
    assert _reprompt(edad="U10")["descripcion"] == sin["descripcion"] and len(estado["peticiones"]) == 1


@pytest.mark.parametrize("respuesta", ["no es json", json.dumps({"duración": "5"}), json.dumps({"nombre": "", "descripcion": ""})])
def test_una_respuesta_inservible_devuelve_vacio(modelo_falso, respuesta):
    modelo_falso([respuesta])
    assert _reprompt() == {}


def test_el_prompt_pide_que_el_nombre_refleje_un_cambio_en_el_numero_de_jugadores(modelo_falso):
    # el diagrama fija los jugadores por el nombre (1c1, 2c1...): si el entrenador quita al defensor, el nombre
    # tiene que dejar de decir 1c1 o el diagrama contradiría el texto
    estado = modelo_falso([CORREGIDO])
    _reprompt()
    prompt = estado["peticiones"][0]["prompt"]
    assert "situación numérica" in prompt and "1c0" in prompt


# ── lo que pide expresamente el entrenador se hace, con aviso ────────────────

def test_si_el_entrenador_pide_una_linea_roja_se_hace_con_aviso(modelo_falso):
    pedido = dict(CORREGIDO, descripcion="A1 recibe y hace un bloqueo directo sencillo con A2 antes de tirar.")
    estado = modelo_falso([pedido])
    ej = _reprompt(edad="U12", instruccion="añade un bloqueo directo con un compañero")
    assert ej["descripcion"] == pedido["descripcion"] and len(estado["peticiones"]) == 1     # sin reintento
    assert len(ej["avisos"]) == 1 and "bloqueo" in ej["avisos"][0] and "U12" in ej["avisos"][0]
    prompt = estado["peticiones"][0]["prompt"]
    assert "EXCEPCIÓN" in prompt and "PROHIBIDO" in prompt


def test_lo_demas_sigue_vetado_aunque_el_entrenador_pida_una_linea_roja(modelo_falso):
    mezcla = dict(CORREGIDO, descripcion="Bloqueo directo y además defensa zonal 2-3 todo el rato.")
    estado = modelo_falso([mezcla])
    assert _reprompt(edad="U12", instruccion="añade un bloqueo directo") == {} and len(estado["peticiones"]) == 2


def test_sin_peticion_vetada_no_hay_aviso(modelo_falso):
    modelo_falso([CORREGIDO])
    assert "avisos" not in _reprompt(edad="U12", instruccion="hazlo más dinámico")
