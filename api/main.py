# api/main.py
import copy
import datetime
import json
import logging
import os
import re
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware

from rag_engine import (
    generar_sesion, generar_coordenadas_ejercicio,
    generar_ejercicio_unico, reprompt_ejercicio, responder_duda_reglamento,
    listar_ambitos, normalizar_ambito,
)
from diagram_renderer import render_diagram, render_all_diagrams
import fichas_edicion
from i18n_fichas import IDIOMA_BASE, IDIOMAS, localizar
from fichas_edicion import CAMPOS_DIAGRAMA, CAMPOS_EDITABLES, CAMPOS_OPCIONALES
from diagramas import _validar_diagrama
from validacion_fichas import _problemas_de_diagrama, validar_ficha
from plantillas import plantilla_para_texto
from resumen_objetivo import resumir_objetivo

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _svg_diagrama_no_disponible() -> str:
    """Placeholder visible cuando la generación automática de coordenadas falla
    (tras reintento) o el renderer lanza una excepción — antes se dejaba un
    hueco en blanco sin ninguna indicación de que algo había fallado. Lleva data-placeholder: la
    interfaz y el PDF no lo pintan (el ejercicio sale sin diagrama, sin avisos), pero conserva su
    posición en la lista."""
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 500 200" data-placeholder="1">'
        '<rect width="500" height="200" fill="#faf8f0" stroke="#2d3748" stroke-width="2"/>'
        '<text x="250" y="95" text-anchor="middle" font-family="sans-serif" font-size="15" '
        'font-weight="bold" fill="#2d3748">Diagrama no disponible</text>'
        '<text x="250" y="120" text-anchor="middle" font-family="sans-serif" font-size="12" '
        'fill="#6b7280">No se pudo generar automáticamente para este ejercicio.</text>'
        '</svg>'
    )


def _svg_sin_diagrama() -> str:
    """Recuadro neutro para las fichas marcadas «sin_diagrama» (juego libre, todos a la vez).
    Ocupa su sitio: el PDF asigna los diagramas por posición de ejercicio y un hueco
    desalinearía los siguientes."""
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 500 200" data-placeholder="1">'
        '<rect width="500" height="200" fill="#faf8f0" stroke="#cbd5e0" stroke-width="2"/>'
        '<text x="250" y="100" text-anchor="middle" font-family="sans-serif" font-size="14" '
        'fill="#6b7280">Juego libre: no necesita diagrama.</text>'
        '</svg>'
    )


def parsear_ejercicios_de_sesion(texto: str) -> list:
    """Extrae nombre y organización de cada ejercicio del texto de sesión generado.
    Reconoce tanto 'Ejercicio N:' como 'Ejercicio N.1:' / 'Ejercicio N.2 (variante):'
    cuando un ejercicio largo se ha partido en base + variante."""
    cab = r'Ejercicio \d+(?:\.\d+)?\s*(?:\([^)]*\))?\s*:'
    ejercicios = []
    partes = re.split(rf'\n(?=\s*{cab})', texto)
    for parte in partes:
        parte = parte.strip()
        m_cab = re.match(cab, parte)
        if not m_cab:
            continue
        cabecera_completa = parte[:m_cab.end()]
        resto_primera_linea = parte[m_cab.end():].split('\n', 1)[0]

        # Nombre: preferir el que va dentro del paréntesis ('variante de "X"'),
        # y si no, el texto tras los dos puntos EN LA MISMA LÍNEA (el modelo a veces
        # no repite el nombre ahí, así que no cruzamos a la línea de "Duración:").
        m_variante = re.search(r'variante de\s+"([^"]+)"', cabecera_completa, re.IGNORECASE)
        if m_variante:
            nombre = m_variante.group(1).strip()
        elif resto_primera_linea.strip():
            nombre = resto_primera_linea.strip().strip('"')
        else:
            continue

        m_org = re.search(
            rf'Organización[:\s]+(.*?)(?=Puntos clave:|Duración:|{cab}|$)',
            parte, re.DOTALL | re.IGNORECASE,
        )
        desc = m_org.group(1).strip() if m_org else ""

        # Variantes (N.2): "Qué cambia respecto a N.1:" va ANTES de "Organización:" en
        # la plantilla y describe la única diferencia real con la base — sin esto, el
        # diagrama de la variante se generaba sin saber qué la distingue del ejercicio base.
        m_cambio = re.search(
            rf'Qué cambia respecto a[^:\n]*:\s*(.*?)(?=Organización:|Puntos clave:|Duración:|{cab}|$)',
            parte, re.DOTALL | re.IGNORECASE,
        )
        if m_cambio and m_cambio.group(1).strip():
            cambio = m_cambio.group(1).strip().rstrip('.')
            desc = f"Cambio respecto al ejercicio base: {cambio}. {desc}".strip()

        ejercicios.append({"nombre": nombre, "descripcion": desc})
    return ejercicios


def parsear_calentamiento_y_vuelta(texto: str) -> list:
    """Extrae el juego de CALENTAMIENTO y VUELTA A LA CALMA para poder darles diagrama
    también — parsear_ejercicios_de_sesion solo captura los 'Ejercicio N:' de la parte
    principal, y estos dos bloques se quedaban siempre sin representación gráfica."""
    resultado = []
    for etiqueta, patron in (
        ("Calentamiento", r'\*\*CALENTAMIENTO[^\n]*\*\*(.*?)(?=\n---|\*\*PARTE PRINCIPAL|\Z)'),
        ("Vuelta a la calma", r'\*\*VUELTA A LA CALMA[^\n]*\*\*(.*?)(?=\*\*Fundamentos|\Z)'),
    ):
        m = re.search(patron, texto, re.DOTALL | re.IGNORECASE)
        if not m:
            continue
        bloque = m.group(1)
        m_juego = re.search(r'Juego:\s*([^\n]+)', bloque)
        if not m_juego:
            continue
        nombre = f"{etiqueta}: {m_juego.group(1).strip()}"
        m_reglas = re.search(r'Reglas:\s*(.*?)(?=Espacio:|\Z)', bloque, re.DOTALL)
        desc = m_reglas.group(1).strip() if m_reglas else bloque.strip()
        resultado.append({"nombre": nombre, "descripcion": desc})
    return resultado


# ── Defensa en profundidad: secret compartido con el proxy ──────────────────
# Si INTERNAL_SECRET está seteado, todas las requests deben llegar con el
# header "X-Internal-Secret: <valor>". Esto hace que la API solo acepte tráfico
# que pase por el proxy (NPM lo añade en la config Advanced del proxy host).
# Si no se setea, el middleware no se activa → no rompe desarrollo local.
INTERNAL_SECRET = os.environ.get("INTERNAL_SECRET", "")
PUBLIC_PATHS    = {"/"}      # con secreto, la documentación de la API (/docs, /openapi.json) tampoco es pública


class InternalSecretMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not INTERNAL_SECRET:
            return await call_next(request)
        if request.url.path in PUBLIC_PATHS:
            return await call_next(request)
        if request.headers.get("X-Internal-Secret") != INTERNAL_SECRET:
            return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
        return await call_next(request)


# ── Rate limiting ────────────────────────────────────────────────────────────
# Memory storage: válido para 1 worker uvicorn. Para más workers, usar redis://...
def _clave_de_limite(request: Request) -> str:
    """Quién cuenta para los límites: la cuenta que manda el frontend (solo se fía con INTERNAL_SECRET, que es lo que
    prueba que la petición viene de él) y, si no, la IP del cliente."""
    usuario = request.headers.get("X-Usuario", "")
    if INTERNAL_SECRET and re.fullmatch(r"\d{1,9}", usuario):
        return f"u{usuario}"
    return get_remote_address(request)


limiter = Limiter(key_func=_clave_de_limite)

app = FastAPI(title="MiPizarra API", version="0.3.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(InternalSecretMiddleware)


EXERCISES_PATH = os.environ.get("EXERCISES_PATH", "/app/data/exercises.json")
FEEDBACK_DIR   = os.environ.get("FEEDBACK_DIR",   "/app/data/sessions")

CATEGORIA_A_EDAD = {
    "Prebenjamín": "U8", "Benjamín": "U10", "Alevín": "U12",
    "Infantil": "U14", "Cadete": "U16", "Junior": "U18", "Senior": "U20"
}
EDAD_A_CATEGORIA = {v: k for k, v in CATEGORIA_A_EDAD.items()}

# ── Constantes de validación ────────────────────────────────────────────────
MAX_OBJETIVO_LEN  = 500       # caracteres
MIN_DURACION      = 30        # min
MAX_DURACION      = 180       # min
MAX_FEEDBACK_BYTES = 64 * 1024  # 64 KB por feedback


class SesionRequest(BaseModel):
    categoria:         Optional[str] = None
    edad:              Optional[str] = None
    duracion:          int  = Field(default=90, ge=MIN_DURACION, le=MAX_DURACION)
    objetivo:          str  = Field(default="defensa", min_length=1, max_length=MAX_OBJETIVO_LEN)
    generar_diagramas: bool = True
    max_jugadores:     Optional[int] = Field(default=None, ge=2, le=40)   # solo fichas que se puedan hacer con tantos o menos


class EjercicioRequest(BaseModel):
    categoria:  Optional[str] = None
    edad:       Optional[str] = None
    objetivo:   str = Field(default="tiro", min_length=1, max_length=MAX_OBJETIVO_LEN)
    descripcion: Optional[str] = Field(default=None, max_length=1000)


class RepromptRequest(BaseModel):
    categoria:   Optional[str] = None
    edad:        Optional[str] = None
    objetivo:    str = Field(default="", max_length=MAX_OBJETIVO_LEN)
    nombre:      str = Field(min_length=1, max_length=200)
    descripcion: str = Field(default="", max_length=2000)
    instruccion: str = Field(min_length=3, max_length=MAX_OBJETIVO_LEN)
    es_calentamiento: bool = False


class ReglamentoRequest(BaseModel):
    pregunta: str = Field(min_length=3, max_length=MAX_OBJETIVO_LEN)
    # "general" (FIBA / federación española) o una comunidad autónoma con carpeta propia en
    # data/reglamento/. Un valor no disponible no falla: se responde con el reglamento general.
    ambito: str = Field(default="general", max_length=30, pattern=r"^[a-z][a-z0-9_]{1,29}$")


class FeedbackRequest(BaseModel):
    timestamp:           Optional[str] = Field(default=None, max_length=32)
    edad:                Optional[str] = Field(default=None, max_length=32)
    duracion:            Optional[int] = Field(default=None, ge=0,  le=300)
    objetivo:            Optional[str] = Field(default=None, max_length=MAX_OBJETIVO_LEN)
    sesion_generada:     Optional[str] = Field(default=None, max_length=20000)
    cambios_realizados:  Optional[str] = Field(default=None, max_length=5000)
    rating:              Optional[int] = Field(default=None, ge=1, le=5)
    ejercicios_usados:   Optional[list] = None

    @field_validator("timestamp")
    @classmethod
    def _valida_ts(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        if not re.fullmatch(r"\d{8}_\d{6}", v):
            raise ValueError("timestamp debe ser AAAAMMDD_HHMMSS")
        return v


@app.get("/")
def root():
    return {"status": "ok", "version": "0.3.0"}


def _base_ejercicios() -> list:
    """exercises.json tal cual, sin los cambios del administrador."""
    try:
        with open(EXERCISES_PATH, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="Biblioteca de ejercicios no disponible")


@app.get("/ejercicios")
@limiter.limit("60/minute")
def listar_ejercicios(request: Request, lang: str = "es"):
    """La biblioteca. `lang=en` devuelve el texto en inglés de las fichas que lo tienen (el resto, en español)."""
    if lang not in IDIOMAS:
        raise HTTPException(status_code=422, detail=f"Idioma no soportado: {lang}")
    return [localizar(e, lang) for e in _base_ejercicios()] if lang != IDIOMA_BASE else _base_ejercicios()


# ── Administración de fichas ─────────────────────────────────────────────────
# Solo las llama el frontend, que comprueba que la cuenta es la del administrador (la API no tiene usuarios: su única
# barrera es el secreto interno). Los cambios se escriben en exercises.json (ver fichas_edicion.py).
ID_FICHA = re.compile(r"^ej_\d{3,}$")
MAX_BYTES_FICHA = 80_000


class FichaCambioRequest(BaseModel):
    ficha: dict


@app.get("/admin/fichas")
@limiter.limit("60/minute")
def admin_listar_fichas(request: Request):
    base = _base_ejercicios()
    ids = {f.get("id") for f in base}
    # «modificadas»: las que tienen una versión anterior a la que volver (ver fichas_edicion.py)
    return {"fichas": base, "modificadas": [i for i in fichas_edicion.ids_con_historial() if i in ids]}


def _limpiar_campos_de_ficha(crudo: dict) -> dict:
    """Solo los campos editables, con los textos recortados; los opcionales vacíos se quitan."""
    def limpio(v):
        if isinstance(v, str):
            return v.strip()
        if isinstance(v, list):
            return [limpio(x) for x in v if not (isinstance(x, str) and not x.strip())]
        if isinstance(v, dict):
            return {k: limpio(x) for k, x in v.items() if not (isinstance(x, str) and not x.strip())}
        return v

    campos = {k: limpio(crudo[k]) for k in CAMPOS_EDITABLES if k in crudo and k not in CAMPOS_DIAGRAMA}
    for k in CAMPOS_OPCIONALES:
        if k in campos and campos[k] in ("", [], {}, None):
            del campos[k]
    if "sin_diagrama" in crudo:         # el editor lo manda siempre: marca que el diagrama también viene en la petición
        campos["sin_diagrama"] = bool(crudo["sin_diagrama"])
        if not campos["sin_diagrama"]:
            if isinstance(crudo.get("diagramas"), list) and crudo["diagramas"]:
                campos["diagramas"] = [_sanear_diagrama(d) for d in crudo["diagramas"]]
            elif crudo.get("diagrama"):
                campos["diagrama"] = _sanear_diagrama(crudo["diagrama"])
    return campos


_CLAVES_DIAGRAMA = {"tipo", "titulo", "jugadores_ataque", "jugadores_defensa", "balon_inicio", "movimientos", "conos"}
_CLAVES_MOVIMIENTO = {"de", "a", "a_pos", "tipo", "orden", "curva"}


def _sanear_diagrama(d):
    """Solo las claves que entiende el renderizador, con textos recortados (no valida: eso lo hace la validación)."""
    if not isinstance(d, dict):
        return d

    def de_lista(clave, permitidas):
        lista = d.get(clave)
        if not isinstance(lista, list):
            return lista
        return [{k: v for k, v in x.items() if k in permitidas} if isinstance(x, dict) else x for x in lista]

    s = {k: v for k, v in d.items() if k in _CLAVES_DIAGRAMA}
    for clave in ("jugadores_ataque", "jugadores_defensa"):
        if clave in s:
            s[clave] = de_lista(clave, {"id", "x", "y", "rol"})
    if "conos" in s:
        s["conos"] = de_lista("conos", {"x", "y"})
    if "movimientos" in s:
        s["movimientos"] = de_lista("movimientos", _CLAVES_MOVIMIENTO)
    if isinstance(s.get("balon_inicio"), dict):
        s["balon_inicio"] = {k: v for k, v in s["balon_inicio"].items() if k == "portador"}
    if isinstance(s.get("titulo"), str):
        s["titulo"] = s["titulo"].strip()
        if not s["titulo"]:
            del s["titulo"]
    return s


def _diagrama_valido(d, etiqueta: str = "diagrama"):
    """(diagrama tal como se dibujará, problemas). El diagrama devuelto es el que la validación deja tras sus
    reparaciones deterministas (separar jugadores pegados, deducir `a_pos`): lo que se guarda es lo que se ve."""
    if not isinstance(d, dict):
        return None, [f"{etiqueta}: no es un objeto"]
    try:
        problemas = _problemas_de_diagrama({"diagrama": copy.deepcopy(d)})
        reparado = copy.deepcopy(d)
        if not problemas:
            _validar_diagrama(reparado, "")
    except Exception as e:        # un diagrama mal formado puede romper el validador
        return None, [f"{etiqueta}: no se puede validar ({type(e).__name__})"]
    if problemas:
        return None, [p.replace("diagrama 1", etiqueta, 1) for p in problemas]
    return reparado, []


@app.put("/admin/fichas/{ficha_id}")
@limiter.limit("60/minute")
def admin_guardar_ficha(request: Request, ficha_id: str, req: FichaCambioRequest):
    if not ID_FICHA.match(ficha_id):
        raise HTTPException(status_code=400, detail="Identificador de ficha no válido")
    if len(json.dumps(req.ficha, ensure_ascii=False)) > MAX_BYTES_FICHA:
        raise HTTPException(status_code=413, detail="La ficha es demasiado grande")
    base = _base_ejercicios()
    original = next((f for f in base if f.get("id") == ficha_id), None)
    if original is None:
        raise HTTPException(status_code=404, detail="No existe esa ficha")
    campos = _limpiar_campos_de_ficha(req.ficha)
    problemas: list[str] = []
    if "sin_diagrama" in campos:
        if "diagramas" in campos:
            for i, d in enumerate(campos["diagramas"], start=1):
                campos["diagramas"][i - 1], malos = _diagrama_valido(d, f"diagrama {i}")
                problemas += malos
        elif "diagrama" in campos:
            campos["diagrama"], malos = _diagrama_valido(campos["diagrama"])
            problemas += malos
    candidata = fichas_edicion.combinar(original, campos)
    if not problemas:
        otras = [f for f in base if f.get("id") != ficha_id]
        problemas = validar_ficha(candidata, otras)
    jm = candidata.get("jugadores_minimos")
    if not (isinstance(jm, int) and not isinstance(jm, bool) and 1 <= jm <= 40):
        problemas.append("jugadores_minimos: entero entre 1 y 40")
    if problemas:
        return JSONResponse(status_code=422, content={"detail": "La ficha no es válida", "problemas": problemas})
    guardada = fichas_edicion.guardar(EXERCISES_PATH, ficha_id, campos)
    return {"ok": True, "ficha": guardada if guardada is not None else candidata}


class DiagramaVistaRequest(BaseModel):
    diagrama: dict


@app.post("/admin/diagrama/vista")
@limiter.limit("240/minute")
def admin_vista_diagrama(request: Request, req: DiagramaVistaRequest):
    """El diagrama tal como lo verán en las sesiones (mismo dibujo), o por qué no es válido."""
    if len(json.dumps(req.diagrama, ensure_ascii=False)) > MAX_BYTES_FICHA:
        raise HTTPException(status_code=413, detail="El diagrama es demasiado grande")
    d, problemas = _diagrama_valido(_sanear_diagrama(req.diagrama))
    if problemas:
        return JSONResponse(status_code=422, content={"detail": "El diagrama no es válido", "problemas": problemas})
    return {"svg": render_diagram(copy.deepcopy(d)), "diagrama": d}


@app.delete("/admin/fichas/{ficha_id}")
@limiter.limit("60/minute")
def admin_restaurar_ficha(request: Request, ficha_id: str):
    if not ID_FICHA.match(ficha_id):
        raise HTTPException(status_code=400, detail="Identificador de ficha no válido")
    if not any(f.get("id") == ficha_id for f in _base_ejercicios()):
        raise HTTPException(status_code=404, detail="No existe esa ficha")
    anterior = fichas_edicion.volver_atras(EXERCISES_PATH, ficha_id)
    if anterior is None:
        raise HTTPException(status_code=404, detail="Esa ficha no tiene una versión anterior")
    return {"ok": True, "ficha": anterior}


@app.post("/generar")
@limiter.limit("10/hour;3/minute")
async def generar_entrenamiento(request: Request, req: SesionRequest):
    if req.edad:
        edad = req.edad
    elif req.categoria:
        edad = CATEGORIA_A_EDAD.get(req.categoria, "U16")
    else:
        edad = "U16"

    logger.info(f"Generando sesión: edad={edad}, duracion={req.duracion}, objetivo={req.objetivo[:60]}")

    try:
        resultado = generar_sesion(edad=edad, duracion=req.duracion, objetivo=req.objetivo,
                                  max_jugadores=req.max_jugadores)
    except Exception:
        logger.exception("Error en generar_sesion")
        raise HTTPException(status_code=500, detail="No se pudo generar la sesión")

    diagramas = []
    if req.generar_diagramas:
        ejercicios_del_texto = parsear_ejercicios_de_sesion(resultado["texto"])
        ejercicios_db = resultado.get("ejercicios_usados", [])

        ejercicios_con_descripcion = []
        # Hasta 12: la parte principal tiene hasta 6 ejercicios y cada uno puede venir partido en
        # base + variante (N.1/N.2) cuando la ficha trae progresión y la duración supera lo que
        # esa edad aguanta.
        # La base usa el diagrama guardado de la ficha; la variante (mismo nombre,
        # segunda aparición) describe un cambio distinto, así que genera el suyo
        # propio en vez de repetir el mismo diagrama dos veces.
        ids_ya_usados = set()
        for i, ej_texto in enumerate(ejercicios_del_texto[:12]):
            # Si el nombre que puso el modelo no coincide (ni de lejos) con ningún
            # ejercicio de la biblioteca, NO caer a "el i-ésimo de la lista" — eso
            # asignaba el diagrama de un ejercicio de biblioteca totalmente distinto
            # (p.ej. uno con conos y defensor) a un ejercicio inventado sin relación.
            # Mejor tratarlo como "sin ficha" y que se genere uno propio a partir de
            # la descripción real más abajo.
            ej_db = next(
                (e for e in ejercicios_db if e.get("nombre", "").lower() in ej_texto["nombre"].lower()
                 or ej_texto["nombre"].lower() in e.get("nombre", "").lower()),
                {}
            )
            es_variante = ej_db.get("id") and ej_db.get("id") in ids_ya_usados
            if ej_db.get("id"):
                ids_ya_usados.add(ej_db["id"])

            ejercicios_con_descripcion.append({
                "nombre":      ej_texto["nombre"],
                "descripcion": ej_texto["descripcion"] or ("" if es_variante else ej_db.get("descripcion", "")),
                "diagrama":    None if es_variante else ej_db.get("diagrama"),
                "id":          f"{ej_db.get('id', f'ej_texto_{i}')}{'_variante' if es_variante else ''}",
                "sin_diagrama": bool(ej_db.get("sin_diagrama")),
                # el diagrama de una ficha ya trae su tipo de pista: la heurística de «pista completa» por palabras
                # del texto solo vale para los diagramas que genera el modelo
                "de_plantilla": bool(ej_db.get("diagrama") and not es_variante),
            })

        if not ejercicios_con_descripcion:
            ejercicios_con_descripcion = ejercicios_db[:4]

        # Calentamiento y vuelta a la calma son juegos inventados por el modelo, sin
        # entrada en exercises.json — igual se benefician de diagrama automático.
        for extra in parsear_calentamiento_y_vuelta(resultado["texto"]):
            momento = extra["nombre"].split(":")[0].strip().lower().replace(" ", "_")
            # Si el juego es uno estándar (zigzag, rondo, estiramientos...) se usa la plantilla
            # validada; si no encaja ninguna, se genera el diagrama como antes.
            ficha_cal = resultado.get("calentamiento_ficha") if momento == "calentamiento" else None
            if ficha_cal:
                # Calentamiento de la biblioteca: lleva su propio diagrama (o es juego libre, sin diagrama).
                ejercicios_con_descripcion.append({
                    "nombre":       extra["nombre"],
                    "descripcion":  extra["descripcion"],
                    "diagrama":     ficha_cal.get("diagrama"),
                    "diagramas":    ficha_cal.get("diagramas"),
                    "sin_diagrama": bool(ficha_cal.get("sin_diagrama")),
                    "de_plantilla": True,       # diagrama ya curado: no se le aplica la heurística de pista completa
                    "id":           momento,
                })
                continue
            de_plantilla = plantilla_para_texto(momento, f"{extra['nombre']} {extra['descripcion']}")
            ejercicios_con_descripcion.append({
                "nombre":      extra["nombre"],
                "descripcion": extra["descripcion"],
                "diagrama":    de_plantilla,
                "de_plantilla": de_plantilla is not None,
                "id":          momento,
            })

        logger.info(f"Intentando generar {len(ejercicios_con_descripcion)} diagramas")

        for idx, ej in enumerate(ejercicios_con_descripcion):
            nombre = ej.get("nombre", f"Ejercicio {idx+1}")
            desc   = ej.get("descripcion", "")

            FULL_COURT = ["transición", "contraataque", "campo a campo", "pista completa",
                          "continuo", "salida rápida", "fastbreak", "2c1", "3c2", "2 contra 1",
                          "3 contra 2", "presión", "campo completo", "toda la pista"]

            # Ejercicio con múltiples diagramas (bloqueo directo, jugadas en fases, etc.)
            if ej.get("diagramas"):
                try:
                    for d in render_all_diagrams(ej, edad=edad):
                        diagramas.append({
                            "id":     ej.get("id", f"ej_{idx}"),
                            "nombre": nombre,
                            "titulo": d["titulo"],
                            "svg":    d["svg"],
                        })
                except Exception:
                    logger.exception(f"Error renderizando diagramas de '{nombre}'")
                    diagramas.append({
                        "id":     ej.get("id", f"ej_{idx}"),
                        "nombre": nombre,
                        "titulo": "",
                        "svg":    _svg_diagrama_no_disponible(),
                    })
                continue

            # Ficha marcada «sin_diagrama» (juego libre): recuadro neutro, no se intenta dibujar.
            if ej.get("sin_diagrama") and not ej.get("diagrama"):
                diagramas.append({
                    "id":     ej.get("id", f"ej_{idx}"),
                    "nombre": nombre,
                    "titulo": "",
                    "svg":    _svg_sin_diagrama(),
                })
                continue

            # Ejercicio con un único diagrama (o sin diagrama → generar automático)
            diagrama_data = ej.get("diagrama")
            if not diagrama_data:
                texto_para_diagrama = desc if desc else nombre
                logger.info(f"→ Generando diagrama automático para: {nombre}")
                diagrama_data = generar_coordenadas_ejercicio(texto_para_diagrama, nombre)

            if diagrama_data:
                if desc and not ej.get("de_plantilla") and any(word in desc.lower() for word in FULL_COURT):
                    diagrama_data["tipo"] = "pista_completa"
                else:
                    diagrama_data["tipo"] = diagrama_data.get("tipo", "media_pista")

                try:
                    svg = render_diagram(diagrama_data, edad=edad)
                except Exception:
                    logger.exception(f"Error renderizando diagrama de '{nombre}'")
                    svg = _svg_diagrama_no_disponible()
                diagramas.append({
                    "id":     ej.get("id", f"ej_{idx}"),
                    "nombre": nombre,
                    "titulo": "",
                    "svg":    svg,
                })
            else:
                logger.warning(f"  ✗ No se pudo generar diagrama para '{nombre}', se muestra aviso")
                diagramas.append({
                    "id":     ej.get("id", f"ej_{idx}"),
                    "nombre": nombre,
                    "titulo": "",
                    "svg":    _svg_diagrama_no_disponible(),
                })

        logger.info(f"Total diagramas generados: {len(diagramas)}")

    return {
        "sesion":    resultado["texto"],
        "duracion":  req.duracion,
        "edad":      edad,
        "objetivo":  req.objetivo,
        "objetivo_resumen": resumir_objetivo(req.objetivo),
        "diagramas": diagramas,
        "teoria_usada": resultado.get("teoria_usada", False),
        "avisos":    resultado.get("avisos", []),
        "ejercicios_usados": [
            {
                "id":            e.get("id", ""),
                "nombre":        e.get("nombre", ""),
                "duracion_min":  e.get("duracion_min", 0),
                "tiene_diagrama": ("diagrama" in e or "diagramas" in e),
            }
            for e in resultado.get("ejercicios_usados", [])
        ],
    }


@app.post("/ejercicio")
@limiter.limit("20/hour;5/minute")
async def generar_ejercicio(request: Request, req: EjercicioRequest):
    """Modo 2: genera un único ejercicio con diagrama."""
    edad = req.edad or (CATEGORIA_A_EDAD.get(req.categoria, "U16") if req.categoria else "U16")
    logger.info(f"Generando ejercicio: edad={edad}, objetivo={req.objetivo[:60]}")
    try:
        resultado = generar_ejercicio_unico(
            edad=edad, objetivo=req.objetivo, descripcion=req.descripcion or ""
        )
    except Exception:
        logger.exception("Error en generar_ejercicio_unico")
        raise HTTPException(status_code=500, detail="No se pudo generar el ejercicio")

    svgs = []
    if resultado.get("diagrama") or resultado.get("diagramas"):
        try:
            for d in render_all_diagrams(resultado, edad=edad):
                svgs.append(d)
        except Exception:
            logger.exception("Error renderizando diagrama del ejercicio")

    return {"ejercicio": resultado, "diagramas": svgs}


@app.post("/reprompt_ejercicio")
@limiter.limit("20/hour;5/minute")
async def corregir_ejercicio(request: Request, req: RepromptRequest):
    """Regenera un ejercicio ya existente de una sesión aplicando una corrección
    pedida por el entrenador (texto y/o diagrama), sin tocar el resto de la sesión."""
    edad = req.edad or (CATEGORIA_A_EDAD.get(req.categoria, "U16") if req.categoria else "U16")
    logger.info(f"Reprompt ejercicio: edad={edad}, nombre={req.nombre[:60]}, instruccion={req.instruccion[:80]}")
    try:
        resultado = reprompt_ejercicio(
            edad=edad, objetivo=req.objetivo, nombre=req.nombre,
            descripcion=req.descripcion, instruccion=req.instruccion,
            es_calentamiento=req.es_calentamiento,
        )
    except Exception:
        logger.exception("Error en reprompt_ejercicio")
        raise HTTPException(status_code=500, detail="No se pudo corregir el ejercicio")

    if not resultado:
        raise HTTPException(status_code=500, detail="No se pudo corregir el ejercicio")

    svgs = []
    if resultado.get("diagrama") or resultado.get("diagramas"):
        try:
            for d in render_all_diagrams(resultado, edad=edad):
                svgs.append(d)
        except Exception:
            logger.exception("Error renderizando diagrama del ejercicio corregido")

    return {"ejercicio": resultado, "diagramas": svgs}


@app.post("/reglamento")
@limiter.limit("30/hour;10/minute")
async def consulta_reglamento(request: Request, req: ReglamentoRequest):
    """Modo 3: responde dudas de reglamento y fundamentos técnicos."""
    ambito = normalizar_ambito(req.ambito)
    logger.info(f"Consulta reglamento [{ambito}]: {req.pregunta[:80]}")
    try:
        respuesta = responder_duda_reglamento(req.pregunta, ambito)
    except Exception:
        logger.exception("Error en responder_duda_reglamento")
        raise HTTPException(status_code=500, detail="No se pudo responder la consulta")
    return {"pregunta": req.pregunta, "ambito": ambito, "respuesta": respuesta}


@app.get("/ambitos_reglamento")
@limiter.limit("60/minute")
async def ambitos_reglamento(request: Request):
    """Ámbitos de reglamento disponibles: "general" más una entrada por comunidad autónoma."""
    return {"ambitos": listar_ambitos()}


@app.post("/guardar_feedback")
@limiter.limit("20/hour")
async def guardar_feedback(request: Request, feedback: FeedbackRequest):
    # Tamaño total (rechazo por si Pydantic pasa pero el serializado es enorme)
    payload = feedback.model_dump(exclude_none=True)
    if len(json.dumps(payload).encode("utf-8")) > MAX_FEEDBACK_BYTES:
        raise HTTPException(status_code=413, detail="Feedback demasiado grande")

    os.makedirs(FEEDBACK_DIR, exist_ok=True)
    ts = feedback.timestamp or datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    # ts ya validado por Pydantic con regex AAAAMMDD_HHMMSS → no admite '/', '..', etc.
    filepath = os.path.join(FEEDBACK_DIR, f"sesion_{ts}.json")

    # Defensa en profundidad: comprobar que la ruta resuelta cae dentro de FEEDBACK_DIR
    if os.path.commonpath([os.path.realpath(filepath), os.path.realpath(FEEDBACK_DIR)]) != os.path.realpath(FEEDBACK_DIR):
        raise HTTPException(status_code=400, detail="Ruta inválida")

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return {"status": "ok", "saved_to": os.path.basename(filepath)}


@app.get("/sesiones_guardadas")
@limiter.limit("30/minute")
async def listar_sesiones_guardadas(request: Request):
    if not os.path.exists(FEEDBACK_DIR):
        return {"sesiones": []}
    sesiones = []
    for filename in sorted(os.listdir(FEEDBACK_DIR), reverse=True):
        if not filename.endswith(".json"):
            continue
        if not re.fullmatch(r"sesion_\d{8}_\d{6}\.json", filename):
            continue
        filepath = os.path.join(FEEDBACK_DIR, filename)
        try:
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)
            sesiones.append({
                "timestamp": data.get("timestamp"),
                "edad":      data.get("edad"),
                "objetivo":  data.get("objetivo"),
                "rating":    data.get("rating"),
                "archivo":   filename,
            })
        except (json.JSONDecodeError, OSError):
            logger.warning(f"Sesión guardada ilegible: {filename}")
            continue
    return {"sesiones": sesiones, "total": len(sesiones)}
