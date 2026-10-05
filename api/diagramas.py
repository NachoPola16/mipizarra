# api/diagramas.py
"""Diagramas: coordenadas JSON generadas por el LLM (con schema) y su validación semántica."""
import json
import logging

import requests

from config import MODEL, OLLAMA_URL
from ejercicios import _extraer_conteo_nc_m
from prompts import SYSTEM_DIAGRAMA

logger = logging.getLogger(__name__)

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
