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


# ── negación: decir que algo NO se trabaja no es trabajarlo ──────────────────

@pytest.mark.parametrize("texto", [
    "Sin bloqueos ni pantallas: es un ejercicio individual.",
    "No se trabaja la defensa zonal en esta categoría.",
    "Evitar el mano a mano y los bloqueos.",
    "Nunca se utilizan pantallas en minibasket.",
    "Está prohibido el bloqueo directo en esta etapa.",
    "No hay bloqueos, pantallas ni defensa zonal.",
    "Trabajo de 1c1 sin bloqueos.",
])
def test_negar_un_contenido_vetado_no_es_trabajarlo(texto):
    assert violaciones(texto, "U12") == [], texto


@pytest.mark.parametrize("texto", [
    "Primero hacen un bloqueo directo y después tiran.",
    "No paran de moverse. Después hacen una pantalla.",       # la negación es de otra frase
    "Defensa zonal 2-3 durante cinco minutos.",
])
def test_si_el_contenido_se_trabaja_de_verdad_sigue_detectandose(texto):
    assert violaciones(texto, "U12"), texto


# ── lo que pide expresamente el entrenador se hace, con aviso ────────────────

from lineas_rojas import aviso_pedido, instruccion_prompt, terminos_pedidos  # noqa: E402


def test_terminos_pedidos_detecta_lo_vetado_que_pide_el_entrenador():
    t = terminos_pedidos("añade un bloqueo directo y una defensa zonal", "U12")
    assert "bloqueo" in t and "defensa zonal" in t


def test_terminos_pedidos_ignora_lo_negado_y_las_edades_sin_veto():
    assert terminos_pedidos("hazlo sin bloqueos", "U12") == []
    assert terminos_pedidos("añade un bloqueo directo", "U16") == []


def test_lo_permitido_no_cuenta_como_violacion_pero_lo_demas_si():
    texto = "Hacen un bloqueo directo y defensa zonal 2-3."
    assert violaciones(texto, "U12", permitidos=["bloqueo"]) == [m for m in violaciones(texto, "U12") if "bloqueo" not in m]
    assert not any("bloqueo" in m for m in violaciones(texto, "U12", permitidos=["bloqueo"]))
    assert any("zonal" in m for m in violaciones(texto, "U12", permitidos=["bloqueo"]))


def test_el_aviso_dice_que_se_hace_porque_lo_pide_y_que_no_es_habitual():
    aviso = aviso_pedido(["bloqueo"], "U12")
    assert "bloqueo" in aviso and "U12" in aviso and "pides" in aviso.lower() and "habitual" in aviso.lower()


def test_el_prompt_con_excepcion_sigue_prohibiendo_el_resto():
    texto = instruccion_prompt("U12", permitidos=["bloqueo"])
    assert "PROHIBIDO" in texto and "EXCEPCIÓN" in texto and "bloqueo" in texto
