#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Indexa PDFs organizados en subcarpetas dentro de /app/data/pdfs/
Cada subcarpeta se convierte en una colección separada en ChromaDB.
"""
import os
import time
import logging
import uuid
from pathlib import Path

from llama_index.core import Settings
from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.node_parser import SentenceSplitter
from llama_index.readers.file import PDFReader
from llama_index.embeddings.ollama import OllamaEmbedding
import chromadb

# --- CONFIGURACIÓN ---
PDFS_BASE_DIR = "/app/data/pdfs"
CHROMA_DB_DIR = "/app/data/chroma_db"
EMBED_MODEL   = "nomic-embed-text"
OLLAMA_URL    = "http://ollama:11434"
CHUNK_SIZE    = 256
CHUNK_OVERLAP = 20
MAX_CHARS     = 6000 * 4          # ~6000 tokens × 4 chars/token
# ---------------------

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)

Settings.embed_model = OllamaEmbedding(model_name=EMBED_MODEL, base_url=OLLAMA_URL)


def texto_util(texto: str) -> str | None:
    """Devuelve el texto limpio o None si está vacío/basura."""
    limpio = texto.strip()
    if len(limpio) < 20:          # menos de 20 chars → no sirve para embedding
        return None
    return limpio[:MAX_CHARS]     # truncar si es muy largo


def generar_embeddings_seguros(nodos: list) -> list:
    """
    Genera embeddings uno a uno.
    Descarta nodos con texto vacío O con embedding vacío/None.
    """
    embed_model = Settings.embed_model
    validos = []
    omitidos = 0
    total = len(nodos)

    for i, node in enumerate(nodos):
        texto = texto_util(node.text)

        # 1. Texto inútil → descartar sin llamar al modelo
        if texto is None:
            omitidos += 1
            continue

        # 2. Llamar al modelo y validar resultado
        try:
            embedding = embed_model.get_text_embedding(texto)
        except Exception as e:
            logger.warning(f"   ⚠️ Excepción en nodo {i+1}/{total}: {e}")
            omitidos += 1
            continue

        # 3. Validar que el embedding no esté vacío
        if not embedding or len(embedding) == 0:
            logger.warning(f"   ⚠️ Embedding vacío en nodo {i+1}/{total}, se omite.")
            omitidos += 1
            continue

        node.text      = texto       # guardar versión truncada/limpia
        node.embedding = embedding
        validos.append(node)

        if (i + 1) % 50 == 0:
            logger.info(f"   🔄 {i+1}/{total} procesados, {len(validos)} válidos...")

    logger.info(f"   ✅ {len(validos)} válidos | {omitidos} omitidos de {total}")
    return validos


def insertar_en_chroma(chroma_collection, nodos: list):
    """
    Inserta directamente en ChromaDB sin pasar por LlamaIndex.
    Así evitamos que insert_nodes revalide embeddings internamente.
    """
    ids        = []
    embeddings = []
    documents  = []
    metadatas  = []

    for node in nodos:
        ids.append(str(uuid.uuid4()))
        embeddings.append(node.embedding)
        documents.append(node.text)
        # metadata solo con tipos primitivos (ChromaDB no acepta listas)
        meta = {k: str(v) for k, v in node.metadata.items()}
        metadatas.append(meta)

    # ChromaDB acepta lotes de hasta 5000; dividir por si acaso
    batch = 500
    for start in range(0, len(ids), batch):
        end = start + batch
        chroma_collection.add(
            ids        = ids[start:end],
            embeddings = embeddings[start:end],
            documents  = documents[start:end],
            metadatas  = metadatas[start:end],
        )
        logger.info(f"   💾 Insertados {min(end, len(ids))}/{len(ids)} nodos...")


def indexar_coleccion(nombre: str, ruta_pdfs: str):
    logger.info(f"\n📂 Colección '{nombre}' ← {ruta_pdfs}")

    pdf_files = list(Path(ruta_pdfs).glob("*.pdf"))
    if not pdf_files:
        logger.warning(f"   ⚠️ Sin PDFs en {ruta_pdfs}")
        return

    # Leer PDFs
    reader    = PDFReader(return_full_document=False)
    documentos = []
    for pdf in pdf_files:
        try:
            docs = reader.load_data(file=pdf)
            for d in docs:
                d.metadata["fuente"]    = pdf.name
                d.metadata["coleccion"] = nombre
            documentos.extend(docs)
            logger.info(f"   📄 {pdf.name} ({len(docs)} páginas)")
        except Exception as e:
            logger.error(f"   ❌ {pdf.name}: {e}")

    if not documentos:
        logger.warning("   ⚠️ Ningún documento procesable.")
        return

    # Dividir en chunks
    pipeline = IngestionPipeline(
        transformations=[SentenceSplitter(chunk_size=CHUNK_SIZE,
                                          chunk_overlap=CHUNK_OVERLAP)],
        disable_cache=True,
    )
    t0    = time.time()
    nodos = pipeline.run(documents=documentos, show_progress=True)
    logger.info(f"   ✂️  {len(nodos)} chunks en {time.time()-t0:.1f}s")

    # Embeddings con validación estricta
    nodos_validos = generar_embeddings_seguros(nodos)
    if not nodos_validos:
        logger.error("   ❌ Sin nodos válidos, abortando esta colección.")
        return

    # ChromaDB: borrar colección existente y crear nueva
    client = chromadb.PersistentClient(path=CHROMA_DB_DIR)
    try:
        client.delete_collection(nombre)
        logger.info(f"   🗑️  Colección anterior eliminada.")
    except Exception:
        pass
    coleccion = client.create_collection(nombre)

    # Insertar directamente (sin LlamaIndex en este paso)
    insertar_en_chroma(coleccion, nodos_validos)
    logger.info(f"   🎉 '{nombre}' indexada: {len(nodos_validos)} nodos.")


if __name__ == "__main__":
    colecciones = {
        "teoria":        os.path.join(PDFS_BASE_DIR, "coleccion_teoria"),
        "planificacion": os.path.join(PDFS_BASE_DIR, "coleccion_planificacion"),
        "reglamento":    os.path.join(PDFS_BASE_DIR, "coleccion_reglamento"),
    }

    for nombre, ruta in colecciones.items():
        if os.path.isdir(ruta):
            indexar_coleccion(nombre, ruta)
        else:
            logger.warning(f"⚠️ {ruta} no existe, se omite.")

    logger.info("\n🏁 Indexado completo.")
