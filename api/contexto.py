# api/contexto.py
"""Recuperación de contexto (RAG): ámbitos de reglamento y consulta a las colecciones de ChromaDB."""
import logging
from pathlib import Path

import chromadb
from llama_index.embeddings.ollama import OllamaEmbedding

from config import (
    AMBITO_GENERAL, CHROMA_DB_DIR, EMBED_MODEL, NOMBRES_AMBITO, OLLAMA_URL, REGLAMENTO_DIR, _AMBITO_RE,
)

logger = logging.getLogger(__name__)

# Inicialización única al arrancar el módulo
_embed_model = OllamaEmbedding(model_name=EMBED_MODEL, base_url=OLLAMA_URL)
_chroma      = chromadb.PersistentClient(path=CHROMA_DB_DIR)


# ─── Ámbitos de reglamento ───────────────────────────────────────────────
def nombre_ambito(ambito: str) -> str:
    return NOMBRES_AMBITO.get(ambito) or ambito.replace("_", " ").title()


def listar_ambitos() -> list[dict]:
    """Ámbitos disponibles: siempre "general" y una entrada por cada carpeta de
    data/reglamento/ con al menos un .md. Añadir una comunidad es crear su carpeta."""
    ids = [AMBITO_GENERAL]
    try:
        for d in sorted(Path(REGLAMENTO_DIR).iterdir()):
            if (d.is_dir() and d.name != AMBITO_GENERAL and _AMBITO_RE.match(d.name)
                    and any(d.glob("*.md"))):
                ids.append(d.name)
    except OSError:
        pass
    return [{"id": i, "nombre": nombre_ambito(i)} for i in ids]


def normalizar_ambito(ambito) -> str:
    """Devuelve un ámbito válido; cualquier valor desconocido cae en "general"."""
    if not ambito:
        return AMBITO_GENERAL
    candidato = str(ambito).strip().lower()
    return candidato if candidato in {a["id"] for a in listar_ambitos()} else AMBITO_GENERAL


# ─── ChromaDB / PDFs ─────────────────────────────────────────────────────
def consultar_coleccion(nombre: str, consulta: str, n_resultados: int = 4, where: dict | None = None) -> str:
    try:
        coleccion = _chroma.get_collection(nombre)
    except Exception:
        return ""

    if coleccion.count() == 0:
        return ""

    try:
        embedding  = _embed_model.get_text_embedding(consulta)
        kwargs = dict(
            query_embeddings=[embedding],
            n_results=min(n_resultados, coleccion.count()),
            include=["documents", "metadatas"],
        )
        if where:
            kwargs["where"] = where
        resultados = coleccion.query(**kwargs)
        fragmentos = resultados.get("documents", [[]])[0]
        # Sin etiqueta de origen: el modelo no debe poder citar documentos concretos.
        lineas = [texto.strip() for texto in fragmentos]
        return "\n".join(lineas)

    except Exception as e:
        logger.warning(f"Error consultando coleccion '{nombre}': {e}")
        return ""


def construir_contexto_teoria(objetivo: str, edad: str, presupuesto_por_coleccion: int = 900) -> str:
    """Presupuesto de caracteres POR COLECCIÓN, no un truncado global al final: antes
    se concatenaban teoria+planificacion+reglamento y se cortaba a 800 caracteres en
    el prompt, así que planificacion y reglamento (los últimos en concatenarse) nunca
    llegaban a sobrevivir el corte — en la práctica solo teoria influía en la sesión.
    "teoria_md" (los 20 .md escritos a propósito) va primero y con más presupuesto:
    antes competían en la misma colección que "teoria" contra PDFs de cientos de KB
    y casi nunca ganaban la búsqueda de vecinos más cercanos."""
    consulta = f"entrenamiento baloncesto {objetivo} categoria {edad}"
    partes   = []
    mapeo    = {
        "teoria_md":     ("MATERIAL PROPIO (prioritario)", int(presupuesto_por_coleccion * 1.5), None),
        "teoria":        ("TEORIA Y METODOLOGIA",           presupuesto_por_coleccion, None),
        "planificacion": ("PLANIFICACION",                  presupuesto_por_coleccion, None),
        "reglamento_md": ("REGLAMENTO",                     presupuesto_por_coleccion, {"ambito": AMBITO_GENERAL}),
    }
    for nombre, (etiqueta, presupuesto, filtro) in mapeo.items():
        fragmento = consultar_coleccion(nombre, consulta, n_resultados=4, where=filtro)
        if fragmento:
            partes.append(f"--- {etiqueta} ---\n{fragmento[:presupuesto]}")

    return "\n\n".join(partes) if partes else ""
