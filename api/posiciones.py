# api/posiciones.py
"""Posiciones con nombre de los diagramas.

Diccionario único nombre → (x, y) con la tabla «Posiciones canónicas (media pista)» de
docs/coordenadas.md. Lo usan el renderer (diagram_renderer.py), el validador
(diagramas.py) y las plantillas de calentamiento. No importa a ningún otro módulo de api/.

Un punto de un diagrama (jugador, cono o a_pos) puede escribirse de tres formas:
  {"x": 35, "y": 41}          coordenadas, como hasta ahora
  {"pos": "codo_derecho"}     nombre de la tabla (si trae x e y, mandan x e y)
  "codo_derecho"              solo en a_pos: el nombre como texto
"""
import difflib
import re
import unicodedata

# Misma tabla que docs/coordenadas.md (si cambias una, cambia la otra; lo comprueba
# tests/test_posiciones.py). Izquierda/derecha desde el atacante mirando al aro.
POSICIONES_CANONICAS: dict[str, tuple[float, float]] = {
    "canasta":                  (50, 11),
    "linea_de_fondo_centro":    (50, 5),
    "poste_bajo_derecho":       (38, 18),
    "poste_bajo_izquierdo":     (62, 18),
    "esquina_triple_derecha":   (6, 22),
    "esquina_triple_izquierda": (94, 22),
    "esquina_mini_derecha":     (10, 22),
    "esquina_mini_izquierda":   (90, 22),
    "poste_alto_derecho":       (38, 36),
    "poste_alto_izquierdo":     (62, 36),
    "codo_derecho":             (35, 41),
    "codo_izquierdo":           (65, 41),
    "linea_tl_centro":          (50, 41),
    "media_distancia_derecha":  (15, 50),
    "media_distancia_izquierda": (85, 50),
    "45_derecho":               (25, 50),
    "45_izquierdo":             (75, 50),
    "arco_triple_frontal":      (50, 60),
    "cabecera":                 (50, 65),
    "medio_campo_derecha":      (25, 95),
    "medio_campo_izquierda":    (75, 95),
    "centro_medio_campo":       (50, 100),
}


class PosicionDesconocida(ValueError):
    """Nombre de posición que no está en POSICIONES_CANONICAS."""


def normalizar_nombre(nombre: str) -> str:
    """'Codo derecho', 'codo-derecho' o 'CODO_DERECHO' → 'codo_derecho' (sin tildes ni °)."""
    sin_tildes = unicodedata.normalize("NFKD", str(nombre))
    sin_tildes = "".join(c for c in sin_tildes if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", "_", sin_tildes).strip("_")


def coordenadas_de_nombre(nombre: str, tipo: str = "media_pista") -> tuple[float, float]:
    """(x, y) de una posición canónica. La tabla es de media pista (y=100 → medio campo);
    en pista completa se sitúa en la mitad de ataque (y=0 → fondo propio, y=50 → medio campo),
    así que la y se divide entre dos."""
    clave = normalizar_nombre(nombre)
    if clave not in POSICIONES_CANONICAS:
        parecidas = difflib.get_close_matches(clave, list(POSICIONES_CANONICAS), n=3, cutoff=0.6)
        pista = f"; ¿quisiste decir {', '.join(parecidas)}?" if parecidas else ""
        raise PosicionDesconocida(
            f"posición desconocida '{nombre}': usa x/y o un nombre de la tabla de "
            f"posiciones canónicas{pista}"
        )
    x, y = POSICIONES_CANONICAS[clave]
    if tipo == "pista_completa":
        return x, y / 2
    return x, y


def posicion_de(punto, tipo: str = "media_pista") -> tuple[float, float]:
    """(x, y) de un punto del diagrama: {"x","y"}, {"pos": nombre} o el nombre como texto.
    Las coordenadas explícitas se devuelven tal cual (mismo tipo numérico) para que los
    diagramas actuales se dibujen exactamente igual."""
    if isinstance(punto, str):
        return coordenadas_de_nombre(punto, tipo)
    if isinstance(punto, dict):
        if "x" in punto and "y" in punto:
            return punto["x"], punto["y"]
        if "pos" in punto:
            return coordenadas_de_nombre(punto["pos"], tipo)
    raise ValueError(f"punto sin posición (faltan x/y o pos): {punto!r}")
