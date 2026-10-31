# tests/test_i18n_fichas.py
"""Fichas bilingües: bloque `i18n` (traducciones) y `origen` (procedencia). El español es el texto de nivel raíz."""
import copy

import pytest

from i18n_fichas import idiomas_de, localizar
from validacion_fichas import validar_ficha

FICHA = {
    "id": "ej_901", "nombre": "Pase y recepción por parejas", "categoria": "juego_equipo",
    "edades": ["U12"], "duracion_min": 10, "intensidad": 2, "carga_cognitiva": 2,
    "objetivos": {"tacticos": ["pase y recepción"]},
    "puntos_clave": ["Mirar al compañero antes de pasar.", "Dar la mano de apoyo al recibir."],
    "descripcion": "ORGANIZACIÓN: parejas enfrentadas a tres metros, un balón por pareja. SECUENCIA: se pasan el balón "
                   "con pase de pecho y dan un paso atrás cada cinco pases. ROTACIÓN: cada minuto se cambia de pareja.",
    "errores_frecuentes": ["Pasar sin mirar."],
    "progresion": {"complicar": "Pasar con una mano."},
    "diagramas": [{"titulo": "Inicio", "tipo": "media_pista", "jugadores_ataque": [{"id": "A1", "x": 40, "y": 40}],
                   "jugadores_defensa": [], "balon_inicio": {"portador": "A1"}, "movimientos": [], "conos": []}],
    "i18n": {"en": {
        "nombre": "Partner passing and catching",
        "descripcion": "SETUP: pairs facing each other three meters apart, one ball per pair. SEQUENCE: they chest-pass "
                       "and step back after every five passes. ROTATION: switch partners every minute.",
        "puntos_clave": ["Look at your teammate before passing.", "Give the target hand when receiving."],
        "errores_frecuentes": ["Passing without looking."],
        "progresion": {"complicar": "Pass with one hand."},
        "titulos_diagramas": ["Start"],
    }},
    "origen": {"tipo": "abierta", "url": "https://example.org/x", "autor": "Autor", "licencia": "CC BY 4.0",
               "consultado": "2026-10-30"},
}


def _con(**cambios):
    f = copy.deepcopy(FICHA)
    f.update(cambios)
    return f


def test_una_ficha_bilingue_correcta_pasa_incluso_exigiendo_bilingue():
    assert validar_ficha(FICHA, bilingue=True) == []


def test_una_ficha_antigua_sin_i18n_ni_origen_sigue_pasando_pero_no_en_modo_bilingue():
    f = _con()
    del f["i18n"], f["origen"]
    assert validar_ficha(f) == []
    problemas = validar_ficha(f, bilingue=True)
    assert any("i18n" in p for p in problemas) and any("origen" in p for p in problemas)


def test_localizar_devuelve_el_ingles_y_cae_al_espanol_si_falta():
    en = localizar(FICHA, "en")
    assert en["nombre"] == "Partner passing and catching" and en["idioma"] == "en"
    assert en["diagramas"][0]["titulo"] == "Start" and "i18n" not in en
    assert en["edades"] == FICHA["edades"] and en["id"] == FICHA["id"]      # lo no textual se comparte
    es = localizar(FICHA, "es")
    assert es["nombre"] == FICHA["nombre"] and es["idioma"] == "es"
    sin = localizar({k: v for k, v in FICHA.items() if k != "i18n"}, "en")
    assert sin["nombre"] == FICHA["nombre"] and sin["idioma"] == "es"


def test_localizar_no_modifica_la_ficha_original():
    original = copy.deepcopy(FICHA)
    localizar(FICHA, "en")
    assert FICHA == original


def test_idiomas_de():
    assert idiomas_de(FICHA) == ["es", "en"]
    assert idiomas_de({"id": "ej_1"}) == ["es"]


@pytest.mark.parametrize("campo", ["nombre", "descripcion", "puntos_clave", "errores_frecuentes", "progresion",
                                   "titulos_diagramas"])
def test_en_modo_bilingue_el_ingles_debe_traer_todo_lo_que_trae_el_espanol(campo):
    f = copy.deepcopy(FICHA)
    del f["i18n"]["en"][campo]
    assert any(campo in p for p in validar_ficha(f, bilingue=True))


def test_las_listas_en_ingles_son_paralelas_a_las_del_espanol():
    f = copy.deepcopy(FICHA)
    f["i18n"]["en"]["puntos_clave"] = ["Only one cue."]
    assert any("puntos_clave" in p and "elementos" in p for p in validar_ficha(f))


def test_i18n_rechaza_idiomas_y_campos_desconocidos():
    assert validar_ficha(_con(i18n={"fr": {"nombre": "x"}}))
    f = copy.deepcopy(FICHA)
    f["i18n"]["en"]["edades"] = ["U12"]
    assert any("no traducibles" in p for p in validar_ficha(f))
    assert validar_ficha(_con(i18n={"es": {"nombre": "x"}}))     # el español es el nivel raíz, no va en i18n


def test_titulos_de_diagramas_uno_por_diagrama():
    f = copy.deepcopy(FICHA)
    f["i18n"]["en"]["titulos_diagramas"] = ["a", "b"]
    assert any("titulos_diagramas" in p for p in validar_ficha(f))


def test_descripcion_en_ingles_demasiado_corta():
    f = copy.deepcopy(FICHA)
    f["i18n"]["en"]["descripcion"] = "Too short."
    assert any("i18n.en.descripcion" in p for p in validar_ficha(f))


@pytest.mark.parametrize("origen", [
    {"tipo": "desconocido"},
    {"tipo": "abierta", "url": "https://x.org", "autor": "A", "licencia": "CC BY 4.0"},               # sin fecha
    {"tipo": "abierta", "url": "http://x.org", "autor": "A", "licencia": "CC BY", "consultado": "d"},  # sin https
    {"tipo": "abierta", "url": "https://x.org", "autor": " ", "licencia": "CC BY", "consultado": "d"},
    "texto",
])
def test_origen_invalido(origen):
    assert any("origen" in p for p in validar_ficha(_con(origen=origen)))


def test_origen_original_no_necesita_url():
    assert validar_ficha(_con(origen={"tipo": "original"}), bilingue=True) == []


def test_la_biblioteca_actual_sigue_pasando_el_filtro_normal(ejercicios):
    # las fichas con i18n u origen (si las hay) también deben pasar; las demás no los necesitan
    for ficha in ejercicios:
        assert not any("i18n" in p or "origen" in p
                       for p in validar_ficha(ficha, [e for e in ejercicios if e["id"] != ficha["id"]])), ficha["id"]


def test_la_api_devuelve_la_biblioteca_en_el_idioma_pedido(monkeypatch, tmp_path):
    import json

    from fastapi.testclient import TestClient

    import main
    ruta = tmp_path / "ejercicios.json"
    ruta.write_text(json.dumps([FICHA], ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(main, "EXERCISES_PATH", str(ruta))
    cliente = TestClient(main.app)
    assert cliente.get("/ejercicios").json()[0]["nombre"] == FICHA["nombre"]
    assert cliente.get("/ejercicios?lang=es").json()[0]["nombre"] == FICHA["nombre"]
    en = cliente.get("/ejercicios?lang=en").json()[0]
    assert en["nombre"] == "Partner passing and catching" and "i18n" not in en
    assert cliente.get("/ejercicios?lang=fr").status_code == 422
