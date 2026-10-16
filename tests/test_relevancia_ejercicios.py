# tests/test_relevancia_ejercicios.py
"""Umbral de relevancia: un ejercicio de la biblioteca solo ocupa un hueco de la sesión si
encaja con el objetivo pedido; si no, ese hueco lo propone la IA (marcado como tal)."""
import re

import pytest

from ejercicios import es_relevante


def _ej(nombre, descripcion="", tacticos=()):
    return {"nombre": nombre, "descripcion": descripcion, "objetivos": {"tacticos": list(tacticos)}}


def test_relevante_si_el_objetivo_aparece_en_el_nombre():
    assert es_relevante(_ej("Circuito de bote en zigzag"), "bote")


def test_relevante_si_el_objetivo_aparece_en_la_descripcion_o_los_tags():
    assert es_relevante(_ej("Rueda", "Cada jugador finaliza tras bote."), "bote")
    assert es_relevante(_ej("Rueda", "", ["tiro en movimiento"]), "tiro")


def test_relevante_con_flexion_de_la_palabra():
    assert es_relevante(_ej("Defensa del 1c1 con ayudas"), "defensivo")
    assert es_relevante(_ej("Tiros libres con consecuencia"), "tiro")


def test_relevante_por_fundamentos_analiticos_del_objetivo():
    # objetivo «defensa» → fundamentos analíticos: posición, ayuda, rebote, deslizamiento, cierre
    assert es_relevante(_ej("Corte en V con cierre rápido"), "defensa")


def test_irrelevante_si_no_hay_ninguna_relacion():
    assert not es_relevante(_ej("Circuito de bote en zigzag", "Zigzag entre conos."), "contraataque")


def test_las_palabras_vacias_del_objetivo_no_cuentan():
    # «de», «el», «con»... están en cualquier descripción: no pueden dar relevancia
    assert not es_relevante(_ej("Circuito de bote", "Sale con el balón de la fila."), "trabajo de la defensa con el equipo")


def test_el_conteo_nc_m_del_objetivo_cuenta():
    assert es_relevante(_ej("1c1 desde el codo"), "1c1")
    assert not es_relevante(_ej("2c1 en transición"), "1c1")


# ── Regresión: sesión U10 de defensa «a media pista» (16-10-2026) ─────────────────────────────────
# Salió con transiciones en pista completa y pases porque palabras sueltas («pista», «jugador», «media») hacían
# relevante casi cualquier ficha y el diagrama pesaba más que el tema.
OBJETIVO_DEFENSA_MEDIA_PISTA = ("Crea un entrenamiento para trabajar defensa pero a media pista. Que estén atentos "
                                "al jugador que defienden. Ejercicios de ventaja de ataque frente a defensa")


def test_las_palabras_de_relleno_no_hacen_relevante_una_ficha():
    pase = _ej("Pase de pecho en parejas", "Pasan el balón por media pista, cada jugador atento al compañero.")
    assert not es_relevante(pase, OBJETIVO_DEFENSA_MEDIA_PISTA, con_asociados=False)


def test_defensa_en_u10_no_llena_la_sesion_de_transiciones_ni_pases(ejercicios):
    import random
    from ejercicios import elegir_fichas
    ajenas = ("pase de pecho", "rebote", "3c0", "2c0")   # una 3c2 sí encaja con «ventaja de ataque frente a defensa»
    for semilla in range(20):
        fichas = elegir_fichas([dict(e) for e in ejercicios], "U10", OBJETIVO_DEFENSA_MEDIA_PISTA, 6,
                               azar=random.Random(semilla))
        nombres = [f["nombre"].lower() for f in fichas if f]
        defensivas = [n for n in nombres if any(k in n for k in ("defens", "defiend", "espejo", "tela", "cierre",
                                                                    "1c1", "1 contra 1", "tocar el bal"))]
        assert len(defensivas) >= 4, (semilla, nombres)
        assert not [n for n in nombres if any(k in n for k in ajenas)], (semilla, nombres)
        assert sum("transici" in n or "contraataque" in n for n in nombres) <= 2, (semilla, nombres)


# ── Espacio: «a media pista» excluye las fichas de pista completa ──────────────────────────────────
def test_espacio_pedido():
    from ejercicios import espacio_pedido
    assert espacio_pedido(OBJETIVO_DEFENSA_MEDIA_PISTA) == "media_pista"
    assert espacio_pedido("defensa en medio campo") == "media_pista"
    assert espacio_pedido("defensa a pista completa") is None
    assert espacio_pedido("presión en toda la pista, no solo media pista") is None
    assert espacio_pedido("defensa") is None


def test_todas_las_fichas_tienen_espacio_valido(ejercicios):
    from validacion_fichas import ESPACIOS
    assert all(e.get("espacio") in ESPACIOS for e in ejercicios)


def test_media_pista_no_elige_fichas_de_pista_completa(ejercicios):
    import random
    from ejercicios import elegir_calentamiento, elegir_fichas
    for edad in ("U8", "U10", "U12", "U14", "U16"):
        for semilla in range(10):
            azar = random.Random(semilla)
            fichas = elegir_fichas([dict(e) for e in ejercicios], edad, OBJETIVO_DEFENSA_MEDIA_PISTA, 6, azar=azar)
            assert not [f["id"] for f in fichas if f and f["espacio"] == "pista_completa"], (edad, semilla)
            calent = elegir_calentamiento(ejercicios, edad, OBJETIVO_DEFENSA_MEDIA_PISTA, azar=azar)
            assert calent is None or calent["espacio"] != "pista_completa"


def test_sin_pedir_media_pista_si_puede_haber_fichas_de_pista_completa(ejercicios):
    import random
    from ejercicios import elegir_fichas
    vistas = set()
    for semilla in range(30):
        for f in elegir_fichas([dict(e) for e in ejercicios], "U10", "contraataque", 6, azar=random.Random(semilla)):
            if f:
                vistas.add(f["espacio"])
    assert "pista_completa" in vistas


# ── «Ventaja de ataque frente a defensa» = fichas de superioridad numérica ──────────────────────────
def test_categorias_pedidas():
    from ejercicios import categorias_pedidas
    assert categorias_pedidas("ejercicios de ventaja de ataque frente a defensa") == {"ventaja_numerica"}
    assert categorias_pedidas("trabajar la superioridad numérica") == {"ventaja_numerica"}
    assert categorias_pedidas("defensa") == set()


def test_ventaja_de_ataque_incluye_fichas_de_superioridad(ejercicios):
    import random
    from ejercicios import elegir_fichas
    for semilla in range(20):
        fichas = elegir_fichas([dict(e) for e in ejercicios], "U10", OBJETIVO_DEFENSA_MEDIA_PISTA, 6,
                               azar=random.Random(semilla))
        assert sum(f["categoria"] == "ventaja_numerica" for f in fichas if f) >= 1, semilla
        assert not [f["id"] for f in fichas if f and f["espacio"] == "pista_completa"], semilla


# ── Peticiones en lenguaje natural: la sesión trata del tema pedido ────────────────────────────────────
# (edad, minutos, objetivo, nombres/tags esperados, cuántas fichas como mínimo, nombres que no deben salir)
PETICIONES = [
    ("U12", 90, "Quiero que mejoren el tiro, sobre todo la mecánica y que tiren muchas veces",
     r"tiro|tir|bomba|mecanic|volumen|canasta", 4, r"defens|corte en v"),
    ("U8", 60, "Sesión divertida para que los más pequeños aprendan a botar con las dos manos",
     r"bote|bota|manejo|globo|aro|pelota", 3, r"bloqueo|pick"),
    ("U10", 60, "Quiero trabajar el pase y que se muevan después de pasar", r"pas|mover|hueco|cuadrado", 3,
     r"tiro libre|bloqueo"),
    ("U12", 75, "Contraataque y transición rápida, que corran las calles",
     r"contraataque|transici|calle|carril|2c1|3c2|2c0|3c0", 4, r"bloqueo directo"),
    ("U14", 90, "Defensa individual: que no pierdan de vista al jugador y se coloquen bien respecto al balón",
     r"defens|defiend|espejo|1c1|1 contra 1|desliz|cierre", 4, r"tiro libre"),
    ("U14", 90, "Trabajar el rebote, que bloqueen al rival antes de ir a por el balón",
     r"rebote", 3, r"bloqueo directo"),
    ("U10", 60, "1c1 ofensivo: que aprendan a superar al defensor con bote y finalizar",
     r"1c1|1 contra 1|penetraci|finaliz", 3, r"rebote 2c2"),
    ("U12", 90, "Superioridad numérica 2c1 y 3c2, con defensores que vuelven",
     r"2c1|3c2|2 contra 1|3 contra 2|superioridad|transici", 4, r"bote en zigzag"),
]


@pytest.mark.parametrize("edad,minutos,objetivo,esperado,minimo,vetado", PETICIONES)
def test_la_sesion_trata_del_tema_pedido(ejercicios, edad, minutos, objetivo, esperado, minimo, vetado):
    import random
    import unicodedata
    from ejercicios import elegir_fichas
    from plan_sesion import plan_de_tiempos

    def plano(t):
        return "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn")

    n = len(plan_de_tiempos(minutos, edad).duraciones)
    for semilla in range(15):
        fichas = [f for f in elegir_fichas([dict(e) for e in ejercicios], edad, objetivo, n, azar=random.Random(semilla)) if f]
        textos = [plano(f"{f['nombre']} {' '.join(f['objetivos']['tacticos'])} {f.get('subcategoria', '')}") for f in fichas]
        assert sum(bool(re.search(esperado, t)) for t in textos) >= minimo, (semilla, [f["nombre"] for f in fichas])
        assert not [f["nombre"] for f in fichas if re.search(vetado, plano(f["nombre"]))], (semilla, objetivo)


def test_pasarlo_bien_no_es_pedir_pases():
    from ejercicios import _palabras_significativas
    assert "pasen" not in _palabras_significativas("juegos para que se lo pasen bien con el balón")
    assert "pasen" in _palabras_significativas("que se pasen el balón")
