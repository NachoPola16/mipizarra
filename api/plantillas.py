# api/plantillas.py
"""Plantillas de diagrama para calentamiento y vuelta a la calma.

Cada plantilla genera, sin modelo, un diagrama de media pista con el mismo JSON que
dibuja diagram_renderer.py y que acepta diagramas._validar_diagrama: jugadores a 8
unidades o más entre sí y de los conos, dentro de la pista y con ids A1..An (atacantes)
y D1..Dn (defensores, pillas). Solo depende de posiciones (no importa al validador ni
al renderer).

Uso: generar_plantilla("rondo_circular", n_jugadores=8, n_conos=4).
"""
import math
from typing import Callable, NamedTuple

from posiciones import POSICIONES_CANONICAS as POS

# Paso entre jugadores de una misma fila: algo más que el mínimo de 8 del validador.
PASO_FILA = 8.5


class Plantilla(NamedTuple):
    funcion: Callable[[int, int], dict]
    momento: str            # "calentamiento" o "vuelta_a_la_calma"
    descripcion: str
    jugadores_min: int
    jugadores_max: int
    conos_min: int
    conos_defecto: int
    conos_max: int


# ── Utilidades ───────────────────────────────────────────────────────────────

def _r(v: float) -> float:
    """Redondeo a 1 decimal (y -0.0 → 0.0) para que el JSON sea legible y estable."""
    return round(v, 1) + 0.0


def _p(x: float, y: float) -> dict:
    return {"x": _r(x), "y": _r(y)}


def _jugador(prefijo: str, n: int, x: float, y: float) -> dict:
    return {"id": f"{prefijo}{n}", **_p(x, y)}


def _repartir(n: int, filas: int) -> list[int]:
    """n jugadores en `filas` filas lo más igualadas posible (las primeras, con uno más)."""
    base, resto = divmod(n, filas)
    return [base + (1 if i < resto else 0) for i in range(filas)]


def _fila(cabeza: tuple, direccion: tuple, n: int, paso: float = PASO_FILA) -> list[tuple]:
    """n posiciones desde `cabeza` hacia `direccion` (vector, se normaliza)."""
    largo = math.hypot(*direccion) or 1.0
    ux, uy = direccion[0] / largo, direccion[1] / largo
    return [(cabeza[0] + ux * paso * k, cabeza[1] + uy * paso * k) for k in range(n)]


def _diagrama(ataque: list[tuple], defensa: list[tuple] = (), conos: list[tuple] = (),
              movimientos: list[dict] = (), portador: str | None = "A1") -> dict:
    d = {
        "tipo": "media_pista",
        "jugadores_ataque": [_jugador("A", i + 1, *p) for i, p in enumerate(ataque)],
        "jugadores_defensa": [_jugador("D", i + 1, *p) for i, p in enumerate(defensa)],
        "movimientos": [dict(m, orden=i + 1) for i, m in enumerate(movimientos)],
        "conos": [_p(*c) for c in conos],
    }
    if portador:
        d["balon_inicio"] = {"portador": portador}
    return d


def _circulo(n: int, centro: tuple, radio: float, angulo0: float = 90.0) -> list[tuple]:
    return [(centro[0] + radio * math.cos(math.radians(angulo0 + 360 * k / n)),
             centro[1] + radio * math.sin(math.radians(angulo0 + 360 * k / n))) for k in range(n)]


def _radio_minimo(n: int, minimo: float) -> float:
    """Radio para que n jugadores en círculo queden a PASO_FILA o más."""
    if n < 2:
        return minimo
    return max(minimo, PASO_FILA / (2 * math.sin(math.pi / n)))


def _bote(de: str, destino: tuple, **extra) -> dict:
    return {"de": de, "tipo": "bote", "a_pos": _p(*destino), **extra}


def _desplazamiento(de: str, destino: tuple, **extra) -> dict:
    return {"de": de, "tipo": "desplazamiento", "a_pos": _p(*destino), **extra}


def _pase(de: str, a: str) -> dict:
    return {"de": de, "tipo": "pase", "a": a}


def _tiro(de: str) -> dict:
    return {"de": de, "tipo": "tiro"}


# ── Calentamiento ────────────────────────────────────────────────────────────

def filas_esquinas(n_jugadores: int, n_conos: int) -> dict:
    """Dos filas en las esquinas de la línea de fondo, a lo largo de la banda. El primero
    de cada fila sale botando hacia el poste bajo de su lado y tira."""
    der, izq = _repartir(n_jugadores, 2)
    ataque = (_fila(POS["esquina_triple_derecha"], (0, 1), der)
              + _fila(POS["esquina_triple_izquierda"], (0, 1), izq))
    conos = [(22, 30), (78, 30)][:n_conos]
    cabeza2 = f"A{der + 1}"
    movimientos = [_bote("A1", POS["poste_bajo_derecho"]), _tiro("A1")]
    if izq:
        movimientos += [_bote(cabeza2, POS["poste_bajo_izquierdo"]), _tiro(cabeza2)]
    return _diagrama(ataque, conos=conos, movimientos=movimientos)


def circuito_conos(n_jugadores: int, n_conos: int) -> dict:
    """Conos en óvalo por la media pista y una fila en el medio campo; el primero
    recorre el circuito botando de cono en cono."""
    # Óvalo (34 x 28) recorrido en sentido horario desde arriba a la izquierda.
    conos = [(50 + 34 * math.cos(math.radians(150 - 360 * k / n_conos)),
              48 + 28 * math.sin(math.radians(150 - 360 * k / n_conos))) for k in range(n_conos)]
    paso = min(PASO_FILA, 90 / max(1, n_jugadores - 1))
    ataque = _fila((5, 94), (1, 0), n_jugadores, paso)
    movimientos = [_bote("A1", c) for c in conos]
    return _diagrama(ataque, conos=conos, movimientos=movimientos)


def rondo_circular(n_jugadores: int, n_conos: int) -> dict:
    """Rondo: atacantes en círculo pasándose el balón y uno o dos defensores dentro
    (dos a partir de 6 jugadores). Los conos marcan el cuadrado del rondo."""
    n_def = 1 if n_jugadores < 6 else 2
    n_at = n_jugadores - n_def
    centro = (50, 55)
    radio = _radio_minimo(n_at, 18)
    ataque = _circulo(n_at, centro, radio)
    defensa = [(45.5, 55), (54.5, 55)] if n_def == 2 else [centro]
    lado = radio + 9
    conos = [(centro[0] - lado, centro[1] - lado), (centro[0] + lado, centro[1] - lado),
             (centro[0] + lado, centro[1] + lado), (centro[0] - lado, centro[1] + lado)][:n_conos]
    receptor = 1 + n_at // 2
    siguiente = receptor % n_at + 1
    rx, ry = ataque[receptor - 1]
    movimientos = [
        _pase("A1", f"A{receptor}"),
        _desplazamiento("D1", ((defensa[0][0] + rx) / 2, (defensa[0][1] + ry) / 2)),
        _pase(f"A{receptor}", f"A{siguiente}"),
    ]
    return _diagrama(ataque, defensa, conos, movimientos)


def cuatro_esquinas(n_jugadores: int, n_conos: int) -> dict:
    """Cuatro conos en cuadrado con una fila detrás de cada uno: pase al siguiente
    cono (sentido contrario a las agujas) y el pasador sigue a su pase."""
    esquinas = [(25, 30), (75, 30), (75, 80), (25, 80)]
    centro = (50, 55)
    ataque, cabezas = [], []
    for esquina, n in zip(esquinas, _repartir(n_jugadores, 4)):
        hacia_fuera = (esquina[0] - centro[0], esquina[1] - centro[1])
        largo = math.hypot(*hacia_fuera)
        cabeza = (esquina[0] + hacia_fuera[0] / largo * 9, esquina[1] + hacia_fuera[1] / largo * 9)
        cabezas.append(f"A{len(ataque) + 1}")
        ataque += _fila(cabeza, hacia_fuera, n)
    movimientos = [_pase(cabezas[0], cabezas[1]), _desplazamiento(cabezas[0], esquinas[1]),
                   _pase(cabezas[1], cabezas[2])]
    return _diagrama(ataque, conos=esquinas[:n_conos], movimientos=movimientos)


def dos_filas_enfrentadas(n_jugadores: int, n_conos: int) -> dict:
    """Dos filas una frente a otra a lo ancho de la pista: pase al de enfrente y el
    pasador corre a colocarse al final de la otra fila."""
    izq, der = _repartir(n_jugadores, 2)
    paso = min(PASO_FILA, 41 / max(1, max(izq, der) - 1))
    fila1 = _fila((41, 72), (-1, 0), izq, paso)
    fila2 = _fila((59, 72), (1, 0), der, paso)
    conos = [(41, 63), (59, 63)][:n_conos]
    cabeza2 = f"A{izq + 1}"
    movimientos = [_pase("A1", cabeza2), _desplazamiento("A1", (fila2[-1][0], 82), curva=True)]
    return _diagrama(fila1 + fila2, conos=conos, movimientos=movimientos)


def zigzag_conos(n_jugadores: int, n_conos: int) -> dict:
    """Conos en zigzag del medio campo hacia el aro; el primero bota rodeando cada
    cono por fuera y termina con tiro. Una fila (dos con más de 6 jugadores)."""
    ys = [82 - k * (52 / max(1, n_conos - 1)) for k in range(n_conos)]
    conos = [(35 if k % 2 == 0 else 65, y) for k, y in enumerate(ys)]
    if n_jugadores <= 6:
        ataque = _fila((50, 95), (1, 0), n_jugadores)
    else:
        a, b = _repartir(n_jugadores, 2)
        paso = min(PASO_FILA, 41 / max(1, a - 1))
        ataque = _fila((42, 95), (-1, 0), a, paso) + _fila((58, 95), (1, 0), b, paso)
    movimientos = [_bote("A1", (x - 9 if x < 50 else x + 9, y)) for x, y in conos]
    movimientos.append(_tiro("A1"))
    return _diagrama(ataque, conos=conos, movimientos=movimientos)


# Huecos repartidos por la media pista para el pilla-pilla (los primeros, los más separados).
_HUECOS_PILLA = [(20, 30), (80, 30), (20, 80), (80, 80), (50, 25), (50, 90),
                 (8, 55), (92, 55), (32, 55), (68, 55), (35, 75), (65, 75)]
_HUECOS_PILLADORES = [(50, 60), (50, 42)]


def pilla_pilla(n_jugadores: int, n_conos: int) -> dict:
    """Pilla-pilla en media pista: uno o dos que pillan (defensores, dos a partir de 10)
    persiguen al más cercano, que escapa. Los conos marcan las esquinas del espacio."""
    n_def = 1 if n_jugadores < 10 else 2
    ataque = _HUECOS_PILLA[:n_jugadores - n_def]
    defensa = _HUECOS_PILLADORES[:n_def]
    movimientos = []
    for i, (dx, dy) in enumerate(defensa):
        objetivo = min(range(len(ataque)), key=lambda k: (math.dist((dx, dy), ataque[k]), k))
        ox, oy = ataque[objetivo]
        movimientos.append(_desplazamiento(f"D{i + 1}", (dx + (ox - dx) * 0.6, dy + (oy - dy) * 0.6)))
        # El perseguido escapa alejándose del que pilla, sin salir de la pista.
        largo = math.dist((dx, dy), (ox, oy)) or 1.0
        hx = min(95, max(5, ox + (ox - dx) / largo * 12))
        hy = min(95, max(5, oy + (oy - dy) / largo * 12))
        movimientos.append(_desplazamiento(f"A{objetivo + 1}", (hx, hy), curva=True))
    conos = [(4, 12), (96, 12), (96, 97), (4, 97)][:n_conos]
    return _diagrama(ataque, defensa, conos, movimientos, portador=None)


def pases_por_parejas(n_jugadores: int, n_conos: int) -> dict:
    """Parejas enfrentadas pasándose el balón a lo ancho de la media pista. Con número
    impar, el último se coloca detrás de su compañero y entra a la siguiente."""
    parejas = n_jugadores // 2
    xs = [50 + (k - (parejas - 1) / 2) * 14 for k in range(parejas)]
    ataque = []
    for x in xs:
        ataque += [(x, 28), (x, 52)]
    if n_jugadores % 2:
        ataque.append((xs[-1], 61))
    movimientos = [_pase(f"A{2 * k + 1}", f"A{2 * k + 2}") for k in range(parejas)]
    conos = [(xs[0] - 10, 40), (xs[-1] + 10, 40)][:n_conos]
    return _diagrama(ataque, conos=conos, movimientos=movimientos)


def rueda_de_tiro(n_jugadores: int, n_conos: int) -> dict:
    """Dos filas en los 45°, alejándose del aro: el primero bota hasta el codo de su
    lado y tira. Los conos marcan los codos."""
    der, izq = _repartir(n_jugadores, 2)
    aro = POS["canasta"]
    filas = []
    for punto, n in ((POS["45_derecho"], der), (POS["45_izquierdo"], izq)):
        filas += _fila(punto, (punto[0] - aro[0], punto[1] - aro[1]), n, 9)
    conos = [POS["codo_derecho"], POS["codo_izquierdo"]][:n_conos]
    cabeza2 = f"A{der + 1}"
    movimientos = [_bote("A1", (30, 36)), _tiro("A1")]
    if izq:
        movimientos += [_bote(cabeza2, (70, 36)), _tiro(cabeza2)]
    return _diagrama(filas, conos=conos, movimientos=movimientos)


# ── Vuelta a la calma ────────────────────────────────────────────────────────

def trote_en_circulo(n_jugadores: int, n_conos: int) -> dict:
    """Trote suave en círculo alrededor del centro de la media pista, todos en el mismo
    sentido. Los conos, si los hay, marcan el círculo por fuera."""
    centro, radio = (50, 52), _radio_minimo(n_jugadores, 30)
    ataque = _circulo(n_jugadores, centro, radio)
    medio = _circulo(2 * n_jugadores, centro, radio)[1]
    conos = _circulo(4, centro, radio + 10, 45)[:n_conos]
    movimientos = [_desplazamiento("A1", medio, curva=True)]
    return _diagrama(ataque, conos=conos, movimientos=movimientos, portador=None)


def estiramientos_en_lineas(n_jugadores: int, n_conos: int) -> dict:
    """Estiramientos en líneas de hasta cuatro, mirando al entrenador (en el medio campo).
    Sin movimientos."""
    ataque = []
    por_linea = 4
    for i in range(n_jugadores):
        linea, col = divmod(i, por_linea)
        en_linea = min(por_linea, n_jugadores - linea * por_linea)
        ataque.append((50 + (col - (en_linea - 1) / 2) * 16, 70 - linea * 15))
    conos = [(14, 70), (86, 70)][:n_conos]
    return _diagrama(ataque, conos=conos, portador=None)


def tiros_libres_rotacion(n_jugadores: int, n_conos: int) -> dict:
    """Tiros libres en rotación: uno tira desde la línea, los siguientes esperan en fila
    detrás de ella y el resto se coloca en los espacios de rebote de la zona."""
    tirador = POS["linea_tl_centro"]
    detras = _fila((tirador[0], tirador[1] + 9), (0, 1), min(n_jugadores - 1, 6), 9)
    rebote = [(33, 14), (67, 14), (33, 23), (67, 23), (33, 32)]
    ataque = [tirador] + detras + rebote[:max(0, n_jugadores - 1 - len(detras))]
    conos = [(20, 41), (80, 41)][:n_conos]
    return _diagrama(ataque, conos=conos, movimientos=[_tiro("A1")])


PLANTILLAS: dict[str, Plantilla] = {
    "filas_esquinas": Plantilla(
        filas_esquinas, "calentamiento", "Dos filas en las esquinas: bote al poste bajo y tiro.",
        2, 12, 0, 0, 2),
    "circuito_conos": Plantilla(
        circuito_conos, "calentamiento", "Circuito de conos en óvalo recorrido con bote.",
        2, 12, 3, 6, 10),
    "rondo_circular": Plantilla(
        rondo_circular, "calentamiento", "Rondo en círculo con uno o dos defensores dentro.",
        4, 12, 0, 4, 4),
    "cuatro_esquinas": Plantilla(
        cuatro_esquinas, "calentamiento", "Cuatro esquinas: pasa y sigue tu pase.",
        4, 12, 4, 4, 4),
    "dos_filas_enfrentadas": Plantilla(
        dos_filas_enfrentadas, "calentamiento", "Dos filas enfrentadas: pase y al final de la otra fila.",
        2, 12, 0, 0, 2),
    "zigzag_conos": Plantilla(
        zigzag_conos, "calentamiento", "Zigzag de conos con bote, cambio de mano y tiro.",
        2, 12, 3, 6, 8),
    "pilla_pilla": Plantilla(
        pilla_pilla, "calentamiento", "Pilla-pilla en media pista con uno o dos que pillan.",
        3, 12, 0, 4, 4),
    "pases_por_parejas": Plantilla(
        pases_por_parejas, "calentamiento", "Parejas enfrentadas pasándose el balón.",
        2, 12, 0, 0, 2),
    "rueda_de_tiro": Plantilla(
        rueda_de_tiro, "calentamiento", "Dos filas en los 45°: bote al codo y tiro.",
        2, 12, 0, 2, 2),
    "trote_en_circulo": Plantilla(
        trote_en_circulo, "vuelta_a_la_calma", "Trote suave en círculo, todos en el mismo sentido.",
        2, 12, 0, 0, 4),
    "estiramientos_en_lineas": Plantilla(
        estiramientos_en_lineas, "vuelta_a_la_calma", "Estiramientos en líneas mirando al entrenador.",
        2, 12, 0, 0, 2),
    "tiros_libres_rotacion": Plantilla(
        tiros_libres_rotacion, "vuelta_a_la_calma", "Tiros libres en rotación con rebote.",
        2, 12, 0, 0, 2),
}


def generar_plantilla(nombre: str, n_jugadores: int, n_conos: int | None = None) -> dict:
    """Diagrama de la plantilla `nombre` con n_jugadores (y n_conos, o los de por defecto).
    Lanza ValueError si la plantilla no existe o los números están fuera de su rango."""
    if nombre not in PLANTILLAS:
        raise ValueError(f"plantilla desconocida '{nombre}'; disponibles: {', '.join(sorted(PLANTILLAS))}")
    p = PLANTILLAS[nombre]
    if not p.jugadores_min <= n_jugadores <= p.jugadores_max:
        raise ValueError(f"'{nombre}' admite de {p.jugadores_min} a {p.jugadores_max} jugadores, "
                         f"no {n_jugadores}")
    if n_conos is None:
        n_conos = p.conos_defecto
    if not p.conos_min <= n_conos <= p.conos_max:
        raise ValueError(f"'{nombre}' admite de {p.conos_min} a {p.conos_max} conos, no {n_conos}")
    return p.funcion(n_jugadores, n_conos)


# ── Elección de plantilla a partir del texto que redactó el modelo ──────────
# (palabra clave en el nombre o las reglas → plantilla, en orden de prioridad)
_CLAVES = {
    "calentamiento": (
        ("pilla", "pilla_pilla"),
        ("rondo", "rondo_circular"),
        ("cuatro esquinas", "cuatro_esquinas"),
        ("4 esquinas", "cuatro_esquinas"),
        ("zigzag", "zigzag_conos"),
        ("zig-zag", "zigzag_conos"),
        ("circuito", "circuito_conos"),
        ("rueda", "rueda_de_tiro"),
        ("dos filas", "dos_filas_enfrentadas"),
        ("pareja", "pases_por_parejas"),
    ),
    "vuelta_a_la_calma": (
        ("estiramiento", "estiramientos_en_lineas"),
        ("tiros libres", "tiros_libres_rotacion"),
        ("tiro libre", "tiros_libres_rotacion"),
        ("trote", "trote_en_circulo"),
        ("caminar", "trote_en_circulo"),
        ("camina", "trote_en_circulo"),
    ),
}

N_JUGADORES_DEFECTO = 8


def plantilla_para_texto(momento: str, texto: str, n_jugadores: int = N_JUGADORES_DEFECTO) -> dict | None:
    """Diagrama de la plantilla cuyo juego describe `texto` (nombre + reglas que escribió el
    modelo), o None si ninguna encaja: entonces se queda el diagrama generado como hasta ahora.
    Sirve para que un juego estándar tenga un diagrama válido sin depender del modelo."""
    t = texto.lower()
    for clave, nombre in _CLAVES.get(momento, ()):
        if clave in t:
            p = PLANTILLAS[nombre]
            n = max(p.jugadores_min, min(p.jugadores_max, n_jugadores))
            return generar_plantilla(nombre, n)
    return None
