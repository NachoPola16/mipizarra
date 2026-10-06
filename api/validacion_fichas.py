# api/validacion_fichas.py
"""Filtro automático de fichas de ejercicio (data/exercises.json).

Devuelve la lista de problemas de una ficha: esquema, edades, líneas rojas, terminología y diagrama válido. Rechaza
solo lo que incumple reglas objetivas; no juzga si el ejercicio es bueno (eso es revisión humana o de muestreo). Es la
primera barrera de los candidatos antes de que nadie los lea y la comparten los tests de la biblioteca."""
import re
import unicodedata

from diagram_renderer import render_diagram
from diagramas import _validar_diagrama
from lineas_rojas import CATEGORIAS_MINIBASKET, violaciones

CATEGORIAS = {"ventaja_numerica", "bloqueo_directo", "bloqueo_indirecto", "tiro", "1c1", "juego_equipo",
              "fisico", "calentamiento"}
EDADES = {"U8", "U10", "U12", "U14", "U16", "U18", "Senior"}
EDADES_MINIBASKET = {"U8", "U10", "U12"}
CATEGORIAS_BLOQUEO = {"bloqueo_directo", "bloqueo_indirecto"}
CAMPOS_OBLIGATORIOS = ("id", "nombre", "categoria", "edades", "duracion_min", "intensidad", "carga_cognitiva",
                       "objetivos", "descripcion", "puntos_clave")
DESCRIPCION_MINIMA = 80
PUNTOS_CLAVE = (2, 7)
DURACION_MIN, DURACION_MAX = 5, 30      # las fichas actuales duran de 6 a 15 minutos

# Procedencia y terminología que no pueden aparecer en la biblioteca (el repositorio es público).
_PROHIBIDAS = (
    (re.compile(r"\bfuentes?\b"), "«fuente» (no se indica de dónde sale el material)"),
    (re.compile(r"\.pdf\b|\bpdf\b"), "«pdf» (no se indica de dónde sale el material)"),
    (re.compile(r"\bpantallas?\b"), "«pantalla» (el término es «bloqueo»)"),
)


def _normalizar(texto: str) -> str:
    sin = unicodedata.normalize("NFD", str(texto).lower())
    return re.sub(r"[^a-z0-9]+", " ", "".join(c for c in sin if unicodedata.category(c) != "Mn")).strip()


def _texto_de(ficha: dict) -> str:
    puntos = [p for p in ficha.get("puntos_clave", []) if isinstance(p, str)]
    extra = []
    for campo in ("material", "consigna"):
        if isinstance(ficha.get(campo), str):
            extra.append(ficha[campo])
    for campo in ("errores_frecuentes", "que_observar"):
        extra += [x for x in ficha.get(campo, []) if isinstance(x, str)] if isinstance(ficha.get(campo), list) else []
    if isinstance(ficha.get("progresion"), dict):
        extra += [v for v in ficha["progresion"].values() if isinstance(v, str)]
    return " ".join([str(ficha.get("nombre", "")), str(ficha.get("descripcion", "")), *puntos, *extra])


def _diagramas(ficha: dict) -> list[dict]:
    if isinstance(ficha.get("diagramas"), list):
        return [d for d in ficha["diagramas"] if isinstance(d, dict)]
    return [ficha["diagrama"]] if isinstance(ficha.get("diagrama"), dict) else []


def _puntos_de(d: dict) -> list:
    puntos = list(d.get("jugadores_ataque", [])) + list(d.get("jugadores_defensa", [])) + list(d.get("conos", []))
    puntos += [m["a_pos"] for m in d.get("movimientos", []) if isinstance(m, dict) and isinstance(m.get("a_pos"), dict)]
    return puntos


def _problemas_de_diagrama(ficha: dict) -> list[str]:
    problemas = []
    for i, d in enumerate(_diagramas(ficha), start=1):
        etiqueta = f"diagrama {i}"
        fuera = [p for p in _puntos_de(d)
                 if isinstance(p, dict) and not all(isinstance(p.get(k), (int, float)) and 0 <= p[k] <= 100 for k in "xy"
                                                    if k in p)]
        if fuera:
            problemas.append(f"{etiqueta}: coordenadas fuera de la pista (0-100): {fuera[:2]}")
            continue
        try:
            # Sin nombre: no se aplica el recuento de jugadores por «1c1/2c1», que en fichas curadas da falsos positivos
            # (pasador sin defensor, +1 recuperando); sí las referencias, los destinos, las distancias y el tipo.
            error = _validar_diagrama(dict(d), "")
        except Exception as e:  # un diagrama mal formado puede romper el validador
            error = f"no se puede validar ({type(e).__name__}: {e})"
        if error:
            problemas.append(f"{etiqueta}: {error}")
            continue
        try:
            if "<svg" not in render_diagram(dict(d)):
                problemas.append(f"{etiqueta}: no se dibuja")
        except Exception as e:
            problemas.append(f"{etiqueta}: no se puede dibujar ({type(e).__name__}: {e})")
    return problemas


def _problemas_de_campos_opcionales(ficha: dict) -> list[str]:
    problemas = []
    for campo in ("material", "consigna"):
        if campo in ficha and not (isinstance(ficha[campo], str) and ficha[campo].strip()):
            problemas.append(f"{campo}: debe ser un texto no vacío")
    for campo in ("errores_frecuentes", "que_observar"):
        if campo in ficha:
            v = ficha[campo]
            if not (isinstance(v, list) and v and all(isinstance(x, str) and x.strip() for x in v)):
                problemas.append(f"{campo}: debe ser una lista de textos no vacíos")
    if "progresion" in ficha:
        p = ficha["progresion"]
        if not (isinstance(p, dict) and p and set(p) <= {"facilitar", "complicar"}
                and all(isinstance(v, str) and v.strip() for v in p.values())):
            problemas.append("progresion: debe ser {'facilitar': texto, 'complicar': texto} (alguno de los dos)")
    return problemas


def validar_ficha(ficha, biblioteca=()) -> list[str]:
    """Problemas de una ficha (lista vacía si pasa el filtro). `biblioteca` son las demás fichas, para detectar
    ids y nombres repetidos."""
    if not isinstance(ficha, dict):
        return ["la ficha no es un objeto"]
    problemas: list[str] = []

    for campo in CAMPOS_OBLIGATORIOS:
        if campo not in ficha:
            problemas.append(f"falta el campo obligatorio «{campo}»")

    ident = ficha.get("id")
    if "id" in ficha:
        if not (isinstance(ident, str) and re.fullmatch(r"ej_\d{3,}", ident)):
            problemas.append("id: debe tener la forma ej_NNN")
        elif any(o.get("id") == ident for o in biblioteca):
            problemas.append(f"id repetido: {ident}")
    if isinstance(ficha.get("nombre"), str) and ficha["nombre"].strip():
        nombre = _normalizar(ficha["nombre"])
        if any(_normalizar(o.get("nombre", "")) == nombre for o in biblioteca if o.get("id") != ident):
            problemas.append(f"nombre repetido: {ficha['nombre']}")
    elif "nombre" in ficha:
        problemas.append("nombre: debe ser un texto no vacío")

    if "categoria" in ficha and ficha["categoria"] not in CATEGORIAS:
        problemas.append(f"categoria: «{ficha['categoria']}» no es una categoría válida")
    edades = ficha.get("edades")
    if "edades" in ficha:
        if not (isinstance(edades, list) and edades and set(edades) <= EDADES):
            problemas.append(f"edades: debe ser una lista no vacía de {sorted(EDADES)}")
    edades = edades if isinstance(edades, list) else []

    d = ficha.get("duracion_min")
    if "duracion_min" in ficha and not (isinstance(d, int) and not isinstance(d, bool)
                                        and DURACION_MIN <= d <= DURACION_MAX):
        problemas.append(f"duracion_min: entero entre {DURACION_MIN} y {DURACION_MAX} minutos")
    for campo in ("intensidad", "carga_cognitiva"):
        v = ficha.get(campo)
        if campo in ficha and not (isinstance(v, int) and not isinstance(v, bool) and 1 <= v <= 5):
            problemas.append(f"{campo}: entero de 1 a 5")
    if "objetivos" in ficha:
        o = ficha["objetivos"]
        listas = [o.get(k) for k in ("tacticos", "tecnicos", "fisicos")] if isinstance(o, dict) else []
        if not any(isinstance(x, list) and x for x in listas):
            problemas.append("objetivos: debe traer al menos una lista no vacía de tacticos, tecnicos o fisicos")

    desc = ficha.get("descripcion")
    if "descripcion" in ficha and not (isinstance(desc, str) and len(desc.strip()) >= DESCRIPCION_MINIMA):
        problemas.append(f"descripcion: texto de al menos {DESCRIPCION_MINIMA} caracteres (organización, secuencia...)")
    pc = ficha.get("puntos_clave")
    if "puntos_clave" in ficha and not (isinstance(pc, list) and PUNTOS_CLAVE[0] <= len(pc) <= PUNTOS_CLAVE[1]
                                        and all(isinstance(p, str) and p.strip() for p in pc)):
        problemas.append(f"puntos_clave: de {PUNTOS_CLAVE[0]} a {PUNTOS_CLAVE[1]} textos no vacíos")

    categoria = ficha.get("categoria")
    if categoria in CATEGORIAS_BLOQUEO and set(edades) & EDADES_MINIBASKET:
        problemas.append("categoría de bloqueo en minibasket: los bloqueos no se trabajan en U8-U12")
    if categoria == "bloqueo_directo" and "U14" in edades:
        problemas.append("bloqueo_directo en U14: la categoría de bloqueo directo es desde U16")

    texto = _texto_de(ficha)
    for edad in edades:
        if edad in CATEGORIAS_MINIBASKET:
            for v in violaciones(texto, edad):
                problemas.append(f"línea roja en {edad}: {v}")
            break          # el veto es el mismo en todo el minibasket: basta con decirlo una vez
    normal = _normalizar(texto)
    for patron, descripcion in _PROHIBIDAS:
        if patron.search(normal):
            problemas.append(f"prohibido: aparece {descripcion}")

    problemas += _problemas_de_diagrama(ficha)
    problemas += _problemas_de_campos_opcionales(ficha)
    return problemas
