# tests/test_relevancia_ejercicios.py
"""Umbral de relevancia: un ejercicio de la biblioteca solo ocupa un hueco de la sesión si
encaja con el objetivo pedido; si no, ese hueco lo propone la IA (marcado como tal)."""
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
