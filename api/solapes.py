# api/solapes.py
"""Separación mínima y determinista de marcadores solapados en un diagrama.

La usan el renderer (al dibujar, sin tocar el JSON) y el validador (para reparar el
diagrama antes de rechazarlo). Trabaja en el sistema de coordenadas 0-100 del diagrama
(docs/coordenadas.md), igual en media pista y en pista completa. No importa a ningún
otro módulo de api/.

Los puntos se colocan en el orden recibido: cada uno se compara solo con los ya
colocados, así que los primeros nunca se mueven (el que llega después es el que se
aparta). Si un punto está a menos de DISTANCIA_MINIMA de alguno, se busca la posición
válida más cercana dentro de la pista y a no más de DESPLAZAMIENTO_MAXIMO; si no la
hay, se deja donde estaba y se informa.
"""
import math

# Mismo umbral que el validador: por debajo, los círculos se solapan en el dibujo.
DISTANCIA_MINIMA = 8
# Más allá, mover el marcador cambiaría el sentido del ejercicio.
DESPLAZAMIENTO_MAXIMO = 8

# Margen sobre el mínimo para que el redondeo a 2 decimales no deje el punto por debajo.
_MARGEN = 0.01
_EPS = 1e-9


def _distancia(p, q) -> float:
    return math.hypot(p[0] - q[0], p[1] - q[1])


def _redondear(p) -> tuple[float, float]:
    return round(p[0], 2), round(p[1], 2)


def _candidatos(q, vecinos: list, radio: float) -> list[tuple[float, float]]:
    """Posiciones donde puede quedar q, de más exactas a más aproximadas. Todas
    deterministas: dependen solo de las coordenadas y del orden de los vecinos."""
    cands = []
    # 1. Empuje en línea recta desde cada vecino (mínimo exacto con un solo conflicto).
    for p in vecinos:
        d = _distancia(p, q)
        if d > _EPS:
            cands.append((p[0] + (q[0] - p[0]) / d * radio, p[1] + (q[1] - p[1]) / d * radio))
    # 2. Cortes entre las circunferencias de dos vecinos (mínimo exacto entre dos).
    for i, p1 in enumerate(vecinos):
        for p2 in vecinos[i + 1:]:
            d = _distancia(p1, p2)
            if _EPS < d <= 2 * radio:
                a = d / 2
                h = math.sqrt(max(0.0, radio ** 2 - a ** 2))
                mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
                ux, uy = (p2[0] - p1[0]) / d, (p2[1] - p1[1]) / d
                cands += [(mx - h * uy, my + h * ux), (mx + h * uy, my - h * ux)]
    # 3. Cortes de cada circunferencia con los bordes de la pista (marcador junto a la línea).
    for p in vecinos:
        for borde in (0, 100):
            for eje in (0, 1):
                dist_borde = abs(p[eje] - borde)
                if dist_borde <= radio:
                    h = math.sqrt(radio ** 2 - dist_borde ** 2)
                    for s in (-1, 1):
                        c = [0.0, 0.0]
                        c[eje] = borde
                        c[1 - eje] = p[1 - eje] + s * h
                        cands.append(tuple(c))
    # 4. Respaldo: anillos alrededor de q (también resuelve puntos coincidentes).
    for k in range(1, 33):
        r = DESPLAZAMIENTO_MAXIMO * k / 32
        for g in range(0, 360, 10):
            ang = math.radians(g)
            cands.append((q[0] + r * math.cos(ang), q[1] + r * math.sin(ang)))
    return cands


def separar_puntos(puntos: list, es_cono: list | None = None,
                   distancia_min: float = DISTANCIA_MINIMA,
                   desplazamiento_max: float = DESPLAZAMIENTO_MAXIMO) -> tuple[list, list[int]]:
    """Devuelve (puntos_separados, indices_sin_sitio). Los puntos que no se mueven se
    devuelven tal cual (mismo objeto); los movidos, redondeados a 2 decimales. Los
    pares cono-cono no cuentan (los conos pueden ir juntos)."""
    es_cono = es_cono or [False] * len(puntos)
    colocados: list = []
    sin_sitio: list[int] = []

    for i, q in enumerate(puntos):
        relevantes = [colocados[k] for k in range(i) if not (es_cono[i] and es_cono[k])]
        if all(_distancia(p, q) >= distancia_min for p in relevantes):
            colocados.append(q)
            continue

        cercanos = [p for p in relevantes if _distancia(p, q) < distancia_min + desplazamiento_max]
        mejor, mejor_d = None, None
        for c in _candidatos(q, cercanos, distancia_min + _MARGEN):
            c = _redondear(c)
            d = _distancia(c, q)
            if d > desplazamiento_max + _EPS or not (0 <= c[0] <= 100 and 0 <= c[1] <= 100):
                continue
            if mejor_d is not None and d >= mejor_d - _EPS:
                continue
            if all(_distancia(p, c) >= distancia_min for p in relevantes):
                mejor, mejor_d = c, d

        if mejor is None:
            sin_sitio.append(i)
            colocados.append(q)
        else:
            colocados.append(mejor)

    return colocados, sin_sitio
