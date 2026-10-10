#!/usr/bin/env python3
"""Cuántos ejercicios de una sesión tendría que inventar la IA por falta de ficha en la biblioteca.

Para cada edad, duración y objetivo, pide al plan cuántos ejercicios lleva la parte principal y mira
cuántos huecos no se pueden cubrir con una ficha relevante de data/exercises.json (esos los propone
el modelo, marcados «Propuesto por la IA (sin revisar)»). Sirve para decidir qué ejercicios añadir a la
biblioteca y para comprobar el avance. No necesita Docker, ChromaDB ni Ollama.

Uso:
  python tools/huecos_biblioteca.py
  python tools/huecos_biblioteca.py --edades U8 U10 --duraciones 60 90
  python tools/huecos_biblioteca.py --objetivos bote pase tiro --solo-huecos
"""
import argparse
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
os.environ.setdefault("EXERCISES_PATH", str(RAIZ / "data" / "exercises.json"))
sys.path.insert(0, str(RAIZ / "api"))

from ejercicios import cargar_ejercicios, elegir_fichas  # noqa: E402
from plan_sesion import plan_de_tiempos  # noqa: E402

EDADES = ["U8", "U10", "U12", "U14", "U16", "U18"]
DURACIONES = [60, 90]
OBJETIVOS = ["bote", "pase", "tiro", "defensa", "1c1", "contraataque", "transición", "rebote"]


def huecos(edad: str, duracion: int, objetivo: str, biblioteca: list, estricto: bool = False) -> tuple[int, int]:
    """(huecos sin ficha, ejercicios de la parte principal) de una sesión. Con `estricto` solo cuentan
    las fichas que nombran el propio objetivo, no las de un fundamento asociado (pase para contraataque)."""
    n = len(plan_de_tiempos(duracion, edad).duraciones)
    fichas = elegir_fichas([dict(e) for e in biblioteca], edad, objetivo, n, solo_directas=estricto)
    return sum(f is None for f in fichas), n


def tabla(edades, duraciones, objetivos, solo_huecos=False, estricto=False) -> tuple[str, int, int]:
    biblioteca = cargar_ejercicios()
    lineas = [f"{'edad':<5}{'min':>4}{'n':>3} | " + "  ".join(f"{o[:9]:>9}" for o in objetivos)]
    total_huecos = total = 0
    for edad in edades:
        for duracion in duraciones:
            fila, n = [], 0
            for objetivo in objetivos:
                h, n = huecos(edad, duracion, objetivo, biblioteca, estricto)
                total_huecos += h
                total += n
                fila.append(f"{h}/{n}".rjust(9))
            if solo_huecos and all(c.strip().startswith("0/") for c in fila):
                continue
            lineas.append(f"{edad:<5}{duracion:>4}{n:>3} | " + "  ".join(fila))
    return "\n".join(lineas), total_huecos, total


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--edades", nargs="+", default=EDADES)
    ap.add_argument("--duraciones", nargs="+", type=int, default=DURACIONES)
    ap.add_argument("--objetivos", nargs="+", default=OBJETIVOS)
    ap.add_argument("--solo-huecos", action="store_true", help="oculta las filas sin ningún hueco")
    ap.add_argument("--estricto", action="store_true",
                    help="solo cuentan las fichas que nombran el objetivo (sin fundamentos asociados)")
    args = ap.parse_args(argv)
    texto, huecos_total, total = tabla(args.edades, args.duraciones, args.objetivos, args.solo_huecos, args.estricto)
    print("Huecos que propondría la IA / ejercicios de la parte principal\n")
    print(texto)
    pct = 100 * huecos_total / total if total else 0
    print(f"\nTotal: {huecos_total} de {total} ejercicios ({pct:.0f} %) los propondría la IA")
    return 0


if __name__ == "__main__":
    sys.exit(main())
