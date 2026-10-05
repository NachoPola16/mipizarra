# tests/test_bloques_curados.py
"""Fase 1.1: los bloques de ejercicios de la biblioteca los compone el código con el
texto curado de exercises.json (descripción y puntos clave íntegros), no el modelo."""
import re

import pytest

from bloques import bloque_curado, bloque_variante_curada, extraer_seccion, formatear_descripcion
from main import parsear_ejercicios_de_sesion


def _normalizado(texto: str) -> str:
    return re.sub(r"\s+", " ", texto).strip()


def _ficha(ejercicios, id_):
    return next(e for e in ejercicios if e["id"] == id_)


# ── formatear_descripcion ────────────────────────────────────────────────────

def test_formatear_quita_el_prefijo_organizacion_y_separa_las_secciones():
    desc = ("ORGANIZACIÓN: dos filas en cabecera. SECUENCIA: (1) A1 corta. (2) A2 pasa. "
            "ROTACIÓN: A1 va a la otra fila. PROGRESIÓN: sin defensa → defensa pasiva.")
    assert formatear_descripcion(desc).split("\n") == [
        "dos filas en cabecera.",
        "SECUENCIA: (1) A1 corta. (2) A2 pasa.",
        "ROTACIÓN: A1 va a la otra fila.",
        "PROGRESIÓN: sin defensa → defensa pasiva.",
    ]


def test_formatear_deja_igual_una_descripcion_sin_secciones():
    assert formatear_descripcion("Dos filas. El primero bota y finaliza.") == "Dos filas. El primero bota y finaliza."


def test_formatear_no_pierde_ni_cambia_ni_una_palabra_en_los_63_ejercicios(ejercicios):
    for ej in ejercicios:
        original = ej["descripcion"].replace("ORGANIZACIÓN:", "", 1) if ej["descripcion"].startswith("ORGANIZACIÓN:") else ej["descripcion"]
        assert _normalizado(formatear_descripcion(ej["descripcion"])) == _normalizado(original), ej["id"]


# ── extraer_seccion ──────────────────────────────────────────────────────────

def test_extraer_seccion_devuelve_el_texto_de_la_progresion(ejercicios):
    desc = formatear_descripcion(_ficha(ejercicios, "ej_003")["descripcion"])
    assert extraer_seccion(desc, ("PROGRESIÓN", "VARIANTES")) == (
        "sin A2 defendiendo (solo corte y tiro) → A2 defiende pasivo → A2 defiende activo."
    )


def test_extraer_seccion_sin_esa_seccion_devuelve_cadena_vacia():
    assert extraer_seccion("dos filas.\nROTACIÓN: cambian.", ("PROGRESIÓN", "VARIANTES")) == ""


def test_extraer_seccion_acaba_donde_empieza_la_siguiente():
    desc = "PROGRESIÓN: primero esto.\nROTACIÓN: luego aquello."
    assert extraer_seccion(desc, ("PROGRESIÓN",)) == "primero esto."


# ── bloque_curado ────────────────────────────────────────────────────────────

def test_bloque_curado_lleva_nombre_duracion_descripcion_y_todos_los_puntos_clave(ejercicios):
    ej = _ficha(ejercicios, "ej_003")
    bloque = bloque_curado("2", ej, 15, partido=False)
    lineas = bloque.split("\n")
    assert lineas[0] == f"Ejercicio 2: {ej['nombre']}"
    assert lineas[1] == "Duración: 15 min"
    assert lineas[2] == "Organización:"
    assert "Puntos clave:" in lineas
    for punto in ej["puntos_clave"]:
        assert f"- {punto}" in lineas
    assert "A1 da un paso lento hacia la línea de fondo" in bloque


def test_bloque_curado_partido_se_numera_n_1(ejercicios):
    bloque = bloque_curado("1", _ficha(ejercicios, "ej_003"), 10, partido=True)
    assert bloque.split("\n")[0].startswith("Ejercicio 1.1: ")


def test_bloque_curado_reproduce_la_ficha_completa_en_los_63_ejercicios(ejercicios):
    for ej in ejercicios:
        bloque = _normalizado(bloque_curado("1", ej, 10, partido=False))
        assert _normalizado(formatear_descripcion(ej["descripcion"])) in bloque, ej["id"]
        for punto in ej["puntos_clave"]:
            assert _normalizado(punto) in bloque, ej["id"]


def test_los_parsers_leen_el_bloque_curado_de_los_63_ejercicios(ejercicios):
    """parsear_ejercicios_de_sesion (diagramas) y el PDF (que abre página en cada línea
    'Ejercicio N') no deben confundirse con el contenido de la ficha."""
    for ej in ejercicios:
        bloque = bloque_curado("1", ej, 10, partido=False)
        cuerpo = bloque.split("\n")[1:]
        assert not any(re.match(r"\s*Ejercicio \d", linea) for linea in cuerpo), ej["id"]
        parseados = parsear_ejercicios_de_sesion(bloque)
        assert len(parseados) == 1, ej["id"]
        assert parseados[0]["nombre"] == ej["nombre"], ej["id"]
        assert _normalizado(formatear_descripcion(ej["descripcion"])) == _normalizado(parseados[0]["descripcion"]), ej["id"]


# ── bloque_variante_curada ───────────────────────────────────────────────────

def test_variante_curada_sale_de_la_progresion_de_la_ficha(ejercicios):
    ej = _ficha(ejercicios, "ej_003")
    bloque = bloque_variante_curada("2", ej, 10)
    assert bloque.split("\n")[0] == f'Ejercicio 2.2 (variante de "{ej["nombre"]}"):'
    assert "Duración: 10 min" in bloque
    assert "A2 defiende pasivo → A2 defiende activo" in bloque
    parseado = parsear_ejercicios_de_sesion(bloque)[0]
    assert parseado["nombre"] == ej["nombre"]
    assert "A2 defiende pasivo" in parseado["descripcion"]


def test_variante_curada_es_none_si_la_ficha_no_tiene_progresion():
    ej = {"nombre": "X", "descripcion": "Dos filas. El primero bota.", "puntos_clave": ["a"]}
    assert bloque_variante_curada("1", ej, 10) is None


@pytest.mark.parametrize("ej_id", ["ej_003"])
def test_variante_curada_no_repite_los_puntos_clave(ejercicios, ej_id):
    bloque = bloque_variante_curada("1", _ficha(ejercicios, ej_id), 10)
    assert "Puntos clave:" not in bloque


def test_las_variantes_curadas_de_todas_las_fichas_con_progresion_se_parsean(ejercicios):
    con_progresion = [e for e in ejercicios if bloque_variante_curada("1", e, 10)]
    assert len(con_progresion) >= 8
    for ej in con_progresion:
        parseados = parsear_ejercicios_de_sesion(bloque_variante_curada("1", ej, 10))
        assert [p["nombre"] for p in parseados] == [ej["nombre"]], ej["id"]


# ── extraer_bloques: trocea la respuesta del modelo por secciones ────────────

def test_extraer_bloques_separa_calentamiento_ejercicios_vuelta_y_fundamentos():
    from bloques import extraer_bloques
    texto = """\
**CALENTAMIENTO (15 min)**
Juego: Pañuelo
Reglas: Dos equipos.

**PARTE PRINCIPAL**

Ejercicio 1.2 (variante de "A" — cambio):
Duración: 5 min
Qué cambia respecto a 1.1: algo.

**DESCANSO (3 min)**

Ejercicio 3: Propuesto
Duración: 10 min

**VUELTA A LA CALMA (5 min)**
Juego: Estiramientos

**Fundamentos**: Bote protegido."""
    b = extraer_bloques(texto)
    assert set(b) == {"calentamiento", "ej:1.2", "ej:3", "vuelta", "fundamentos"}
    assert b["calentamiento"] == "Juego: Pañuelo\nReglas: Dos equipos."
    assert b["ej:1.2"].startswith('Ejercicio 1.2 (variante de "A"')
    assert b["ej:1.2"].endswith("Qué cambia respecto a 1.1: algo.")
    assert b["ej:3"] == "Ejercicio 3: Propuesto\nDuración: 10 min"
    assert b["vuelta"] == "Juego: Estiramientos"
    assert b["fundamentos"] == "Bote protegido."


def test_extraer_bloques_conserva_solo_la_primera_aparicion_de_cada_bloque():
    from bloques import extraer_bloques
    texto = "Ejercicio 1: Uno\nDuración: 5 min\n\nEjercicio 1: Repetido\nOrganización: otra cosa"
    assert extraer_bloques(texto)["ej:1"] == "Ejercicio 1: Uno\nDuración: 5 min"


def test_extraer_bloques_de_un_texto_vacio_es_un_diccionario_vacio():
    from bloques import extraer_bloques
    assert extraer_bloques("") == {}
