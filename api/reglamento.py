# api/reglamento.py
"""Modo 3: dudas de reglamento y fundamentos técnicos, por ámbito (general o comunidad autónoma)."""
import logging
import re

import requests

from config import AMBITO_GENERAL, MODEL_REGLAMENTO, MODEL_SESION, OLLAMA_URL
from contexto import consultar_coleccion, nombre_ambito, normalizar_ambito
from prompts import SYSTEM_REGLAMENTO

logger = logging.getLogger(__name__)

# ── Modo 3: Reglamento y dudas técnicas ─────────────────────────────────────

# SYSTEM_REGLAMENTO importado de api/prompts.py


# Vocabulario de la calle → vocabulario del reglamento. La búsqueda por significado se desorienta con «cuartos» o
# «niños» cuando el texto dice «periodos» y «jugadores»: se añaden los términos del reglamento a la consulta
# (solo a la que se busca; el modelo recibe la pregunta tal como se escribió).
_SINONIMOS_REGLAMENTO = (
    (r"\bcuartos?\b|\bparte[s]? del partido\b", "periodos"),
    (r"\bni[ñn]os?\b|\bni[ñn]as?\b|\bcr[ií]os?\b|\bchavales?\b|\bchic[oa]s?\b|\bpeques?\b|\bcrios?\b", "jugadores"),
    (r"\bbenjam[ií]n(?:es)?\b|\balev[ií]n(?:es)?\b|\bmini\b|\bminibasqu?et\b|\bminibasket\b|\bu-?(?:10|12)\b",
     "minibasket benjamín alevín"),
    (r"\bminutos? (?:jugados?|de juego)\b|\btiempo de juego\b|\bjuegan?\b|\bjugar\b|\bjugad[oa]s?\b|\bparticip\w+\b",
     "participación mínima periodos"),
    (r"\bcambios?\b|\bsustituci\w+\b", "sustituciones cambios"),
    (r"\bfaltas?\b", "faltas personales"),
)


def consulta_ampliada(pregunta: str) -> str:
    """La pregunta más los términos del reglamento que equivalen a lo que se ha escrito, sin repetir."""
    texto = pregunta.lower()
    extra: list[str] = []
    for patron, termino in _SINONIMOS_REGLAMENTO:
        if re.search(patron, texto) and termino not in extra:
            extra.append(termino)
    return f"{pregunta} {' '.join(extra)}".strip() if extra else pregunta


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
    consulta = consulta_ampliada(pregunta)      # solo para buscar; al modelo le llega la pregunta original

    # Presupuesto de caracteres POR COLECCIÓN, no un recorte sobre la suma: los fragmentos del .md
    # curado van primero y, si se recortaba el conjunto, los PDF (donde a veces está el dato)
    # nunca llegaban al modelo. Del .md curado se piden más fragmentos porque es la colección más
    # fiable y el fragmento correcto no siempre queda entre los tres primeros. Los PDF, sin curar, pesan
    # poco: con 4 fragmentos de PDF el modelo contestaba con cifras de una tabla ajena (31/35 aciertos en
    # 7 preguntas x 5 repeticiones); con 2 y el .md como base, 35/35.
    contexto_ccaa = ""
    if especifico:
        contexto_ccaa = "\n".join(filter(None, [
            consultar_coleccion("reglamento_md", consulta, n_resultados=6, where=filtro_ccaa)[:2800],
            consultar_coleccion("reglamento", consulta, n_resultados=3, where=filtro_ccaa)[:800],
        ]))
    contexto_general = "\n".join(filter(None, [
        consultar_coleccion("reglamento_md", consulta, n_resultados=6, where=filtro_general)[:3600],
        consultar_coleccion("reglamento", consulta, n_resultados=2, where=filtro_general)[:700],
    ]))
    contexto_curado = consultar_coleccion("teoria_md", consulta, n_resultados=2)

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
            f"Si no hay norma específica de {nombre} sobre el asunto, dilo brevemente y aplica la general. "
            f"Las reglas de juego que no dependen de la comunidad (violaciones, faltas, tiempos, material, "
            f"señales) se responden con el reglamento general de FIBA y de la federación española como en "
            f"cualquier otra consulta: no hace falta que {nombre} las regule para contestarlas.\n"
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
    # Ollama falla a veces al cargar gemma4 (el proceso muere y devuelve 500 a los ~35 s) y a la segunda carga
    # funciona: se reintenta una vez con el mismo modelo y, si sigue fallando, responde el modelo de sesión
    # (más pequeño, menos preciso en reglamento) avisándolo, antes que dar un error.
    modelos = [MODEL_REGLAMENTO, MODEL_REGLAMENTO]
    if MODEL_SESION != MODEL_REGLAMENTO:
        modelos.append(MODEL_SESION)
    for intento, modelo in enumerate(modelos, start=1):
        try:
            texto = _chat_reglamento(modelo, mensaje_usuario)
        except Exception as e:
            logger.warning(f"Error en reglamento (intento {intento}, {modelo}): {e}")
            continue
        if modelo != MODEL_REGLAMENTO:
            texto += ("\n\n*(Respuesta generada con el modelo reducido porque el principal no respondió: "
                      "contrástala con el reglamento.)*")
        return texto
    return "No se pudo responder la consulta. Inténtalo de nuevo."


def _chat_reglamento(modelo: str, mensaje_usuario: str) -> str:
    r = requests.post(
        f"{OLLAMA_URL}/api/chat",
        json={
            "model": modelo,
            "messages": [
                {"role": "system", "content": SYSTEM_REGLAMENTO},
                {"role": "user", "content": mensaje_usuario},
            ],
            "stream": False,
            "think": False,    # modelos con razonamiento por defecto no deben gastar el presupuesto pensando
            "keep_alive": "30m",   # tras un rato inactivo, cargar el modelo en la GPU tarda 35-100 s: se mantiene cargado
            "options": {"temperature": 0.3, "num_predict": 500, "num_ctx": 6144},
        },
        timeout=180,
    )
    r.raise_for_status()
    return r.json()["message"]["content"].strip()
