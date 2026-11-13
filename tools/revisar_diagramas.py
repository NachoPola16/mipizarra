#!/usr/bin/env python3
"""Mechanical review of the diagrams of every card in the library (no model involved).

The checks live in api/revision_mecanica.py (the Fichas editor shows the same warnings live): the card validator plus
BALL, LABEL, DEF, RANGE, ORDER and CONES (see that module).

Usage (with the .venv Python):
  python tools/revisar_diagramas.py            # report on every card
  python tools/revisar_diagramas.py ej_237 ... # only these cards
"""
import json
import os
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
RAIZ = Path(__file__).resolve().parent.parent
RUTA = RAIZ / "data" / "exercises.json"
os.environ.setdefault("EXERCISES_PATH", str(RUTA))
sys.path.insert(0, str(RAIZ / "api"))

from revision_mecanica import revisar  # noqa: E402


def main(ids: list[str]) -> int:
    biblioteca = json.loads(RUTA.read_text(encoding="utf-8"))
    cuenta = Counter()
    fichas_con_problema = 0
    for f in biblioteca:
        if ids and f["id"] not in ids:
            continue
        problemas = revisar(f, biblioteca)
        if problemas:
            fichas_con_problema += 1
            print(f"{f['id']}  {f['nombre'][:70]}")
            for tipo, texto in problemas:
                cuenta[tipo] += 1
                print(f"    {tipo:9} {texto}")
    total = sum(1 for f in biblioteca if not ids or f["id"] in ids)
    print(f"\n{fichas_con_problema} fichas con avisos de {total}. Por tipo: {dict(cuenta)}")
    return 1 if fichas_con_problema else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
