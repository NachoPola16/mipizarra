# api/modelo_indice.py
"""Marca del modelo de embeddings con el que se indexó la base de ChromaDB.

Consultar con un modelo distinto del que indexó da vectores incomparables: la búsqueda devuelve
fragmentos sin relación y no lanza ningún error. El indexador escribe aquí el modelo y la API
comprueba al arrancar que coincide. No tiene dependencias: lo usan la API y las herramientas."""
from pathlib import Path

NOMBRE_MARCA = "modelo_embeddings.txt"


def escribir_marca(ruta_db, modelo: str) -> None:
    carpeta = Path(ruta_db)
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / NOMBRE_MARCA).write_text(modelo + "\n", encoding="utf-8")


def leer_marca(ruta_db) -> str | None:
    try:
        return (Path(ruta_db) / NOMBRE_MARCA).read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def desajuste(ruta_db, modelo: str) -> str | None:
    """Texto de aviso si la base no se indexó con `modelo` (o no se sabe), None si todo coincide."""
    marca = leer_marca(ruta_db)
    if marca is None:
        return (f"La base {ruta_db} no tiene marca del modelo de embeddings: no se sabe con cuál se indexó. "
                f"Si no fue '{modelo}', la búsqueda no funcionará; reindexa con tools/indexar_colecciones.py.")
    if marca != modelo:
        return (f"La base {ruta_db} se indexó con '{marca}' pero la API consulta con '{modelo}': la búsqueda "
                f"devolverá resultados sin sentido. Reindexa con tools/indexar_colecciones.py.")
    return None
