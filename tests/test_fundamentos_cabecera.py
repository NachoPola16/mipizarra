# tests/test_fundamentos_cabecera.py
"""FMT-01: la limpieza de la sesión corta tras la cabecera «Fundamentos», no tras la palabra suelta en una frase."""
import sesion

SESION = ("**CALENTAMIENTO (10 min)**\nJuego: Pilla-pilla\nReglas: Los fundamentos del bote se trabajan a ritmo suave.\n\n"
          "**PARTE PRINCIPAL**\n\nEjercicio 1: Bote\nDuración: 15 min\nOrganización: Parejas con un balón; repasamos "
          "fundamentos de la posición básica antes de empezar.\nPuntos clave:\n- Mirada arriba.\n- Cambio de ritmo.\n\n"
          "**Fundamentos**: bote de protección y cambio de mano.")


def test_la_palabra_en_prosa_no_corta_la_sesion():
    limpio = sesion._limpiar_respuesta(SESION)
    assert "Ejercicio 1: Bote" in limpio and "Puntos clave" in limpio
    assert limpio.rstrip().endswith("cambio de mano.")


def test_la_cabecera_sigue_cortando_lo_que_va_detras():
    sobra = SESION + "\n\nEjercicio 9: Rambling\nDuración: 5 min\n"
    assert "Rambling" not in sesion._limpiar_respuesta(sobra)
    for cab in ("**Fundamentos**: x.", "Fundamentos: x.", "FUNDAMENTOS: x."):
        limpio = sesion._limpiar_respuesta(SESION.split("**Fundamentos**")[0] + cab + "\nBasura posterior.")
        assert limpio.rstrip().endswith("x."), cab
    # cabecera sola en su línea, con el texto debajo
    limpio = sesion._limpiar_respuesta(SESION.split("**Fundamentos**")[0] + "Fundamentos\nbote y pase.\nBasura.")
    assert limpio.rstrip().endswith("bote y pase.")
