# tests/test_ejercicio_unico.py
"""Modo 2: un ejercicio suelto. El texto se genera con un esquema que fuerza los campos (el modelo, sin esquema,
inventaba claves como «duración» u «organización») y el diagrama lo genera el generador de diagramas validado."""
import json

import pytest

import ejercicio_unico

DIAGRAMA = {"tipo": "media_pista", "jugadores_ataque": [{"id": "A1", "x": 50, "y": 60}],
            "jugadores_defensa": [{"id": "D1", "x": 50, "y": 45}], "balon_inicio": {"portador": "A1"},
            "movimientos": [{"de": "A1", "tipo": "tiro", "orden": 1}], "conos": []}

EJERCICIO_BUENO = {
    "nombre": "1c1 desde el 45°",
    "descripcion": "Dos filas, una en cada 45°. El atacante recibe, mira al aro y ataca al defensor. "
                   "Rotación: el atacante pasa a defender y el defensor a la fila contraria.",
    "duracion_min": 10,
    "puntos_clave": ["Mirar al aro al recibir.", "Salida cruzada con el pie contrario."],
}


class _Resp:
    def __init__(self, ejercicio):
        self._ejercicio = ejercicio

    def raise_for_status(self):
        pass

    def json(self):
        texto = self._ejercicio if isinstance(self._ejercicio, str) else json.dumps(self._ejercicio, ensure_ascii=False)
        return {"response": texto, "done_reason": "stop"}


@pytest.fixture
def modelo_falso(monkeypatch):
    """Respuestas del modelo en orden (la última se repite); registra peticiones y llamadas al generador de diagramas."""
    estado = {"peticiones": [], "diagramas": []}

    def preparar(respuestas, diagrama=DIAGRAMA):
        respuestas = list(respuestas)

        def post(url, json=None, timeout=None):
            estado["peticiones"].append(json)
            r = respuestas.pop(0) if len(respuestas) > 1 else respuestas[0]
            return _Resp(r)

        def coordenadas(descripcion, nombre):
            estado["diagramas"].append((descripcion, nombre))
            return json_copia(diagrama)

        monkeypatch.setattr(ejercicio_unico.requests, "post", post)
        monkeypatch.setattr(ejercicio_unico, "generar_coordenadas_ejercicio", coordenadas)
        return estado

    return preparar


def json_copia(d):
    return None if d is None else json.loads(json.dumps(d))


def test_el_ejercicio_trae_texto_y_diagrama(modelo_falso):
    modelo_falso([EJERCICIO_BUENO])
    ej = ejercicio_unico.generar_ejercicio_unico("U12", "1c1")
    assert ej["nombre"] == "1c1 desde el 45°" and ej["descripcion"].startswith("Dos filas")
    assert ej["puntos_clave"] == EJERCICIO_BUENO["puntos_clave"] and ej["duracion_min"] == 10
    assert ej["diagrama"] == DIAGRAMA


def test_el_diagrama_se_pide_con_la_descripcion_y_el_nombre_del_ejercicio(modelo_falso):
    estado = modelo_falso([EJERCICIO_BUENO])
    ejercicio_unico.generar_ejercicio_unico("U12", "1c1")
    assert estado["diagramas"] == [(EJERCICIO_BUENO["descripcion"], EJERCICIO_BUENO["nombre"])]


def test_el_texto_se_pide_con_un_esquema_que_fuerza_los_campos_y_sin_razonamiento(modelo_falso):
    estado = modelo_falso([EJERCICIO_BUENO])
    ejercicio_unico.generar_ejercicio_unico("U12", "1c1")
    peticion = estado["peticiones"][0]
    esquema = peticion["format"]
    assert isinstance(esquema, dict) and esquema["type"] == "object"
    assert {"nombre", "descripcion", "puntos_clave"} <= set(esquema["required"])
    assert esquema["properties"]["puntos_clave"]["type"] == "array"
    assert peticion["think"] is False


def test_el_prompt_lleva_la_edad_el_objetivo_la_descripcion_pedida_y_los_ejercicios_de_referencia(modelo_falso):
    estado = modelo_falso([EJERCICIO_BUENO])
    ejercicio_unico.generar_ejercicio_unico("U12", "1c1", "con salida cruzada")
    prompt = estado["peticiones"][0]["prompt"]
    assert "U12" in prompt and "1c1" in prompt and "con salida cruzada" in prompt
    assert "Ejercicios de referencia" in prompt


def test_el_prompt_prohibe_lo_que_no_se_trabaja_en_esa_edad(modelo_falso):
    estado = modelo_falso([EJERCICIO_BUENO])
    ejercicio_unico.generar_ejercicio_unico("U10", "bote")
    assert "PROHIBIDO" in estado["peticiones"][0]["prompt"]


def test_si_el_diagrama_no_se_puede_generar_se_devuelve_el_ejercicio_sin_diagrama(modelo_falso):
    modelo_falso([EJERCICIO_BUENO], diagrama=None)
    ej = ejercicio_unico.generar_ejercicio_unico("U12", "1c1")
    assert ej["nombre"] and "diagrama" not in ej


def test_si_el_modelo_incumple_una_linea_roja_se_reintenta_avisando(modelo_falso):
    malo = dict(EJERCICIO_BUENO, descripcion="Hacen un bloqueo directo con el pívot y finalizan.")
    estado = modelo_falso([malo, EJERCICIO_BUENO])
    ej = ejercicio_unico.generar_ejercicio_unico("U10", "bote")
    assert len(estado["peticiones"]) == 2
    assert "CORRECCIÓN" not in estado["peticiones"][0]["prompt"]
    segundo = estado["peticiones"][1]["prompt"]
    assert "CORRECCIÓN" in segundo and "bloqueo" in segundo.split("CORRECCIÓN")[1].lower()
    assert ej["descripcion"] == EJERCICIO_BUENO["descripcion"]


def test_si_sigue_incumpliendo_tras_el_reintento_no_se_entrega(modelo_falso):
    malo = dict(EJERCICIO_BUENO, puntos_clave=["Defensa zonal 2-3 en media pista."])
    estado = modelo_falso([malo])
    assert ejercicio_unico.generar_ejercicio_unico("U10", "bote") == {}
    assert len(estado["peticiones"]) == 2                    # un único reintento


def test_en_u14_el_bloqueo_directo_no_es_linea_roja(modelo_falso):
    puntual = dict(EJERCICIO_BUENO, descripcion="Bloqueo directo sencillo con el base, de forma puntual.")
    estado = modelo_falso([puntual])
    assert ejercicio_unico.generar_ejercicio_unico("U14", "bloqueo")["descripcion"] == puntual["descripcion"]
    assert len(estado["peticiones"]) == 1


@pytest.mark.parametrize("respuesta", ["esto no es json", "{", json.dumps({"nombre": "", "descripcion": ""}),
                                       json.dumps({"duración": "10 min", "organización": "algo"})])
def test_una_respuesta_sin_nombre_y_descripcion_validos_no_es_un_ejercicio(modelo_falso, respuesta):
    modelo_falso([respuesta])
    assert ejercicio_unico.generar_ejercicio_unico("U12", "1c1") == {}


def test_los_puntos_clave_se_limpian_y_la_duracion_se_normaliza(modelo_falso):
    modelo_falso([dict(EJERCICIO_BUENO, puntos_clave=["  Mirar al aro.  ", "", "Salida cruzada."], duracion_min="12")])
    ej = ejercicio_unico.generar_ejercicio_unico("U12", "1c1")
    assert ej["puntos_clave"] == ["Mirar al aro.", "Salida cruzada."] and ej["duracion_min"] == 12


def test_los_ejercicios_de_la_biblioteca_se_ofrecen_como_referencia_solo_de_esa_edad(modelo_falso):
    estado = modelo_falso([EJERCICIO_BUENO])
    ejercicio_unico.generar_ejercicio_unico("U8", "bote")
    prompt = estado["peticiones"][0]["prompt"]
    assert "poste bajo" not in prompt.lower()
