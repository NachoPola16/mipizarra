# api/diagram_renderer.py
import math
import logging

logger = logging.getLogger(__name__)

ESCALA         = 45
ANCHO_M        = 15       # court width in meters
MEDIO_M        = 14       # half-court length in meters
PAD            = 70       # padding around the court in px
RADIO_JUGADOR  = 22

CATEGORIAS_MINI = ["U8", "U10", "U12", "Prebenjamín", "Benjamín", "Alevín"]

ARROW_DEFS = """<defs>
<marker id="arr"  markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto">
  <path d="M0,0 L0,6 L7,3 z" fill="#2d3748"/></marker>
<marker id="arrs" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto">
  <path d="M0,0 L0,6 L7,3 z" fill="#15803d"/></marker>
</defs>"""


def _bezier_ctrl_pt(x1, y1, x2, y2, curvature):
    """Quadratic bezier control point offset perpendicular to the line midpoint."""
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    dx, dy = x2 - x1, y2 - y1
    L = math.sqrt(dx**2 + dy**2)
    if L < 1:
        return mx, my
    px, py = -dy / L, dx / L   # perpendicular unit vector (left of direction)
    return mx + curvature * px, my + curvature * py


def _wavy_path(x1, y1, x2, y2, amplitude=12.0, cx=None, cy=None):
    """
    SVG path string for a sinusoidal wave from (x1,y1) to (x2,y2).
    If cx,cy given the wave follows the quadratic bezier through that control point.
    The last half-arc's control point sits on the axis so orient="auto" on
    marker-end points in the correct forward direction.
    """
    if cx is None:
        def _pos(t):
            return x1 + t * (x2 - x1), y1 + t * (y2 - y1)
        def _tang(_):
            dx, dy = x2 - x1, y2 - y1
            L = math.sqrt(dx**2 + dy**2) or 1.0
            return dx / L, dy / L
    else:
        def _pos(t):
            bx = (1 - t)**2 * x1 + 2 * (1 - t) * t * cx + t**2 * x2
            by = (1 - t)**2 * y1 + 2 * (1 - t) * t * cy + t**2 * y2
            return bx, by
        def _tang(t):
            tdx = 2 * (1 - t) * (cx - x1) + 2 * t * (x2 - cx)
            tdy = 2 * (1 - t) * (cy - y1) + 2 * t * (y2 - cy)
            L = math.sqrt(tdx**2 + tdy**2) or 1.0
            return tdx / L, tdy / L

    N_ARC = 20
    arc = sum(
        math.sqrt(
            (_pos((i + 1) / N_ARC)[0] - _pos(i / N_ARC)[0])**2 +
            (_pos((i + 1) / N_ARC)[1] - _pos(i / N_ARC)[1])**2
        )
        for i in range(N_ARC)
    )

    n_waves = max(2, round(arc / 35))
    n_segs  = n_waves * 2   # 2 quadratic half-arcs per full wave

    p0x, p0y = _pos(0)
    parts = [f"M {p0x:.1f},{p0y:.1f}"]

    for i in range(n_segs):
        t_end = (i + 1) / n_segs
        t_mid = (i + 0.5) / n_segs
        ex, ey = _pos(t_end)

        if i == n_segs - 1:
            cp_x, cp_y = _pos(t_mid)   # on-axis → arrowhead aligned with direction
        else:
            amp = amplitude if i % 2 == 0 else -amplitude
            tang_x, tang_y = _tang(t_mid)
            mx, my = _pos(t_mid)
            cp_x = mx + amp * (-tang_y)
            cp_y = my + amp * tang_x

        parts.append(f"Q {cp_x:.1f},{cp_y:.1f} {ex:.1f},{ey:.1f}")

    return " ".join(parts)


def _half_court_elements(svg: list, cx: float, base_y: float, pad_x: float,
                          width: float, edad: str, flip: bool = False) -> None:
    """Añade los elementos de media pista al SVG (zona, TL, triple, aro).
    flip=True dibuja el extremo superior (defensa) con eje Y invertido."""
    s = -1 if flip else 1   # sign for vertical offsets from baseline

    zona_w = 4.9 * ESCALA
    zona_h = 5.8 * ESCALA
    zona_x = cx - zona_w / 2
    zona_y = base_y - s * zona_h
    tl_y   = zona_y

    # Zona pintada
    if flip:
        svg.append(f'<rect x="{zona_x:.1f}" y="{zona_y:.1f}" width="{zona_w:.1f}" '
                   f'height="{zona_h:.1f}" fill="none" stroke="#2d3748" stroke-width="2.5"/>')
    else:
        svg.append(f'<rect x="{zona_x:.1f}" y="{zona_y:.1f}" width="{zona_w:.1f}" '
                   f'height="{zona_h:.1f}" fill="none" stroke="#2d3748" stroke-width="2.5"/>')

    # Línea TL
    svg.append(f'<line x1="{zona_x:.1f}" y1="{tl_y:.1f}" '
               f'x2="{zona_x+zona_w:.1f}" y2="{tl_y:.1f}" stroke="#2d3748" stroke-width="2.5"/>')

    # Semicírculos TL
    r_tl = 1.8 * ESCALA
    sw0, sw1 = ("0 0 0", "0 0 1") if not flip else ("0 0 1", "0 0 0")
    svg.append(f'<path d="M {zona_x:.1f},{tl_y:.1f} A {r_tl:.1f},{r_tl:.1f} {sw0} {zona_x+zona_w:.1f},{tl_y:.1f}" '
               f'fill="none" stroke="#2d3748" stroke-width="2.5"/>')
    svg.append(f'<path d="M {zona_x:.1f},{tl_y:.1f} A {r_tl:.1f},{r_tl:.1f} {sw1} {zona_x+zona_w:.1f},{tl_y:.1f}" '
               f'fill="none" stroke="#2d3748" stroke-width="2" stroke-dasharray="6,4"/>')

    # Canasta
    canasta_y = base_y - s * 1.575 * ESCALA
    svg.append(f'<rect x="{cx-40:.1f}" y="{base_y - s*6:.1f}" width="80" height="{s*6:.1f}" fill="#1a202c"/>')
    svg.append(f'<circle cx="{cx:.1f}" cy="{canasta_y:.1f}" r="13" fill="none" stroke="#e53e3e" stroke-width="3.5"/>')

    # Tacos rebote — simétricos: ambos pegados al exterior de la línea del área
    for d in [0.85, 1.70, 2.55]:
        ty = base_y - s * d * ESCALA
        svg.append(f'<rect x="{zona_x-5:.1f}" y="{ty-12:.1f}" width="5" height="24" fill="#2d3748"/>')
        svg.append(f'<rect x="{zona_x+zona_w:.1f}" y="{ty-12:.1f}" width="5" height="24" fill="#2d3748"/>')

    # Triple FIBA (siempre, todas las categorías)
    r3  = 6.75 * ESCALA
    ex  = 0.9 * ESCALA
    exl = pad_x + ex
    exr = pad_x + width - ex
    dx  = width / 2 - ex
    dy  = math.sqrt(max(0, r3**2 - dx**2))
    ey  = canasta_y - s * dy
    arc_sw = "0 0 1" if not flip else "0 0 0"
    svg.append(f'<path d="M {exl:.1f},{ey:.1f} A {r3:.1f},{r3:.1f} {arc_sw} {exr:.1f},{ey:.1f}" '
               f'fill="none" stroke="#2d3748" stroke-width="2.5"/>')
    svg.append(f'<line x1="{exl:.1f}" y1="{ey:.1f}" x2="{exl:.1f}" y2="{base_y:.1f}" stroke="#2d3748" stroke-width="2.5"/>')
    svg.append(f'<line x1="{exr:.1f}" y1="{ey:.1f}" x2="{exr:.1f}" y2="{base_y:.1f}" stroke="#2d3748" stroke-width="2.5"/>')
    logger.info("  → Triple FIBA 6.75m")

    # Triple Minibasket (solo Alevín e inferiores: U8, U10, U12)
    if edad in CATEGORIAS_MINI:
        hw    = 4.0 * ESCALA
        ch    = 4.6 * ESCALA
        ml_x  = cx - hw
        mr_x  = cx + hw
        top_y = base_y - s * ch
        svg.append(f'<line x1="{ml_x:.0f}" y1="{base_y:.0f}" x2="{ml_x:.0f}" y2="{top_y:.0f}" '
                   f'stroke="#2d3748" stroke-width="2.5"/>')
        svg.append(f'<line x1="{mr_x:.0f}" y1="{base_y:.0f}" x2="{mr_x:.0f}" y2="{top_y:.0f}" '
                   f'stroke="#2d3748" stroke-width="2.5"/>')
        arc_sw_mini = "0 0 1" if not flip else "0 0 0"
        svg.append(f'<path d="M {ml_x:.0f},{top_y:.0f} A {hw:.0f},{hw:.0f} {arc_sw_mini} {mr_x:.0f},{top_y:.0f}" '
                   f'fill="none" stroke="#2d3748" stroke-width="2.5"/>')
        logger.info("  → Triple MINIBASKET (4m, 4.6m corner)")


def _draw_players_and_moves(svg: list, data: dict, to_px) -> None:
    posiciones = {}

    for j in data.get("jugadores_ataque", []):
        jid = j["id"]
        x, y = to_px(j["x"], j["y"])
        posiciones[jid] = (j["x"], j["y"])
        svg.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{RADIO_JUGADOR}" fill="#ffffff" stroke="#1a202c" stroke-width="3"/>')
        svg.append(f'<text x="{x:.1f}" y="{y+7:.1f}" text-anchor="middle" font-size="15" font-weight="bold" fill="#1a202c">{jid}</text>')

    for j in data.get("jugadores_defensa", []):
        jid = j["id"]
        x, y = to_px(j["x"], j["y"])
        posiciones[jid] = (j["x"], j["y"])
        t = RADIO_JUGADOR * 1.7
        svg.append(f'<rect x="{x-t/2:.1f}" y="{y-t/2:.1f}" width="{t:.1f}" height="{t:.1f}" '
                   f'fill="#1a202c" stroke="#ffffff" stroke-width="3" rx="5"/>')
        svg.append(f'<text x="{x:.1f}" y="{y+7:.1f}" text-anchor="middle" font-size="15" font-weight="bold" fill="#ffffff">{jid}</text>')

    if "balon_inicio" in data:
        portador = data["balon_inicio"].get("portador")
        if portador in posiciones:
            bx, by = to_px(*posiciones[portador])
            svg.append(f'<circle cx="{bx+28:.1f}" cy="{by-28:.1f}" r="11" fill="#ff8c00" stroke="#1a202c" stroke-width="2"/>')

    for cono in data.get("conos", []):
        cx, cy = to_px(cono["x"], cono["y"])
        svg.append(f'<polygon points="{cx:.0f},{cy-16:.0f} {cx-10:.0f},{cy+10:.0f} {cx+10:.0f},{cy+10:.0f}" '
                   f'fill="#fbbf24" stroke="#1a202c" stroke-width="1.5"/>')

    def shorten(x1, y1, x2, y2, d):
        dx, dy = x2-x1, y2-y1
        L = math.sqrt(dx**2+dy**2)
        if L < d:
            return x1, y1, x2, y2
        r = (L-d)/L
        return x1, y1, x1+dx*r, y1+dy*r

    movimientos = sorted(data.get("movimientos", []), key=lambda m: m.get("orden", 0))
    for mov in movimientos:
        tipo      = mov.get("tipo", "desplazamiento")
        de        = mov.get("de")
        curva_raw = mov.get("curva", False)
        if not de or de not in posiciones:
            continue

        curvature = None
        if curva_raw is True:
            curvature = 50.0
        elif curva_raw and isinstance(curva_raw, (int, float)):
            curvature = float(curva_raw)

        x1, y1 = to_px(*posiciones[de])

        if tipo in ("desplazamiento", "bote") and "a_pos" in mov:
            p = mov["a_pos"]
            x2, y2 = to_px(p["x"], p["y"])
            a, b, c, d2 = shorten(x1, y1, x2, y2, 26)
            if tipo == "bote":
                if curvature is not None:
                    cx_ctrl, cy_ctrl = _bezier_ctrl_pt(a, b, c, d2, curvature)
                    path_d = _wavy_path(a, b, c, d2, cx=cx_ctrl, cy=cy_ctrl)
                else:
                    path_d = _wavy_path(a, b, c, d2)
                svg.append(f'<path d="{path_d}" fill="none" stroke="#334155" stroke-width="3" '
                           f'marker-end="url(#arr)"/>')
            else:  # desplazamiento — solid line
                if curvature is not None:
                    cx_ctrl, cy_ctrl = _bezier_ctrl_pt(a, b, c, d2, curvature)
                    path_d = f"M {a:.1f},{b:.1f} Q {cx_ctrl:.1f},{cy_ctrl:.1f} {c:.1f},{d2:.1f}"
                    svg.append(f'<path d="{path_d}" fill="none" stroke="#334155" stroke-width="3" '
                               f'marker-end="url(#arr)"/>')
                else:
                    svg.append(f'<line x1="{a:.1f}" y1="{b:.1f}" x2="{c:.1f}" y2="{d2:.1f}" '
                               f'stroke="#334155" stroke-width="3" marker-end="url(#arr)"/>')
            posiciones[de] = (p["x"], p["y"])

        elif tipo == "pase":
            a2 = mov.get("a")
            if a2 in posiciones:
                x2, y2 = to_px(*posiciones[a2])
                a, b, c, d2 = shorten(x1, y1, x2, y2, 26)
                if curvature is not None:
                    cx_ctrl, cy_ctrl = _bezier_ctrl_pt(a, b, c, d2, curvature)
                    path_d = f"M {a:.1f},{b:.1f} Q {cx_ctrl:.1f},{cy_ctrl:.1f} {c:.1f},{d2:.1f}"
                    svg.append(f'<path d="{path_d}" fill="none" stroke="#334155" stroke-width="3" '
                               f'stroke-dasharray="8,4" marker-end="url(#arr)"/>')
                else:
                    svg.append(f'<line x1="{a:.1f}" y1="{b:.1f}" x2="{c:.1f}" y2="{d2:.1f}" '
                               f'stroke="#334155" stroke-width="3" stroke-dasharray="8,4" '
                               f'marker-end="url(#arr)"/>')

        elif tipo == "tiro":
            x2, y2 = to_px(50, 11)
            a, b, c, d2 = shorten(x1, y1, x2, y2, 14)
            if curvature is not None:
                cx_ctrl, cy_ctrl = _bezier_ctrl_pt(a, b, c, d2, curvature)
                path_d = f"M {a:.1f},{b:.1f} Q {cx_ctrl:.1f},{cy_ctrl:.1f} {c:.1f},{d2:.1f}"
                svg.append(f'<path d="{path_d}" fill="none" stroke="#15803d" stroke-width="3.5" '
                           f'marker-end="url(#arrs)"/>')
            else:
                svg.append(f'<line x1="{a:.1f}" y1="{b:.1f}" x2="{c:.1f}" y2="{d2:.1f}" '
                           f'stroke="#15803d" stroke-width="3.5" marker-end="url(#arrs)"/>')

        elif tipo == "bloqueo" and "a_pos" in mov:
            p = mov["a_pos"]
            x2, y2 = to_px(p["x"], p["y"])
            # Línea de recorrido del bloqueador: acortada para que termine en el borde
            # del símbolo del defensor, no en su centro
            a, b, c, d2 = shorten(x1, y1, x2, y2, RADIO_JUGADOR)
            if curvature is not None:
                cx_ctrl, cy_ctrl = _bezier_ctrl_pt(a, b, c, d2, curvature)
                path_d = f"M {a:.1f},{b:.1f} Q {cx_ctrl:.1f},{cy_ctrl:.1f} {c:.1f},{d2:.1f}"
                svg.append(f'<path d="{path_d}" fill="none" stroke="#dc2626" stroke-width="2.5"/>')
            else:
                svg.append(f'<line x1="{a:.1f}" y1="{b:.1f}" x2="{c:.1f}" y2="{d2:.1f}" '
                           f'stroke="#dc2626" stroke-width="2.5"/>')
            # Barra perpendicular en el destino (la pantalla física)
            dx, dy = x2 - x1, y2 - y1
            L = math.sqrt(dx**2 + dy**2) or 1.0
            px_u, py_u = -dy / L, dx / L   # perpendicular al movimiento
            bar = 16                        # semilongitud ~0.7 m a esta escala
            svg.append(f'<line x1="{x2 - bar*px_u:.1f}" y1="{y2 - bar*py_u:.1f}" '
                       f'x2="{x2 + bar*px_u:.1f}" y2="{y2 + bar*py_u:.1f}" '
                       f'stroke="#dc2626" stroke-width="7"/>')
            # El bloqueador queda en a_pos para movimientos posteriores (rol a canasta, etc.)
            posiciones[de] = (p["x"], p["y"])


def render_diagram(data: dict, edad: str = "U16") -> str:
    tipo = data.get("tipo", "media_pista")
    if tipo == "pista_completa":
        return _render_pista_completa(data, edad)
    return _render_media_pista(data, edad)


def render_all_diagrams(ejercicio: dict, edad: str = "U16") -> list:
    """
    Devuelve una lista de dicts {titulo, svg} para un ejercicio.
    Soporta tanto 'diagrama' (objeto único) como 'diagramas' (array, cada uno con 'titulo').
    """
    if "diagramas" in ejercicio:
        result = []
        for d in ejercicio["diagramas"]:
            titulo = d.get("titulo", "")
            svg = render_diagram({k: v for k, v in d.items() if k != "titulo"}, edad)
            result.append({"titulo": titulo, "svg": svg})
        return result
    if "diagrama" in ejercicio:
        return [{"titulo": "", "svg": render_diagram(ejercicio["diagrama"], edad)}]
    return []


def _render_media_pista(data: dict, edad: str) -> str:
    pad = 30          # margen ajustado para media pista
    W = int(ANCHO_M * ESCALA)
    H = int(MEDIO_M * ESCALA)
    SVG_W = W + 2 * pad
    SVG_H = H + 2 * pad

    baseline_y = pad + H
    cx         = pad + W / 2

    def to_px(xp, yp):
        return pad + (xp/100)*W, SVG_H - pad - (yp/100)*H

    r_centro = 1.8 * ESCALA
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {SVG_W} {SVG_H}">',
        ARROW_DEFS,
        f'<rect width="{SVG_W}" height="{SVG_H}" fill="#faf8f0"/>',
        f'<rect x="{pad}" y="{pad}" width="{W}" height="{H}" fill="none" stroke="#2d3748" stroke-width="3.5"/>',
        # Solo el semiciclo inferior del centro (la mitad que queda dentro de la media pista)
        f'<path d="M {cx-r_centro:.1f},{pad} A {r_centro:.1f},{r_centro:.1f} 0 0 0 {cx+r_centro:.1f},{pad}" '
        f'fill="none" stroke="#2d3748" stroke-width="2.5"/>',
    ]

    _half_court_elements(svg, cx, baseline_y, pad, W, edad, flip=False)
    _draw_players_and_moves(svg, data, to_px)

    svg.append('</svg>')
    return "\n".join(svg)


def _render_pista_completa(data: dict, edad: str) -> str:
    W  = int(ANCHO_M * ESCALA)
    H  = int(MEDIO_M * ESCALA * 2)   # 28m full court
    SVG_W = W + 2 * PAD
    SVG_H = H + 2 * PAD

    base_bot = PAD + H       # bottom baseline (attack)
    base_top = PAD           # top baseline (defense)
    mid_y    = PAD + H // 2  # mid-court
    cx       = PAD + W / 2

    # For full court: y=0 → attack basket (bottom), y=100 → defense basket (top)
    def to_px(xp, yp):
        return PAD + (xp/100)*W, SVG_H - PAD - (yp/100)*H

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {SVG_W} {SVG_H}">',
        ARROW_DEFS,
        f'<rect width="{SVG_W}" height="{SVG_H}" fill="#faf8f0"/>',
        # Perímetro
        f'<rect x="{PAD}" y="{PAD}" width="{W}" height="{H}" fill="none" stroke="#2d3748" stroke-width="3.5"/>',
        # Línea de medio campo
        f'<line x1="{PAD}" y1="{mid_y}" x2="{PAD+W}" y2="{mid_y}" stroke="#2d3748" stroke-width="3"/>',
        # Círculo central
        f'<circle cx="{cx:.1f}" cy="{mid_y}" r="{1.8*ESCALA:.1f}" fill="none" stroke="#2d3748" stroke-width="2.5"/>',
    ]

    # Attack half (bottom, y ≈ 0–50%)
    _half_court_elements(svg, cx, base_bot, PAD, W, edad, flip=False)
    # Defense half (top, y ≈ 50–100%) — mirrored
    _half_court_elements(svg, cx, base_top, PAD, W, edad, flip=True)

    _draw_players_and_moves(svg, data, to_px)

    svg.append('</svg>')
    return "\n".join(svg)


if __name__ == "__main__":
    import sys

    # Bloqueo directo:
    # A5 sube a bloquear a D1 que defiende a A1.
    # A1 bota hacia la derecha usando el bloqueo.
    # A5 cae hacia canasta tras plantar el bloqueo.
    # A1 pasa a A5 que recibe en el poste bajo.
    _test = {
        "tipo": "media_pista",
        "jugadores_ataque": [
            {"id": "A1", "x": 50, "y": 65},   # base, cabecera con balón
            {"id": "A2", "x": 25, "y": 50},   # alero izquierdo, abre espacio
            {"id": "A5", "x": 62, "y": 36},   # pívot, poste alto izquierdo
        ],
        "jugadores_defensa": [
            {"id": "D1", "x": 48, "y": 62},   # defiende a A1
            {"id": "D5", "x": 64, "y": 34},   # defiende a A5
        ],
        "balon_inicio": {"portador": "A1"},
        "movimientos": [
            # A5 sube a plantar bloqueo sobre D1 (línea fina roja + barra perpendicular)
            {"de": "A5", "a_pos": {"x": 48, "y": 62}, "tipo": "bloqueo", "orden": 1},
            # A1 bota hacia la derecha usando el bloqueo (curva que rodea la pantalla)
            {"de": "A1", "a_pos": {"x": 65, "y": 50}, "tipo": "bote", "curva": -40, "orden": 2},
            # A5 cae hacia canasta tras plantar el bloqueo (desde a_pos del bloqueo)
            {"de": "A5", "a_pos": {"x": 62, "y": 18}, "tipo": "desplazamiento", "orden": 3},
            # A1 pasa a A5 que cae hacia canasta (pase)
            {"de": "A1", "a": "A5", "tipo": "pase", "orden": 4},
        ],
    }

    sys.stdout.write(render_diagram(_test, edad="U16") + "\n")
