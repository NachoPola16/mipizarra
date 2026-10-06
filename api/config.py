# api/config.py
"""Configuración común de la API: variables de entorno, modelos y ámbitos de reglamento."""
import os
import re

# Mapeo de códigos UXX a nombres de categorías
EDAD_A_CATEGORIA = {
    "U8": "Prebenjamín",
    "U10": "Benjamín",
    "U12": "Alevín",
    "U14": "Infantil",
    "U16": "Cadete",
    "U18": "Junior",
    "U20": "Senior",
    "Senior": "Senior"
}

OLLAMA_URL     = os.environ.get("OLLAMA_URL", "http://ollama:11434")
# qwen3:4b (con thinking) filtra razonamiento en inglés dentro del propio texto (no
# solo como preámbulo) y el parámetro "think": False no lo evita de forma fiable.
# Esto afecta igual al texto libre (generar_sesion, reglamento) y al JSON de diagramas:
# bajo restricción de formato el modelo con thinking degrada y devuelve diagramas
# vacíos o inventados. La variante -instruct no tiene modo thinking, así que no puede
# colarse ningún razonamiento por ninguna de las dos rutas.
MODEL          = os.environ.get("OLLAMA_MODEL", "qwen3:4b-instruct")
MODEL_SESION   = os.environ.get("OLLAMA_MODEL_SESION", os.environ.get("OLLAMA_MODEL", "qwen3:4b-instruct"))
# El modo reglamento puede usar un modelo distinto: responde con datos recuperados y se beneficia
# de un modelo mayor sin alargar la generación de sesiones. Por defecto, el mismo que las sesiones.
MODEL_REGLAMENTO = os.environ.get("OLLAMA_MODEL_REGLAMENTO", MODEL_SESION)
EXERCISES_PATH = os.environ.get("EXERCISES_PATH", "/app/data/exercises.json")
CHROMA_DB_DIR  = os.environ.get("CHROMA_DB_DIR", "/app/data/chroma_db")
# Reglamento por ámbito: data/reglamento/<ámbito>/*.md ("general" = FIBA/FEB; una carpeta por
# comunidad autónoma, p. ej. "aragon"). La consulta de una comunidad usa también el general.
REGLAMENTO_DIR = os.environ.get("REGLAMENTO_DIR", "/app/data/reglamento")
AMBITO_GENERAL = "general"
NOMBRES_AMBITO = {
    "general": "General (FIBA y normativa común)",
    "aragon": "Aragón",
}
_AMBITO_RE = re.compile(r"^[a-z][a-z0-9_]{1,29}$")
# Modelo de embeddings de la búsqueda (RAG). Medido con tools/evaluar_recuperacion.py sobre 20 preguntas fijas:
# qwen3-embedding:0.6b acierta en la primera posición el 80 % (nomic-embed-text, el 45 %) y es multilingüe.
# Cambiarlo obliga a reindexar (tools/indexar_colecciones.py): la base recuerda con cuál se indexó.
EMBED_MODEL    = os.environ.get("EMBED_MODEL", "qwen3-embedding:0.6b")
