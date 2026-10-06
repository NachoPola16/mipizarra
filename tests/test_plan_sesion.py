# tests/test_plan_sesion.py
"""Reparto de tiempo de una sesión: cuántos ejercicios y cuánto dura cada uno.

Requisito del entrenador: cada sesión tiene entre 5 y 8 ejercicios EN TOTAL (cuentan el
calentamiento y la vuelta a la calma), según la duración y la edad. Los minutos son una guía:
múltiplos de 5."""
import pytest

from plan_sesion import plan_de_tiempos

EDADES = ["U8", "U10", "U12", "U14", "U16", "U18", "Senior"]
DURACIONES = list(range(45, 181, 5))


def _total(plan):
    return len(plan.duraciones) + 2          # + calentamiento + vuelta a la calma


@pytest.mark.parametrize("edad", EDADES)
@pytest.mark.parametrize("duracion", DURACIONES)
def test_el_total_de_ejercicios_esta_entre_5_y_8(edad, duracion):
    assert 5 <= _total(plan_de_tiempos(duracion, edad)) <= 8, (edad, duracion)


@pytest.mark.parametrize("edad", EDADES)
@pytest.mark.parametrize("duracion", DURACIONES)
def test_los_minutos_son_multiplos_de_5_y_desde_60_min_ningun_ejercicio_baja_de_10(edad, duracion):
    plan = plan_de_tiempos(duracion, edad)
    for t in [plan.t_calentamiento, plan.t_vuelta, *plan.duraciones]:
        assert t % 5 == 0 and t >= 5
    if duracion >= 60:      # en sesiones cortas, los bloques bajan a 5 min antes que perder ejercicios
        assert all(t >= 10 for t in plan.duraciones), (edad, duracion, plan.duraciones)


@pytest.mark.parametrize("edad", EDADES)
@pytest.mark.parametrize("duracion", DURACIONES)
def test_la_suma_de_tiempos_no_pasa_de_la_duracion_ni_se_queda_corta_mas_de_10_min(edad, duracion):
    plan = plan_de_tiempos(duracion, edad)
    suma = plan.t_calentamiento + plan.t_vuelta + plan.t_descanso + sum(plan.duraciones)
    assert duracion - 10 <= suma <= duracion, (edad, duracion, suma)


@pytest.mark.parametrize("edad", EDADES)
def test_mas_minutos_nunca_dan_menos_ejercicios(edad):
    totales = [_total(plan_de_tiempos(d, edad)) for d in DURACIONES]
    assert totales == sorted(totales)


@pytest.mark.parametrize("duracion", [60, 75, 90, 120])
def test_minibasket_hace_al_menos_tantos_ejercicios_como_cadete(duracion):
    # los pequeños aguantan menos haciendo lo mismo: más ejercicios y más cortos
    assert _total(plan_de_tiempos(duracion, "U10")) >= _total(plan_de_tiempos(duracion, "U16"))
    assert max(plan_de_tiempos(duracion, "U10").duraciones) <= max(plan_de_tiempos(duracion, "U16").duraciones)


def test_ejemplos_de_referencia():
    # (edad, duración) → (nº total de ejercicios, minutos de cada ejercicio de la parte principal)
    esperado = {
        ("U10", 60): (6, [10, 10, 10, 10]),
        ("U16", 60): (5, [15, 15, 10]),
        ("U10", 90): (8, [15, 10, 10, 10, 10, 10]),
        ("U16", 90): (6, [20, 15, 15, 15]),
        ("U14", 90): (7, [15, 15, 15, 10, 10]),
        ("U14", 60): (5, [15, 15, 10]),
    }
    for (edad, duracion), (total, duraciones) in esperado.items():
        plan = plan_de_tiempos(duracion, edad)
        assert (_total(plan), sorted(plan.duraciones, reverse=True)) == (total, duraciones), (edad, duracion, plan)


def test_sesion_muy_corta_hace_los_ejercicios_que_caben_y_no_se_pasa_de_tiempo():
    plan = plan_de_tiempos(30, "U12")          # 30 min no dan para 5 ejercicios: no se fuerzan
    assert len(plan.duraciones) >= 1
    assert plan.t_calentamiento + plan.t_vuelta + plan.t_descanso + sum(plan.duraciones) <= 30


def test_en_45_min_caben_tres_ejercicios_de_parte_principal():
    assert len(plan_de_tiempos(45, "U16").duraciones) == 3          # total 5, con bloques de 5 min si hace falta


def test_el_descanso_es_de_3_min_desde_60_y_de_2_antes():
    assert plan_de_tiempos(90, "U16").t_descanso == 3
    assert plan_de_tiempos(45, "U16").t_descanso == 2


@pytest.mark.parametrize("duracion", [75, 90, 105])
def test_u14_hace_menos_ejercicios_que_minibasket_y_no_menos_que_cadete(duracion):
    u10, u14, u16 = (len(plan_de_tiempos(duracion, e).duraciones) for e in ("U10", "U14", "U16"))
    assert u10 >= u14 >= u16
    assert u10 > u16
