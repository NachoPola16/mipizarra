# tests/conftest.py
"""Configuración común de los tests offline.

Los tests importan directamente de api/ (como hace uvicorn dentro del contenedor),
sin Ollama ni red. rag_engine crea al importarse un cliente de ChromaDB y un modelo
de embeddings de Ollama; aquí se sustituyen por módulos vacíos porque ninguna de las
funciones que se prueban (filtrado, selección, validación) los usa.
"""
import json
import os
import sys
import types
from pathlib import Path

import pytest

RAIZ     = Path(__file__).resolve().parent.parent
API_DIR  = RAIZ / "api"
DATA_DIR = RAIZ / "data"
EXERCISES_JSON = DATA_DIR / "exercises.json"

# Antes de importar nada de api/: la biblioteca de ejercicios del repo, no la del
# contenedor (/app/data/...).
os.environ["EXERCISES_PATH"] = str(EXERCISES_JSON)
os.environ["REGLAMENTO_DIR"] = str(DATA_DIR / "reglamento")
os.environ.setdefault("FEEDBACK_DIR", str(RAIZ / "data" / "sessions"))

if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))


def _instalar_stubs() -> None:
    """Módulos falsos para chromadb y llama_index (solo lo que rag_engine toca al importarse)."""
    chromadb = types.ModuleType("chromadb")
    chromadb.PersistentClient = lambda *a, **k: None
    llama_index = types.ModuleType("llama_index")
    embeddings  = types.ModuleType("llama_index.embeddings")
    ollama      = types.ModuleType("llama_index.embeddings.ollama")
    ollama.OllamaEmbedding = lambda *a, **k: None
    sys.modules["chromadb"] = chromadb
    sys.modules["llama_index"] = llama_index
    sys.modules["llama_index.embeddings"] = embeddings
    sys.modules["llama_index.embeddings.ollama"] = ollama


_instalar_stubs()


@pytest.fixture
def ejercicios():
    """Copia fresca de data/exercises.json en cada test (filtrar_ejercicios marca
    los dicts con '_fase', así que no se comparte entre tests)."""
    with open(EXERCISES_JSON, encoding="utf-8") as f:
        return json.load(f)
