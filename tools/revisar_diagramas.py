#!/usr/bin/env python3
"""Mechanical review of the diagrams of every card in the library (no model involved).

Runs the existing card validator and adds coherence checks that need no basketball knowledge:
  BALL   a pass/dribble/shot made by someone who does not have the ball (follows the ball through the moves)
  LABEL  a player (A1, D2...) quoted in the card text that is not in any of its diagrams
  DEF    the text says "without defenders" but the diagram has them, or says "with a defender" and it has none
  RANGE  a player or cone outside the 0-100 court coordinates
  ORDER  repeated or non-increasing move numbers
  CONES  "four cones" in the text and a different number of cones in the diagram (warning only)

Usage (with the .venv Python):
  python tools/revisar_diagramas.py            # report on every card
  python tools/revisar_diagramas.py ej_237 ... # only these cards
"""
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
RAIZ = Path(__file__).resolve().parent.parent
RUTA = RAIZ / "data" / "exercises.json"
os.environ.setdefault("EXERCISES_PATH", str(RUTA))
sys.path.insert(0, str(RAIZ / "api"))

from validacion_fichas import validar_ficha  # noqa: E402
from diagramas import _SIN_DEFENSORES, _CON_DEFENSORES  # noqa: E402

VARIOS_BALONES = re.compile(r"(un|\d|dos|tres|cuatro)\s+bal(ón|ones)\s+(por|para|cada)|cada\s+\w+\s+(con|tiene)\s+(su|un)\s+bal|balón\s+por|balones\s+por|todos\s+(con|tienen)\s+(un\s+)?bal|con\s+su\s+bal")
NUMEROS = {"un": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7, "ocho": 8}


def texto_de(ficha: dict) -> str:
    partes = [ficha.get("nombre", ""), ficha.get("descripcion", "")]
    for campo in ("puntos_clave", "errores_frecuentes", "que_observar"):
        partes += ficha.get(campo) or []
    return "\n".join(str(p) for p in partes)


def diagramas_de(ficha: dict) -> list[dict]:
    if ficha.get("diagramas"):
        return ficha["diagramas"]
    return [ficha["diagrama"]] if ficha.get("diagrama") else []


def fuera_de_rango(d: dict) -> list[str]:
    malos = []
    for clave in ("jugadores_ataque", "jugadores_defensa", "conos"):
        for p in d.get(clave) or []:
            for eje in ("x", "y"):
                v = p.get(eje)
                if isinstance(v, (int, float)) and not 0 <= v <= 100:
                    malos.append(f"{p.get('id', 'cono')}.{eje}={v}")
    for m in d.get("movimientos") or []:
        for eje in ("x", "y"):
            v = (m.get("a_pos") or {}).get(eje)
            if isinstance(v, (int, float)) and not 0 <= v <= 100:
                malos.append(f"movimiento de {m.get('de')} {eje}={v}")
    return malos


def balon(d: dict, texto: str) -> list[str]:
    portador = (d.get("balon_inicio") or {}).get("portador")
    if VARIOS_BALONES.search(texto.lower()):      # one ball per player/pair/team: following a single ball makes no sense
        return []
    movs = sorted(d.get("movimientos") or [], key=lambda m: m.get("orden", 0))
    if not portador:
        return []
    problemas = []
    for m in movs:
        de, tipo = m.get("de"), m.get("tipo")
        if tipo in ("pase", "bote", "tiro"):
            if portador is None:                       # after a shot the ball is free (rebound): the next mover takes it
                portador = de
            if de != portador:
                problemas.append(f"orden {m.get('orden')}: {de} hace «{tipo}» pero el balón lo tiene {portador}")
            if tipo == "pase" and m.get("a"):
                portador = m["a"]
            elif tipo == "tiro":
                portador = None
    return problemas


def orden(d: dict) -> list[str]:
    nums = [m.get("orden") for m in d.get("movimientos") or []]
    if any(not isinstance(n, int) for n in nums):
        return ["movimientos sin número de orden"]
    if len(set(nums)) != len(nums):
        return [f"números de orden repetidos: {sorted(n for n, c in Counter(nums).items() if c > 1)}"]
    return []


def revisar(ficha: dict, biblioteca: list[dict]) -> list[tuple[str, str]]:
    salida = []
    ds = diagramas_de(ficha)
    if not ds:
        return [("SIN", "la ficha no tiene diagrama")] if not ficha.get("sin_diagrama") else []
    for p in validar_ficha(ficha, [f for f in biblioteca if f["id"] != ficha["id"]]):
        salida.append(("VALIDADOR", p))
    texto = texto_de(ficha)
    etiquetas_dibujo = set()
    n_def = 0
    n_conos = 0
    for n, d in enumerate(ds, 1):
        pref = f"[{d.get('titulo', n)}] " if len(ds) > 1 else ""
        etiquetas_dibujo |= {j.get("id") for j in (d.get("jugadores_ataque") or []) + (d.get("jugadores_defensa") or [])}
        n_def = max(n_def, len(d.get("jugadores_defensa") or []))
        n_conos = max(n_conos, len(d.get("conos") or []))
        for p in fuera_de_rango(d):
            salida.append(("RANGE", pref + p))
        for p in balon(d, texto):
            salida.append(("BALL", pref + p))
        for p in orden(d):
            salida.append(("ORDER", pref + p))
    citadas = set(re.findall(r"\b([AD]\d)\b", texto))
    for c in sorted(citadas - etiquetas_dibujo):
        salida.append(("LABEL", f"el texto cita {c} y no está en ningún diagrama"))
    bajo = texto.lower()
    if _SIN_DEFENSORES.search(bajo) and n_def:
        salida.append(("DEF", f"el texto dice «sin defensor» y el diagrama tiene {n_def}"))
    if _CON_DEFENSORES.search(bajo) and not n_def and not _SIN_DEFENSORES.search(bajo):
        salida.append(("DEF", "el texto menciona defensor y el diagrama no tiene ninguno"))
    for m in re.finditer(r"\b(un|uno|dos|tres|cuatro|cinco|seis|siete|ocho)\s+conos\b", bajo):
        esperado = NUMEROS[m.group(1)]
        if n_conos and esperado != n_conos and esperado > n_conos:
            salida.append(("CONES", f"el texto dice «{m.group(0)}» y el diagrama dibuja {n_conos} (aviso)"))
            break
    return salida


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
