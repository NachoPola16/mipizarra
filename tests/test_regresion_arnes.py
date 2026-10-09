# tests/test_regresion_arnes.py
"""Verifica tools/regresion.py contra una API simulada (http.server en local, sin
Ollama): respuestas buenas → código 0; respuestas con fallos → código distinto de
cero y criterios concretos marcados; --comparar detecta empeoramientos."""
import importlib.util
import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from conftest import RAIZ
from diagram_renderer import render_diagram
from plan_sesion import plan_de_tiempos

_spec = importlib.util.spec_from_file_location("regresion", RAIZ / "tools" / "regresion.py")
regresion = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(regresion)


# ─── Respuestas simuladas ────────────────────────────────────────────────────

DIAGRAMA_1C1 = {
    "tipo": "media_pista",
    "jugadores_ataque": [{"id": "A1", "x": 25, "y": 50}],
    "jugadores_defensa": [{"id": "D1", "x": 30, "y": 40}],
    "balon_inicio": {"portador": "A1"},
    "movimientos": [
        {"de": "A1", "tipo": "bote", "a_pos": {"x": 40, "y": 20}, "orden": 1},
        {"de": "A1", "tipo": "tiro", "orden": 2},
    ],
    "conos": [],
}
DIAGRAMA_2C1 = {
    "tipo": "media_pista",
    "jugadores_ataque": [{"id": "A1", "x": 50, "y": 65}, {"id": "A2", "x": 25, "y": 50}],
    "jugadores_defensa": [{"id": "D1", "x": 50, "y": 40}],
    "balon_inicio": {"portador": "A1"},
    "movimientos": [
        {"de": "A1", "tipo": "bote", "a_pos": {"x": 50, "y": 50}, "orden": 1},
        {"de": "A1", "tipo": "pase", "a": "A2", "orden": 2},
        {"de": "A2", "tipo": "tiro", "orden": 3},
    ],
    "conos": [],
}
SVG_OK = render_diagram(DIAGRAMA_1C1)
SVG_NO_DISPONIBLE = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 500 200">'
                     '<text x="250" y="95">Diagrama no disponible</text></svg>')

FORMACION = {"U8", "U10", "U12"}


def _bloque(n, nombre, partido):
    if not partido:
        return (f"Ejercicio {n}: {nombre}\nDuración: 15 min\n"
                f"Organización: Filas en el medio campo; el primero sale con balón.\n"
                f"Puntos clave:\n- Mirada arriba.\n- Cambio de ritmo.\n")
    return (f"Ejercicio {n}.1: {nombre}\nDuración: 10 min\n"
            f"Organización: Filas en el medio campo; el primero sale con balón.\n"
            f"Puntos clave:\n- Mirada arriba.\n\n"
            f'Ejercicio {n}.2 (variante de "{nombre}" — mismo ejercicio con un cambio o regla nueva, '
            f"no lo repitas igual):\nDuración: 5 min\n"
            f"Qué cambia respecto a {n}.1: Se añade un defensor pasivo.\n"
            f"Organización: Igual, con defensor.\nPuntos clave:\n- Proteger el balón.\n")


NOMBRES_EJERCICIOS = ["Rueda de bote", "2c1 desde medio campo", "3c3 en media pista",
                      "Pase y corte 3c0", "1c1 desde el codo", "4c4 en transición"]


def sesion_buena(edad, objetivo, duracion=90):
    """Sesión como la de la API real: n ejercicios en la parte principal (n según plan_de_tiempos),
    el descanso hacia la mitad y, en formación, el primero partido en base + variante."""
    NL = "\n"
    plan = plan_de_tiempos(duracion, edad)
    n = len(plan.duraciones)
    partido = edad in FORMACION
    contenido = "bote de protección y cambio de mano" if partido else f"{objetivo} con lectura de la defensa"
    partes = [
        "**CALENTAMIENTO (10 min)**" + NL + "Juego: Cazadores" + NL
        + "Reglas: Dos cazadores persiguen a los demás, que botan sin salir de media pista." + NL
        + "Espacio: Media pista." + NL + NL + "**PARTE PRINCIPAL**" + NL + NL
    ]
    nombres = []
    for i in range(1, n + 1):
        nombre = NOMBRES_EJERCICIOS[(i - 1) % len(NOMBRES_EJERCICIOS)]
        con_variante = partido and i == 1
        partes.append(_bloque(i, nombre, con_variante) + NL)
        nombres += [nombre, nombre + " (variante)"] if con_variante else [nombre]
        if i == (n + 1) // 2:
            partes.append("**DESCANSO (3 min)**" + NL + NL)
    # la sesión acaba con un ejercicio más, sin bloque de vuelta a la calma (plan_sesion.CON_VUELTA_A_LA_CALMA)
    partes.append(f"**Fundamentos**: {contenido}.")
    nombres += ["Calentamiento: Cazadores"]
    return {"sesion": "".join(partes), "diagramas": [{"id": f"d{i}", "nombre": nom, "titulo": "", "svg": SVG_OK}
                                                     for i, nom in enumerate(nombres)]}


RESPUESTAS_REGLAMENTO = {
    "pista delantera": "El equipo dispone de 8 segundos para pasar el balón a su pista delantera.",
    "rebote": "Si el balón toca el aro y el equipo atacante recupera el rebote, el reloj se reinicia a 14 segundos.",
    "eliminado": "En reglamento FIBA un jugador queda eliminado al cometer 5 faltas personales.",
    "3 segundos": "Un atacante no puede permanecer más de tres segundos seguidos en la zona restringida "
                  "rival mientras su equipo controla el balón.",
    "periodos": "En alevín cada jugador debe jugar al menos dos periodos completos.",
    "minibasket": "En minibasket el aro está a 2,60 m de altura.",
    "disruptiva": "La falta disruptiva es un contacto ilegal que no llega a flagrante y no descalifica al jugador.",
}


class ApiSimulada(BaseHTTPRequestHandler):
    """Imita /generar, /ejercicio y /reglamento. El atributo de clase 'modo' decide si
    las respuestas son correctas ('bueno'), defectuosas ('malo') o si la primera
    petición de reglamento devuelve 429 ('429')."""
    modo = "bueno"
    peticiones = []
    ya_429 = False

    def log_message(self, *args):
        pass

    def _responder(self, status, cuerpo, cabeceras=None):
        datos = json.dumps(cuerpo, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        for k, v in (cabeceras or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)

    def do_GET(self):
        self._responder(200, {"status": "ok", "version": "simulada"})

    def do_POST(self):
        largo = int(self.headers.get("Content-Length", 0))
        req = json.loads(self.rfile.read(largo) or b"{}")
        type(self).peticiones.append((self.path, req))
        malo = type(self).modo == "malo"

        if self.path == "/generar":
            resp = sesion_buena(req["edad"], req["objetivo"], req["duracion"])
            if malo and req["edad"] == "U10":
                resp["sesion"] = resp["sesion"].replace(
                    "**Fundamentos**:", "Hoy trabajamos el bloqueo directo según el manual.\n\n**Fundamentos**:")
                resp["diagramas"][0]["svg"] = SVG_NO_DISPONIBLE
            elif malo and req["edad"] == "U14":
                resp["sesion"] = resp["sesion"].rsplit("**Fundamentos**", 1)[0] + \
                    "**Fundamentos**: posición básica, deslizamiento y"
            elif malo and req["edad"] == "U16":
                resp["sesion"] = resp["sesion"].replace("**CALENTAMIENTO (10 min)**", "")
                resp["diagramas"] = resp["diagramas"][:2]
            elif malo and req["edad"] == "U18":
                return self._responder(500, {"detail": "No se pudo generar la sesión"})
            return self._responder(200, resp)

        if self.path == "/ejercicio":
            es_1c1 = req["edad"] == "U12"
            diagrama = json.loads(json.dumps(DIAGRAMA_1C1 if es_1c1 else DIAGRAMA_2C1))
            ej = {
                "nombre": "1c1 desde el 45°" if es_1c1 else "2c1 en media pista",
                "descripcion": "El atacante recibe en el 45° y ataca el aro." if es_1c1
                               else "Dos atacantes contra un defensor que espera en la zona.",
                "puntos_clave": ["Salida cruzada."],
                "diagrama": diagrama,
            }
            svgs = [{"titulo": "", "svg": SVG_OK}]
            if malo and es_1c1:
                ej["diagrama"]["movimientos"].append({"de": "A9", "tipo": "tiro", "orden": 3})
                ej["descripcion"] += " Variante con presión a toda la pista."
            elif malo:
                svgs = [{"titulo": "", "svg": "<svg><g></svg>"}]
                ej["descripcion"] += " Fuente: material_tecnico.pdf"
            return self._responder(200, {"ejercicio": ej, "diagramas": svgs})

        if self.path == "/reglamento":
            if type(self).modo == "429" and not type(self).ya_429:
                type(self).ya_429 = True
                return self._responder(429, {"error": "Rate limit exceeded"}, {"Retry-After": "0"})
            pregunta = req["pregunta"]
            respuesta = next(v for k, v in RESPUESTAS_REGLAMENTO.items() if k in pregunta)
            if malo and "minibasket" in pregunta:
                respuesta = "Depende de la competición, consulta la normativa de tu federación."
            elif malo and "eliminado" in pregunta:
                respuesta += " (según el documento reglamento_fiba_normas_clave.md)"
            return self._responder(200, {"pregunta": pregunta, "respuesta": respuesta})

        self._responder(404, {"detail": "Not Found"})


@pytest.fixture
def api():
    ApiSimulada.modo = "bueno"
    ApiSimulada.peticiones = []
    ApiSimulada.ya_429 = False
    servidor = ThreadingHTTPServer(("localhost", 0), ApiSimulada)
    hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()
    yield f"http://localhost:{servidor.server_address[1]}"
    servidor.shutdown()
    servidor.server_close()


def _leer(ruta):
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def _por_id(informe):
    return {r["id"]: r for r in informe["resultados"]}


def _fallidos(resultado):
    return {n for n, c in resultado["criterios"].items() if not c["ok"]}


# ─── Casos fijos ─────────────────────────────────────────────────────────────

def test_casos_fijos():
    assert len(regresion.CASOS_SESIONES) == 6
    assert len(regresion.CASOS_EJERCICIOS) == 2
    assert len(regresion.CASOS_REGLAMENTO) == 7
    ids = [c["id"] for c in regresion.CASOS_SESIONES + regresion.CASOS_EJERCICIOS + regresion.CASOS_REGLAMENTO]
    assert len(ids) == len(set(ids))
    for c in regresion.CASOS_SESIONES:
        assert 30 <= c["duracion"] <= 180


# ─── Arnés completo contra la API simulada ───────────────────────────────────

def test_api_buena_pasa(api, tmp_path):
    salida = tmp_path / "bueno.json"
    assert regresion.main(["--api", api, "--salida", str(salida)]) == 0

    informe = _leer(salida)
    assert informe["resumen"]["casos"] == 15
    assert informe["resumen"]["fallidos"] == []
    assert informe["version_api"] == "simulada"
    res = _por_id(informe)
    # U10 a 60 min: 4 ejercicios y el primero partido en N.1/N.2 → 5 bloques + calentamiento.
    assert res["ses_u10_bote"]["metricas"]["diagramas_esperados"] == 6
    assert res["ses_u10_bote"]["metricas"]["ejercicios"] == 4
    # U16 a 90 min: 5 ejercicios sin variantes → 5 bloques + calentamiento.
    assert res["ses_u16_bloqueo"]["metricas"]["diagramas_esperados"] == 6
    assert res["ses_u16_bloqueo"]["metricas"]["ejercicios"] == 5
    # El validador semántico real se ha aplicado a los ejercicios.
    assert "omitido" not in res["ej_u12_1c1_45"]["criterios"]["diagrama_valido"]["detalle"]
    # Peticiones exactas que se mandan a la API.
    assert ("/generar", {"edad": "U12", "duracion": 75, "objetivo": "1c1"}) in ApiSimulada.peticiones


def test_api_mala_falla_con_criterios_concretos(api, tmp_path):
    ApiSimulada.modo = "malo"
    salida = tmp_path / "malo.json"
    assert regresion.main(["--api", api, "--salida", str(salida)]) == 1

    res = _por_id(_leer(salida))
    assert _fallidos(res["ses_u10_bote"]) == {"reglas_edad", "sin_fugas"}
    assert res["ses_u10_bote"]["metricas"]["diagramas_no_disponibles"] == 1
    assert _fallidos(res["ses_u14_defensa"]) == {"no_truncado"}
    assert _fallidos(res["ses_u16_bloqueo"]) == {"secciones", "diagramas"}
    assert "http_200" in _fallidos(res["ses_u18_tiro"])
    assert res["ses_senior_transicion"]["aprobado"]
    assert _fallidos(res["ej_u12_1c1_45"]) == {"diagrama_valido", "reglas_edad"}
    assert _fallidos(res["ej_u16_2c1"]) == {"diagrama", "sin_fugas"}
    assert _fallidos(res["reg_aro_minibasket"]) == {"palabras_clave"}
    assert _fallidos(res["reg_faltas_eliminacion"]) == {"sin_fugas"}
    assert res["reg_8_segundos"]["aprobado"]


def test_comparar_marca_empeoramientos(api, tmp_path):
    base = tmp_path / "base.json"
    assert regresion.main(["--api", api, "--salida", str(base)]) == 0

    # Misma calidad → sin empeoramientos.
    igual = tmp_path / "igual.json"
    assert regresion.main(["--api", api, "--salida", str(igual), "--comparar", str(base)]) == 0
    assert _leer(igual)["resumen"]["empeoramientos"] == []

    # Peor calidad → empeoramientos por caso y criterio.
    ApiSimulada.modo = "malo"
    peor = tmp_path / "peor.json"
    assert regresion.main(["--api", api, "--salida", str(peor), "--comparar", str(base)]) == 1
    empeoramientos = _leer(peor)["resumen"]["empeoramientos"]
    assert any(e.startswith("ses_u14_defensa: 'no_truncado'") for e in empeoramientos)
    assert any(e.startswith("ses_u10_bote: diagramas no disponibles 0 → 1") for e in empeoramientos)
    assert any(e.startswith("reg_aro_minibasket: palabras clave 1 → 0") for e in empeoramientos)


def test_comparar_fichero_inexistente(api, tmp_path):
    assert regresion.main(["--api", api, "--comparar", str(tmp_path / "no_existe.json"),
                           "--salida", str(tmp_path / "x.json")]) == 2


def test_solo_reglamento(api, tmp_path):
    salida = tmp_path / "reg.json"
    assert regresion.main(["--api", api, "--salida", str(salida), "--solo", "reglamento"]) == 0
    informe = _leer(salida)
    assert {r["tipo"] for r in informe["resultados"]} == {"reglamento"}
    assert informe["resumen"]["casos"] == 7
    assert all(ruta == "/reglamento" for ruta, _ in ApiSimulada.peticiones)


def test_reintenta_tras_429(api, tmp_path):
    ApiSimulada.modo = "429"
    salida = tmp_path / "429.json"
    assert regresion.main(["--api", api, "--salida", str(salida), "--solo", "reglamento"]) == 0
    assert len(ApiSimulada.peticiones) == 8   # 7 casos + 1 reintento


def test_api_caida(tmp_path):
    salida = tmp_path / "caida.json"
    # Puerto local sin nada escuchando.
    assert regresion.main(["--api", "http://localhost:9", "--salida", str(salida), "--solo", "reglamento"]) == 1
    assert all(not r["aprobado"] for r in _leer(salida)["resultados"])


def test_cli_codigo_de_salida(api, tmp_path):
    """Lanzado como script (como se usará de verdad) devuelve el código de salida."""
    script = RAIZ / "tools" / "regresion.py"
    ok = subprocess.run([sys.executable, str(script), "--api", api, "--solo", "reglamento",
                         "--salida", str(tmp_path / "a.json")], capture_output=True, text=True)
    assert ok.returncode == 0, ok.stdout + ok.stderr
    assert "7/7 casos aprobados" in ok.stdout

    ApiSimulada.modo = "malo"
    mal = subprocess.run([sys.executable, str(script), "--api", api, "--solo", "reglamento",
                          "--salida", str(tmp_path / "b.json")], capture_output=True, text=True)
    assert mal.returncode == 1
    assert "FALLO" in mal.stdout


# ─── Funciones de comprobación ───────────────────────────────────────────────

@pytest.mark.parametrize("texto", [
    "Trabajamos el bloqueo directo en el ala.",
    "Juego: pick and roll central",
    "Organización: defensa zonal 2-3 en media pista.",
    "Presión a toda la pista tras canasta.",
    "Finalización con aro pasado.",
    "Bandeja convencional por la derecha.",
    "Defensa en zona para cerrar el rebote.",
])
def test_contenido_prohibido_en_formacion(texto):
    assert regresion.buscar_contenido_prohibido(texto, "U10")
    assert regresion.buscar_contenido_prohibido(texto, "Alevín")


@pytest.mark.parametrize("texto", [
    "Sin bloqueos directos ni indirectos en esta categoría.",
    "No se trabaja la defensa zonal.",
    "Evitamos la presión a toda la pista.",
    "Defensa individual en la zona pintada.",
    "Bote de protección y bandeja con mano dominante.",
])
def test_contenido_permitido_o_negado(texto):
    assert regresion.buscar_contenido_prohibido(texto, "U12") == []


def test_reglas_de_edad_solo_hasta_u12():
    assert regresion.buscar_contenido_prohibido("Bloqueo directo central.", "U16") == []


@pytest.mark.parametrize("texto", [
    "Según el documento de la federación...",
    "Según el manual, la regla es...",
    "Fuente: reglamento oficial",
    "Ver apuntes.pdf",
    "Como dice bloqueos.md",
    "Leído de /app/data/teoria",
    "--- MATERIAL PROPIO ---",
])
def test_fugas_detectadas(texto):
    assert regresion.buscar_fugas(texto)


@pytest.mark.parametrize("texto", [
    "El aro está a 2,60 m.",
    "Tiro desde el 45° tras bote. Cambio de ritmo.",
    "Fundamentos: bote, pase y tiro.",
])
def test_sin_fugas(texto):
    assert regresion.buscar_fugas(texto) == []


@pytest.mark.parametrize("texto, esperado", [
    ("**VUELTA A LA CALMA**\n\n**Fundamentos**: bote, pase y tiro.", True),
    ("**Fundamentos**: bote de protección, cambio de mano", True),
    ("**Fundamentos**: bote de protección, cambio de mano y", False),
    ("**Fundamentos**: bote de protección,", False),
    ("**Fundamentos**:", False),
    ("Ejercicio 3: 3c3\nOrganización: tres contra tres en", False),
    ("**Error generando sesión**: timeout.", False),
    ("", False),
])
def test_texto_completo(texto, esperado):
    assert regresion.texto_completo(texto) is esperado


def test_contar_ejercicios_con_variantes():
    texto = sesion_buena("U10", "bote", 60)["sesion"]
    assert regresion.contar_ejercicios(texto) == (4, 5)
    assert regresion.diagramas_esperados_sesion(texto) == 6


# ─── Número de ejercicios esperado: sale del plan, no es fijo ────────────────

@pytest.mark.parametrize("edad,duracion,esperado", [("U10", 60, 4), ("U12", 75, 6), ("U14", 90, 6), ("U16", 90, 5)])
def test_ejercicios_esperados_salen_del_plan(edad, duracion, esperado):
    assert regresion.ejercicios_esperados({"edad": edad, "duracion": duracion}) == esperado


def _evaluar(edad, duracion, n_ejercicios_en_el_texto):
    caso = {"id": "x", "edad": edad, "duracion": duracion, "objetivo": "bote"}
    resp = sesion_buena(edad, "bote", duracion)
    if n_ejercicios_en_el_texto is not None:
        # quita ejercicios del final de la parte principal hasta dejar los pedidos
        texto = resp["sesion"]
        while regresion.contar_ejercicios(texto)[0] > n_ejercicios_en_el_texto:
            ultimo = max(int(m) for m, _ in regresion.CAB_EJERCICIO.findall(texto))
            ini = texto.index(f"Ejercicio {ultimo}")
            fin = texto.index("**Fundamentos**")
            texto = texto[:ini] + texto[fin:]
        resp["sesion"] = texto
    return regresion.evaluar_sesion(caso, 200, resp, 1.0)


def test_el_arnes_acepta_el_numero_de_ejercicios_que_pide_el_plan():
    assert _evaluar("U10", 60, None)["criterios"]["num_ejercicios"]["ok"]
    assert _evaluar("U16", 90, None)["criterios"]["num_ejercicios"]["ok"]


def test_el_arnes_rechaza_un_numero_de_ejercicios_distinto_al_del_plan():
    # el plan de U10 a 60 min pide 4 ejercicios: con 3 falla y lo dice
    criterio = _evaluar("U10", 60, 3)["criterios"]["num_ejercicios"]
    assert not criterio["ok"] and "3" in criterio["detalle"] and "4" in criterio["detalle"]
