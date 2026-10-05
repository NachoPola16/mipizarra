# api/bloques.py
"""Bloques de la sesión que compone el código a partir de las fichas de exercises.json.

La descripción y los puntos clave de un ejercicio de la biblioteca están curados por el
entrenador: se copian tal cual (el modelo no los reescribe ni los acorta). Solo cambia el
formato de la descripción: las secciones en mayúsculas pasan a línea propia."""
import re

# Etiqueta de sección dentro de una descripción: palabra(s) en mayúsculas seguida de ':'
# ("SECUENCIA:", "ROTACIÓN:", "SECUENCIA PROGRESIVA:"...), siempre al principio o tras un espacio.
_ETIQUETA = re.compile(r"(?<!\S)[A-ZÁÉÍÓÚÑ]{4,}(?: [A-ZÁÉÍÓÚÑ]{2,})*:")
_PREFIJO_ORGANIZACION = re.compile(r"^ORGANIZACIÓN:\s*")

SECCIONES_PROGRESION = ("PROGRESIÓN", "VARIANTES")


def formatear_descripcion(descripcion: str) -> str:
    """Quita el prefijo 'ORGANIZACIÓN:' (ya lo pone la etiqueta del bloque) y pone cada
    sección en mayúsculas en su propia línea. No cambia ni una palabra del texto."""
    texto = _PREFIJO_ORGANIZACION.sub("", descripcion.strip())
    texto = _ETIQUETA.sub(lambda m: "\n" + m.group(0), texto)
    lineas = (linea.strip() for linea in texto.split("\n"))
    return "\n".join(linea for linea in lineas if linea)


def extraer_seccion(descripcion: str, nombres: tuple[str, ...]) -> str:
    """Texto de la primera sección cuyo nombre esté en `nombres` (sin la etiqueta), hasta
    donde empiece la siguiente sección. Cadena vacía si la descripción no la tiene."""
    recogido: list[str] = []
    dentro = False
    for linea in formatear_descripcion(descripcion).split("\n"):
        if _ETIQUETA.match(linea):
            if dentro:
                break
            etiqueta = linea.split(":", 1)[0]
            if etiqueta in nombres:
                dentro = True
                recogido.append(linea.split(":", 1)[1].strip())
        elif dentro:
            recogido.append(linea)
    return " ".join(parte for parte in recogido if parte)


def bloque_curado(numero, ej: dict, duracion: int, partido: bool) -> str:
    """Bloque 'Ejercicio N' (o 'N.1' si el ejercicio se parte en base + variante) con la
    descripción y los puntos clave de la ficha, íntegros."""
    sufijo = ".1" if partido else ""
    lineas = [
        f"Ejercicio {numero}{sufijo}: {ej['nombre']}",
        f"Duración: {duracion} min",
        "Organización:",
        formatear_descripcion(ej.get("descripcion", "")),
    ]
    puntos = ej.get("puntos_clave", [])
    if puntos:
        lineas.append("Puntos clave:")
        lineas.extend(f"- {punto}" for punto in puntos)
    return "\n".join(lineas)


def bloque_variante_curada(numero, ej: dict, duracion: int) -> str | None:
    """Variante 'Ejercicio N.2' construida con la progresión curada de la ficha, o None
    si la ficha no trae sección de progresión/variantes (entonces la propone el modelo)."""
    cambio = extraer_seccion(ej.get("descripcion", ""), SECCIONES_PROGRESION)
    if not cambio:
        return None
    return "\n".join([
        f'Ejercicio {numero}.2 (variante de "{ej["nombre"]}"):',
        f"Duración: {duracion} min",
        f"Qué cambia respecto a {numero}.1: {cambio}",
        f"Organización: Igual que en {numero}.1, con el cambio indicado.",
    ])


# ─── Troceado de la respuesta del modelo ─────────────────────────────────

_CAB_CALENTAMIENTO = re.compile(r"^\*{0,2}\s*CALENTAMIENTO", re.IGNORECASE)
_CAB_VUELTA = re.compile(r"^\*{0,2}\s*VUELTA A LA CALMA", re.IGNORECASE)
_CAB_FIN = re.compile(r"^\*{0,2}\s*(?:PARTE PRINCIPAL|DESCANSO)", re.IGNORECASE)
_CAB_EJERCICIO = re.compile(r"^Ejercicio\s+(\d+(?:\.\d+)?)\b")
_CAB_FUNDAMENTOS = re.compile(r"^(?:\*{2}fundamentos\*{2}|fundamentos)\s*:?\s*(.*)$", re.IGNORECASE)


def _cabecera(linea: str):
    """('clave', resto_de_la_linea) si la línea abre un bloque de la sesión; ('fin', '') si
    cierra el bloque en curso sin abrir otro; None si es una línea normal."""
    if _CAB_CALENTAMIENTO.match(linea):
        return "calentamiento", ""
    if _CAB_VUELTA.match(linea):
        return "vuelta", ""
    if _CAB_FIN.match(linea):
        return "fin", ""
    m = _CAB_EJERCICIO.match(linea)
    if m:
        return f"ej:{m.group(1)}", linea
    m = _CAB_FUNDAMENTOS.match(linea)
    if m and (linea.startswith("**") or ":" in linea):
        return "fundamentos", m.group(1).strip()
    return None


def extraer_bloques(texto: str) -> dict[str, str]:
    """Trocea la respuesta del modelo en 'calentamiento', 'vuelta', 'fundamentos' y
    'ej:<N>' / 'ej:<N.1>' / 'ej:<N.2>' (este último con su línea de cabecera). Solo cuenta la
    primera aparición de cada bloque: lo que el modelo repita después se ignora."""
    bloques: dict[str, str] = {}
    clave: str | None = None
    lineas: list[str] = []

    def cerrar():
        if clave is not None:
            bloques.setdefault(clave, "\n".join(lineas).strip())

    for linea in texto.split("\n"):
        encontrada = _cabecera(linea.strip())
        if encontrada:
            cerrar()
            nueva, resto = encontrada
            if nueva == "fin" or nueva in bloques:
                clave, lineas = None, []
            else:
                clave, lineas = nueva, [resto] if resto else []
        elif clave is not None:
            lineas.append(linea.rstrip())
    cerrar()
    return bloques


# ─── Bloques redactados por el modelo ────────────────────────────────────

MARCA_PROPUESTO = "Propuesto por la IA (sin revisar)"


def nombre_de_cabecera(bloque: str) -> str:
    """Nombre que el modelo puso en la cabecera 'Ejercicio N: nombre' (sin comillas)."""
    primera = bloque.split("\n", 1)[0]
    return primera.split(":", 1)[1].strip().strip('"') if ":" in primera else ""


def reescribir_bloque(bloque: str, cabecera: str, duracion: int, propuesto: bool = False) -> str:
    """Bloque del modelo con la cabecera dada y la duración fijada por el código (el modelo
    no decide los minutos), más la marca de «propuesto» cuando no sale de la biblioteca."""
    cuerpo = [l for l in bloque.split("\n")[1:] if not l.strip().lower().startswith("duración:")]
    lineas = [cabecera, f"Duración: {duracion} min"]
    if propuesto:
        lineas.append(MARCA_PROPUESTO)
    return "\n".join(lineas + cuerpo).rstrip()
