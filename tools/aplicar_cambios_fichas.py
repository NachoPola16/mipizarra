#!/usr/bin/env python3
"""Vuelca a data/exercises.json (git) los cambios que el administrador hizo a las fichas desde la pestaña «Fichas».

Los cambios viven en el servidor (data/cambios/ficha_cambios.json). Para subirlos a git: copia ese fichero a tu equipo,
ejecuta este script, revisa `git diff` y haz commit. Con `--vaciar` borra el fichero de cambios al terminar (ya están en
exercises.json). El id y el diagrama no cambian nunca. Solo biblioteca estándar.

Uso:
  python tools/aplicar_cambios_fichas.py --cambios ficha_cambios.json
  python tools/aplicar_cambios_fichas.py --cambios ficha_cambios.json --vaciar
"""
import argparse
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "api"))
from ficha_cambios import aplicar  # noqa: E402


def volcar(ejercicios: Path, cambios: dict) -> int:
    base = json.loads(ejercicios.read_text(encoding="utf-8"))
    nuevas = aplicar(base, cambios)
    cambiadas = sum(1 for a, b in zip(base, nuevas) if a != b)
    ejercicios.write_text(json.dumps(nuevas, ensure_ascii=False, indent=2), encoding="utf-8")
    return cambiadas


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--cambios", type=Path, required=True, help="ficha_cambios.json copiado del servidor")
    ap.add_argument("--ejercicios", type=Path, default=RAIZ / "data" / "exercises.json")
    ap.add_argument("--vaciar", action="store_true", help="borra el fichero de cambios al terminar")
    a = ap.parse_args()
    cambios = json.loads(a.cambios.read_text(encoding="utf-8"))
    n = volcar(a.ejercicios, cambios)
    print(f"{n} fichas actualizadas en {a.ejercicios}")
    if a.vaciar:
        a.cambios.unlink()
    return 0


if __name__ == "__main__":
    sys.exit(main())
