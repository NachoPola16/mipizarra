# tests/test_admin_fichas.py
"""Cambios del administrador sobre las fichas: se guardan aparte (ficha_cambios.json), se aplican encima de
exercises.json, se validan con validar_ficha y se pueden restaurar."""
import json
import shutil

import pytest
from fastapi.testclient import TestClient

import ejercicios
import fichas_edicion
import main
from conftest import RAIZ


@pytest.fixture
def api(tmp_path, monkeypatch):
    """La API sobre una COPIA de exercises.json (los tests nunca tocan el del repositorio)."""
    copia = tmp_path / "exercises.json"
    shutil.copy(RAIZ / "data" / "exercises.json", copia)
    monkeypatch.setattr(main, "EXERCISES_PATH", str(copia))
    monkeypatch.setattr(ejercicios, "EXERCISES_PATH", str(copia))
    monkeypatch.setattr(fichas_edicion, "CARPETA", str(tmp_path / "cambios"))
    monkeypatch.setattr(main, "INTERNAL_SECRET", "")
    main.limiter.reset()
    cliente = TestClient(main.app)
    cliente.ruta = copia
    return cliente


def _ficha(api, ficha_id="ej_176"):
    return next(f for f in api.get("/admin/fichas").json()["fichas"] if f["id"] == ficha_id)


def test_sin_cambios_la_biblioteca_es_la_de_git(api):
    datos = api.get("/admin/fichas").json()
    assert datos["modificadas"] == []
    assert len(datos["fichas"]) == len(json.load(open(RAIZ / "data" / "exercises.json", encoding="utf-8")))


def test_guardar_cambia_la_ficha_y_conserva_id_y_diagrama(api):
    f = _ficha(api, "ej_003")                   # una ficha con diagrama
    nueva = {**f, "nombre": f["nombre"] + " (revisada)", "intensidad": 2}
    r = api.put("/admin/fichas/ej_003", json={"ficha": nueva})
    assert r.status_code == 200, r.text
    despues = _ficha(api, "ej_003")
    assert despues["nombre"].endswith("(revisada)") and despues["intensidad"] == 2
    assert despues["id"] == "ej_003" and despues["diagrama"] == f["diagrama"]
    assert api.get("/admin/fichas").json()["modificadas"] == ["ej_003"]
    # se escribió en exercises.json y el resto de la API lo ve (generación de sesiones, /ejercicios)
    assert next(e for e in json.loads(api.ruta.read_text(encoding="utf-8")) if e["id"] == "ej_003")["intensidad"] == 2
    assert next(e for e in ejercicios.cargar_ejercicios() if e["id"] == "ej_003")["intensidad"] == 2
    assert next(e for e in api.get("/ejercicios").json() if e["id"] == "ej_003")["intensidad"] == 2


def test_volver_atras_deja_la_ficha_como_estaba(api):
    f = _ficha(api)
    api.put("/admin/fichas/ej_176", json={"ficha": {**f, "duracion_min": 12}})
    assert _ficha(api)["duracion_min"] == 12
    assert api.get("/admin/fichas").json()["modificadas"] == ["ej_176"]
    assert api.delete("/admin/fichas/ej_176").status_code == 200
    assert _ficha(api) == f
    assert api.get("/admin/fichas").json()["modificadas"] == []
    assert api.delete("/admin/fichas/ej_176").status_code == 404          # ya no hay versión anterior


def test_una_ficha_invalida_no_se_guarda_y_dice_por_que(api):
    f = _ficha(api)
    r = api.put("/admin/fichas/ej_176", json={"ficha": {**f, "edades": ["U10"], "duracion_min": 999, "intensidad": 9}})
    assert r.status_code == 422
    texto = " ".join(r.json()["problemas"])
    assert "duracion_min" in texto and "intensidad" in texto
    assert _ficha(api)["duracion_min"] == f["duracion_min"]


def test_las_lineas_rojas_por_edad_tambien_valen_al_editar(api):
    f = _ficha(api)
    r = api.put("/admin/fichas/ej_176", json={"ficha": {**f, "descripcion": f["descripcion"] + " Se juega con zona 2-3 y mano a mano."}})
    assert r.status_code == 422 and any("línea roja" in p for p in r.json()["problemas"])


def test_nombre_repetido_o_id_raro_se_rechazan(api):
    f = _ficha(api)
    otra = _ficha(api, "ej_175")
    assert api.put("/admin/fichas/ej_176", json={"ficha": {**f, "nombre": otra["nombre"]}}).status_code == 422
    assert api.put("/admin/fichas/../x", json={"ficha": f}).status_code in (400, 404, 405)
    assert api.put("/admin/fichas/ej_99999", json={"ficha": f}).status_code == 404
    assert api.put("/admin/fichas/zz_1", json={"ficha": f}).status_code == 400


def test_los_opcionales_vacios_se_quitan_y_los_textos_se_recortan(api):
    f = _ficha(api)
    r = api.put("/admin/fichas/ej_176", json={"ficha": {**f, "nombre": "  " + f["nombre"] + "  ", "material": "  ",
                                                         "errores_frecuentes": ["", " "], "progresion": {}}})
    assert r.status_code == 200, r.text
    g = _ficha(api)
    assert g["nombre"] == f["nombre"] and "material" not in g and "errores_frecuentes" not in g and "progresion" not in g


def test_sin_el_marcador_sin_diagrama_el_diagrama_no_se_toca_ni_el_id(api):
    f = _ficha(api, "ej_003")
    api.put("/admin/fichas/ej_003", json={"ficha": {**f, "id": "ej_999", "diagrama": {"tipo": "x"}}})
    g = _ficha(api, "ej_003")
    assert g["id"] == "ej_003" and g["diagrama"] == f["diagrama"] and "sin_diagrama" not in g


def test_con_secreto_las_rutas_de_admin_exigen_el_secreto(api, monkeypatch):
    monkeypatch.setattr(main, "INTERNAL_SECRET", "s")
    assert api.get("/admin/fichas").status_code == 401
    assert api.get("/admin/fichas", headers={"X-Internal-Secret": "s"}).status_code == 200


# ── diagramas ────────────────────────────────────────────────────────────────

DIAG = {"tipo": "media_pista", "titulo": "Prueba",
        "jugadores_ataque": [{"id": "A1", "x": 20, "y": 30}, {"id": "A2", "x": 60, "y": 50}],
        "jugadores_defensa": [{"id": "D1", "x": 22, "y": 36}],
        "balon_inicio": {"portador": "A1"},
        "movimientos": [{"de": "A1", "tipo": "pase", "a": "A2", "orden": 1},
                        {"de": "A2", "tipo": "desplazamiento", "a_pos": {"x": 70, "y": 40}, "orden": 2, "curva": 0.3},
                        {"de": "A2", "tipo": "tiro", "orden": 3}],
        "conos": [{"x": 50, "y": 20}]}


def test_vista_previa_devuelve_el_svg_o_los_problemas(api):
    r = api.post("/admin/diagrama/vista", json={"diagrama": DIAG})
    assert r.status_code == 200 and r.json()["svg"].startswith("<svg") and "MiPizarra" in r.json()["svg"]
    malo = {**DIAG, "movimientos": [{"de": "Z9", "tipo": "pase", "a": "A1", "orden": 1}]}
    r = api.post("/admin/diagrama/vista", json={"diagrama": malo})
    assert r.status_code == 422 and "Z9" in " ".join(r.json()["problemas"])
    fuera = {**DIAG, "jugadores_ataque": [{"id": "A1", "x": 150, "y": 30}]}
    assert api.post("/admin/diagrama/vista", json={"diagrama": fuera}).status_code == 422


def test_la_vista_ignora_claves_raras_y_no_rompe_con_basura(api):
    r = api.post("/admin/diagrama/vista", json={"diagrama": {**DIAG, "script": "<x>", "jugadores_ataque":
                 [{"id": "A1", "x": 20, "y": 30, "html": "<b>"}, {"id": "A2", "x": 60, "y": 50}]}})
    assert r.status_code == 200 and "<b>" not in r.text
    assert api.post("/admin/diagrama/vista", json={"diagrama": {"jugadores_ataque": "no"}}).status_code == 422
    assert api.post("/admin/diagrama/vista", json={"diagrama": {"jugadores_ataque": [3]}}).status_code == 422


def test_editar_el_diagrama_de_una_ficha_y_restaurarlo(api):
    f = _ficha(api, "ej_003")
    r = api.put("/admin/fichas/ej_003", json={"ficha": {**f, "sin_diagrama": False, "diagrama": DIAG}})
    assert r.status_code == 200, r.text
    g = _ficha(api, "ej_003")
    assert g["diagrama"]["titulo"] == "Prueba" and len(g["diagrama"]["movimientos"]) == 3 and "diagramas" not in g
    assert api.delete("/admin/fichas/ej_003").status_code == 200
    assert _ficha(api, "ej_003")["diagrama"] == f["diagrama"]


def test_pasar_de_un_diagrama_a_varios_o_a_juego_libre(api):
    f = _ficha(api, "ej_003")
    sin = {k: v for k, v in f.items() if k != "diagrama"}
    r = api.put("/admin/fichas/ej_003", json={"ficha": {**sin, "sin_diagrama": False, "diagramas": [DIAG, {**DIAG, "titulo": "Fase 2"}]}})
    assert r.status_code == 200, r.text
    g = _ficha(api, "ej_003")
    assert "diagrama" not in g and [d["titulo"] for d in g["diagramas"]] == ["Prueba", "Fase 2"]
    r = api.put("/admin/fichas/ej_003", json={"ficha": {**sin, "sin_diagrama": True}})
    assert r.status_code == 200
    g = _ficha(api, "ej_003")
    assert g["sin_diagrama"] is True and "diagrama" not in g and "diagramas" not in g


def test_un_diagrama_invalido_no_se_guarda(api):
    f = _ficha(api, "ej_003")
    r = api.put("/admin/fichas/ej_003", json={"ficha": {**f, "sin_diagrama": False, "diagrama": {**DIAG, "balon_inicio": {"portador": "Q"}}}})
    assert r.status_code == 422 and "portador" in " ".join(r.json()["problemas"])
    assert _ficha(api, "ej_003")["diagrama"] == f["diagrama"]


# ── red de seguridad: copias del fichero e historial ─────────────────────────

def test_cada_guardado_hace_una_copia_del_fichero_y_guarda_la_version_anterior(api, tmp_path):
    f = _ficha(api)
    original = api.ruta.read_text(encoding="utf-8")
    api.put("/admin/fichas/ej_176", json={"ficha": {**f, "intensidad": 2}})
    copias = list((tmp_path / "cambios" / "copias").iterdir())
    assert len(copias) == 1 and copias[0].read_text(encoding="utf-8") == original
    historial = json.loads((tmp_path / "cambios" / "ficha_historial.json").read_text(encoding="utf-8"))
    assert historial["ej_176"][0]["ficha"] == f


def test_guardar_sin_cambios_no_toca_nada(api, tmp_path):
    f = _ficha(api)
    antes = api.ruta.read_bytes()
    assert api.put("/admin/fichas/ej_176", json={"ficha": f}).status_code == 200
    assert api.ruta.read_bytes() == antes and not (tmp_path / "cambios").exists()


def test_se_conservan_solo_las_ultimas_copias_y_versiones(api, tmp_path, monkeypatch):
    monkeypatch.setattr(fichas_edicion, "COPIAS_MAX", 3)
    monkeypatch.setattr(fichas_edicion, "HISTORIAL_MAX", 2)
    f = _ficha(api)
    for n in range(1, 6):
        assert api.put("/admin/fichas/ej_176", json={"ficha": {**f, "duracion_min": 5 + n}}).status_code == 200
    assert len(list((tmp_path / "cambios" / "copias").iterdir())) == 3
    historial = json.loads((tmp_path / "cambios" / "ficha_historial.json").read_text(encoding="utf-8"))
    assert [v["ficha"]["duracion_min"] for v in historial["ej_176"]] == [8, 9]
    assert api.delete("/admin/fichas/ej_176").status_code == 200 and _ficha(api)["duracion_min"] == 9


def test_apagar_la_red_de_seguridad(api, tmp_path, monkeypatch):
    monkeypatch.setattr(fichas_edicion, "COPIAS_MAX", 0)
    monkeypatch.setattr(fichas_edicion, "HISTORIAL_MAX", 0)
    f = _ficha(api)
    assert api.put("/admin/fichas/ej_176", json={"ficha": {**f, "intensidad": 2}}).status_code == 200
    assert _ficha(api)["intensidad"] == 2 and not (tmp_path / "cambios").exists()
    assert api.delete("/admin/fichas/ej_176").status_code == 404


def test_el_orden_de_las_claves_se_conserva_para_que_el_diff_de_git_sea_limpio(api):
    f = _ficha(api)
    api.put("/admin/fichas/ej_176", json={"ficha": {**f, "intensidad": 2}})
    assert list(_ficha(api)) == list(f)
