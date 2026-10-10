# tests/test_validacion_diagrama.py
"""Validador semántico de diagramas (_validar_diagrama) y conteo NcM del nombre."""
import copy

import pytest

from rag_engine import _extraer_conteo_nc_m, _validar_diagrama


# ── _extraer_conteo_nc_m ─────────────────────────────────────────────────────

@pytest.mark.parametrize("nombre, esperado", [
    ("1c1 desde el codo", (1, 1)),
    ("2c1 en transición", (2, 1)),
    ("3C2 con ayuda", (3, 2)),
    ("2 contra 1 desde saque de banda", (2, 1)),
    ("3 contra 3 — inversión de lado", (3, 3)),
    ("Tiro tras 3c0", (3, 0)),
    ("Juego de 5contra4", (5, 4)),
    ("Carrera + finalización 1 c 1", (1, 1)),
])
def test_conteo_nc_m_reconoce_formatos(nombre, esperado):
    assert _extraer_conteo_nc_m(nombre) == esperado


@pytest.mark.parametrize("nombre", [
    "",
    "Tiro tras bote",
    "Bloqueo directo central",
    "Rueda de pases en 3 filas",
    "Contraataque",
])
def test_conteo_nc_m_sin_patron_devuelve_none(nombre):
    assert _extraer_conteo_nc_m(nombre) is None


# ── _validar_diagrama ────────────────────────────────────────────────────────

DIAGRAMA_2C1 = {
    "tipo": "media_pista",
    "jugadores_ataque": [
        {"id": "A1", "x": 50, "y": 65},
        {"id": "A2", "x": 25, "y": 50},
    ],
    "jugadores_defensa": [
        {"id": "D1", "x": 50, "y": 45},
    ],
    "balon_inicio": {"portador": "A1"},
    "movimientos": [
        {"de": "A1", "tipo": "bote", "a_pos": {"x": 50, "y": 45}, "orden": 1},
        {"de": "A1", "tipo": "pase", "a": "A2", "orden": 2},
        {"de": "A2", "tipo": "desplazamiento", "a_pos": {"x": 20, "y": 30}, "orden": 3},
        {"de": "A2", "tipo": "tiro", "orden": 4},
    ],
    "conos": [],
}


def _diagrama():
    return copy.deepcopy(DIAGRAMA_2C1)


def test_diagrama_valido():
    assert _validar_diagrama(_diagrama(), "2c1 en media pista") is None


def test_diagrama_valido_sin_nombre_nc_m():
    # Sin patrón NcM en el nombre no se comprueba el conteo.
    assert _validar_diagrama(_diagrama(), "Pase y finalización") is None


def test_bloqueo_con_a_pos_es_valido():
    d = _diagrama()
    d["movimientos"].append({"de": "A2", "tipo": "bloqueo", "a_pos": {"x": 45, "y": 45}, "orden": 5})
    assert _validar_diagrama(d, "") is None


def test_sin_atacantes_es_invalido():
    d = _diagrama()
    d["jugadores_ataque"] = []
    assert "vacío" in _validar_diagrama(d, "")


def test_ids_repetidos_es_invalido():
    d = _diagrama()
    d["jugadores_defensa"][0]["id"] = "A2"
    assert "repetidos" in _validar_diagrama(d, "")


def test_movimiento_de_jugador_no_declarado():
    d = _diagrama()
    d["movimientos"].append({"de": "A5", "tipo": "tiro", "orden": 5})
    error = _validar_diagrama(d, "")
    assert error and "A5" in error


def test_pase_a_jugador_no_declarado():
    d = _diagrama()
    d["movimientos"][1]["a"] = "A3"
    error = _validar_diagrama(d, "")
    assert error and "pase" in error and "A3" in error


def test_portador_no_declarado():
    d = _diagrama()
    d["balon_inicio"]["portador"] = "A4"
    error = _validar_diagrama(d, "")
    assert error and "portador" in error


@pytest.mark.parametrize("tipo", ["desplazamiento", "bote", "bloqueo"])
def test_movimiento_sin_a_pos(tipo):
    d = _diagrama()
    d["movimientos"].append({"de": "A2", "tipo": tipo, "orden": 5})
    error = _validar_diagrama(d, "")
    assert error == f"movimiento '{tipo}' sin 'a_pos'"


def test_tipo_de_movimiento_desconocido():
    d = _diagrama()
    d["movimientos"].append({"de": "A2", "tipo": "pantalla", "orden": 5})
    assert "desconocido" in _validar_diagrama(d, "")


@pytest.mark.parametrize("nombre", ["3c2 con ayuda", "2 contra 2 sin bote"])
def test_conteo_no_coincide_con_nombre(nombre):
    error = _validar_diagrama(_diagrama(), nombre)
    assert error and "atacante" in error and "defensor" in error


def test_defensores_de_mas_para_el_nombre():
    d = _diagrama()
    d["jugadores_defensa"].append({"id": "D2", "x": 25, "y": 35})
    assert _validar_diagrama(copy.deepcopy(d), "2c1 en media pista") is None     # el sobrante se recorta
    assert _validar_diagrama(d, "2c2 en media pista") is None
    assert len(d["jugadores_defensa"]) == 2                                      # con 2c2 no se toca nada


# ── Jugadores de más: se recortan en vez de rechazar el diagrama ────────────────────────────

def test_1c1_con_dos_atacantes_se_recorta_al_portador_y_sus_movimientos():
    d = _diagrama()                                    # A1 con balón + A2, D1
    assert _validar_diagrama(d, "1c1 en el ala") is None
    assert [j["id"] for j in d["jugadores_ataque"]] == ["A1"]
    assert [j["id"] for j in d["jugadores_defensa"]] == ["D1"]
    # fuera el pase a A2 y todo lo de A2; se queda lo de A1
    assert [(m["de"], m["tipo"]) for m in d["movimientos"]] == [("A1", "bote")]


def test_el_recorte_conserva_al_portador_aunque_no_sea_el_primero():
    d = _diagrama()
    d["balon_inicio"]["portador"] = "A2"
    assert _validar_diagrama(d, "1c1") is None
    assert [j["id"] for j in d["jugadores_ataque"]] == ["A2"]


def test_el_recorte_conserva_al_que_mas_se_mueve_si_no_hay_portador_entre_los_sobrantes():
    d = {
        "tipo": "media_pista",
        "jugadores_ataque": [{"id": "A1", "x": 20, "y": 60}, {"id": "A2", "x": 50, "y": 60},
                             {"id": "A3", "x": 80, "y": 60}],
        "jugadores_defensa": [{"id": "D1", "x": 50, "y": 45}],
        "balon_inicio": {"portador": "D1"},
        "movimientos": [
            {"de": "A3", "tipo": "desplazamiento", "a_pos": {"x": 70, "y": 40}, "orden": 1},
            {"de": "A3", "tipo": "tiro", "orden": 2},
            {"de": "A1", "tipo": "desplazamiento", "a_pos": {"x": 30, "y": 40}, "orden": 3},
        ],
        "conos": [],
    }
    assert _validar_diagrama(d, "1c1") is None
    assert [j["id"] for j in d["jugadores_ataque"]] == ["A3"]


def test_el_recorte_no_deja_movimientos_de_jugadores_quitados():
    d = _diagrama()
    d["jugadores_defensa"].append({"id": "D2", "x": 25, "y": 35})
    d["movimientos"].append({"de": "D2", "tipo": "desplazamiento", "a_pos": {"x": 30, "y": 30}, "orden": 5})
    assert _validar_diagrama(d, "2c1") is None
    ids = {j["id"] for j in d["jugadores_ataque"] + d["jugadores_defensa"]}
    assert all(m["de"] in ids for m in d["movimientos"])


def test_2c0_recorta_el_defensor():
    d = _diagrama()
    assert _validar_diagrama(d, "2c0") is None
    assert d["jugadores_defensa"] == []


def test_si_faltan_jugadores_no_se_inventan():
    d = _diagrama()
    error = _validar_diagrama(d, "3c1")
    assert error and "atacante" in error
    assert len(d["jugadores_ataque"]) == 2


def _dist(p, q):
    return ((p["x"] - q["x"]) ** 2 + (p["y"] - q["y"]) ** 2) ** 0.5


def test_jugadores_demasiado_cerca_se_separan():
    d = _diagrama()
    # A1 en (50, 65): D1 a ~5 unidades → por debajo del mínimo de 8. Hay sitio:
    # el validador separa a D1 lo mínimo (A1 no se mueve) y el diagrama es válido.
    d["jugadores_defensa"][0].update({"x": 53, "y": 61})
    assert _validar_diagrama(d, "") is None
    a1, d1 = d["jugadores_ataque"][0], d["jugadores_defensa"][0]
    assert (a1["x"], a1["y"]) == (50, 65)
    assert 8 <= _dist(a1, d1) < 8.05
    assert _dist(d1, {"x": 53, "y": 61}) < 3.1


def test_atacantes_demasiado_cerca_entre_si_se_separan():
    d = _diagrama()
    d["jugadores_ataque"][1].update({"x": 47, "y": 60})
    assert _validar_diagrama(d, "") is None
    assert _dist(d["jugadores_ataque"][0], d["jugadores_ataque"][1]) >= 8


def test_separacion_del_validador_es_determinista():
    d1, d2 = _diagrama(), _diagrama()
    for d in (d1, d2):
        d["jugadores_defensa"][0].update({"x": 50, "y": 65})   # encima de A1
        _validar_diagrama(d, "")
    assert d1 == d2


def test_jugadores_demasiado_cerca_sin_sitio_sigue_siendo_invalido():
    # Retícula 3x3 de atacantes con paso 8 y un defensor en el centro de una celda:
    # no hay hueco a menos de 8 unidades → se mantiene el error y no se toca nada.
    d = _diagrama()
    d["jugadores_ataque"] = [{"id": f"A{i + 1}", "x": x, "y": y}
                             for i, (x, y) in enumerate((x, y) for y in (42, 50, 58) for x in (42, 50, 58))]
    d["jugadores_defensa"] = [{"id": "D1", "x": 46, "y": 46}]
    d["movimientos"] = []
    antes = copy.deepcopy(d)
    error = _validar_diagrama(d, "")
    assert error and "demasiado cerca" in error
    assert d == antes


def test_distancia_exactamente_en_el_minimo_es_valida():
    d = _diagrama()
    # D1 a exactamente 8 unidades de A1 (y 65 → 57) y lejos de A2.
    d["jugadores_defensa"][0].update({"x": 50, "y": 57})
    assert _validar_diagrama(d, "") is None
    assert d == {**_diagrama(), "jugadores_defensa": [{"id": "D1", "x": 50, "y": 57}]}


def test_diagrama_valido_no_se_modifica():
    d = _diagrama()
    assert _validar_diagrama(d, "2c1") is None
    assert d == DIAGRAMA_2C1


# ── Reparación determinista de a_pos ─────────────────────────────────────────

@pytest.mark.parametrize("tipo", ["desplazamiento", "bote", "bloqueo"])
def test_a_pos_desde_nombre_de_posicion_en_a(tipo):
    d = _diagrama()
    d["movimientos"].append({"de": "A2", "tipo": tipo, "a": "codo_derecho", "orden": 5})
    assert _validar_diagrama(d, "") is None
    mov = d["movimientos"][-1]
    assert mov["a_pos"] == {"x": 35, "y": 41}
    assert "a" not in mov


def test_a_pos_desde_nombre_en_pista_completa():
    d = _diagrama()
    d["tipo"] = "pista_completa"
    d["movimientos"].append({"de": "A2", "tipo": "bote", "a": "Codo derecho", "orden": 5})
    assert _validar_diagrama(d, "") is None
    assert d["movimientos"][-1]["a_pos"] == {"x": 35, "y": 20.5}


def test_a_pos_desde_coordenadas_en_a():
    d = _diagrama()
    d["movimientos"].append({"de": "A2", "tipo": "desplazamiento", "a": {"x": 30, "y": 20}, "orden": 5})
    assert _validar_diagrama(d, "") is None
    assert d["movimientos"][-1]["a_pos"] == {"x": 30, "y": 20}


def test_bloqueo_sobre_defensor_toma_su_posicion_actual():
    d = _diagrama()
    # D1 se desplaza antes del bloqueo: el bloqueo va a donde está D1 en ese momento.
    d["movimientos"].insert(0, {"de": "D1", "tipo": "desplazamiento", "a_pos": {"x": 40, "y": 40}, "orden": 0})
    d["movimientos"].append({"de": "A2", "tipo": "bloqueo", "a": "D1", "orden": 5})
    assert _validar_diagrama(d, "") is None
    assert d["movimientos"][-1]["a_pos"] == {"x": 40, "y": 40}


def test_bloqueo_sobre_defensor_sin_moverse_toma_su_posicion_inicial():
    d = _diagrama()
    d["movimientos"].append({"de": "A2", "tipo": "bloqueo", "a": "D1", "orden": 5})
    assert _validar_diagrama(d, "") is None
    assert d["movimientos"][-1]["a_pos"] == {"x": 50, "y": 45}


@pytest.mark.parametrize("tipo", ["desplazamiento", "bote"])
def test_bote_o_desplazamiento_hacia_un_jugador_no_se_inventa(tipo):
    # Botar «hacia A1» no dice dónde termina: no es seguro inferirlo.
    d = _diagrama()
    d["movimientos"].append({"de": "A2", "tipo": tipo, "a": "A1", "orden": 5})
    assert _validar_diagrama(d, "") == f"movimiento '{tipo}' sin 'a_pos'"


def test_bloqueo_sobre_companero_no_se_inventa():
    d = _diagrama()
    d["movimientos"].append({"de": "A2", "tipo": "bloqueo", "a": "A1", "orden": 5})
    assert _validar_diagrama(d, "") == "movimiento 'bloqueo' sin 'a_pos'"


@pytest.mark.parametrize("tipo", ["desplazamiento", "bote", "bloqueo"])
def test_a_pos_desde_el_inicio_del_siguiente_movimiento_del_mismo_jugador(tipo):
    d = _diagrama()
    d["movimientos"] += [
        {"de": "A2", "tipo": tipo, "orden": 5},
        {"de": "A1", "tipo": "desplazamiento", "a_pos": {"x": 70, "y": 70}, "desde": {"x": 1, "y": 1}, "orden": 6},
        {"de": "A2", "tipo": "tiro", "desde": {"x": 30, "y": 25}, "orden": 7},
    ]
    assert _validar_diagrama(d, "") is None
    assert d["movimientos"][4]["a_pos"] == {"x": 30, "y": 25}


def test_inicio_del_siguiente_movimiento_por_nombre():
    d = _diagrama()
    d["movimientos"] += [
        {"de": "A2", "tipo": "bote", "orden": 5},
        {"de": "A2", "tipo": "tiro", "desde": "poste_bajo_derecho", "orden": 6},
    ]
    assert _validar_diagrama(d, "") is None
    assert d["movimientos"][4]["a_pos"] == {"x": 38, "y": 18}


def test_siguiente_movimiento_sin_inicio_no_repara():
    d = _diagrama()
    d["movimientos"] += [
        {"de": "A2", "tipo": "bote", "orden": 5},
        {"de": "A2", "tipo": "tiro", "orden": 6},
    ]
    assert _validar_diagrama(d, "") == "movimiento 'bote' sin 'a_pos'"


def test_orden_por_campo_orden_no_por_lista():
    # El siguiente movimiento se busca por 'orden', no por posición en la lista.
    d = _diagrama()
    d["movimientos"] += [
        {"de": "A2", "tipo": "tiro", "desde": {"x": 90, "y": 90}, "orden": 9},
        {"de": "A2", "tipo": "bote", "orden": 5},
        {"de": "A2", "tipo": "tiro", "desde": {"x": 30, "y": 25}, "orden": 6},
    ]
    assert _validar_diagrama(d, "") is None
    assert d["movimientos"][5]["a_pos"] == {"x": 30, "y": 25}


def test_a_con_nombre_desconocido_mantiene_el_error():
    d = _diagrama()
    d["movimientos"].append({"de": "A2", "tipo": "bote", "a": "nube", "orden": 5})
    assert _validar_diagrama(d, "") == "movimiento 'bote' sin 'a_pos'"
