# api/ejercicio_unico.py
"""Modo 2: generación de un ejercicio suelto y reprompt (corrección pedida por el entrenador)."""
import json
import logging

import requests

from config import MODEL, OLLAMA_URL
from ejercicios import cargar_ejercicios, construir_contexto_ejercicios, filtrar_ejercicios

logger = logging.getLogger(__name__)

# ── Modo 2: Ejercicio único ──────────────────────────────────────────────────

# SYSTEM_EJERCICIO importado de api/prompts.py


def generar_ejercicio_unico(edad: str, objetivo: str, descripcion: str = "") -> dict:
    """Modo 2: genera un único ejercicio con diagrama."""
    ctx = construir_contexto_ejercicios(
        filtrar_ejercicios(cargar_ejercicios(), edad, objetivo)
    )
    prompt = (
        f"Genera un ejercicio de baloncesto para la categoría {edad} con objetivo: {objetivo}.\n"
        + (f"Descripción adicional: {descripcion}\n" if descripcion else "")
        + f"\nEjercicios de referencia:\n{ctx}\n\n"
        "Devuelve SOLO el JSON del ejercicio (sin texto adicional):"
    )
    try:
        r = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model":  MODEL,
                "prompt": prompt,
                "format": "json",
                "think":  False,          # Qwen3: sin thinking para JSON estructurado
                "stream": False,
                "options": {"temperature": 0.4, "num_predict": 900, "top_k": 40},
            },
            timeout=120,
        )
        r.raise_for_status()
        ej = json.loads(r.json()["response"].strip())
        logger.info(f"Ejercicio generado: {ej.get('nombre', '?')}")
        return ej
    except Exception as e:
        logger.warning(f"Error generando ejercicio: {e}")
        return {}


def reprompt_ejercicio(edad: str, objetivo: str, nombre: str, descripcion: str, instruccion: str) -> dict:
    """Regenera un ejercicio ya existente aplicando una corrección pedida por el
    entrenador — mismo formato de salida que generar_ejercicio_unico (texto y
    diagrama en un único JSON), pero partiendo del ejercicio actual en vez de
    generar uno nuevo desde cero, para que el modelo sepa qué está corrigiendo."""
    ctx = construir_contexto_ejercicios(
        filtrar_ejercicios(cargar_ejercicios(), edad, objetivo)
    )
    # OJO: no usar etiquetas tipo "Nombre:"/"Descripción:" (mayúscula) para describir
    # el ejercicio actual — el modelo tiende a copiar ese estilo de mayúsculas/nombres
    # de campo en el JSON de salida en vez de usar el esquema real de la app (se
    # observó "Nombre"/"ORGANIZACIÓN"/"SECUENCIA" y ningún campo de diagrama en
    # absoluto). Por eso aquí se describe en minúscula y se especifica el esquema
    # de salida de forma explícita, con ejemplo, en vez de darlo por hecho.
    prompt = (
        f"Este ejercicio de baloncesto ya está generado para la categoría {edad}, "
        f"dentro de una sesión con objetivo general: {objetivo}.\n\n"
        f"ejercicio actual — nombre: {nombre}\n"
        f"ejercicio actual — descripción: {descripcion}\n\n"
        f"El entrenador pide este cambio sobre ESTE ejercicio: {instruccion}\n\n"
        "Genera la versión corregida del ejercicio aplicando ese cambio. Si el cambio "
        "pedido afecta solo al diagrama (jugadores, movimientos), mantén el resto del "
        "ejercicio igual y actualiza el diagrama acorde al cambio.\n\n"
        f"Ejercicios de referencia:\n{ctx}\n\n"
        "Devuelve SOLO un JSON con EXACTAMENTE estos campos (nombres en minúscula, "
        "sin inventar ni renombrar ninguno): \"nombre\" (string), \"descripcion\" "
        "(string, la organización del ejercicio en prosa), \"duracion_min\" (entero), "
        "\"puntos_clave\" (array de strings), y \"diagrama\" con esta forma exacta:\n"
        '{"tipo": "media_pista", "jugadores_ataque": [{"id": "A1", "rol": "atacante", '
        '"x": 50, "y": 65}], "jugadores_defensa": [{"id": "D1", "rol": "defensor", '
        '"x": 50, "y": 45}], "balon_inicio": {"portador": "A1"}, "movimientos": '
        '[{"de": "A1", "tipo": "tiro", "orden": 1}], "conos": []}\n'
        "(coordenadas x/y de 0 a 100; ajusta jugadores/movimientos al ejercicio real, "
        "el ejemplo es solo para mostrar la forma del JSON). "
        "No devuelvas ningún otro campo ni cambies mayúsculas/minúsculas de estos nombres:"
    )
    try:
        r = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model":  MODEL,
                "prompt": prompt,
                "format": "json",
                "think":  False,          # Qwen3: sin thinking para JSON estructurado
                "stream": False,
                "options": {"temperature": 0.4, "num_predict": 900, "top_k": 40},
            },
            timeout=120,
        )
        r.raise_for_status()
        ej = json.loads(r.json()["response"].strip())
        logger.info(f"Ejercicio corregido: {ej.get('nombre', '?')}")
        return ej
    except Exception as e:
        logger.warning(f"Error corrigiendo ejercicio: {e}")
        return {}
