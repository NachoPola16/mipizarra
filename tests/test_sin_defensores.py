# tests/test_sin_defensores.py
"""Un ejercicio que el texto declara sin oposición no conserva los defensores que el modelo pequeño dibuja de más."""
from diagramas import _sin_defensores_si_no_hay

DIAGRAMA = {
    "tipo": "media_pista",
    "jugadores_ataque": [{"id": "A1", "x": 40, "y": 60}, {"id": "A2", "x": 60, "y": 60}],
    "jugadores_defensa": [{"id": "D1", "x": 40, "y": 45}],
    "movimientos": [{"de": "A1", "tipo": "bote", "a_pos": {"x": 40, "y": 30}, "orden": 1},
                    {"de": "D1", "tipo": "desplazamiento", "a_pos": {"x": 40, "y": 35}, "orden": 2},
                    {"de": "A2", "tipo": "pase", "a": "D1", "orden": 3}],
}


def test_si_el_nombre_dice_sin_oposicion_se_quitan_los_defensores_y_sus_movimientos():
    d = _sin_defensores_si_no_hay(DIAGRAMA, "Espejo con bote 1c0", "Parejas enfrentadas.")
    assert d["jugadores_defensa"] == []
    assert [m["de"] for m in d["movimientos"]] == ["A1"]


def test_si_la_descripcion_dice_sin_defensor_y_no_habla_de_defensores_tambien():
    d = _sin_defensores_si_no_hay(DIAGRAMA, "Espejo con bote", "Por parejas y sin defensor: uno guía, otro copia.")
    assert d["jugadores_defensa"] == []


def test_si_el_texto_menciona_defensores_en_otro_momento_no_se_toca():
    d = _sin_defensores_si_no_hay(DIAGRAMA, "Espejo con bote", "Primero sin defensor y luego con un defensor pasivo.")
    assert d["jugadores_defensa"]


def test_un_ejercicio_con_oposicion_no_cambia():
    assert _sin_defensores_si_no_hay(DIAGRAMA, "1c1 desde el codo", "Ataca y defiende.") == DIAGRAMA
