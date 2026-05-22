# tools/indexar_pdfs.py
import os
import time
import logging
from pathlib import Path

# LlamaIndex Core
from llama_index.core import (
    VectorStoreIndex, StorageContext, Settings
)
from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.node_parser import SentenceSplitter

# Lectura de PDFs y Embeddings
from llama_index.readers.file import PDFReader
from llama_index.embeddings.ollama import OllamaEmbedding

# Base de Datos Vectorial
from llama_index.vector_stores.chroma import ChromaVectorStore
import chromadb

# --- CONFIGURACIÓN (AJUSTA ESTAS RUTAS) ---
# Directorio donde están tus PDFs (teoría, planificación, etc.)
PDFS_DIR = "/app/data/pdfs"
# Directorio donde ChromaDB guardará los datos (dentro del volumen de datos)
CHROMA_DB_DIR = "/app/data/chroma_db"
# Nombre de la colección dentro de ChromaDB
COLLECTION_NAME = "teoria_baloncesto"
# Tamaño de los "trozos" de texto en los que se dividirán los PDFs
CHUNK_SIZE = 1024
# Número de núcleos a usar para el paralelismo. Usamos `None` para que detecte todos.
NUM_WORKERS = os.cpu_count()
# Modelo de Ollama para los embeddings (¡no es el LLM!)
EMBED_MODEL = "nomic-embed-text"
# URL de tu servidor Ollama
OLLAMA_URL = "http://ollama:11434"
# -------------------------------------------

# Configurar logging para ver qué está pasando
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def indexar_pdfs_con_metadatos():
    # ...
    all_documents = []
    pdf_files = list(Path(PDFS_DIR).rglob("*.pdf")) # rglob busca en subcarpetas
    
    for file_path in pdf_files:
        # 1. Extraer la categoría de la carpeta padre
        categoria = file_path.parent.name 
        
        # 2. Cargar el documento
        docs = reader.load_data(file=file_path)
        
        # 3. Añadir el metadato a cada "nodo" de texto
        for doc in docs:
            doc.metadata["categoria"] = categoria
            doc.metadata["fuente"] = file_path.name
            
        all_documents.extend(docs)
        
def indexar_pdfs():
    # 1. Preparar el modelo de embeddings y el lector de PDFs
    logger.info(f"🚀 Iniciando indexado de PDFs en '{PDFS_DIR}'")
    logger.info(f"🧠 Usando {NUM_WORKERS} núcleos para el procesamiento en paralelo")
    logger.info(f"🔢 Usando el modelo de embeddings: {EMBED_MODEL}")

    # Configurar el modelo de embeddings global para LlamaIndex
    Settings.embed_model = OllamaEmbedding(
        model_name=EMBED_MODEL,
        base_url=OLLAMA_URL,
    )

    # 2. Cargar todos los documentos PDF
    #    Usamos un extractor de PDFs y los cargamos en paralelo
    reader = PDFReader(return_full_document=False)
    all_documents = []
    pdf_files = list(Path(PDFS_DIR).glob("*.pdf"))
    
    if not pdf_files:
        logger.error(f"❌ No se encontraron archivos PDF en '{PDFS_DIR}'")
        return

    logger.info(f"📚 Encontrados {len(pdf_files)} archivos PDF. Cargando...")
    # SimpleDirectoryReader no expone num_workers, pero podemos cargarlos con un pool
    from multiprocessing import Pool
    def load_pdf(file_path):
        try:
            return reader.load_data(file=file_path)
        except Exception as e:
            logger.error(f"Error cargando {file_path}: {e}")
            return []
    
    with Pool(processes=NUM_WORKERS) as pool:
        docs_nested = pool.map(load_pdf, pdf_files)
    for doc_list in docs_nested:
        all_documents.extend(doc_list)
    
    logger.info(f"✅ Carga completada. {len(all_documents)} páginas/documentos extraídos.")

    # 3. Configurar ChromaDB como nuestro almacén de vectores
    logger.info(f"💾 Conectando a ChromaDB en '{CHROMA_DB_DIR}'...")
    chroma_client = chromadb.PersistentClient(path=CHROMA_DB_DIR)
    chroma_collection = chroma_client.get_or_create_collection(COLLECTION_NAME)
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    # 4. Crear y ejecutar el pipeline de ingesta en paralelo
    logger.info("⚙️ Creando pipeline de ingesta en paralelo...")
    pipeline = IngestionPipeline(
        transformations=[
            # Divide los documentos en trozos manejables
            SentenceSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=50),
            # El modelo de embeddings se toma de Settings
        ],
        # Desactivar la caché para evitar problemas con el paralelismo
        disable_cache=True,
    )

    logger.info(f"⏳ Procesando documentos con {NUM_WORKERS} workers...")
    start_time = time.time()
    # Aquí es donde ocurre la magia del paralelismo
    nodes = pipeline.run(
        documents=all_documents,
        num_workers=NUM_WORKERS,
        show_progress=True
    )
    elapsed = time.time() - start_time
    logger.info(f"✅ Procesamiento completado en {elapsed:.2f} segundos. Se generaron {len(nodes)} nodos.")

    # 5. Construir el índice y guardarlo en ChromaDB
    logger.info("🗂️ Construyendo y guardando el índice en ChromaDB...")
    VectorStoreIndex(
        nodes,
        storage_context=storage_context,
        show_progress=True
    )
    logger.info("🎉 ¡Indexado completado con éxito!")
    
    # 6. (Opcional) Probar una consulta rápida
    logger.info("🔍 Probando una consulta rápida...")
    index = VectorStoreIndex.from_vector_store(
        vector_store,
        embed_model=Settings.embed_model
    )
    query_engine = index.as_query_engine(similarity_top_k=2)
    response = query_engine.query("¿Cuáles son los principios de la defensa en zona?")
    logger.info(f"📝 Respuesta de prueba: {response.response[:200]}...")


if __name__ == "__main__":
    indexar_pdfs()
