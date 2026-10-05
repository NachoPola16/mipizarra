# tests/test_sesion_ensamblado.py
"""Fase 1.1: generar_sesion compone con el código los ejercicios de la biblioteca (ficha
curada íntegra) y deja al modelo solo calentamiento, vuelta a la calma, fundamentos, las
variantes N.2 sin progresión curada y los huecos sin ficha relevante (propuestos por la IA).
El modelo se simula: no hay Ollama ni red."""
import pytest

import sesion

MARCA_PROPUESTO = "Propuesto por la IA (sin revisar)"

FICHA_A = {
    "id": "t_a", "nombre": "Rueda de bote", "edades": ["U10", "U12", "U16"],
    "objetivos": {"tacticos": ["bote"]},
    "descripcion": "ORGANIZACIÓN: Dos filas en cabecera. SECUENCIA: A bota y finaliza. "
                   "NOTA: no se cuenta el primer bote. PROGRESIÓN: sin defensa → con defensa pasiva.",
    "puntos_clave": ["Cabeza arriba al botar.", "Proteger el balón con el cuerpo."],
}
FICHA_B = {
    "id": "t_b", "nombre": "Zigzag con cambio", "edades": ["U10", "U12", "U16"],
    "objetivos": {"tacticos": ["bote"]},
    "descripcion": "ORGANIZACIÓN: Fila en el fondo. SECUENCIA: zigzag entre conos y cambio de mano.",
    "puntos_clave": ["Cambio de mano lejos del cono."],
}
FICHA_C = {
    "id": "t_c", "nombre": "Bote 1c1 desde el codo", "edades": ["U10", "U12", "U16"],
    "objetivos": {"tacticos": ["bote"]},
    "descripcion": "ORGANIZACIÓN: Un defensor en el codo. PROGRESIÓN: defensor pasivo → defensor activo.",
    "puntos_clave": ["Mirar al aro antes de atacar."],
}
FICHA_SIN_RELACION = {
    "id": "t_x", "nombre": "Circuito de conos", "edades": ["U10", "U12", "U16"],
    "objetivos": {"tacticos": ["agilidad"]},
    "descripcion": "ORGANIZACIÓN: Conos en línea. SECUENCIA: slalom.",
    "puntos_clave": ["Pasos cortos."],
}

RESPUESTA_BASE = """\
**CALENTAMIENTO (15 min)**
Juego: Pañuelo con balón
Reglas: Dos equipos numerados.
Espacio: Media pista.

**VUELTA A LA CALMA (5 min)**
Juego: Estiramientos en círculo
Reglas: Sin balón.

**Fundamentos**: Bote protegido y cabeza arriba."""


class _Resp:
    def __init__(self, texto, done_reason="stop"):
        self._datos = {"response": texto, "done_reason": done_reason}

    def raise_for_status(self):
        pass

    def json(self):
        return self._datos


@pytest.fixture
def sesion_falsa(monkeypatch):
    """Devuelve una función que prepara la selección de fichas y las respuestas del modelo,
    y la lista de peticiones que recibió el 'modelo'."""
    peticiones = []

    def preparar(fichas, respuestas):
        respuestas = list(respuestas)
        monkeypatch.setattr(sesion, "cargar_ejercicios", lambda: [])
        monkeypatch.setattr(sesion, "filtrar_ejercicios", lambda ejs, edad, obj: [])
        monkeypatch.setattr(sesion, "seleccionar_tres_ejercicios", lambda rel: tuple(fichas))
        monkeypatch.setattr(sesion, "construir_contexto_teoria", lambda obj, edad: "")

        def post(url, json, timeout):
            peticiones.append(json)
            r = respuestas.pop(0) if len(respuestas) > 1 else respuestas[0]
            return r if isinstance(r, _Resp) else _Resp(r)

        monkeypatch.setattr(sesion.requests, "post", post)
        return peticiones

    return preparar


# ── ejercicios de la biblioteca: ficha íntegra, compuesta por el código ──────

def test_los_ejercicios_de_biblioteca_salen_con_su_ficha_integra(sesion_falsa):
    sesion_falsa([FICHA_A, FICHA_B, FICHA_C], [RESPUESTA_BASE])
    texto = sesion.generar_sesion("U16", 90, "bote")["texto"]

    assert ("Ejercicio 1: Rueda de bote\nDuración: 20 min\nOrganización:\n"
            "Dos filas en cabecera.\nSECUENCIA: A bota y finaliza.\n"
            "NOTA: no se cuenta el primer bote.\n"
            "PROGRESIÓN: sin defensa → con defensa pasiva.\n"
            "Puntos clave:\n- Cabeza arriba al botar.\n- Proteger el balón con el cuerpo.") in texto
    assert "Ejercicio 2: Zigzag con cambio\nDuración: 20 min" in texto
    assert "- Cambio de mano lejos del cono." in texto
    assert "Ejercicio 3: Bote 1c1 desde el codo\nDuración: 20 min" in texto
    assert MARCA_PROPUESTO not in texto


def test_lo_curado_no_se_corta_por_las_marcas_de_limpieza_del_texto_del_modelo(sesion_falsa):
    # FICHA_A contiene «NOTA:», uno de los patrones con los que se corta el texto del modelo.
    sesion_falsa([FICHA_A, FICHA_B, FICHA_C], [RESPUESTA_BASE])
    texto = sesion.generar_sesion("U16", 90, "bote")["texto"]
    assert "NOTA: no se cuenta el primer bote." in texto
    assert "Ejercicio 3: Bote 1c1 desde el codo" in texto


def test_el_orden_de_la_sesion_es_el_de_siempre(sesion_falsa):
    sesion_falsa([FICHA_A, FICHA_B, FICHA_C], [RESPUESTA_BASE])
    texto = sesion.generar_sesion("U16", 90, "bote")["texto"]
    orden = ["**CALENTAMIENTO (15 min)**", "**PARTE PRINCIPAL**", "Ejercicio 1:", "Ejercicio 2:",
             "**DESCANSO (3 min)**", "Ejercicio 3:", "**VUELTA A LA CALMA (5 min)**", "**Fundamentos**: Bote"]
    posiciones = [texto.index(marca) for marca in orden]
    assert posiciones == sorted(posiciones)


def test_si_el_modelo_escribe_un_bloque_para_una_ficha_se_ignora(sesion_falsa):
    respuesta = RESPUESTA_BASE.replace(
        "**VUELTA A LA CALMA",
        "Ejercicio 1: Rueda de bote\nOrganización: texto inventado por el modelo.\n\n**VUELTA A LA CALMA",
    )
    sesion_falsa([FICHA_A, FICHA_B, FICHA_C], [respuesta])
    texto = sesion.generar_sesion("U16", 90, "bote")["texto"]
    assert "texto inventado por el modelo" not in texto
    assert texto.count("Ejercicio 1:") == 1


def test_el_prompt_lleva_la_ficha_completa_y_no_pide_reescribirla(sesion_falsa):
    peticiones = sesion_falsa([FICHA_A, FICHA_B, FICHA_C], [RESPUESTA_BASE])
    sesion.generar_sesion("U16", 90, "bote")
    prompt = peticiones[0]["prompt"]
    assert "NOTA: no se cuenta el primer bote" in prompt          # descripción completa, no 120 caracteres
    assert "Cabeza arriba al botar." in prompt                     # puntos clave
    assert "Puntos clave:\n-\n-" not in prompt                     # sin plantilla vacía que rellenar


def test_ejercicios_usados_son_solo_los_de_biblioteca(sesion_falsa):
    sesion_falsa([FICHA_A, FICHA_B, FICHA_C], [RESPUESTA_BASE])
    r = sesion.generar_sesion("U16", 90, "bote")
    assert [e["id"] for e in r["ejercicios_usados"]] == ["t_a", "t_b", "t_c"]
    assert r["propuestos"] == []


# ── variante N.2 ─────────────────────────────────────────────────────────────

RESPUESTA_VARIANTE_MODELO = RESPUESTA_BASE.replace(
    "**VUELTA A LA CALMA",
    '''Ejercicio 2.2 (variante de "Zigzag con cambio" — mismo ejercicio con un cambio o regla nueva):
Duración: 99 min
Qué cambia respecto a 2.1: Con límite de dos botes entre conos.
Organización: Igual, con un defensor al final.
Puntos clave:
- Tope de botes.

**VUELTA A LA CALMA''',
)


def test_bloque_partido_la_variante_sale_de_la_progresion_curada_o_del_modelo(sesion_falsa):
    sesion_falsa([FICHA_A, FICHA_B, FICHA_C], [RESPUESTA_VARIANTE_MODELO])
    texto = sesion.generar_sesion("U10", 90, "bote")["texto"]

    assert "Ejercicio 1.1: Rueda de bote\nDuración: 10 min" in texto
    assert 'Ejercicio 1.2 (variante de "Rueda de bote"):\nDuración: 10 min' in texto
    assert "Qué cambia respecto a 1.1: sin defensa → con defensa pasiva." in texto   # curada

    assert "Ejercicio 2.1: Zigzag con cambio\nDuración: 10 min" in texto
    assert 'Ejercicio 2.2 (variante de "Zigzag con cambio"):\nDuración: 10 min' in texto  # duración fijada por el código
    assert "Con límite de dos botes entre conos." in texto                               # del modelo
    assert "99 min" not in texto

    assert "Qué cambia respecto a 3.1: defensor pasivo → defensor activo." in texto      # curada


def test_si_el_modelo_no_da_variante_el_ejercicio_no_se_parte(sesion_falsa):
    sesion_falsa([FICHA_A, FICHA_B, FICHA_C], [RESPUESTA_BASE])
    texto = sesion.generar_sesion("U10", 90, "bote")["texto"]
    assert "Ejercicio 2: Zigzag con cambio\nDuración: 20 min" in texto
    assert "Ejercicio 2.1" not in texto and "Ejercicio 2.2" not in texto


def test_el_prompt_pide_variante_solo_a_las_fichas_sin_progresion(sesion_falsa):
    peticiones = sesion_falsa([FICHA_A, FICHA_B, FICHA_C], [RESPUESTA_VARIANTE_MODELO])
    sesion.generar_sesion("U10", 90, "bote")
    prompt = peticiones[0]["prompt"]
    assert "Ejercicio 2.2" in prompt
    assert "Ejercicio 1.2" not in prompt and "Ejercicio 3.2" not in prompt


# ── umbral de relevancia: huecos propuestos por la IA ────────────────────────

RESPUESTA_PROPUESTO = RESPUESTA_BASE.replace(
    "**VUELTA A LA CALMA",
    '''Ejercicio 1: Cierre y recuperación
Duración: 7 min
Organización: Dos filas; el defensor cierra tras el pase.
Puntos clave:
- Manos activas.

**VUELTA A LA CALMA''',
)


def test_un_hueco_sin_ficha_relevante_lo_propone_la_ia_y_va_marcado(sesion_falsa):
    r_prompt = sesion_falsa([FICHA_SIN_RELACION, FICHA_B, FICHA_C], [RESPUESTA_PROPUESTO])
    r = sesion.generar_sesion("U16", 90, "bote")
    texto = r["texto"]

    assert ("Ejercicio 1: Cierre y recuperación\nDuración: 20 min\n" + MARCA_PROPUESTO +
            "\nOrganización: Dos filas; el defensor cierra tras el pase.") in texto
    assert "Circuito de conos" not in texto                    # la ficha sin relación no se fuerza
    assert texto.count(MARCA_PROPUESTO) == 1                   # solo el propuesto lleva marca
    assert r["propuestos"] == [1]
    assert [e["id"] for e in r["ejercicios_usados"]] == ["t_b", "t_c"]
    assert "Circuito de conos" not in r_prompt[0]["prompt"]


def test_si_ninguna_ficha_es_relevante_los_tres_huecos_son_propuestos(sesion_falsa):
    respuesta = RESPUESTA_BASE.replace("**VUELTA A LA CALMA", "\n".join(
        f"Ejercicio {n}: Propuesta {n}\nDuración: 5 min\nOrganización: algo {n}.\nPuntos clave:\n- clave {n}\n"
        for n in (1, 2, 3)) + "\n**VUELTA A LA CALMA")
    sesion_falsa([FICHA_SIN_RELACION] * 3, [respuesta])
    r = sesion.generar_sesion("U16", 90, "defensa")
    assert r["propuestos"] == [1, 2, 3]
    assert r["texto"].count(MARCA_PROPUESTO) == 3
    assert r["ejercicios_usados"] == []


# ── truncado: se mantiene el reintento por done_reason ───────────────────────

def test_si_el_modelo_se_queda_sin_presupuesto_se_reintenta_con_mas(sesion_falsa):
    peticiones = sesion_falsa([FICHA_A, FICHA_B, FICHA_C],
                              [_Resp("**CALENTAMIENTO (15 min)**\nJuego: Paña", "length"), RESPUESTA_BASE])
    texto = sesion.generar_sesion("U16", 90, "bote")["texto"]
    assert len(peticiones) == 2
    assert peticiones[1]["options"]["num_predict"] > peticiones[0]["options"]["num_predict"]
    assert "**Fundamentos**: Bote protegido" in texto


def test_aunque_se_trunque_la_ficha_curada_no_se_pierde(sesion_falsa):
    sesion_falsa([FICHA_A, FICHA_B, FICHA_C], [_Resp("**CALENTAMIENTO (15 min)**\nJuego: Paña", "length")])
    texto = sesion.generar_sesion("U16", 90, "bote")["texto"]
    for ficha in ("Rueda de bote", "Zigzag con cambio", "Bote 1c1 desde el codo"):
        assert ficha in texto


def test_el_presupuesto_inicial_baja_cuando_el_modelo_escribe_menos(sesion_falsa):
    peticiones = sesion_falsa([FICHA_A, FICHA_B, FICHA_C], [RESPUESTA_BASE])
    sesion.generar_sesion("U16", 90, "bote")
    assert peticiones[0]["options"]["num_predict"] < 3200


# ── guardia de líneas rojas ──────────────────────────────────────────────────

def _con_calentamiento(juego):
    return RESPUESTA_BASE.replace("Pañuelo con balón", juego)


def test_si_el_modelo_incumple_una_linea_roja_se_reintenta_avisando(sesion_falsa):
    peticiones = sesion_falsa(
        [FICHA_A, FICHA_B, FICHA_C],
        [_con_calentamiento("Bloqueo directo con el pívot"), _con_calentamiento("Pañuelo con balón")],
    )
    r = sesion.generar_sesion("U12", 90, "bote")
    assert len(peticiones) == 2
    assert "CORRECCIÓN" not in peticiones[0]["prompt"]
    assert "CORRECCIÓN" in peticiones[1]["prompt"] and "bloqueo" in peticiones[1]["prompt"].split("CORRECCIÓN")[1].lower()
    assert "bloqueo" not in r["texto"].lower()
    assert "Pañuelo con balón" in r["texto"]
    assert r["avisos"] == []


def test_si_sigue_incumpliendo_tras_el_reintento_se_quita_esa_pieza(sesion_falsa):
    peticiones = sesion_falsa([FICHA_A, FICHA_B, FICHA_C], [_con_calentamiento("Bloqueo directo con el pívot")])
    r = sesion.generar_sesion("U12", 90, "bote")
    assert len(peticiones) == 2                                   # un único reintento
    assert "bloqueo" not in r["texto"].lower()
    assert "**CALENTAMIENTO" not in r["texto"]
    assert "**VUELTA A LA CALMA (5 min)**" in r["texto"]          # lo demás se conserva
    assert "Bote 1c1 desde el codo" in r["texto"]
    assert any("calentamiento" in a.lower() for a in r["avisos"])


def test_la_guardia_tambien_vigila_a_los_ejercicios_propuestos(sesion_falsa):
    malo = RESPUESTA_PROPUESTO.replace("Dos filas; el defensor cierra", "Pick and roll; el defensor cierra")
    sesion_falsa([FICHA_SIN_RELACION, FICHA_B, FICHA_C], [malo])
    r = sesion.generar_sesion("U12", 90, "bote")
    assert "pick and roll" not in r["texto"].lower()
    assert MARCA_PROPUESTO not in r["texto"]
    assert any("Ejercicio 1" in a for a in r["avisos"])


def test_las_fichas_curadas_no_pasan_por_la_guardia(sesion_falsa):
    # una ficha del entrenador con «pantalla» en U12 no se toca, ni genera avisos ni reintentos
    ficha = dict(FICHA_B, descripcion="ORGANIZACIÓN: Pantalla indirecta para el tirador.")
    peticiones = sesion_falsa([FICHA_A, ficha, FICHA_C], [RESPUESTA_BASE])
    r = sesion.generar_sesion("U12", 90, "bote")
    assert len(peticiones) == 1 and "Pantalla indirecta" in r["texto"] and r["avisos"] == []


# ── robustez ante la numeración que escriba el modelo ────────────────────────

def test_hueco_propuesto_partido_acepta_cabecera_sin_sufijo(sesion_falsa):
    # U10 a 90 min parte los ejercicios; el modelo escribe «Ejercicio 1:» en vez de «1.1»
    sesion_falsa([FICHA_SIN_RELACION, FICHA_B, FICHA_C], [RESPUESTA_PROPUESTO])
    r = sesion.generar_sesion("U10", 90, "bote")
    assert "Ejercicio 1: Cierre y recuperación\nDuración: 20 min\n" + MARCA_PROPUESTO in r["texto"]
    assert r["propuestos"] == [1]


def test_hueco_propuesto_no_partido_acepta_cabecera_con_sufijo(sesion_falsa):
    respuesta = RESPUESTA_PROPUESTO.replace("Ejercicio 1: Cierre", "Ejercicio 1.1: Cierre")
    sesion_falsa([FICHA_SIN_RELACION, FICHA_B, FICHA_C], [respuesta])
    r = sesion.generar_sesion("U16", 90, "bote")
    assert "Ejercicio 1: Cierre y recuperación\nDuración: 20 min" in r["texto"]


def test_si_el_modelo_no_escribe_un_hueco_propuesto_se_avisa(sesion_falsa):
    sesion_falsa([FICHA_SIN_RELACION, FICHA_B, FICHA_C], [RESPUESTA_BASE])
    r = sesion.generar_sesion("U16", 90, "bote")
    assert r["propuestos"] == []
    assert any("Ejercicio 1" in a for a in r["avisos"])
