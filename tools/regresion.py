#!/usr/bin/env python3
"""
Test de regresión en vivo contra la API real de MiPizarra (pipeline completo: RAG,
LLM, validación y renderer). Sirve para detectar si un cambio de modelo o de prompts
empeora la calidad: lanza siempre los mismos casos fijos y guarda métricas comparables
entre ejecuciones.

A diferencia de tools/evaluar_modelo.py (que llama a Ollama con prompts propios), aquí
se llama a los endpoints HTTP de la API, así que se evalúa exactamente lo que ve el
usuario.

Casos (fijos y deterministas, ver CASOS_* más abajo):
  - 6 sesiones (POST /generar)
  - 2 ejercicios sueltos con diagrama (POST /ejercicio)
  - 7 preguntas de reglamento (POST /reglamento)

Criterios duros (si alguno falla, código de salida 1):
  - Sesiones: HTTP 200; las 4 secciones (CALENTAMIENTO, PARTE PRINCIPAL, VUELTA A LA
    CALMA, Fundamentos); exactamente 3 ejercicios; texto no truncado; un diagrama por
    cada bloque esperado y todos los SVG bien formados.
  - Ejercicios: HTTP 200; nombre y descripción; diagrama presente, semánticamente
    válido (_validar_diagrama) y SVG bien formado.
  - Reglamento: HTTP 200; respuesta no vacía; todas las palabras clave esperadas.
  - Todos: reglas de edad (≤U12) y ninguna fuga de fuentes.
Métricas blandas (se comparan con --comparar): latencia, diagramas "no disponibles".

Uso (necesita la API levantada con Ollama y GPU; no se ejecuta en la nube):
  python tools/regresion.py
  python tools/regresion.py --api http://localhost:8090 --solo sesiones
  python tools/regresion.py --comparar data/regresion/2026-01-01_1200.json

Si la API tiene INTERNAL_SECRET, exporta la misma variable de entorno antes de lanzar
el script y se enviará en la cabecera X-Internal-Secret.

Ojo con el rate limiting de la API (/generar: 3/minuto y 10/hora por IP): el script
espera y reintenta ante un 429, pero dos ejecuciones completas seguidas dentro de la
misma hora agotarán el cupo de /generar. Reiniciar el contenedor de la API lo resetea.
"""
import argparse
import datetime
import importlib.util
import json
import os
import re
import sys
import time
import types
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

RAIZ = Path(__file__).resolve().parent.parent

TIMEOUT_SESION     = 900   # s — sesión + reintento por truncado + diagramas automáticos
TIMEOUT_EJERCICIO  = 300
TIMEOUT_REGLAMENTO = 180
MAX_REINTENTOS_429 = 3
ESPERA_429_DEFECTO = 30    # s si la API no manda Retry-After

# Criterios de latencia para --comparar: solo aviso, no empeoramiento (el tiempo de
# GPU varía mucho entre ejecuciones).
FACTOR_LATENCIA_AVISO = 1.5
MARGEN_LATENCIA_AVISO = 10.0  # s

EDADES_FORMACION = {"U8", "U10", "U12", "Prebenjamín", "Benjamín", "Alevín"}

# ─── Casos fijos ─────────────────────────────────────────────────────────────

CASOS_SESIONES = [
    {"id": "ses_u10_bote",        "edad": "U10",    "duracion": 60, "objetivo": "bote"},
    {"id": "ses_u12_1c1",         "edad": "U12",    "duracion": 75, "objetivo": "1c1"},
    {"id": "ses_u14_defensa",     "edad": "U14",    "duracion": 90, "objetivo": "defensa"},
    {"id": "ses_u16_bloqueo",     "edad": "U16",    "duracion": 90, "objetivo": "bloqueo directo"},
    {"id": "ses_u18_tiro",        "edad": "U18",    "duracion": 75, "objetivo": "tiro"},
    {"id": "ses_senior_transicion", "edad": "Senior", "duracion": 90, "objetivo": "transición"},
]

CASOS_EJERCICIOS = [
    {"id": "ej_u12_1c1_45", "edad": "U12", "objetivo": "1c1",
     "descripcion": "1c1 desde el 45° tras recibir, con salida cruzada y finalización"},
    {"id": "ej_u16_2c1", "edad": "U16", "objetivo": "contraataque",
     "descripcion": "2c1 en media pista: dos atacantes contra un defensor que espera en la zona"},
]

# Cada grupo de "claves" es una lista de alternativas; basta con que aparezca una de
# ellas, y tienen que aparecer todos los grupos (comparación sin tildes ni mayúsculas).
CASOS_REGLAMENTO = [
    {"id": "reg_8_segundos",
     "pregunta": "¿Cuántos segundos tiene un equipo para pasar el balón a pista delantera?",
     "claves": [["8 segundos", "ocho segundos"]]},
    {"id": "reg_rebote_ofensivo",
     "pregunta": "En reglamento FIBA, si tras un tiro el balón toca el aro y el equipo atacante "
                 "recupera el rebote, ¿a cuántos segundos se reinicia el reloj de posesión?",
     "claves": [["14 segundos", "catorce segundos", "14 s"]]},
    {"id": "reg_faltas_eliminacion",
     "pregunta": "¿Con cuántas faltas personales queda eliminado un jugador en reglamento FIBA?",
     "claves": [["5 faltas", "cinco faltas", "quinta falta", "5 personales", "cinco personales"]]},
    {"id": "reg_3_segundos",
     "pregunta": "¿En qué consiste la regla de los 3 segundos?",
     "claves": [["3 segundos", "tres segundos"], ["zona", "area restringida", "pintura"]]},
    {"id": "reg_falta_disruptiva",
     "pregunta": "¿Qué es una falta disruptiva en el reglamento FIBA actual y puede descalificar a un jugador?",
     "claves": [["disruptiva"], ["flagrante"]]},
    {"id": "reg_aragon_periodos_alevin", "ambito": "aragon",
     "pregunta": "En los Juegos Escolares de Aragón, ¿cuántos periodos tiene que jugar como mínimo cada "
                 "jugador en alevín?",
     "claves": [["dos periodos", "2 periodos"]]},
    {"id": "reg_aro_minibasket",
     "pregunta": "¿A qué altura está el aro en minibasket?",
     "claves": [["2,60", "2.60", "260 cm", "2 metros y 60", "2,6 m"]]},
]

# ─── Patrones de comprobación ────────────────────────────────────────────────

SECCIONES = {
    "CALENTAMIENTO":     re.compile(r"CALENTAMIENTO"),
    "PARTE PRINCIPAL":   re.compile(r"PARTE PRINCIPAL"),
    "VUELTA A LA CALMA": re.compile(r"VUELTA A LA CALMA"),
    "Fundamentos":       re.compile(r"fundamentos", re.IGNORECASE),
}

CAB_EJERCICIO = re.compile(r"^\s*(?:\*\*)?Ejercicio\s+(\d+)(?:\.(\d+))?\s*(?:\([^)]*\))?\s*:", re.MULTILINE)

# Contenido que no se trabaja en U12 e inferiores (docs/coordenadas.md, data/teoria/).
# Se buscan sobre texto normalizado (minúsculas, sin tildes).
PROHIBIDOS_FORMACION = {
    "bloqueo directo/indirecto": re.compile(r"\bbloqueos?\s+(?:directos?|indirectos?)\b|\bpick\s*(?:and|&|y|n)\s*roll\b"),
    "defensa zonal":             re.compile(r"\bdefensas?\s+(?:zonal(?:es)?|en\s+zona|de\s+zona|individual\s+y\s+zona)\b"
                                            r"|\bzona\s+(?:2-3|3-2|1-3-1|2-1-2|1-2-2)\b"),
    "presión a pista completa":  re.compile(r"\bpresion(?:es)?\s+(?:defensiva\s+)?(?:a|en|de)\s+"
                                            r"(?:toda\s+la\s+pista|pista\s+completa|todo\s+(?:el\s+)?campo|campo\s+completo)\b"
                                            r"|\bfull\s*court\s+press"),
    "aro pasado":                re.compile(r"\baro\s+pasado\b"),
    "bandeja convencional":      re.compile(r"\bbandeja\s+convencional\b"),
}

# Si el fragmento (frase) que contiene la coincidencia la niega antes («sin bloqueos
# directos», «no se trabaja la defensa zonal»), no cuenta como contenido a trabajar.
NEGACION = re.compile(r"\b(?:sin|no|nunca|ni|evit\w*|prohib\w*|todavia|aun)\b")

FUGAS = [
    ("mención a .pdf",          re.compile(r"\.pdf\b", re.IGNORECASE)),
    ("«según el documento»",    re.compile(r"seg[uú]n\s+el\s+documento", re.IGNORECASE)),
    ("«según el manual»",       re.compile(r"seg[uú]n\s+el\s+manual", re.IGNORECASE)),
    ("«fuente:»",               re.compile(r"\bfuentes?\s*:", re.IGNORECASE)),
    ("nombre de fichero",       re.compile(r"\b[\w\-]+\.(?:pdf|md|docx?|txt|json|csv|epub|pptx?|xlsx?|html?)\b",
                                           re.IGNORECASE)),
    ("ruta de fichero",         re.compile(r"(?<![\w/])/(?:app|data|home|mnt|tmp|root)/", re.IGNORECASE)),
    ("cabecera de contexto RAG", re.compile(r"MATERIAL PROPIO|EXTRACTOS DE REGLAMENTO|CONTEXTO METODOL[OÓ]GICO")),
]

PLACEHOLDER_DIAGRAMA = "Diagrama no disponible"

# Última palabra que delata una frase cortada a medias.
PALABRAS_COLGANTES = {
    "y", "o", "u", "e", "de", "del", "con", "a", "al", "el", "la", "los", "las", "un", "una",
    "para", "en", "por", "que", "se", "su", "sus", "sin", "entre", "hacia", "desde", "tras",
}


def _normalizar(texto: str) -> str:
    """Minúsculas y sin tildes (para buscar palabras clave y reglas de edad)."""
    sin_tildes = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in sin_tildes if not unicodedata.combining(c)).lower()


# ─── Validador de diagramas de la API (opcional) ─────────────────────────────

def _cargar_validador():
    """Carga _validar_diagrama de rag_engine sin arrancar ChromaDB ni Ollama.
    rag_engine crea un cliente de ChromaDB y un embedding de Ollama al importarse;
    se sustituyen temporalmente por módulos vacíos (la validación no los usa) y se
    restaura sys.modules al terminar. Funciona tanto en el repo (api/) como dentro del
    contenedor (rag_engine.py en /app). Devuelve None si no se encuentra."""
    candidatos = [RAIZ / "api", RAIZ]
    api_dir = next((d for d in candidatos if (d / "rag_engine.py").exists()), None)
    if api_dir is None:
        return None

    nombres = ["chromadb", "llama_index", "llama_index.embeddings", "llama_index.embeddings.ollama", "prompts"]
    guardados = {n: sys.modules.get(n) for n in nombres}
    path_original = list(sys.path)
    try:
        for n in nombres[:-1]:
            sys.modules[n] = types.ModuleType(n)
        sys.modules["chromadb"].PersistentClient = lambda *a, **k: None
        sys.modules["llama_index.embeddings.ollama"].OllamaEmbedding = lambda *a, **k: None
        sys.modules.pop("prompts", None)
        sys.path.insert(0, str(api_dir))
        spec = importlib.util.spec_from_file_location("_rag_engine_regresion", api_dir / "rag_engine.py")
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
        return modulo._validar_diagrama
    except Exception as e:
        print(f"⚠ No se pudo cargar _validar_diagrama ({e}); se omite la validación semántica.")
        return None
    finally:
        sys.path[:] = path_original
        for n, m in guardados.items():
            if m is None:
                sys.modules.pop(n, None)
            else:
                sys.modules[n] = m


# ─── Comprobaciones (funciones puras, testeables sin API) ────────────────────

def buscar_fugas(texto: str) -> list[str]:
    """Indicios de que la respuesta cita material de referencia o el contexto interno."""
    encontradas = []
    for nombre, patron in FUGAS:
        m = patron.search(texto or "")
        if m:
            encontradas.append(f"{nombre}: «{m.group(0)}»")
    return encontradas


def buscar_contenido_prohibido(texto: str, edad: str) -> list[str]:
    """Contenidos no adecuados para U12 e inferiores presentes como algo a trabajar."""
    if edad not in EDADES_FORMACION:
        return []
    encontrados = []
    for fragmento in re.split(r"[.\n;:!?]+", _normalizar(texto or "")):
        for nombre, patron in PROHIBIDOS_FORMACION.items():
            m = patron.search(fragmento)
            if m and not NEGACION.search(fragmento[:m.start()]):
                encontrados.append(f"{nombre}: «{fragmento.strip()[:80]}»")
    return encontrados


def contar_ejercicios(texto: str) -> tuple[int, int]:
    """(nº de ejercicios distintos N, nº de bloques N/N.M) en la parte principal."""
    cabeceras = CAB_EJERCICIO.findall(texto or "")
    return len({n for n, _ in cabeceras}), len(cabeceras)


def texto_completo(texto: str) -> bool:
    """La sesión termina en frase completa: con puntuación final, o con la línea de
    Fundamentos (una lista) sin acabar en una palabra que deje la frase colgando."""
    limpio = (texto or "").rstrip().rstrip("*_ ").rstrip()
    if not limpio or limpio.startswith("**Error"):
        return False
    if limpio[-1] in ".!?…)»\"'":
        return True
    ultima_linea = limpio.splitlines()[-1]
    if not re.search(r"fundamentos", ultima_linea, re.IGNORECASE):
        return False
    contenido = re.sub(r"^.*?fundamentos\W*", "", ultima_linea, flags=re.IGNORECASE).strip()
    if not contenido:
        return False
    ultima_palabra = re.findall(r"\w+", _normalizar(contenido))[-1:]
    return bool(ultima_palabra) and ultima_palabra[0] not in PALABRAS_COLGANTES \
        and not contenido.endswith((",", "-", "("))


def svg_bien_formado(svg: str) -> bool:
    try:
        raiz = ET.fromstring(svg)
    except ET.ParseError:
        return False
    return raiz.tag in ("svg", "{http://www.w3.org/2000/svg}svg")


def diagramas_esperados_sesion(texto: str) -> int:
    """Mismo criterio que /generar: un diagrama por bloque 'Ejercicio N[.M]:' (máx. 6)
    más uno por el juego de calentamiento y otro por el de vuelta a la calma."""
    _, bloques = contar_ejercicios(texto)
    juegos = 0
    for patron in (r"\*\*CALENTAMIENTO[^\n]*\*\*(.*?)(?=\n---|\*\*PARTE PRINCIPAL|\Z)",
                   r"\*\*VUELTA A LA CALMA[^\n]*\*\*(.*?)(?=\*\*Fundamentos|\Z)"):
        m = re.search(patron, texto or "", re.DOTALL | re.IGNORECASE)
        if m and re.search(r"Juego:\s*\S", m.group(1)):
            juegos += 1
    return min(bloques, 6) + juegos


def _criterio(ok: bool, detalle: str = "") -> dict:
    return {"ok": bool(ok), "detalle": detalle}


def evaluar_sesion(caso: dict, status: int, datos: dict | None, latencia: float) -> dict:
    criterios, metricas = {}, {"latencia_s": round(latencia, 1)}
    criterios["http_200"] = _criterio(status == 200, f"HTTP {status}")
    texto = (datos or {}).get("sesion", "") if status == 200 else ""
    diagramas = (datos or {}).get("diagramas", []) if status == 200 else []

    faltan = [s for s, p in SECCIONES.items() if not p.search(texto)]
    criterios["secciones"] = _criterio(not faltan, f"faltan: {', '.join(faltan)}" if faltan else "")

    n_ej, n_bloques = contar_ejercicios(texto)
    criterios["tres_ejercicios"] = _criterio(n_ej == 3, f"{n_ej} ejercicio(s)")
    criterios["no_truncado"] = _criterio(texto_completo(texto), "" if texto_completo(texto)
                                         else f"termina en: «{texto.rstrip()[-60:]}»")

    esperados = diagramas_esperados_sesion(texto)
    # Ejercicios con varios diagramas (fases) devuelven varias entradas con el mismo nombre.
    generados = len({d.get("nombre") for d in diagramas})
    mal_formados = sum(1 for d in diagramas if not svg_bien_formado(d.get("svg", "")))
    no_disponibles = sum(1 for d in diagramas if PLACEHOLDER_DIAGRAMA in d.get("svg", ""))
    criterios["diagramas"] = _criterio(
        status == 200 and generados >= esperados and mal_formados == 0,
        f"{generados}/{esperados} generados, {mal_formados} SVG mal formado(s)",
    )

    prohibidos = buscar_contenido_prohibido(texto, caso["edad"])
    criterios["reglas_edad"] = _criterio(not prohibidos, "; ".join(prohibidos))
    fugas = buscar_fugas(texto)
    criterios["sin_fugas"] = _criterio(not fugas, "; ".join(fugas))

    metricas.update({
        "ejercicios": n_ej,
        "bloques_ejercicio": n_bloques,
        "diagramas_esperados": esperados,
        "diagramas_generados": generados,
        "diagramas_svg": len(diagramas),
        "diagramas_mal_formados": mal_formados,
        "diagramas_no_disponibles": no_disponibles,
        "longitud_texto": len(texto),
    })
    return {"criterios": criterios, "metricas": metricas, "respuesta": {"sesion": texto}}


def evaluar_ejercicio(caso: dict, status: int, datos: dict | None, latencia: float,
                      validador=None) -> dict:
    criterios, metricas = {}, {"latencia_s": round(latencia, 1)}
    criterios["http_200"] = _criterio(status == 200, f"HTTP {status}")
    ej = ((datos or {}).get("ejercicio") or {}) if status == 200 else {}
    svgs = (datos or {}).get("diagramas", []) if status == 200 else []

    criterios["contenido"] = _criterio(
        bool(str(ej.get("nombre", "")).strip()) and bool(str(ej.get("descripcion", "")).strip()),
        "falta nombre o descripción" if not (ej.get("nombre") and ej.get("descripcion")) else "",
    )

    diagramas_json = ej.get("diagramas") or ([ej["diagrama"]] if isinstance(ej.get("diagrama"), dict) else [])
    mal_formados = sum(1 for d in svgs if not svg_bien_formado(d.get("svg", "")))
    criterios["diagrama"] = _criterio(
        bool(diagramas_json) and bool(svgs) and mal_formados == 0,
        f"{len(svgs)} SVG, {mal_formados} mal formado(s)" if diagramas_json else "sin diagrama",
    )

    if validador is None:
        criterios["diagrama_valido"] = {"ok": True, "detalle": "omitido (validador no disponible)"}
    else:
        errores = []
        for d in diagramas_json:
            try:
                error = validador(d, ej.get("nombre", ""))
            except Exception as e:
                error = f"excepción validando: {e}"
            if error:
                errores.append(error)
        criterios["diagrama_valido"] = _criterio(bool(diagramas_json) and not errores,
                                                 "; ".join(errores) if errores else "")

    texto = json.dumps(ej, ensure_ascii=False)
    texto_legible = " ".join(
        [str(ej.get("nombre", "")), str(ej.get("descripcion", ""))]
        + [str(p) for p in ej.get("puntos_clave", []) if isinstance(p, str)]
    )
    prohibidos = buscar_contenido_prohibido(texto_legible, caso["edad"])
    criterios["reglas_edad"] = _criterio(not prohibidos, "; ".join(prohibidos))
    fugas = buscar_fugas(texto)
    criterios["sin_fugas"] = _criterio(not fugas, "; ".join(fugas))

    metricas.update({"diagramas_json": len(diagramas_json), "diagramas_svg": len(svgs)})
    return {"criterios": criterios, "metricas": metricas, "respuesta": {"ejercicio": ej}}


def evaluar_reglamento(caso: dict, status: int, datos: dict | None, latencia: float) -> dict:
    criterios, metricas = {}, {"latencia_s": round(latencia, 1)}
    criterios["http_200"] = _criterio(status == 200, f"HTTP {status}")
    respuesta = (datos or {}).get("respuesta", "") if status == 200 else ""
    criterios["respuesta"] = _criterio(
        bool(respuesta.strip()) and not respuesta.startswith("No se pudo responder"),
        "vacía o error" if not respuesta.strip() or respuesta.startswith("No se pudo") else "",
    )

    norm = _normalizar(respuesta)
    faltan = [grupo[0] for grupo in caso["claves"]
              if not any(_normalizar(alt) in norm for alt in grupo)]
    criterios["palabras_clave"] = _criterio(not faltan, f"faltan: {', '.join(faltan)}" if faltan else "")
    fugas = buscar_fugas(respuesta)
    criterios["sin_fugas"] = _criterio(not fugas, "; ".join(fugas))

    metricas.update({
        "claves_encontradas": len(caso["claves"]) - len(faltan),
        "claves_total": len(caso["claves"]),
        "longitud_texto": len(respuesta),
    })
    return {"criterios": criterios, "metricas": metricas, "respuesta": {"respuesta": respuesta}}


# ─── Ejecución ───────────────────────────────────────────────────────────────

def _post(api: str, ruta: str, payload: dict, timeout: int, cabeceras: dict) -> tuple[int, dict | None, float, str]:
    """POST con reintento ante 429 (rate limiting). Devuelve (status, json, latencia, error).
    La latencia es la de la petición que respondió, sin contar las esperas por 429."""
    for intento in range(MAX_REINTENTOS_429 + 1):
        inicio = time.monotonic()
        try:
            r = requests.post(f"{api.rstrip('/')}{ruta}", json=payload, timeout=timeout, headers=cabeceras)
        except requests.RequestException as e:
            return 0, None, time.monotonic() - inicio, f"{type(e).__name__}: {e}"
        latencia = time.monotonic() - inicio
        if r.status_code == 429 and intento < MAX_REINTENTOS_429:
            try:
                espera = float(r.headers.get("Retry-After", ESPERA_429_DEFECTO))
            except ValueError:
                espera = ESPERA_429_DEFECTO
            print(f"  · 429 en {ruta}, esperando {espera:.0f} s (reintento {intento + 1}/{MAX_REINTENTOS_429})")
            time.sleep(espera)
            continue
        try:
            datos = r.json()
        except ValueError:
            datos = None
        return r.status_code, datos, latencia, "" if r.ok else r.text[:200]
    return 429, None, 0.0, "rate limit agotado"


def ejecutar(api: str, solo: str | None, validador=None) -> list[dict]:
    cabeceras = {}
    if os.environ.get("INTERNAL_SECRET"):
        cabeceras["X-Internal-Secret"] = os.environ["INTERNAL_SECRET"]

    resultados = []

    def registrar(tipo, caso, peticion, evaluacion, error):
        aprobado = all(c["ok"] for c in evaluacion["criterios"].values())
        resultados.append({
            "id": caso["id"], "tipo": tipo, "peticion": peticion, "aprobado": aprobado,
            "error": error, **evaluacion,
        })
        fallos = [n for n, c in evaluacion["criterios"].items() if not c["ok"]]
        estado = "OK" if aprobado else f"FALLO ({', '.join(fallos)})"
        print(f"  {caso['id']:<24} {evaluacion['metricas']['latencia_s']:>7.1f} s  {estado}")

    if solo in (None, "sesiones"):
        print("Sesiones (POST /generar)")
        for caso in CASOS_SESIONES:
            peticion = {"edad": caso["edad"], "duracion": caso["duracion"], "objetivo": caso["objetivo"]}
            status, datos, lat, error = _post(api, "/generar", peticion, TIMEOUT_SESION, cabeceras)
            registrar("sesion", caso, peticion, evaluar_sesion(caso, status, datos, lat), error)

    if solo in (None, "ejercicios"):
        print("Ejercicios (POST /ejercicio)")
        for caso in CASOS_EJERCICIOS:
            peticion = {"edad": caso["edad"], "objetivo": caso["objetivo"], "descripcion": caso["descripcion"]}
            status, datos, lat, error = _post(api, "/ejercicio", peticion, TIMEOUT_EJERCICIO, cabeceras)
            registrar("ejercicio", caso, peticion,
                      evaluar_ejercicio(caso, status, datos, lat, validador), error)

    if solo in (None, "reglamento"):
        print("Reglamento (POST /reglamento)")
        for caso in CASOS_REGLAMENTO:
            peticion = {"pregunta": caso["pregunta"]}
            if caso.get("ambito"):
                peticion["ambito"] = caso["ambito"]
            status, datos, lat, error = _post(api, "/reglamento", peticion, TIMEOUT_REGLAMENTO, cabeceras)
            registrar("reglamento", caso, peticion, evaluar_reglamento(caso, status, datos, lat), error)

    return resultados


# ─── Comparación con una ejecución anterior ──────────────────────────────────

def comparar(actual: list[dict], anterior: list[dict]) -> tuple[list[str], list[str]]:
    """Devuelve (empeoramientos, avisos). Empeoramiento: un criterio que antes pasaba
    y ahora falla, o una métrica de calidad que baja. Aviso: latencia notablemente peor
    o casos que no estaban en la ejecución anterior."""
    previos = {r["id"]: r for r in anterior}
    empeoramientos, avisos = [], []
    for r in actual:
        p = previos.get(r["id"])
        if p is None:
            avisos.append(f"{r['id']}: no está en la ejecución anterior")
            continue
        for nombre, c in r["criterios"].items():
            antes = p.get("criterios", {}).get(nombre, {}).get("ok")
            if antes is True and not c["ok"]:
                empeoramientos.append(f"{r['id']}: '{nombre}' pasaba y ahora falla ({c['detalle']})")

        m, mp = r["metricas"], p.get("metricas", {})
        if m.get("diagramas_no_disponibles", 0) > mp.get("diagramas_no_disponibles", 0):
            empeoramientos.append(
                f"{r['id']}: diagramas no disponibles {mp.get('diagramas_no_disponibles', 0)} → "
                f"{m['diagramas_no_disponibles']}")
        if "claves_encontradas" in m and m["claves_encontradas"] < mp.get("claves_encontradas", 0):
            empeoramientos.append(
                f"{r['id']}: palabras clave {mp['claves_encontradas']} → {m['claves_encontradas']}")

        lat, lat_p = m.get("latencia_s", 0), mp.get("latencia_s", 0)
        if lat_p and lat > lat_p * FACTOR_LATENCIA_AVISO and lat - lat_p > MARGEN_LATENCIA_AVISO:
            avisos.append(f"{r['id']}: latencia {lat_p:.1f} s → {lat:.1f} s")
    return empeoramientos, avisos


# ─── Salida ──────────────────────────────────────────────────────────────────

def imprimir_tabla(resultados: list[dict]) -> None:
    filas = []
    for r in resultados:
        m = r["metricas"]
        if r["tipo"] == "sesion":
            extra = (f"ej={m['ejercicios']} diag={m['diagramas_generados']}/{m['diagramas_esperados']}"
                     f" n/d={m['diagramas_no_disponibles']}")
        elif r["tipo"] == "ejercicio":
            extra = f"diag={m['diagramas_svg']}"
        else:
            extra = f"claves={m['claves_encontradas']}/{m['claves_total']}"
        fallos = ", ".join(n for n, c in r["criterios"].items() if not c["ok"]) or "-"
        filas.append((r["id"], r["tipo"], "OK" if r["aprobado"] else "FALLO",
                      f"{m['latencia_s']:.1f}", extra, fallos))

    cabecera = ("caso", "tipo", "estado", "lat (s)", "métricas", "criterios fallidos")
    anchos = [max(len(str(f[i])) for f in filas + [cabecera]) for i in range(len(cabecera))]
    linea = "  ".join("{:<%d}" % a for a in anchos)
    print()
    print(linea.format(*cabecera).rstrip())
    print("  ".join("-" * a for a in anchos))
    for f in filas:
        print(linea.format(*f).rstrip())
    aprobados = sum(1 for r in resultados if r["aprobado"])
    print(f"\n{aprobados}/{len(resultados)} casos aprobados")


def _salida_por_defecto() -> Path:
    return RAIZ / "data" / "regresion" / f"{datetime.datetime.now():%Y-%m-%d_%H%M}.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Test de regresión en vivo contra la API de MiPizarra")
    parser.add_argument("--api", default="http://localhost:8090", help="URL base de la API")
    parser.add_argument("--salida", type=Path, default=None,
                        help="Fichero JSON de resultados (por defecto data/regresion/AAAA-MM-DD_HHMM.json)")
    parser.add_argument("--comparar", type=Path, default=None, metavar="RUTA",
                        help="JSON de una ejecución anterior con el que comparar")
    parser.add_argument("--solo", choices=["sesiones", "ejercicios", "reglamento"], default=None)
    args = parser.parse_args(argv)

    anterior = None
    if args.comparar:
        try:
            with open(args.comparar, encoding="utf-8") as f:
                anterior = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            print(f"✗ No se pudo leer {args.comparar}: {e}")
            return 2

    try:
        version = requests.get(f"{args.api.rstrip('/')}/", timeout=10).json().get("version")
    except (requests.RequestException, ValueError):
        version = None

    validador = _cargar_validador() if args.solo in (None, "ejercicios") else None
    inicio = datetime.datetime.now()
    resultados = ejecutar(args.api, args.solo, validador)
    imprimir_tabla(resultados)

    empeoramientos, avisos = [], []
    if anterior is not None:
        empeoramientos, avisos = comparar(resultados, anterior.get("resultados", []))
        print(f"\nComparación con {args.comparar.name}:")
        for e in empeoramientos:
            print(f"  ✗ EMPEORA  {e}")
        for a in avisos:
            print(f"  ⚠ aviso    {a}")
        if not empeoramientos and not avisos:
            print("  sin cambios a peor")

    fallos_duros = [r["id"] for r in resultados if not r["aprobado"]]
    informe = {
        "fecha": inicio.isoformat(timespec="seconds"),
        "duracion_total_s": round((datetime.datetime.now() - inicio).total_seconds(), 1),
        "version_api": version,
        "solo": args.solo,
        "comparado_con": args.comparar.name if args.comparar else None,
        "resumen": {
            "casos": len(resultados),
            "aprobados": len(resultados) - len(fallos_duros),
            "fallidos": fallos_duros,
            "empeoramientos": empeoramientos,
            "avisos": avisos,
        },
        "resultados": resultados,
    }
    salida = args.salida or _salida_por_defecto()
    salida.parent.mkdir(parents=True, exist_ok=True)
    with open(salida, "w", encoding="utf-8") as f:
        json.dump(informe, f, ensure_ascii=False, indent=2)
    print(f"\nResultados guardados en {salida}")

    return 1 if fallos_duros or empeoramientos else 0


if __name__ == "__main__":
    sys.exit(main())
