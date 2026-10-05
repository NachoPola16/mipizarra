# tests/test_lineas_rojas.py
"""Guardia de líneas rojas: el texto que genera el modelo (calentamiento, variantes,
vuelta a la calma, ejercicios propuestos) no puede incluir contenidos vetados por edad.
Criterio: data/teoria/contenidos_por_edad_lineas_rojas.md (manda sobre cualquier otro documento)."""
import pytest

from lineas_rojas import violaciones


@pytest.mark.parametrize("edad", ["U8", "U10", "U12", "Benjamín"])
@pytest.mark.parametrize("texto", [
    "Los jugadores hacen un bloqueo directo al balón.",
    "Pick and roll con el pívot.",
    "Mano a mano en el lateral.",
    "Defensa zonal 2-3 en media pista.",
    "Practican la pantalla indirecta.",
    "Trabajo de poste bajo de espaldas a canasta.",
    "Trampa defensiva 1c2 en la esquina.",
])
def test_minibasket_veta_bloqueos_zonas_y_poste(edad, texto):
    assert violaciones(texto, edad), texto


@pytest.mark.parametrize("texto", [
    "Bloqueo directo al jugador con balón.",
    "Defensa del pick and roll.",
    "Bloqueo indirecto para liberar al tirador.",
])
def test_u14_admite_el_bloqueo_directo_de_forma_puntual(texto):
    # Criterio del entrenador: en U14 el bloqueo directo puede aparecer en casos especiales
    # (según el nivel del equipo o en una jugada puntual), así que la guardia no lo veta.
    assert violaciones(texto, "U14") == []
    assert violaciones(texto, "Infantil") == []


def test_u14_sigue_vetando_lo_de_minibasket_que_no_cambia():
    # La excepción es solo el bloqueo directo; la defensa zonal en formación sigue sin ser el foco
    # pero no es línea roja de U14 (solo de minibasket): la guardia no se mete donde no hay veto.
    assert violaciones("Defensa zonal 2-3.", "U14") == []


@pytest.mark.parametrize("edad", ["U16", "U18", "Senior"])
def test_cadete_en_adelante_permite_el_bloqueo_directo(edad):
    assert violaciones("Bloqueo directo y continuación.", edad) == []


@pytest.mark.parametrize("texto", [
    "Zona pintada libre de jugadores.",
    "Bloquear al rival para el rebote.",
    "Bloqueo de rebote tras el tiro.",
    "Defensa individual presionando al balón.",
    "Juego de pies de pivote.",
])
def test_no_hay_falsos_positivos_con_lenguaje_legitimo_de_formacion(texto):
    assert violaciones(texto, "U10") == []


def test_devuelve_el_motivo_para_poder_avisar_al_modelo_en_el_reintento():
    assert any("bloqueo" in v.lower() for v in violaciones("Hacen un bloqueo directo.", "U12"))


# ── instruccion_prompt: lo mismo, dicho al modelo antes de generar ───────────

def test_instruccion_prompt_por_edad():
    from lineas_rojas import instruccion_prompt
    assert "bloqueos" in instruccion_prompt("U10") and "poste" in instruccion_prompt("U10")
    u14 = instruccion_prompt("U14")
    assert "bloqueo directo" in u14 and "puntual" in u14 and "PROHIBIDO" not in u14
    assert instruccion_prompt("U16") == ""
