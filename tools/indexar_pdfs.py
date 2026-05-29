#!/usr/bin/env python3
"""
Indexa en ChromaDB todos los documentos de conocimiento para el RAG.

Lee:
  - PDFs de data/pdfs/coleccion_teoria/, coleccion_reglamento/ y coleccion_planificacion/
  - Documentos .md de data/teoria/  (teoría elaborada, puede ser de PDFs procesados o escrita a mano)

La colección resultante ("teoria_baloncesto") es la que usa rag_engine.py
para dar contexto al modelo en tiempo real.

Uso:
  docker exec -it mipizarra-api python /app/tools/indexar_pdfs.py
  python tools/indexar_pdfs.py  (en local apuntando a Ollama del servidor)
"""
import logging
import os
from pathlib import Path

from llama_index.core import Document, Settings, StorageContext, VectorStoreIndex
from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore
import chromadb

try:
    from llama_index.readers.file import PDFReader
    _PDF_READER = PDFReader(return_full_document=False)
except Exception:
    _PDF_READER = None

PDFS_DIR      = Path(os.environ.get("PDFS_DIR",      "/app/data/pdfs"))
TEORIA_DIR    = Path(os.environ.get("TEORIA_DIR",    "/app/data/teoria"))
CHROMA_DB_DIR = Path(os.environ.get("CHROMA_DB_DIR", "/app/data/chroma_db"))
COLLECTION    = "teoria_baloncesto"
CHUNK_SIZE    = 1024
OLLAMA_URL    = os.environ.get("OLLAMA_URL", "http://ollama:11434")
EMBED_MODEL   = "nomic-embed-text"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


# ── Cargadores ────────────────────────────────────────────────────────────────

def _cargar_pdf(path: Path) -> list[Document]:
    if _PDF_READER is None:
        log.warning(f"PDFReader no disponible, omitiendo {path.name}")
        return []
    try:
        docs = _PDF_READER.load_data(file=path)
        for d in docs:
            d.metadata.setdefault("source", path.name)
            d.metadata["tipo"] = "pdf"
        return docs
    except Exception as e:
        log.error(f"Error leyendo PDF {path.name}: {e}")
        return []


def _cargar_md(path: Path) -> list[Document]:
    try:
        texto = path.read_text(encoding="utf-8").strip()
        if not texto:
            return []
        return [Document(
            text=texto,
            metadata={"source": path.name, "tipo": "teoria_md"},
        )]
    except Exception as e:
        log.error(f"Error leyendo {path.name}: {e}")
        return []


# ── Main ──────────────────────────────────────────────────────────────────────

def indexar():
    log.info("Iniciando indexado de conocimiento para RAG")

    Settings.embed_model = OllamaEmbedding(
        model_name=EMBED_MODEL, base_url=OLLAMA_URL
    )

    documentos: list[Document] = []

    # 1. PDFs de las colecciones (teoria, reglamento, planificacion)
    colecciones_pdf = [
        PDFS_DIR / "coleccion_teoria",
        PDFS_DIR / "coleccion_reglamento",
        PDFS_DIR / "coleccion_planificacion",
    ]
    for col in colecciones_pdf:
        if not col.exists():
            continue
        pdfs = list(col.glob("**/*.pdf"))
        log.info(f"  {col.name}: {len(pdfs)} PDFs")
        for p in pdfs:
            documentos.extend(_cargar_pdf(p))

    # 2. Documentos .md de data/teoria/
    if TEORIA_DIR.exists():
        mds = list(TEORIA_DIR.glob("*.md"))
        log.info(f"  teoria/*.md: {len(mds)} ficheros")
        for m in mds:
            documentos.extend(_cargar_md(m))
    else:
        log.warning(f"Carpeta {TEORIA_DIR} no encontrada")

    if not documentos:
        log.error("No se encontraron documentos. Comprueba las rutas.")
        return

    log.info(f"Total documentos cargados: {len(documentos)}")

    # 3. ChromaDB
    chroma_client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))
    col = chroma_client.get_or_create_collection(COLLECTION)
    vector_store = ChromaVectorStore(col)
    storage_ctx = StorageContext.from_defaults(vector_store=vector_store)

    # 4. Pipeline de ingesta
    pipeline = IngestionPipeline(
        transformations=[SentenceSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=50)],
        disable_cache=True,
    )
    nodes = pipeline.run(documents=documentos, show_progress=True)
    log.info(f"Nodos generados: {len(nodes)}")

    VectorStoreIndex(nodes, storage_context=storage_ctx, show_progress=True)
    log.info("Indexado completado. ChromaDB actualizado.")


if __name__ == "__main__":
    indexar()
