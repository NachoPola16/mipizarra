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


def nivel_objetivo(posicion: int, n: int) -> int:
    """Nivel de oposición que toca en la posición `posicion` (desde 0) de una parte principal de n
    ejercicios: el primer tercio sin oposición, el segundo con oposición reducida y el último igualada."""
    return min(2, (3 * posicion) // n)


def seleccionar_ejercicios(relevantes: list, n: int) -> list:
    """Elige n ejercicios de la biblioteca siguiendo el arco sin oposición → reducida → igualada
    (con n = 3 coincide con seleccionar_tres_ejercicios). Si faltan candidatos, esos huecos quedan a
    None: los propone la IA."""
    analiticos = [e for e in relevantes if e.get('_fase') == 'ANALÍTICO']
    directos   = [e for e in relevantes if e.get('_fase') == 'OBJETIVO']
    if not analiticos:
        analiticos = [e for e in directos if _nivel_oposicion(e) == 0] or directos[:1]

    elegidos: list = []
    for posicion in range(n):
        objetivo = nivel_objetivo(posicion, n)
        usados = [id(e) for e in elegidos if e is not None]
        libres = [e for e in directos if id(e) not in usados]
        elegido = None
        if objetivo == 0:
            elegido = next((e for e in analiticos if id(e) not in usados), None)
            if elegido is None and libres:
                elegido = min(libres, key=lambda e: abs(_nivel_oposicion(e)))   # estable: el primero entre empates
        elif objetivo == 1:
            elegido = min(libres, key=lambda e: abs(_nivel_oposicion(e) - 1), default=None)
        else:
            elegido = min(libres, key=lambda e: -_nivel_oposicion(e), default=None)
        elegidos.append(elegido)
    return elegidos


def elegir_fichas(ejercicios: list, edad: str, objetivo: str, n: int, solo_directas: bool = False) -> list:
    """n fichas de la biblioteca para la parte principal, siguiendo el arco de oposición. Solo entran
    las que encajan con el objetivo (umbral de relevancia): se filtran antes de elegir para que una
    ficha irrelevante no ocupe un hueco cuando hay otras relevantes sin usar. Los huecos que no se
    pueden cubrir quedan a None: los propone la IA, marcados como tales. `solo_directas` (para medir, no
    para generar) exige que la palabra del propio objetivo aparezca en la ficha: no vale un fundamento asociado."""
    relevantes = [e for e in filtrar_ejercicios(ejercicios, edad, objetivo)
                  if es_relevante(e, objetivo, con_asociados=not solo_directas)]
    return seleccionar_ejercicios(relevantes, n)


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


def _palabras_significativas(objetivo: str) -> list[str]:
    palabras = re.findall(r"[a-z0-9]+", _sin_acentos(objetivo))
    return [p for p in palabras
            if p not in _PALABRAS_VACIAS and (len(p) >= 4 or any(c.isdigit() for c in p))]


def es_relevante(ej: dict, objetivo: str, con_asociados: bool = True) -> bool:
    """¿Encaja el ejercicio con el objetivo? Sí si alguna palabra significativa del objetivo
    (o un fundamento analítico asociado a él) aparece al inicio de una palabra del nombre, la
    descripción o los tags tácticos. Si no encaja, ese hueco de la sesión lo propone la IA."""
    palabras = _palabras_significativas(objetivo)
    raices = {_raiz(p) for p in palabras}
    for clave, fundamentos in (COMPONENTES_ANALITICOS.items() if con_asociados else ()):
        clave_norm = _sin_acentos(clave)
        if any(clave_norm.startswith(r) or r.startswith(_raiz(clave_norm)) for r in raices):
            raices.update(_raiz(_sin_acentos(f)) for f in fundamentos)
    if not raices:
        return False
    tags = " ".join(ej.get("objetivos", {}).get("tacticos", []))
    texto = _sin_acentos(f"{ej.get('nombre', '')} {ej.get('descripcion', '')} {tags}")
    return any(re.search(rf"(?<!\w){re.escape(r)}", texto) for r in raices)
