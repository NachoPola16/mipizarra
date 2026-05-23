#!/usr/bin/env python3
"""
Script para convertir descripciones tácticas de baloncesto (usando jerga de entrenador)
en el bloque 'diagrama' JSON con coordenadas normalizadas.
"""
import json
import sys
import requests

OLLAMA_URL = "http://<SERVER_IP>:11434"
MODEL = "llama3.2:3b"

# ─── TRADUCCIÓN DE TÉRMINOS A COORDENADAS APROXIMADAS (x, y) ─────────────────
# Sistema: x=0 (izquierda), x=100 (derecha); y=0 (fondo/canasta), y=100 (medio campo)

REFERENCIA_POSICIONES = """
REFERENCIA DE COORDENADAS PARA TÉRMINOS TÁCTICOS:
- "Cabecera" o "Tope del arco": (50, 60-70)
- "45 grados" o "Ala izquierda": (25, 55-65)
- "45 grados" o "Ala derecha": (75, 55-65)
- "Codo izquierdo": (33, 40-45)
- "Codo derecho": (67, 40-45)
- "Esquina izquierda": (5, 15-25)
- "Esquina derecha": (95, 15-25)
- "Taco izquierdo" (marca lateral de la zona): (20, 30-35)
- "Taco derecho": (80, 30-35)
- "Debajo de canasta" o "Aro": (50, 5-10)
- "Poste alto izquierdo": (35, 50)
- "Poste alto derecho": (65, 50)
- "Poste bajo izquierdo": (35, 20)
- "Poste bajo derecho": (65, 20)

ACCIONES:
- "Cortar a canasta": desplazamiento desde posición actual hacia (50, 10)
- "Bloquear": posición del bloqueador y línea de bloqueo (línea gruesa)
- "Aclarado": los jugadores se abren a las esquinas o alas.
"""

def construir_prompt(descripcion: str) -> str:
    return f"""Eres un experto en baloncesto que conoce la jerga táctica de los entrenadores españoles.
Tu tarea es convertir una descripción textual de una jugada en un diagrama JSON válido.

{REFERENCIA_POSICIONES}

INSTRUCCIONES:
1. Analiza la descripción y asigna coordenadas (x,y) a cada jugador mencionado (A1, A2, D1, D2, etc.) según la referencia de arriba.
2. Los movimientos deben ordenarse lógicamente (orden: 1, 2, 3...).
3. El campo "balon_inicio" debe indicar quién tiene el balón al principio (normalmente "A1").
4. Usa "desplazamiento" para cortes o movimientos sin balón; "pase" para pasar el balón; "tiro" para lanzamiento; "bloqueo" para pantallas.
5. Si la descripción es vaga, elige coordenadas razonables dentro de los rangos indicados.

DESCRIPCIÓN DEL ENTRENADOR:
"{descripcion}"

Genera EXCLUSIVAMENTE el JSON, sin markdown ni explicaciones. El formato debe ser exactamente:
{{
  "tipo": "media_pista",
  "jugadores_ataque": [ {{"id": "A1", "rol": "...", "x": 50, "y": 60}}, ... ],
  "jugadores_defensa": [ {{"id": "D1", "rol": "...", "x": 50, "y": 45}}, ... ],
  "balon_inicio": {{"portador": "A1"}},
  "movimientos": [
    {{"de": "A2", "a_pos": {{"x": 45, "y": 55}}, "tipo": "bloqueo", "orden": 1}},
    {{"de": "A1", "a_pos": {{"x": 30, "y": 40}}, "tipo": "desplazamiento", "orden": 2}},
    {{"de": "A1", "tipo": "tiro", "orden": 3}}
  ],
  "conos": []
}}

JSON:"""

def descripcion_a_diagrama(descripcion: str) -> dict:
    prompt = construir_prompt(descripcion)
    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": 900}
            },
            timeout=90
        )
        resp.raise_for_status()
        texto = resp.json()["response"]
    except Exception as e:
        print(f"Error llamando a Ollama: {e}", file=sys.stderr)
        return {}

    # Limpiar posible markdown
    if "```json" in texto:
        texto = texto.split("```json")[1].split("```")[0]
    elif "```" in texto:
        texto = texto.split("```")[1].split("```")[0]

    try:
        return json.loads(texto)
    except json.JSONDecodeError as e:
        print(f"JSON inválido generado: {e}\nTexto recibido:\n{texto}", file=sys.stderr)
        return {}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python generar_coordenadas.py \"Descripción del ejercicio...\"")
        print("Ejemplo: python generar_coordenadas.py \"Base en cabecera, alero en 45 izquierdo. Bloqueo codo y corte a canasta.\"")
        sys.exit(1)

    desc = " ".join(sys.argv[1:])
    diagrama = descripcion_a_diagrama(desc)
    if diagrama:
        print(json.dumps(diagrama, indent=2, ensure_ascii=False))
    else:
        print("No se pudo generar el diagrama.", file=sys.stderr)
        sys.exit(1)
