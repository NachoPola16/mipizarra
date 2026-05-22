#!/usr/bin/env python3
"""
Corrige ejercicios cuyo campo 'diagrama' no sigue el formato esperado,
reemplazándolo por null.
"""
import json
import sys
import shutil
from datetime import datetime

EXERCISES_PATH = "/app/data/exercises.json"

def es_diagrama_valido(diagrama):
    """Comprueba si el diagrama tiene la estructura mínima esperada."""
    if diagrama is None:
        return True   # null es válido
    if not isinstance(diagrama, dict):
        return False
    # Debe contener al menos 'jugadores_ataque' o 'movimientos' (según tu diseño)
    return "jugadores_ataque" in diagrama or "movimientos" in diagrama

def main():
    # Crear copia de seguridad
    backup = f"{EXERCISES_PATH}.backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    shutil.copy(EXERCISES_PATH, backup)
    print(f"📦 Copia de seguridad guardada en {backup}")

    with open(EXERCISES_PATH, "r", encoding="utf-8") as f:
        ejercicios = json.load(f)

    corregidos = 0
    for ej in ejercicios:
        if not es_diagrama_valido(ej.get("diagrama")):
            ej["diagrama"] = None
            corregidos += 1
            print(f"🔧 Corregido: {ej.get('id')} - {ej.get('nombre')}")

    with open(EXERCISES_PATH, "w", encoding="utf-8") as f:
        json.dump(ejercicios, f, indent=2, ensure_ascii=False)

    print(f"\n✅ {corregidos} ejercicios corregidos (diagrama -> null).")
    print(f"📁 Archivo actualizado: {EXERCISES_PATH}")

if __name__ == "__main__":
    main()
