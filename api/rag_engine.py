# api/rag_engine.py
import json
import os
import logging
import requests
import chromadb
from llama_index.embeddings.ollama import OllamaEmbedding
from prompts import SYSTEM_SESION, SYSTEM_EJERCICIO, SYSTEM_DIAGRAMA, SYSTEM_REGLAMENTO  # noqa: F401

# Mapeo de códigos UXX a nombres de categorías
EDAD_A_CATEGORIA = {
    "U8": "Prebenjamín",
    "U10": "Benjamín",
    "U12": "Alevín",
    "U14": "Infantil",
    "U16": "Cadete",
    "U18": "Junior",
    "U20": "Senior",
    "Senior": "Senior"
}

logger = logging.getLogger(__name__)

OLLAMA_URL     = os.environ.get("OLLAMA_URL", "http://ollama:11434")
MODEL          = os.environ.get("OLLAMA_MODEL", "qwen3:4b")
# Modelo para generar_sesion(): texto libre largo y estructurado. qwen3:4b filtra
# razonamiento en inglés dentro del propio texto (no solo como preámbulo) y el
# parámetro "think": False no lo evita de forma fiable. qwen2.5-instruct no tiene
# modo thinking, así que no puede colarse ningún razonamiento.
MODEL_SESION   = os.environ.get("OLLAMA_MODEL_SESION", "qwen2.5:7b-instruct-q4_K_M")
EXERCISES_PATH = os.environ.get("EXERCISES_PATH", "/app/data/exercises.json")
CHROMA_DB_DIR  = os.environ.get("CHROMA_DB_DIR", "/app/data/chroma_db")
EMBED_MODEL    = "nomic-embed-text"

# Inicialización única al arrancar el módulo
_embed_model = OllamaEmbedding(model_name=EMBED_MODEL, base_url=OLLAMA_URL)
_chroma      = chromadb.PersistentClient(path=CHROMA_DB_DIR)


# ─── Ejercicios ──────────────────────────────────────────────────────────

# Fundamentos analíticos relacionados con cada tipo de objetivo.
# Sirven para seleccionar ejercicios de fase analítica (ejercicio 1)
# aunque no sean directamente del objetivo principal.
COMPONENTES_ANALITICOS = {
    "contraataque":      ["pase", "rebote", "transición", "salida", "carrera"],
    "transición":        ["pase", "rebote", "salida", "carrera"],
    "tiro":              ["tiro", "recepción", "desmarque", "corte", "movimiento"],
    "defensa":           ["posición", "ayuda", "rebote", "deslizamiento", "cierre"],
    "bloqueo":           ["bloqueo", "lectura", "pase"],
    "ataque posicional": ["pase", "corte", "espaciado", "movimiento"],
    "1c1":               ["bote", "tiro", "finalizacion", "entrada", "penetración"],
    "pase":              ["pase", "recepción", "movimiento", "corte"],
    "rebote":            ["rebote", "posición", "salida"],
}


def cargar_ejercicios() -> list:
    with open(EXERCISES_PATH, encoding="utf-8") as f:
        return json.load(f)


def _palabras_objetivo(objetivo: str) -> tuple[list[str], list[str]]:
    """Devuelve (palabras_directas, palabras_componentes) para un objetivo."""
    palabras = objetivo.lower().split()
    componentes = []
    for clave, fundamentos in COMPONENTES_ANALITICOS.items():
        if any(p in clave for p in palabras) or any(clave in p for p in palabras):
            componentes.extend(fundamentos)
    return palabras, list(set(componentes))


def filtrar_ejercicios(ejercicios: list, edad: str, objetivo: str) -> list:
    categoria = EDAD_A_CATEGORIA.get(edad, edad)
    palabras_obj, palabras_comp = _palabras_objetivo(objetivo)

    def en_categoria(ej):
        edades_ej = ej.get("edades", [])
        return edad in edades_ej or categoria in edades_ej

    def texto_ej(ej):
        tags = " ".join(ej.get("objetivos", {}).get("tacticos", []))
        return f"{ej['nombre']} {ej.get('descripcion', '')} {tags}".lower()

    directos, analiticos, resto = [], [], []
    for ej in ejercicios:
        if not en_categoria(ej):
            continue
        txt = texto_ej(ej)
        if any(p in txt for p in palabras_obj):
            directos.append(ej)
        elif palabras_comp and any(p in txt for p in palabras_comp):
            analiticos.append(ej)
        else:
            resto.append(ej)

    # Fallback: si no hay directos, usar toda la categoría
    if not directos:
        directos = analiticos + resto
        analiticos = []

    def score(ej, palabras):
        txt = texto_ej(ej)
        coincidencias = sum(1 for p in palabras if p in txt)
        tiene_diagrama = 10 if "diagrama" in ej else 0
        return tiene_diagrama + coincidencias

    directos   = sorted(directos,   key=lambda e: score(e, palabras_obj),  reverse=True)
    analiticos = sorted(analiticos, key=lambda e: score(e, palabras_comp), reverse=True)[:4]

    # Marcar fase para que construir_contexto_ejercicios pueda etiquetarlos
    for ej in analiticos:
        ej["_fase"] = "ANALÍTICO"
    for ej in directos:
        ej["_fase"] = "OBJETIVO"

    # Devolver: analíticos primero (para fase 1), directos después (fases 2-3)
    return analiticos + directos


def _nivel_oposicion(ej: dict) -> int:
    """0=sin oposición, 1=reducida (ventaja numérica), 2=igualada (mismo nº ataque/defensa)"""
    import re as _re
    nombre = ej['nombre'].lower()
    # Extrae "AcB" o "A contra B" (con o sin espacios): ataque vs defensa
    m = _re.search(r'(\d)\s*c(?:ontra)?\s*(\d)', nombre)
    if m:
        ataque, defensa = int(m.group(1)), int(m.group(2))
        if defensa == 0:
            return 0
        return 2 if ataque == defensa else 1
    return 0 if ej.get('_fase') == 'ANALÍTICO' else 1


def seleccionar_tres_ejercicios(relevantes: list) -> tuple:
    """Elige (ej1_analitico, ej2_reducida, ej3_aplicado) directamente en Python."""
    analiticos = [e for e in relevantes if e.get('_fase') == 'ANALÍTICO']
    directos   = [e for e in relevantes if e.get('_fase') == 'OBJETIVO']

    # Fallback: si no hay analíticos, usar el primer directo de nivel 0
    if not analiticos:
        analiticos = [e for e in directos if _nivel_oposicion(e) == 0] or directos[:1]

    ej1 = analiticos[0] if analiticos else None

    # Ejercicio 2: directo con oposición reducida (nivel 1), diferente al ej1
    candidatos_2 = sorted(
        [e for e in directos if e != ej1],
        key=lambda e: abs(_nivel_oposicion(e) - 1)
    )
    ej2 = candidatos_2[0] if candidatos_2 else None

    # Ejercicio 3: directo con mayor oposición (nivel 2 preferible), diferente a ej1 y ej2
    candidatos_3 = sorted(
        [e for e in directos if e != ej1 and e != ej2],
        key=lambda e: -_nivel_oposicion(e)
    )
    ej3 = candidatos_3[0] if candidatos_3 else None

    return ej1, ej2, ej3


def construir_contexto_ejercicios(ejercicios: list, max_ejs: int = 10) -> str:
    analiticos = [e for e in ejercicios if e.get("_fase") == "ANALÍTICO"]
    directos   = [e for e in ejercicios if e.get("_fase") != "ANALÍTICO"]

    con_diagrama = [e for e in directos if "diagrama" in e]
    sin_diagrama = [e for e in directos if "diagrama" not in e]
    resto_directos = con_diagrama[:2] + sin_diagrama
    n_directos = max(max_ejs - len(analiticos), 4)

    seleccion = analiticos + resto_directos[:n_directos]
    seleccion = seleccion[:max_ejs]

    lineas = ["EJERCICIOS DISPONIBLES (usa el nombre EXACTO):"]
    for ej in seleccion:
        tacticos  = ", ".join(ej.get("objetivos", {}).get("tacticos",  []))
        tecnicos  = ", ".join(ej.get("objetivos", {}).get("tecnicos",  []))
        fisicos   = ", ".join(ej.get("objetivos", {}).get("fisicos",   []))
        obj_str   = " | ".join(filter(None, [tacticos, tecnicos, fisicos]))
        desc = ej.get("descripcion", "")[:150]
        lineas.append(
            f"- \"{ej['nombre']}\" "
            f"({ej['duracion_min']} min, intensidad {ej['intensidad']}/5): "
            f"{obj_str}. {desc}"
        )
    return "\n".join(lineas)

# ─── ChromaDB / PDFs ─────────────────────────────────────────────────────
def consultar_coleccion(nombre: str, consulta: str, n_resultados: int = 4) -> str:
    try:
        coleccion = _chroma.get_collection(nombre)
    except Exception:
        return ""

    if coleccion.count() == 0:
        return ""

    try:
        embedding  = _embed_model.get_text_embedding(consulta)
        resultados = coleccion.query(
            query_embeddings=[embedding],
            n_results=min(n_resultados, coleccion.count()),
            include=["documents", "metadatas"],
        )
        fragmentos = resultados.get("documents", [[]])[0]
        fuentes    = [
            m.get("fuente", "?")
            for m in resultados.get("metadatas", [[]])[0]
        ]
        lineas = []
        for texto, fuente in zip(fragmentos, fuentes):
            lineas.append(f"[{fuente}] {texto.strip()}")
        return "\n".join(lineas)

    except Exception as e:
        logger.warning(f"Error consultando coleccion '{nombre}': {e}")
        return ""


def construir_contexto_teoria(objetivo: str, edad: str) -> str:
    consulta = f"entrenamiento baloncesto {objetivo} categoria {edad}"
    partes   = []
    mapeo    = {
        "teoria":        "TEORIA Y METODOLOGIA",
        "planificacion": "PLANIFICACION",
        "reglamento":    "REGLAMENTO",
    }
    for nombre, etiqueta in mapeo.items():
        fragmento = consultar_coleccion(nombre, consulta, n_resultados=4)
        if fragmento:
            partes.append(f"--- {etiqueta} ---\n{fragmento}")

    return "\n\n".join(partes) if partes else ""


# ─── Generación ──────────────────────────────────────────────────────────
VOCABULARIO_TECNICO = """\
TERMINOLOGÍA TÉCNICA (usa siempre en las descripciones):
- Zonas de pista: codo TL derecho/izquierdo, cabecera triple, esquina derecha/izquierda, baseline, poste alto, poste bajo, zona pintada, ala derecha/izquierda
- Bote: progresión (velocidad), protección (cuerpo entre balón y defensor), crossover, entre piernas, por detrás, bote de retroceso
- Tiro: suspensión, bandeja mano dominante/débil, entrada 1-2 con parada, floater, tiro de media distancia desde codo, tiro libre
- Pase: pecho, picado, béisbol, por encima (overhead), pase en movimiento, pase de salida tras rebote
- Defensa: posición básica (pies separados, rodillas flexionadas, manos activas), deslizamiento lateral, ayuda, rotación, negación, tapping, defensa al bloqueo directo (pasar por delante/detrás, cambio)
- Conceptos: bloqueo directo, caída hacia canasta, corte (en V, puerta atrás), penetración, 1vs1 con bote\
"""


def _eliminar_secciones_duplicadas(texto: str) -> str:
    """Si el modelo repite un 'Ejercicio N:' ya visto (rambling tras terminar la
    plantilla), elimina ese bloque duplicado hasta la siguiente sección válida."""
    import re as _re
    lineas = texto.split('\n')
    vistos = set()
    resultado = []
    saltando = False
    for linea in lineas:
        m = _re.match(r'Ejercicio\s+(\d+)\s*:', linea.strip())
        if m:
            num = m.group(1)
            if num in vistos:
                saltando = True
                continue
            vistos.add(num)
            saltando = False
        elif _re.match(r'(\*\*?VUELTA A LA CALMA|\*\*?Fundamentos|DESCANSO)', linea.strip(), _re.IGNORECASE):
            saltando = False
        if not saltando:
            resultado.append(linea)
    return '\n'.join(resultado)


def _desc_ej(ej: dict) -> str:
    """Línea corta de descripción para el prompt de sesión."""
    tacticos = ", ".join(ej.get("objetivos", {}).get("tacticos", [])[:3])
    desc = ej.get("descripcion", "")[:120]
    return f"{tacticos}. {desc}".strip(". ")


def generar_sesion(edad: str, duracion: int, objetivo: str) -> dict:
    import re

    ejercicios = cargar_ejercicios()
    relevantes = filtrar_ejercicios(ejercicios, edad, objetivo)
    ej1, ej2, ej3 = seleccionar_tres_ejercicios(relevantes)
    ctx_teoria  = construir_contexto_teoria(objetivo, edad)

    teoria_intro = ""
    if ctx_teoria:
        teoria_intro = f"CONTEXTO METODOLÓGICO:\n{ctx_teoria[:800]}\n\n"

    t_descanso = 3 if duracion >= 60 else 2
    descanso_texto = f"**DESCANSO ({t_descanso} min)**"

    t_calent = max(10, duracion // 6)
    t_vuelta = max(5, duracion // 15)
    t_parte  = duracion - t_calent - t_vuelta - t_descanso
    t_ej     = t_parte // 3
    categoria_nombre = EDAD_A_CATEGORIA.get(edad, edad)

    n1 = ej1['nombre'] if ej1 else "ejercicio analítico"
    n2 = ej2['nombre'] if ej2 else "ejercicio con superioridad"
    n3 = ej3['nombre'] if ej3 else "ejercicio aplicado"

    prompt = f"""Eres MiPizarra, asistente de entrenamiento de baloncesto.
Rellena la plantilla de abajo con contenido concreto. No añadas texto fuera de la plantilla.

CATEGORÍA: {categoria_nombre} ({edad}) | DURACIÓN: {duracion} min | OBJETIVO: {objetivo}

{teoria_intro}{VOCABULARIO_TECNICO}

EJERCICIOS DE LA SESIÓN (ya seleccionados — usa estos nombres exactos):
1. "{n1}" — sin oposición o defensa pasiva. {_desc_ej(ej1) if ej1 else ''}
2. "{n2}" — con superioridad numérica. {_desc_ej(ej2) if ej2 else ''}
3. "{n3}" — con oposición igualada. {_desc_ej(ej3) if ej3 else ''}

**CALENTAMIENTO ({t_calent} min)**
Juego:
Reglas:
Espacio:

**PARTE PRINCIPAL**

Ejercicio 1: {n1}
Duración: {t_ej} min
Organización:
Puntos clave:
-
-

Ejercicio 2: {n2}
Duración: {t_ej} min
Organización:
Puntos clave:
-
-

{descanso_texto}

Ejercicio 3: {n3}
Duración: {t_parte - 2*t_ej} min
Organización:
Puntos clave:
-
-

**VUELTA A LA CALMA ({t_vuelta} min)**
Juego:
Reglas:

**Fundamentos**: """

    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model":   MODEL_SESION,
                "prompt":  prompt,
                "stream":  False,
                "options": {
                    "temperature": 0.4,
                    "num_predict": 900,
                    "num_ctx":     6144,
                    "top_p":       0.9,
                    "min_p":       0.05,
                    "repeat_penalty": 1.2,
                    "stop": [
                        "```",
                        # Instrucciones (con o sin "CRÍTICAS", con o sin negrita)
                        "INSTRUCCIONES:", "INSTRUCCIONES CRÍTICAS", "**INSTRUCCIONES",
                        # Meta-comentarios del LLM
                        "Este es un texto", "Aquí tienes", "Aquí está",
                        "La respuesta completa", "A continuación",
                        # Secciones no deseadas
                        "IMPORTANTE:", "FORMATO:", "REGLAS:",
                        "{", "¿Cómo", "NOTA:", "En resumen",
                        "También es importante", "para ajustar este plan",
                        "**SESIÓN**",
                        # Ejercicios extra
                        "Ejercicio 4:", "Ejercicio 5:",
                    ],
                },
            },
            timeout=300,
        )
        response.raise_for_status()
        texto = response.json()["response"].strip()

        if texto.startswith("{") or texto.startswith("["):
            logger.warning("Modelo devolvió JSON en lugar de texto, reintentando...")
            raise ValueError("Respuesta en JSON no válida")

        # ── 0. Eliminar bloques <think>...</think> (Qwen3 con think no desactivado) ──
        texto = re.sub(r'<think>.*?</think>', '', texto, flags=re.DOTALL).strip()

        # ── 0b. Cortar razonamiento previo y encontrar el inicio real de la sesión ──
        # Busca el primer marcador estructural de la sesión (en cualquier orden)
        match_inicio = re.search(
            r'(\*\*CALENTAMIENTO|\*\*PARTE PRINCIPAL|^Ejercicio\s+1\s*:)',
            texto, re.MULTILINE
        )
        if match_inicio:
            texto = texto[match_inicio.start():]
        else:
            # Fallback: primera línea que comience una sección conocida
            lineas = texto.split('\n')
            primera_es = next(
                (i for i, l in enumerate(lineas)
                 if re.match(r'(Ejercicio\s+1|CALENTAMIENTO|\*\*CALENTAMIENTO|\*\*PARTE)', l.strip())),
                None
            )
            if primera_es:
                texto = '\n'.join(lineas[primera_es:]).strip()

        # ── 1. Limpiar preámbulos que el modelo añade antes de la sesión ──────
        preambles = ['"""', "'''", '""', "''"]
        for p in preambles:
            if texto.startswith(p):
                texto = texto[len(p):].lstrip()
        # Eliminar "Sesión:" o variantes en la primera línea
        primera_linea, *resto = texto.split('\n')
        if primera_linea.strip().rstrip(':') in ('Sesión', 'Sesion', 'SESIÓN', '"""', "'''"):
            texto = '\n'.join(resto).lstrip()

        # ── 2. Truncar en patrones que indican que el modelo se ha ido de madre ─
        truncar_en = [
            "INSTRUCCIONES CRÍTICAS", "**INSTRUCCIONES", "INSTRUCCIONES:",
            "IMPORTANTE:", "REGLAS:", "FORMATO:",
            "ESTRUCTURA OBLIGATORIA:", "REGLAS ABSOLUTAS:",
            "Este es un texto", "Aquí tienes", "Aquí está",
            "La respuesta completa", "A continuación te",
            "¿Cómo", "NOTA:", "En resumen,", "También es importante",
            "para ajustar este plan", "**SESIÓN**",
        ]
        for patron in truncar_en:
            if patron in texto:
                texto = texto.split(patron)[0].strip()

        # ── 3. Eliminar Ejercicio 4+ si se ha colado ──────────────────────────
        for patron_extra in ["\nEjercicio 4:", "\nEjercicio 5:"]:
            if patron_extra in texto:
                texto = texto.split(patron_extra)[0].strip()

        # ── 3b. Eliminar "Ejercicio 1/2/3" repetidos (rambling tras terminar) ──
        texto = _eliminar_secciones_duplicadas(texto)

        # ── 4. Truncar al final natural (tras Fundamentos) ────────────────────
        # Acepta: **Fundamentos**: texto | Fundamentos\ntexto | FUNDAMENTOS: texto
        match_fund = re.search(
            r'(?:\*\*)?(?:Fundamentos|FUNDAMENTOS)(?:\*\*)?:?\s*\n?[^\n]+',
            texto, re.IGNORECASE
        )
        if match_fund:
            texto = texto[:match_fund.end()].strip()
        else:
            for patron in ["¿Cómo", "NOTA:", "En resumen,", "También es importante",
                           "para ajustar este plan", "**SESIÓN**"]:
                if patron in texto:
                    texto = texto.split(patron)[0].strip()

    except Exception as e:
        logger.error(f"Error generando sesión: {e}")
        return {
            "texto": f"**Error generando sesión**: {str(e)}",
            "ejercicios_usados": [e for e in [ej1, ej2, ej3] if e],
            "teoria_usada": bool(ctx_teoria),
        }

    return {
        "texto":             texto,
        "ejercicios_usados": [e for e in [ej1, ej2, ej3] if e],
        "teoria_usada":      bool(ctx_teoria),
    }

def generar_diagrama_desde_texto(descripcion_ejercicio: str) -> dict | None:
    """Convierte una descripción textual en coordenadas JSON de diagrama."""
    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model":  MODEL,
                "think":  False,
                "format": "json",
                "stream": False,
                "messages": [
                    {"role": "system", "content": SYSTEM_DIAGRAMA},
                    {"role": "user",   "content": (
                        f"Genera las coordenadas JSON del diagrama para este ejercicio.\n\n"
                        f"DESCRIPCIÓN:\n{descripcion_ejercicio}\n\n"
                        "Devuelve SOLO el JSON con: tipo, jugadores_ataque, jugadores_defensa, "
                        "balon_inicio, movimientos (con orden), conos."
                    )},
                ],
                "options": {"temperature": 0.2, "num_predict": 600},
            },
            timeout=60,
        )
        response.raise_for_status()
        texto = response.json()["message"]["content"].strip()
        diagrama = json.loads(texto)
        return diagrama
        
    except Exception as e:
        logger.warning(f"Error generando diagrama: {e}")
        return None


# Función para generar coordenadas a partir de descripción y nombre
def generar_coordenadas_ejercicio(descripcion: str, nombre: str) -> dict | None:
    """Genera coordenadas precisas basadas en la descripción del ejercicio."""
    
    # Ejemplos más variados para que el modelo aprenda patrones
    ejemplos = [
        {
            "tipo": "media_pista",
            "jugadores_ataque": [
                {"id": "A1", "rol": "base", "x": 6, "y": 22},
                {"id": "A2", "rol": "ala", "x": 35, "y": 41},
                {"id": "A3", "rol": "alero", "x": 65, "y": 41},
                {"id": "A4", "rol": "pivot", "x": 94, "y": 22}
            ],
            "jugadores_defensa": [],
            "balon_inicio": {"portador": "A1"},
            "movimientos": [
                {"de": "A1", "a_pos": {"x": 35, "y": 41}, "tipo": "desplazamiento", "orden": 1},
                {"de": "A1", "tipo": "tiro", "orden": 2}
            ],
            "conos": [{"x": 25, "y": 50}, {"x": 75, "y": 50}]
        },
        {
            "tipo": "media_pista",
            "jugadores_ataque": [
                {"id": "A1", "rol": "base", "x": 50, "y": 65},
                {"id": "A2", "rol": "escolta", "x": 75, "y": 50}
            ],
            "jugadores_defensa": [
                {"id": "D1", "rol": "defensor", "x": 50, "y": 55}
            ],
            "balon_inicio": {"portador": "A1"},
            "movimientos": [
                {"de": "A1", "a": "A2", "tipo": "pase", "orden": 1},
                {"de": "A2", "tipo": "tiro", "orden": 2}
            ],
            "conos": []
        },
        {
            "tipo": "media_pista",
            "jugadores_ataque": [
                {"id": "A1", "rol": "base", "x": 50, "y": 65},
                {"id": "A2", "rol": "alero", "x": 78, "y": 50}
            ],
            "jugadores_defensa": [
                {"id": "D2", "rol": "defensor", "x": 74, "y": 43}
            ],
            "balon_inicio": {"portador": "A1"},
            "movimientos": [
                {"de": "A1", "a": "A2", "tipo": "pase", "orden": 1},
                {"de": "A2", "a_pos": {"x": 62, "y": 28}, "tipo": "bote", "curva": True, "orden": 2},
                {"de": "A2", "tipo": "tiro", "orden": 3}
            ],
            "conos": []
        }
    ]

    prompt = f"""Genera coordenadas JSON para este ejercicio de baloncesto.

EJERCICIO: {nombre}
DESCRIPCIÓN: {descripcion}

SISTEMA DE COORDENADAS (media pista, 0-100):
- X=0 lateral izquierdo, X=100 lateral derecho, X=50 centro
- Y=0 baseline (bajo el aro), Y=100 línea de medio campo

POSICIONES CANÓNICAS:
- Canasta: (50, 11)
- Baseline centro: (50, 5)
- Poste bajo derecho: (38, 18), poste bajo izquierdo: (62, 18)
- Esquina triple derecha: (6, 22), esquina triple izquierda: (94, 22)
- Poste alto derecho: (38, 36), poste alto izquierdo: (62, 36)
- Codo TL derecho: (35, 41), codo TL izquierdo: (65, 41), línea TL centro: (50, 41)
- Ala derecha: (15, 50), ala izquierda: (85, 50)
- 45° derecho: (25, 50), 45° izquierdo: (75, 50)
- Arco triple top: (50, 60)
- Cabecera triple: (50, 65)
- Centro medio campo: (50, 100)

TIPOS DE MOVIMIENTO:
- desplazamiento: jugador se mueve SIN balón (de + a_pos). Línea continua.
- pase: jugador pasa el balón a otro (de + a id). Línea punteada.
- bote: jugador avanza BOTANDO (de + a_pos). Línea ondulada. Actualiza su posición.
- tiro: jugador lanza al aro (solo de). Flecha verde.
- bloqueo: jugador planta bloqueo en a_pos (de + a_pos). Línea roja + barra perpendicular.

Campo opcional "curva" (en cualquier movimiento): true o número de píxeles.
Usar "curva" cuando el jugador rodea a un defensor o el trayecto no es recto.

REGLAS CRÍTICAS:
1. jugadores_ataque = TODOS los jugadores atacantes/pasadores/tiradores (personas)
2. jugadores_defensa = TODOS los jugadores defensores (personas)
3. conos = SOLO pylons/conos físicos en el suelo para delimitar zonas, NO jugadores
4. Pon SIEMPRE al menos 2 jugadores_ataque (nunca dejes el ejercicio con 1 solo jugador)
5. Si la descripción menciona "esquinas y alas" → coloca jugadores en (6,22), (25,50), (75,50), (94,22)
6. Si dice "codo TL" → usa (35,41) o (65,41)
7. Si un jugador tira, añade movimiento tipo "tiro" desde ese jugador
8. Si hay pase, añade movimiento tipo "pase"
9. Si un jugador bota hacia delante, usa "bote" (no "desplazamiento")
10. Si el jugador rodea un defensor al botar, añade "curva": true al bote
11. NUNCA uses conos para representar jugadores en espera

EJEMPLOS:
{json.dumps(ejemplos[0], indent=2, ensure_ascii=False)}

{json.dumps(ejemplos[1], indent=2, ensure_ascii=False)}

Genera SOLO el JSON (sin explicaciones):"""

    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model":   MODEL,
                "prompt":  prompt,
                "format":  "json",
                "think":   False,          # Qwen3: sin thinking para JSON estructurado
                "stream":  False,
                "options": {
                    "temperature": 0.2,
                    "num_predict": 800,
                    "top_k": 40,
                },
            },
            timeout=120,
        )
        response.raise_for_status()
        texto = response.json()["response"]

        diagrama = json.loads(texto.strip())

        # Validación mínima
        if "jugadores_ataque" not in diagrama or len(diagrama.get("jugadores_ataque", [])) == 0:
            logger.warning(f"  ✗ Diagrama sin jugadores de ataque")
            return None
            
        logger.info(f"  ✓ Coordenadas generadas: {len(diagrama.get('jugadores_ataque', []))} atacantes, {len(diagrama.get('jugadores_defensa', []))} defensores")
        return diagrama

    except Exception as e:
        logger.warning(f"  ✗ Error generando coordenadas: {e}")
        return None


# ── Modo 2: Ejercicio único ──────────────────────────────────────────────────

# SYSTEM_EJERCICIO importado de api/prompts.py


def generar_ejercicio_unico(edad: str, objetivo: str, descripcion: str = "") -> dict:
    """Modo 2: genera un único ejercicio con diagrama."""
    ctx = construir_contexto_ejercicios(
        filtrar_ejercicios(cargar_ejercicios(), edad, objetivo)
    )
    prompt = (
        f"Genera un ejercicio de baloncesto para la categoría {edad} con objetivo: {objetivo}.\n"
        + (f"Descripción adicional: {descripcion}\n" if descripcion else "")
        + f"\nEjercicios de referencia:\n{ctx}\n\n"
        "Devuelve SOLO el JSON del ejercicio (sin texto adicional):"
    )
    try:
        r = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model":  MODEL,
                "prompt": prompt,
                "format": "json",
                "think":  False,          # Qwen3: sin thinking para JSON estructurado
                "stream": False,
                "options": {"temperature": 0.4, "num_predict": 900, "top_k": 40},
            },
            timeout=120,
        )
        r.raise_for_status()
        ej = json.loads(r.json()["response"].strip())
        logger.info(f"Ejercicio generado: {ej.get('nombre', '?')}")
        return ej
    except Exception as e:
        logger.warning(f"Error generando ejercicio: {e}")
        return {}


# ── Modo 3: Reglamento y dudas técnicas ─────────────────────────────────────

# SYSTEM_REGLAMENTO importado de api/prompts.py


def responder_duda_reglamento(pregunta: str) -> str:
    """Modo 3: responde una duda de reglamento o fundamento técnico."""
    try:
        r = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": MODEL,
                "think": False,
                "messages": [
                    {"role": "system", "content": SYSTEM_REGLAMENTO},
                    {"role": "user", "content": pregunta},
                ],
                "stream": False,
                "options": {"temperature": 0.3, "num_predict": 500, "num_ctx": 4096},
            },
            timeout=90,
        )
        r.raise_for_status()
        return r.json()["message"]["content"].strip()
    except Exception as e:
        logger.warning(f"Error en reglamento: {e}")
        return "No se pudo responder la consulta. Inténtalo de nuevo."
