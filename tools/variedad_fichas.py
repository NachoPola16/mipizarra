#!/usr/bin/env python3
"""Cuánta variedad hay en las fichas que elige el sistema para los mismos parámetros.

Para cada edad, duración y objetivo repite la elección de fichas de la parte principal y cuenta
cuántas sesiones distintas salen, y cuántos huecos sin ficha deja (que no deben subir respecto a
la elección determinista). No necesita Docker, ChromaDB ni Ollama.

Uso:
  python tools/variedad_fichas.py
  python tools/variedad_fichas.py --edades U8 U10 --objetivos bote pase --repeticiones 6
  python tools/variedad_fichas.py --determinista     # el «antes»: sin azar
"""
import argparse
import os
import random
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


def medir(edad, duracion, objetivo, biblioteca, repeticiones, determinista, semilla=0):
    """(sesiones distintas, huecos máximos, huecos de la elección determinista, n)."""
    n = len(plan_de_tiempos(duracion, edad).duraciones)
    base = elegir_fichas([dict(e) for e in biblioteca], edad, objetivo, n)
    huecos_base = sum(f is None for f in base)
    azar = random.Random(f"{semilla}-{edad}-{duracion}-{objetivo}")
    vistas, huecos_max = set(), 0
    for _ in range(repeticiones):
        kwargs = {} if determinista else {"azar": azar}
        fichas = elegir_fichas([dict(e) for e in biblioteca], edad, objetivo, n, **kwargs)
        vistas.add(tuple(f["id"] if f else None for f in fichas))
        huecos_max = max(huecos_max, sum(f is None for f in fichas))
    return len(vistas), huecos_max, huecos_base, n


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--edades", nargs="+", default=EDADES)
    ap.add_argument("--duraciones", nargs="+", type=int, default=DURACIONES)
    ap.add_argument("--objetivos", nargs="+", default=OBJETIVOS)
    ap.add_argument("--repeticiones", type=int, default=6)
    ap.add_argument("--determinista", action="store_true", help="sin azar (el comportamiento anterior)")
    args = ap.parse_args(argv)

    biblioteca = cargar_ejercicios()
    print(f"Sesiones distintas / {args.repeticiones} repeticiones"
          f"{' (determinista)' if args.determinista else ''}\n")
    print(f"{'edad':<5}{'min':>4}{'n':>3} | " + "  ".join(f"{o[:9]:>9}" for o in args.objetivos))
    total = distintas = con_variedad = peor_hueco = 0
    for edad in args.edades:
        for duracion in args.duraciones:
            fila, n = [], 0
            for objetivo in args.objetivos:
                d, h_max, h_base, n = medir(edad, duracion, objetivo, biblioteca,
                                            args.repeticiones, args.determinista)
                total += 1
                distintas += d
                con_variedad += d > 1
                peor_hueco = max(peor_hueco, h_max - h_base)
                fila.append(f"{d}{'!' if h_max > h_base else ''}".rjust(9))
            print(f"{edad:<5}{duracion:>4}{n:>3} | " + "  ".join(fila))
    print(f"\n{con_variedad} de {total} combinaciones dan más de una sesión; "
          f"media {distintas / total:.2f} sesiones distintas.")
    print("«!» marca una combinación donde el azar deja más huecos que la elección determinista."
          if peor_hueco > 0 else "Ninguna combinación deja más huecos que la elección determinista.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
