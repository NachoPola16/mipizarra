# api/ficha_cambios.py
"""Cambios del administrador sobre las fichas de la biblioteca.

`data/exercises.json` (git) es la base; los cambios viven aparte, en un fichero propio del servidor
(`ficha_cambios.json`: {id: campos}), y se aplican encima al cargar la biblioteca. Así `git pull` nunca choca con
ellos, cada ficha se puede «restaurar la original» y el fichero entra en la copia de seguridad. Un cambio sustituye
los campos editables de la ficha; el id y el diagrama salen siempre de la base. Sin dependencias pesadas: lo importa
`ejercicios.py`."""
import json
import os
import tempfile
import threading

CAMBIOS_PATH = os.environ.get("FICHA_CAMBIOS_PATH", "/app/data/cambios/ficha_cambios.json")

# Lo que el administrador puede editar. Todo lo demás (id, diagrama, diagramas, sin_diagrama) viene de la base.
CAMPOS_EDITABLES = (
    "nombre", "categoria", "subcategoria", "espacio", "edades", "duracion_min", "intensidad", "carga_cognitiva",
    "jugadores_minimos", "objetivos", "descripcion", "puntos_clave", "material", "consigna", "errores_frecuentes",
    "que_observar", "progresion",
)
CAMPOS_OPCIONALES = ("material", "consigna", "errores_frecuentes", "que_observar", "progresion")

_cerrojo = threading.Lock()
_cache: dict = {"clave": None, "datos": {}}


def leer_cambios() -> dict:
    """{id: campos}. Vacío si no hay fichero o está estropeado (la biblioteca base sigue funcionando)."""
    try:
        st = os.stat(CAMBIOS_PATH)
    except OSError:
        return {}
    clave = (CAMBIOS_PATH, st.st_mtime_ns, st.st_size)
    if _cache["clave"] == clave:
        return _cache["datos"]
    try:
        with open(CAMBIOS_PATH, encoding="utf-8") as f:
            datos = json.load(f)
    except (OSError, ValueError):
        return {}
    datos = datos if isinstance(datos, dict) else {}
    _cache.update(clave=clave, datos=datos)
    return datos


def aplicar(base: list, cambios: dict | None = None) -> list:
    """La biblioteca con los cambios encima (copias: no toca `base`)."""
    cambios = leer_cambios() if cambios is None else cambios
    if not cambios:
        return base
    salida = []
    for ficha in base:
        cambio = cambios.get(ficha.get("id"))
        if isinstance(cambio, dict):
            fija = {k: v for k, v in ficha.items() if k not in CAMPOS_EDITABLES}
            ficha = {**fija, **{k: v for k, v in cambio.items() if k in CAMPOS_EDITABLES}}
        salida.append(ficha)
    return salida


def _escribir(cambios: dict) -> None:
    carpeta = os.path.dirname(CAMBIOS_PATH) or "."
    os.makedirs(carpeta, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=carpeta, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(cambios, f, ensure_ascii=False, indent=1)
        os.replace(tmp, CAMBIOS_PATH)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def guardar_cambio(ficha_id: str, campos: dict) -> None:
    with _cerrojo:
        cambios = dict(leer_cambios())
        cambios[ficha_id] = {k: campos[k] for k in CAMPOS_EDITABLES if k in campos}
        _escribir(cambios)


def borrar_cambio(ficha_id: str) -> bool:
    with _cerrojo:
        cambios = dict(leer_cambios())
        if ficha_id not in cambios:
            return False
        del cambios[ficha_id]
        _escribir(cambios)
        return True
