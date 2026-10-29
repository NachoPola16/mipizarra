#!/usr/bin/env python3
"""Diagramas para fichas de la biblioteca que no tienen (o que están marcadas «sin_diagrama»), por lotes.

Un parche es un JSON {id_ficha: {"diagrama": {...}} | {"diagramas": [{"titulo": "...", ...}]} | {"sin_diagrama": true}}.

Uso (con el Python de .venv):
  python tools/diagramas_lote.py listar ej_064 ej_065 ...     # ficha completa de cada id, para dibujarla
  python tools/diagramas_lote.py comprobar parche.json        # valida cada diagrama contra el filtro de fichas
  python tools/diagramas_lote.py hoja parche.json hoja.html   # hoja de contactos con los SVG para revisarlos a ojo
  python tools/diagramas_lote.py aplicar parche.json          # vuelca el parche en data/exercises.json
"""
import json
import os
import sys
from html import escape
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
RAIZ = Path(__file__).resolve().parent.parent
RUTA = RAIZ / "data" / "exercises.json"
os.environ.setdefault("EXERCISES_PATH", str(RUTA))
sys.path.insert(0, str(RAIZ / "api"))

from diagram_renderer import render_diagram  # noqa: E402
from validacion_fichas import validar_ficha  # noqa: E402


def _cargar():
    return json.loads(RUTA.read_text(encoding="utf-8"))


def _fusionada(ficha: dict, cambio: dict) -> dict:
    nueva = {k: v for k, v in ficha.items() if k not in ("diagrama", "diagramas", "sin_diagrama")}
    nueva.update(cambio)
    return nueva


def listar(ids):
    por_id = {f["id"]: f for f in _cargar()}
    for i in ids:
        f = por_id[i]
        print(f"=== {i} · {f['nombre']} · {f['categoria']}/{f.get('subcategoria', '')} · edades {f['edades']} · "
              f"espacio {f.get('espacio', '?')} · mín. {f.get('jugadores_minimos')} jugadores")
        print("DESCRIPCIÓN:", f["descripcion"])
        if f.get("material"):
            print("MATERIAL:", f["material"])
        print()


def comprobar(parche) -> int:
    biblioteca = _cargar()
    por_id = {f["id"]: f for f in biblioteca}
    malos = 0
    for i, cambio in parche.items():
        if i not in por_id:
            print(f"{i}: NO EXISTE")
            malos += 1
            continue
        if cambio.get("sin_diagrama"):
            print(f"{i}: sin diagrama (se queda como juego libre)")
            continue
        problemas = validar_ficha(_fusionada(por_id[i], cambio), [f for f in biblioteca if f["id"] != i])
        print(f"{i}: " + ("OK" if not problemas else "PROBLEMAS " + " | ".join(problemas)))
        malos += bool(problemas)
    return 1 if malos else 0


def hoja(parche, salida):
    por_id = {f["id"]: f for f in _cargar()}
    trozos = ["<meta charset=utf-8><style>body{font-family:sans-serif;background:#eee}.f{display:inline-block;"
              "vertical-align:top;width:430px;margin:6px;background:#fff;padding:6px}svg{width:100%;height:auto}"
              "h4{margin:2px 0;font-size:13px}</style>"]
    for i, cambio in parche.items():
        if cambio.get("sin_diagrama"):
            continue
        ficha = por_id[i]
        ds = cambio.get("diagramas") or [cambio["diagrama"]]
        for n, d in enumerate(ds):
            titulo = escape(f"{i} · {ficha['nombre'][:60]}" + (f" · {d.get('titulo', n + 1)}" if len(ds) > 1 else ""))
            edad = "U10" if set(ficha["edades"]) <= {"U8", "U10", "U12"} else "U16"
            trozos.append(f"<div class=f><h4>{titulo}</h4>{render_diagram(dict(d), edad=edad)}</div>")
    Path(salida).write_text("".join(trozos), encoding="utf-8")
    print("escrita", salida)


def aplicar(parche):
    biblioteca = _cargar()
    por_id = {f["id"]: f for f in biblioteca}
    for i, cambio in parche.items():
        f = por_id[i]
        if cambio.get("sin_diagrama"):
            continue
        for k in ("diagrama", "diagramas", "sin_diagrama"):
            f.pop(k, None)
        f.update({k: v for k, v in cambio.items() if k in ("diagrama", "diagramas")})
    with open(RUTA, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(biblioteca, ensure_ascii=False, indent=2))
    print("aplicado")


if __name__ == "__main__":
    orden, *resto = sys.argv[1:]
    if orden == "listar":
        listar(resto)
    else:
        datos = json.loads(Path(resto[0]).read_text(encoding="utf-8"))
        if orden == "comprobar":
            sys.exit(comprobar(datos))
        elif orden == "hoja":
            hoja(datos, resto[1])
        elif orden == "aplicar":
            if comprobar(datos):
                sys.exit("hay problemas: no se aplica")
            aplicar(datos)
