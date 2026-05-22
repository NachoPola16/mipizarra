#!/usr/bin/env python3
"""
Genera el dataset de entrenamiento para el fine-tuning del modelo de baloncesto.

Produce ejemplos para 3 tareas:
  1. Generación de sesiones de entrenamiento (texto largo)
  2. Generación de coordenadas de diagramas (JSON)
  3. Estructuración de ejercicios desde descripción (JSON)

Uso:
  python tools/generar_dataset.py --todo              # usa el profesor por defecto (qwen2.5:7b)
  python tools/generar_dataset.py --model qwen2.5:14b-instruct-q4_K_M --todo  # mejor calidad, más lento
  python tools/generar_dataset.py --solo-estructura   # esqueleto sin llamar al LLM
"""
import hashlib
import json
import random
import argparse
import requests
import time
from pathlib import Path

random.seed(42)

EXERCISES_PATH = Path("data/exercises.json")
OUTPUT_DIR     = Path("data/dataset")
OUTPUT_FILE    = OUTPUT_DIR / "train.jsonl"
REVIEW_FILE    = OUTPUT_DIR / "para_revisar.jsonl"

SYSTEM_SESION = (
    "Eres MiPizarra, un asistente experto en entrenamiento de baloncesto. "
    "Diseñas sesiones de entrenamiento estructuradas, prácticas y adaptadas a cada categoría. "
    "Usas terminología técnica española (codo, cabecera, TL, baseline, poste alto/bajo). "
    "Siempre propones ejercicios concretos con posiciones claras."
)

SYSTEM_DIAGRAMA = (
    "Eres un asistente experto en diagramas de baloncesto. "
    "Conviertes descripciones de ejercicios en coordenadas JSON precisas. "
    "Sistema de coordenadas (media pista, normalizado 0-100): "
    "X=0 lateral izquierdo, X=100 lateral derecho, X=50 centro. "
    "Y=0 baseline (bajo el aro), Y=100 línea de medio campo. "
    "Posiciones canónicas: canasta (50,11); baseline centro (50,5); "
    "poste bajo derecho (38,18), poste bajo izquierdo (62,18); "
    "esquina triple derecha (6,22), esquina triple izquierda (94,22); "
    "poste alto derecho (38,36), poste alto izquierdo (62,36); "
    "codo TL derecho (35,41), codo TL izquierdo (65,41), línea TL centro (50,41); "
    "ala derecha (15,50), ala izquierda (85,50); "
    "45° derecho (25,50), 45° izquierdo (75,50); "
    "arco triple top (50,60); cabecera triple (50,65); "
    "centro medio campo (50,100). "
    "Roles ataque: A1 base, A2 escolta/alero, A3 alero, A4 ala-pívot, A5 pívot. "
    "Defensa: D1..D5 (mismo número que el atacante). "
    "Movimientos: 'desplazamiento' (de + a_pos), 'pase' (de + a id), 'tiro' (de), "
    "'bloqueo' (de + a_pos). Todos con campo 'orden'."
)

SYSTEM_EJERCICIO = (
    "Eres un asistente experto en baloncesto. "
    "Estructuras ejercicios de baloncesto en formato JSON con todos sus campos: "
    "nombre, categoria, subcategoria, edades, duracion_min, intensidad (1-5), "
    "carga_cognitiva (1-5), objetivos (tacticos, tecnicos, fisicos) y diagrama si aplica."
)

EDADES       = ["U8", "U10", "U12", "U14", "U16", "U18", "U20"]
CATEGORIAS   = ["Prebenjamín", "Benjamín", "Alevín", "Infantil", "Cadete", "Junior", "Senior"]
OBJETIVOS    = [
    "defensa", "ataque", "tiro", "pase", "bote", "bloqueo directo",
    "transición ofensiva", "transición defensiva", "juego interior",
    "tiro exterior", "presión", "1 contra 1", "2 contra 2", "contraataque"
]
DURACIONES   = [45, 60, 75, 90, 105, 120]

EDAD_A_CAT = dict(zip(EDADES, CATEGORIAS))


def llamar_ollama(ollama_url: str, model: str, messages: list, max_tokens: int = 1500) -> str:
    """Llama a Ollama en formato chat."""
    try:
        r = requests.post(
            f"{ollama_url}/api/chat",
            json={
                "model":    model,
                "messages": messages,
                "stream":   False,
                "options":  {"temperature": 0.5, "num_predict": max_tokens, "num_ctx": 4096},
            },
            timeout=180,
        )
        r.raise_for_status()
        return r.json()["message"]["content"].strip()
    except Exception as e:
        print(f"  ✗ Error Ollama: {e}")
        return ""


def cargar_ejercicios() -> list:
    with open(EXERCISES_PATH, encoding="utf-8") as f:
        return json.load(f)


def ejercicios_para_edad(ejercicios: list, edad: str, objetivo: str, n: int = 8) -> list:
    cat = EDAD_A_CAT.get(edad, edad)
    palabras = objetivo.lower().split()
    sel = []
    for ej in ejercicios:
        edades_ej = ej.get("edades", [])
        if edad not in edades_ej and cat not in edades_ej:
            continue
        tags  = " ".join(ej.get("objetivos", {}).get("tacticos", []))
        texto = f"{ej['nombre']} {ej.get('descripcion', '')} {tags}".lower()
        if any(p in texto for p in palabras):
            sel.append(ej)
    if not sel:
        sel = [e for e in ejercicios if edad in e.get("edades", []) or cat in e.get("edades", [])]
    random.shuffle(sel)
    return sel[:n]


def construir_lista_ejercicios(ejercicios: list) -> str:
    lineas = ["EJERCICIOS DISPONIBLES:"]
    for ej in ejercicios:
        tags = ", ".join(ej.get("objetivos", {}).get("tacticos", []))
        desc = ej.get("descripcion", "")[:100]
        lineas.append(
            f"- {ej['nombre']} ({ej['duracion_min']} min, intensidad {ej['intensidad']}/5): {tags}. {desc}"
        )
    return "\n".join(lineas)


# ─── Tarea 1: Generación de sesiones ────────────────────────────────────────
def generar_ejemplo_sesion(ejercicios: list, edad: str, duracion: int, objetivo: str,
                           ollama_url: str, model: str) -> dict | None:
    relevantes = ejercicios_para_edad(ejercicios, edad, objetivo, n=8)
    if not relevantes:
        return None

    lista = construir_lista_ejercicios(relevantes)
    cat   = EDAD_A_CAT.get(edad, edad)

    descanso = "**DESCANSO (3 min)** después de cada 25-30 minutos" if duracion >= 60 else "**DESCANSO (3 min)** a mitad de la parte principal"

    user_prompt = f"Genera una sesión de entrenamiento de baloncesto.\n\nCategoría: {cat} ({edad})\nDuración: {duracion} min\nObjetivo: {objetivo}\n\n{lista}\n\nESTRUCTURA:\n**CALENTAMIENTO (15 min)**\n**PARTE PRINCIPAL**\nEjercicio 1: ...\nEjercicio 2: ...\n{descanso}\nEjercicio 3: ...\n**VUELTA A LA CALMA (8 min)**\n**Fundamentos trabajados**\n\nUsa nombres EXACTOS de los ejercicios. Posiciones concretas (codo TL, esquina, cabecera). Responde solo texto."

    assistant_response = llamar_ollama(
        ollama_url, model,
        [
            {"role": "system",    "content": SYSTEM_SESION},
            {"role": "user",      "content": user_prompt},
        ],
        max_tokens=1500,
    )

    if not assistant_response or len(assistant_response) < 200:
        return None

    return {
        "task":          "sesion",
        "conversations": [
            {"role": "system",    "content": SYSTEM_SESION},
            {"role": "user",      "content": user_prompt},
            {"role": "assistant", "content": assistant_response},
        ],
        "meta": {"edad": edad, "duracion": duracion, "objetivo": objetivo},
    }


# ─── Tarea 2: Generación de diagramas ───────────────────────────────────────
EJERCICIOS_CON_POSICIONES = [
    # ── Bloqueos directos ────────────────────────────────────────────────────
    ("Bloqueo directo central base-pivot", "A1 base en cabecera con balón. A2 pivot sube desde poste bajo derecho a poner bloqueo directo al base. A1 lee el bloqueo y decide: continuar al codo TL derecho o pasar a A2 que rola a canasta."),
    ("Bloqueo directo lateral", "A1 base en 45 derecho con balón. A2 pivot sube desde poste bajo a poner bloqueo lateral. A1 bota hacia el centro buscando codo, A2 rola por línea de fondo."),
    ("Pick and pop", "A1 base en cabecera. A2 ala-pívot sube a poner bloqueo. Tras el bloqueo, A2 sale (pops) a la línea de tiros libres en lugar de rolar. A1 puede tirar, penetrar o pasar a A2 en poste alto."),
    ("Rechazo de bloqueo", "A1 base en cabecera con balón. A2 sube a poner bloqueo desde la derecha. A1 rechaza el bloqueo y va al lado izquierdo (45 izquierdo) en bote, dejando al defensor descolocado."),
    # ── Bloqueos indirectos ──────────────────────────────────────────────────
    ("Bloqueo ciego flare", "A1 base en cabecera. A2 alero en 45 derecho. A3 pivot sube de poste bajo a poner bloqueo ciego a A2. A2 sale al ala derecha y recibe pase de A1 para tiro abierto."),
    ("Pin down desde poste bajo", "A2 alero en esquina derecha. A3 pivot en poste bajo derecho sube a poner pin down a A2. A2 sube al codo TL derecho a recibir pase de A1 en cabecera y tirar."),
    # ── Cortes sin balón ─────────────────────────────────────────────────────
    ("Corte en V desde esquina", "A2 alero en esquina derecha hace corte en V: baja a baseline y sube al 45 derecho para recibir pase de A1 base en cabecera. Tras recibir, tira o entra."),
    ("Backdoor desde 45", "A2 alero en 45 izquierdo. Hace amago hacia A1 base en cabecera, su defensor sobrerreacciona. A2 corta backdoor a canasta por línea de fondo, A1 le hace lob."),
    ("UCLA cut", "A1 base en cabecera pasa a A2 alero en 45 derecho. A3 pivot en poste alto izquierdo. A1 corta a canasta usando a A3 como bloqueo. A2 lee y pasa o tira."),
    ("Recorte desde esquina a canasta", "A2 alero en esquina izquierda. Amaga hacia el poste y corta directo a canasta por línea de fondo para recibir lob de A1 base en cabecera."),
    # ── Tiros con dinámica ───────────────────────────────────────────────────
    ("Tiro desde codo tras pase", "A1 base con balón en cabecera. A2 sale del poste alto izquierdo al codo TL derecho. A1 le pasa y A2 tira de media distancia desde el codo."),
    ("Triple desde esquina tras circulación", "A1 base en cabecera, A2 alero en 45 derecho, A3 alero en esquina izquierda. A1 pasa a A2, A2 reversa a A1, A1 pasa skip a A3 en esquina para triple abierto."),
    ("Tiro de cabecera tras bote", "A1 base recibe en medio campo derecha, bota hacia el centro hasta cabecera y tira de triple. Trabaja la mecánica con desplazamiento previo."),
    ("Bandeja en carrera desde 45", "A1 en 45 izquierdo bota hacia línea de fondo, entra por debajo del aro y bandeja por el lado contrario protegiendo el balón."),
    # ── Penetración y 1c1 ────────────────────────────────────────────────────
    ("1c1 desde codo TL", "A1 recibe pase del entrenador en codo TL derecho. D1 sale desde el aro a defender. A1 decide: tiro inmediato, salida en bote a canasta o salida atrás para tirar."),
    ("Drive and kick", "A1 base en cabecera con balón. A2 alero en esquina derecha. A1 penetra a canasta forzando ayuda, cuando viene la ayuda pasa a A2 que sube a 45 derecho para triple."),
    ("1c1 con bote desde 45", "A1 en 45 derecho con balón, D1 defendiendo en posición básica. A1 hace cambio de mano por delante y entra a canasta por línea de fondo."),
    # ── Juego interior ───────────────────────────────────────────────────────
    ("Pivot en poste bajo con giro de poder", "A2 pivot en poste bajo derecho. A1 base en cabecera. A1 pasa a A2 en poste bajo. A2 gira hacia canasta (giro de poder) y tira o pasa al alero A3 que recorta desde el 45 derecho."),
    ("Doble poste bajo", "A4 ala-pívot en poste bajo derecho, A5 pivot en poste bajo izquierdo. A1 base pasa a A4. A5 corta por baseline a poste bajo derecho liberando espacio. A4 puede tirar o pasar a A5."),
    # ── Ventaja numérica ─────────────────────────────────────────────────────
    ("2 contra 1 contraataque", "A1 y A2 salen de medio campo en contraataque. D1 defiende solo en zona de TL. A1 bota hacia el centro fijando al defensor, pasa a A2 en el lado libre para bandeja."),
    ("3 contra 2 contraataque", "A1 base centro, A2 alero derecha, A3 alero izquierda salen de medio campo. D1 y D2 defienden en triángulo (uno en TL, otro en aro). A1 ataca al primer defensor y reparte."),
    ("4 contra 3 con kick out", "Cuatro atacantes salen en contraataque contra tres defensores. A1 ataca, fija defensa, kick out a esquina para triple o continuación."),
    # ── Rotaciones / juego de equipo ─────────────────────────────────────────
    ("3 contra 0 con rotaciones", "A1 en cabecera, A2 en 45 derecho, A3 en 45 izquierdo. A1 pasa a A2, A1 corta a canasta, A3 sube a cabecera. A2 decide: tira, pasa a A1 en corte o reversa a A3."),
    ("Reversas en triángulo", "A1 en cabecera, A2 en 45 derecho, A3 en 45 izquierdo. Pase en triángulo: A1 a A2, A2 reversa a A1, A1 a A3. Trabajar pases precisos sin oposición."),
    ("Pase y corte continuo", "A1 base pasa a A2 en 45 derecho, A1 corta por la línea TL hasta esquina derecha. A2 reversa a A3 que sube de poste bajo a cabecera. Rotación continua de pase y corte."),
    # ── Defensa ──────────────────────────────────────────────────────────────
    ("Defensa del bloqueo directo 2c2", "A1 con balón en cabecera, A2 pivot pone bloqueo directo. D1 lucha por pasar por delante, D2 (defensor del bloqueador) decide saltar y presionar o hundir."),
    ("Cierre defensivo desde esquina", "A1 ataca desde 45 derecho. A2 atacante espera en esquina derecha. D1 defiende a A1, D2 defiende a A2. Si A1 penetra, D2 hace ayuda y se cierra el lado débil; D1 rota a A2 al kick out."),
    ("Defensa 1c1 desde codo", "A1 atacante recibe en codo TL derecho con balón. D1 defiende presionando lateral hacia la línea de fondo. Trabajar pies activos y manos arriba."),
]

def generar_ejemplo_diagrama(ej_nombre: str, ej_desc: str,
                              ollama_url: str, model: str) -> dict | None:
    user_prompt = f"Genera las coordenadas JSON del diagrama para este ejercicio de baloncesto.\n\nEjercicio: {ej_nombre}\nDescripción: {ej_desc}\n\nDevuelve SOLO el JSON con los campos: tipo, jugadores_ataque, jugadores_defensa, balon_inicio, movimientos (con campo orden), conos."

    response = llamar_ollama(
        ollama_url, model,
        [
            {"role": "system",    "content": SYSTEM_DIAGRAMA},
            {"role": "user",      "content": user_prompt},
        ],
        max_tokens=600,
    )

    if not response:
        return None

    # Limpiar markdown
    if "```json" in response:
        response = response.split("```json")[1].split("```")[0].strip()
    elif "```" in response:
        response = response.split("```")[1].split("```")[0].strip()

    try:
        json.loads(response)  # Validar que es JSON
    except json.JSONDecodeError:
        print(f"  ✗ JSON inválido para '{ej_nombre}'")
        return None

    return {
        "task":          "diagrama",
        "conversations": [
            {"role": "system",    "content": SYSTEM_DIAGRAMA},
            {"role": "user",      "content": user_prompt},
            {"role": "assistant", "content": response},
        ],
        "meta": {"nombre": ej_nombre},
    }


# ─── Tarea 3: Estructuración de ejercicios ──────────────────────────────────
DESCRIPCIONES_EJERCICIOS = [
    "Ejercicio de tiro desde esquinas para cadetes. Los jugadores rotan por esquina derecha e izquierda tirando de triple. 5 minutos, intensidad media.",
    "Juego de pillar con balón para prebenjamines. Todos botan en media pista, hay 2 pilladoras que intentan robar el balón. Alta intensidad, 8 minutos.",
    "Ejercicio de pase y recepción en movimiento para infantiles. Dos filas se pasan el balón mientras avanzan hacia canasta. Bandeja final. 10 minutos.",
    "1 contra 1 desde poste alto para cadetes y juniors. El defensor sale del aro, el atacante recibe en el codo y decide. Alta carga cognitiva y física.",
    "Ejercicio de defensa de bloqueo directo para seniors. 2 contra 2 con bloqueo obligatorio. El defensor del bloqueador decide saltar o hundir.",
    "Circuito de bote para alevines: zigzag entre conos, cambio de mano en el codo, entrada a canasta. 15 minutos, alta intensidad física.",
    "Tiro libre con consecuencia para infantiles y cadetes. Por parejas: si fallas el tiro libre, tu pareja hace 5 flexiones. Mejora la concentración bajo presión.",
    "Juego reducido 3 contra 3 en media pista para todas las categorías. 5 minutos por set, rotación automática de equipos.",
    "Ejercicio de contraataque 2 contra 1 para infantiles. Salida desde medio campo, defensor único en zona de TL, finalizar con bandeja o tiro corto. 10 minutos, intensidad alta.",
    "Pase de béisbol largo para juniors. Por parejas a lo largo de la pista, trabajar la potencia y la precisión del pase de salida tras rebote. 7 minutos.",
    "Rebote defensivo con bloqueo para cadetes. El entrenador tira y los defensores bloquean a los atacantes antes de coger el rebote. 8 minutos, alta intensidad física.",
    "Ejercicio de pies defensivos para benjamines. Filas en baseline, desplazamiento lateral hasta línea de fondo, sprint a baseline contraria. 5 minutos, calentamiento.",
    "Juego de transición ofensiva 3 contra 2 para cadetes. Tres atacantes salen contra dos defensores, deben decidir entre bandeja, tiro corto o pase a esquina. 12 minutos.",
    "Trabajo de pivot bajo poste con balón para juniors. Recibir, fijar al defensor con el cuerpo, decidir entre giro de poder, gancho o pase al alero que recorta. 10 minutos.",
    "Ejercicio de tiro tras autopase para infantiles y cadetes. El jugador hace pase al suelo hacia el codo, recoge el bote y tira. Trabajar mecánica fluida. 6 minutos.",
    "Defensa de corte backdoor para seniors. Atacante en 45, defensor en negación. Cuando atacante hace amago de salir, corta a canasta. Defensor reacciona. 8 minutos.",
]

def generar_ejemplo_ejercicio(descripcion: str, ollama_url: str, model: str) -> dict | None:
    user_prompt = f"Estructura este ejercicio de baloncesto en formato JSON.\n\nDescripción:\n\"{descripcion}\"\n\nDevuelve SOLO el JSON con: nombre, categoria, subcategoria, edades, duracion_min, intensidad (1-5), carga_cognitiva (1-5), objetivos (tacticos/tecnicos/fisicos), diagrama (null si no hay posiciones concretas)."

    response = llamar_ollama(
        ollama_url, model,
        [
            {"role": "system",    "content": SYSTEM_EJERCICIO},
            {"role": "user",      "content": user_prompt},
        ],
        max_tokens=700,
    )

    if not response:
        return None

    if "```json" in response:
        response = response.split("```json")[1].split("```")[0].strip()
    elif "```" in response:
        response = response.split("```")[1].split("```")[0].strip()

    try:
        json.loads(response)
    except json.JSONDecodeError:
        print(f"  ✗ JSON inválido para ejercicio")
        return None

    return {
        "task":          "ejercicio",
        "conversations": [
            {"role": "system",    "content": SYSTEM_EJERCICIO},
            {"role": "user",      "content": user_prompt},
            {"role": "assistant", "content": response},
        ],
        "meta": {"descripcion": descripcion[:60]},
    }


# ─── Main ────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Genera dataset para fine-tuning de MiPizarra")
    parser.add_argument("--ollama",         default="http://192.168.1.72:11434", help="URL de Ollama")
    parser.add_argument("--model",          default="qwen2.5:7b-instruct-q4_K_M",
                        help="Modelo Ollama 'profesor' que destila ejemplos. Recomendado: 7B+ para calidad.")
    parser.add_argument("--sesiones",       type=int, default=60,               help="Número de ejemplos de sesión")
    parser.add_argument("--diagramas",      type=int, default=20,               help="Número de ejemplos de diagrama")
    parser.add_argument("--ejercicios-json",type=int, default=15,               help="Número de ejemplos de estructuración")
    parser.add_argument("--solo-estructura",action="store_true",                help="Solo crear estructura sin llamar al LLM")
    parser.add_argument("--incluir-pdfs",        action="store_true", help="Fusionar con data/dataset/from_pdfs.jsonl")
    parser.add_argument("--incluir-conocimiento", action="store_true", help="Fusionar con data/dataset/from_conocimiento.jsonl")
    parser.add_argument("--incluir-web",          action="store_true", help="Fusionar con data/dataset/from_web.jsonl")
    parser.add_argument("--todo",                 action="store_true", help="Fusionar todas las fuentes disponibles")
    parser.add_argument("--seed",                 type=int, default=42,
                        help="Semilla aleatoria para reproducibilidad (combos de edad/duración/objetivo)")
    args = parser.parse_args()

    random.seed(args.seed)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ejercicios = cargar_ejercicios()
    print(f"Ejercicios cargados: {len(ejercicios)}")

    todos_ejemplos = []
    errores = 0

    # ── Sesiones ──────────────────────────────────────────────────────────────
    print(f"\n── Generando {args.sesiones} ejemplos de SESIÓN ──")
    combos = []
    for _ in range(args.sesiones):
        edad     = random.choice(EDADES)
        duracion = random.choice(DURACIONES)
        objetivo = random.choice(OBJETIVOS)
        combos.append((edad, duracion, objetivo))

    for i, (edad, duracion, objetivo) in enumerate(combos, 1):
        print(f"  [{i}/{args.sesiones}] {EDAD_A_CAT[edad]} · {duracion}min · {objetivo} ... ", end="", flush=True)
        if args.solo_estructura:
            print("(skip)")
            continue
        ej = generar_ejemplo_sesion(ejercicios, edad, duracion, objetivo, args.ollama, args.model)
        if ej:
            todos_ejemplos.append(ej)
            print(f"✓ ({len(ej['conversations'][2]['content'])} chars)")
        else:
            errores += 1
            print("✗")
        time.sleep(0.5)

    # ── Diagramas ─────────────────────────────────────────────────────────────
    n_diag = min(args.diagramas, len(EJERCICIOS_CON_POSICIONES))
    if n_diag < args.diagramas:
        print(f"\n⚠ Solo hay {len(EJERCICIOS_CON_POSICIONES)} patrones únicos de diagrama; "
              f"se piden {args.diagramas} pero se generarán {n_diag} sin repetir.")
    print(f"\n── Generando {n_diag} ejemplos de DIAGRAMA (sin reemplazo) ──")
    muestra = random.sample(EJERCICIOS_CON_POSICIONES, n_diag)
    for i, (nombre, desc) in enumerate(muestra, 1):
        print(f"  [{i}/{args.diagramas}] {nombre} ... ", end="", flush=True)
        if args.solo_estructura:
            print("(skip)")
            continue
        ej = generar_ejemplo_diagrama(nombre, desc, args.ollama, args.model)
        if ej:
            todos_ejemplos.append(ej)
            print("✓")
        else:
            errores += 1
            print("✗")
        time.sleep(0.3)

    # ── Ejercicios JSON ───────────────────────────────────────────────────────
    n_ejs = min(args.ejercicios_json, len(DESCRIPCIONES_EJERCICIOS))
    if n_ejs < args.ejercicios_json:
        print(f"\n⚠ Solo hay {len(DESCRIPCIONES_EJERCICIOS)} descripciones únicas; "
              f"se piden {args.ejercicios_json} pero se generarán {n_ejs} sin repetir.")
    print(f"\n── Generando {n_ejs} ejemplos de ESTRUCTURACIÓN (sin reemplazo) ──")
    muestra2 = random.sample(DESCRIPCIONES_EJERCICIOS, n_ejs)
    for i, desc in enumerate(muestra2, 1):
        print(f"  [{i}/{args.ejercicios_json}] {desc[:50]}... ", end="", flush=True)
        if args.solo_estructura:
            print("(skip)")
            continue
        ej = generar_ejemplo_ejercicio(desc, args.ollama, args.model)
        if ej:
            todos_ejemplos.append(ej)
            print("✓")
        else:
            errores += 1
            print("✗")
        time.sleep(0.3)

    # ── Fusionar fuentes adicionales ──────────────────────────────────────────
    fuentes_extra = {
        "from_pdfs.jsonl":        (args.incluir_pdfs        or args.todo, "python tools/indexar_entrenamientos.py"),
        "from_conocimiento.jsonl":(args.incluir_conocimiento or args.todo, "python tools/indexar_conocimiento.py"),
        "from_web.jsonl":         (args.incluir_web          or args.todo, "python tools/scraper_isportcoach.py"),
    }
    for filename, (activado, cmd_previo) in fuentes_extra.items():
        extra_file = OUTPUT_DIR / filename
        if activado and extra_file.exists():
            antes = len(todos_ejemplos)
            with open(extra_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        todos_ejemplos.append(json.loads(line))
            print(f"\n── Fusionado {filename}: +{len(todos_ejemplos)-antes} ejemplos")
        elif activado:
            print(f"\n⚠ No se encontró {extra_file}")
            print(f"  Ejecuta primero: {cmd_previo}")

    # ── Deduplicar (por hash de la respuesta del assistant) ───────────────────
    n_antes = len(todos_ejemplos)
    vistos = set()
    unicos = []
    for ej in todos_ejemplos:
        try:
            assistant_text = next(
                m["content"] for m in ej["conversations"] if m["role"] == "assistant"
            )
        except (StopIteration, KeyError):
            continue
        h = hashlib.sha256(assistant_text.strip().encode("utf-8")).hexdigest()
        if h not in vistos:
            vistos.add(h)
            unicos.append(ej)
    todos_ejemplos = unicos
    duplicados = n_antes - len(todos_ejemplos)
    if duplicados:
        print(f"\n🗑  Deduplicados: {duplicados} ejemplos repetidos eliminados")

    # ── Guardar ───────────────────────────────────────────────────────────────
    random.shuffle(todos_ejemplos)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for ej in todos_ejemplos:
            f.write(json.dumps(ej, ensure_ascii=False) + "\n")

    with open(REVIEW_FILE, "w", encoding="utf-8") as f:
        for ej in todos_ejemplos:
            f.write(json.dumps(ej, ensure_ascii=False, indent=2) + "\n---\n")

    por_tipo = {}
    for ej in todos_ejemplos:
        t = ej.get("task", "?")
        por_tipo[t] = por_tipo.get(t, 0) + 1

    print(f"\n{'='*50}")
    print(f"✅ Dataset generado: {len(todos_ejemplos)} ejemplos únicos")
    for tipo, n in por_tipo.items():
        print(f"   · {tipo}: {n}")
    print(f"✗  Errores síntéticos: {errores}")
    print(f"📄 JSONL listo para fine-tuning: {OUTPUT_FILE}")
    print(f"📋 Para revisar manualmente: {REVIEW_FILE}")
    print(f"\nPróximo paso:")
    print(f"  python tools/finetune_qwen.py --dataset {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
