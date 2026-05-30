"""Lee exercises_editable.txt y sincroniza DESCRIPCION y PUNTOS_CLAVE
de vuelta a exercises.json. Solo modifica esos dos campos; el resto
(categoría, diagramas, intensidad, etc.) lo deja intacto en el JSON.
"""
import json, re, sys

SRC_TXT  = r"c:\Users\nacho\Proyectos\servidor-config\mipizarra\exercises_editable.txt"
SRC_JSON = r"c:\Users\nacho\Proyectos\servidor-config\mipizarra\data\exercises.json"
SEP      = "=" * 80


def parse_txt(path: str) -> dict:
    """Devuelve {id: {descripcion, puntos_clave}} para cada ejercicio."""
    with open(path, encoding="utf-8") as f:
        content = f.read()

    blocks = re.split(r"={80}\n", content)
    result = {}

    i = 0
    while i < len(blocks):
        block = blocks[i].strip()
        if not block:
            i += 1
            continue

        # Primera línea del bloque: "EJ_001 | Nombre"
        first_line = block.splitlines()[0].strip()
        m = re.match(r"^(EJ_\d+)\s*\|", first_line, re.IGNORECASE)
        if not m:
            i += 1
            continue

        ex_id = m.group(1).lower()  # ej_001

        # Extraer DESCRIPCION y PUNTOS_CLAVE dentro del bloque
        # Formato: bloque contiene la cabecera, luego el contenido real está en
        # el bloque SIGUIENTE al separador que viene después de la cabecera.
        # En realidad, la estructura del fichero es:
        #   SEP
        #   ID | nombre
        #   metadatos
        #   SEP          ← aquí split genera un bloque con "DESCRIPCION:..."
        # Así que el contenido (DESCRIPCION + PUNTOS_CLAVE) está en blocks[i+1]
        if i + 1 >= len(blocks):
            i += 1
            continue

        content_block = blocks[i + 1]

        # Descripción
        desc_match = re.search(
            r"DESCRIPCION:\n(.*?)(?=\nPUNTOS_CLAVE:|\Z)", content_block, re.DOTALL
        )
        descripcion = desc_match.group(1).strip() if desc_match else ""

        # Puntos clave (líneas "N. texto")
        pk_match = re.search(
            r"PUNTOS_CLAVE:\n(.*?)(?=\Z)", content_block, re.DOTALL
        )
        puntos_clave = []
        if pk_match:
            pk_block = pk_match.group(1)
            for line in pk_block.splitlines():
                line = line.strip()
                m2 = re.match(r"^\d+\.\s+(.*)", line)
                if m2:
                    puntos_clave.append(m2.group(1))

        result[ex_id] = {
            "descripcion": descripcion,
            "puntos_clave": puntos_clave,
        }
        i += 2  # saltar el bloque de cabecera Y el de contenido

    return result


def main():
    print(f"Leyendo: {SRC_TXT}")
    updates = parse_txt(SRC_TXT)
    print(f"  Ejercicios encontrados en el .txt: {len(updates)}")

    with open(SRC_JSON, encoding="utf-8") as f:
        exercises = json.load(f)

    changed = 0
    for ex in exercises:
        upd = updates.get(ex["id"])
        if not upd:
            continue
        modified = False
        if upd["descripcion"] and upd["descripcion"] != ex.get("descripcion", ""):
            ex["descripcion"] = upd["descripcion"]
            modified = True
        if upd["puntos_clave"] and upd["puntos_clave"] != ex.get("puntos_clave", []):
            ex["puntos_clave"] = upd["puntos_clave"]
            modified = True
        if modified:
            changed += 1
            print(f"  Actualizado {ex['id']}: {ex['nombre']}")

    with open(SRC_JSON, "w", encoding="utf-8") as f:
        json.dump(exercises, f, ensure_ascii=False, indent=2)

    # Verificar JSON
    with open(SRC_JSON, encoding="utf-8") as f:
        check = json.load(f)
    print(f"\nOK — {changed} ejercicios modificados. JSON válido ({len(check)} ejercicios).")


if __name__ == "__main__":
    main()
