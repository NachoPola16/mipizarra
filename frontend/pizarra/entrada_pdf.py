"""Validación de lo que llega a /pdf/ (entrada del navegador, no confiable).

Solo biblioteca estándar. Rechaza tipos erróneos y tamaños desmedidos (un cuerpo de ~2 MB tumbaba un worker de 128 MB)
y deja pasar únicamente los SVG que dibuja `api/diagram_renderer.py`: sin DOCTYPE/entidades, sin referencias externas
(`href`), sin scripts ni estilos y con un tope de elementos (un `<use>` anidado tardaba 14 s en renderizarse).
"""
import re
import xml.etree.ElementTree as _ET          # solo para la excepción ParseError

try:                                           # en el contenedor viene con cairosvg
    from defusedxml import ElementTree as ET
except ImportError:                            # el filtro de «<!» de svg_permitido ya impide entidades
    ET = _ET

MAX_SESION = 60_000
MAX_CAMPO = 500
MAX_DIAGRAMAS = 30
MAX_SVG = 150_000
MAX_ELEMENTOS = 1_500
MAX_DIMENSION = 5_000

_ETIQUETAS = {'svg', 'g', 'defs', 'marker', 'rect', 'line', 'path', 'circle', 'ellipse', 'polygon', 'polyline',
              'text', 'tspan'}
_NUMERO = re.compile(r'^\s*(\d+(?:\.\d+)?)\s*(?:px)?\s*$')


def _local(nombre):
    return nombre.rsplit('}', 1)[-1]


def svg_permitido(svg):
    """True si `svg` es un SVG simple, sin recursos externos ni construcciones que disparen el coste."""
    if not isinstance(svg, str) or not svg or len(svg) > MAX_SVG:
        return False
    if '<!' in svg.replace('<!--', ''):          # DOCTYPE, ENTITY, CDATA: ninguno hace falta
        return False
    try:
        raiz = ET.fromstring(svg)
    except (_ET.ParseError, ValueError):       # defusedxml avisa con ValueError (entidades, DTD)
        return False
    if _local(raiz.tag) != 'svg':
        return False
    n = 0
    for el in raiz.iter():
        n += 1
        if n > MAX_ELEMENTOS or not isinstance(el.tag, str) or _local(el.tag) not in _ETIQUETAS:
            return False
        for atributo in el.attrib:
            nombre = _local(atributo).lower()
            if nombre == 'href' or nombre.startswith('on') or nombre == 'style':
                return False
    for dim in ('width', 'height'):
        valor = raiz.attrib.get(dim)
        if valor is not None:
            m = _NUMERO.match(valor)
            if not m or float(m.group(1)) > MAX_DIMENSION:
                return False
    return True


def _texto(valor, defecto, maximo):
    if valor is None:
        return defecto
    if not isinstance(valor, str):
        raise ValueError('campo de texto no válido')
    if len(valor) > maximo:
        raise ValueError('campo demasiado largo')
    return valor


def limpiar_entrada_pdf(data):
    """Cuerpo JSON de /pdf/ → (sesion, edad, objetivo, duracion, diagramas) ya saneados. ValueError si no vale.
    Un diagrama que no pasa `svg_permitido` se omite (el PDF sale igualmente, sin ese dibujo)."""
    if not isinstance(data, dict):
        raise ValueError('cuerpo no válido')
    sesion = _texto(data.get('sesion'), '', MAX_SESION)
    edad = _texto(data.get('edad'), 'General', 32) or 'General'
    objetivo = _texto(data.get('objetivo'), '', MAX_CAMPO)
    duracion = data.get('duracion', 0)
    if isinstance(duracion, bool) or not isinstance(duracion, (int, float)):
        duracion = 0
    duracion = max(0, min(int(duracion), 300))
    crudos = data.get('diagramas') or []
    if not isinstance(crudos, list) or len(crudos) > MAX_DIAGRAMAS:
        raise ValueError('diagramas no válidos')
    diagramas = []
    for d in crudos:
        if not isinstance(d, dict):
            raise ValueError('diagrama no válido')
        if not svg_permitido(d.get('svg', '')):
            continue
        diagramas.append({
            'id': _texto(d.get('id'), '', 80),
            'nombre': _texto(d.get('nombre'), '', 200),
            'titulo': _texto(d.get('titulo'), '', 200),
            'svg': d['svg'],
        })
    return sesion, edad, objetivo, duracion, diagramas
