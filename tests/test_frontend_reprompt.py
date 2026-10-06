# tests/test_frontend_reprompt.py
"""formatEjercicioTexto (frontend/pizarra/templates/pizarra/index.html): reconstruye el bloque de un ejercicio
corregido con el reprompt. Se ejecuta con Node, extrayendo la función de la plantilla; se omite si no hay Node."""
import json
import re
import shutil
import subprocess

import pytest

from conftest import RAIZ
from main import parsear_ejercicios_de_sesion

PLANTILLA = RAIZ / "frontend" / "pizarra" / "templates" / "pizarra" / "index.html"
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="Node no está instalado")


def _funcion() -> str:
    html = PLANTILLA.read_text(encoding="utf-8")
    m = re.search(r"function formatEjercicioTexto\(.*?\n\}\n", html, re.DOTALL)
    assert m, "no se encuentra formatEjercicioTexto en la plantilla"
    return m.group(0)


def formatear(cabecera: str, ej: dict, original: dict) -> str:
    codigo = _funcion() + f"\nprocess.stdout.write(formatEjercicioTexto({json.dumps(cabecera)}, " \
                          f"{json.dumps(ej)}, {json.dumps(original)}));"
    r = subprocess.run(["node", "-e", codigo], capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert r.returncode == 0, r.stderr
    return r.stdout


ORIGINAL = {"descripcion": "Texto original.\nDuración: 15 min", "nombre": "Original"}
CORREGIDO = {"nombre": "1 contra 1 sin defensor", "duracion_min": 10,
             "descripcion": "A1 recibe en el codo y bota dos veces con la mano izquierda antes de tirar.",
             "puntos_clave": ["Dos botes con la izquierda.", "Mirar al aro antes de decidir."]}


def test_el_bloque_corregido_conserva_la_descripcion_nueva_y_el_formato_de_la_sesion():
    assert formatear("Ejercicio 2", CORREGIDO, ORIGINAL) == (
        "Ejercicio 2: 1 contra 1 sin defensor\n"
        "Duración: 10 min\n"
        "Organización:\n"
        "A1 recibe en el codo y bota dos veces con la mano izquierda antes de tirar.\n"
        "Puntos clave:\n"
        "- Dos botes con la izquierda.\n"
        "- Mirar al aro antes de decidir."
    )


def test_la_duracion_original_se_conserva_si_la_correccion_no_trae_una():
    texto = formatear("Ejercicio 1", {k: v for k, v in CORREGIDO.items() if k != "duracion_min"}, ORIGINAL)
    assert "Duración: 15 min" in texto


def test_sin_descripcion_ni_objetivos_no_se_deja_una_etiqueta_vacia():
    texto = formatear("Ejercicio 1", {"nombre": "X", "puntos_clave": ["Uno."]}, ORIGINAL)
    assert "Organización" not in texto and "- Uno." in texto


def test_el_bloque_corregido_lo_entiende_el_analizador_de_la_api():
    # lo que el navegador reconstruye es lo que luego recibe el PDF y el analizador de diagramas
    bloque = formatear("Ejercicio 2", CORREGIDO, ORIGINAL)
    parseados = parsear_ejercicios_de_sesion(bloque)
    assert [p["nombre"] for p in parseados] == ["1 contra 1 sin defensor"]
    assert parseados[0]["descripcion"] == CORREGIDO["descripcion"]


# ── diagramas: la corrección sustituye en su sitio y, si no trae diagrama, se conserva el que había ──────────

def _reemplazar(diagramas, diag_nombre, nuevo_nombre, nuevos):
    html = PLANTILLA.read_text(encoding="utf-8")
    m = re.search(r"function reemplazarDiagramas\(.*?\n\}\n", html, re.DOTALL)
    assert m, "no se encuentra reemplazarDiagramas en la plantilla"
    codigo = m.group(0) + (f"\nprocess.stdout.write(JSON.stringify(reemplazarDiagramas({json.dumps(diagramas)}, "
                           f"{json.dumps(diag_nombre)}, {json.dumps(nuevo_nombre)}, {json.dumps(nuevos)})));")
    r = subprocess.run(["node", "-e", codigo], capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


SESION = [{"id": "a", "nombre": "A", "titulo": "", "svg": "<svg>A</svg>"},
          {"id": "b", "nombre": "B", "titulo": "fase 1", "svg": "<svg>B1</svg>"},
          {"id": "b", "nombre": "B", "titulo": "fase 2", "svg": "<svg>B2</svg>"},
          {"id": "c", "nombre": "C", "titulo": "", "svg": "<svg>C</svg>"}]


def test_un_diagrama_nuevo_sustituye_al_viejo_en_su_misma_posicion():
    r = _reemplazar(SESION, "B", "B corregido", [{"titulo": "", "svg": "<svg>NUEVO</svg>"}])
    assert [d["svg"] for d in r] == ["<svg>A</svg>", "<svg>NUEVO</svg>", "<svg>C</svg>"]
    assert r[1]["nombre"] == "B corregido" and r[1]["id"] == "B"


def test_si_la_correccion_no_trae_diagrama_se_conserva_el_que_habia():
    assert _reemplazar(SESION, "B", "B", []) == SESION


def test_los_diagramas_de_los_demas_ejercicios_no_se_tocan():
    r = _reemplazar(SESION, "A", "A2", [{"titulo": "x", "svg": "<svg>X</svg>"}])
    assert [d["svg"] for d in r][1:] == ["<svg>B1</svg>", "<svg>B2</svg>", "<svg>C</svg>"]
