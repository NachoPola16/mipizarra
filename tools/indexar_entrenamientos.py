#!/usr/bin/env python3
"""
Extrae ejemplos de entrenamiento de PDFs para el fine-tuning.

Lee todos los PDFs de coleccion_entrenamientos/, extrae el texto,
identifica si es una sesión completa o una colección de ejercicios,
y convierte cada uno en pares (instrucción → respuesta) para fine-tuning.

Para ejercicios con posiciones concretas, regenera automáticamente
las coordenadas del diagrama usando el LLM.

Uso:
  python tools/indexar_entrenamientos.py
  python tools/indexar_entrenamientos.py --ollama http://192.168.1.72:11434 --model llama3.2:3b
  python tools/indexar_entrenamientos.py --dry-run   # Solo muestra qué encontraría
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

PDF_DIR    = Path("data/pdfs/coleccion_entrenamientos")
OUTPUT_DIR = Path("data/dataset")
OUTPUT_FILE = OUTPUT_DIR / "from_pdfs.jsonl"

SYSTEM_SESION = (
    "Eres MiPizarra, un asistente experto en entrenamiento de baloncesto. "
    "Diseñas sesiones de entrenamiento estructuradas y prácticas. "
    "Usas terminología técnica española (codo TL, cabecera, baseline, poste alto/bajo, "
    "45 grados, esquina, poste bajo, línea de fondo). "
    "Siempre propones ejercicios con posiciones y organizaciones concretas."
)

SYSTEM_EJERCICIO = (
    "Eres un asistente experto en baloncesto. "
    "Estructuras ejercicios de baloncesto en formato JSON con todos sus campos. "
    "Cuando la descripción menciona posiciones concretas (cabecera, 45, codo, esquina...) "
    "generas también el diagrama con coordenadas normalizadas (x:0-100, y:0-100; y=0 es baseline)."
)

SYSTEM_DIAGRAMA = (
    "Eres un experto en diagramas de baloncesto. Conviertes descripciones tácticas en JSON. "
    "Coordenadas (x, y): x=0 lateral izquierdo, x=100 lateral derecho; "
    "y=0 baseline/canasta, y=41 línea TL, y=60 arco triple, y=100 medio campo. "
    "Posiciones clave: esquina derecha (6,22), esquina izquierda (94,22), "
    "codo TL derecho (35,41), codo TL izquierdo (65,41), "
    "45° derecha (25,52), 45° izquierda (75,52), cabecera (50,65), canasta (50,11)."
)

PALABRAS_POSICION = [
    "cabecera", "45", "codo", "esquina", "poste", "baseline", "fondo",
    "línea de tiros", "tl ", "tiro libre", "triple", "arco", "lateral",
    "banda", "poste alto", "poste bajo", "bloqueo", "pantalla",
]

PALABRAS_SESION = [
    "calentamiento", "parte principal", "vuelta a la calma", "sesión",
    "ejercicio 1", "ejercicio 2", "minutos", "objetivo:", "categoría:",
    "intensidad", "fundamentos", "descanso"
]


def llamar_ollama(ollama_url: str, model: str, messages: list, max_tokens: int = 1200) -> str:
    try:
        r = requests.post(
            f"{ollama_url}/api/chat",
            json={
                "model":    model,
                "messages": messages,
                "stream":   False,
                "options":  {"temperature": 0.4, "num_predict": max_tokens, "num_ctx": 4096},
            },
            timeout=240,
        )
        r.raise_for_status()
        return r.json()["message"]["content"].strip()
    except Exception as e:
        print(f"    ✗ Ollama error: {e}")
        return ""


def extraer_texto_pdf(pdf_path: Path) -> str:
    """Extrae todo el texto del PDF, página por página."""
    try:
        reader = PdfReader(str(pdf_path))
        partes = []
        for i, page in enumerate(reader.pages):
            texto = page.extract_text()
            if texto and texto.strip():
                partes.append(f"[Página {i+1}]\n{texto.strip()}")
        return "\n\n".join(partes)
    except Exception as e:
        print(f"    ✗ Error leyendo PDF: {e}")
        return ""


def tiene_posiciones(texto: str) -> bool:
    """Detecta si la descripción menciona posiciones concretas en pista."""
    texto_lower = texto.lower()
    return sum(1 for p in PALABRAS_POSICION if p in texto_lower) >= 2


def es_sesion_completa(texto: str) -> bool:
    """Detecta si el texto es una sesión estructurada completa."""
    texto_lower = texto.lower()
    return sum(1 for p in PALABRAS_SESION if p in texto_lower) >= 3


def generar_diagrama(descripcion: str, nombre: str, ollama_url: str, model: str) -> dict | None:
    """Genera coordenadas JSON de diagrama para un ejercicio con posiciones concretas."""
    prompt = (
        f"Genera las coordenadas JSON del diagrama para este ejercicio.\n\n"
        f"Ejercicio: {nombre}\n"
        f"Descripción: {descripcion}\n\n"
        f"Devuelve SOLO el JSON con: tipo, jugadores_ataque, jugadores_defensa, "
        f"balon_inicio, movimientos (con campo orden), conos."
    )
    resp = llamar_ollama(
        ollama_url, model,
        [{"role": "system", "content": SYSTEM_DIAGRAMA}, {"role": "user", "content": prompt}],
        max_tokens=600,
    )
    if not resp:
        return None
    # Limpiar markdown
    if "```json" in resp:
        resp = resp.split("```json")[1].split("```")[0].strip()
    elif "```" in resp:
        resp = resp.split("```")[1].split("```")[0].strip()
    try:
        return json.loads(resp)
    except Exception:
        return None


# ─── Extracción de sesión completa ──────────────────────────────────────────
def procesar_como_sesion(texto_pdf: str, pdf_path: Path,
                         ollama_url: str, model: str) -> list[dict]:
    """
    El PDF contiene una sesión completa.
    Le pedimos al LLM que identifique categoría/objetivo/duración
    y reformatee el contenido al estilo de la app.
    """
    # Truncar para no superar el contexto
    texto_truncado = texto_pdf[:3000]

    # Paso 1: extraer metadatos
    meta_prompt = (
        f"Lee este texto de una sesión de entrenamiento de baloncesto y extrae:\n"
        f"- categoria: la categoría de edad (Prebenjamín/Benjamín/Alevín/Infantil/Cadete/Junior/Senior)\n"
        f"- duracion: duración total en minutos (número entero)\n"
        f"- objetivo: objetivo principal en 2-4 palabras (ej: 'defensa individual', 'tiro exterior')\n\n"
        f"Texto:\n{texto_truncado}\n\n"
        f"Devuelve SOLO JSON: {{\"categoria\": \"...\", \"duracion\": 90, \"objetivo\": \"...\"}}"
    )
    meta_resp = llamar_ollama(
        ollama_url, model,
        [{"role": "user", "content": meta_prompt}],
        max_tokens=100,
    )
    if "```" in meta_resp:
        meta_resp = meta_resp.split("```")[1] if "json" not in meta_resp else meta_resp.split("```json")[1]
        meta_resp = meta_resp.split("```")[0].strip()
    try:
        meta = json.loads(meta_resp)
        categoria = meta.get("categoria", "Cadete")
        duracion  = int(meta.get("duracion", 90))
        objetivo  = meta.get("objetivo", "baloncesto")
    except Exception:
        categoria, duracion, objetivo = "Cadete", 90, "baloncesto"

    # Paso 2: reformatear la sesión al estilo de la app
    reformat_prompt = (
        f"Tienes esta sesión de entrenamiento de baloncesto:\n\n{texto_truncado}\n\n"
        f"Reformateala manteniendo todo el contenido pero usando exactamente esta estructura:\n"
        f"**CALENTAMIENTO (X min)**\n"
        f"Juego: ...\nReglas: ...\n\n"
        f"**PARTE PRINCIPAL**\n\n"
        f"Ejercicio 1: [nombre]\nDuración: X min\nOrganización: [posiciones concretas]\nPuntos clave: ...\n\n"
        f"[más ejercicios...]\n\n"
        f"**VUELTA A LA CALMA (X min)**\n...\n\n"
        f"**Fundamentos**: ..."
    )
    sesion_reformateada = llamar_ollama(
        ollama_url, model,
        [{"role": "system", "content": SYSTEM_SESION}, {"role": "user", "content": reformat_prompt}],
        max_tokens=1400,
    )
    if not sesion_reformateada or len(sesion_reformateada) < 200:
        return []

    user_prompt = (
        f"Genera una sesión de entrenamiento de baloncesto.\n\n"
        f"Categoría: {categoria}\nDuración: {duracion} minutos\nObjetivo: {objetivo}"
    )

    return [{
        "task": "sesion",
        "fuente": pdf_path.name,
        "conversations": [
            {"role": "system",    "content": SYSTEM_SESION},
            {"role": "user",      "content": user_prompt},
            {"role": "assistant", "content": sesion_reformateada},
        ],
        "meta": {"categoria": categoria, "duracion": duracion, "objetivo": objetivo},
    }]


# ─── Extracción de colección de ejercicios ──────────────────────────────────
def procesar_como_ejercicios(texto_pdf: str, pdf_path: Path,
                              ollama_url: str, model: str) -> list[dict]:
    """
    El PDF contiene uno o varios ejercicios.
    Divide el texto en ejercicios individuales y genera un ejemplo por cada uno,
    incluyendo diagrama si el ejercicio menciona posiciones concretas.
    """
    # Paso 1: dividir el PDF en ejercicios individuales
    division_prompt = (
        f"Este texto contiene ejercicios de baloncesto (puede ser uno o varios).\n"
        f"Identifica cada ejercicio y devuelve un JSON array donde cada elemento tiene:\n"
        f"  {{\"nombre\": \"...\", \"descripcion\": \"descripción completa del ejercicio\"}}\n\n"
        f"Incluye TODA la información de cada ejercicio en su descripción "
        f"(organización, posiciones, variantes, puntos clave).\n\n"
        f"Texto:\n{texto_pdf[:4000]}\n\n"
        f"JSON array:"
    )
    division_resp = llamar_ollama(
        ollama_url, model,
        [{"role": "user", "content": division_prompt}],
        max_tokens=1500,
    )
    if "```json" in division_resp:
        division_resp = division_resp.split("```json")[1].split("```")[0].strip()
    elif "```" in division_resp:
        division_resp = division_resp.split("```")[1].split("```")[0].strip()

    try:
        ejercicios_raw = json.loads(division_resp)
        if not isinstance(ejercicios_raw, list):
            ejercicios_raw = [ejercicios_raw]
    except Exception:
        print(f"    ✗ No se pudo dividir en ejercicios")
        return []

    ejemplos = []
    for ej_raw in ejercicios_raw:
        nombre = ej_raw.get("nombre", "Ejercicio")
        desc   = ej_raw.get("descripcion", "")
        if not desc or len(desc) < 30:
            continue

        print(f"    → Ejercicio: '{nombre[:50]}' ", end="", flush=True)

        # Paso 2: estructurar como JSON de ejercicio
        con_diagrama = tiene_posiciones(desc)
        struct_prompt = (
            f"Estructura este ejercicio de baloncesto como JSON.\n\n"
            f"Nombre: {nombre}\nDescripción: {desc}\n\n"
            f"Campos requeridos: nombre, categoria (tiro/defensa/bloqueo_directo/etc.), "
            f"subcategoria, edades (array de categorías españolas), duracion_min, "
            f"intensidad (1-5), carga_cognitiva (1-5), "
            f"objetivos {{tacticos:[], tecnicos:[], fisicos:[]}}.\n"
            f"{'Incluye también el campo diagrama con jugadores y movimientos.' if con_diagrama else 'Usa diagrama: null.'}\n\n"
            f"SOLO JSON:"
        )
        struct_resp = llamar_ollama(
            ollama_url, model,
            [{"role": "system", "content": SYSTEM_EJERCICIO}, {"role": "user", "content": struct_prompt}],
            max_tokens=700,
        )
        if "```json" in struct_resp:
            struct_resp = struct_resp.split("```json")[1].split("```")[0].strip()
        elif "```" in struct_resp:
            struct_resp = struct_resp.split("```")[1].split("```")[0].strip()

        try:
            json.loads(struct_resp)
        except Exception:
            print("✗ JSON inválido")
            continue

        # Ejemplo de estructuración de ejercicio
        ejemplos.append({
            "task": "ejercicio",
            "fuente": pdf_path.name,
            "conversations": [
                {"role": "system",    "content": SYSTEM_EJERCICIO},
                {"role": "user",      "content": f"Estructura este ejercicio de baloncesto como JSON.\n\nDescripción:\n\"{desc}\""},
                {"role": "assistant", "content": struct_resp},
            ],
            "meta": {"nombre": nombre},
        })

        # Si tiene posiciones, generar también ejemplo de diagrama
        if con_diagrama:
            diagrama = generar_diagrama(desc, nombre, ollama_url, model)
            if diagrama:
                diagrama_json = json.dumps(diagrama, ensure_ascii=False)
                ejemplos.append({
                    "task": "diagrama",
                    "fuente": pdf_path.name,
                    "conversations": [
                        {"role": "system",    "content": SYSTEM_DIAGRAMA},
                        {"role": "user",      "content": f"Genera las coordenadas del diagrama para este ejercicio.\n\nEjercicio: {nombre}\nDescripción: {desc}"},
                        {"role": "assistant", "content": diagrama_json},
                    ],
                    "meta": {"nombre": nombre},
                })
                print(f"✓ (con diagrama)")
            else:
                print(f"✓ (sin diagrama)")
        else:
            print(f"✓")

        time.sleep(0.3)

    return ejemplos


# ─── Main ────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Indexa PDFs de entrenamientos para fine-tuning")
    parser.add_argument("--ollama",  default="http://192.168.1.72:11434")
    parser.add_argument("--model",   default="llama3.2:3b")
    parser.add_argument("--dir",     default=str(PDF_DIR), help="Carpeta con PDFs")
    parser.add_argument("--dry-run", action="store_true",  help="Solo muestra qué encontraría, sin procesar")
    args = parser.parse_args()

    pdf_dir = Path(args.dir)
    if not pdf_dir.exists():
        pdf_dir.mkdir(parents=True)
        print(f"✓ Carpeta creada: {pdf_dir}/")
        print(f"  Añade aquí tus PDFs de entrenamientos y vuelve a ejecutar el script.")
        return

    pdfs = sorted(pdf_dir.glob("**/*.pdf"))
    if not pdfs:
        print(f"No se encontraron PDFs en {pdf_dir}/")
        print(f"Añade PDFs de sesiones de entrenamiento o colecciones de ejercicios.")
        return

    print(f"PDFs encontrados: {len(pdfs)}")
    for p in pdfs:
        print(f"  · {p.relative_to(pdf_dir)}")

    if args.dry_run:
        print("\n(dry-run: termina aquí sin procesar)")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    todos_ejemplos = []

    for i, pdf_path in enumerate(pdfs, 1):
        print(f"\n[{i}/{len(pdfs)}] Procesando: {pdf_path.name}")

        texto = extraer_texto_pdf(pdf_path)
        if not texto or len(texto) < 100:
            print("  ✗ No se pudo extraer texto suficiente")
            continue

        print(f"  Texto extraído: {len(texto)} chars")

        # Decidir tipo de documento
        if es_sesion_completa(texto):
            print("  Tipo detectado: SESIÓN COMPLETA")
            nuevos = procesar_como_sesion(texto, pdf_path, args.ollama, args.model)
        else:
            print("  Tipo detectado: COLECCIÓN DE EJERCICIOS")
            nuevos = procesar_como_ejercicios(texto, pdf_path, args.ollama, args.model)

        print(f"  ✓ {len(nuevos)} ejemplos generados")
        todos_ejemplos.extend(nuevos)
        time.sleep(0.5)

    # Guardar
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for ej in todos_ejemplos:
            f.write(json.dumps(ej, ensure_ascii=False) + "\n")

    # Resumen por tipo
    por_tipo = {}
    for ej in todos_ejemplos:
        t = ej["task"]
        por_tipo[t] = por_tipo.get(t, 0) + 1

    print(f"\n{'='*50}")
    print(f"✅ Indexación completada")
    print(f"   Total ejemplos: {len(todos_ejemplos)}")
    for tipo, n in por_tipo.items():
        print(f"   · {tipo}: {n}")
    print(f"   Guardado en: {OUTPUT_FILE}")
    print(f"\nPróximo paso — generar dataset completo (sintético + PDFs):")
    print(f"  python tools/generar_dataset.py --incluir-pdfs")


if __name__ == "__main__":
    main()
