# tests/test_botes_ondulados.py
"""Los botes se dibujan con la punta de flecha orientada hacia donde va el jugador (el conversor a PNG del PDF giraba la
del marcador en las ondas) y los botes seguidos de un mismo jugador forman una sola onda continua."""
import re

from diagram_renderer import _punta_de_flecha, _unir_botes_seguidos, render_diagram

SLALOM = {
    "tipo": "media_pista",
    "jugadores_ataque": [{"id": "A1", "x": 20, "y": 80}],
    "jugadores_defensa": [],
    "conos": [{"x": 20, "y": 65}, {"x": 20, "y": 50}, {"x": 20, "y": 35}],
    "movimientos": [{"de": "A1", "tipo": "bote", "a_pos": {"x": 28, "y": 65}, "orden": 1},
                    {"de": "A1", "tipo": "bote", "a_pos": {"x": 12, "y": 50}, "orden": 2},
                    {"de": "A1", "tipo": "bote", "a_pos": {"x": 28, "y": 35}, "orden": 3}],
}


def test_la_punta_apunta_en_la_direccion_del_movimiento():
    d = _punta_de_flecha(100, 100, 0, -1)          # hacia arriba (y decrece)
    ys = [float(v) for v in re.findall(r",(-?\d+\.\d)", d)]
    assert ys[0] < min(ys[1:])                    # el vértice de la punta es el más alto


def test_los_botes_seguidos_del_mismo_jugador_se_unen_en_una_ruta():
    unidos = _unir_botes_seguidos(SLALOM["movimientos"])
    assert len(unidos) == 1 and len(unidos[0]["_ruta"]) == 3
    assert unidos[0]["a_pos"] == {"x": 28, "y": 35}
    assert len(SLALOM["movimientos"]) == 3 and "_ruta" not in SLALOM["movimientos"][0]      # no toca la entrada


def test_un_pase_al_jugador_entre_dos_botes_los_separa():
    movs = [SLALOM["movimientos"][0], {"de": "A2", "tipo": "pase", "a": "A1", "orden": 2}, SLALOM["movimientos"][1]]
    assert len(_unir_botes_seguidos(movs)) == 3


def test_el_slalom_se_dibuja_con_una_sola_flecha():
    svg = render_diagram(SLALOM, edad="U16")
    assert svg.count('class="punta"') == 1 and "marker-end" not in svg.split("</defs>")[1].split("<text")[0]
