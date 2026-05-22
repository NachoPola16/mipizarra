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
  <path d="M0,0 L0,6 L7,3 z" fill="#16a34a"/></marker>
</defs>"""


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

    # Tacos rebote
    for d in [0.85, 1.70, 2.55]:
        ty = base_y - s * d * ESCALA
        svg.append(f'<rect x="{zona_x-6:.1f}" y="{ty-12:.1f}" width="4" height="24" fill="#2d3748"/>')
        svg.append(f'<rect x="{zona_x+zona_w+2:.1f}" y="{ty-12:.1f}" width="4" height="24" fill="#2d3748"/>')

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
        tipo = mov.get("tipo", "desplazamiento")
        de   = mov.get("de")
        if not de or de not in posiciones:
            continue
        x1, y1 = to_px(*posiciones[de])
        if tipo == "desplazamiento" and "a_pos" in mov:
            p = mov["a_pos"]
            x2, y2 = to_px(p["x"], p["y"])
            a, b, c, d2 = shorten(x1, y1, x2, y2, 26)
            svg.append(f'<line x1="{a:.1f}" y1="{b:.1f}" x2="{c:.1f}" y2="{d2:.1f}" '
                       f'stroke="#334155" stroke-width="3" stroke-dasharray="8,4" marker-end="url(#arr)"/>')
            posiciones[de] = (p["x"], p["y"])
        elif tipo == "pase":
            a2 = mov.get("a")
            if a2 in posiciones:
                x2, y2 = to_px(*posiciones[a2])
                a, b, c, d2 = shorten(x1, y1, x2, y2, 26)
                svg.append(f'<line x1="{a:.1f}" y1="{b:.1f}" x2="{c:.1f}" y2="{d2:.1f}" '
                           f'stroke="#334155" stroke-width="3" marker-end="url(#arr)"/>')
        elif tipo == "tiro":
            x2, y2 = to_px(50, 11)
            a, b, c, d2 = shorten(x1, y1, x2, y2, 14)
            svg.append(f'<line x1="{a:.1f}" y1="{b:.1f}" x2="{c:.1f}" y2="{d2:.1f}" '
                       f'stroke="#16a34a" stroke-width="3.5" marker-end="url(#arrs)"/>')
        elif tipo == "bloqueo" and "a_pos" in mov:
            p = mov["a_pos"]
            x2, y2 = to_px(p["x"], p["y"])
            a, b, c, d2 = shorten(x1, y1, x2, y2, 26)
            svg.append(f'<line x1="{a:.1f}" y1="{b:.1f}" x2="{c:.1f}" y2="{d2:.1f}" '
                       f'stroke="#dc2626" stroke-width="7"/>')


def render_diagram(data: dict, edad: str = "U16") -> str:
    tipo = data.get("tipo", "media_pista")
    if tipo == "pista_completa":
        return _render_pista_completa(data, edad)
    return _render_media_pista(data, edad)


def _render_media_pista(data: dict, edad: str) -> str:
    W = int(ANCHO_M * ESCALA)
    H = int(MEDIO_M * ESCALA)
    SVG_W = W + 2 * PAD
    SVG_H = H + 2 * PAD

    baseline_y = PAD + H
    medio_y    = PAD
    cx         = PAD + W / 2

    def to_px(xp, yp):
        return PAD + (xp/100)*W, SVG_H - PAD - (yp/100)*H

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {SVG_W} {SVG_H}">',
        ARROW_DEFS,
        f'<rect width="{SVG_W}" height="{SVG_H}" fill="#faf8f0"/>',
        # Perímetro
        f'<rect x="{PAD}" y="{PAD}" width="{W}" height="{H}" fill="none" stroke="#2d3748" stroke-width="3.5"/>',
        # Línea de medio campo
        f'<line x1="{PAD}" y1="{medio_y}" x2="{PAD+W}" y2="{medio_y}" stroke="#2d3748" stroke-width="3.5"/>',
        # Círculo central
        f'<circle cx="{cx:.1f}" cy="{medio_y}" r="{1.8*ESCALA:.1f}" fill="none" stroke="#2d3748" stroke-width="2.5"/>',
    ]

    _half_court_elements(svg, cx, baseline_y, PAD, W, edad, flip=False)
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
