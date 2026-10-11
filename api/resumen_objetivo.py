"""Resumen corto del objetivo que escribe el entrenador, para la cabecera del PDF.

Un objetivo largo (muchas pautas) llena la portada. Si cabe en una línea se deja tal cual; si no, se le pide al modelo
una frase corta con los temas clave y, si falla o devuelve algo que no sirve, se recorta por palabras. Nunca lanza.
"""
import logging
import re

import requests

from config import MODEL, OLLAMA_URL

logger = logging.getLogger(__name__)

MAX_LINEA = 80            # hasta aquí el objetivo se muestra tal cual
MAX_RESUMEN = 110         # tope del resumen (una o dos líneas de la portada)

_PROMPT = (
    "Resume este objetivo de entrenamiento de baloncesto en una frase corta y natural, con los 3 o 4 temas "
    "principales separados por comas (máximo 14 palabras, sin punto final). Usa solo lo que dice el texto, sin "
    "añadir nada, sin comillas y sin explicaciones.\n\n"
    "Ejemplo\nObjetivo: quiero que mejoren el bote con las dos manos, que miren al frente, que no haya filas y "
    "que acaben siempre con una bandeja\nResumen: Bote con ambas manos, mirada al frente y finalización con bandeja\n\n"
    "Objetivo: {objetivo}\nResumen:"
)


def _recortar(texto: str, limite: int = MAX_RESUMEN) -> str:
    """Recorte por palabras con puntos suspensivos, sin dejar una palabra a medias."""
    if len(texto) <= limite:
        return texto
    corte = texto[:limite - 1].rsplit(" ", 1)[0].rstrip(" ,;:.-")
    return corte + "…"


def _recortar_por_comas(texto: str, limite: int = MAX_RESUMEN) -> str:
    """Si el modelo enumera demasiados temas, se quedan los primeros (los últimos son los menos importantes)."""
    if len(texto) <= limite:
        return texto
    corte = texto[:limite].rsplit(",", 1)[0]
    return corte if len(corte) >= 8 else texto


def _limpiar_respuesta(texto: str) -> str:
    t = " ".join(str(texto).split()).strip().strip("\"'«»“”")
    t = re.sub(r"^(resumen|objetivo)\s*:\s*", "", t, flags=re.IGNORECASE)
    return t.rstrip(" .")


def resumir_objetivo(objetivo: str) -> str:
    limpio = " ".join(str(objetivo or "").split())
    if len(limpio) <= MAX_LINEA:
        return limpio
    try:
        r = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": MODEL,
                "prompt": _PROMPT.format(objetivo=limpio),
                "think": False,
                "stream": False,
                "options": {"temperature": 0.0, "num_predict": 60},
            },
            timeout=20,
        )
        r.raise_for_status()
        resumen = _recortar_por_comas(_limpiar_respuesta(r.json().get("response", "")))
        if 8 <= len(resumen) <= MAX_RESUMEN and len(resumen) < len(limpio):
            return resumen
        logger.info("Resumen de objetivo descartado (%d caracteres)", len(resumen))
    except Exception as e:                 # sin modelo, tiempo agotado, JSON raro...: se recorta y listo
        logger.warning("No se pudo resumir el objetivo con el modelo: %s", e)
    return _recortar(limpio)
