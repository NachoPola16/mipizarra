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
