import json
import re
import os
import tempfile
import logging
from pathlib import Path

import requests
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .entrada_pdf import limpiar_entrada_pdf

logger = logging.getLogger(__name__)


def _api_headers():
    """Headers para llamadas internas a la API (incluye el secreto si está configurado)."""
    h = {'Content-Type': 'application/json'}
    secret = getattr(settings, 'INTERNAL_SECRET', '')
    if secret:
        h['X-Internal-Secret'] = secret
    return h


def _error_respuesta(e, generico):
    """Respuesta de error para el navegador sin filtrar rutas internas ni trazas: 429 y los mensajes propios de la API
    (cadena en `detail`, 4xx) se muestran; todo lo demás, el texto genérico."""
    resp = getattr(e, 'response', None)
    status = getattr(resp, 'status_code', None)
    if status == 429:
        return JsonResponse({'error': 'Demasiadas peticiones seguidas. Espera un momento e inténtalo de nuevo.'}, status=429)
    if status and 400 <= status < 500:
        try:
            detalle = resp.json().get('detail')
        except Exception:
            detalle = None
        if isinstance(detalle, str) and len(detalle) <= 300:
            return JsonResponse({'error': detalle}, status=status)
        return JsonResponse({'error': 'Los datos enviados no son válidos.'}, status=400)
    return JsonResponse({'error': generico}, status=502 if status else 500)


AMBITO_GENERAL = {'id': 'general', 'nombre': 'General (FIBA y normativa común)'}


def _ambitos_reglamento():
    """Ámbitos del modo reglamento (general y una entrada por comunidad autónoma). Si la API no
    responde, la página sigue funcionando solo con el ámbito general."""
    try:
        resp = requests.get(f"{settings.API_URL}/ambitos_reglamento", headers=_api_headers(), timeout=3)
        resp.raise_for_status()
        ambitos = [
            {'id': str(a['id']), 'nombre': str(a['nombre'])}
            for a in resp.json().get('ambitos', [])
            if isinstance(a, dict) and re.fullmatch(r'[a-z][a-z0-9_]{1,29}', str(a.get('id', ''))) and a.get('nombre')
        ]
        if ambitos and ambitos[0]['id'] == 'general':
            return ambitos
    except Exception as e:
        logger.warning('No se pudo obtener la lista de ámbitos de reglamento: %s', e)
    return [AMBITO_GENERAL]


def index(request):
    return render(request, 'pizarra/index.html', {'ambitos': _ambitos_reglamento()})


def privacidad(request):
    return render(request, 'pizarra/privacidad.html')


def aviso_legal(request):
    return render(request, 'pizarra/aviso_legal.html')


@require_POST
def generar(request):
    try:
        data = json.loads(request.body)
        resp = requests.post(
            f"{settings.API_URL}/generar",
            json=data,
            headers=_api_headers(),
            timeout=300,
        )
        resp.raise_for_status()
        return JsonResponse(resp.json())
    except requests.Timeout:
        return JsonResponse({'error': 'La generación tardó demasiado. Inténtalo de nuevo.'}, status=504)
    except Exception as e:
        logger.error('Error llamando API: %s', e)
        return _error_respuesta(e, 'El servicio no está disponible ahora mismo. Inténtalo de nuevo en un momento.')


@require_POST
def reglamento(request):
    try:
        data = json.loads(request.body)
        resp = requests.post(
            f"{settings.API_URL}/reglamento",
            json=data,
            headers=_api_headers(),
            timeout=210,      # la primera consulta carga el modelo (35-100 s) y puede haber un reintento
        )
        resp.raise_for_status()
        return JsonResponse(resp.json())
    except requests.Timeout:
        return JsonResponse({'error': 'Tiempo de espera agotado. Inténtalo de nuevo.'}, status=504)
    except Exception as e:
        logger.error('Error llamando API reglamento: %s', e)
        return _error_respuesta(e, 'El servicio no está disponible ahora mismo. Inténtalo de nuevo en un momento.')


@require_POST
def reprompt_ejercicio(request):
    try:
        data = json.loads(request.body)
        resp = requests.post(
            f"{settings.API_URL}/reprompt_ejercicio",
            json=data,
            headers=_api_headers(),
            timeout=120,
        )
        resp.raise_for_status()
        return JsonResponse(resp.json())
    except requests.Timeout:
        return JsonResponse({'error': 'La corrección tardó demasiado. Inténtalo de nuevo.'}, status=504)
    except Exception as e:
        logger.error('Error llamando API reprompt: %s', e)
        return _error_respuesta(e, 'El servicio no está disponible ahora mismo. Inténtalo de nuevo en un momento.')


@require_POST
def guardar_feedback(request):
    try:
        data = json.loads(request.body)
        resp = requests.post(
            f"{settings.API_URL}/guardar_feedback",
            json=data,
            headers=_api_headers(),
            timeout=10,
        )
        resp.raise_for_status()
        return JsonResponse({'ok': True})
    except Exception as e:
        logger.error('Error guardando feedback: %s', e)
        return _error_respuesta(e, 'No se pudo guardar. Inténtalo de nuevo.')


@require_POST
def descargar_pdf(request):
    try:
        data = json.loads(request.body)
        sesion_texto, edad, objetivo, duracion, diagramas = limpiar_entrada_pdf(data)
    except (ValueError, UnicodeDecodeError) as e:      # JSON inválido o campos fuera de lo permitido
        logger.warning('Entrada de PDF rechazada: %s', e)
        return JsonResponse({'error': 'Los datos de la sesión no son válidos.'}, status=400)
    try:
        pdf_bytes = _generar_pdf(sesion_texto, edad, objetivo, duracion, diagramas)

        edad_fn = re.sub(r'[^\w]', '_', edad.lower())[:20]
        obj_fn = re.sub(r'[^\w]', '_', objetivo)[:30]
        filename = f"sesion_{edad_fn}_{obj_fn}.pdf"

        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    except Exception:
        logger.exception('Error generando PDF')
        return JsonResponse({'error': 'No se pudo generar el PDF.'}, status=500)

# ── PDF de la sesión ──────────────────────────────────────────────────────────
# Tipografía: Inter (texto) y Sora (títulos), las mismas de la web, en TTF dentro de static/pizarra/fonts/pdf.
# Estructura: portada compacta con los datos de la sesión, un título por sección, cada ejercicio como ficha
# (etiqueta | contenido) y el diagrama a un lado del texto cuando existe. Si no hay diagrama no se dibuja nada.

_ETIQUETA_CAMPO = re.compile(
    r'^(?:(Juego|Reglas|Organización|Duración|Espacio|Material|Consigna|Puntos clave|Errores frecuentes|'
    r'Qué observar|Cómo facilitar|Cómo complicar|Qué cambia respecto a [\d.]+|Fundamentos)'
    r'|([A-ZÁÉÍÓÚÑ]{4,}(?: [A-ZÁÉÍÓÚÑ]{2,})*))\s*:\s*(.*)$'
)
_FUENTES_PDF = Path(__file__).resolve().parent / 'static' / 'pizarra' / 'fonts' / 'pdf'


def _limpiar_texto_pdf(txt):
    """Quita el markdown que el renderer no interpreta y sustituye lo que Inter no tiene."""
    txt = txt.replace('**', '').replace('*', '')
    for malo, bueno in (('→', '->'), ('≥', '>='), ('≤', '<='), (' ', ' '), ('​', '')):
        txt = txt.replace(malo, bueno)
    return txt.strip()


def _etiqueta_legible(texto):
    s = texto.lower()
    return s[:1].upper() + s[1:]


def _campos_de_bloque(lineas):
    """Líneas de un ejercicio o del calentamiento → [{'etiqueta', 'texto', 'items'}]. Lo que no lleva etiqueta
    se une al campo anterior o queda como texto libre; las listas «- ítem» cuelgan de su etiqueta."""
    campos, actual = [], None
    for crudo in lineas:
        linea = _limpiar_texto_pdf(crudo)
        if not linea:
            continue
        m = _ETIQUETA_CAMPO.match(linea)
        if m:
            actual = {'etiqueta': _etiqueta_legible(m.group(1) or m.group(2)), 'texto': m.group(3) or '', 'items': []}
            campos.append(actual)
        elif re.match(r'^[-•]\s+', linea) and actual is not None:
            actual['items'].append(re.sub(r'^[-•]\s+', '', linea))
        elif actual is not None and not actual['items']:
            actual['texto'] = (actual['texto'] + ' ' + linea).strip()
        else:
            actual = {'etiqueta': '', 'texto': linea, 'items': []}
            campos.append(actual)
    for campo in campos:     # el texto puede llegar en la línea siguiente a la etiqueta: se capitaliza al final
        campo['texto'] = campo['texto'][:1].upper() + campo['texto'][1:]
    return campos


def _parsear_sesion_para_pdf(texto):
    """Texto de la sesión → lista de bloques: {'tipo': 'seccion'|'ejercicio'|'calentamiento'|'texto', ...}."""
    bloques, actual = [], None

    def cerrar():
        nonlocal actual
        if actual is not None:
            bloques.append(actual)
            actual = None

    for crudo in texto.split('\n'):
        linea = crudo.strip()
        if not linea:
            continue
        m = re.match(r'^\*\*(.+?)\*\*\s*:\s*(.+)$', linea)             # «**Fundamentos**: texto»
        if m:
            cerrar()
            bloques.append({'tipo': 'seccion', 'titulo': m.group(1).strip()})
            bloques.append({'tipo': 'texto', 'texto': _limpiar_texto_pdf(m.group(2))})
            continue
        m = re.match(r'^\*\*(.+?)\*\*$', linea)                         # «**CALENTAMIENTO (10 min)**»
        if m:
            cerrar()
            titulo = m.group(1).strip()
            bloques.append({'tipo': 'seccion', 'titulo': titulo})
            if 'CALENTAMIENTO' in titulo.upper():
                actual = {'tipo': 'calentamiento', 'lineas': []}
            continue
        if re.match(r'^Ejercicio \d+', _limpiar_texto_pdf(linea)):
            cerrar()
            actual = {'tipo': 'ejercicio', 'titulo': _limpiar_texto_pdf(linea), 'lineas': []}
            continue
        if actual is not None:
            actual['lineas'].append(linea)
        else:
            bloques.append({'tipo': 'texto', 'texto': _limpiar_texto_pdf(linea)})
    cerrar()
    return bloques


def _svg_a_png(svg, ancho_px=900):
    import cairosvg
    with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp:
        ruta = tmp.name
    cairosvg.svg2png(bytestring=svg.encode('utf-8'), write_to=ruta, output_width=ancho_px)
    return ruta


def _generar_pdf(sesion_texto, edad, objetivo, duracion, diagramas):
    from fpdf import FPDF

    NARANJA = (232, 117, 44)
    NARANJA_OSCURO = (180, 74, 12)
    TINTA = (27, 27, 31)
    GRIS = (107, 98, 87)
    LINEA = (225, 219, 208)
    FONDO_SUAVE = (252, 244, 235)

    ANCHO_PAG, ML, MR = 210, 18, 18
    ANCHO = ANCHO_PAG - ML - MR           # 174 mm
    X_ETIQUETA, ANCHO_ETIQUETA = ML, 32
    X_TEXTO = ML + 36
    ANCHO_TEXTO = ANCHO_PAG - MR - X_TEXTO
    ANCHO_DIAGRAMA = 104
    ALTO_MAX_DIAGRAMA = 92
    # El primer diagrama de cada ejercicio va a la izquierda y el texto a su derecha (caben dos ejercicios por página).
    ANCHO_LATERAL, ALTO_LATERAL, SEPARACION_LATERAL = 58, 90, 5
    ANCHO_ETIQUETA_LAT = 24
    lateral = {}       # {'pagina', 'y_fin', 'x'} mientras una fila pueda ir junto al diagrama
    MARGEN_INFERIOR = 18

    edad_txt = edad or 'General'
    duracion_txt = f'{duracion} min' if duracion else 'Flexible'

    class PDF(FPDF):
        def header(self):
            self.set_fill_color(*NARANJA)
            self.rect(0, 0, ANCHO_PAG, 4, 'F')
            if self.page_no() > 1:
                self.set_xy(ML, 8)
                self.set_font('Inter', '', 7.5)
                self.set_text_color(*GRIS)
                self.cell(ANCHO / 2, 4, 'MiPizarra', align='L')
                self.cell(ANCHO / 2, 4, f'{edad_txt}  ·  {duracion_txt}', align='R')
                self.set_draw_color(*LINEA)
                self.set_line_width(0.2)
                self.line(ML, 14, ANCHO_PAG - MR, 14)
                self.set_y(19)

        def footer(self):
            self.set_y(-12)
            self.set_font('Inter', '', 7.5)
            self.set_text_color(*GRIS)
            self.cell(0, 6, f'{self.page_no()} / {{nb}}', align='C')

    pdf = PDF(format='A4')
    pdf.alias_nb_pages()
    for estilo, fichero in (('', 'Inter-Regular.ttf'), ('B', 'Inter-Bold.ttf')):
        pdf.add_font('Inter', estilo, str(_FUENTES_PDF / fichero))
    pdf.add_font('InterSB', '', str(_FUENTES_PDF / 'Inter-SemiBold.ttf'))
    pdf.add_font('Sora', 'B', str(_FUENTES_PDF / 'Sora-Bold.ttf'))
    pdf.set_margins(left=ML, top=19, right=MR)
    pdf.set_auto_page_break(auto=True, margin=MARGEN_INFERIOR)
    pdf.add_page()

    # ── Portada compacta ──────────────────────────────────────────────────────
    pdf.set_y(12)
    pdf.set_font('Sora', 'B', 22)
    pdf.set_text_color(*TINTA)
    ancho_mi = pdf.get_string_width('Mi')
    pdf.set_x(ML)
    pdf.cell(ancho_mi, 10, 'Mi')
    pdf.set_text_color(*NARANJA)
    pdf.cell(pdf.get_string_width('Pizarra') + 1, 10, 'Pizarra', new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('Inter', '', 8.5)
    pdf.set_text_color(*GRIS)
    pdf.cell(0, 5, 'Sesión de entrenamiento de baloncesto', new_x='LMARGIN', new_y='NEXT')
    pdf.ln(4)

    y0 = pdf.get_y()
    obj_txt = _limpiar_texto_pdf(objetivo or '') or '—'
    pdf.set_font('Inter', '', 10)
    alto_obj = pdf.multi_cell(ANCHO - 8, 5, obj_txt, align='L', dry_run=True, output='HEIGHT')
    alto_caja = 6 + 9 + alto_obj + 5
    pdf.set_fill_color(*FONDO_SUAVE)
    pdf.set_draw_color(*LINEA)
    pdf.rect(ML, y0, ANCHO, alto_caja, 'FD')
    for i, (rotulo, valor) in enumerate((('Categoría', edad_txt), ('Duración', duracion_txt))):
        x = ML + 4 + i * 42
        pdf.set_xy(x, y0 + 3.5)
        pdf.set_font('InterSB', '', 7)
        pdf.set_text_color(*GRIS)
        pdf.cell(38, 4, rotulo.upper())
        pdf.set_xy(x, y0 + 7.5)
        pdf.set_font('Inter', 'B', 11)
        pdf.set_text_color(*TINTA)
        pdf.cell(38, 6, valor)
    pdf.set_xy(ML + 4, y0 + 15.5)
    pdf.set_font('InterSB', '', 7)
    pdf.set_text_color(*GRIS)
    pdf.cell(40, 4, 'OBJETIVO')
    pdf.set_xy(ML + 4, y0 + 19.5)
    pdf.set_font('Inter', '', 10)
    pdf.set_text_color(*TINTA)
    pdf.multi_cell(ANCHO - 8, 5, obj_txt, align='L')
    pdf.set_y(y0 + alto_caja + 7)

    # ── Diagramas: por grupo de ejercicio (multifase) y el del calentamiento por id ───────────
    def es_placeholder(d):
        svg = (d or {}).get('svg', '')
        return not svg or 'data-placeholder' in svg

    grupos, i = [], 0
    ejercicios_d = [d for d in diagramas if not str(d.get('id', '')).startswith(('calentamiento', 'vuelta_a_la_calma'))]
    while i < len(ejercicios_d):
        nombre = ejercicios_d[i].get('nombre')
        grupo = []
        while i < len(ejercicios_d) and ejercicios_d[i].get('nombre') == nombre:
            grupo.append(ejercicios_d[i])
            i += 1
        grupos.append(grupo)

    def diagramas_de(bloque_idx_ejercicio, tipo):
        if tipo == 'calentamiento':
            d = next((d for d in diagramas if str(d.get('id', '')).startswith('calentamiento')), None)
            return [] if es_placeholder(d) else [d]
        if bloque_idx_ejercicio < len(grupos):
            return [d for d in grupos[bloque_idx_ejercicio] if not es_placeholder(d)]
        return []

    # ── Dibujo ────────────────────────────────────────────────────────────────
    def espacio_libre():
        return pdf.h - MARGEN_INFERIOR - pdf.get_y()

    def asegurar(alto):
        if espacio_libre() < alto:
            pdf.add_page()

    def titulo_seccion(titulo):
        asegurar(28)
        pdf.ln(3)
        pdf.set_font('Sora', 'B', 12.5)
        pdf.set_text_color(*NARANJA_OSCURO)
        pdf.set_x(ML)
        pdf.multi_cell(ANCHO, 7, titulo, align='L')
        pdf.set_draw_color(*NARANJA)
        pdf.set_line_width(0.5)
        pdf.line(ML, pdf.get_y() + 0.5, ANCHO_PAG - MR, pdf.get_y() + 0.5)
        pdf.ln(4)

    def geometria():
        """(x etiqueta, ancho etiqueta, x texto, ancho texto, x sin etiqueta, ancho sin etiqueta) según haya o no un
        diagrama a la izquierda en la posición actual."""
        if lateral and lateral['pagina'] == pdf.page_no() and pdf.get_y() < lateral['y_fin']:
            x = lateral['x']
            x_t = x + ANCHO_ETIQUETA_LAT + 3
            return x, ANCHO_ETIQUETA_LAT, x_t, ANCHO_PAG - MR - x_t, x, ANCHO_PAG - MR - x
        return X_ETIQUETA, ANCHO_ETIQUETA, X_TEXTO, ANCHO_TEXTO, ML, ANCHO

    def alto_fila(campo, ancho_texto=None):
        ancho_texto = ancho_texto or ANCHO_TEXTO
        alto = 0
        pdf.set_font('Inter', '', 9.5)
        if campo['texto']:
            alto += pdf.multi_cell(ancho_texto, 4.9, campo['texto'], align='L', dry_run=True, output='HEIGHT')
        for item in campo['items']:
            alto += pdf.multi_cell(ancho_texto - 4, 4.9, item, align='L', dry_run=True, output='HEIGHT')
        return max(alto, 5) + 3.2

    def fila(campo):
        _, _, _, ancho_t, _, ancho_sin = geometria()
        asegurar(alto_fila(campo, ancho_t if campo['etiqueta'] else ancho_sin) + 1)
        x_et, ancho_et, x_t, ancho_t, x_sin, ancho_sin = geometria()     # tras un posible salto de página
        y = pdf.get_y()
        if campo['etiqueta']:
            pdf.set_xy(x_et, y + 0.9)
            pdf.set_font('InterSB', '', 7)
            pdf.set_text_color(*GRIS)
            pdf.multi_cell(ancho_et, 3.6, campo['etiqueta'].upper(), align='L')
            x_texto, ancho_texto = x_t, ancho_t
        else:
            x_texto, ancho_texto = x_sin, ancho_sin
        pdf.set_xy(x_texto, y)
        negrita = campo['etiqueta'] in ('Juego',)
        pdf.set_font('Inter', 'B' if negrita else '', 9.5)
        pdf.set_text_color(*TINTA)
        if campo['texto']:
            pdf.multi_cell(ancho_texto, 4.9, campo['texto'], align='L')
        for item in campo['items']:
            pdf.set_x(x_texto)
            pdf.set_font('Inter', '', 9.5)
            pdf.cell(4, 4.9, '•')
            pdf.multi_cell(ancho_texto - 4, 4.9, item, align='L')
        y_fin = max(pdf.get_y(), y + 5)
        pdf.set_draw_color(*LINEA)
        pdf.set_line_width(0.15)
        pdf.line(x_et, y_fin + 1.4, ANCHO_PAG - MR, y_fin + 1.4)
        pdf.set_y(y_fin + 2.8)

    def preparar_diagramas(lista, ancho_max=None, alto_max=None):
        """Convierte cada SVG a PNG y calcula su tamaño en la página (sin pasar de ALTO_MAX_DIAGRAMA)."""
        from PIL import Image
        ancho_max = ancho_max or ANCHO_DIAGRAMA
        alto_max = alto_max or ALTO_MAX_DIAGRAMA
        listos = []
        for d in lista:
            try:
                ruta = _svg_a_png(d['svg'])
                with Image.open(ruta) as im:
                    proporcion = im.height / im.width
                ancho = min(ancho_max, alto_max / proporcion)
                listos.append({'ruta': ruta, 'ancho': ancho, 'alto': ancho * proporcion, 'titulo': d.get('titulo')})
            except Exception:
                logger.exception('No se pudo convertir un diagrama del PDF')
        return listos

    def pintar_diagramas(listos):
        for d in listos:
            try:
                asegurar(d['alto'] + 8)
                if d.get('titulo'):
                    pdf.set_font('InterSB', '', 7)
                    pdf.set_text_color(*GRIS)
                    pdf.set_x(ML)
                    pdf.cell(ANCHO, 4, str(d['titulo']).upper(), new_x='LMARGIN', new_y='NEXT')
                pdf.image(d['ruta'], x=ML, w=d['ancho'])
                pdf.set_y(pdf.get_y() + 4)
            finally:
                os.unlink(d['ruta'])

    def pintar_lateral(d):
        """Primer diagrama de un bloque: a la izquierda; las filas siguientes se colocan a su derecha."""
        try:
            y0 = pdf.get_y()
            if d.get('titulo'):
                pdf.set_xy(ML, y0)
                pdf.set_font('InterSB', '', 7)
                pdf.set_text_color(*GRIS)
                pdf.cell(d['ancho'], 4, str(d['titulo']).upper())
                y0 += 4.5
            pdf.image(d['ruta'], x=ML, y=y0, w=d['ancho'])
            lateral.update(pagina=pdf.page_no(), y_fin=y0 + d['alto'] + 1, x=ML + d['ancho'] + SEPARACION_LATERAL)
            pdf.set_xy(ML, y0)
        finally:
            os.unlink(d['ruta'])

    def cerrar_lateral():
        """Al acabar las filas, si el diagrama baja más que el texto, sigue por debajo de él."""
        if lateral and lateral['pagina'] == pdf.page_no() and pdf.get_y() < lateral['y_fin']:
            pdf.set_y(lateral['y_fin'] + 1)
        lateral.clear()

    bloques = _parsear_sesion_para_pdf(sesion_texto)
    n_ejercicio = -1
    for pos, bloque in enumerate(bloques):
        tipo = bloque['tipo']
        if tipo == 'seccion':
            titulo = bloque['titulo']
            # un título de sección nunca se queda solo al pie: si lo siguiente es un ejercicio, pide sitio para empezarlo
            if pos + 1 < len(bloques) and bloques[pos + 1]['tipo'] in ('ejercicio', 'calentamiento'):
                asegurar(min(150, pdf.h - MARGEN_INFERIOR - 25))
            if 'DESCANSO' in titulo.upper():
                asegurar(14)
                pdf.ln(2)
                pdf.set_font('Inter', '', 8.5)
                pdf.set_text_color(*GRIS)
                pdf.set_x(ML)
                pdf.cell(ANCHO, 6, titulo.replace('**', '').capitalize(), align='C', new_x='LMARGIN', new_y='NEXT')
                pdf.ln(2)
            else:
                titulo_seccion(titulo)
        elif tipo == 'texto':
            pdf.set_font('Inter', '', 9.5)
            pdf.set_text_color(*TINTA)
            pdf.set_x(ML)
            pdf.multi_cell(ANCHO, 5, bloque['texto'], align='L')
            pdf.ln(2)
        elif tipo == 'calentamiento':
            campos = _campos_de_bloque(bloque['lineas'])
            listos = preparar_diagramas(diagramas_de(None, 'calentamiento'), ANCHO_LATERAL, ALTO_LATERAL)
            if listos:
                asegurar(min(listos[0]['alto'] + 25, pdf.h - MARGEN_INFERIOR - 25))
                pintar_lateral(listos[0])
            for campo in campos:
                fila(campo)
            cerrar_lateral()
            pintar_diagramas(listos[1:])
        elif tipo == 'ejercicio':
            n_ejercicio += 1
            campos = _campos_de_bloque(bloque['lineas'])
            m = re.match(r'^(Ejercicio \d+(?:\.\d+)?)\s*(?:\([^)]*\))?\s*:?\s*(.*)$', bloque['titulo'])
            rotulo, nombre = (m.group(1), m.group(2)) if m else ('Ejercicio', bloque['titulo'])
            pdf.set_font('Sora', 'B', 12.5)
            alto_titulo = pdf.multi_cell(ANCHO, 6.4, nombre or rotulo, align='L', dry_run=True, output='HEIGHT')
            listos = preparar_diagramas(diagramas_de(n_ejercicio, 'ejercicio'), ANCHO_LATERAL, ALTO_LATERAL)
            # título + diagrama + al menos una fila de texto en la misma página: nunca un título suelto abajo
            necesario = alto_titulo + 12 + (listos[0]['alto'] if listos else 0) + 10
            asegurar(min(necesario, pdf.h - MARGEN_INFERIOR - 25))
            pdf.ln(2.5)
            pdf.set_font('InterSB', '', 7.5)
            pdf.set_text_color(*NARANJA_OSCURO)
            pdf.set_x(ML)
            pdf.cell(ANCHO, 4.2, rotulo.upper(), new_x='LMARGIN', new_y='NEXT')
            pdf.set_font('Sora', 'B', 12.5)
            pdf.set_text_color(*TINTA)
            pdf.set_x(ML)
            pdf.multi_cell(ANCHO, 6.4, nombre or rotulo, align='L')
            pdf.ln(2.5)
            if listos:
                pintar_lateral(listos[0])
            for campo in campos:
                fila(campo)
            cerrar_lateral()
            pintar_diagramas(listos[1:])
            pdf.ln(3)

    return bytes(pdf.output())
