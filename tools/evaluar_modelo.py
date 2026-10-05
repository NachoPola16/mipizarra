#!/usr/bin/env python3
"""
Evalúa el modelo fine-tuneado contra el modelo base con métricas estructurales.

Métricas para SESIONES (texto):
  - presencia de las 4 secciones (CALENTAMIENTO, PARTE PRINCIPAL, VUELTA A LA CALMA, Fundamentos)
  - exactamente 3 ejercicios numerados
  - ejercicios con nombres distintos (no duplicados)
  - nombres de ejercicios presentes en data/exercises.json
  - longitud media (chars)
  - latencia media (s)

Métricas para DIAGRAMAS (JSON):
  - JSON válido
  - ≥ 2 jugadores_ataque
  - tiene movimientos

Uso (desde el contenedor mipizarra-api):
  python /app/tools/evaluar_modelo.py --base qwen3:4b --finetuned mipizarra
  python /app/tools/evaluar_modelo.py --base qwen3:4b --finetuned mipizarra --n 20
  python /app/tools/evaluar_modelo.py --base mipizarra --finetuned mipizarra-v2 --solo sesiones
"""
import argparse
import json
import random
import re
import time
from collections import defaultdict
from pathlib import Path
from typing import Callable

import requests

random.seed(123)  # seed distinta al de generar_dataset.py: no overlapping casos

EDADES     = ["U10", "U12", "U14", "U16", "U18", "Senior"]
EDAD_A_CAT = {"U8": "Prebenjamín", "U10": "Benjamín", "U12": "Alevín",
              "U14": "Infantil", "U16": "Cadete", "U18": "Junior", "Senior": "Senior"}
DURACIONES = [60, 75, 90]
OBJETIVOS  = ["defensa", "tiro", "pase", "bloqueo directo",
              "contraataque", "1 contra 1", "juego interior"]

EJERCICIOS_DIAG_TEST = [
    ("Pick and roll central", "Base con balón en cabecera. Pivot sube de poste bajo a hacer bloqueo directo. Base lee el bloqueo y continúa al codo."),
    ("Backdoor desde esquina", "Alero en esquina derecha hace amago hacia el poste y corta directo a canasta por baseline para recibir pase del base."),
    ("Tiro de codo tras pase", "A1 base en cabecera pasa a A2 que sale al codo TL derecho. A2 tira de media distancia."),
]


def cargar_nombres_ejercicios(path: Path) -> set[str]:
    if not path.exists():
        return set()
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {ej["nombre"].strip() for ej in data if "nombre" in ej}


def llamar_ollama(ollama_url: str, model: str, prompt: str,
                  num_predict: int = 1800, temperature: float = 0.4,
                  num_ctx: int = 6144) -> tuple[str, float]:
    t0 = time.time()
    try:
        r = requests.post(
            f"{ollama_url}/api/generate",
            json={
                "model":  model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": num_predict,
                    "num_ctx":     num_ctx,
                    "top_p":       0.9,
                    "min_p":       0.05,
                },
            },
            timeout=600,
        )
        r.raise_for_status()
        return r.json().get("response", "").strip(), time.time() - t0
    except Exception as e:
        return f"[ERROR] {e}", time.time() - t0


# ─── Métricas SESIÓN ────────────────────────────────────────────────────────
def evaluar_sesion(texto: str, nombres_validos: set[str]) -> dict:
    txt_low = texto.lower()
    secciones_ok = all(
        s in txt_low for s in ("calentamiento", "parte principal", "vuelta a la calma", "fundamentos")
    )

    ejercicios = re.findall(r"ejercicio\s*\d+\s*:\s*([^\n]+)", texto, flags=re.IGNORECASE)
    nombres = [e.strip().strip('"').strip("'").rstrip(".") for e in ejercicios]
    n_ejs = len(nombres)
    sin_duplicados = n_ejs == len(set(n.lower() for n in nombres))

    if nombres_validos and nombres:
        en_lista = sum(1 for n in nombres if n in nombres_validos)
        pct_en_lista = en_lista / len(nombres)
    else:
        pct_en_lista = None

    return {
        "secciones_ok":   secciones_ok,
        "n_ejs":          n_ejs,
        "exactos_3_ejs":  n_ejs == 3,
        "sin_duplicados": sin_duplicados,
        "pct_en_lista":   pct_en_lista,
        "chars":          len(texto),
        "es_error":       texto.startswith("[ERROR]"),
    }


# ─── Métricas DIAGRAMA ──────────────────────────────────────────────────────
def evaluar_diagrama(texto: str) -> dict:
    if texto.startswith("[ERROR]"):
        return {"json_valido": False, "atacantes_ok": False, "movimientos_ok": False, "es_error": True}

    # Limpiar markdown
    t = texto.replace("```json", "").replace("```", "").strip()
    # Quedarse con el primer bloque {...}
    m = re.search(r"\{[\s\S]*\}", t)
    if not m:
        return {"json_valido": False, "atacantes_ok": False, "movimientos_ok": False, "es_error": False}

    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return {"json_valido": False, "atacantes_ok": False, "movimientos_ok": False, "es_error": False}

    return {
        "json_valido":    True,
        "atacantes_ok":   len(data.get("jugadores_ataque", []) or []) >= 2,
        "movimientos_ok": len(data.get("movimientos", []) or []) >= 1,
        "es_error":       False,
    }


# ─── Runners ────────────────────────────────────────────────────────────────
SYSTEM_SESION = (
    "Eres MiPizarra, un asistente experto en entrenamiento de baloncesto. "
    "Diseñas sesiones de entrenamiento estructuradas y prácticas. "
    "Usas terminología técnica española (codo TL, cabecera, baseline, poste alto/bajo). "
    "Siempre propones ejercicios concretos con posiciones claras."
)


def prompt_sesion(edad: str, duracion: int, objetivo: str) -> str:
    cat = EDAD_A_CAT.get(edad, edad)
    return f"""{SYSTEM_SESION}

Genera una sesión de entrenamiento de baloncesto.

Categoría: {cat} ({edad})
Duración: {duracion} min
Objetivo: {objetivo}

ESTRUCTURA:
**CALENTAMIENTO (15 min)**
**PARTE PRINCIPAL**
Ejercicio 1: ...
Ejercicio 2: ...
Ejercicio 3: ...
**VUELTA A LA CALMA (8 min)**
**Fundamentos**

Responde solo el texto de la sesión."""


def prompt_diagrama(nombre: str, desc: str) -> str:
    return f"""Genera las coordenadas JSON del diagrama para este ejercicio de baloncesto.

Ejercicio: {nombre}
Descripción: {desc}

Coordenadas (0-100): X=0 izq, X=100 dcha; Y=0 baseline, Y=41 TL, Y=60 triple, Y=100 medio campo.
Devuelve SOLO el JSON con: jugadores_ataque, jugadores_defensa, balon_inicio, movimientos."""


def correr_tarea(modelo: str, ollama_url: str, casos: list, prompt_fn: Callable,
                 evaluar_fn: Callable, evaluar_kwargs: dict, label: str) -> list[dict]:
    print(f"\n── {label} con {modelo} ({len(casos)} casos) ──")
    resultados = []
    for i, caso in enumerate(casos, 1):
        prompt = prompt_fn(*caso)
        texto, lat = llamar_ollama(ollama_url, modelo, prompt)
        m = evaluar_fn(texto, **evaluar_kwargs)
        m["latencia"] = lat
        resultados.append(m)
        marca = "✓" if not m.get("es_error") else "✗"
        print(f"  [{i}/{len(casos)}] {marca} {lat:.1f}s")
    return resultados


# ─── Agregación y tabla ─────────────────────────────────────────────────────
def agregar_sesion(res: list[dict]) -> dict:
    n_ok = [r for r in res if not r["es_error"]]
    if not n_ok:
        return {"n_validos": 0}
    out = {
        "n_validos":         len(n_ok),
        "errores":           len(res) - len(n_ok),
        "%_secciones_ok":    100 * sum(r["secciones_ok"] for r in n_ok) / len(n_ok),
        "%_3_ejercicios":    100 * sum(r["exactos_3_ejs"] for r in n_ok) / len(n_ok),
        "%_sin_duplicados":  100 * sum(r["sin_duplicados"] for r in n_ok) / len(n_ok),
        "chars_media":       sum(r["chars"] for r in n_ok) / len(n_ok),
        "latencia_media_s":  sum(r["latencia"] for r in n_ok) / len(n_ok),
    }
    con_lista = [r["pct_en_lista"] for r in n_ok if r["pct_en_lista"] is not None]
    if con_lista:
        out["%_nombres_en_lista"] = 100 * sum(con_lista) / len(con_lista)
    return out


def agregar_diagrama(res: list[dict]) -> dict:
    n_ok = [r for r in res if not r["es_error"]]
    if not n_ok:
        return {"n_validos": 0}
    return {
        "n_validos":         len(n_ok),
        "errores":           len(res) - len(n_ok),
        "%_json_valido":     100 * sum(r["json_valido"] for r in n_ok) / len(n_ok),
        "%_atacantes_ok":    100 * sum(r["atacantes_ok"] for r in n_ok) / len(n_ok),
        "%_movimientos_ok": 100 * sum(r["movimientos_ok"] for r in n_ok) / len(n_ok),
        "latencia_media_s":  sum(r["latencia"] for r in n_ok) / len(n_ok),
    }


def imprimir_comparativa(titulo: str, base: dict, ft: dict):
    print(f"\n{'='*60}")
    print(f"  {titulo}")
    print('='*60)
    claves = sorted(set(base) | set(ft))
    print(f"  {'Métrica':<22}  {'base':>10}  {'fine-tuned':>12}  {'Δ':>8}")
    print(f"  {'-'*22}  {'-'*10}  {'-'*12}  {'-'*8}")
    for k in claves:
        b = base.get(k)
        f = ft.get(k)
        if isinstance(b, (int, float)) and isinstance(f, (int, float)):
            delta = f - b
            flecha = "↑" if delta > 0.5 else ("↓" if delta < -0.5 else "·")
            print(f"  {k:<22}  {b:>10.2f}  {f:>12.2f}  {delta:>+7.2f}{flecha}")
        else:
            print(f"  {k:<22}  {str(b):>10}  {str(f):>12}")


def main():
    ap = argparse.ArgumentParser(description="Evalúa modelo base vs fine-tuned")
    ap.add_argument("--base",       required=True, help="Nombre del modelo base en Ollama")
    ap.add_argument("--finetuned",  required=True, help="Nombre del modelo fine-tuned en Ollama")
    ap.add_argument("--ollama",     default="http://ollama:11434")
    ap.add_argument("--n",          type=int, default=10, help="Nº de sesiones a generar por modelo")
    ap.add_argument("--ejercicios", default="/app/data/exercises.json",
                    help="Ruta a exercises.json para validar nombres")
    ap.add_argument("--solo",       choices=["sesiones", "diagramas", "todo"], default="todo")
    ap.add_argument("--salida",     default="data/eval_resultados.json",
                    help="Donde guardar los resultados detallados")
    args = ap.parse_args()

    nombres_validos = cargar_nombres_ejercicios(Path(args.ejercicios))
    if not nombres_validos:
        print(f"⚠ No se cargaron nombres desde {args.ejercicios} — métrica %_nombres_en_lista deshabilitada")

    casos_sesion   = [(random.choice(EDADES), random.choice(DURACIONES), random.choice(OBJETIVOS))
                      for _ in range(args.n)]
    casos_diagrama = [random.choice(EJERCICIOS_DIAG_TEST) for _ in range(max(3, args.n // 2))]

    resultados = {}

    if args.solo in ("sesiones", "todo"):
        res_base = correr_tarea(args.base, args.ollama, casos_sesion, prompt_sesion,
                                evaluar_sesion, {"nombres_validos": nombres_validos}, "SESIONES")
        res_ft   = correr_tarea(args.finetuned, args.ollama, casos_sesion, prompt_sesion,
                                evaluar_sesion, {"nombres_validos": nombres_validos}, "SESIONES")
        agg_b, agg_f = agregar_sesion(res_base), agregar_sesion(res_ft)
        imprimir_comparativa("SESIONES", agg_b, agg_f)
        resultados["sesiones"] = {"base": agg_b, "finetuned": agg_f,
                                   "detalle_base": res_base, "detalle_ft": res_ft}

    if args.solo in ("diagramas", "todo"):
        res_base = correr_tarea(args.base, args.ollama, casos_diagrama, prompt_diagrama,
                                evaluar_diagrama, {}, "DIAGRAMAS")
        res_ft   = correr_tarea(args.finetuned, args.ollama, casos_diagrama, prompt_diagrama,
                                evaluar_diagrama, {}, "DIAGRAMAS")
        agg_b, agg_f = agregar_diagrama(res_base), agregar_diagrama(res_ft)
        imprimir_comparativa("DIAGRAMAS", agg_b, agg_f)
        resultados["diagramas"] = {"base": agg_b, "finetuned": agg_f,
                                    "detalle_base": res_base, "detalle_ft": res_ft}

    salida = Path(args.salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    with open(salida, "w", encoding="utf-8") as f:
        json.dump({"base": args.base, "finetuned": args.finetuned, "n": args.n,
                   "resultados": resultados}, f, ensure_ascii=False, indent=2)
    print(f"\n📄 Resultados detallados: {salida}")

    # Veredicto
    print(f"\n{'='*60}")
    print("  VEREDICTO")
    print('='*60)
    if "sesiones" in resultados:
        b, f = resultados["sesiones"]["base"], resultados["sesiones"]["finetuned"]
        mejoras = sum(1 for k in ("%_secciones_ok", "%_3_ejercicios", "%_sin_duplicados",
                                   "%_nombres_en_lista")
                      if isinstance(b.get(k), (int, float)) and isinstance(f.get(k), (int, float))
                      and f[k] > b[k] + 5)
        print(f"  Sesiones — mejoras claras (>5 pp) en {mejoras}/4 métricas críticas")
        if mejoras >= 2:
            print("  → ✅ El fine-tuned merece la pena.")
        else:
            print("  → ⚠ El fine-tuned NO mejora claramente. Revisa el dataset.")


if __name__ == "__main__":
    main()
