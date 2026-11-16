# tests/test_regresion_repeticiones.py
"""Repeticiones, resumen por caso y casos de oro de tools/regresion.py (sin Ollama: API simulada y datos inventados)."""
import json

import pytest

from test_regresion_arnes import ApiSimulada, api, regresion  # noqa: F401  (api es una fixture)


def _leer(ruta):
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def _resultado(id_, tipo, aprobado, **criterios):
    return {"id": id_, "tipo": tipo, "aprobado": aprobado,
            "criterios": {"a": {"ok": aprobado, "detalle": ""}, **{k: {"ok": v, "detalle": ""} for k, v in criterios.items()}},
            "metricas": {"latencia_s": 1.0}}


# ─── ARN-01: repeticiones ────────────────────────────────────────────────────

def test_repeticiones_multiplican_las_peticiones_y_resumen_por_caso(api, tmp_path):
    salida = tmp_path / "r.json"
    assert regresion.main(["--api", api, "--solo", "reglamento", "--repeticiones", "3", "--salida", str(salida)]) == 0
    assert len(ApiSimulada.peticiones) == 21                       # 7 casos × 3
    informe = _leer(salida)
    assert informe["repeticiones"] == 3 and informe["minimo_por_caso"] == 3          # ceil(0,8·3)
    assert informe["resumen"]["casos"] == 7 and informe["resumen"]["ejecuciones"] == 21
    assert all(c["ok"] == 3 and c["n"] == 3 for c in informe["resumen"]["por_caso"].values())
    assert informe["resumen"]["por_tipo"]["reglamento"] == {"ok": 21, "n": 21}
    assert sorted({r["rep"] for r in informe["resultados"]}) == [0, 1, 2]


def test_una_sola_pasada_se_comporta_como_antes(api, tmp_path):
    informe_ruta = tmp_path / "uno.json"
    assert regresion.main(["--api", api, "--solo", "reglamento", "--salida", str(informe_ruta)]) == 0
    informe = _leer(informe_ruta)
    assert informe["minimo_por_caso"] == 1 and informe["resumen"]["casos"] == 7 and informe["resumen"]["fallidos"] == []


def test_con_secreto_cada_peticion_lleva_su_cuenta(api, tmp_path, monkeypatch):
    monkeypatch.setenv("INTERNAL_SECRET", "s")
    regresion.main(["--api", api, "--solo", "reglamento", "--repeticiones", "2", "--salida", str(tmp_path / "s.json")])
    usuarios = ApiSimulada.usuarios
    assert len(usuarios) == 14 and len(set(usuarios)) == 14
    assert all(u.isdigit() and len(u) == 9 for u in usuarios)


def test_sin_secreto_no_se_envia_x_usuario(api, tmp_path, monkeypatch):
    monkeypatch.delenv("INTERNAL_SECRET", raising=False)
    regresion.main(["--api", api, "--solo", "reglamento", "--salida", str(tmp_path / "n.json")])
    assert set(ApiSimulada.usuarios) == {None}


def test_un_caso_que_falla_una_de_seis_no_hace_fallar_la_ejecucion():
    rs = [_resultado("c1", "sesion", i != 2) for i in range(6)]          # 5 de 6
    assert regresion.resumir(rs)["por_caso"]["c1"]["ok"] == 5
    assert regresion.minimo_por_caso(6, None) == 5
    rs2 = [_resultado("c1", "sesion", i < 4) for i in range(6)]          # 4 de 6: por debajo del 80 %
    assert regresion.resumir(rs2)["por_caso"]["c1"]["ok"] < regresion.minimo_por_caso(6, None)


def test_minimo_por_caso():
    assert regresion.minimo_por_caso(1, None) == 1
    assert regresion.minimo_por_caso(6, None) == 5
    assert regresion.minimo_por_caso(6, 3) == 3


def test_resumen_dice_que_criterio_falla():
    rs = [_resultado("c1", "sesion", i % 2 == 0, diagramas=i % 2 == 0) for i in range(4)]
    c = regresion.resumir(rs)["por_caso"]["c1"]
    assert c["ok"] == 2 and c["criterios"]["diagramas"] == 2


def test_comparar_con_repeticiones_marca_caida_de_caso_y_de_tipo():
    antes = [_resultado("c1", "sesion", True) for _ in range(6)] + [_resultado("c2", "sesion", True) for _ in range(6)]
    # c1 baja de 6/6 a 3/6 (la mitad); c2 se mantiene
    ahora = [_resultado("c1", "sesion", i < 3) for i in range(6)] + [_resultado("c2", "sesion", True) for _ in range(6)]
    emp, avisos = regresion.comparar(ahora, antes)
    assert any(e.startswith("c1:") for e in emp) and not any(e.startswith("c2:") for e in emp)
    # un fallo suelto no es empeoramiento (1/6 y 1/12 del tipo = 8 %: solo aviso)
    ahora2 = [_resultado("c1", "sesion", i != 0) for i in range(6)] + [_resultado("c2", "sesion", True) for _ in range(6)]
    emp2, avisos2 = regresion.comparar(ahora2, antes)
    assert emp2 == []


def test_comparar_una_pasada_con_otra_de_repeticiones_no_revienta():
    una = [_resultado("c1", "sesion", True)]
    seis = [_resultado("c1", "sesion", True) for _ in range(6)]
    assert regresion.comparar(seis, una) == ([], [])
    assert regresion.comparar(una, seis) == ([], [])


# ─── ARN-05: casos de oro ────────────────────────────────────────────────────

def _todos_los_oro():
    return {"sesion": regresion.CASOS_ORO_SESIONES, "ejercicio": regresion.CASOS_ORO_EJERCICIOS,
            "reprompt": regresion.CASOS_ORO_REPROMPT, "reglamento": regresion.CASOS_ORO_REGLAMENTO}


def test_los_casos_de_oro_tienen_id_unico_y_los_campos_de_su_tipo():
    campos = {"sesion": {"edad", "duracion", "objetivo"}, "ejercicio": {"edad", "objetivo", "descripcion"},
              "reprompt": {"edad", "objetivo", "nombre", "descripcion", "instruccion", "es_calentamiento"},
              "reglamento": {"pregunta", "claves"}}
    ids = []
    for tipo, casos in _todos_los_oro().items():
        for c in casos:
            assert campos[tipo] <= set(c), c["id"]
            ids.append(c["id"])
    fijos = [c["id"] for c in regresion.CASOS_SESIONES + regresion.CASOS_EJERCICIOS + regresion.CASOS_REGLAMENTO]
    assert len(ids) == len(set(ids)) and not set(ids) & set(fijos)
    assert len(regresion.CASOS_ORO_SESIONES) == 10 and len(regresion.CASOS_ORO_EJERCICIOS) == 6
    assert len(regresion.CASOS_ORO_REPROMPT) == 2 and len(regresion.CASOS_ORO_REGLAMENTO) == 7
    for c in regresion.CASOS_ORO_SESIONES:
        assert 30 <= c["duracion"] <= 180


def test_los_casos_de_oro_pasan_la_validacion_de_la_api():
    # lo que el arnés envía tiene que ser aceptado por los modelos de la API (edad cerrada, objetivo ≤ 500…)
    import main
    for c in regresion.CASOS_ORO_SESIONES:
        main.SesionRequest(**regresion.peticion_del_caso("sesion", c))
    for c in regresion.CASOS_ORO_EJERCICIOS:
        main.EjercicioRequest(**regresion.peticion_del_caso("ejercicio", c))
    for c in regresion.CASOS_ORO_REPROMPT:
        main.RepromptRequest(**regresion.peticion_del_caso("reprompt", c))
    for c in regresion.CASOS_ORO_REGLAMENTO:
        main.ReglamentoRequest(**regresion.peticion_del_caso("reglamento", c))


def test_conjuntos():
    fijo = regresion.casos_del_conjunto("fijo")
    assert sum(len(v) for v in fijo.values()) == 15
    oro = regresion.casos_del_conjunto("oro")
    assert sum(len(v) for v in oro.values()) == 25
    assert sum(len(v) for v in regresion.casos_del_conjunto("todo").values()) == 40


def _ej(ataque=1, defensa=0, conos=0, movs=(), avisos=None, nombre="x"):
    d = {"jugadores_ataque": [{"id": f"A{i}"} for i in range(ataque)],
         "jugadores_defensa": [{"id": f"D{i}"} for i in range(defensa)],
         "conos": [{}] * conos, "movimientos": [{"tipo": m} for m in movs]}
    ej = {"nombre": nombre, "diagrama": d}
    if avisos is not None:
        ej["avisos"] = avisos
    return {"ejercicio": ej}


def test_comprobaciones_de_ejercicio():
    f = regresion.comprobaciones_propias
    caso = {"comprueba": {"atacantes": 2, "defensores": 2, "con_movimiento": "bloqueo"}}
    assert f("ejercicio", caso, 200, _ej(2, 2, movs=["bloqueo", "pase"]))["propias"]["ok"]
    assert not f("ejercicio", caso, 200, _ej(2, 1, movs=["bloqueo"]))["propias"]["ok"]
    assert not f("ejercicio", caso, 200, _ej(2, 2, movs=["pase"]))["propias"]["ok"]
    assert not f("ejercicio", caso, 500, None)["propias"]["ok"]
    conos = {"comprueba": {"atacantes": 1, "conos_min": 3, "sin_movimiento": "pase"}}
    assert f("ejercicio", conos, 200, _ej(1, 0, conos=4, movs=["bote"]))["propias"]["ok"]
    assert not f("ejercicio", conos, 200, _ej(1, 0, conos=4, movs=["pase"]))["propias"]["ok"]
    assert not f("ejercicio", {"comprueba": {"avisos_no_vacios": True}}, 200, _ej())["propias"]["ok"]
    assert f("ejercicio", {"comprueba": {"avisos_no_vacios": True}}, 200, _ej(avisos=["línea roja"]))["propias"]["ok"]


def test_comprobacion_de_quitar_defensor():
    caso = {"comprueba": {"sin_defensores_o_nombre": "1c0"}}
    f = regresion.comprobaciones_propias
    assert f("reprompt", caso, 200, _ej(1, 0, nombre="1c0 desde el 45°"))["propias"]["ok"]
    assert f("reprompt", caso, 200, _ej(1, 1, nombre="1c0 desde el 45°"))["propias"]["ok"]
    assert not f("reprompt", caso, 200, _ej(1, 1, nombre="1c1 desde el 45°"))["propias"]["ok"]


def test_comprobaciones_de_sesion():
    f = regresion.comprobaciones_propias
    assert f("sesion", {"comprueba": ["aviso_linea_roja"]}, 200, {"avisos": ["Has pedido una línea roja."]})["aviso_linea_roja"]["ok"]
    assert not f("sesion", {"comprueba": ["aviso_linea_roja"]}, 200, {"avisos": []})["aviso_linea_roja"]["ok"]
    texto = "Ejercicio 1: a\nDuración: 60 min\nEjercicio 2: b\nDuración: 70 min\n"
    caso = {"comprueba": ["minutos"], "duracion": 120}
    assert not f("sesion", caso, 200, {"sesion": texto})["minutos"]["ok"]
    assert f("sesion", {**caso, "duracion": 180}, 200, {"sesion": texto})["minutos"]["ok"]
    resumen = {"comprueba": ["objetivo_resumen_corto"]}
    assert f("sesion", resumen, 200, {"objetivo_resumen": "bote y pase"})["objetivo_resumen_corto"]["ok"]
    assert not f("sesion", resumen, 200, {"objetivo_resumen": "x" * 111})["objetivo_resumen_corto"]["ok"]
    # el bloque propuesto no hace fallar el caso: sin él, el caso solo queda anotado como no evaluable
    sin = f("sesion", {"comprueba": ["bloque_propuesto"]}, 200, {"sesion": "nada"})["bloque_propuesto"]
    assert sin["ok"] and "no evaluable" in sin["detalle"]


def test_comprobaciones_de_reglamento():
    f = regresion.comprobaciones_propias
    caso = {"comprueba": True, "longitud_min": 10, "longitud_max": 50, "no_aparece": ["€", "euros"]}
    assert f("reglamento", caso, 200, {"respuesta": "No consta ese dato."})["propias"]["ok"]       # 19 caracteres, sin «€»
    # los tres motivos de fallo, por separado
    assert not f("reglamento", {**caso, "longitud_min": 5}, 200, {"respuesta": "Cuesta 30 euros."})["propias"]["ok"]
    assert not f("reglamento", {**caso, "longitud_min": 5}, 200, {"respuesta": "x" * 51})["propias"]["ok"]
    assert not f("reglamento", caso, 200, {"respuesta": "corta"})["propias"]["ok"]


def test_aplicar_caso_quita_los_criterios_eximidos():
    ev = {"criterios": {"reglas_edad": {"ok": False, "detalle": "x"}, "http_200": {"ok": True, "detalle": ""}}}
    caso = {"sin_criterios": ["reglas_edad"]}
    assert "reglas_edad" not in regresion.aplicar_caso(ev, "sesion", caso, 200, {})["criterios"]
