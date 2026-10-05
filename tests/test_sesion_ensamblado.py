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

VARIANTE_ZIGZAG = (
    'Ejercicio 2.2 (variante de "Zigzag con cambio"):\nDuración: 10 min\n'
    "Qué cambia respecto a 2.1: Se añade un defensor pasivo.\nOrganización: Igual que en 2.1.\n\n"
)


def _con_variante(respuesta):
    """En U12 a 90 min los ejercicios se parten: una respuesta completa incluye la variante
    de «Zigzag con cambio», que no trae progresión curada."""
    return respuesta.replace("**VUELTA A LA CALMA", VARIANTE_ZIGZAG + "**VUELTA A LA CALMA", 1)


def _con_calentamiento(juego):
    return _con_variante(RESPUESTA_BASE.replace("Pañuelo con balón", juego))


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
    peticiones = sesion_falsa([FICHA_A, ficha, FICHA_C], [_con_variante(RESPUESTA_BASE)])
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


# ── el prompt termina empezando la respuesta (el modelo sigue la plantilla en orden) ──────────

INICIO = "**CALENTAMIENTO (15 min)**\nJuego:"
CONTINUACION = (" Pañuelo con balón\nReglas: Dos equipos.\nEspacio: Media pista.\n\n"
                "**VUELTA A LA CALMA (5 min)**\nJuego: Estiramientos\nReglas: Sin balón.\n\n"
                "**Fundamentos**: Bote protegido.")


def test_el_prompt_termina_con_el_inicio_de_la_respuesta(sesion_falsa):
    peticiones = sesion_falsa([FICHA_A, FICHA_B, FICHA_C], [CONTINUACION])
    sesion.generar_sesion("U16", 90, "bote")
    assert peticiones[0]["prompt"].endswith(INICIO)


def test_si_el_modelo_continua_desde_el_inicio_se_antepone_el_inicio(sesion_falsa):
    sesion_falsa([FICHA_A, FICHA_B, FICHA_C], [CONTINUACION])
    r = sesion.generar_sesion("U16", 90, "bote")
    assert "**CALENTAMIENTO (15 min)**\nJuego: Pañuelo con balón" in r["texto"]
    assert r["texto"].count("**CALENTAMIENTO") == 1


def test_si_el_modelo_repite_la_cabecera_no_se_duplica(sesion_falsa):
    sesion_falsa([FICHA_A, FICHA_B, FICHA_C], [RESPUESTA_BASE])
    r = sesion.generar_sesion("U16", 90, "bote")
    assert r["texto"].count("**CALENTAMIENTO") == 1
    assert r["texto"].count("Juego: Pañuelo con balón") == 1


def test_la_plantilla_del_hueco_propuesto_pide_el_nombre(sesion_falsa):
    peticiones = sesion_falsa([FICHA_SIN_RELACION, FICHA_B, FICHA_C], [CONTINUACION])
    sesion.generar_sesion("U16", 90, "bote")
    assert "Ejercicio 1: (nombre propio del ejercicio)" in peticiones[0]["prompt"]


# ── generación por pasos: si el modelo se detiene, se le piden los apartados que faltan ──────

CALENTAMIENTO_SOLO = " Pañuelo con balón\nReglas: Dos equipos.\nEspacio: Media pista."


def test_si_el_modelo_se_para_tras_el_calentamiento_se_piden_los_apartados_que_faltan(sesion_falsa):
    peticiones = sesion_falsa(
        [FICHA_A, FICHA_B, FICHA_C],
        [CALENTAMIENTO_SOLO, " Estiramientos\nReglas: Sin balón.", " Bote protegido."],
    )
    r = sesion.generar_sesion("U16", 90, "bote")
    assert len(peticiones) == 3
    assert peticiones[1]["prompt"].endswith("**VUELTA A LA CALMA (5 min)**\nJuego:")
    assert "Juego: Pañuelo con balón" in peticiones[1]["prompt"]      # ve lo ya escrito
    assert peticiones[2]["prompt"].endswith("**Fundamentos**: En esta sesión se trabajan")
    assert "**VUELTA A LA CALMA (5 min)**\nJuego: Estiramientos" in r["texto"]
    assert r["texto"].rstrip().endswith("**Fundamentos**: En esta sesión se trabajan Bote protegido.")
    assert r["avisos"] == []


def test_los_pasos_se_piden_en_el_orden_de_la_sesion_incluida_la_variante(sesion_falsa):
    # U12 a 90 min parte los ejercicios; Zigzag no trae progresión curada → la variante la escribe el modelo
    peticiones = sesion_falsa(
        [FICHA_A, FICHA_B, FICHA_C],
        [CALENTAMIENTO_SOLO, " Cambia el cono por un defensor pasivo.\nOrganización: Igual.",
         " Estiramientos\nReglas: Sin balón.", " Bote protegido."],
    )
    r = sesion.generar_sesion("U12", 90, "bote")
    assert len(peticiones) == 4
    assert peticiones[1]["prompt"].endswith(
        'Ejercicio 2.2 (variante de "Zigzag con cambio"):\nDuración: 10 min\nQué cambia respecto a 2.1:')
    assert peticiones[2]["prompt"].endswith("**VUELTA A LA CALMA (5 min)**\nJuego:")
    assert "Qué cambia respecto a 2.1: Cambia el cono por un defensor pasivo." in r["texto"]


def test_un_apartado_que_el_modelo_no_da_se_pide_una_sola_vez(sesion_falsa):
    peticiones = sesion_falsa([FICHA_A, FICHA_B, FICHA_C], [CALENTAMIENTO_SOLO, "", ""])
    r = sesion.generar_sesion("U16", 90, "bote")
    assert len(peticiones) == 3                      # calentamiento + vuelta + fundamentos, sin bucles
    assert "**CALENTAMIENTO (15 min)**" in r["texto"]


def test_los_pasos_de_relleno_cortan_en_la_siguiente_cabecera(sesion_falsa):
    peticiones = sesion_falsa([FICHA_A, FICHA_B, FICHA_C], [CALENTAMIENTO_SOLO, " Algo", " Algo"])
    sesion.generar_sesion("U16", 90, "bote")
    assert "\n**" in peticiones[1]["options"]["stop"]
    assert "\n**" in peticiones[1]["options"]["stop"] and "\nEjercicio " in peticiones[1]["options"]["stop"]


def test_si_en_un_paso_el_modelo_repite_la_cabecera_no_se_duplica(sesion_falsa):
    sesion_falsa(
        [FICHA_A, FICHA_B, FICHA_C],
        [CALENTAMIENTO_SOLO, '**VUELTA A LA CALMA (5 min)**\nJuego: Estiramientos\nReglas: Sin balón.',
         "**Fundamentos**: Bote protegido."],
    )
    texto = sesion.generar_sesion("U16", 90, "bote")["texto"]
    assert texto.count("**VUELTA A LA CALMA") == 1
    assert "Juego: Estiramientos" in texto
    assert "Juego:\n**VUELTA" not in texto and "Juego:**VUELTA" not in texto
    assert texto.count("**Fundamentos**") == 1


def test_si_en_un_paso_el_modelo_abre_otra_seccion_se_descarta_ese_paso(sesion_falsa):
    sesion_falsa(
        [FICHA_A, FICHA_B, FICHA_C],
        [CALENTAMIENTO_SOLO, " Estiramientos\nReglas: Sin balón.", "**CALENTAMIENTO (10 min)**\nJuego: otro"],
    )
    r = sesion.generar_sesion("U16", 90, "bote")
    assert r["texto"].count("**CALENTAMIENTO") == 1
    assert "**Fundamentos**" not in r["texto"]            # sin texto de fundamentos no se deja la etiqueta vacía


def test_los_fundamentos_se_cortan_si_el_modelo_abre_otra_seccion_en_la_misma_linea(sesion_falsa):
    peticiones = sesion_falsa([FICHA_A, FICHA_B, FICHA_C], [CALENTAMIENTO_SOLO, " Algo", " Bote protegido."])
    sesion.generar_sesion("U16", 90, "bote")
    assert "**" in peticiones[2]["options"]["stop"]


# ── defectos vistos con el modelo real ───────────────────────────────────────

def test_si_el_modelo_repite_la_etiqueta_con_la_que_acaba_el_arranque_no_sale_duplicada(sesion_falsa):
    sesion_falsa(
        [FICHA_A, FICHA_B, FICHA_C],
        ["Juego: Pañuelo con balón\nReglas: Dos equipos.", "Juego: Estiramientos\nReglas: Sin balón.", " el bote."],
    )
    texto = sesion.generar_sesion("U16", 90, "bote")["texto"]
    assert "Juego:Juego:" not in texto and "Juego: Juego:" not in texto
    assert "**CALENTAMIENTO (15 min)**\nJuego: Pañuelo con balón" in texto
    assert "**VUELTA A LA CALMA (5 min)**\nJuego: Estiramientos" in texto


def test_los_fundamentos_continuan_la_frase_guia(sesion_falsa):
    sesion_falsa([FICHA_A, FICHA_B, FICHA_C], [CALENTAMIENTO_SOLO, " Estiramientos", " el bote protegido y la visión."])
    texto = sesion.generar_sesion("U16", 90, "bote")["texto"]
    assert texto.rstrip().endswith("**Fundamentos**: En esta sesión se trabajan el bote protegido y la visión.")


def test_si_el_modelo_no_da_fundamentos_se_componen_con_los_objetivos_tecnicos_de_las_fichas(sesion_falsa):
    a = dict(FICHA_A, objetivos={"tacticos": ["bote"], "tecnicos": ["agarre del balón", "cambio de mano"]})
    b = dict(FICHA_B, objetivos={"tacticos": ["bote"], "tecnicos": ["cambio de mano", "bote bajo"]})
    sesion_falsa([a, b, FICHA_C], [CALENTAMIENTO_SOLO, " Estiramientos", ""])
    r = sesion.generar_sesion("U16", 90, "bote")
    assert r["texto"].rstrip().endswith("**Fundamentos**: agarre del balón, cambio de mano, bote bajo.")
    assert r["avisos"] == []


def test_sin_fichas_con_objetivos_tecnicos_y_sin_respuesta_no_hay_fundamentos(sesion_falsa):
    sesion_falsa([FICHA_A, FICHA_B, FICHA_C], [CALENTAMIENTO_SOLO, " Estiramientos", ""])
    assert "**Fundamentos**" not in sesion.generar_sesion("U16", 90, "bote")["texto"]


# ── la pista de la plantilla no puede acabar como nombre del ejercicio ───────────────────────

def test_si_el_modelo_copia_la_pista_de_nombre_no_sale_como_nombre_del_ejercicio(sesion_falsa):
    copiada = RESPUESTA_PROPUESTO.replace("Ejercicio 1: Cierre y recuperación",
                                          "Ejercicio 1: (nombre propio del ejercicio)")
    sesion_falsa([FICHA_SIN_RELACION, FICHA_B, FICHA_C], [copiada])
    texto = sesion.generar_sesion("U16", 90, "bote")["texto"]
    assert "(nombre propio" not in texto
    assert "Ejercicio 1: Ejercicio propuesto\nDuración: 20 min\n" + MARCA_PROPUESTO in texto


def test_la_variante_de_un_hueco_propuesto_tampoco_lleva_la_pista(sesion_falsa):
    # U10 a 90 min: el hueco propuesto se parte en 1.1 y 1.2
    base = ("Ejercicio 1.1: (nombre propio del ejercicio)\nDuración: 10 min\nOrganización: Dos filas.\n"
            "Puntos clave:\n- Manos activas.\n\n"
            "Ejercicio 1.2:\nDuración: 10 min\nQué cambia respecto a 1.1: Con defensor.\nOrganización: Igual.\n\n")
    respuesta = RESPUESTA_BASE.replace("**VUELTA A LA CALMA", base + "**VUELTA A LA CALMA", 1)
    sesion_falsa([FICHA_SIN_RELACION, FICHA_B, FICHA_C], [respuesta])
    texto = sesion.generar_sesion("U10", 90, "bote")["texto"]
    assert "(nombre propio" not in texto


def test_la_peticion_al_modelo_desactiva_el_razonamiento(sesion_falsa):
    # modelos con razonamiento por defecto (Qwen3.5, Gemma 4) gastarían el presupuesto pensando
    peticiones = sesion_falsa([FICHA_A, FICHA_B, FICHA_C], [RESPUESTA_BASE])
    sesion.generar_sesion("U16", 90, "bote")
    assert peticiones and all(p.get("think") is False for p in peticiones)
