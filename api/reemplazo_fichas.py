# api/reemplazo_fichas.py
"""Buscar y reemplazar texto en las fichas (pestaña «Fichas»). Solo toca los campos de texto, nunca ids, números,
diagramas ni identificadores; el ámbito es el español, el inglés (`i18n.en`) o los dos."""
import copy
import re

CAMPOS_TEXTO = ("nombre", "descripcion", "material", "consigna", "puntos_clave", "errores_frecuentes", "que_observar",
                "progresion", "objetivos")
CAMPOS_TEXTO_EN = ("nombre", "descripcion", "material", "consigna", "puntos_clave", "errores_frecuentes",
                   "que_observar", "progresion", "titulos_diagramas")
AMBITOS = ("es", "en", "ambos")
MAX_PATRON = 200
CONTEXTO = 45


def _compilar(buscar: str, palabra: bool, mayusculas: bool):
    if not buscar or len(buscar) > MAX_PATRON:
        raise ValueError(f"El texto a buscar debe tener entre 1 y {MAX_PATRON} caracteres")
    p = re.escape(buscar)
    if palabra:
        p = r"(?<!\w)" + p + r"(?!\w)"
    return re.compile(p, 0 if mayusculas else re.IGNORECASE)


def _sustituir(patron, nuevo: str, texto: str, adaptar_mayuscula: bool):
    """(texto nuevo, número de cambios). Sin distinguir mayúsculas, «Reversa» → «Reverso» conserva la inicial."""
    def cambia(m):
        if adaptar_mayuscula and m.group(0)[:1].isupper() and nuevo[:1].islower():
            return nuevo[:1].upper() + nuevo[1:]
        return nuevo
    return patron.subn(cambia, texto)


def _recorre(o, ruta, patron, nuevo, adaptar, cambios):
    """Sustituye en las hojas de texto de `o` (modifica en sitio) y anota cada cambio.
    `ruta` es el nombre del campo hasta aquí: «puntos_clave[2]», «progresion.facilitar»..."""
    if isinstance(o, dict):
        items = [(f"{ruta}{k}", k, v, f"{ruta}{k}.") for k, v in o.items()]
        for campo, k, v, hijos in items:
            if isinstance(v, str):
                t, n = _sustituir(patron, nuevo, v, adaptar)
                if n:
                    cambios.append({"campo": campo, "antes": _fragmento(patron, v),
                                    "despues": _fragmento_nuevo(patron, nuevo, v, adaptar)})
                    o[k] = t
            elif isinstance(v, dict):
                _recorre(v, hijos, patron, nuevo, adaptar, cambios)
            else:
                _recorre(v, campo, patron, nuevo, adaptar, cambios)
    elif isinstance(o, list):
        for i, v in enumerate(o):
            campo = f"{ruta}[{i + 1}]"
            if isinstance(v, str):
                t, n = _sustituir(patron, nuevo, v, adaptar)
                if n:
                    cambios.append({"campo": campo, "antes": _fragmento(patron, v),
                                    "despues": _fragmento_nuevo(patron, nuevo, v, adaptar)})
                    o[i] = t
            elif isinstance(v, dict):
                _recorre(v, campo + ".", patron, nuevo, adaptar, cambios)
            else:
                _recorre(v, campo, patron, nuevo, adaptar, cambios)


def _fragmento(patron, texto: str) -> str:
    m = patron.search(texto)
    a, b = max(0, m.start() - CONTEXTO), min(len(texto), m.end() + CONTEXTO)
    return ("…" if a else "") + texto[a:b] + ("…" if b < len(texto) else "")


def _fragmento_nuevo(patron, nuevo: str, texto: str, adaptar: bool) -> str:
    m = patron.search(texto)
    a, b = max(0, m.start() - CONTEXTO), min(len(texto), m.end() + CONTEXTO)
    t, _ = _sustituir(patron, nuevo, texto[a:b], adaptar)
    return ("…" if a else "") + t + ("…" if b < len(texto) else "")


def reemplazar_en_ficha(ficha: dict, buscar: str, nuevo: str, ambito: str = "es", palabra: bool = False,
                        mayusculas: bool = False):
    """(ficha nueva, lista de cambios). La ficha original no se modifica."""
    if ambito not in AMBITOS:
        raise ValueError("Ámbito no válido")
    if len(nuevo) > MAX_PATRON:
        raise ValueError(f"El texto de reemplazo debe tener como mucho {MAX_PATRON} caracteres")
    patron = _compilar(buscar, palabra, mayusculas)
    adaptar = not mayusculas
    salida = copy.deepcopy(ficha)
    cambios: list = []
    if ambito in ("es", "ambos"):
        for campo in CAMPOS_TEXTO:
            if campo in salida:
                parcial = {campo: salida[campo]}
                _recorre(parcial, "", patron, nuevo, adaptar, cambios)
                salida[campo] = parcial[campo]
    if ambito in ("en", "ambos"):
        en = (salida.get("i18n") or {}).get("en")
        if isinstance(en, dict):
            for campo in CAMPOS_TEXTO_EN:
                if campo in en:
                    parcial = {campo: en[campo]}
                    _recorre(parcial, "EN ", patron, nuevo, adaptar, cambios)
                    en[campo] = parcial[campo]
    return salida, cambios
