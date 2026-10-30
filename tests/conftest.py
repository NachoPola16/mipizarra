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
# La biblioteca completa (ejercicios, jugadas, teoría) es privada y no viene en el repositorio público
# (docs/datos-privados.md). Sin ella los tests usan la muestra y se saltan los que dependen del contenido.
BIBLIOTECA_COMPLETA = EXERCISES_JSON.exists()
if not BIBLIOTECA_COMPLETA:
    EXERCISES_JSON = DATA_DIR / "muestra_ejercicios.json"
# Módulos de test (o "modulo::test") que necesitan la biblioteca completa.
REQUIEREN_BIBLIOTECA: set[str] = {
    "test_admin_fichas", "test_seleccion_ejercicios", "test_relevancia_ejercicios", "test_cobertura_temas", "test_validar_candidatos",
    "test_bloques_curados", "test_calentamiento_de_biblioteca", "test_validacion_fichas", "test_sin_diagrama",
    "test_seleccion_n_ejercicios", "test_huecos_biblioteca", "test_exercises_json", "test_evaluar_recuperacion",
    "test_posiciones::test_la_biblioteca_tiene_diagramas", "test_jugadas::test_el_catalogo_de_jugadas_es_coherente",
    "test_cuentas::test_cuentas_y_jugadas_guardadas",
}

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


def pytest_collection_modifyitems(config, items):
    if BIBLIOTECA_COMPLETA:
        return
    salto = pytest.mark.skip(reason="necesita la biblioteca privada (docs/datos-privados.md)")
    for item in items:
        modulo = item.module.__name__.split(".")[-1]
        if modulo in REQUIEREN_BIBLIOTECA or f"{modulo}::{item.originalname}" in REQUIEREN_BIBLIOTECA:
            item.add_marker(salto)
