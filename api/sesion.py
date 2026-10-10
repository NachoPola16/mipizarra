# api/sesion.py
"""Modo 1: generación de una sesión completa de entrenamiento.

La sesión tiene entre 5 y 8 ejercicios en total (cuenta el calentamiento; acaba con un ejercicio más,
sin bloque de vuelta a la calma salvo que plan_sesion.CON_VUELTA_A_LA_CALMA lo active);
cuántos y cuánto dura cada uno lo decide plan_sesion según la duración y la edad. Los ejercicios de
la biblioteca los compone el código con la ficha curada íntegra (ver bloques.py); el modelo solo
redacta calentamiento, vuelta a la calma, fundamentos y los huecos para los que no hay ficha
relevante (marcados como «propuestos por la IA»). La variante N.2 solo existe si la ficha trae
progresión curada. Todo lo que escribe el modelo pasa por la guardia de líneas rojas."""
import logging
import random
import re
from dataclasses import dataclass

import requests

from bloques import (
    MARCA_PROPUESTO, bloque_calentamiento, bloque_curado, bloque_variante_curada, extraer_bloques,
    formatear_descripcion, nombre_de_cabecera, reescribir_bloque,
)
from config import EDAD_A_CATEGORIA, MODEL_SESION, OLLAMA_URL
from contexto import construir_contexto_teoria
from ejercicios import (
    cargar_ejercicios, elegir_calentamiento as _elegir_calentamiento, elegir_fichas as _elegir_fichas,
    nivel_objetivo,
)
from lineas_rojas import (
    CATEGORIAS_MINIBASKET, aviso_pedido, aviso_pedido_no_incluido, instruccion_prompt, pedidos_presentes,
    terminos_pedidos, violaciones,
)
from plan_sesion import plan_de_tiempos

logger = logging.getLogger(__name__)

# ─── Generación ──────────────────────────────────────────────────────────
# Categorías de formación (minibasket y alevín) donde no se recomienda enseñar
# juego de poste ni bloqueos — no es ilegal, pero no aporta a esas edades
# (mismo criterio que la tabla de restricciones de docs/coordenadas.md).
CATEGORIAS_SIN_POSTE_NI_BLOQUEO = CATEGORIAS_MINIBASKET


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


# Minutos máximos razonables haciendo lo mismo antes de perder la atención/
# motivación del grupo. Categorías de formación aguantan menos que Cadete+.
MAX_BLOQUE_POR_EDAD = {
    "U8": 10, "U10": 10, "Prebenjamín": 10, "Benjamín": 10,
    "U12": 10, "Alevín": 10,
    "U14": 15, "Infantil": 15,
}
MAX_BLOQUE_DEFECTO = 20  # Cadete en adelante

# Qué se espera de un ejercicio según su nivel de oposición (el arco de la parte principal va de
# sin oposición a oposición igualada; ver ejercicios.nivel_objetivo).
ROLES_EJERCICIO = {
    0: "sin oposición o defensa pasiva",
    1: "con superioridad numérica u oposición reducida",
    2: "con oposición igualada",
}


def _redondear_5(minutos: float, minimo: int = 5) -> int:
    """Las duraciones son una guía para el entrenador, no una medida exacta —
    se redondean siempre a múltiplos de 5 (5, 10, 15, 20...), nunca por debajo del mínimo."""
    return max(minimo, round(minutos / 5) * 5)


def _bloque_ejercicio(numero: int, nombre: str, duracion: int) -> str:
    """Plantilla que el modelo rellena para un hueco sin ficha: siempre un bloque único (la variante
    N.2 solo existe si la ficha trae progresión curada). Con nombre vacío, el modelo propone también
    el nombre del ejercicio."""
    return f"""Ejercicio {numero}: {nombre}
Duración: {duracion} min
Organización:
Puntos clave:
-
-
"""


@dataclass
class _Hueco:
    """Uno de los ejercicios de la parte principal."""
    numero: int
    ficha: dict | None   # ficha de la biblioteca, o None si el hueco lo propone la IA
    t1: int              # minutos del bloque base (o del bloque entero si no se parte)
    t2: int = 0          # minutos de la variante N.2 (0 si no se parte)
    variante_curada: str | None = None
    nivel: int = 1       # nivel de oposición que le toca en el arco de la sesión (0, 1 o 2)

    @property
    def partido(self) -> bool:
        return self.variante_curada is not None

    def claves_del_modelo(self) -> list[str]:
        """Bloques que se piden al modelo para este hueco: solo el propio ejercicio si no hay ficha."""
        return [f"ej:{self.numero}"] if self.ficha is None else []


def _duraciones(duracion: int, partido: bool) -> tuple[int, int]:
    if not partido:
        return duracion, 0
    t1 = _redondear_5(duracion / 2)
    return t1, _redondear_5(duracion - t1)


def _linea_prompt(hueco: _Hueco) -> str:
    rol = ROLES_EJERCICIO[hueco.nivel]
    ficha = hueco.ficha
    if ficha is None:
        return (f"{hueco.numero}. SIN FICHA en la biblioteca para este hueco: propón tú un ejercicio "
                f"{rol}, con nombre propio, coherente con el objetivo y la categoría, y escribe su bloque "
                f"«Ejercicio {hueco.numero}» completo.")
    descripcion = formatear_descripcion(ficha.get("descripcion", "")).replace("\n", "\n   ")
    puntos = " | ".join(ficha.get("puntos_clave", []))
    return (f'{hueco.numero}. "{ficha["nombre"]}" — {rol}.\n'
            f"   Ficha del entrenador (se incluye sola en la sesión: NO la escribas ni la resumas):\n"
            f"   {descripcion}\n   Puntos clave: {puntos}")


def _plantilla_modelo(huecos: list[_Hueco], t_calent: int, t_vuelta: int, con_calentamiento: bool = True) -> str:
    """Solo los apartados que redacta el modelo, en el orden de la sesión. Con ficha de calentamiento
    (con_calentamiento=False) el modelo no lo escribe: lo compone el código."""
    bloques = [_bloque_ejercicio(h.numero, "(nombre propio del ejercicio)", h.t1) for h in huecos if h.ficha is None]
    principal = chr(10).join(bloques)
    vuelta = f"**VUELTA A LA CALMA ({t_vuelta} min)**{chr(10)}Juego:{chr(10)}Reglas:{chr(10)}{chr(10)}" if t_vuelta else ""
    calentamiento = f"**CALENTAMIENTO ({t_calent} min)**{chr(10)}Juego:{chr(10)}Reglas:{chr(10)}Espacio:{chr(10)}{chr(10)}" \
        if con_calentamiento else ""
    return f"""{calentamiento}**PARTE PRINCIPAL**

{principal}
{vuelta}**Fundamentos**: """


def _limpiar_respuesta(texto: str) -> str:
    """Quita del texto del modelo el razonamiento, preámbulos, meta-comentarios y repeticiones."""
    texto = texto.strip()

    if texto.startswith("{") or texto.startswith("["):
        logger.warning("Modelo devolvió JSON en lugar de texto, reintentando...")
        raise ValueError("Respuesta en JSON no válida")

    # ── 0. Eliminar bloques <think>...</think> (Qwen3 con think no desactivado) ──
    texto = re.sub(r'<think>.*?</think>', '', texto, flags=re.DOTALL).strip()

    # ── 0b. Cortar razonamiento previo y encontrar el inicio real de la sesión ──
    # Busca el primer marcador estructural de la sesión (en cualquier orden)
    match_inicio = re.search(
        r'(\*\*CALENTAMIENTO|\*\*PARTE PRINCIPAL|^Ejercicio\s+\d(?:\.\d+)?\s*(?:\([^)]*\))?\s*:)',
        texto, re.MULTILINE
    )
    if match_inicio:
        texto = texto[match_inicio.start():]
    else:
        # Fallback: primera línea que comience una sección conocida
        lineas = texto.split('\n')
        primera_es = next(
            (i for i, l in enumerate(lineas)
             if re.match(r'(Ejercicio\s+\d|CALENTAMIENTO|\*\*CALENTAMIENTO|\*\*PARTE)', l.strip())),
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
    return texto


def _pedir_texto_sesion(prompt: str, num_predict: int, num_ctx: int,
                       parar_en: tuple[str, ...] = ()) -> tuple[str, str | None]:
    """Devuelve (texto, done_reason). done_reason=='length' significa que Ollama
    agotó num_predict y cortó a mitad de frase — señal real de truncado, a
    diferencia de adivinar de antemano si el presupuesto alcanzará."""
    response = requests.post(
        f"{OLLAMA_URL}/api/generate",
        json={
            "model":   MODEL_SESION,
            "prompt":  prompt,
            "stream":  False,
            "think":   False,          # modelos con razonamiento por defecto no deben gastar el presupuesto pensando
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
                    *parar_en,
                ],
            },
        },
        timeout=300,
    )
    response.raise_for_status()
    data = response.json()
    return data["response"], data.get("done_reason")


def _con_inicio(texto: str, inicio: str) -> str:
    """El prompt termina con el inicio de la respuesta (cabecera de calentamiento): el modelo
    continúa desde ahí, así que se le antepone. Si repite la cabecera por su cuenta, no se duplica."""
    if re.match(r"\s*\*{0,2}\s*CALENTAMIENTO", texto, re.IGNORECASE):
        return texto
    return _unir(inicio, texto)


def _texto_del_modelo(prompt: str, inicio: str, num_predict: int, num_ctx: int) -> str:
    """Pide el texto al modelo, con un reintento con más presupuesto si se trunca."""
    texto, done_reason = _pedir_texto_sesion(prompt, num_predict, num_ctx)
    if done_reason == "length":
        logger.warning(
            f"Sesión truncada (agotó num_predict={num_predict}), reintentando con más presupuesto..."
        )
        texto, done_reason = _pedir_texto_sesion(prompt, num_predict + 2500, num_ctx + 3000)
        if done_reason == "length":
            logger.warning(
                "Sesión sigue truncada tras el reintento — se entrega el texto "
                "parcial (mejor incompleto y avisado que nada)."
            )
    return _limpiar_respuesta(_con_inicio(texto, inicio))


# Cómo empieza, según el apartado, una continuación que repite su propia cabecera.
_CABECERA_PROPIA = {
    "calentamiento": re.compile(r"\s*\*{0,2}\s*CALENTAMIENTO", re.IGNORECASE),
    "vuelta":        re.compile(r"\s*\*{0,2}\s*VUELTA A LA CALMA", re.IGNORECASE),
    "fundamentos":   re.compile(r"\s*\*{0,2}\s*fundamentos", re.IGNORECASE),
    "ej":            re.compile(r"\s*Ejercicio\s+\d"),
}
_ABRE_SECCION = re.compile(r"\s*(?:\*\*|Ejercicio\s+\d)")


def _completar_apartados(cuerpo: str, texto: str, huecos: list[_Hueco], inicios: dict[str, str],
                         num_ctx: int, fundamentos_reserva: str = "") -> str:
    """El modelo (4B) suele darse por terminado tras el primer apartado. Cada apartado que falta
    se le pide por separado, en el orden de la sesión: el código escribe el comienzo del apartado
    y el modelo lo continúa viendo todo lo ya escrito. Cada apartado se pide una sola vez."""
    orden = ["calentamiento"] + [c for h in huecos for c in h.claves_del_modelo()] + ["vuelta", "fundamentos"]
    for clave in (c for c in orden if c in inicios):
        bloques = extraer_bloques(texto)
        _normalizar_claves(huecos, bloques)
        if bloques.get(clave, "").strip():
            continue
        inicio = inicios[clave]
        parar = ("\n\n", "**") if clave == "fundamentos" else ("\n**", "\nEjercicio ")
        presupuesto = 900 if clave.startswith("ej:") else 600
        continuacion, _ = _pedir_texto_sesion(f"{cuerpo}{texto}\n\n{inicio}", presupuesto, num_ctx, parar)
        propia = _CABECERA_PROPIA[clave.split(":")[0]].match(continuacion)
        if propia:
            # el modelo repitió la cabecera que ya se le había dado: se usa su versión, sin duplicarla
            texto = f"{texto}\n\n{continuacion.lstrip()}"
        elif _ABRE_SECCION.match(continuacion) or not continuacion.strip():
            # abrió otra sección o no escribió nada: este apartado queda sin generar
            if clave == "fundamentos" and fundamentos_reserva:
                texto = f"{texto}\n\n**Fundamentos**: {fundamentos_reserva}"
        else:
            texto = f"{texto}\n\n{_unir(inicio, continuacion)}"
    return texto


def _unir(inicio: str, continuacion: str) -> str:
    """Arranque + continuación. Si el modelo repite la etiqueta con la que acaba el arranque
    ('Juego:'), se queda con una sola."""
    ultima = inicio.split("\n")[-1]
    if ultima.endswith(":") and continuacion.lstrip().startswith(ultima):
        return inicio[:len(inicio) - len(ultima)] + continuacion.lstrip()
    return inicio + continuacion


def _fundamentos_de_las_fichas(huecos: list[_Hueco]) -> str:
    """Fundamentos de reserva, sin inventar nada: los objetivos técnicos de las fichas de la sesión."""
    vistos: list[str] = []
    for h in huecos:
        for tecnico in (h.ficha or {}).get("objetivos", {}).get("tecnicos", []):
            if tecnico not in vistos:
                vistos.append(tecnico)
    return (", ".join(vistos[:6]) + ".") if vistos else ""


def _nombre_de_pieza(clave: str) -> str:
    return {"calentamiento": "Calentamiento", "vuelta": "Vuelta a la calma",
            "fundamentos": "Fundamentos"}.get(clave, clave.replace("ej:", "Ejercicio "))


def _normalizar_claves(huecos: list[_Hueco], bloques: dict[str, str]) -> None:
    """El modelo a veces escribe 'Ejercicio N.1:' donde la plantilla pedía 'N:': se acepta."""
    for h in huecos:
        n = h.numero
        if h.ficha is None and f"ej:{n}" not in bloques and f"ej:{n}.1" in bloques:
            bloques[f"ej:{n}"] = bloques.pop(f"ej:{n}.1")


def _piezas_con_linea_roja(bloques: dict[str, str], claves: list[str], edad: str,
                           permitidos=()) -> dict[str, list[str]]:
    """Piezas redactadas por el modelo que incumplen las líneas rojas de la edad. `permitidos` son los
    términos que el entrenador pidió expresamente en el objetivo: no cuentan."""
    malas = {}
    for clave in claves:
        if clave in bloques:
            encontradas = violaciones(bloques[clave], edad, permitidos)
            if encontradas:
                malas[clave] = encontradas
    return malas


def _bloques_de_hueco(hueco: _Hueco, bloques: dict[str, str]) -> list[str]:
    """Texto final de un hueco: ficha curada (con su variante si la trae) o bloque propuesto por el
    modelo (puede ser [])."""
    n = hueco.numero
    if hueco.ficha is not None:
        if hueco.partido:
            return [bloque_curado(n, hueco.ficha, hueco.t1, partido=True), hueco.variante_curada]
        return [bloque_curado(n, hueco.ficha, hueco.t1, partido=False)]

    # Hueco propuesto por la IA
    bloque = bloques.get(f"ej:{n}")
    if bloque is None:
        return []
    nombre = nombre_de_cabecera(bloque) or "Ejercicio propuesto"
    return [reescribir_bloque(bloque, f"Ejercicio {n}: {nombre}", hueco.t1, propuesto=True)]


def _ensamblar(huecos: list[_Hueco], bloques: dict[str, str],
               t_calent: int, t_vuelta: int, t_descanso: int) -> tuple[str, list[int]]:
    """Compone el texto final de la sesión y devuelve también qué huecos son propuestos."""
    partes: list[str] = []
    if bloques.get("calentamiento"):
        partes.append(f"**CALENTAMIENTO ({t_calent} min)**\n{bloques['calentamiento']}")
    partes.append("**PARTE PRINCIPAL**")
    propuestos = []
    for hueco in huecos:
        textos = _bloques_de_hueco(hueco, bloques)
        partes.extend(textos)
        if textos and hueco.ficha is None:
            propuestos.append(hueco.numero)
        if hueco.numero == (len(huecos) + 1) // 2:     # el descanso va hacia la mitad
            partes.append(f"**DESCANSO ({t_descanso} min)**")
    if t_vuelta and bloques.get("vuelta"):
        partes.append(f"**VUELTA A LA CALMA ({t_vuelta} min)**\n{bloques['vuelta']}")
    if bloques.get("fundamentos"):
        partes.append(f"**Fundamentos**: {bloques['fundamentos']}")
    return "\n\n".join(partes), propuestos


def generar_sesion(edad: str, duracion: int, objetivo: str) -> dict:
    plan = plan_de_tiempos(duracion, edad)
    n = len(plan.duraciones)
    # azar: mismos parámetros, distinta elección de fichas entre los empates (misma calidad y arco)
    biblioteca = cargar_ejercicios()
    azar = random.Random()
    fichas = _elegir_fichas(biblioteca, edad, objetivo, n, azar=azar)
    ctx_teoria = construir_contexto_teoria(objetivo, edad)

    # Sin truncado global aquí: construir_contexto_teoria ya aplica presupuesto por
    # colección, así que lo que devuelve ya está acotado a un tamaño razonable.
    teoria_intro = f"CONTEXTO METODOLÓGICO:\n{ctx_teoria}\n\n" if ctx_teoria else ""

    t_calent, t_vuelta, t_descanso = plan.t_calentamiento, plan.t_vuelta, plan.t_descanso
    # Calentamiento: una ficha curada de la biblioteca si hay una para la edad (el 4B inventaba juegos
    # poco adecuados y repetía material); si no, lo redacta el modelo como siempre.
    ficha_calent = (_elegir_calentamiento(biblioteca, edad, objetivo, {f.get("id") for f in fichas if f}, azar)
                    if t_calent else None)
    categoria_nombre = EDAD_A_CATEGORIA.get(edad, edad)

    # Una ficha con progresión curada se parte en N.1 + N.2 si el ejercicio dura más de lo que esa
    # edad aguanta haciendo lo mismo; sin progresión curada va entera (el modelo no inventa variantes).
    max_bloque = MAX_BLOQUE_POR_EDAD.get(edad, MAX_BLOQUE_DEFECTO)
    huecos = []
    for numero, (ficha, minutos) in enumerate(zip(fichas, plan.duraciones), start=1):
        t1, t2, variante = minutos, 0, None
        if ficha and minutos > max_bloque:
            parte1, parte2 = _duraciones(minutos, True)
            variante = bloque_variante_curada(numero, ficha, parte2)
            if variante:
                t1, t2 = parte1, parte2
        huecos.append(_Hueco(numero, ficha, t1, t2, variante, nivel_objetivo(numero - 1, n)))

    # Presupuesto de generación: solo lo que escribe el modelo. Es un punto de partida, no una
    # garantía (la verbosidad varía de una generación a otra); si se trunca de verdad,
    # _texto_del_modelo reintenta con más en vez de confiar en una estimación fija.
    n_propuestos = sum(1 for h in huecos if h.ficha is None)
    num_predict_sesion = 1200 + 800 * n_propuestos
    num_ctx_sesion     = 9000 + 800 * max(0, n - 3)

    lineas_ejercicios = "\n".join(_linea_prompt(h) for h in huecos)
    plantilla = _plantilla_modelo(huecos, t_calent, t_vuelta, con_calentamiento=ficha_calent is None)
    # Lo que el entrenador pide expresamente en el objetivo se hace, con aviso (igual que en el ejercicio suelto).
    permitidos = terminos_pedidos(objetivo, edad)
    prohibido = instruccion_prompt(edad, permitidos)
    prohibido = f"{prohibido}\n\n" if prohibido else ""

    inicio_respuesta = f"**CALENTAMIENTO ({t_calent} min)**\nJuego:"

    def cuerpo_prompt(correccion: str = "") -> str:
        return f"""Eres MiPizarra, asistente de entrenamiento de baloncesto.
Rellena la plantilla de abajo con contenido concreto. No añadas texto fuera de la plantilla.
Escribe SOLO los apartados que aparecen en la plantilla: los ejercicios con ficha del entrenador
ya están redactados y se añaden solos (no escribas su bloque «Ejercicio N», ni repitas su contenido).

CATEGORÍA: {categoria_nombre} ({edad}) | DURACIÓN: {duracion} min | OBJETIVO: {objetivo}

Si el objetivo es amplio o genérico (p.ej. solo "tiro", sin más detalle), no lo trates
igual en todos los ejercicios: cada uno debe concretar un aspecto distinto (tiro en
estático, pies de tiro, mano/muñeca, tiro tras bote, tiro en movimiento...) en vez de
repetir siempre la misma idea general. Además, el objetivo no tiene que ser
necesariamente el foco principal de todos los ejercicios — está bien que en alguno sea
secundario o terciario si eso da más variedad a la sesión.

{teoria_intro}{vocabulario_tecnico(edad)}

{prohibido}{correccion}EJERCICIOS DE LA SESIÓN:
{lineas_ejercicios}

{plantilla}

RESPUESTA (rellena TODOS los apartados de la plantilla, en este orden, sin saltarte ninguno):
"""

    inicios = {"fundamentos": "**Fundamentos**: En esta sesión se trabajan"}
    if ficha_calent is None:
        inicios["calentamiento"] = inicio_respuesta
    if t_vuelta:
        inicios["vuelta"] = f"**VUELTA A LA CALMA ({t_vuelta} min)**\nJuego:"
    for h in huecos:
        for clave in h.claves_del_modelo():
            inicios[clave] = f"Ejercicio {clave[3:]}:"

    claves_modelo = ((["calentamiento"] if ficha_calent is None else []) + (["vuelta"] if t_vuelta else [])
                     + ["fundamentos"] + [c for h in huecos for c in h.claves_del_modelo()])
    if ficha_calent is not None:
        # el modelo arranca en el primer apartado que le toca, en el orden de la sesión
        primera = next((c for h in huecos for c in h.claves_del_modelo()),
                       "vuelta" if t_vuelta else "fundamentos")
        inicio_respuesta = inicios[primera]

    try:
        correccion = ""
        for intento in (1, 2):
            cuerpo = cuerpo_prompt(correccion)
            texto = _texto_del_modelo(cuerpo + inicio_respuesta, inicio_respuesta,
                                     num_predict_sesion, num_ctx_sesion)
            texto = _limpiar_respuesta(_completar_apartados(
                cuerpo, texto, huecos, inicios, num_ctx_sesion, _fundamentos_de_las_fichas(huecos)))
            bloques = extraer_bloques(texto)
            _normalizar_claves(huecos, bloques)
            malas = _piezas_con_linea_roja(bloques, claves_modelo, edad, permitidos)
            if not malas or intento == 2:
                break
            detalle = "; ".join(f"{_nombre_de_pieza(c)}: {', '.join(v)}" for c, v in malas.items())
            logger.warning(f"Línea roja en la sesión generada ({detalle}); reintentando...")
            correccion = (f"CORRECCIÓN: tu respuesta anterior incumplió las reglas de la categoría "
                          f"({detalle}). Reescríbela sin esos contenidos.\n\n")

        avisos = []
        for clave, encontradas in malas.items():
            bloques.pop(clave, None)
            avisos.append(f"{_nombre_de_pieza(clave)} omitido por incumplir las líneas rojas de {edad}: "
                          f"{', '.join(encontradas)}")
        if avisos:
            logger.warning("Piezas omitidas tras el reintento: " + " | ".join(avisos))

        if ficha_calent is not None:
            bloques["calentamiento"] = bloque_calentamiento(ficha_calent)
        texto, propuestos = _ensamblar(huecos, bloques, t_calent, t_vuelta, t_descanso)
        if permitidos:
            # el aviso solo promete «se ha hecho» si el término aparece en la sesión final
            presentes = pedidos_presentes(list(permitidos), texto, edad)
            avisos.insert(0, aviso_pedido(presentes, edad) if presentes
                          else aviso_pedido_no_incluido(list(permitidos), edad))
        for h in huecos:
            ya_avisado = any(a.startswith(f"Ejercicio {h.numero}") for a in avisos)
            if h.ficha is None and h.numero not in propuestos and not ya_avisado:
                avisos.append(f"Ejercicio {h.numero} no se pudo generar (sin ficha adecuada y sin propuesta del modelo)")
    except Exception as e:
        logger.error(f"Error generando sesión: {e}")
        return {
            "texto": f"**Error generando sesión**: {str(e)}",
            "ejercicios_usados": [f for f in fichas if f],
            "calentamiento_ficha": ficha_calent,
            "teoria_usada": bool(ctx_teoria),
            "propuestos": [],
            "avisos": [],
        }

    return {
        "texto":             texto,
        "ejercicios_usados": [f for f in fichas if f],
        "calentamiento_ficha": ficha_calent,
        "teoria_usada":      bool(ctx_teoria),
        "propuestos":        propuestos,
        "avisos":            avisos,
    }
