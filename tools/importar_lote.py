#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Importa ejercicios desde un archivo de texto (una línea por ejercicio)
y los añade a exercises.json utilizando Ollama para generar el JSON.
"""
import json
import sys
import time
import requests
import os

# ─── Configuración ─────────────────────────────────────────────────
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://ollama:11434")
MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:3b")
EXERCISES_PATH = "/app/data/exercises.json"
SLEEP_BETWEEN = 3   # segundos entre ejercicios (ajústalo si quieres)

# Prompt para generar el JSON del ejercicio (igual que en importar_ejercicio.py)
PROMPT_TEMPLATE = """Eres un entrenador de baloncesto que convierte descripciones de ejercicios en JSON estructurado.

Reglas:
- Si la descripción especifica posiciones de jugadores (cabecera, 45, codo, esquina, etc.), genera un campo "diagrama" con coordenadas normalizadas (x:0-100, y:0-100; y=0 es fondo).
- Si NO hay referencias posicionales claras (juegos de calentamiento, pillar, etc.), usa "diagrama": null.
- "edades": incluye la categoría mencionada (ej: "cadetes") y todas las inferiores según herencia federativa (Prebenjamín, Benjamín, Alevín, Infantil, Cadete, Junior, Senior).
- "categoria" principal: "calentamiento" para juegos de activación; "bloqueo_directo", "tiro", "defensa", etc. según el objetivo.
- "duracion_min", "intensidad" (1-5), "carga_cognitiva" (1-5) se infieren o se dejan en valores por defecto razonables.
- "objetivos" se rellenan con arrays de strings (tácticos, técnicos, físicos).
- Los movimientos en "diagrama" deben incluir un campo "orden" (1,2,3...) para dibujar el número en la flecha.

Descripción:
"{descripcion}"

Devuelve EXCLUSIVAMENTE el JSON, sin explicaciones. Formato:
{{
  "id": "ej_XXX",
  "nombre": "...",
  "categoria": "...",
  "subcategoria": "...",
  "edades": [...],
  "duracion_min": 10,
  "intensidad": 3,
  "carga_cognitiva": 2,
  "objetivos": {{ "tacticos": [...], "tecnicos": [...], "fisicos": [...] }},
  "descripcion": "{descripcion}",
  "diagrama": null  // o el objeto completo si hay posiciones
}}

JSON:"""

CATEGORIAS = ["Prebenjamín", "Benjamín", "Alevín", "Infantil", "Cadete", "Junior", "Senior"]
HERENCIA = {
    "Prebenjamín": ["Prebenjamín"],
    "Benjamín": ["Prebenjamín", "Benjamín"],
    "Alevín": ["Prebenjamín", "Benjamín", "Alevín"],
    "Infantil": ["Prebenjamín", "Benjamín", "Alevín", "Infantil"],
    "Cadete": ["Prebenjamín", "Benjamín", "Alevín", "Infantil", "Cadete"],
    "Junior": ["Prebenjamín", "Benjamín", "Alevín", "Infantil", "Cadete", "Junior"],
    "Senior": CATEGORIAS,
}

def limpiar_linea(linea: str) -> str:
    """Elimina viñetas y espacios extra."""
    linea = linea.strip()
    if linea.startswith('o ') or linea.startswith('- '):
        linea = linea[2:].strip()
    return linea

def generar_ejercicio(descripcion: str) -> dict:
    prompt = PROMPT_TEMPLATE.format(descripcion=descripcion)
    resp = requests.post(
        f"{OLLAMA_URL}/api/generate",
        json={"model": MODEL, "prompt": prompt, "stream": False,
              "options": {"temperature": 0.1, "num_predict": 1200}},
        timeout=120
    )
    resp.raise_for_status()
    texto = resp.json()["response"]

    # Limpiar markdown
    if "```json" in texto:
        texto = texto.split("```json")[1].split("```")[0]
    elif "```" in texto:
        texto = texto.split("```")[1].split("```")[0]

    data = json.loads(texto)

    # Aplicar herencia de categorías
    if "edades" not in data or not data["edades"]:
        desc_lower = descripcion.lower()
        cat_principal = "Alevín"  # default
        for cat in CATEGORIAS:
            if cat.lower() in desc_lower:
                cat_principal = cat
                break
        data["edades"] = HERENCIA.get(cat_principal, ["Alevín", "Infantil", "Cadete", "Junior", "Senior"])

    # La descripción original se mantiene
    data["descripcion"] = descripcion
    return data

def cargar_ejercicios():
    try:
        with open(EXERCISES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def guardar_ejercicios(ejercicios):
    with open(EXERCISES_PATH, "w", encoding="utf-8") as f:
        json.dump(ejercicios, f, indent=2, ensure_ascii=False)

def obtener_ultimo_id(ejercicios):
    if not ejercicios:
        return 0
    ids = [int(e["id"].split("_")[1]) for e in ejercicios if e.get("id", "").startswith("ej_")]
    return max(ids) if ids else 0

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python importar_lote.py archivo.txt")
        sys.exit(1)

    archivo = sys.argv[1]
    try:
        with open(archivo, "r", encoding="utf-8") as f:
            lineas = f.readlines()
    except FileNotFoundError:
        print(f"Error: No se encuentra el archivo '{archivo}'")
        sys.exit(1)

    ejercicios_actuales = cargar_ejercicios()
    ultimo_id = obtener_ultimo_id(ejercicios_actuales)
    total_lineas = len(lineas)
    exitos = 0
    fallos = 0

    print(f"📋 Procesando {total_lineas} ejercicios...")
    print(f"📌 Último ID existente: ej_{ultimo_id:03d}\n")

    for i, linea in enumerate(lineas, 1):
        desc = limpiar_linea(linea)
        if len(desc) < 10:
            print(f"⏭️  Línea {i} demasiado corta, se omite.")
            continue

        print(f"🔄 [{i}/{total_lineas}] Procesando: {desc[:60]}...")
        try:
            ejercicio = generar_ejercicio(desc)
            # Asignar ID secuencial
            ultimo_id += 1
            ejercicio["id"] = f"ej_{ultimo_id:03d}"
            # Añadir a la lista y guardar incrementalmente
            ejercicios_actuales.append(ejercicio)
            guardar_ejercicios(ejercicios_actuales)
            print(f"   ✅ Añadido: {ejercicio['nombre']} (ID: {ejercicio['id']})")
            exitos += 1
        except Exception as e:
            print(f"   ❌ Error: {e}")
            fallos += 1

        time.sleep(SLEEP_BETWEEN)

    print("\n" + "="*50)
    print(f"🏁 IMPORTACIÓN FINALIZADA")
    print(f"   ✅ Ejercicios añadidos: {exitos}")
    print(f"   ❌ Errores: {fallos}")
    print(f"   📦 Total ejercicios en la base de datos: {len(ejercicios_actuales)}")
    print("="*50)
