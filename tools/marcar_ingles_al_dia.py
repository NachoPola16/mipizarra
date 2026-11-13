#!/usr/bin/env python3
"""Stamp `i18n.en.es_hash` (a fingerprint of the Spanish text) on cards whose English is known to be up to date.

The Fichas editor uses that stamp to flag cards whose Spanish changed after the English was last reviewed
("inglés desfasado"). Cards without a stamp are never flagged (nothing is known about them).

Usage (with the .venv Python):
  python tools/marcar_ingles_al_dia.py            # report only: how many cards have / lack the stamp, and the stale ones
  python tools/marcar_ingles_al_dia.py --aplicar  # stamp every card that has English and no stamp yet (idempotent)
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
RAIZ = Path(__file__).resolve().parent.parent
RUTA = RAIZ / "data" / "exercises.json"
sys.path.insert(0, str(RAIZ / "api"))

from i18n_fichas import CLAVE_SINCRONIA, hash_es, ingles_desfasado  # noqa: E402


def main(aplicar: bool) -> int:
    fichas = json.loads(RUTA.read_text(encoding="utf-8"))
    con_ingles = [f for f in fichas if isinstance((f.get("i18n") or {}).get("en"), dict)]
    sin_marca = [f for f in con_ingles if not f["i18n"]["en"].get(CLAVE_SINCRONIA)]
    desfasadas = [f["id"] for f in con_ingles if ingles_desfasado(f)]
    print(f"{len(fichas)} fichas, {len(con_ingles)} con inglés, {len(sin_marca)} sin marca, {len(desfasadas)} desfasadas {desfasadas}")
    if not aplicar:
        return 0
    for f in sin_marca:
        f["i18n"]["en"][CLAVE_SINCRONIA] = hash_es(f)
    if sin_marca:
        with open(RUTA, "w", encoding="utf-8", newline="\n") as salida:
            json.dump(fichas, salida, ensure_ascii=False, indent=2)
    print(f"marcadas {len(sin_marca)} fichas")
    return 0


if __name__ == "__main__":
    sys.exit(main("--aplicar" in sys.argv))
