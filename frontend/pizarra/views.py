import json
import re
import os
import tempfile
import logging

import requests
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)


def index(request):
    return render(request, 'pizarra/index.html')


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
            timeout=300,
        )
        resp.raise_for_status()
        return JsonResponse(resp.json())
    except requests.Timeout:
        return JsonResponse({'error': 'La generación tardó demasiado. Inténtalo de nuevo.'}, status=504)
    except Exception as e:
        logger.error('Error llamando API: %s', e)
        return JsonResponse({'error': str(e)}, status=500)


@require_POST
def guardar_feedback(request):
    try:
        data = json.loads(request.body)
        resp = requests.post(
            f"{settings.API_URL}/guardar_feedback",
            json=data,
            timeout=10,
        )
        resp.raise_for_status()
        return JsonResponse({'ok': True})
    except Exception as e:
        logger.error('Error guardando feedback: %s', e)
        return JsonResponse({'error': str(e)}, status=500)


@require_POST
def descargar_pdf(request):
    try:
        data = json.loads(request.body)
        sesion_texto = data.get('sesion', '')
        edad = data.get('edad', 'General')
        objetivo = data.get('objetivo', '')
        duracion = data.get('duracion', 0)
        diagramas = data.get('diagramas', [])

        pdf_bytes = _generar_pdf(sesion_texto, edad, objetivo, duracion, diagramas)

        edad_fn = (edad or 'general').lower().replace(' ', '_')
        obj_fn = re.sub(r'[^\w]', '_', objetivo)[:30]
        filename = f"sesion_{edad_fn}_{obj_fn}.pdf"

        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    except Exception as e:
        logger.error('Error generando PDF: %s', e)
        return JsonResponse({'error': str(e)}, status=500)


def _generar_pdf(sesion_texto, edad, objetivo, duracion, diagramas):
    import cairosvg
    from fpdf import FPDF

    BLUE_R, BLUE_G, BLUE_B = 79, 142, 247
    DARK_R, DARK_G, DARK_B = 30, 30, 40

    class PDF_MiPizarra(FPDF):
        def header(self):
            self.set_fill_color(BLUE_R, BLUE_G, BLUE_B)
            self.rect(0, 0, 210, 7, 'F')
            self.set_y(11)
            self.set_font('Helvetica', 'B', 22)
            self.set_text_color(DARK_R, DARK_G, DARK_B)
            self.cell(0, 9, 'MiPizarra', align='C', new_x='LMARGIN', new_y='NEXT')
            self.set_font('Helvetica', '', 8)
            self.set_text_color(130, 130, 140)
            self.cell(0, 4, 'Asistente de entrenamiento de baloncesto', align='C', new_x='LMARGIN', new_y='NEXT')
            self.ln(2)

        def footer(self):
            self.set_y(-13)
            self.set_font('Helvetica', '', 7)
            self.set_text_color(160, 160, 170)
            self.cell(0, 8, f'Pág. {self.page_no()}', align='C')

    pdf = PDF_MiPizarra()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.set_margins(left=20, top=30, right=20)
    pdf.add_page()

    duracion_text = f'{duracion} min' if duracion else 'Flexible'
    edad_text = edad if edad else 'General'
    objetivo_corto = objetivo[:40] + '...' if len(objetivo) > 40 else objetivo

    y_meta = pdf.get_y()
    pdf.set_fill_color(240, 244, 255)
    pdf.set_draw_color(200, 215, 250)
    pdf.rect(20, y_meta, 170, 11, 'FD')
    pdf.set_font('Helvetica', 'B', 9)
    pdf.set_text_color(50, 80, 160)
    pdf.set_xy(20, y_meta + 1)
    meta_str = f'Categoría: {edad_text}   ·   Duración: {duracion_text}   ·   Objetivo: {objetivo_corto}'
    pdf.cell(170, 9, meta_str, align='C', new_x='LMARGIN', new_y='NEXT')
    pdf.ln(7)

    def clean(txt):
        return (
            txt.replace('–', '-').replace('—', '-')
               .replace('‘', "'").replace('’', "'")
               .replace('“', '"').replace('”', '"')
               .replace('•', '*')
               .encode('latin-1', errors='ignore').decode('latin-1')
        )

    def add_diagram(idx):
        if idx < len(diagramas):
            svg_content = diagramas[idx].get('svg', '')
            if svg_content:
                try:
                    if pdf.get_y() > 170:
                        pdf.add_page()
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp:
                        cairosvg.svg2png(
                            bytestring=svg_content.encode('utf-8'),
                            write_to=tmp.name,
                            output_width=900,
                        )
                        pdf.image(tmp.name, x=20, w=170)
                        os.unlink(tmp.name)
                    pdf.set_x(pdf.l_margin)
                    pdf.ln(4)
                except Exception:
                    pass

    ejercicio_actual = -1
    pagina_recien_nueva = False
    subsec_keys = ['Juego:', 'Reglas:', 'Organización:', 'Puntos clave:',
                   'Espacio:', 'Duración:', 'Fundamentos:', 'Puntos Clave:']

    for linea in sesion_texto.split('\n'):
        linea = linea.strip()
        if not linea:
            pdf.ln(2)
            continue
        linea = clean(linea)

        if linea.startswith('**') and linea.endswith('**'):
            titulo = linea.replace('**', '').strip()
            titulo_up = titulo.upper()
            if 'PARTE PRINCIPAL' in titulo_up or 'VUELTA A LA CALMA' in titulo_up:
                pdf.add_page()
                pagina_recien_nueva = True
            else:
                pdf.ln(4)
                pagina_recien_nueva = False
            pdf.set_font('Helvetica', 'B', 12)
            pdf.set_text_color(BLUE_R, BLUE_G, BLUE_B)
            pdf.set_x(pdf.l_margin)
            pdf.cell(170, 7, titulo[:60], new_x='LMARGIN', new_y='NEXT')
            pdf.set_draw_color(BLUE_R, BLUE_G, BLUE_B)
            pdf.set_line_width(0.5)
            pdf.line(20, pdf.get_y(), 190, pdf.get_y())
            pdf.ln(4)
            pdf.set_font('Helvetica', size=10)
            pdf.set_text_color(40, 40, 50)
            continue

        if re.match(r'Ejercicio \d+', linea):
            if not pagina_recien_nueva:
                pdf.add_page()
            pagina_recien_nueva = False
            ejercicio_actual += 1
            pdf.set_font('Helvetica', 'B', 13)
            pdf.set_text_color(DARK_R, DARK_G, DARK_B)
            pdf.set_x(pdf.l_margin)
            pdf.cell(170, 8, linea[:80], new_x='LMARGIN', new_y='NEXT')
            pdf.ln(2)
            add_diagram(ejercicio_actual)
            pdf.set_x(pdf.l_margin)
            pdf.set_font('Helvetica', size=10)
            pdf.set_text_color(40, 40, 50)
            continue

        if any(linea.startswith(k) for k in subsec_keys):
            pdf.set_x(pdf.l_margin)
            pdf.set_font('Helvetica', 'B', 10)
            pdf.set_text_color(60, 60, 70)
            pdf.multi_cell(170, 5, linea)
            pdf.set_x(pdf.l_margin)
            pdf.set_font('Helvetica', size=10)
            pdf.set_text_color(40, 40, 50)
            continue

        pdf.set_x(pdf.l_margin)
        pdf.set_font('Helvetica', size=10)
        pdf.set_text_color(50, 50, 60)
        pdf.multi_cell(170, 5, linea)

    return bytes(pdf.output())
