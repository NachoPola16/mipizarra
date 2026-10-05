# api/reglamento.py
"""Modo 3: dudas de reglamento y fundamentos técnicos, por ámbito (general o comunidad autónoma)."""
import logging

import requests

from config import AMBITO_GENERAL, MODEL_SESION, OLLAMA_URL
from contexto import consultar_coleccion, nombre_ambito, normalizar_ambito
from prompts import SYSTEM_REGLAMENTO

logger = logging.getLogger(__name__)

# ── Modo 3: Reglamento y dudas técnicas ─────────────────────────────────────

# SYSTEM_REGLAMENTO importado de api/prompts.py


def responder_duda_reglamento(pregunta: str, ambito: str = AMBITO_GENERAL) -> str:
    """Modo 3: responde una duda de reglamento o fundamento técnico.

    `ambito` es "general" (FIBA / federación española) o una comunidad autónoma
    (carpeta de data/reglamento/). Con una comunidad se recupera primero su normativa
    y se completa con la general: la específica prevalece cuando ambas difieren.

    Capas de recuperación: "reglamento_md" (los .md curados, por ámbito, siempre
    disponibles), "reglamento" (PDF oficiales locales, opcionales; mismo filtro por
    ámbito) y "teoria_md" (fundamentos técnicos). Todo sin etiqueta de origen."""
    ambito = normalizar_ambito(ambito)
    especifico = ambito != AMBITO_GENERAL
    nombre = nombre_ambito(ambito)
    filtro_general = {"ambito": AMBITO_GENERAL}
    filtro_ccaa = {"ambito": ambito}

    # Presupuesto de caracteres POR COLECCIÓN, no un recorte sobre la suma: los fragmentos del .md
    # curado van primero y, si se recortaba el conjunto, los PDF (donde a veces está el dato)
    # nunca llegaban al modelo. Del .md curado se piden más fragmentos porque es la colección más
    # fiable y el fragmento correcto no siempre queda entre los tres primeros.
    contexto_ccaa = ""
    if especifico:
        contexto_ccaa = "\n".join(filter(None, [
            consultar_coleccion("reglamento_md", pregunta, n_resultados=6, where=filtro_ccaa)[:1600],
            consultar_coleccion("reglamento", pregunta, n_resultados=3, where=filtro_ccaa)[:800],
        ]))
    contexto_general = "\n".join(filter(None, [
        consultar_coleccion("reglamento_md", pregunta, n_resultados=8, where=filtro_general)[:4800],
        consultar_coleccion("reglamento", pregunta, n_resultados=4, where=filtro_general)[:1400],
    ]))
    contexto_curado = consultar_coleccion("teoria_md", pregunta, n_resultados=2)

    partes = []
    if contexto_ccaa:
        partes.append(f"--- NORMATIVA DE {nombre.upper()} (prevalece sobre la general) ---\n{contexto_ccaa}")
    if contexto_general:
        partes.append(f"--- REGLAMENTO GENERAL (FIBA / federación española) ---\n{contexto_general}")
    if contexto_curado:
        partes.append(f"--- MATERIAL PROPIO ---\n{contexto_curado[:1000]}")

    if especifico:
        instruccion_ambito = (
            f"ÁMBITO DE LA CONSULTA: {nombre}. Responde con la normativa de {nombre} cuando exista y "
            f"complétala con el reglamento general; si ambas difieren, indica cuál se aplica en {nombre}. "
            f"Si no hay norma específica de {nombre} sobre el asunto, dilo y aplica la general.\n"
        )
    else:
        instruccion_ambito = (
            "ÁMBITO DE LA CONSULTA: general (FIBA y federación española). No apliques normas de una "
            "comunidad autónoma concreta; si la respuesta puede variar por comunidad, avísalo.\n"
        )

    mensaje_usuario = f"{instruccion_ambito}\nPREGUNTA: {pregunta}"
    if partes:
        mensaje_usuario = (
            f"{instruccion_ambito}\n"
            f"EXTRACTOS DE REGLAMENTO (pueden no cubrir toda la pregunta; si no "
            f"encuentras la respuesta aquí, usa tu conocimiento pero dilo):\n"
            f"{chr(10).join(partes)}\n\nPREGUNTA: {pregunta}"
        )
    try:
        r = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": MODEL_SESION,
                "messages": [
                    {"role": "system", "content": SYSTEM_REGLAMENTO},
                    {"role": "user", "content": mensaje_usuario},
                ],
                "stream": False,
                "think": False,    # modelos con razonamiento por defecto no deben gastar el presupuesto pensando
                "options": {"temperature": 0.3, "num_predict": 500, "num_ctx": 6144},
            },
            timeout=90,
        )
        r.raise_for_status()
        return r.json()["message"]["content"].strip()
    except Exception as e:
        logger.warning(f"Error en reglamento: {e}")
        return "No se pudo responder la consulta. Inténtalo de nuevo."
