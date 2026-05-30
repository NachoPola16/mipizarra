# api/main.py
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
    generar_ejercicio_unico, responder_duda_reglamento,
)
from diagram_renderer import render_diagram, render_all_diagrams

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def parsear_ejercicios_de_sesion(texto: str) -> list:
    """Extrae nombre y organización de cada ejercicio del texto de sesión generado."""
    ejercicios = []
    partes = re.split(r'\n(?=Ejercicio \d+:)', texto)
    for parte in partes:
        m = re.match(r'Ejercicio \d+:\s*"?([^"\n]+)"?', parte.strip())
        if not m:
            continue
        nombre = m.group(1).strip().strip('"')
        m_org = re.search(
            r'Organización[:\s]+(.*?)(?=Puntos clave:|Duración:|Ejercicio \d+:|$)',
            parte, re.DOTALL | re.IGNORECASE,
        )
        desc = m_org.group(1).strip() if m_org else ""
        ejercicios.append({"nombre": nombre, "descripcion": desc})
    return ejercicios


# ── Defensa en profundidad: secret compartido con el proxy ──────────────────
# Si INTERNAL_SECRET está seteado, todas las requests deben llegar con el
# header "X-Internal-Secret: <valor>". Esto hace que la API solo acepte tráfico
# que pase por el proxy (NPM lo añade en la config Advanced del proxy host).
# Si no se setea, el middleware no se activa → no rompe desarrollo local.
INTERNAL_SECRET = os.environ.get("INTERNAL_SECRET", "")
PUBLIC_PATHS    = {"/", "/docs", "/openapi.json", "/redoc"}


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
limiter = Limiter(key_func=get_remote_address)

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


class EjercicioRequest(BaseModel):
    categoria:  Optional[str] = None
    edad:       Optional[str] = None
    objetivo:   str = Field(default="tiro", min_length=1, max_length=MAX_OBJETIVO_LEN)
    descripcion: Optional[str] = Field(default=None, max_length=1000)


class ReglamentoRequest(BaseModel):
    pregunta: str = Field(min_length=3, max_length=MAX_OBJETIVO_LEN)


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


@app.get("/ejercicios")
@limiter.limit("60/minute")
def listar_ejercicios(request: Request):
    try:
        with open(EXERCISES_PATH, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="Biblioteca de ejercicios no disponible")


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
        resultado = generar_sesion(edad=edad, duracion=req.duracion, objetivo=req.objetivo)
    except Exception:
        logger.exception("Error en generar_sesion")
        raise HTTPException(status_code=500, detail="No se pudo generar la sesión")

    diagramas = []
    if req.generar_diagramas:
        ejercicios_del_texto = parsear_ejercicios_de_sesion(resultado["texto"])
        ejercicios_db = resultado.get("ejercicios_usados", [])

        ejercicios_con_descripcion = []
        for i, ej_texto in enumerate(ejercicios_del_texto[:3]):
            ej_db = next(
                (e for e in ejercicios_db if e.get("nombre", "").lower() in ej_texto["nombre"].lower()
                 or ej_texto["nombre"].lower() in e.get("nombre", "").lower()),
                ejercicios_db[i] if i < len(ejercicios_db) else {}
            )
            ejercicios_con_descripcion.append({
                "nombre":      ej_texto["nombre"],
                "descripcion": ej_texto["descripcion"] or ej_db.get("descripcion", ""),
                "diagrama":    ej_db.get("diagrama"),
                "id":          ej_db.get("id", f"ej_texto_{i}"),
            })

        if not ejercicios_con_descripcion:
            ejercicios_con_descripcion = ejercicios_db[:4]

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
                continue

            # Ejercicio con un único diagrama (o sin diagrama → generar automático)
            diagrama_data = ej.get("diagrama")
            if not diagrama_data:
                texto_para_diagrama = desc if desc else nombre
                logger.info(f"→ Generando diagrama automático para: {nombre}")
                diagrama_data = generar_coordenadas_ejercicio(texto_para_diagrama, nombre)

            if diagrama_data:
                if desc and any(word in desc.lower() for word in FULL_COURT):
                    diagrama_data["tipo"] = "pista_completa"
                else:
                    diagrama_data["tipo"] = diagrama_data.get("tipo", "media_pista")

                try:
                    svg = render_diagram(diagrama_data, edad=edad)
                    diagramas.append({
                        "id":     ej.get("id", f"ej_{idx}"),
                        "nombre": nombre,
                        "titulo": "",
                        "svg":    svg,
                    })
                except Exception:
                    logger.exception(f"Error renderizando diagrama de '{nombre}'")

        logger.info(f"Total diagramas generados: {len(diagramas)}")

    return {
        "sesion":    resultado["texto"],
        "diagramas": diagramas,
        "teoria_usada": resultado.get("teoria_usada", False),
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


@app.post("/reglamento")
@limiter.limit("30/hour;10/minute")
async def consulta_reglamento(request: Request, req: ReglamentoRequest):
    """Modo 3: responde dudas de reglamento y fundamentos técnicos."""
    logger.info(f"Consulta reglamento: {req.pregunta[:80]}")
    try:
        respuesta = responder_duda_reglamento(req.pregunta)
    except Exception:
        logger.exception("Error en responder_duda_reglamento")
        raise HTTPException(status_code=500, detail="No se pudo responder la consulta")
    return {"pregunta": req.pregunta, "respuesta": respuesta}


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
