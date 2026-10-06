#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Indexa los documentos propios (.md) en ChromaDB: teoría (data/teoria) y reglamento por ámbito
(data/reglamento/<ámbito>). Cada grupo es una colección.

Los PDF de terceros están aislados del sistema: este indexador no sabe leerlos y, al ejecutarse, elimina de la
base las colecciones que antes se construían con ellos.
"""
import os
import time
import logging
import uuid
from pathlib import Path

from llama_index.core import Settings
from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.ollama import OllamaEmbedding
import chromadb
import sys

# modelo_indice.py vive en api/ (en el contenedor, api/ es /app y tools/ es /app/tools)
for _base in (Path(__file__).resolve().parent.parent / "api", Path(__file__).resolve().parent.parent):
    if (_base / "modelo_indice.py").exists():
        sys.path.insert(0, str(_base))
        break
from colecciones import COLECCIONES_PDF, colecciones_a_indexar
from modelo_indice import escribir_marca

# --- CONFIGURACIÓN ---
BASE_DIR      = Path(__file__).resolve().parent.parent / "data"
TEORIA_MD_DIR = Path(os.environ.get("TEORIA_MD_DIR", "/app/data/teoria" if os.path.exists("/app/data/teoria") else str(BASE_DIR / "teoria")))
REGLAMENTO_DIR = Path(os.environ.get("REGLAMENTO_DIR", "/app/data/reglamento" if os.path.exists("/app/data/reglamento") else str(BASE_DIR / "reglamento")))
CHROMA_DB_DIR = os.environ.get("CHROMA_DB_DIR", "/app/data/chroma_db" if os.path.exists("/app/data") else str(BASE_DIR / "chroma_db"))
EMBED_MODEL   = os.environ.get("EMBED_MODEL", "qwen3-embedding:0.6b")
OLLAMA_URL    = os.environ.get("OLLAMA_URL", "http://ollama:11434")
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


def indexar_coleccion(nombre: str, rutas: list):
    """`rutas` admite Path o (Path, ambito): con ámbito, cada documento lleva ese dato en
    su metadato, para filtrar por comunidad autónoma al consultar el reglamento."""
    logger.info(f"\n📂 Colección '{nombre}' ← {[str(r) for r in rutas]}")

    documentos = []

    for ruta in rutas:
        ambito = None
        if isinstance(ruta, tuple):
            ruta, ambito = ruta
        if not ruta.exists():
            continue

        # Leer archivos Markdown (.md): los documentos propios
        md_files = list(ruta.glob("*.md"))
        if md_files:
            for md in md_files:
                try:
                    texto = md.read_text(encoding="utf-8").strip()
                    if texto:
                        from llama_index.core import Document
                        doc = Document(
                            text=texto,
                            metadata={
                                "documento": md.name,
                                "coleccion": nombre,
                                "tipo": "markdown",
                                **({"ambito": ambito} if ambito else {}),
                            }
                        )
                        documentos.append(doc)
                        logger.info(f"   📝 [MD] {md.name} ({len(texto)} caracteres)")
                except Exception as e:
                    logger.error(f"   ❌ {md.name}: {e}")

    if not documentos:
        logger.warning(f"   ⚠️ Ningún documento procesable para colección '{nombre}'.")
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

    # Insertar directamente
    insertar_en_chroma(coleccion, nodos_validos)
    logger.info(f"   🎉 '{nombre}' indexada: {len(nodos_validos)} nodos.")


if __name__ == "__main__":
    # Reglamento por ámbito: los .md viven en data/reglamento/<ámbito>/ ("general" = FIBA y federación
    # española; una carpeta por comunidad autónoma).
    def _subcarpetas(base: Path) -> list:
        return sorted(d for d in base.iterdir() if d.is_dir()) if base.exists() else []

    colecciones = {
        "teoria_md":     [TEORIA_MD_DIR],
        "reglamento_md": [(d, d.name) for d in _subcarpetas(REGLAMENTO_DIR)],
    }

    # Los PDF de terceros están aislados: se eliminan de la base las colecciones que se hubieran construido con ellos.
    cliente = chromadb.PersistentClient(path=CHROMA_DB_DIR)
    for nombre in sorted(COLECCIONES_PDF):
        try:
            cliente.delete_collection(nombre)
            logger.info(f"🗑️  Colección '{nombre}' eliminada (antes se construía con PDF de terceros).")
        except Exception:
            pass

    for nombre, rutas in colecciones_a_indexar(colecciones).items():
        indexar_coleccion(nombre, rutas)

    escribir_marca(CHROMA_DB_DIR, EMBED_MODEL)       # la API avisa si consulta con otro modelo
    logger.info("\n🏁 Indexado completo.")
