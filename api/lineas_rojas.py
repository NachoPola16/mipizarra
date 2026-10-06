# api/lineas_rojas.py
"""Guardia de líneas rojas por edad para el texto que genera el modelo.

Criterio: data/teoria/contenidos_por_edad_lineas_rojas.md, que manda sobre cualquier otro
documento. Es una red de seguridad léxica, no un análisis del contenido: detecta los términos
vetados y deja pasar el lenguaje legítimo de formación (zona pintada, bloquear para el rebote...)."""
import re
import unicodedata

# Minibasket y alevín: sin poste, bloqueos, mano a mano, zonas ni trampas.
CATEGORIAS_MINIBASKET = {"U8", "U10", "U12", "Prebenjamín", "Benjamín", "Alevín"}
# Infantil/U14: el bloqueo directo no es línea roja. Se admite de forma puntual (según el
# nivel del equipo o en una jugada concreta); el prompt lo pide así, pero no se veta.
CATEGORIAS_BLOQUEO_DIRECTO_PUNTUAL = {"U14", "Infantil"}

_PICK_AND_ROLL = r"pick\s*(?:and|n|&|y)?\s*'?\s*roll"

_VETADOS_MINIBASKET = (
    r"bloqueos?\b(?!\s+(?:de\s+|del\s+|y\s+)?rebote)",
    r"\bpantallas?\b",
    _PICK_AND_ROLL,
    r"mano a mano",
    r"defensa zonal|\bzonal\b|zona\s+(?:2-3|3-2|1-3-1|2-1-2)",
    r"poste (?:bajo|alto)|juego de poste|de espaldas a (?:la )?canasta",
    r"trampas? defensivas?",
)


def _normalizar(texto: str) -> str:
    sin_acentos = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in sin_acentos if unicodedata.category(c) != "Mn")


# Decir que algo NO se trabaja («sin bloqueos», «no hay pantallas», «evitar el mano a mano») no es trabajarlo.
# Mismo criterio que el arnés (tools/regresion.py): la negación va antes del término, en la misma frase.
_NEGACION = re.compile(r"\b(?:sin|no|nunca|ni|evit\w*|prohib\w*|todavia|aun)\b")
_FRASES = re.compile(r"[.\n;:!?]+")


def violaciones(texto: str, edad: str) -> list[str]:
    """Términos del texto que son línea roja para esa edad (lista vacía si no hay ninguno)."""
    if edad in CATEGORIAS_MINIBASKET:
        patrones = _VETADOS_MINIBASKET
    else:
        return []
    encontrados: list[str] = []
    for frase in _FRASES.split(_normalizar(texto)):
        for patron in patrones:
            for m in re.finditer(patron, frase):
                if _NEGACION.search(frase[:m.start()]):
                    continue
                motivo = f"«{m.group(0).strip()}» no se trabaja en {edad} (línea roja)"
                if motivo not in encontrados:
                    encontrados.append(motivo)
    return encontrados


def instruccion_prompt(edad: str) -> str:
    """Aviso para el prompt de sesión con lo que no se puede incluir en esa edad ('' si nada)."""
    if edad in CATEGORIAS_MINIBASKET:
        return ("PROHIBIDO en esta categoría (no lo uses en ningún apartado): bloqueos, pantallas, "
                "mano a mano, defensa zonal, juego de poste y trampas defensivas.")
    if edad in CATEGORIAS_BLOQUEO_DIRECTO_PUNTUAL:
        return ("El bloqueo directo solo de forma puntual y sencilla (una jugada concreta o si el "
                "nivel del equipo lo permite), nunca como contenido central; el indirecto sí se puede trabajar.")
    return ""
