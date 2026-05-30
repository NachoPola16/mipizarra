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
EXERCISES_PATH = os.environ.get("EXERCISES_PATH", "/app/data/exercises.json")
CHROMA_DB_DIR  = os.environ.get("CHROMA_DB_DIR", "/app/data/chroma_db")
EMBED_MODEL    = "nomic-embed-text"

# Inicialización única al arrancar el módulo
_embed_model = OllamaEmbedding(model_name=EMBED_MODEL, base_url=OLLAMA_URL)
_chroma      = chromadb.PersistentClient(path=CHROMA_DB_DIR)


# ─── Ejercicios ──────────────────────────────────────────────────────────
def cargar_ejercicios() -> list:
    with open(EXERCISES_PATH, encoding="utf-8") as f:
        return json.load(f)

def filtrar_ejercicios(ejercicios: list, edad: str, objetivo: str) -> list:
    # Convertir U16 → Cadete si es necesario
    categoria = EDAD_A_CATEGORIA.get(edad, edad)
    
    palabras = objetivo.lower().split()
    seleccionados = []

    for ej in ejercicios:
        edades_ej = ej.get("edades", [])
        # Buscar tanto por código (U16) como por nombre (Cadete)
        if edad not in edades_ej and categoria not in edades_ej:
            continue
        
        tags  = " ".join(ej.get("objetivos", {}).get("tacticos", []))
        texto = f"{ej['nombre']} {ej.get('descripcion', '')} {tags}".lower()
        if any(p in texto for p in palabras):
            seleccionados.append(ej)

    # Fallback: todos los de esa edad/categoría
    if not seleccionados:
        seleccionados = [
            e for e in ejercicios 
            if edad in e.get("edades", []) or categoria in e.get("edades", [])
        ]

    # Ordenar: primero los que tienen diagrama, luego por relevancia
    def score(ej):
        tags  = " ".join(ej.get("objetivos", {}).get("tacticos", []))
        texto = f"{ej['nombre']} {ej.get('descripcion', '')} {tags}".lower()
        coincidencias = sum(1 for p in palabras if p in texto)
        tiene_diagrama = 10 if "diagrama" in ej else 0
        return tiene_diagrama + coincidencias

    return sorted(seleccionados, key=score, reverse=True)

def construir_contexto_ejercicios(ejercicios: list, max_ejs: int = 10) -> str:
    con_diagrama = [e for e in ejercicios if "diagrama" in e]
    sin_diagrama = [e for e in ejercicios if "diagrama" not in e]
    
    seleccion = con_diagrama[:2] + sin_diagrama[:max_ejs-2]
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


def generar_sesion(edad: str, duracion: int, objetivo: str) -> dict:
    import re

    ejercicios = cargar_ejercicios()
    relevantes = filtrar_ejercicios(ejercicios, edad, objetivo)
    ctx_ejercs = construir_contexto_ejercicios(relevantes, max_ejs=10)
    ctx_teoria = construir_contexto_teoria(objetivo, edad)

    teoria_intro = ""
    if ctx_teoria:
        teoria_intro = f"TEORIA Y METODOLOGÍA (usa estos conceptos):\n{ctx_teoria[:1500]}\n\n"

    t_descanso = 3 if duracion >= 60 else 2
    descanso_texto = f"**DESCANSO ({t_descanso} min)**"

    t_calent = max(10, duracion // 6)
    t_vuelta = max(5, duracion // 15)
    t_parte  = duracion - t_calent - t_vuelta - t_descanso
    t_ej     = t_parte // 3
    categoria_nombre = EDAD_A_CATEGORIA.get(edad, edad)

    prompt = f"""Eres MiPizarra, experto en entrenamiento de baloncesto. Diseña una sesión completa y detallada.

CATEGORÍA: {categoria_nombre} ({edad}) | DURACIÓN TOTAL: {duracion} min | OBJETIVO PRINCIPAL: {objetivo}

REPARTO DE TIEMPO OBLIGATORIO (debe sumar exactamente {duracion} min):
- Calentamiento: {t_calent} min
- Parte principal: {t_parte} min → ~{t_ej} min por ejercicio ({t_parte} min en total entre los 3)
- Descanso: {t_descanso} min
- Vuelta a la calma: {t_vuelta} min

{teoria_intro}{VOCABULARIO_TECNICO}

{ctx_ejercs}

ESTRUCTURA EXACTA A SEGUIR — rellena TODOS los campos, sin añadir ni eliminar secciones:

**CALENTAMIENTO ({t_calent} min)**
Juego: "[nombre del juego dinámico con balón]"
Reglas: [2-3 frases concretas sobre cómo se juega, con mecánicas de {objetivo}]
Espacio: [media pista / pista completa]

**PARTE PRINCIPAL**

Ejercicio 1: [NOMBRE EXACTO de la lista de ejercicios]
Duración: {t_ej} min
Organización: [descripción con posiciones concretas: codo TL, esquina, baseline, poste alto...]
Puntos clave:
- [aspecto técnico 1 relacionado con {objetivo}]
- [aspecto técnico 2 relacionado con {objetivo}]

Ejercicio 2: [NOMBRE EXACTO de la lista — DIFERENTE al Ejercicio 1]
Duración: {t_ej} min
Organización: [descripción detallada]
Puntos clave:
- [aspecto técnico 1 relacionado con {objetivo}]
- [aspecto técnico 2 relacionado con {objetivo}]

{descanso_texto}

Ejercicio 3: [NOMBRE EXACTO de la lista — DIFERENTE a Ejercicio 1 y 2]
Duración: {t_parte - 2*t_ej} min
Organización: [descripción detallada con mayor complejidad que los anteriores]
Puntos clave:
- [aspecto técnico 1 relacionado con {objetivo}]
- [aspecto técnico 2 relacionado con {objetivo}]

**VUELTA A LA CALMA ({t_vuelta} min)**
Juego: "[juego recreativo o tiro libre, DIFERENTE al calentamiento]"
Reglas: [2-3 frases breves]

**Fundamentos**: [SOLO las técnicas específicas de {objetivo} practicadas hoy, p.ej. suspensión, entrada 1-2, floater, tiro de codo — NO copiar fundamentos genéricos]

INSTRUCCIONES CRÍTICAS:
- Usa SOLO nombres EXACTOS de la lista de ejercicios disponibles
- EXACTAMENTE 3 ejercicios en Parte Principal — ni uno más ni uno menos
- Los 3 ejercicios deben tener nombres DISTINTOS entre sí
- TODOS los ejercicios deben trabajar el objetivo "{objetivo}" directamente
- Progresión pedagógica: Ejercicio 1 (individual/parejas) → 2 (grupos) → 3 (juego reducido)
- Calentamiento: juego dinámico con balón, mecánica distinta a los ejercicios de parte principal
- Vuelta a la calma: recreativo o tiro libre
- Los Fundamentos deben listar técnicas DE TIRO/PASE/etc. reales que se hayan practicado hoy
- Responde ÚNICAMENTE con la sesión, sin explicaciones ni comentarios

SESIÓN:"""

    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model":   MODEL,
                "prompt":  prompt,
                "think":   False,          # Qwen3: desactivar thinking para evitar bloques <think>
                "stream":  False,
                "options": {
                    "temperature": 0.4,
                    "num_predict": 1800,
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
            "ejercicios_usados": relevantes[:10],
            "teoria_usada": bool(ctx_teoria),
        }

    return {
        "texto":             texto,
        "ejercicios_usados": relevantes[:10],
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
