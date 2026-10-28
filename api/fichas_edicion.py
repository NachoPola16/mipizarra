# api/fichas_edicion.py
"""Edición de las fichas de la biblioteca por el administrador (pestaña «Fichas»).

Los cambios se escriben **directamente en `data/exercises.json`**. Como red de seguridad temporal (se apaga con las
variables de abajo cuando ya no haga falta), antes de cada guardado se hace:
  - una copia del fichero entero en `<CARPETA>/copias/` (se conservan las últimas COPIAS_MAX), y
  - se guarda la versión anterior de esa ficha en `<CARPETA>/ficha_historial.json` (hasta HISTORIAL_MAX por ficha),
    que es lo que usa «volver a la versión anterior».
El fichero del servidor queda por delante de git: ver docs/administracion-fichas.md para traerlo al repositorio."""
import datetime
import json
import os
import threading

CARPETA = os.environ.get("FICHAS_COPIAS_DIR", "/app/data/cambios")
COPIAS_MAX = int(os.environ.get("FICHAS_COPIAS_MAX", "20"))           # 0 = no hacer copias del fichero
HISTORIAL_MAX = int(os.environ.get("FICHAS_HISTORIAL_MAX", "10"))     # 0 = no guardar versiones (sin «volver atrás»)

# Lo que el administrador puede editar. El id no cambia nunca.
CAMPOS_EDITABLES = (
    "nombre", "categoria", "subcategoria", "espacio", "edades", "duracion_min", "intensidad", "carga_cognitiva",
    "jugadores_minimos", "objetivos", "descripcion", "puntos_clave", "material", "consigna", "errores_frecuentes",
    "que_observar", "progresion", "diagrama", "diagramas", "sin_diagrama",
)
CAMPOS_OPCIONALES = ("material", "consigna", "errores_frecuentes", "que_observar", "progresion")
# Un guardado solo sustituye el diagrama de la ficha si trae alguno de estos campos (el editor manda siempre
# `sin_diagrama`).
CAMPOS_DIAGRAMA = ("diagrama", "diagramas", "sin_diagrama")

_cerrojo = threading.Lock()


def leer(ruta: str) -> list:
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def combinar(viejo: dict, campos: dict) -> dict:
    """La ficha `viejo` con los `campos` editados encima, conservando el orden de las claves (diff limpio en git).
    El diagrama solo cambia si `campos` lo trae."""
    toca_diagrama = any(k in campos for k in CAMPOS_DIAGRAMA)
    propios = {k for k in CAMPOS_EDITABLES if toca_diagrama or k not in CAMPOS_DIAGRAMA}
    nueva = {}
    for k, v in viejo.items():
        if k not in propios:
            nueva[k] = v
        elif k in campos:
            nueva[k] = campos[k]
    for k in CAMPOS_EDITABLES:
        if k in campos and k in propios and k not in nueva:
            nueva[k] = campos[k]
    if not nueva.get("sin_diagrama"):
        nueva.pop("sin_diagrama", None)
    return nueva


def _escribir_en_sitio(ruta: str, lista: list) -> None:
    """Escribe exercises.json en su sitio (en Docker es un fichero montado: no se puede reemplazar por renombrado).
    El texto se genera y se comprueba antes de abrir el fichero, así un fallo no lo deja a medias."""
    texto = json.dumps(lista, ensure_ascii=False, indent=2)
    json.loads(texto)
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(texto)


def _instantanea(ruta: str) -> None:
    if COPIAS_MAX <= 0:
        return
    carpeta = os.path.join(CARPETA, "copias")
    os.makedirs(carpeta, exist_ok=True)
    nombre = f"exercises-{datetime.datetime.now():%Y%m%d-%H%M%S-%f}.json"
    with open(ruta, "rb") as origen, open(os.path.join(carpeta, nombre), "wb") as destino:
        destino.write(origen.read())
    for vieja in sorted(os.listdir(carpeta))[:-COPIAS_MAX]:
        os.unlink(os.path.join(carpeta, vieja))


def _ruta_historial() -> str:
    return os.path.join(CARPETA, "ficha_historial.json")


def _leer_historial() -> dict:
    try:
        with open(_ruta_historial(), encoding="utf-8") as f:
            datos = json.load(f)
    except (OSError, ValueError):
        return {}
    return datos if isinstance(datos, dict) else {}


def _escribir_historial(historial: dict) -> None:
    os.makedirs(CARPETA, exist_ok=True)
    with open(_ruta_historial(), "w", encoding="utf-8") as f:
        json.dump(historial, f, ensure_ascii=False, indent=1)


def ids_con_historial() -> list:
    return [i for i, versiones in _leer_historial().items() if versiones]


def guardar(ruta: str, ficha_id: str, campos: dict) -> dict | None:
    """Escribe los cambios en exercises.json y devuelve la ficha resultante (None si la ficha no existe)."""
    with _cerrojo:
        lista = leer(ruta)
        i = next((n for n, f in enumerate(lista) if f.get("id") == ficha_id), None)
        if i is None:
            return None
        viejo = lista[i]
        nueva = combinar(viejo, campos)
        if nueva == viejo:
            return nueva
        _instantanea(ruta)
        if HISTORIAL_MAX > 0:
            historial = _leer_historial()
            versiones = historial.setdefault(ficha_id, [])
            versiones.append({"fecha": f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S}", "ficha": viejo})
            historial[ficha_id] = versiones[-HISTORIAL_MAX:]
            _escribir_historial(historial)
        lista[i] = nueva
        _escribir_en_sitio(ruta, lista)
        return nueva


def volver_atras(ruta: str, ficha_id: str) -> dict | None:
    """Devuelve la ficha a su versión anterior (la última guardada en el historial). None si no hay ninguna."""
    with _cerrojo:
        historial = _leer_historial()
        versiones = historial.get(ficha_id) or []
        if not versiones:
            return None
        lista = leer(ruta)
        i = next((n for n, f in enumerate(lista) if f.get("id") == ficha_id), None)
        if i is None:
            return None
        anterior = versiones.pop()["ficha"]
        _instantanea(ruta)
        lista[i] = anterior
        _escribir_en_sitio(ruta, lista)
        historial[ficha_id] = versiones
        _escribir_historial(historial)
        return anterior
