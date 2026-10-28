"""Pestaña «Fichas» del administrador: ver y corregir las fichas de ejercicios una a una.

Solo la cuenta administradora (la misma del botón de la biblioteca de jugadas). La web no guarda nada: pasa las
peticiones a la API (/admin/fichas), que guarda los cambios en su propio fichero y los aplica encima de
data/exercises.json."""
import logging

import requests
from django.conf import settings
from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_http_methods

from .cuentas import _es_admin
from .views import _api_headers

logger = logging.getLogger(__name__)
TIMEOUT = 15


def _sin_permiso():
    return JsonResponse({'error': 'No tienes permiso para cambiar las fichas.'}, status=403)


def _respuesta(resp):
    """Lo que dijo la API (JSON), con su código: así llegan al navegador los problemas de validación."""
    try:
        cuerpo = resp.json()
    except ValueError:
        cuerpo = {'error': 'Respuesta no válida de la API.'}
    if resp.status_code >= 400 and 'error' not in cuerpo:
        cuerpo['error'] = cuerpo.get('detail') if isinstance(cuerpo.get('detail'), str) else 'No se pudo completar.'
    return JsonResponse(cuerpo, status=resp.status_code, safe=False)


@ensure_csrf_cookie
def pagina(request):
    if not _es_admin(request):
        raise Http404()
    return render(request, 'pizarra/fichas.html', {'usuario': request.user.get_username()})


@require_GET
def datos(request):
    if not _es_admin(request):
        return _sin_permiso()
    try:
        resp = requests.get(f"{settings.API_URL}/admin/fichas", headers=_api_headers(request), timeout=TIMEOUT)
    except requests.RequestException:
        logger.exception('No se pudieron pedir las fichas a la API')
        return JsonResponse({'error': 'No se pudo hablar con la API.'}, status=502)
    return _respuesta(resp)


@require_http_methods(['PUT', 'DELETE'])
def guardar(request, ficha_id):
    """PUT {ficha: {...}}: guarda los cambios de la ficha. DELETE: vuelve a la original."""
    if not _es_admin(request):
        return _sin_permiso()
    url = f"{settings.API_URL}/admin/fichas/{ficha_id}"
    try:
        if request.method == 'DELETE':
            resp = requests.delete(url, headers=_api_headers(request), timeout=TIMEOUT)
        else:
            if len(request.body) > 40_000:
                return JsonResponse({'error': 'La ficha es demasiado grande.'}, status=413)
            resp = requests.put(url, data=request.body, headers=_api_headers(request), timeout=TIMEOUT)
    except requests.RequestException:
        logger.exception('No se pudo guardar la ficha %s en la API', ficha_id)
        return JsonResponse({'error': 'No se pudo hablar con la API.'}, status=502)
    return _respuesta(resp)
