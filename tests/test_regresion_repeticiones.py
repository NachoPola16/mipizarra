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


# ─── ARN-03: criterios generales nuevos ──────────────────────────────────────

def test_idioma_sospechoso():
    f = regresion.idioma_sospechoso
    assert f("Cada jugador bota entre los conos y termina con una bandeja por la derecha.") == ""
    assert f("Each player must dribble through the cones and then finish, and the coach will check their form.")
    assert f("热身：每个人运球")
    assert f("") == ""
    # una o dos palabras sueltas en inglés (pick and roll) no bastan
    assert f("Trabajamos el pick and roll con el balón y los dos jugadores del lado débil.") == ""


def test_bloques_incompletos():
    f = regresion.bloques_incompletos
    org = "Filas en el medio campo; el primero sale con balón y el resto espera su turno detrás del cono."
    bueno = f"Ejercicio 1: A\nDuración: 10 min\nOrganización: {org}\nPuntos clave:\n- Uno.\n- Dos.\n"
    assert f(bueno) == []
    assert f(bueno.replace("- Dos.\n", "")) == ["Ejercicio 1"]                    # un solo punto clave
    assert f(bueno.replace(org, "Corta.")) == ["Ejercicio 1"]                      # organización corta
    variante = bueno + 'Ejercicio 1.2 (variante de "A"):\nDuración: 5 min\nOrganización: Igual.\n'
    assert f(variante) == []                                                        # las N.2 están exentas
    dos = bueno + bueno.replace("Ejercicio 1", "Ejercicio 2").replace("- Dos.\n", "")
    assert f(dos) == ["Ejercicio 2"]


def test_minutos_de_sesion():
    assert regresion.minutos_de_sesion("Duración: 10 min\nDuración: 15 min") == 25
    assert regresion.minutos_de_sesion("") == 0


def test_la_sesion_buena_pasa_y_sin_teoria_o_pasada_de_minutos_falla():
    from test_regresion_arnes import sesion_buena
    caso = {"id": "x", "edad": "U12", "duracion": 75, "objetivo": "1c1"}
    ok = regresion.evaluar_sesion(caso, 200, sesion_buena("U12", "1c1", 75), 1.0)
    assert all(c["ok"] for c in ok["criterios"].values()), {n: c for n, c in ok["criterios"].items() if not c["ok"]}
    sin_rag = dict(sesion_buena("U12", "1c1", 75), teoria_usada=False)
    assert not regresion.evaluar_sesion(caso, 200, sin_rag, 1.0)["criterios"]["rag_vivo"]["ok"]
    larga = dict(sesion_buena("U12", "1c1", 75))
    larga["sesion"] = larga["sesion"] + "\nDuración: 90 min\n"
    assert not regresion.evaluar_sesion(caso, 200, larga, 1.0)["criterios"]["minutos"]["ok"]


# ─── ARN-04: el arnés suma la guardia de la API ──────────────────────────────

def test_el_arnes_detecta_lo_que_veta_la_api():
    assert regresion._LINEAS_ROJAS is not None
    for texto in ("Trabajamos el juego de poste bajo con los dos jugadores.", "Hacemos un mano a mano en la banda."):
        assert regresion.buscar_contenido_prohibido(texto, "U10"), texto
    assert regresion.buscar_contenido_prohibido("Sin poste bajo ni mano a mano: solo pase y bote.", "U10") == []
    assert regresion.buscar_contenido_prohibido("Trabajamos el poste bajo.", "U16") == []


def test_la_metrica_de_origen_de_diagramas():
    from test_regresion_arnes import SVG_OK, sesion_buena
    caso = {"id": "x", "edad": "U12", "duracion": 75, "objetivo": "1c1"}
    datos = sesion_buena("U12", "1c1", 75)
    for d, o in zip(datos["diagramas"], ["modelo", "modelo", "no_disponible"]):
        d["origen"] = o
    m = regresion.evaluar_sesion(caso, 200, datos, 1.0)["metricas"]
    assert m["diagramas_modelo"] == 2 and m["diagramas_modelo_no_disponibles"] == 1


def test_la_organizacion_de_una_ficha_va_en_varias_lineas():
    # en las fichas, «Organización:» es una frase corta y el detalle va en SECUENCIA, ROTACIÓN y PROGRESIÓN
    texto = ("Ejercicio 1: A\nDuración: 10 min\nOrganización:\ntríos con un balón.\n"
             "SECUENCIA: el que tiene el balón bota por la pista y los otros dos se colocan donde pueda verlos.\n"
             "ROTACIÓN: cada minuto cambian los tríos.\nPuntos clave:\n- Uno.\n- Dos.\n")
    assert regresion.bloques_incompletos(texto) == []
    assert regresion.bloques_incompletos(texto.replace("SECUENCIA", "S").replace("ROTACIÓN", "R")
                                         .replace("el que tiene el balón bota por la pista y los otros dos se colocan donde pueda verlos.", "x")) == ["Ejercicio 1"]


def test_la_abstencion_reconoce_las_formas_habituales_del_modelo():
    casos = {c["id"]: c for c in regresion.CASOS_ORO_REGLAMENTO}
    for respuesta in ("No se proporciona información sobre el costo de la licencia.",
                      "Por tanto, **no se puede determinar el precio** con la información disponible.",
                      "No consta ese dato."):
        ev = regresion.evaluar_reglamento(casos["oro_reg_fuera_de_tema"], 200, {"respuesta": respuesta}, 1.0)
        assert ev["criterios"]["palabras_clave"]["ok"], respuesta
    ev = regresion.evaluar_reglamento(casos["oro_reg_fuera_de_tema"], 200, {"respuesta": "Ganó el Real Madrid."}, 1.0)
    assert not ev["criterios"]["palabras_clave"]["ok"]


def test_caso_limita_la_ejecucion_a_los_ids_pedidos(api, tmp_path):
    salida = tmp_path / "c.json"
    assert regresion.main(["--api", api, "--solo", "reglamento", "--caso", "reg_8_segundos", "--caso", "reg_aro_minibasket",
                           "--salida", str(salida)]) == 0
    assert len(ApiSimulada.peticiones) == 2
    assert {r["id"] for r in _leer(salida)["resultados"]} == {"reg_8_segundos", "reg_aro_minibasket"}
