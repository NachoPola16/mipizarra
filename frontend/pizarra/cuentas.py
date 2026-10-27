"""Cuentas y jugadas guardadas: inicio de sesión de Django y una API mínima (listar, guardar, abrir y borrar)."""
import json

from django.contrib.auth import views as vistas_auth
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods, require_POST

from .jugadas_datos import validar_jugada
from .models import Jugada

MAX_BYTES = 200_000        # tamaño máximo del cuerpo de una jugada
MAX_JUGADAS = 200          # jugadas por cuenta
INTENTOS_MAX, VENTANA_S = 8, 600     # fallos de inicio de sesión por IP en 10 minutos


@ensure_csrf_cookie
def jugadas(request):
    usuario = request.user.get_username() if request.user.is_authenticated else ''
    return render(request, 'pizarra/jugadas.html', {'usuario': usuario})


def _clave_intentos(request):
    return 'login-fallos:' + request.META.get('REMOTE_ADDR', '?')


class Entrar(vistas_auth.LoginView):
    """Inicio de sesión con un freno sencillo contra la fuerza bruta (por IP)."""
    template_name = 'pizarra/entrar.html'
    redirect_authenticated_user = True

    def post(self, request, *args, **kwargs):
        if cache.get(_clave_intentos(request), 0) >= INTENTOS_MAX:
            form = self.get_form()
            form.add_error(None, 'Demasiados intentos fallidos. Espera unos minutos y vuelve a probar.')
            return self.render_to_response(self.get_context_data(form=form), status=429)
        return super().post(request, *args, **kwargs)

    def form_invalid(self, form):
        clave = _clave_intentos(self.request)
        cache.set(clave, cache.get(clave, 0) + 1, VENTANA_S)
        return super().form_invalid(form)

    def form_valid(self, form):
        cache.delete(_clave_intentos(self.request))
        return super().form_valid(form)


@require_POST
def salir(request):
    vistas_auth.logout(request)
    return redirect('jugadas')


def _sin_sesion():
    return JsonResponse({'error': 'Inicia sesión para usar tus jugadas guardadas.'}, status=401)


@require_http_methods(['GET', 'POST'])
def guardadas(request):
    """GET: lista (id y nombre). POST {nombre, datos}: crea o actualiza la jugada de ese nombre."""
    if not request.user.is_authenticated:
        return _sin_sesion()
    if request.method == 'GET':
        filas = request.user.jugadas.values('id', 'nombre')
        return JsonResponse({'jugadas': [{'id': f['id'], 'nombre': f['nombre']} for f in filas]})
    if len(request.body) > MAX_BYTES:
        return JsonResponse({'error': 'La jugada es demasiado grande.'}, status=413)
    try:
        cuerpo = json.loads(request.body)
    except ValueError:
        return JsonResponse({'error': 'Cuerpo no válido.'}, status=400)
    nombre = (cuerpo.get('nombre') if isinstance(cuerpo, dict) else None)
    nombre = nombre.strip()[:80] if isinstance(nombre, str) else ''
    datos = validar_jugada(cuerpo.get('datos') if isinstance(cuerpo, dict) else None)
    if not nombre or datos is None:
        return JsonResponse({'error': 'La jugada no es válida.'}, status=400)
    existente = request.user.jugadas.filter(nombre=nombre).first()
    if existente is None and request.user.jugadas.count() >= MAX_JUGADAS:
        return JsonResponse({'error': 'Has llegado al máximo de jugadas guardadas.'}, status=409)
    obj, creada = Jugada.objects.update_or_create(usuario=request.user, nombre=nombre, defaults={'datos': datos})
    return JsonResponse({'id': obj.id, 'nombre': obj.nombre, 'creada': creada}, status=201 if creada else 200)


@require_http_methods(['GET', 'DELETE'])
def guardada(request, pk):
    if not request.user.is_authenticated:
        return _sin_sesion()
    obj = request.user.jugadas.filter(pk=pk).first()      # solo las propias: no se pueden pedir las de otra cuenta
    if obj is None:
        return JsonResponse({'error': 'No existe esa jugada.'}, status=404)
    if request.method == 'DELETE':
        obj.delete()
        return JsonResponse({'ok': True})
    return JsonResponse({'id': obj.id, 'nombre': obj.nombre, 'datos': obj.datos})
