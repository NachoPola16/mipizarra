# tests/test_sesion_ensamblado.py
"""generar_sesion compone con el código los ejercicios de la biblioteca (ficha curada íntegra) y
deja al modelo solo calentamiento, vuelta a la calma, fundamentos y los huecos sin ficha relevante
(propuestos por la IA). La sesión tiene entre 5 y 8 ejercicios en total, según plan_sesion.
El modelo se simula: no hay Ollama ni red."""
import pytest

import sesion
from plan_sesion import PlanDeTiempos

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
    """Devuelve una función que prepara las fichas elegidas (None = hueco que propone la IA), el plan
    de tiempos y las respuestas del modelo, y la lista de peticiones que recibió el 'modelo'.
    Por defecto, tres ejercicios de 20 min (calentamiento 15, vuelta 5, descanso 3)."""
    peticiones = []

    def preparar(fichas, respuestas, duraciones=None, plan_real=False):
        respuestas = list(respuestas)
        fichas = list(fichas)
        monkeypatch.setattr(sesion, "cargar_ejercicios", lambda: [])
        monkeypatch.setattr(sesion, "_elegir_fichas",
                            lambda ejercicios, edad, objetivo, n, **kw: (fichas + [None] * n)[:n])
        monkeypatch.setattr(sesion, "construir_contexto_teoria", lambda obj, edad: "")
        if not plan_real:
            tiempos = tuple(duraciones or (20,) * len(fichas))
            monkeypatch.setattr(sesion, "plan_de_tiempos", lambda d, e: PlanDeTiempos(15, 5, 3, tiempos))

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


# ── cuántos ejercicios: el plan manda (entre 5 y 8 en total) ─────────────────

def test_se_piden_a_la_seleccion_tantas_fichas_como_ejercicios_tiene_el_plan(monkeypatch):
    pedidas = []
    monkeypatch.setattr(sesion, "cargar_ejercicios", lambda: [])
    monkeypatch.setattr(sesion, "construir_contexto_teoria", lambda obj, edad: "")
    monkeypatch.setattr(sesion, "_elegir_fichas",
                        lambda ejercicios, edad, objetivo, n, **kw: (pedidas.append(n), [None] * n)[1])
    monkeypatch.setattr(sesion.requests, "post", lambda url, json, timeout: _Resp(RESPUESTA_BASE))
    for edad, duracion, esperado in (("U10", 60, 4), ("U10", 90, 7), ("U16", 60, 4), ("U16", 90, 5)):
        sesion.generar_sesion(edad, duracion, "bote")
        assert pedidas[-1] == esperado, (edad, duracion)


@pytest.mark.parametrize("edad,duracion", [("U10", 90), ("U10", 60), ("U14", 90), ("U16", 60), ("U16", 120)])
def test_la_sesion_completa_tiene_entre_5_y_8_ejercicios_contando_calentamiento_y_vuelta(
        sesion_falsa, edad, duracion):
    fichas = [FICHA_A, FICHA_B, FICHA_C, FICHA_A, FICHA_B, FICHA_C]
    sesion_falsa(fichas, [RESPUESTA_BASE], plan_real=True)
    texto = sesion.generar_sesion(edad, duracion, "bote")["texto"]
    principales = {linea.split(":")[0] for linea in texto.split("\n")
                   if linea.startswith("Ejercicio ") and "." not in linea.split(":")[0]}
    assert 5 <= len(principales) + 2 <= 8, (edad, duracion, sorted(principales))


def test_los_minutos_de_cada_ejercicio_son_los_del_plan(sesion_falsa):
    sesion_falsa([FICHA_A, FICHA_B, FICHA_C, FICHA_B], [RESPUESTA_BASE], duraciones=(15, 10, 10, 5), plan_real=False)
    texto = sesion.generar_sesion("U16", 90, "bote")["texto"]
    for numero, minutos in ((1, 15), (2, 10), (3, 10), (4, 5)):
        assert f"Ejercicio {numero}: " in texto
        bloque = texto.split(f"Ejercicio {numero}: ")[1].split("\n")[1]
        assert bloque == f"Duración: {minutos} min", numero


@pytest.mark.parametrize("n,tras", [(3, 2), (4, 2), (5, 3), (6, 3)])
def test_el_descanso_va_hacia_la_mitad_de_la_parte_principal(sesion_falsa, n, tras):
    fichas = [FICHA_B] * n
    sesion_falsa(fichas, [RESPUESTA_BASE])
    texto = sesion.generar_sesion("U16", 90, "bote")["texto"]
    assert texto.count("**DESCANSO") == 1
    descanso = texto.index("**DESCANSO")
    assert texto.index(f"Ejercicio {tras}:") < descanso < texto.index(f"Ejercicio {tras + 1}:")


# ── variante N.2: solo si la ficha trae progresión curada y el ejercicio es largo para esa edad ──

def test_la_variante_sale_de_la_progresion_curada_solo_en_las_fichas_que_la_traen(sesion_falsa):
    # U10 aguanta 10 min seguidos: a 20 min se parten A y C (traen PROGRESIÓN); B no la trae y va entero
    sesion_falsa([FICHA_A, FICHA_B, FICHA_C], [RESPUESTA_BASE])
    texto = sesion.generar_sesion("U10", 90, "bote")["texto"]

    assert "Ejercicio 1.1: Rueda de bote\nDuración: 10 min" in texto
    assert 'Ejercicio 1.2 (variante de "Rueda de bote"):\nDuración: 10 min' in texto
    assert "Qué cambia respecto a 1.1: sin defensa → con defensa pasiva." in texto

    assert "Ejercicio 2: Zigzag con cambio\nDuración: 20 min" in texto
    assert "Ejercicio 2.1" not in texto and "Ejercicio 2.2" not in texto

    assert "Ejercicio 3.1: Bote 1c1 desde el codo\nDuración: 10 min" in texto
    assert "Qué cambia respecto a 3.1: defensor pasivo → defensor activo." in texto


def test_el_modelo_no_inventa_variantes(sesion_falsa):
    respuesta = RESPUESTA_BASE.replace(
        "**VUELTA A LA CALMA",
        'Ejercicio 2.2 (variante de "Zigzag con cambio"):\nDuración: 99 min\nQué cambia respecto a 2.1: algo inventado.\n\n'
        "**VUELTA A LA CALMA",
    )
    sesion_falsa([FICHA_A, FICHA_B, FICHA_C], [respuesta])
    texto = sesion.generar_sesion("U10", 90, "bote")["texto"]
    assert "algo inventado" not in texto and "99 min" not in texto


def test_el_prompt_no_pide_variantes_al_modelo(sesion_falsa):
    peticiones = sesion_falsa([FICHA_A, FICHA_B, FICHA_C], [RESPUESTA_BASE])
    sesion.generar_sesion("U10", 90, "bote")
    prompt = peticiones[0]["prompt"]
    assert "Ejercicio 1.2" not in prompt and "Ejercicio 2.2" not in prompt and "Ejercicio 3.2" not in prompt


def test_un_ejercicio_que_no_supera_lo_que_aguanta_su_edad_no_se_parte(sesion_falsa):
    # Cadete aguanta 20 min seguidos: a 20 min no hace falta variante aunque la ficha la traiga
    sesion_falsa([FICHA_A, FICHA_B, FICHA_C], [RESPUESTA_BASE])
    texto = sesion.generar_sesion("U16", 90, "bote")["texto"]
    assert "Ejercicio 1.1" not in texto and "variante de" not in texto


def test_pueden_convivir_ejercicios_con_variante_y_sin_ella(sesion_falsa):
    sesion_falsa([FICHA_A, FICHA_B, FICHA_C], [RESPUESTA_BASE], duraciones=(15, 10, 20))
    texto = sesion.generar_sesion("U10", 90, "bote")["texto"]
    assert "Ejercicio 1.1: Rueda de bote\nDuración: 10 min" in texto        # 15 > 10: se parte (10 + 5)
    assert 'Ejercicio 1.2 (variante de "Rueda de bote"):\nDuración: 5 min' in texto
    assert "Ejercicio 2: Zigzag con cambio\nDuración: 10 min" in texto       # 10 no supera 10: entero
    assert "Ejercicio 3.1: Bote 1c1 desde el codo\nDuración: 10 min" in texto


# ── huecos sin ficha: los propone la IA y van marcados ──────────────────────

RESPUESTA_PROPUESTO = RESPUESTA_BASE.replace(
    "**VUELTA A LA CALMA",
    '''Ejercicio 1: Cierre y recuperación
Duración: 7 min
Organización: Dos filas; el defensor cierra tras el pase.
Puntos clave:
- Manos activas.

**VUELTA A LA CALMA''',
)


def test_un_hueco_sin_ficha_lo_propone_la_ia_y_va_marcado(sesion_falsa):
    peticiones = sesion_falsa([None, FICHA_B, FICHA_C], [RESPUESTA_PROPUESTO])
    r = sesion.generar_sesion("U16", 90, "bote")
    texto = r["texto"]

    assert ("Ejercicio 1: Cierre y recuperación\nDuración: 20 min\n" + MARCA_PROPUESTO +
            "\nOrganización: Dos filas; el defensor cierra tras el pase.") in texto
    assert texto.count(MARCA_PROPUESTO) == 1                   # solo el propuesto lleva marca
    assert r["propuestos"] == [1]
    assert [e["id"] for e in r["ejercicios_usados"]] == ["t_b", "t_c"]
    assert "SIN FICHA" in peticiones[0]["prompt"]


def test_si_todos_los_huecos_son_propuestos(sesion_falsa):
    respuesta = RESPUESTA_BASE.replace("**VUELTA A LA CALMA", "\n".join(
        f"Ejercicio {n}: Propuesta {n}\nDuración: 5 min\nOrganización: algo {n}.\nPuntos clave:\n- clave {n}\n"
        for n in (1, 2, 3)) + "\n**VUELTA A LA CALMA")
    sesion_falsa([None, None, None], [respuesta])
    r = sesion.generar_sesion("U16", 90, "defensa")
    assert r["propuestos"] == [1, 2, 3]
    assert r["texto"].count(MARCA_PROPUESTO) == 3
    assert r["ejercicios_usados"] == []


def test_un_hueco_propuesto_no_se_parte_aunque_sea_largo_para_su_edad(sesion_falsa):
    respuesta = RESPUESTA_PROPUESTO.replace("Ejercicio 1: Cierre", "Ejercicio 1: Cierre")
    sesion_falsa([None, FICHA_B, FICHA_C], [respuesta])
    texto = sesion.generar_sesion("U10", 90, "bote")["texto"]
    assert "Ejercicio 1.1" not in texto and "Ejercicio 1.2" not in texto
    assert "Ejercicio 1: Cierre y recuperación\nDuración: 20 min" in texto


# ── elegir las fichas: solo relevantes, y se aprovechan todas las que haya ───

def _ficha_sintetica(nombre, tacticos=(), edades=("U12",)):
    return {"id": nombre, "nombre": nombre, "categoria": "juego_equipo", "edades": list(edades),
            "descripcion": "", "objetivos": {"tacticos": list(tacticos)}}


def test_elegir_fichas_solo_devuelve_las_relevantes_para_el_objetivo():
    biblioteca = [_ficha_sintetica("Circuito de bote", ["bote"]), _ficha_sintetica("Zigzag con bote 2c0"),
                  _ficha_sintetica("Rueda de conos", ["agilidad"])]
    elegidas = sesion._elegir_fichas(biblioteca, "U12", "bote", 3)
    assert all(e is None or "bote" in e["nombre"].lower() for e in elegidas)
    assert [e["nombre"] for e in elegidas if e] and "Rueda de conos" not in [e["nombre"] for e in elegidas if e]


def test_elegir_fichas_aprovecha_las_relevantes_en_vez_de_dejar_huecos_por_una_irrelevante():
    # tres relevantes y una irrelevante para tres huecos: no debe quedar ningún hueco propuesto
    biblioteca = [_ficha_sintetica("Rueda de conos", ["agilidad"]), _ficha_sintetica("Bote en zigzag"),
                  _ficha_sintetica("Bote 1c1 desde el codo"), _ficha_sintetica("Bote y pase 3c0")]
    elegidas = sesion._elegir_fichas(biblioteca, "U12", "bote", 3)
    assert all(elegidas) and "Rueda de conos" not in [e["nombre"] for e in elegidas]


def test_elegir_fichas_devuelve_n_con_none_si_no_hay_suficientes():
    biblioteca = [_ficha_sintetica("Bote en zigzag")]
    elegidas = sesion._elegir_fichas(biblioteca, "U12", "bote", 5)
    assert len(elegidas) == 5 and sum(e is not None for e in elegidas) == 1


@pytest.mark.parametrize("edad", ["U8", "U10", "U12", "U14", "U16", "Senior"])
@pytest.mark.parametrize("objetivo", ["bote", "defensa", "tiro", "contraataque", "1c1", "pase"])
@pytest.mark.parametrize("n", [3, 4, 5, 6])
def test_elegir_fichas_en_la_biblioteca_real(ejercicios, edad, objetivo, n):
    from ejercicios import es_relevante
    elegidas = sesion._elegir_fichas(ejercicios, edad, objetivo, n)
    ids = [e["id"] for e in elegidas if e]
    assert len(elegidas) == n and len(ids) == len(set(ids))
    assert all(es_relevante(e, objetivo) for e in elegidas if e)


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


def test_el_presupuesto_crece_con_los_huecos_que_escribe_el_modelo(sesion_falsa):
    con_fichas = sesion_falsa([FICHA_A, FICHA_B, FICHA_C], [RESPUESTA_BASE])
    sesion.generar_sesion("U16", 90, "bote")
    base = con_fichas[0]["options"]["num_predict"]
    con_fichas.clear()
    sesion_falsa([None, None, FICHA_C], [RESPUESTA_BASE])
    sesion.generar_sesion("U16", 90, "bote")
    assert con_fichas[0]["options"]["num_predict"] > base


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
    sesion_falsa([None, FICHA_B, FICHA_C], [malo])
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

def test_hueco_propuesto_acepta_cabecera_con_sufijo(sesion_falsa):
    respuesta = RESPUESTA_PROPUESTO.replace("Ejercicio 1: Cierre", "Ejercicio 1.1: Cierre")
    sesion_falsa([None, FICHA_B, FICHA_C], [respuesta])
    r = sesion.generar_sesion("U16", 90, "bote")
    assert "Ejercicio 1: Cierre y recuperación\nDuración: 20 min" in r["texto"]


def test_si_el_modelo_no_escribe_un_hueco_propuesto_se_avisa(sesion_falsa):
    sesion_falsa([None, FICHA_B, FICHA_C], [RESPUESTA_BASE])
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
    peticiones = sesion_falsa([None, FICHA_B, FICHA_C], [CONTINUACION])
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


def test_los_pasos_se_piden_en_el_orden_de_la_sesion_incluido_el_hueco_propuesto(sesion_falsa):
    peticiones = sesion_falsa(
        [None, FICHA_B, FICHA_C],
        [CALENTAMIENTO_SOLO,
         " Cierre y recuperación\nDuración: 20 min\nOrganización: Dos filas.\nPuntos clave:\n- Manos activas.",
         " Estiramientos\nReglas: Sin balón.", " Bote protegido."],
    )
    r = sesion.generar_sesion("U16", 90, "bote")
    assert len(peticiones) == 4
    assert peticiones[1]["prompt"].endswith("Ejercicio 1:")
    assert peticiones[2]["prompt"].endswith("**VUELTA A LA CALMA (5 min)**\nJuego:")
    assert "Ejercicio 1: Cierre y recuperación" in r["texto"] and MARCA_PROPUESTO in r["texto"]


def test_un_apartado_que_el_modelo_no_da_se_pide_una_sola_vez(sesion_falsa):
    peticiones = sesion_falsa([FICHA_A, FICHA_B, FICHA_C], [CALENTAMIENTO_SOLO, "", ""])
    r = sesion.generar_sesion("U16", 90, "bote")
    assert len(peticiones) == 3                      # calentamiento + vuelta + fundamentos, sin bucles
    assert "**CALENTAMIENTO (15 min)**" in r["texto"]


def test_los_pasos_de_relleno_cortan_en_la_siguiente_cabecera(sesion_falsa):
    peticiones = sesion_falsa([FICHA_A, FICHA_B, FICHA_C], [CALENTAMIENTO_SOLO, " Algo", " Algo"])
    sesion.generar_sesion("U16", 90, "bote")
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
    sesion_falsa([None, FICHA_B, FICHA_C], [copiada])
    texto = sesion.generar_sesion("U16", 90, "bote")["texto"]
    assert "(nombre propio" not in texto
    assert "Ejercicio 1: Ejercicio propuesto\nDuración: 20 min\n" + MARCA_PROPUESTO in texto


def test_la_peticion_al_modelo_desactiva_el_razonamiento(sesion_falsa):
    # modelos con razonamiento por defecto (Qwen3.5, Gemma 4) gastarían el presupuesto pensando
    peticiones = sesion_falsa([FICHA_A, FICHA_B, FICHA_C], [RESPUESTA_BASE])
    sesion.generar_sesion("U16", 90, "bote")
    assert peticiones and all(p.get("think") is False for p in peticiones)


# ── más de tres ejercicios: nada heredado del límite de tres ─────────────────

def _respuesta_con_propuestas(numeros):
    bloques = "\n".join(
        f"Ejercicio {n}: Propuesta {n}\nDuración: 10 min\nOrganización: algo {n}.\nPuntos clave:\n- clave {n}\n"
        for n in numeros)
    return RESPUESTA_BASE.replace("**VUELTA A LA CALMA", bloques + "\n**VUELTA A LA CALMA")


def test_los_ejercicios_propuestos_a_partir_del_cuarto_no_se_recortan(sesion_falsa):
    fichas = [FICHA_B, FICHA_B, FICHA_B, None, None, None]
    sesion_falsa(fichas, [_respuesta_con_propuestas([4, 5, 6])], duraciones=(10,) * 6)
    r = sesion.generar_sesion("U16", 90, "bote")
    for n in (4, 5, 6):
        assert f"Ejercicio {n}: Propuesta {n}" in r["texto"], n
    assert r["propuestos"] == [4, 5, 6] and r["avisos"] == []


def test_las_paradas_del_modelo_no_incluyen_numeros_de_ejercicio(sesion_falsa):
    # «Ejercicio 4:» como parada cortaba en seco al modelo cuando repetía la cabecera de su hueco
    peticiones = sesion_falsa([FICHA_A, FICHA_B, FICHA_C], [RESPUESTA_BASE])
    sesion.generar_sesion("U16", 90, "bote")
    assert not any(p.startswith("Ejercicio ") for p in peticiones[0]["options"]["stop"])


def test_un_paso_de_hueco_acepta_que_el_modelo_repita_su_cabecera(sesion_falsa):
    peticiones = sesion_falsa(
        [FICHA_B, FICHA_B, FICHA_B, None],
        [CALENTAMIENTO_SOLO,
         "Ejercicio 4: Propuesta 4\nDuración: 10 min\nOrganización: algo.\nPuntos clave:\n- clave",
         " Estiramientos", " el bote."],
        duraciones=(10, 10, 10, 10),
    )
    r = sesion.generar_sesion("U16", 90, "bote")
    assert "Ejercicio 4: Propuesta 4" in r["texto"] and r["propuestos"] == [4]


# ── lo que el entrenador pide expresamente se hace, con aviso (también en la sesión completa) ────────

def test_si_el_objetivo_pide_una_linea_roja_se_hace_y_se_avisa(sesion_falsa):
    peticiones = sesion_falsa([FICHA_A, FICHA_B, FICHA_C], [_con_calentamiento("Bloqueo directo con el pívot")])
    r = sesion.generar_sesion("U12", 90, "bloqueo directo")
    assert len(peticiones) == 1                                    # sin reintento por línea roja
    assert "EXCEPCIÓN" in peticiones[0]["prompt"] and "bloqueo" in peticiones[0]["prompt"].split("EXCEPCIÓN")[1]
    assert "Bloqueo directo con el pívot" in r["texto"]            # la pieza del modelo se conserva
    assert len(r["avisos"]) == 1
    assert "Has pedido" in r["avisos"][0] and "bloqueo" in r["avisos"][0] and "U12" in r["avisos"][0]


def test_lo_pedido_no_deja_pasar_otras_lineas_rojas(sesion_falsa):
    peticiones = sesion_falsa(
        [FICHA_A, FICHA_B, FICHA_C],
        [_con_calentamiento("Defensa zonal 2-3 con bloqueos"), _con_calentamiento("Defensa zonal 2-3 con bloqueos")],
    )
    r = sesion.generar_sesion("U12", 90, "bloqueo directo")
    assert len(peticiones) == 2                                    # reintenta por la zonal, no por el bloqueo
    assert "zonal" not in r["texto"].lower()
    assert any("calentamiento" in a.lower() for a in r["avisos"])
    assert any("Has pedido" in a for a in r["avisos"])


def test_el_plural_de_lo_pedido_tambien_vale(sesion_falsa):
    sesion_falsa([FICHA_A, FICHA_B, FICHA_C], [_con_calentamiento("Juego con bloqueos y continuación")])
    r = sesion.generar_sesion("U12", 90, "trabajar el bloqueo")
    assert "bloqueos" in r["texto"]
    assert len(r["avisos"]) == 1


def test_sin_peticion_expresa_no_hay_aviso_de_peticion(sesion_falsa):
    peticiones = sesion_falsa([FICHA_A, FICHA_B, FICHA_C], [RESPUESTA_BASE])
    r = sesion.generar_sesion("U12", 90, "bote")
    assert r["avisos"] == []
    assert "EXCEPCIÓN" not in peticiones[0]["prompt"]


def test_en_edades_sin_linea_roja_el_objetivo_no_genera_aviso(sesion_falsa):
    sesion_falsa([FICHA_A, FICHA_B, FICHA_C], [RESPUESTA_BASE])
    assert sesion.generar_sesion("U18", 90, "bloqueo directo")["avisos"] == []


def test_si_la_sesion_final_no_incluye_lo_pedido_el_aviso_lo_dice(sesion_falsa):
    # el objetivo pide bloqueo, pero ni las fichas ni el modelo lo traen: no se promete que «se ha hecho»
    sesion_falsa([FICHA_A, FICHA_B, FICHA_C], [RESPUESTA_BASE])
    r = sesion.generar_sesion("U12", 90, "bloqueo directo")
    assert len(r["avisos"]) == 1
    assert "no lo incluye" in r["avisos"][0] and "bloqueo" in r["avisos"][0]
    assert "Se ha hecho" not in r["avisos"][0]


def test_si_la_sesion_final_si_incluye_lo_pedido_el_aviso_dice_que_se_hizo(sesion_falsa):
    sesion_falsa([FICHA_A, FICHA_B, FICHA_C], [_con_calentamiento("Bloqueo directo con el pívot")])
    r = sesion.generar_sesion("U12", 90, "bloqueo directo")
    assert "Se ha hecho porque lo pides" in r["avisos"][0]


def test_con_varios_terminos_pedidos_se_avisa_de_cada_uno(sesion_falsa):
    # pide bloqueo y pantalla; el modelo solo escribe el bloqueo: dos avisos, uno por cada situación
    sesion_falsa([FICHA_A, FICHA_B, FICHA_C], [_con_calentamiento("Bloqueo directo con el pívot")])
    r = sesion.generar_sesion("U12", 90, "bloqueo y pantalla")
    assert len(r["avisos"]) == 2
    hecho = next(a for a in r["avisos"] if "Se ha hecho" in a)
    ausente = next(a for a in r["avisos"] if "no lo incluye" in a)
    assert "bloqueo" in hecho and "pantalla" in ausente
