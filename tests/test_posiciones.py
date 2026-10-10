# tests/test_posiciones.py
"""Posiciones con nombre (api/posiciones.py): la tabla «Posiciones canónicas» de
docs/coordenadas.md, nombres desconocidos y compatibilidad con los diagramas actuales."""
import json
import re
import unicodedata

import pytest

from conftest import EXERCISES_JSON, RAIZ
from diagram_renderer import render_all_diagrams, render_diagram
from posiciones import (
    POSICIONES_CANONICAS, PosicionDesconocida, coordenadas_de_nombre, normalizar_nombre, posicion_de,
)
from rag_engine import _validar_diagrama


def _filas_tabla_canonica() -> list[tuple[str, float, float]]:
    """(posición, x, y) de cada fila de la tabla «Posiciones canónicas (media pista)»."""
    texto = (RAIZ / "docs" / "coordenadas.md").read_text(encoding="utf-8")
    seccion = texto.split("## Posiciones canónicas", 1)[1].split("\n## ", 1)[0]
    filas = []
    for linea in seccion.splitlines():
        celdas = [c.strip() for c in linea.strip().strip("|").split("|")]
        if len(celdas) >= 3 and re.fullmatch(r"\d+", celdas[1]) and re.fullmatch(r"\d+", celdas[2]):
            filas.append((celdas[0], float(celdas[1]), float(celdas[2])))
    return filas


FILAS = _filas_tabla_canonica()


def _slug(texto: str) -> str:
    """Nombre de la fila tal como aparece en la columna «Nombre» de la tabla."""
    sin_tildes = unicodedata.normalize("NFKD", texto)
    sin_tildes = "".join(c for c in sin_tildes if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", "_", sin_tildes).strip("_")


def test_la_tabla_de_la_documentacion_tiene_todas_las_filas():
    assert len(FILAS) == 22


def test_el_diccionario_tiene_exactamente_las_filas_de_la_tabla():
    coordenadas_doc = sorted((x, y) for _, x, y in FILAS)
    assert sorted(POSICIONES_CANONICAS.values()) == coordenadas_doc


@pytest.mark.parametrize("fila, x, y", FILAS, ids=[f[0] for f in FILAS])
def test_cada_nombre_de_la_tabla_se_resuelve(fila, x, y):
    # El nombre del código aparece entre comillas invertidas en la fila de la tabla.
    texto = (RAIZ / "docs" / "coordenadas.md").read_text(encoding="utf-8")
    linea = next(l for l in texto.splitlines() if l.strip().startswith(f"| {fila}"))
    nombre = re.search(r"`([a-z0-9_]+)`", linea)
    assert nombre, f"la fila «{fila}» no indica su nombre en el código"
    assert coordenadas_de_nombre(nombre.group(1)) == (x, y)
    assert POSICIONES_CANONICAS[nombre.group(1)] == (x, y)


@pytest.mark.parametrize("entrada", [
    "codo_derecho", "Codo derecho", "  CODO-DERECHO ", "codo derecho",
])
def test_nombre_normalizado(entrada):
    assert normalizar_nombre(entrada) == "codo_derecho"
    assert coordenadas_de_nombre(entrada) == (35, 41)


def test_tildes_y_simbolos_se_normalizan():
    assert coordenadas_de_nombre("Línea de fondo centro") == (50, 5)
    assert coordenadas_de_nombre("45° derecho") == (25, 50)


def test_ejemplos_de_la_peticion():
    assert coordenadas_de_nombre("codo_derecho") == (35, 41)
    assert coordenadas_de_nombre("poste_bajo_izquierdo") == (62, 18)


@pytest.mark.parametrize("nombre", ["codo_central", "esquina", "", "A1", "poste bajo"])
def test_nombre_desconocido_da_error_claro(nombre):
    with pytest.raises(PosicionDesconocida) as exc:
        coordenadas_de_nombre(nombre)
    mensaje = str(exc.value)
    assert "posición desconocida" in mensaje
    assert repr(nombre) in mensaje or f"'{nombre}'" in mensaje


def test_nombre_desconocido_sugiere_el_parecido():
    with pytest.raises(PosicionDesconocida) as exc:
        coordenadas_de_nombre("codo_derecha")
    assert "codo_derecho" in str(exc.value)


def test_posicion_desconocida_es_value_error():
    assert issubclass(PosicionDesconocida, ValueError)


def test_pista_completa_usa_la_mitad_de_ataque():
    # La tabla es de media pista (y=100 → medio campo); en pista completa el medio campo es y=50.
    assert coordenadas_de_nombre("codo_derecho", "pista_completa") == (35, 20.5)
    assert coordenadas_de_nombre("centro_medio_campo", "pista_completa") == (50, 50)
    assert coordenadas_de_nombre("codo_derecho", "media_pista") == (35, 41)


# ── posicion_de: {x, y}, {pos} o texto ───────────────────────────────────────

def test_posicion_de_coordenadas_numericas():
    assert posicion_de({"id": "A1", "x": 12, "y": 34}) == (12, 34)
    assert posicion_de({"x": 12.5, "y": 3}, "pista_completa") == (12.5, 3)


def test_posicion_de_nombre_en_campo_pos():
    assert posicion_de({"id": "A1", "pos": "codo_izquierdo"}) == (65, 41)


def test_posicion_de_texto():
    assert posicion_de("cabecera") == (50, 65)


def test_coordenadas_explicitas_tienen_prioridad_sobre_el_nombre():
    assert posicion_de({"x": 1, "y": 2, "pos": "cabecera"}) == (1, 2)


def test_posicion_de_sin_posicion_da_error():
    with pytest.raises(ValueError):
        posicion_de({"id": "A1"})
    with pytest.raises(PosicionDesconocida):
        posicion_de({"id": "A1", "pos": "nube"})


# ── Diagramas con posiciones por nombre ──────────────────────────────────────

DIAGRAMA_CON_NOMBRES = {
    "tipo": "media_pista",
    "jugadores_ataque": [{"id": "A1", "pos": "cabecera"}, {"id": "A2", "pos": "45_derecho"}],
    "jugadores_defensa": [{"id": "D1", "pos": "linea_tl_centro"}],
    "balon_inicio": {"portador": "A1"},
    "movimientos": [
        {"de": "A1", "a": "A2", "tipo": "pase", "orden": 1},
        {"de": "A2", "a_pos": "codo_derecho", "tipo": "bote", "orden": 2},
        {"de": "A2", "a_pos": {"pos": "poste_bajo_derecho"}, "tipo": "desplazamiento", "orden": 3},
        {"de": "A2", "tipo": "tiro", "orden": 4},
    ],
    "conos": [{"pos": "esquina_triple_izquierda"}],
}

DIAGRAMA_EQUIVALENTE_XY = {
    "tipo": "media_pista",
    "jugadores_ataque": [{"id": "A1", "x": 50, "y": 65}, {"id": "A2", "x": 25, "y": 50}],
    "jugadores_defensa": [{"id": "D1", "x": 50, "y": 41}],
    "balon_inicio": {"portador": "A1"},
    "movimientos": [
        {"de": "A1", "a": "A2", "tipo": "pase", "orden": 1},
        {"de": "A2", "a_pos": {"x": 35, "y": 41}, "tipo": "bote", "orden": 2},
        {"de": "A2", "a_pos": {"x": 38, "y": 18}, "tipo": "desplazamiento", "orden": 3},
        {"de": "A2", "tipo": "tiro", "orden": 4},
    ],
    "conos": [{"x": 94, "y": 22}],
}


@pytest.mark.parametrize("tipo", ["media_pista", "pista_completa"])
def test_render_con_nombres_igual_que_con_coordenadas(tipo):
    con_nombres = render_diagram({**DIAGRAMA_CON_NOMBRES, "tipo": tipo})
    if tipo == "media_pista":
        assert con_nombres == render_diagram(DIAGRAMA_EQUIVALENTE_XY)
    else:
        # En pista completa las y de la tabla se reducen a la mitad de ataque.
        mitad = json.loads(json.dumps(DIAGRAMA_EQUIVALENTE_XY))
        for j in mitad["jugadores_ataque"] + mitad["jugadores_defensa"] + mitad["conos"]:
            j["y"] = j["y"] / 2
        for m in mitad["movimientos"]:
            if "a_pos" in m:
                m["a_pos"]["y"] = m["a_pos"]["y"] / 2
        assert con_nombres == render_diagram({**mitad, "tipo": tipo})


def test_render_con_nombre_desconocido_da_error_claro():
    datos = json.loads(json.dumps(DIAGRAMA_CON_NOMBRES))
    datos["jugadores_ataque"][0]["pos"] = "tribuna"
    with pytest.raises(PosicionDesconocida, match="tribuna"):
        render_diagram(datos)


def test_validador_acepta_nombres():
    assert _validar_diagrama(json.loads(json.dumps(DIAGRAMA_CON_NOMBRES)), "2c1") is None


@pytest.mark.parametrize("donde", ["jugador", "cono", "a_pos"])
def test_validador_rechaza_nombre_desconocido(donde):
    datos = json.loads(json.dumps(DIAGRAMA_CON_NOMBRES))
    if donde == "jugador":
        datos["jugadores_defensa"][0]["pos"] = "banquillo"
    elif donde == "cono":
        datos["conos"][0]["pos"] = "banquillo"
    else:
        datos["movimientos"][1]["a_pos"] = "banquillo"
    error = _validar_diagrama(datos, "")
    assert error and "posición desconocida" in error and "banquillo" in error


# ── Compatibilidad con los 69 diagramas de la biblioteca ─────────────────────

with open(EXERCISES_JSON, encoding="utf-8") as _f:
    _EJERCICIOS = json.load(_f)

_DIAGRAMAS = [
    (e["id"], i, d)
    for e in _EJERCICIOS
    for i, d in enumerate(e["diagramas"] if "diagramas" in e else [e["diagrama"]] if "diagrama" in e else [])
]


def test_la_biblioteca_tiene_74_diagramas():
    assert len(_DIAGRAMAS) == 74


@pytest.mark.parametrize("id_, i, d", _DIAGRAMAS, ids=[f"{a}_{b}" for a, b, _ in _DIAGRAMAS])
def test_biblioteca_posiciones_numericas_se_leen_igual(id_, i, d):
    tipo = d.get("tipo", "media_pista")
    for p in d.get("jugadores_ataque", []) + d.get("jugadores_defensa", []) + d.get("conos", []):
        assert posicion_de(p, tipo) == (p["x"], p["y"])
    for m in d.get("movimientos", []):
        if "a_pos" in m:
            assert posicion_de(m["a_pos"], tipo) == (m["a_pos"]["x"], m["a_pos"]["y"])


@pytest.mark.parametrize("ej", [e for e in _EJERCICIOS if "diagrama" in e or "diagramas" in e],
                         ids=lambda e: e["id"])
def test_biblioteca_sigue_renderizando(ej):
    assert render_all_diagrams(ej, edad="U16")
