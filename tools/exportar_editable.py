"""Exporta exercises.json a un .txt editable por humanos.
El usuario edita DESCRIPCION y PUNTOS_CLAVE; después ejecuta importar_editable.py
para sincronizar los cambios de vuelta a exercises.json.
"""
import json, textwrap

SRC  = r"c:\Users\nacho\Proyectos\servidor-config\mipizarra\data\exercises.json"
DEST = r"c:\Users\nacho\Proyectos\servidor-config\mipizarra\exercises_editable.txt"
SEP  = "=" * 80

with open(SRC, encoding="utf-8") as f:
    data = json.load(f)

lines = []
for ex in data:
    lines.append(SEP)
    # Cabecera con ID y nombre
    lines.append(f"{ex['id'].upper()} | {ex['nombre']}")
    # Metadatos de contexto (no se editan, son informacionales)
    cat = ex.get("categoria", "")
    sub = ex.get("subcategoria", "")
    cat_str = f"{cat}/{sub}" if sub else cat
    edades  = " ".join(ex.get("edades", []))
    dur     = ex.get("duracion_min", "?")
    ints    = ex.get("intensidad", "?")
    cog     = ex.get("carga_cognitiva", "?")
    minp    = ex.get("jugadores_minimos", "?")
    lines.append(f"[{cat_str}] [{edades}] [{dur} min] [Int:{ints}/5 Cog:{cog}/5] [Mín:{minp} jug]")
    lines.append(SEP)
    lines.append("")
    # Descripción
    lines.append("DESCRIPCION:")
    desc = ex.get("descripcion", "")
    # Mantener párrafos, sin wrap forzado (el usuario lo ve todo en una línea por intención)
    lines.append(desc)
    lines.append("")
    # Puntos clave
    lines.append("PUNTOS_CLAVE:")
    for i, pk in enumerate(ex.get("puntos_clave", []), 1):
        lines.append(f"{i}. {pk}")
    lines.append("")
    lines.append("")

with open(DEST, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print(f"Exportado: {DEST}")
print(f"  {len(data)} ejercicios | Edita DESCRIPCION y PUNTOS_CLAVE libremente.")
print(f"  Cuando termines, ejecuta: python tools/importar_editable.py")
