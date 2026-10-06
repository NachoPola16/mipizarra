#!/usr/bin/env python3
"""Informe del filtro automático para un lote de fichas candidatas (JSON), contrastado con la biblioteca.

Rechaza solo lo que incumple reglas objetivas (esquema, edades, líneas rojas, terminología, diagrama válido, ids y
nombres repetidos); no juzga si el ejercicio es bueno. Es la primera barrera antes de que nadie lea un candidato.

Uso:
  python tools/validar_candidatos.py data/candidatos/lote_01.json
  python tools/validar_candidatos.py lote.json --solo-errores
Código de salida: 0 si todas pasan, 1 si alguna tiene problemas, 2 si el fichero no es un JSON válido.
"""
import argparse
import json
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
os.environ.setdefault("EXERCISES_PATH", str(RAIZ / "data" / "exercises.json"))
sys.path.insert(0, str(RAIZ / "api"))

from validacion_fichas import validar_ficha  # noqa: E402


def _cargar(ruta: str):
    with open(ruta, encoding="utf-8") as f:
        datos = json.load(f)
    return datos if isinstance(datos, list) else [datos]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("lote", help="fichero JSON con una ficha o una lista de fichas")
    ap.add_argument("--biblioteca", default=str(RAIZ / "data" / "exercises.json"))
    ap.add_argument("--solo-errores", action="store_true", help="oculta las fichas que pasan el filtro")
    args = ap.parse_args(argv)

    try:
        candidatas = _cargar(args.lote)
    except (OSError, ValueError) as e:
        print(f"No se puede leer {args.lote} como JSON: {e}")
        return 2
    biblioteca = _cargar(args.biblioteca)

    con_problemas = 0
    for i, ficha in enumerate(candidatas):
        # se contrasta con la biblioteca y con las demás del lote
        otras = biblioteca + [c for j, c in enumerate(candidatas) if j != i and isinstance(c, dict)]
        problemas = validar_ficha(ficha, otras)
        etiqueta = f"{ficha.get('id', '?')} {str(ficha.get('nombre', ''))[:50]}" if isinstance(ficha, dict) else f"#{i + 1}"
        if problemas:
            con_problemas += 1
            print(f"✗ {etiqueta}")
            for p in problemas:
                print(f"    - {p}")
        elif not args.solo_errores:
            print(f"✓ {etiqueta}")
    pasan = len(candidatas) - con_problemas
    print(f"\n{pasan} de {len(candidatas)} candidatas pasan el filtro automático.")
    return 1 if con_problemas else 0


if __name__ == "__main__":
    sys.exit(main())
