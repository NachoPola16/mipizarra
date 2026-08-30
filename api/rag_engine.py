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
# qwen3:4b (con thinking) filtra razonamiento en inglés dentro del propio texto (no
# solo como preámbulo) y el parámetro "think": False no lo evita de forma fiable.
# Esto afecta igual al texto libre (generar_sesion, reglamento) y al JSON de diagramas:
# bajo restricción de formato el modelo con thinking degrada y devuelve diagramas
# vacíos o inventados. La variante -instruct no tiene modo thinking, así que no puede
# colarse ningún razonamiento por ninguna de las dos rutas.
MODEL          = os.environ.get("OLLAMA_MODEL", "qwen3:4b-instruct")
MODEL_SESION   = os.environ.get("OLLAMA_MODEL_SESION", os.environ.get("OLLAMA_MODEL", "qwen3:4b-instruct"))
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

    def score(ej, palabras):
        txt = texto_ej(ej)
        coincidencias = sum(1 for p in palabras if p in txt)
        tiene_diagrama = 10 if "diagrama" in ej else 0
        return tiene_diagrama + coincidencias

    # Fallback: si no hay directos, usar toda la categoría
    if not directos:
        directos = analiticos + resto
        analiticos = []
    elif len(directos) < 3:
        # El objetivo no tiene por qué ser lo PRINCIPAL de los 3 ejercicios — si hay
        # pocos con coincidencia directa, se completa con los mejores del resto
        # (objetivo como aspecto secundario/terciario) en vez de forzar solo directos.
        resto_ordenado = sorted(resto, key=lambda e: score(e, palabras_obj), reverse=True)
        directos = directos + resto_ordenado[:3 - len(directos)]

    directos   = sorted(directos,   key=lambda e: score(e, palabras_obj),  reverse=True)
    analiticos = sorted(analiticos, key=lambda e: score(e, palabras_comp), reverse=True)[:4]

    # Marcar fase para que construir_contexto_ejercicios pueda etiquetarlos
    for ej in analiticos:
        ej["_fase"] = "ANALÍTICO"
    for ej in directos:
        ej["_fase"] = "OBJETIVO"

    # Devolver: analíticos primero (para fase 1), directos después (fases 2-3)
    return analiticos + directos


def _extraer_conteo_nc_m(nombre: str) -> tuple[int, int] | None:
    """Extrae (nº atacantes, nº defensores) de un nombre tipo 'AcB' / 'A contra B'
    (con o sin espacios), p.ej. '1c1', '2 contra 1', '3c0'. None si no matchea."""
    import re as _re
    m = _re.search(r'(\d)\s*c(?:ontra)?\s*(\d)', nombre.lower())
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def _nivel_oposicion(ej: dict) -> int:
    """0=sin oposición, 1=reducida (ventaja numérica), 2=igualada (mismo nº ataque/defensa)"""
    conteo = _extraer_conteo_nc_m(ej['nombre'])
    if conteo:
        ataque, defensa = conteo
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


def construir_contexto_teoria(objetivo: str, edad: str, presupuesto_por_coleccion: int = 900) -> str:
    """Presupuesto de caracteres POR COLECCIÓN, no un truncado global al final: antes
    se concatenaban teoria+planificacion+reglamento y se cortaba a 800 caracteres en
    el prompt, así que planificacion y reglamento (los últimos en concatenarse) nunca
    llegaban a sobrevivir el corte — en la práctica solo teoria influía en la sesión.
    "teoria_md" (los 20 .md escritos a propósito) va primero y con más presupuesto:
    antes competían en la misma colección que "teoria" contra PDFs de cientos de KB
    y casi nunca ganaban la búsqueda de vecinos más cercanos."""
    consulta = f"entrenamiento baloncesto {objetivo} categoria {edad}"
    partes   = []
    mapeo    = {
        "teoria_md":     ("MATERIAL PROPIO (prioritario)", int(presupuesto_por_coleccion * 1.5)),
        "teoria":        ("TEORIA Y METODOLOGIA",           presupuesto_por_coleccion),
        "planificacion": ("PLANIFICACION",                  presupuesto_por_coleccion),
        "reglamento":    ("REGLAMENTO",                      presupuesto_por_coleccion),
    }
    for nombre, (etiqueta, presupuesto) in mapeo.items():
        fragmento = consultar_coleccion(nombre, consulta, n_resultados=4)
        if fragmento:
            partes.append(f"--- {etiqueta} ---\n{fragmento[:presupuesto]}")

    return "\n\n".join(partes) if partes else ""


# ─── Generación ──────────────────────────────────────────────────────────
# Categorías de formación (minibasket y alevín) donde no se recomienda enseñar
# juego de poste ni bloqueos — no es ilegal, pero no aporta a esas edades
# (mismo criterio que la tabla de restricciones de docs/coordenadas.md).
CATEGORIAS_SIN_POSTE_NI_BLOQUEO = {"U8", "U10", "U12", "Prebenjamín", "Benjamín", "Alevín"}


def vocabulario_tecnico(edad: str) -> str:
    """Terminología técnica para el prompt de sesión, adaptada a la edad:
    sin poste bajo/bloqueos para categorías de formación."""
    mini = edad in CATEGORIAS_SIN_POSTE_NI_BLOQUEO

    zonas = ("codo TL derecho/izquierdo, cabecera triple, esquina derecha/izquierda, "
             "baseline, zona pintada, ala derecha/izquierda")
    if not mini:
        zonas += ", poste alto, poste bajo"

    defensa = ("posición básica (pies separados, rodillas flexionadas, manos activas), "
                "deslizamiento lateral, ayuda, rotación, negación, tapping")
    conceptos = "caída hacia canasta, corte (en V, puerta atrás), penetración, 1vs1 con bote"
    if not mini:
        defensa += ", defensa al bloqueo directo (pasar por delante/detrás, cambio)"
        conceptos = "bloqueo directo, " + conceptos

    return f"""\
TERMINOLOGÍA TÉCNICA (úsala donde tenga sentido táctico; no fuerces varios términos \
en una misma frase ni encadenes acciones sin relación lógica entre sí):
- Zonas de pista: {zonas}
- Bote: progresión (velocidad), protección (cuerpo entre balón y defensor), crossover, entre piernas, por detrás, bote hacia atrás
- Tiro: suspensión, bandeja mano dominante/débil, entrada 1-2 con parada, floater, tiro de media distancia desde codo, tiro libre
- Pase: pecho, picado, béisbol, por encima (overhead), pase en movimiento, pase de salida tras rebote
- Defensa: {defensa}
- Conceptos: {conceptos}\
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
        m = _re.match(r'Ejercicio\s+(\d+(?:\.\d+)?)\s*(?:\([^)]*\))?\s*:', linea.strip())
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


# Minutos máximos razonables haciendo lo mismo antes de perder la atención/
# motivación del grupo. Categorías de formación aguantan menos que Cadete+.
MAX_BLOQUE_POR_EDAD = {
    "U8": 10, "U10": 10, "Prebenjamín": 10, "Benjamín": 10,
    "U12": 10, "Alevín": 10,
    "U14": 15, "Infantil": 15,
}
MAX_BLOQUE_DEFECTO = 20  # Cadete en adelante


def _redondear_5(minutos: float, minimo: int = 5) -> int:
    """Las duraciones son una guía para el entrenador, no una medida exacta —
    se redondean siempre a múltiplos de 5 (5, 10, 15, 20...), nunca por debajo del mínimo."""
    return max(minimo, round(minutos / 5) * 5)


def _bloque_ejercicio(numero: int, nombre: str, duracion: int, edad: str) -> str:
    """Plantilla para un ejercicio de la parte principal. Si la duración supera lo que
    ese grupo de edad aguanta haciendo lo mismo, lo parte en N.1 (base) + N.2 (variante:
    mismo ejercicio con un cambio/regla nueva) en vez de un único bloque monótono."""
    max_bloque = MAX_BLOQUE_POR_EDAD.get(edad, MAX_BLOQUE_DEFECTO)
    if duracion <= max_bloque:
        return f"""Ejercicio {numero}: {nombre}
Duración: {duracion} min
Organización:
Puntos clave:
-
-
"""
    t1 = _redondear_5(duracion / 2)
    t2 = _redondear_5(duracion - t1)
    return f"""Ejercicio {numero}.1: {nombre}
Duración: {t1} min
Organización:
Puntos clave:
-
-

Ejercicio {numero}.2 (variante de "{nombre}" — mismo ejercicio con un cambio o regla nueva, no lo repitas igual):
Duración: {t2} min
Qué cambia respecto a {numero}.1:
Organización:
Puntos clave:
-
-
"""


def generar_sesion(edad: str, duracion: int, objetivo: str) -> dict:
    import re

    ejercicios = cargar_ejercicios()
    relevantes = filtrar_ejercicios(ejercicios, edad, objetivo)
    ej1, ej2, ej3 = seleccionar_tres_ejercicios(relevantes)
    ctx_teoria  = construir_contexto_teoria(objetivo, edad)

    # Sin truncado global aquí: construir_contexto_teoria ya aplica presupuesto por
    # colección, así que lo que devuelve ya está acotado a un tamaño razonable.
    teoria_intro = f"CONTEXTO METODOLÓGICO:\n{ctx_teoria}\n\n" if ctx_teoria else ""

    t_descanso = 3 if duracion >= 60 else 2
    descanso_texto = f"**DESCANSO ({t_descanso} min)**"

    t_calent = _redondear_5(duracion / 6, minimo=10)
    t_vuelta = _redondear_5(duracion / 15, minimo=5)
    t_parte  = duracion - t_calent - t_vuelta - t_descanso
    t_ej     = _redondear_5(t_parte / 3)
    categoria_nombre = EDAD_A_CATEGORIA.get(edad, edad)

    # Categorías de formación con sesiones largas parten los 3 ejercicios en N.1+N.2
    # (ver _bloque_ejercicio) — la plantilla pasa de 3 a 6 bloques a rellenar, así que
    # hace falta bastante más presupuesto de generación que con 3. Pero esto es solo
    # un punto de partida razonable, no una garantía: la verbosidad del modelo varía
    # de una generación a otra (confirmado con 2 sesiones reales que agotaron
    # done_reason="length" con presupuestos distintos — una de 6 bloques con 2500 y
    # otra de 3 bloques a 90 min con el "2500 de toda la vida" que hasta ahora parecía
    # suficiente). Por eso el número de aquí abajo es solo el primer intento; el
    # reintento en _pedir_texto_sesion() reacciona al truncado real en vez de confiar
    # en una estimación fija.
    max_bloque = MAX_BLOQUE_POR_EDAD.get(edad, MAX_BLOQUE_DEFECTO)
    bloques_partidos = t_ej > max_bloque
    num_predict_sesion = 5000 if bloques_partidos else 3200
    num_ctx_sesion     = 11000 if bloques_partidos else 9000

    n1 = ej1['nombre'] if ej1 else "ejercicio analítico"
    n2 = ej2['nombre'] if ej2 else "ejercicio con superioridad"
    n3 = ej3['nombre'] if ej3 else "ejercicio aplicado"

    prompt = f"""Eres MiPizarra, asistente de entrenamiento de baloncesto.
Rellena la plantilla de abajo con contenido concreto. No añadas texto fuera de la plantilla.

CATEGORÍA: {categoria_nombre} ({edad}) | DURACIÓN: {duracion} min | OBJETIVO: {objetivo}

Si el objetivo es amplio o genérico (p.ej. solo "tiro", sin más detalle), no lo trates
igual en los tres ejercicios: cada uno debe concretar un aspecto distinto (tiro en
estático, pies de tiro, mano/muñeca, tiro tras bote, tiro en movimiento...) en vez de
repetir siempre la misma idea general. Además, el objetivo no tiene que ser
necesariamente el foco principal de los tres ejercicios — está bien que en alguno sea
secundario o terciario si eso da más variedad a la sesión.

{teoria_intro}{vocabulario_tecnico(edad)}

EJERCICIOS DE LA SESIÓN (ya seleccionados — usa estos nombres exactos):
1. "{n1}" — sin oposición o defensa pasiva. {_desc_ej(ej1) if ej1 else ''}
2. "{n2}" — con superioridad numérica. {_desc_ej(ej2) if ej2 else ''}
3. "{n3}" — con oposición igualada. {_desc_ej(ej3) if ej3 else ''}

**CALENTAMIENTO ({t_calent} min)**
Juego:
Reglas:
Espacio:

**PARTE PRINCIPAL**

{_bloque_ejercicio(1, n1, t_ej, edad)}
{_bloque_ejercicio(2, n2, t_ej, edad)}
{descanso_texto}

{_bloque_ejercicio(3, n3, t_ej, edad)}
**VUELTA A LA CALMA ({t_vuelta} min)**
Juego:
Reglas:

**Fundamentos**: """

    def _pedir_texto_sesion(num_predict: int, num_ctx: int) -> tuple[str, str | None]:
        """Devuelve (texto, done_reason). done_reason=='length' significa que Ollama
        agotó num_predict y cortó a mitad de frase — señal real de truncado, a
        diferencia de adivinar de antemano si el presupuesto alcanzará."""
        response = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model":   MODEL_SESION,
                "prompt":  prompt,
                "stream":  False,
                "options": {
                    "temperature": 0.4,
                    "num_predict": num_predict,
                    "num_ctx":     num_ctx,
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
        data = response.json()
        return data["response"], data.get("done_reason")

    try:
        texto, done_reason = _pedir_texto_sesion(num_predict_sesion, num_ctx_sesion)
        if done_reason == "length":
            logger.warning(
                f"Sesión truncada (agotó num_predict={num_predict_sesion}), "
                f"reintentando con más presupuesto..."
            )
            texto, done_reason = _pedir_texto_sesion(
                num_predict_sesion + 2500, num_ctx_sesion + 3000
            )
            if done_reason == "length":
                logger.warning(
                    "Sesión sigue truncada tras el reintento — se entrega el texto "
                    "parcial (mejor incompleto y avisado que nada)."
                )
        texto = texto.strip()

        if texto.startswith("{") or texto.startswith("["):
            logger.warning("Modelo devolvió JSON en lugar de texto, reintentando...")
            raise ValueError("Respuesta en JSON no válida")

        # ── 0. Eliminar bloques <think>...</think> (Qwen3 con think no desactivado) ──
        texto = re.sub(r'<think>.*?</think>', '', texto, flags=re.DOTALL).strip()

        # ── 0b. Cortar razonamiento previo y encontrar el inicio real de la sesión ──
        # Busca el primer marcador estructural de la sesión (en cualquier orden)
        match_inicio = re.search(
            r'(\*\*CALENTAMIENTO|\*\*PARTE PRINCIPAL|^Ejercicio\s+1(?:\.\d+)?\s*(?:\([^)]*\))?\s*:)',
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
# JSON Schema del diagrama para "format" en /api/generate: Ollama compila esto a
# una gramática (XGrammar) que restringe la decodificación token a token, así que
# garantiza forma válida (tipos, enums de "tipo") — a diferencia de "format": "json",
# que solo garantiza JSON parseable de cualquier forma. Deliberadamente permisivo en
# "required" por movimiento (solo de/tipo/orden): qué campos hacen falta según el
# tipo de movimiento (a_pos vs a) es una regla cruzada que JSON Schema no expresa
# bien, así que se comprueba en _validar_diagrama.
_DIAGRAMA_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "tipo": {"type": "string", "enum": ["media_pista", "pista_completa"]},
        "jugadores_ataque": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "x":  {"type": "number", "minimum": 0, "maximum": 100},
                    "y":  {"type": "number", "minimum": 0, "maximum": 100},
                },
                "required": ["id", "x", "y"],
            },
        },
        "jugadores_defensa": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "x":  {"type": "number", "minimum": 0, "maximum": 100},
                    "y":  {"type": "number", "minimum": 0, "maximum": 100},
                },
                "required": ["id", "x", "y"],
            },
        },
        "balon_inicio": {
            "type": "object",
            "properties": {"portador": {"type": "string"}},
            "required": ["portador"],
        },
        "movimientos": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "de":    {"type": "string"},
                    "a":     {"type": "string"},
                    "a_pos": {
                        "type": "object",
                        "properties": {
                            "x": {"type": "number", "minimum": 0, "maximum": 100},
                            "y": {"type": "number", "minimum": 0, "maximum": 100},
                        },
                        "required": ["x", "y"],
                    },
                    "tipo":  {"type": "string", "enum": ["desplazamiento", "pase", "bote", "tiro", "bloqueo"]},
                    "orden": {"type": "integer", "minimum": 1},
                    "curva": {"type": "boolean"},
                },
                "required": ["de", "tipo", "orden"],
            },
        },
        "conos": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "x": {"type": "number", "minimum": 0, "maximum": 100},
                    "y": {"type": "number", "minimum": 0, "maximum": 100},
                },
                "required": ["x", "y"],
            },
        },
    },
    "required": ["jugadores_ataque", "jugadores_defensa", "balon_inicio", "movimientos"],
}


def _validar_diagrama(diagrama: dict, nombre_ejercicio: str = "") -> str | None:
    """Valida coherencia semántica del diagrama que el JSON Schema no puede expresar:
    referencias de movimientos a jugadores realmente declarados, y que el nº de
    jugadores coincide con lo que dice el nombre (p.ej. "1c1" = 1 atacante + 1
    defensor). Devuelve None si es válido, o una descripción del error (para
    reintentar con el modelo señalándoselo) si no lo es."""
    ataque  = diagrama.get("jugadores_ataque") or []
    defensa = diagrama.get("jugadores_defensa") or []
    if not ataque:
        return "jugadores_ataque no puede estar vacío"

    ids = [j.get("id") for j in ataque] + [j.get("id") for j in defensa]
    if len(set(ids)) != len(ids):
        return "hay ids de jugador repetidos entre jugadores_ataque y jugadores_defensa"
    ids = set(ids)

    # Distancia mínima entre jugadores: en ejercicios "cara a cara muy cerca"
    # (p.ej. 1c1 de protección) el modelo a veces coloca atacante y defensor casi
    # en la misma coordenada — sus círculos se solapan en el render y uno queda
    # ilegible. 8 unidades (sistema 0-100) da un margen visible sin impedir
    # emparejamientos realmente pegados (un defensor presionando de cerca).
    MIN_DIST_JUGADORES = 8
    todos = ataque + defensa
    for i in range(len(todos)):
        for j in range(i + 1, len(todos)):
            p1, p2 = todos[i], todos[j]
            dist = ((p1.get("x", 0) - p2.get("x", 0)) ** 2 + (p1.get("y", 0) - p2.get("y", 0)) ** 2) ** 0.5
            if dist < MIN_DIST_JUGADORES:
                return (
                    f"jugadores '{p1.get('id')}' y '{p2.get('id')}' están demasiado cerca "
                    f"({dist:.1f} unidades, mínimo {MIN_DIST_JUGADORES}) — sus círculos se solaparían "
                    "en el diagrama, sepáralos aunque el ejercicio sea de marca cercana"
                )

    conteo = _extraer_conteo_nc_m(nombre_ejercicio)
    if conteo:
        n_ataque, n_defensa = conteo
        if len(ataque) != n_ataque or len(defensa) != n_defensa:
            return (
                f"el nombre del ejercicio indica {n_ataque}c{n_defensa} pero el diagrama "
                f"tiene {len(ataque)} atacante(s) y {len(defensa)} defensor(es)"
            )

    portador = (diagrama.get("balon_inicio") or {}).get("portador")
    if portador and portador not in ids:
        return f"balon_inicio.portador='{portador}' no es un jugador declarado"

    for mov in diagrama.get("movimientos") or []:
        de = mov.get("de")
        if de not in ids:
            return f"movimiento con de='{de}' no coincide con ningún jugador declarado"
        tipo = mov.get("tipo")
        if tipo == "pase":
            a = mov.get("a")
            if a not in ids:
                return f"movimiento 'pase' con a='{a}' no coincide con ningún jugador declarado"
        elif tipo in ("desplazamiento", "bote", "bloqueo") and "a_pos" not in mov:
            return f"movimiento '{tipo}' sin 'a_pos'"
        elif tipo not in ("desplazamiento", "bote", "bloqueo", "tiro", "pase"):
            return f"tipo de movimiento desconocido: '{tipo}'"

    return None


def generar_coordenadas_ejercicio(descripcion: str, nombre: str) -> dict | None:
    """Genera coordenadas precisas basadas en la descripción del ejercicio.
    JSON Schema restringe la forma (Ollama/XGrammar); _validar_diagrama comprueba
    lo que el schema no puede (conteo de jugadores, referencias cruzadas). Si el
    primer intento no pasa la validación semántica, reintenta una vez señalando el
    error concreto; si sigue sin ser válido, no hay diagrama — preferible a uno que
    contradice el texto."""

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
4. El número de jugadores_ataque y jugadores_defensa tiene que coincidir con lo que diga
   el NOMBRE o la DESCRIPCIÓN (ej. "1c1" o "1 contra 1" = 1 atacante y 1 defensor exactos,
   nunca añadas un segundo atacante; "3c0" = 3 atacantes, 0 defensores; "2c1" = 2 atacantes,
   1 defensor). Si describe a UN SOLO jugador entrenando individualmente (bote, tiro,
   técnica en solitario, circuito de conos) → usa exactamente 1 jugador_ataque, NUNCA
   inventes un intercambio de pases entre varios jugadores si la descripción no menciona
   pase explícitamente. Solo usa 2+ jugadores si el texto describe interacción real entre
   ellos (pase, defensa, competición por parejas). Ante la duda entre "inventar más
   jugadores" o "menos", elige siempre menos.
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

    def _pedir(prompt_txt: str) -> dict | None:
        try:
            response = requests.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model":   MODEL,
                    "prompt":  prompt_txt,
                    "format":  _DIAGRAMA_JSON_SCHEMA,
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
            return json.loads(response.json()["response"].strip())
        except Exception as e:
            logger.warning(f"  ✗ Error generando coordenadas: {e}")
            return None

    diagrama = _pedir(prompt)
    if diagrama is None:
        return None

    error = _validar_diagrama(diagrama, nombre)
    if error:
        logger.warning(f"  ✗ Diagrama inválido para '{nombre}': {error}. Reintentando...")
        prompt_retry = (
            prompt
            + f"\n\nTu intento anterior tenía este error, corrígelo: {error}\n"
              f"Diagrama anterior (no lo repitas igual):\n{json.dumps(diagrama, ensure_ascii=False)}\n\n"
              "Genera SOLO el JSON corregido:"
        )
        diagrama = _pedir(prompt_retry)
        if diagrama is None:
            return None
        error = _validar_diagrama(diagrama, nombre)
        if error:
            logger.warning(f"  ✗ Diagrama sigue inválido tras reintento para '{nombre}': {error}")
            return None

    logger.info(
        f"  ✓ Coordenadas generadas: {len(diagrama.get('jugadores_ataque', []))} atacantes, "
        f"{len(diagrama.get('jugadores_defensa', []))} defensores"
    )
    return diagrama


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


def reprompt_ejercicio(edad: str, objetivo: str, nombre: str, descripcion: str, instruccion: str) -> dict:
    """Regenera un ejercicio ya existente aplicando una corrección pedida por el
    entrenador — mismo formato de salida que generar_ejercicio_unico (texto y
    diagrama en un único JSON), pero partiendo del ejercicio actual en vez de
    generar uno nuevo desde cero, para que el modelo sepa qué está corrigiendo."""
    ctx = construir_contexto_ejercicios(
        filtrar_ejercicios(cargar_ejercicios(), edad, objetivo)
    )
    # OJO: no usar etiquetas tipo "Nombre:"/"Descripción:" (mayúscula) para describir
    # el ejercicio actual — el modelo tiende a copiar ese estilo de mayúsculas/nombres
    # de campo en el JSON de salida en vez de usar el esquema real de la app (se
    # observó "Nombre"/"ORGANIZACIÓN"/"SECUENCIA" y ningún campo de diagrama en
    # absoluto). Por eso aquí se describe en minúscula y se especifica el esquema
    # de salida de forma explícita, con ejemplo, en vez de darlo por hecho.
    prompt = (
        f"Este ejercicio de baloncesto ya está generado para la categoría {edad}, "
        f"dentro de una sesión con objetivo general: {objetivo}.\n\n"
        f"ejercicio actual — nombre: {nombre}\n"
        f"ejercicio actual — descripción: {descripcion}\n\n"
        f"El entrenador pide este cambio sobre ESTE ejercicio: {instruccion}\n\n"
        "Genera la versión corregida del ejercicio aplicando ese cambio. Si el cambio "
        "pedido afecta solo al diagrama (jugadores, movimientos), mantén el resto del "
        "ejercicio igual y actualiza el diagrama acorde al cambio.\n\n"
        f"Ejercicios de referencia:\n{ctx}\n\n"
        "Devuelve SOLO un JSON con EXACTAMENTE estos campos (nombres en minúscula, "
        "sin inventar ni renombrar ninguno): \"nombre\" (string), \"descripcion\" "
        "(string, la organización del ejercicio en prosa), \"duracion_min\" (entero), "
        "\"puntos_clave\" (array de strings), y \"diagrama\" con esta forma exacta:\n"
        '{"tipo": "media_pista", "jugadores_ataque": [{"id": "A1", "rol": "atacante", '
        '"x": 50, "y": 65}], "jugadores_defensa": [{"id": "D1", "rol": "defensor", '
        '"x": 50, "y": 45}], "balon_inicio": {"portador": "A1"}, "movimientos": '
        '[{"de": "A1", "tipo": "tiro", "orden": 1}], "conos": []}\n'
        "(coordenadas x/y de 0 a 100; ajusta jugadores/movimientos al ejercicio real, "
        "el ejemplo es solo para mostrar la forma del JSON). "
        "No devuelvas ningún otro campo ni cambies mayúsculas/minúsculas de estos nombres:"
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
        logger.info(f"Ejercicio corregido: {ej.get('nombre', '?')}")
        return ej
    except Exception as e:
        logger.warning(f"Error corrigiendo ejercicio: {e}")
        return {}


# ── Modo 3: Reglamento y dudas técnicas ─────────────────────────────────────

# SYSTEM_REGLAMENTO importado de api/prompts.py


def responder_duda_reglamento(pregunta: str) -> str:
    """Modo 3: responde una duda de reglamento o fundamento técnico.
    Antes respondía solo de memoria paramétrica del modelo pese a tener 1.238 chunks
    de reglas FIBA/minibasket/normativa de competición ya indexados en ChromaDB sin
    usar — normativa autonómica/long-tail es justo donde un 4B alucina más y donde
    hay más que ganar con retrieval. También consulta "teoria_md": ahí viven los dos
    .md curados de reglamento (normas clave FIBA, competición de formación en España),
    más concisos y de más señal que extraer un fragmento suelto de un PDF de reglas."""
    contexto_curado = consultar_coleccion("teoria_md", pregunta, n_resultados=3)
    contexto_reglas  = consultar_coleccion("reglamento", pregunta, n_resultados=6)
    partes = []
    if contexto_curado:
        partes.append(f"--- MATERIAL PROPIO ---\n{contexto_curado[:1500]}")
    if contexto_reglas:
        partes.append(f"--- REGLAMENTO FIBA / COMPETICIÓN ---\n{contexto_reglas[:2500]}")

    mensaje_usuario = pregunta
    if partes:
        mensaje_usuario = (
            f"EXTRACTOS DE REGLAMENTO (pueden no cubrir toda la pregunta; si no "
            f"encuentras la respuesta aquí, usa tu conocimiento pero dilo):\n"
            f"{chr(10).join(partes)}\n\nPREGUNTA: {pregunta}"
        )
    try:
        r = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": MODEL_SESION,
                "messages": [
                    {"role": "system", "content": SYSTEM_REGLAMENTO},
                    {"role": "user", "content": mensaje_usuario},
                ],
                "stream": False,
                "options": {"temperature": 0.3, "num_predict": 500, "num_ctx": 6144},
            },
            timeout=90,
        )
        r.raise_for_status()
        return r.json()["message"]["content"].strip()
    except Exception as e:
        logger.warning(f"Error en reglamento: {e}")
        return "No se pudo responder la consulta. Inténtalo de nuevo."
