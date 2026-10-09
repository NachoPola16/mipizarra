# api/plan_sesion.py
"""Reparto de tiempo de una sesión: cuántos ejercicios y cuánto dura cada uno.

Cada sesión tiene entre 5 y 8 ejercicios EN TOTAL (cuenta el calentamiento; la sesión acaba con un
ejercicio más de la parte principal, no con un bloque de vuelta a la calma, salvo que
CON_VUELTA_A_LA_CALMA lo vuelva a activar). Dependen de la duración y de la edad: los pequeños aguantan menos haciendo lo mismo, así
que hacen más ejercicios y más cortos. Los minutos son una guía: siempre múltiplos de 5."""
from dataclasses import dataclass

# Duración orientativa de un ejercicio de la parte principal, por edad.
BLOQUE_OBJETIVO_MINIBASKET = 10      # U8, U10, U12 (y sus nombres de categoría)
BLOQUE_OBJETIVO_U14 = 13
BLOQUE_OBJETIVO_DEFECTO = 15         # Cadete en adelante
CATEGORIAS_MINIBASKET = {"U8", "U10", "U12", "Prebenjamín", "Benjamín", "Alevín"}
CATEGORIAS_U14 = {"U14", "Infantil"}

# A veces no hace falta acabar con una vuelta a la calma: se acaba con otro ejercicio. El bloque que
# inventaba el modelo era el que más fallaba (texto movido para una vuelta a la calma y diagrama inválido).
CON_VUELTA_A_LA_CALMA = False

_BLOQUES_FIJOS = 2 if CON_VUELTA_A_LA_CALMA else 1                 # calentamiento (+ vuelta a la calma)
MIN_EJERCICIOS_PRINCIPAL = 5 - _BLOQUES_FIJOS                     # total mínimo: 5
MAX_EJERCICIOS_PRINCIPAL = 8 - _BLOQUES_FIJOS                     # total máximo: 8


@dataclass(frozen=True)
class PlanDeTiempos:
    t_calentamiento: int
    t_vuelta: int
    t_descanso: int
    duraciones: tuple[int, ...]      # minutos de cada ejercicio de la parte principal, en orden


def _redondear_5(minutos: float, minimo: int = 5) -> int:
    return max(minimo, round(minutos / 5) * 5)


def _bloque_objetivo(edad: str) -> int:
    if edad in CATEGORIAS_MINIBASKET:
        return BLOQUE_OBJETIVO_MINIBASKET
    if edad in CATEGORIAS_U14:
        return BLOQUE_OBJETIVO_U14
    return BLOQUE_OBJETIVO_DEFECTO


def plan_de_tiempos(duracion: int, edad: str) -> PlanDeTiempos:
    t_descanso = 3 if duracion >= 60 else 2
    t_calentamiento = _redondear_5(duracion / 6, minimo=10)
    t_vuelta = _redondear_5(duracion / 15, minimo=5) if CON_VUELTA_A_LA_CALMA else 0
    t_parte = duracion - t_calentamiento - t_vuelta - t_descanso
    unidades = max(1, t_parte // 5)                  # bloques de 5 min: la suma nunca pasa de la duración

    n = round(t_parte / _bloque_objetivo(edad))
    n = max(MIN_EJERCICIOS_PRINCIPAL, min(MAX_EJERCICIOS_PRINCIPAL, n))
    # ningún ejercicio baja de 10 min salvo que, así, no cupieran los 3 mínimos (sesiones cortas)
    minimo_unidades = 2 if unidades >= 2 * MIN_EJERCICIOS_PRINCIPAL else 1
    n = max(1, min(n, unidades // minimo_unidades))

    base, extra = divmod(unidades, n)
    duraciones = tuple((base + (1 if i < extra else 0)) * 5 for i in range(n))
    return PlanDeTiempos(t_calentamiento, t_vuelta, t_descanso, duraciones)
