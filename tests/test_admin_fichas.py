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


# ── Inglés editable, avisos mecánicos y buscar/reemplazar ─────────────────────────────────────────
def test_se_puede_editar_el_ingles_y_no_se_pisa_el_resto(api):
    f = _ficha(api, "ej_204")
    assert f["i18n"]["en"]["nombre"]
    en = {**f["i18n"]["en"], "nombre": "Slalom dribble against a defender (edited)"}
    r = api.put("/admin/fichas/ej_204", json={"ficha": {**f, "i18n": {"en": en}}})
    assert r.status_code == 200, r.text
    despues = _ficha(api, "ej_204")
    assert despues["i18n"]["en"]["nombre"].endswith("(edited)")
    assert despues["nombre"] == f["nombre"] and despues["descripcion"] == f["descripcion"]
    assert api.get("/ejercicios?lang=en").json() and next(e for e in api.get("/ejercicios?lang=en").json() if e["id"] == "ej_204")["nombre"].endswith("(edited)")


def test_el_ingles_debe_seguir_el_espanol_en_las_listas(api):
    f = _ficha(api, "ej_204")
    en = {**f["i18n"]["en"], "puntos_clave": f["i18n"]["en"]["puntos_clave"] + ["one more"]}
    r = api.put("/admin/fichas/ej_204", json={"ficha": {**f, "i18n": {"en": en}}})
    assert r.status_code == 422 and any("puntos_clave" in p for p in r.json()["problemas"])
    en2 = {**f["i18n"]["en"], "campo_raro": "x"}
    assert api.put("/admin/fichas/ej_204", json={"ficha": {**f, "i18n": {"en": en2}}}).status_code == 422
    assert _ficha(api, "ej_204")["i18n"] == f["i18n"]


def test_los_avisos_salen_de_la_ficha_tal_como_esta_en_el_editor(api):
    f = _ficha(api, "ej_003")
    sin = api.post("/admin/fichas/ej_003/avisos", json={"ficha": f}).json()["avisos"]
    con = api.post("/admin/fichas/ej_003/avisos", json={"ficha": {**f, "descripcion": f["descripcion"] + " Entonces A9 tira."}}).json()["avisos"]
    assert any(a["tipo"] == "LABEL" and "A9" in a["texto"] for a in con)
    assert not any(a["tipo"] == "LABEL" and "A9" in a["texto"] for a in sin)
    assert api.post("/admin/fichas/ej_9999x/avisos", json={"ficha": f}).status_code == 400
    assert api.post("/admin/fichas/ej_9999/avisos", json={"ficha": f}).status_code == 404
    assert _ficha(api, "ej_003")["descripcion"] == f["descripcion"]            # no guarda nada


def _con_texto(api, texto):
    return [f["id"] for f in api.get("/admin/fichas").json()["fichas"] if texto.lower() in json.dumps({k: v for k, v in f.items() if k not in ("diagrama", "diagramas", "i18n")}, ensure_ascii=False).lower()]


def test_reemplazar_primero_enseña_y_no_toca_nada(api):
    antes = api.ruta.read_text(encoding="utf-8")
    r = api.post("/admin/reemplazar", json={"buscar": "reverso", "reemplazar": "giro", "ambito": "es"})
    assert r.status_code == 200
    ids = {x["id"] for x in r.json()["fichas"]}
    assert {"ej_193", "ej_216"} <= ids and r.json()["total_cambios"] >= 5
    assert all({"campo", "antes", "despues"} <= set(c) for x in r.json()["fichas"] for c in x["cambios"])
    assert api.ruta.read_text(encoding="utf-8") == antes


def test_reemplazar_solo_en_las_fichas_marcadas_con_una_copia_y_una_version_anterior_cada_una(api, tmp_path):
    r = api.post("/admin/reemplazar", json={"buscar": "reverso", "reemplazar": "giro", "ambito": "es", "aplicar": True, "ids": ["ej_216"]})
    assert r.status_code == 200 and r.json()["guardadas"] == ["ej_216"] and r.json()["omitidas"] == []
    assert "reverso" not in json.dumps(_ficha(api, "ej_216")["descripcion"]).lower()
    assert "reverso" in _ficha(api, "ej_193")["nombre"].lower()                   # la no marcada no cambia
    assert api.get("/admin/fichas").json()["modificadas"] == ["ej_216"]
    assert len(list((tmp_path / "cambios" / "copias").iterdir())) == 1
    assert api.delete("/admin/fichas/ej_216").status_code == 200                  # se puede deshacer una a una
    assert "reverso" in _ficha(api, "ej_216")["nombre"].lower()


def test_reemplazar_conserva_la_mayuscula_inicial_y_respeta_palabra_entera(api):
    r = api.post("/admin/reemplazar", json={"buscar": "reverso", "reemplazar": "giro", "ambito": "es"}).json()
    nombre = next(c for x in r["fichas"] if x["id"] == "ej_216" for c in x["cambios"] if c["campo"] == "nombre")
    assert nombre["antes"].startswith("Reverso") and nombre["despues"].startswith("Giro")
    parcial = api.post("/admin/reemplazar", json={"buscar": "revers", "reemplazar": "X", "ambito": "es", "palabra": True}).json()
    assert parcial["fichas"] == []                                                # «revers» no es una palabra entera
    exacto = api.post("/admin/reemplazar", json={"buscar": "Reverso", "reemplazar": "giro", "ambito": "es", "mayusculas": True}).json()
    assert {x["id"] for x in exacto["fichas"]} == {"ej_216"} or {"ej_216"} <= {x["id"] for x in exacto["fichas"]}


def test_reemplazar_en_ingles_y_entradas_no_validas(api):
    r = api.post("/admin/reemplazar", json={"buscar": "floater", "reemplazar": "floaters", "ambito": "en"}).json()
    assert r["fichas"] and all(c["campo"].startswith("EN ") for x in r["fichas"] for c in x["cambios"])
    assert api.post("/admin/reemplazar", json={"buscar": "", "reemplazar": "x"}).status_code == 422
    assert api.post("/admin/reemplazar", json={"buscar": "a", "ambito": "fr"}).status_code == 400
    assert api.post("/admin/reemplazar", json={"buscar": "a", "aplicar": True}).status_code == 400
    assert api.post("/admin/reemplazar", json={"buscar": "a", "aplicar": True, "ids": ["no"]}).status_code == 400


def test_un_reemplazo_que_deja_una_ficha_invalida_la_omite_sin_parar_las_demas(api):
    # quitar «bandeja» de un nombre no es problema; vaciar el nombre sí: esa ficha se omite
    r = api.post("/admin/reemplazar", json={"buscar": _ficha(api, "ej_216")["nombre"], "reemplazar": "", "ambito": "es", "aplicar": True, "ids": ["ej_216", "ej_193"]})
    assert r.status_code == 200
    assert r.json()["guardadas"] == [] and [o["id"] for o in r.json()["omitidas"]] == ["ej_216"]


# ── «Inglés desfasado»: el inglés recuerda con qué español se revisó (i18n.en.es_hash) ────────────────
def _desfasadas(api):
    return api.get("/admin/fichas").json()["desfasadas"]


def test_hash_del_espanol_cambia_con_el_espanol_y_no_con_el_ingles():
    from i18n_fichas import hash_es, ingles_desfasado
    f = next(e for e in json.load(open(RAIZ / "data" / "exercises.json", encoding="utf-8")) if e["id"] == "ej_204")
    h = hash_es(f)
    assert len(h) == 12 and hash_es({**f, "i18n": {"en": {"nombre": "otro"}}}) == h
    assert hash_es({**f, "nombre": f["nombre"] + "!"}) != h
    assert not ingles_desfasado(f)                                             # sin huella guardada no se sabe: no avisa
    marcada = {**f, "i18n": {"en": {**f["i18n"]["en"], "es_hash": h}}}
    assert not ingles_desfasado(marcada) and ingles_desfasado({**marcada, "nombre": f["nombre"] + "!"})


def test_cambiar_solo_el_espanol_marca_el_ingles_como_desfasado_y_revisarlo_lo_arregla(api):
    f = _ficha(api, "ej_204")
    assert _desfasadas(api) == []
    # guardar el inglés cambiado fija la huella del español actual
    en = {**f["i18n"]["en"], "nombre": f["i18n"]["en"]["nombre"] + " (rev)"}
    r = api.put("/admin/fichas/ej_204", json={"ficha": {**f, "i18n": {"en": en}}})
    assert r.status_code == 200 and r.json()["desfasada"] is False and _desfasadas(api) == []
    guardada = _ficha(api, "ej_204")
    assert len(guardada["i18n"]["en"]["es_hash"]) == 12
    # solo cambia el español (el editor reenvía el mismo inglés): queda desfasado
    r = api.put("/admin/fichas/ej_204", json={"ficha": {**guardada, "nombre": guardada["nombre"] + " (nuevo)"}})
    assert r.status_code == 200 and r.json()["desfasada"] is True and _desfasadas(api) == ["ej_204"]
    # darlo por revisado sin tocar el texto
    r = api.put("/admin/fichas/ej_204", json={"ficha": {**_ficha(api, "ej_204"), "ingles_revisado": True}})
    assert r.status_code == 200 and r.json()["desfasada"] is False and _desfasadas(api) == []
    # la huella no se filtra a quien lee la web en inglés
    pub = next(e for e in api.get("/ejercicios?lang=en").json() if e["id"] == "ej_204")
    assert "es_hash" not in json.dumps(pub) and "i18n" not in pub


def test_volver_atras_recalcula_si_el_ingles_esta_desfasado(api):
    f = _ficha(api, "ej_204")
    en = {**f["i18n"]["en"], "nombre": f["i18n"]["en"]["nombre"] + " (rev)"}
    api.put("/admin/fichas/ej_204", json={"ficha": {**f, "i18n": {"en": en}}})
    g = _ficha(api, "ej_204")
    api.put("/admin/fichas/ej_204", json={"ficha": {**g, "nombre": g["nombre"] + " (nuevo)"}})
    assert _desfasadas(api) == ["ej_204"]
    r = api.delete("/admin/fichas/ej_204")
    assert r.status_code == 200 and r.json()["desfasada"] is False and _desfasadas(api) == []


def test_la_api_no_se_fia_de_la_huella_que_manda_el_cliente_y_el_validador_la_exige_bien_formada(api):
    f = _ficha(api, "ej_204")
    r = api.put("/admin/fichas/ej_204", json={"ficha": {**f, "i18n": {"en": {**f["i18n"]["en"], "es_hash": "0123456789ab"}}}})
    # sin cambios en el inglés: se conserva la marca que ya tenía (o ninguna), nunca la que manda el navegador
    assert r.status_code == 200 and _ficha(api, "ej_204")["i18n"]["en"].get("es_hash") == f["i18n"]["en"].get("es_hash") != "0123456789ab"
    from validacion_fichas import validar_ficha
    mala = {**f, "i18n": {"en": {**f["i18n"]["en"], "es_hash": "xx"}}}
    assert any("es_hash" in p for p in validar_ficha(mala))


def test_reemplazar_en_espanol_no_desfasa_un_ingles_que_estaba_al_dia_pero_no_arregla_uno_desfasado(api):
    # dos fichas con «reverso»: ej_193 con el inglés revisado, ej_216 con el inglés desfasado
    a, b = _ficha(api, "ej_193"), _ficha(api, "ej_216")
    api.put("/admin/fichas/ej_193", json={"ficha": {**a, "ingles_revisado": True}})
    api.put("/admin/fichas/ej_216", json={"ficha": {**b, "ingles_revisado": True}})
    b2 = _ficha(api, "ej_216")
    api.put("/admin/fichas/ej_216", json={"ficha": {**b2, "consigna": "Protege, gira y sal (nuevo)"}})
    assert _desfasadas(api) == ["ej_216"]
    r = api.post("/admin/reemplazar", json={"buscar": "reverso", "reemplazar": "giro", "ambito": "es", "aplicar": True, "ids": ["ej_193", "ej_216"]})
    assert r.status_code == 200 and set(r.json()["guardadas"]) == {"ej_193", "ej_216"}
    assert _desfasadas(api) == ["ej_216"]
