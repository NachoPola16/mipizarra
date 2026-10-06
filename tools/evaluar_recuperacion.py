#!/usr/bin/env python3
"""Evalúa la recuperación (RAG) de las colecciones de .md curados con preguntas fijas.

Para cada pregunta se mira en qué posición aparece el primer fragmento que contiene la respuesta
(los «términos de respuesta» de PREGUNTAS) y se resume con acierto en las 1, 3, 5 y 8 primeras
posiciones y el rango recíproco medio (MRR). Sirve para comparar modelos de embeddings con los mismos
documentos y las mismas preguntas, y para vigilar que un cambio no empeora la búsqueda.

Se ejecuta dentro del contenedor de la API (necesita ChromaDB y Ollama). El modelo y la base de
datos se eligen con variables de entorno, así que se puede probar un modelo nuevo sin tocar la base real:

  # base real (el modelo con el que está indexada)
  docker exec mipizarra-api python /app/tools/evaluar_recuperacion.py

  # modelo nuevo en una base temporal: indexa los .md y evalúa
  docker exec -e EMBED_MODEL=bge-m3 -e CHROMA_DB_DIR=/tmp/chroma_bge mipizarra-api \\
      python /app/tools/evaluar_recuperacion.py --indexar
"""
import argparse
import os
import sys
import unicodedata
from pathlib import Path

# (id, colección, ámbito o None, pregunta, términos: basta que el fragmento contenga alguno)
PREGUNTAS = [
    ("pista_delantera", "reglamento_md", "general",
     "¿Cuántos segundos tiene un equipo para pasar el balón a su pista delantera?", ["8 segundos"]),
    ("rebote_ofensivo", "reglamento_md", "general",
     "Si tras un tiro el balón toca el aro y el equipo atacante recupera el rebote, ¿a cuántos segundos se "
     "reinicia el reloj de posesión?", ["restablecen 14 segundos", "14 segundos"]),
    ("faltas_eliminacion", "reglamento_md", "general",
     "¿Con cuántas faltas personales queda eliminado un jugador?", ["5 faltas personales", "5 faltas = exclusión"]),
    ("tres_segundos", "reglamento_md", "general",
     "¿Cuánto tiempo puede estar un atacante en la zona restringida rival?", ["3 segundos"]),
    ("falta_disruptiva", "reglamento_md", "general",
     "¿Qué es una falta disruptiva?", ["falta disruptiva (art. 37)", "## falta disruptiva"]),
    ("falta_flagrante", "reglamento_md", "general",
     "¿Qué es una falta flagrante y qué sanción tiene?", ["falta flagrante"]),
    ("antideportiva", "reglamento_md", "general",
     "¿Sigue existiendo la falta antideportiva?", ["antideportiva"]),
    ("cinco_segundos", "reglamento_md", "general",
     "¿Cuántos segundos tiene un jugador para sacar de banda o lanzar un tiro libre?", ["5 segundos"]),
    ("semicirculo", "reglamento_md", "general",
     "¿Qué es el semicírculo de no carga?", ["semicírculo"]),
    ("pasos", "reglamento_md", "general",
     "¿Cuándo se señala pasos o desplazamiento ilegal?", ["desplazamiento ilegal"]),
    ("goaltending", "reglamento_md", "general",
     "¿Qué es el goaltending o interferencia en el aro?", ["goaltending"]),
    ("triple_fiba", "reglamento_md", "general",
     "¿A qué distancia está la línea de triple en FIBA?", ["6,75"]),
    ("aro_minibasket", "reglamento_md", "general",
     "¿A qué altura está el aro en minibasket?", ["2,60"]),
    ("periodos_alevin", "reglamento_md", "aragon",
     "¿Cuántos periodos debe jugar cada jugador en alevín en Aragón?", ["al menos dos periodos"]),
    ("defensas_minibasket", "reglamento_md", "aragon",
     "¿Qué defensas están permitidas en minibasket en las competiciones escolares de Aragón?",
     ["prohibidas las defensas en zona", "presión individual"]),
    ("tecnica_categorias", "reglamento_md", "general",
     "¿Cuántas categorías tiene ahora la falta técnica?", ["ahora hay dos categorías"]),
    ("bloqueo_directo_edad", "teoria_md", None,
     "¿Desde qué categoría se trabaja el bloqueo directo?", ["Cadete | U16 | Bloqueo directo"]),
    ("paso_cero", "teoria_md", None,
     "¿Qué es el paso cero?", ["paso cero"]),
    ("espaciado", "teoria_md", None,
     "¿Cómo se trabaja el espaciado con niños de preminibasket?", ["generar espacios en preminibasket", "bases"]),
    ("lineas_rojas_mini", "teoria_md", None,
     "¿Qué contenidos no se recomiendan en minibasket?", ["aro pasado", "línea roja", "líneas rojas"]),
]

COLECCIONES_MD = ("reglamento_md", "teoria_md")
PUNTOS_CORTE = (1, 3, 5, 8)
PROFUNDIDAD = 12


def normalizar(texto: str) -> str:
    """Minúsculas y sin tildes, para comparar términos sin depender de la grafía."""
    sin = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in sin if unicodedata.category(c) != "Mn")


def contiene(fragmento: str, terminos: list[str]) -> bool:
    f = normalizar(fragmento)
    return any(normalizar(t) in f for t in terminos)


def rango(fragmentos: list[str], terminos: list[str]) -> int | None:
    """Posición (desde 1) del primer fragmento que contiene alguno de los términos, o None."""
    for i, fragmento in enumerate(fragmentos, start=1):
        if contiene(fragmento, terminos):
            return i
    return None


def resumen(rangos: list[int | None]) -> dict:
    """Acierto en las k primeras posiciones y rango recíproco medio de una lista de rangos."""
    n = len(rangos)
    r = {f"@{k}": sum(1 for x in rangos if x is not None and x <= k) / n for k in PUNTOS_CORTE}
    r["MRR"] = sum(1 / x for x in rangos if x) / n
    return r


def _indexar() -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import indexar_colecciones as ic

    def subcarpetas(base: Path) -> list:
        return sorted(d for d in base.iterdir() if d.is_dir()) if base.exists() else []

    ic.indexar_coleccion("teoria_md", [ic.TEORIA_MD_DIR])
    ic.indexar_coleccion("reglamento_md", [(d, d.name) for d in subcarpetas(ic.REGLAMENTO_DIR)])
    ic.escribir_marca(ic.CHROMA_DB_DIR, ic.EMBED_MODEL)


def _evaluar(modelo: str, ruta_db: str, detalle: bool) -> dict:
    import chromadb
    from llama_index.embeddings.ollama import OllamaEmbedding

    embed = OllamaEmbedding(model_name=modelo, base_url=os.environ.get("OLLAMA_URL", "http://ollama:11434"))
    cliente = chromadb.PersistentClient(path=ruta_db)
    colecciones = {c: cliente.get_collection(c) for c in COLECCIONES_MD}
    cuerpo = {c: col.get(include=["documents"])["documents"] for c, col in colecciones.items()}

    rangos, fallos, sin_respuesta = [], [], []
    for id_, coleccion, ambito, pregunta, terminos in PREGUNTAS:
        # comprobación de la propia pregunta: la respuesta tiene que estar en algún fragmento de la colección
        if not any(contiene(d, terminos) for d in cuerpo[coleccion]):
            sin_respuesta.append(id_)
            continue
        consulta = dict(query_embeddings=[embed.get_text_embedding(pregunta)], n_results=PROFUNDIDAD,
                        include=["documents"])
        if ambito:
            consulta["where"] = {"ambito": ambito}
        docs = colecciones[coleccion].query(**consulta)["documents"][0]
        r = rango(docs, terminos)
        rangos.append(r)
        if detalle or r is None or r > 3:
            fallos.append((id_, r))
    return {"resumen": resumen(rangos) if rangos else {}, "n": len(rangos), "fallos": fallos,
            "sin_respuesta": sin_respuesta}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--indexar", action="store_true", help="indexa los .md en la base indicada antes de evaluar")
    ap.add_argument("--detalle", action="store_true", help="muestra el rango de todas las preguntas")
    args = ap.parse_args(argv)

    modelo = os.environ.get("EMBED_MODEL", "nomic-embed-text")
    ruta_db = os.environ.get("CHROMA_DB_DIR", "/app/data/chroma_db")
    if args.indexar:
        _indexar()
    res = _evaluar(modelo, ruta_db, args.detalle)

    print(f"\nModelo: {modelo} | base: {ruta_db} | preguntas evaluadas: {res['n']}")
    if res["sin_respuesta"]:
        print(f"Sin respuesta en el corpus (excluidas): {', '.join(res['sin_respuesta'])}")
    if res["resumen"]:
        print("  ".join(f"{k}: {v:.0%}" if k != "MRR" else f"MRR: {v:.2f}" for k, v in res["resumen"].items()))
    for id_, r in res["fallos"]:
        print(f"  · {id_}: {'no aparece en las %d primeras' % PROFUNDIDAD if r is None else 'puesto %d' % r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
