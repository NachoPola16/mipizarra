#!/usr/bin/env python3
"""
Extrae pares Q&A de los PDFs de teoría, reglamento y planificación
para enriquecer el dataset de fine-tuning con conocimiento de baloncesto.

Uso:
  python tools/indexar_conocimiento.py
  python tools/indexar_conocimiento.py --ollama http://192.168.1.72:11434 --model llama3.2:3b
"""
import json
import argparse
import requests
import time
from pathlib import Path

try:
    from pypdf import PdfReader
except ImportError:
    from PyPDF2 import PdfReader

OUTPUT_DIR  = Path("data/dataset")
OUTPUT_FILE = OUTPUT_DIR / "from_conocimiento.jsonl"

COLECCIONES = {
    "teoria": {
        "path": Path("data/pdfs/coleccion_teoria"),
        "system": (
            "Eres MiPizarra, un asistente experto en entrenamiento de baloncesto. "
            "Tienes profundos conocimientos de metodología, técnica, táctica y pedagogía del baloncesto. "
            "Das respuestas claras, prácticas y adaptadas al nivel de formación."
        ),
        "tipo_qa": "metodologia",
    },
    "reglamento": {
        "path": Path("data/pdfs/coleccion_reglamento"),
        "system": (
            "Eres MiPizarra, un asistente experto en baloncesto. "
            "Conoces en detalle el reglamento FIBA y las normativas de competición en categorías de formación. "
            "Explicas las reglas de forma clara y con ejemplos prácticos."
        ),
        "tipo_qa": "reglamento",
    },
    "planificacion": {
        "path": Path("data/pdfs/coleccion_planificacion"),
        "system": (
            "Eres MiPizarra, un asistente experto en planificación del entrenamiento de baloncesto. "
            "Ayudas a los entrenadores a estructurar temporadas, microciclos y sesiones. "
            "Das consejos prácticos adaptados a las categorías de formación."
        ),
        "tipo_qa": "planificacion",
    },
}

PREGUNTAS_TIPO = {
    "metodologia": [
        "¿Qué aspectos técnicos y tácticos trabaja este contenido?",
        "¿Cómo se enseña esto en categorías de formación?",
        "¿Qué ejercicios o actividades se proponen?",
        "¿Cuáles son los errores más comunes y cómo corregirlos?",
        "¿Cómo se adapta este contenido según la edad de los jugadores?",
    ],
    "reglamento": [
        "¿Cuál es la regla o normativa que describe este texto?",
        "¿Cómo se aplica esta regla en una situación de juego real?",
        "¿En qué categorías aplica esta normativa?",
        "¿Cuáles son las infracciones más frecuentes relacionadas?",
    ],
    "planificacion": [
        "¿Cómo se estructura la planificación descrita?",
        "¿Qué objetivos se persiguen en cada fase?",
        "¿Cómo se adapta la carga de entrenamiento a lo largo de la temporada?",
        "¿Qué recomendaciones prácticas se dan para el entrenador?",
    ],
}


def llamar_ollama(ollama_url: str, model: str, messages: list, max_tokens: int = 800) -> str:
    try:
        r = requests.post(
            f"{ollama_url}/api/chat",
            json={
                "model":    model,
                "messages": messages,
                "stream":   False,
                "options":  {"temperature": 0.4, "num_predict": max_tokens, "num_ctx": 4096},
            },
            timeout=180,
        )
        r.raise_for_status()
        return r.json()["message"]["content"].strip()
    except Exception as e:
        print(f"    ✗ Ollama: {e}")
        return ""


def extraer_texto_pdf(pdf_path: Path, max_chars: int = 8000) -> list[str]:
    """Extrae texto del PDF y lo divide en chunks de ~1500 chars."""
    try:
        reader = PdfReader(str(pdf_path))
        texto_total = []
        for page in reader.pages:
            t = page.extract_text()
            if t and t.strip():
                texto_total.append(t.strip())
        texto = "\n\n".join(texto_total)[:max_chars]
    except Exception as e:
        print(f"    ✗ Error PDF: {e}")
        return []

    # Dividir en chunks de ~1500 chars en límites de párrafo
    chunks = []
    chunk_size = 1500
    inicio = 0
    while inicio < len(texto):
        fin = min(inicio + chunk_size, len(texto))
        # Buscar el próximo salto de párrafo para no cortar a mitad
        if fin < len(texto):
            siguiente_parrafo = texto.rfind("\n\n", inicio, fin + 200)
            if siguiente_parrafo > inicio + 500:
                fin = siguiente_parrafo
        chunk = texto[inicio:fin].strip()
        if len(chunk) > 200:
            chunks.append(chunk)
        inicio = fin

    return chunks


def generar_qa_de_chunk(chunk: str, system: str, preguntas: list,
                         ollama_url: str, model: str) -> list[dict]:
    """Genera pares Q&A a partir de un fragmento de texto."""
    import random
    pregunta = random.choice(preguntas)

    prompt = (
        f"Basándote EXCLUSIVAMENTE en este texto sobre baloncesto:\n\n"
        f"{chunk}\n\n"
        f"Responde de forma clara y completa: {pregunta}\n\n"
        f"Si el texto no contiene información suficiente para responder, "
        f"responde solo con: NO_APLICA"
    )

    respuesta = llamar_ollama(
        ollama_url, model,
        [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        max_tokens=600,
    )

    if not respuesta or "NO_APLICA" in respuesta or len(respuesta) < 80:
        return []

    return [{
        "task": "conocimiento",
        "conversations": [
            {"role": "system",    "content": system},
            {"role": "user",      "content": pregunta},
            {"role": "assistant", "content": respuesta},
        ],
        "meta": {"pregunta": pregunta},
    }]


def procesar_coleccion(nombre: str, config: dict, ollama_url: str, model: str,
                        max_chunks_por_pdf: int = 4) -> list[dict]:
    col_path = config["path"]
    if not col_path.exists():
        print(f"  ⚠ Carpeta no encontrada: {col_path}")
        return []

    pdfs = sorted(col_path.glob("**/*.pdf"))
    if not pdfs:
        print(f"  ⚠ Sin PDFs en {col_path}")
        return []

    print(f"\n── Colección '{nombre}': {len(pdfs)} PDFs ──")
    todos = []

    for pdf_path in pdfs:
        print(f"  · {pdf_path.name[:55]:<55} ", end="", flush=True)
        chunks = extraer_texto_pdf(pdf_path)
        if not chunks:
            print("(sin texto)")
            continue

        # Limitar chunks por PDF para no tardar demasiado
        chunks_a_usar = chunks[:max_chunks_por_pdf]
        ejemplos_pdf = []

        for chunk in chunks_a_usar:
            pares = generar_qa_de_chunk(
                chunk,
                config["system"],
                PREGUNTAS_TIPO[config["tipo_qa"]],
                ollama_url, model,
            )
            ejemplos_pdf.extend(pares)
            time.sleep(0.2)

        todos.extend(ejemplos_pdf)
        print(f"✓ {len(ejemplos_pdf)} Q&A")

    return todos


def main():
    parser = argparse.ArgumentParser(description="Extrae Q&A de PDFs de conocimiento")
    parser.add_argument("--ollama",           default="http://192.168.1.72:11434")
    parser.add_argument("--model",            default="llama3.2:3b")
    parser.add_argument("--chunks-por-pdf",   type=int, default=4,
                        help="Máximo de fragmentos a procesar por PDF (default: 4)")
    parser.add_argument("--colecciones",      nargs="+",
                        choices=["teoria", "reglamento", "planificacion"],
                        default=["teoria", "reglamento", "planificacion"],
                        help="Colecciones a procesar")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    todos_ejemplos = []

    for nombre in args.colecciones:
        config = COLECCIONES[nombre]
        ejemplos = procesar_coleccion(
            nombre, config, args.ollama, args.model,
            max_chunks_por_pdf=args.chunks_por_pdf,
        )
        todos_ejemplos.extend(ejemplos)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for ej in todos_ejemplos:
            f.write(json.dumps(ej, ensure_ascii=False) + "\n")

    por_col = {}
    for ej in todos_ejemplos:
        c = ej.get("meta", {}).get("pregunta", "?")[:30]
        por_col[ej["task"]] = por_col.get(ej["task"], 0) + 1

    print(f"\n{'='*50}")
    print(f"✅ Conocimiento indexado: {len(todos_ejemplos)} Q&A")
    print(f"   Guardado en: {OUTPUT_FILE}")
    print(f"\nPróximo paso:")
    print(f"  python tools/generar_dataset.py --incluir-pdfs --incluir-conocimiento")


if __name__ == "__main__":
    main()
