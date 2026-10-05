# api/sesion.py
"""Modo 1: generación de una sesión completa de entrenamiento."""
import logging

import requests

from config import EDAD_A_CATEGORIA, MODEL_SESION, OLLAMA_URL
from contexto import construir_contexto_teoria
from ejercicios import cargar_ejercicios, filtrar_ejercicios, seleccionar_tres_ejercicios

logger = logging.getLogger(__name__)

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
