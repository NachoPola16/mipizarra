# api/ejercicios.py
"""Biblioteca de ejercicios: carga, filtrado por edad/objetivo y selección de los tres de la sesión."""
import json
import re
import unicodedata

from config import EDAD_A_CATEGORIA, EXERCISES_PATH

# ─── Ejercicios ──────────────────────────────────────────────────────────

# Fundamentos analíticos relacionados con cada tipo de objetivo.
# Sirven para seleccionar ejercicios de fase analítica (ejercicio 1)
# aunque no sean directamente del objetivo principal.
COMPONENTES_ANALITICOS = {
    "contraataque":      ["pase", "rebote", "transición", "salida", "carrera"],
    "transición":        ["pase", "rebote", "salida", "carrera"],
    "tiro":              ["tiro", "recepción", "desmarque", "corte", "movimiento"],
    "defensa":           ["posición", "ayuda", "deslizamiento", "cierre"],
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


def _es_de_la_edad(ej: dict, edad: str) -> bool:
    """¿La ficha admite esa edad, por la edad misma o por su categoría?"""
    edades_ej = ej.get("edades", [])
    return edad in edades_ej or EDAD_A_CATEGORIA.get(edad, edad) in edades_ej


def filtrar_ejercicios(ejercicios: list, edad: str, objetivo: str) -> list:
    palabras_obj, palabras_comp = _palabras_objetivo(objetivo)

    def texto_ej(ej):
        tags = " ".join(ej.get("objetivos", {}).get("tacticos", []))
        return f"{ej['nombre']} {ej.get('descripcion', '')} {tags}".lower()

    directos, analiticos, resto = [], [], []
    for ej in ejercicios:
        if not _es_de_la_edad(ej, edad):
            continue
        txt = texto_ej(ej)
        if any(p in txt for p in palabras_obj):
            directos.append(ej)
        elif palabras_comp and any(p in txt for p in palabras_comp):
            analiticos.append(ej)
        else:
            resto.append(ej)

    def score(ej, palabras):
        # el tema pesa más que el diagrama: antes +10 por diagrama hacía ganar a fichas sin relación con el objetivo
        # (y una ficha de calentamiento vale menos en la parte principal que una de igual tema que no lo es)
        penalizacion = 1 if ej.get("categoria") == "calentamiento" and edad not in _MINIBASKET else 0
        return (puntuacion_tema(ej, objetivo) if palabras is palabras_obj else (
            sum(1 for p in palabras if p in texto_ej(ej)) + (1 if "diagrama" in ej else 0))) - penalizacion

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


def nivel_objetivo(posicion: int, n: int) -> int:
    """Nivel de oposición que toca en la posición `posicion` (desde 0) de una parte principal de n
    ejercicios: el primer tercio sin oposición, el segundo con oposición reducida y el último igualada."""
    return min(2, (3 * posicion) // n)


# En minibasket (U8–U12) el bote y los juegos viven en fichas de calentamiento: ahí no se penalizan en la parte principal.
_MINIBASKET = {"U8", "U10", "U12", "Prebenjamín", "Benjamín", "Alevín"}

# Con `azar`, cuántas fichas empatadas en nivel compiten por un hueco. Llegan ordenadas por relevancia:
# limitarlo a las primeras evita que el azar elija una ficha floja habiendo mejores.
EMPATES_CON_VARIEDAD = 3


def _entre_empates(candidatos: list, clave, azar):
    """El mejor candidato según `clave` (el primero entre empates) o, con `azar`, uno cualquiera de los
    primeros empatados con él y del mismo nivel de oposición (la clave puede empatar niveles distintos,
    p. ej. 0 y 2 para «reducida»: eso rompería el arco). None si no hay candidatos."""
    if not candidatos:
        return None
    mejor = min(candidatos, key=clave)
    if azar is None:
        return mejor
    empatados = [e for e in candidatos
                 if clave(e) == clave(mejor) and _nivel_oposicion(e) == _nivel_oposicion(mejor)]
    return azar.choice(empatados[:EMPATES_CON_VARIEDAD])


# Cuánto pesa en la elección un nivel de oposición de distancia frente a un punto de tema: una palabra del objetivo en
# el nombre o los tags vale 3, así que una ficha del tema le gana a otra de otro tema aunque se salga un nivel del arco.
# Así una ficha ajena no ocupa un hueco solo porque su nivel encaje justo (p. ej. un 3c0 de pases en una sesión de defensa).
PESO_NIVEL = 2


def _tema(e: dict) -> int:
    """Puntos de tema que `elegir_fichas` anota en la ficha; 0 si no los hay (fichas sueltas, tests)."""
    # solo cuenta el tema que está en el nombre o los tags (3 o más): una mención suelta en la descripción no basta
    # para que una ficha desplace a otra de su nivel
    puntos = int(e.get("_tema", 0))
    return puntos if puntos >= 3 else 0


def _elegir_por_arco(analiticos: list, directos: list, n: int, azar, analiticos_reales: bool = True) -> list:
    """Una pasada del arco por posiciones; con `azar`, los empates de mismo nivel se sortean."""
    elegidos: list = []
    for posicion in range(n):
        objetivo = nivel_objetivo(posicion, n)
        usados = [id(e) for e in elegidos if e is not None]
        libres = [e for e in directos if id(e) not in usados]
        elegido = None
        if objetivo == 0:
            sin_usar = [e for e in analiticos if id(e) not in usados]
            if analiticos_reales:
                elegido = _entre_empates(sin_usar, lambda e: -_tema(e), azar)
            if elegido is None:
                elegido = _entre_empates(libres, lambda e: PESO_NIVEL * abs(_nivel_oposicion(e)) - _tema(e), azar)
        elif objetivo == 1:
            elegido = _entre_empates(libres, lambda e: PESO_NIVEL * abs(_nivel_oposicion(e) - 1) - _tema(e), azar)
        else:
            elegido = _entre_empates(libres, lambda e: PESO_NIVEL * (2 - _nivel_oposicion(e)) - _tema(e), azar)
        elegidos.append(elegido)
    return elegidos


def _desvio_del_arco(elegidos: list) -> tuple[int, int]:
    """(huecos sin ficha, suma de lo que cada ficha se aleja del nivel que toca en su posición)."""
    n = len(elegidos)
    return (sum(e is None for e in elegidos),
            sum(abs(_nivel_oposicion(e) - nivel_objetivo(i, n)) for i, e in enumerate(elegidos) if e))


# Sorteos que se prueban antes de volver a la elección determinista (que siempre es válida).
INTENTOS_CON_VARIEDAD = 8


def seleccionar_ejercicios(relevantes: list, n: int, azar=None) -> list:
    """Elige n ejercicios de la biblioteca siguiendo el arco sin oposición → reducida → igualada
    (con n = 3 coincide con seleccionar_tres_ejercicios). Si faltan candidatos, esos huecos quedan a
    None: los propone la IA. Sin `azar` la elección es determinista; con él (un `random.Random`) los
    empates entre fichas del mismo nivel se resuelven al azar, y solo se admite un sorteo que no deje
    más huecos ni encaje peor en el arco que la elección determinista."""
    analiticos = [e for e in relevantes if e.get('_fase') == 'ANALÍTICO']
    directos   = [e for e in relevantes if e.get('_fase') == 'OBJETIVO']
    reales = bool(analiticos)
    if not analiticos:
        analiticos = [e for e in directos if _nivel_oposicion(e) == 0] or directos[:1]

    base = _elegir_por_arco(analiticos, directos, n, None, reales)
    if azar is None:
        return base
    for _ in range(INTENTOS_CON_VARIEDAD):
        candidata = _elegir_por_arco(analiticos, directos, n, azar, reales)
        if _desvio_del_arco(candidata) <= _desvio_del_arco(base):
            return candidata
    return base


# Frases del entrenador que piden un tipo de ejercicio y no aparecen tal cual en las fichas: «ventaja de ataque frente a
# defensa» son las fichas de superioridad numérica (2c1, 3c2...).
CATEGORIAS_POR_FRASE = (
    (r"ventaja\s+(numerica\s+)?(del?\s+)?(ataque|atacante)|superioridad|ataque\s+(en\s+)?(ventaja|superioridad)"
     r"|ventaja\s+numerica|atacantes?\s+(en\s+)?ventaja", "ventaja_numerica"),
)


def categorias_pedidas(objetivo: str) -> set[str]:
    t = _sin_acentos(objetivo)
    return {cat for patron, cat in CATEGORIAS_POR_FRASE if re.search(patron, t)}


def espacio_pedido(objetivo: str) -> str | None:
    """«media_pista» si el entrenador pide media pista (o medio campo / una sola canasta); None si no dice nada o
    si pide expresamente pista completa."""
    t = _sin_acentos(objetivo)
    if re.search(r"(pista|campo)\s+completa?|toda\s+(la\s+)?pista|todo\s+(el\s+)?campo|a\s+pista\s+entera", t):
        return None
    if re.search(r"media\s+pista|medio\s+campo|medias\s+pistas|una\s+(sola\s+)?canasta", t):
        return "media_pista"
    return None


def elegir_fichas(ejercicios: list, edad: str, objetivo: str, n: int, solo_directas: bool = False,
                  azar=None) -> list:
    """n fichas de la biblioteca para la parte principal, siguiendo el arco de oposición. Solo entran
    las que encajan con el objetivo (umbral de relevancia): se filtran antes de elegir para que una
    ficha irrelevante no ocupe un hueco cuando hay otras relevantes sin usar. Los huecos que no se
    pueden cubrir quedan a None: los propone la IA, marcados como tales. `solo_directas` (para medir, no
    para generar) exige que la palabra del propio objetivo aparezca en la ficha: no vale un fundamento asociado.
    `azar` (un `random.Random`) da variedad entre sesiones con los mismos parámetros; sin él es determinista."""
    relevantes = [e for e in filtrar_ejercicios(ejercicios, edad, objetivo)
                  if es_relevante(e, objetivo, con_asociados=not solo_directas)]
    pedidas = categorias_pedidas(objetivo)
    if pedidas:
        # lo que el entrenador pide por su tipo (p. ej. «ventaja de ataque») entra aunque la ficha no use sus palabras
        ids = {id(e) for e in relevantes}
        extra = [e for e in ejercicios if e.get("categoria") in pedidas and _es_de_la_edad(e, edad)
                 and id(e) not in ids and e.get("categoria") != "calentamiento"]
        for e in extra:
            e.setdefault("_fase", "OBJETIVO")
        relevantes = relevantes + extra
    if espacio_pedido(objetivo) == "media_pista":
        # «a media pista»: fuera las que exigen ir a la otra canasta. Si no queda ninguna, el hueco lo propone la IA
        relevantes = [e for e in relevantes if e.get("espacio", "media_pista") != "pista_completa"]
    # Las fichas de calentamiento son para el calentamiento: en la parte principal solo entran si nombran el
    # propio objetivo en el nombre o los tags (el bote de U8–U12 vive en fichas de calentamiento) o como último recurso, si sin ellas
    # quedaría un hueco. Así una ficha de calentamiento asociada de lejos no desplaza a una ficha de la parte principal.
    # Si hay fichas de sobra que nombran el tema (nombre o tags), las que solo lo mencionan de pasada en la descripción
    # no compiten: una ficha de pase con una frase sobre defensa no debe abrir una sesión de defensa.
    for e in relevantes:
        e["_tema"] = int(puntuacion_tema(e, objetivo))
    centradas = [e for e in relevantes if puntuacion_tema(e, objetivo) >= 3]
    if sum(e.get("categoria") != "calentamiento" for e in centradas) >= n:
        relevantes = centradas
    principales = [e for e in relevantes
                   if e.get("categoria") != "calentamiento"
                   or es_relevante({**e, "descripcion": ""}, objetivo, con_asociados=False)]   # nombre o tags
    fichas = seleccionar_ejercicios(principales, n, azar=azar)
    if len(principales) < len(relevantes) and any(f is None for f in fichas):
        con_calentamientos = seleccionar_ejercicios(relevantes, n, azar=azar)
        if sum(f is None for f in con_calentamientos) < sum(f is None for f in fichas):
            fichas = con_calentamientos
    return _limitar_flojas(fichas, n)


def _limitar_flojas(fichas: list, n: int) -> list:
    """Una ficha que solo menciona el tema de pasada en la descripción (menos de 3 puntos) vale de relleno, pero no
    debe llenar la sesión: pasado un tercio de los huecos, el resto queda a None y lo propone la IA, marcado como
    tal, en vez de colar ejercicios de otro tema (p. ej. una defensa de la puerta en una sesión de pase)."""
    tope = max(1, n // 3)
    flojas = 0
    resultado = []
    for ficha in fichas:
        if ficha is not None and ficha.get("_tema", 3) < 3:
            flojas += 1
            if flojas > tope:
                ficha = None
        resultado.append(ficha)
    return resultado


def elegir_calentamiento(ejercicios: list, edad: str, objetivo: str, excluir=(), azar=None) -> dict | None:
    """Ficha de calentamiento de la biblioteca para la edad, o None si no hay (entonces lo redacta el
    modelo). Prefiere las que encajan con el objetivo; no repite las de `excluir` (las de la parte
    principal). Sin `azar` es determinista; con él elige entre todas las candidatas del grupo (entre
    calentamientos el orden de la biblioteca no es un orden de relevancia)."""
    excluir = {i for i in excluir if i is not None}
    candidatas = [e for e in ejercicios
                  if e.get("categoria") == "calentamiento" and _es_de_la_edad(e, edad)
                  and e.get("id") not in excluir
                  and not (espacio_pedido(objetivo) == "media_pista" and e.get("espacio") == "pista_completa")]
    if not candidatas:
        return None
    # relevancia directa (el objetivo en la propia ficha): con los fundamentos asociados casi todas encajaban y
    # una ficha con muchas palabras (movilidad con balón, pases...) salía en la mayoría de las sesiones
    grupo = [e for e in candidatas if es_relevante(e, objetivo, con_asociados=False)] or candidatas
    return grupo[0] if azar is None else azar.choice(grupo)


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


# ─── Umbral de relevancia ────────────────────────────────────────────────

# Palabras que aparecen en cualquier objetivo («trabajar el bote») y no indican tema.
_PALABRAS_VACIAS = {
    "para", "como", "sobre", "desde", "entre", "hacia", "tras", "mediante", "trabajo",
    "trabajar", "trabajando", "sesion", "equipo", "ejercicio", "ejercicios", "jugadores",
    "mejorar", "entrenamiento", "ejercitar",
    # relleno de una petición en lenguaje natural («crea un entrenamiento para trabajar defensa pero a media pista»):
    # casi cualquier ficha las lleva en la descripción y la hacían «relevante» sin tratar del tema
    "crea", "crear", "quiero", "quieres", "haz", "hacer", "pero", "esten", "estan", "atentos", "atento",
    "pista", "pistas", "media", "medias", "medio", "campo", "jugador", "frente", "ventaja", "ataque",
    "ataques", "que", "cada", "todos", "todas", "mismo", "misma", "ejercicios",
    "divertida", "divertido", "divertidas", "divertidos", "pequenos", "pequenas", "aprendan", "aprender", "mejoren",
    "mejora", "bien", "muchas", "muchos", "veces", "despues", "antes", "sobre", "todo", "tambien", "ademas",
    "balon", "balones", "coger", "coge", "superar", "superen", "supere", "trabajo", "sesion", "grupo", "tengan", "puedan", "sean", "estar", "estos", "estas", "algo", "mas", "menos",
}

# Formas verbales y palabras de uso corriente que en las fichas se escriben de otra manera (raíz → raíces de la ficha):
# «que aprendan a botar» no encontraba las fichas de «bote», ni «que tiren más» las de «tiro».
_EQUIVALENTES = {
    "bota": ("bote", "botan", "botando"), "pasa": ("pase", "pasar"), "tira": ("tiro",), "tire": ("tiro",),
    "lanz": ("tiro",), "defien": ("defens",), "rebo": ("rebote",), "corr": ("carrera", "contraataque"),
    "fina": ("finaliz",), "driv": ("penetraci",), "pene": ("penetraci",),
}


def _sin_acentos(texto: str) -> str:
    descompuesto = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in descompuesto if unicodedata.category(c) != "Mn")


def _raiz(palabra: str) -> str:
    """Prefijo con el que se compara una palabra: la palabra entera si es corta o lleva
    números (1c1) y, si no, sin las últimas letras para cubrir flexiones (defensa/defensivo)."""
    if len(palabra) <= 4 or any(c.isdigit() for c in palabra):
        return palabra
    return palabra[:max(4, len(palabra) - 3)]


# «que se lo pasen bien» es pasarlo bien, no el pase
_PASARLO_BIEN = re.compile(r"\bse\s+lo\s+pas\w+(\s+bien)?|\bpasarlo(\s+bien)?")


def _palabras_significativas(objetivo: str) -> list[str]:
    texto = _PASARLO_BIEN.sub(" ", _sin_acentos(objetivo))
    palabras = re.findall(r"[a-z0-9]+", texto)
    if "rebot" in texto:
        # «que bloqueen al rival» en una sesión de rebote es bloqueo de rebote, no las fichas de bloqueo directo
        palabras = [p for p in palabras if not p.startswith("bloque") or p in ("bloqueo", "bloqueos")]
    return [p for p in palabras
            if p not in _PALABRAS_VACIAS and (len(p) >= 4 or any(c.isdigit() for c in p))]


def _raices_del_objetivo(objetivo: str) -> set[str]:
    raices = {_raiz(p) for p in _palabras_significativas(objetivo)}
    for r in list(raices):
        for equivalente in _EQUIVALENTES.get(r, ()):
            raices.add(_raiz(equivalente))
    return raices


def es_relevante(ej: dict, objetivo: str, con_asociados: bool = True) -> bool:
    """¿Encaja el ejercicio con el objetivo? Sí si alguna palabra significativa del objetivo
    (o un fundamento analítico asociado a él) aparece al inicio de una palabra del nombre, la
    descripción o los tags tácticos. Si no encaja, ese hueco de la sesión lo propone la IA."""
    raices = _raices_del_objetivo(objetivo)
    for clave, fundamentos in (COMPONENTES_ANALITICOS.items() if con_asociados else ()):
        clave_norm = _sin_acentos(clave)
        if any(clave_norm.startswith(r) or r.startswith(_raiz(clave_norm)) for r in raices):
            raices.update(_raiz(_sin_acentos(f)) for f in fundamentos)
    if not raices:
        return False
    tags = " ".join(ej.get("objetivos", {}).get("tacticos", []))
    texto = _sin_acentos(f"{ej.get('nombre', '')} {ej.get('descripcion', '')} {tags}")
    return any(re.search(rf"(?<!\w){re.escape(r)}", texto) for r in raices)


CATEGORIAS_GENERICAS = {"juego_equipo", "calentamiento"}


def puntuacion_tema(ej: dict, objetivo: str) -> float:
    """Cuánto trata la ficha del tema del objetivo: cada palabra significativa vale 3 si aparece en el nombre o
    los tags tácticos y 1 si solo en la descripción; el diagrama (0,5) solo desempata."""
    # la categoría genérica («juego_equipo», «calentamiento») no dice de qué trata la ficha; la subcategoría sí
    categoria = ej.get("categoria", "")
    clase = f"{'' if categoria in CATEGORIAS_GENERICAS else categoria} {ej.get('subcategoria', '')}".replace("_", " ")
    nombre_y_tags = _sin_acentos(f"{ej.get('nombre', '')} {' '.join(ej.get('objetivos', {}).get('tacticos', []))} {clase}")
    descripcion = _sin_acentos(ej.get("descripcion", ""))
    total = 0.0
    for palabra in _palabras_significativas(objetivo):
        # una palabra y sus equivalentes (botar/bote) cuentan una sola vez
        raices = {_raiz(palabra), *(_raiz(q) for q in _EQUIVALENTES.get(_raiz(palabra), ()))}
        if any(re.search(rf"(?<!\w){re.escape(r)}", nombre_y_tags) for r in raices):
            total += 3
        elif any(re.search(rf"(?<!\w){re.escape(r)}", descripcion) for r in raices):
            total += 1
    if ej.get("categoria") in categorias_pedidas(objetivo):
        total += 3
    return total + (0.5 if "diagrama" in ej else 0)
