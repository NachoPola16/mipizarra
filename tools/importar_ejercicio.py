#!/usr/bin/env python3
"""
Importa un ejercicio desde una descripción en lenguaje natural.
Uso: docker exec -it hoops-api python /app/importar_ejercicio.py "Descripción..."
"""
import json, sys, os, re, requests

OLLAMA_URL = "http://ollama:11434"
MODEL = "llama3.2:3b"
EXERCISES_PATH = "/app/data/exercises.json"

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

PROMPT_TEMPLATE = """Eres un entrenador de baloncesto que convierte descripciones de ejercicios en JSON estructurado.

Reglas:
- Si la descripción especifica posiciones de jugadores (cabecera, 45, codo, esquina, etc.), genera un campo "diagrama" con coordenadas normalizadas (x:0-100, y:0-100; y=0 es fondo).
- Si NO hay referencias posicionales claras (juegos de calentamiento, pillar, etc.), usa "diagrama": null.
- "edades": incluye la categoría mencionada (ej: "cadetes") y todas las inferiores según herencia federativa.
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

def generar_ejercicio(descripcion: str) -> dict:
    prompt = PROMPT_TEMPLATE.format(descripcion=descripcion)
    resp = requests.post(
        f"{OLLAMA_URL}/api/generate",
        json={"model": MODEL, "prompt": prompt, "stream": False, "options": {"temperature": 0.1, "num_predict": 1200}},
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

    # Generar ID automático
    try:
        with open(EXERCISES_PATH, "r", encoding="utf-8") as f:
            ejercicios = json.load(f)
        ultimo_id = max(int(e["id"].split("_")[1]) for e in ejercicios if e["id"].startswith("ej_"))
    except:
        ultimo_id = 0
    data["id"] = f"ej_{ultimo_id + 1:03d}"

    # La descripción original se mantiene
    data["descripcion"] = descripcion
    return data

def guardar_ejercicio(ejercicio: dict):
    try:
        with open(EXERCISES_PATH, "r", encoding="utf-8") as f:
            ejercicios = json.load(f)
    except FileNotFoundError:
        ejercicios = []
    ejercicios.append(ejercicio)
    with open(EXERCISES_PATH, "w", encoding="utf-8") as f:
        json.dump(ejercicios, f, indent=2, ensure_ascii=False)
    print(f"✅ Ejercicio '{ejercicio['nombre']}' añadido a {EXERCISES_PATH}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python importar_ejercicio.py \"Descripción del ejercicio...\"")
        sys.exit(1)
    desc = " ".join(sys.argv[1:])
    ejercicio = generar_ejercicio(desc)
    guardar_ejercicio(ejercicio)
