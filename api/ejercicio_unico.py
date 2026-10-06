# api/ejercicio_unico.py
"""Modo 2: generación de un ejercicio suelto y reprompt (corrección pedida por el entrenador).

Los dos comparten el mismo núcleo: el texto del ejercicio sale con un esquema fijo (sin él, el modelo inventaba
las claves: «duración», «organización», «secuencia»...), pasa por la guardia de líneas rojas de la edad (un
reintento avisando) y el diagrama lo genera y valida el mismo generador que usan las sesiones."""
import json
import logging

import requests

from config import MODEL, OLLAMA_URL
from diagramas import generar_coordenadas_ejercicio
from ejercicios import cargar_ejercicios, construir_contexto_ejercicios, filtrar_ejercicios
from lineas_rojas import instruccion_prompt, violaciones

logger = logging.getLogger(__name__)

# Forma que debe tener el ejercicio; restringe la decodificación (Ollama/XGrammar).
_ESQUEMA_EJERCICIO = {
    "type": "object",
    "properties": {
        "nombre":       {"type": "string"},
        "descripcion":  {"type": "string"},
        "duracion_min": {"type": "integer"},
        "puntos_clave": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["nombre", "descripcion", "puntos_clave"],
}

_CAMPOS_PEDIDOS = (
    "Devuelve un JSON con: \"nombre\" (nombre propio del ejercicio; si es de una situación numérica, "
    "indícala, p. ej. 1c1 o 2c1), \"descripcion\" (en prosa: organización y material, secuencia, "
    "rotación y progresión), \"duracion_min\" (minutos, múltiplo de 5) y \"puntos_clave\" "
    "(de 3 a 5 indicaciones técnicas para el entrenador)."
)


def _normalizar(ej) -> dict | None:
    """El ejercicio con los campos limpios, o None si no tiene nombre y descripción."""
    if not isinstance(ej, dict):
        return None
    nombre = str(ej.get("nombre") or "").strip()
    descripcion = str(ej.get("descripcion") or "").strip()
    if not nombre or not descripcion:
        return None
    resultado = {"nombre": nombre, "descripcion": descripcion}
    try:
        resultado["duracion_min"] = int(ej["duracion_min"])
    except (KeyError, TypeError, ValueError):
        pass
    puntos = ej.get("puntos_clave") if isinstance(ej.get("puntos_clave"), list) else []
    resultado["puntos_clave"] = [str(p).strip() for p in puntos if str(p).strip()]
    return resultado


def _pedir_ejercicio(prompt: str) -> dict | None:
    r = requests.post(
        f"{OLLAMA_URL}/api/generate",
        json={
            "model":  MODEL,
            "prompt": prompt,
            "format": _ESQUEMA_EJERCICIO,
            "think":  False,          # sin razonamiento: debe ser JSON estructurado
            "stream": False,
            "options": {"temperature": 0.4, "num_predict": 900, "top_k": 40},
        },
        timeout=120,
    )
    r.raise_for_status()
    try:
        return _normalizar(json.loads(r.json()["response"].strip()))
    except (ValueError, KeyError):
        return None


def _ejercicio_validado(edad: str, construir_prompt) -> dict:
    """Pide el ejercicio, lo pasa por la guardia de líneas rojas (un reintento avisando) y le añade el
    diagrama validado. `construir_prompt(correccion)` arma el prompt; devuelve {} si no hay ejercicio válido."""
    correccion = ""
    for intento in (1, 2):
        ej = _pedir_ejercicio(construir_prompt(correccion))
        if ej is not None:
            texto = " ".join([ej["nombre"], ej["descripcion"], *ej["puntos_clave"]])
            malas = violaciones(texto, edad)
            if not malas:
                break
            detalle = ", ".join(malas)
            logger.warning(f"Línea roja en el ejercicio generado ({detalle})")
            correccion = (f"CORRECCIÓN: tu respuesta anterior incumplió las reglas de la categoría "
                          f"({detalle}). Hazlo de nuevo sin esos contenidos.\n\n")
        if intento == 2:
            return {}
    diagrama = generar_coordenadas_ejercicio(ej["descripcion"], ej["nombre"])
    if diagrama:
        ej["diagrama"] = diagrama
    return ej


def _contexto(edad: str, objetivo: str) -> str:
    return construir_contexto_ejercicios(filtrar_ejercicios(cargar_ejercicios(), edad, objetivo))


def generar_ejercicio_unico(edad: str, objetivo: str, descripcion: str = "") -> dict:
    """Modo 2: genera un único ejercicio con diagrama. Devuelve {} si no se consigue uno válido."""
    ctx = _contexto(edad, objetivo)
    prohibido = instruccion_prompt(edad)
    prohibido = f"{prohibido}\n\n" if prohibido else ""

    def construir_prompt(correccion: str = "") -> str:
        return (
            f"Genera un ejercicio de baloncesto para la categoría {edad} con objetivo: {objetivo}.\n"
            + (f"Descripción adicional: {descripcion}\n" if descripcion else "")
            + f"\n{prohibido}{correccion}Ejercicios de referencia:\n{ctx}\n\n{_CAMPOS_PEDIDOS}"
        )

    try:
        ej = _ejercicio_validado(edad, construir_prompt)
        if ej:
            logger.info(f"Ejercicio generado: {ej['nombre']}")
        return ej
    except Exception as e:
        logger.warning(f"Error generando ejercicio: {e}")
        return {}


def reprompt_ejercicio(edad: str, objetivo: str, nombre: str, descripcion: str, instruccion: str) -> dict:
    """Regenera un ejercicio ya existente aplicando una corrección pedida por el entrenador. Solo viaja ese
    ejercicio (no la sesión entera): el contexto no crece con el número de ejercicios de la sesión."""
    ctx = _contexto(edad, objetivo)
    prohibido = instruccion_prompt(edad)
    prohibido = f"{prohibido}\n\n" if prohibido else ""

    def construir_prompt(correccion: str = "") -> str:
        # OJO: no usar etiquetas con mayúscula («Nombre:», «Descripción:») para describir el ejercicio actual: el
        # modelo las copiaba como claves del JSON en lugar del esquema real (se observó «Nombre»/«ORGANIZACIÓN»).
        return (
            f"Este ejercicio de baloncesto ya está generado para la categoría {edad}, "
            f"dentro de una sesión con objetivo general: {objetivo}.\n\n"
            f"ejercicio actual — nombre: {nombre}\n"
            f"ejercicio actual — descripción: {descripcion}\n\n"
            f"El entrenador pide este cambio sobre ESTE ejercicio: {instruccion}\n\n"
            "Genera la versión corregida del ejercicio aplicando ese cambio y manteniendo lo demás. "
            "Si el cambio cambia a los jugadores o sus movimientos (por ejemplo, quitar el defensor), "
            "la descripción debe reflejarlo con claridad. Si cambia cuántos atacantes y defensores hay, el "
            "nombre del ejercicio debe indicar la nueva situación numérica (por ejemplo, 1c0 si ya no hay "
            "defensor): el diagrama se dibuja con los jugadores que dice el nombre.\n\n"
            f"{prohibido}{correccion}Ejercicios de referencia:\n{ctx}\n\n{_CAMPOS_PEDIDOS}"
        )

    try:
        ej = _ejercicio_validado(edad, construir_prompt)
        if ej:
            logger.info(f"Ejercicio corregido: {ej['nombre']}")
        return ej
    except Exception as e:
        logger.warning(f"Error corrigiendo ejercicio: {e}")
        return {}
