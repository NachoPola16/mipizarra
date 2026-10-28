"""Cuentas y jugadas guardadas: inicio de sesión de Django y una API mínima (listar, guardar, abrir y borrar)."""
import json
import re
from pathlib import Path

from django.conf import settings
from django.contrib.auth import logout, views as vistas_auth
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods, require_POST

from .jugadas_datos import validar_jugada
from .models import Jugada, JugadaBiblioteca

MAX_BYTES = 200_000        # tamaño máximo del cuerpo de una jugada
MAX_JUGADAS = 200          # jugadas por cuenta
INTENTOS_MAX, VENTANA_S = 8, 600     # fallos de inicio de sesión por IP en 10 minutos


@ensure_csrf_cookie
def jugadas(request):
    usuario = request.user.get_username() if request.user.is_authenticated else ''
    return render(request, 'pizarra/jugadas.html', {'usuario': usuario, 'es_admin': _es_admin(request)})


def _es_admin(request):
    admin = getattr(settings, 'JUGADAS_ADMIN', '')
    return bool(admin) and request.user.is_authenticated and request.user.get_username() == admin


BIBLIOTECA = Path(__file__).resolve().parent / 'static' / 'pizarra' / 'data' / 'jugadas.json'
ID_JUGADA = re.compile(r'^j_\d{3,4}$')


def _biblioteca_base():
    try:
        datos = json.loads(BIBLIOTECA.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return []
    return datos if isinstance(datos, list) else []


def biblioteca_json(request):
    """La biblioteca de jugadas: el fichero del repositorio con los cambios del administrador encima."""
    cambios = {c.id_jugada: c.datos for c in JugadaBiblioteca.objects.all()}
    salida = [cambios.pop(j.get('id'), j) for j in _biblioteca_base()]
    salida.extend(cambios.values())
    resp = JsonResponse(salida, safe=False)
    resp['Cache-Control'] = 'no-cache'
    return resp


@require_http_methods(['POST', 'DELETE'])
def biblioteca_guardar(request, jid):
    """Solo el administrador. POST {datos}: sustituye la jugada jid de la biblioteca. DELETE: vuelve a la original."""
    if not request.user.is_authenticated:
        return _sin_sesion()
    if not _es_admin(request) or not (ID_JUGADA.match(jid) or (jid == 'nueva' and request.method == 'POST')):
        return JsonResponse({'error': 'No tienes permiso para cambiar la biblioteca.'}, status=403)
    if request.method == 'DELETE':
        JugadaBiblioteca.objects.filter(id_jugada=jid).delete()
        return JsonResponse({'ok': True})
    if len(request.body) > MAX_BYTES:
        return JsonResponse({'error': 'La jugada es demasiado grande.'}, status=413)
    try:
        cuerpo = json.loads(request.body)
    except ValueError:
        return JsonResponse({'error': 'Cuerpo no válido.'}, status=400)
    nuevos = cuerpo.get('datos') if isinstance(cuerpo, dict) else None
    validada = validar_jugada(nuevos)
    if validada is None:
        return JsonResponse({'error': 'La jugada no es válida.'}, status=400)
    if jid == 'nueva':        # jugada nueva para todos: siguiente número libre de la biblioteca
        usados = [int(j['id'][2:]) for j in _biblioteca_base() if ID_JUGADA.match(str(j.get('id', '')))]
        usados += [int(c.id_jugada[2:]) for c in JugadaBiblioteca.objects.all()]
        jid = 'j_%03d' % (max(usados, default=0) + 1)
        base = {'descripcion': '', 'edades': ['U16', 'U18', 'Senior'], 'borrador': True}
    else:
        actual = JugadaBiblioteca.objects.filter(id_jugada=jid).first()
        base = actual.datos if actual else next((j for j in _biblioteca_base() if j.get('id') == jid), {})
    entrada = dict(base)                        # edades, descripción, borrador, conceptos… se conservan
    entrada.update(validada)
    entrada['id'] = jid
    nombre = nuevos.get('nombre') if isinstance(nuevos, dict) else None
    if isinstance(nombre, str) and nombre.strip():
        entrada['nombre'] = nombre.strip()[:120]
    if not validada.get('defensa'):
        entrada.pop('defensa', None)
    JugadaBiblioteca.objects.update_or_create(id_jugada=jid, defaults={'datos': entrada})
    return JsonResponse({'ok': True, 'id': jid})


def _clave_intentos(request):
    # Detrás de Cloudflare y del proxy, REMOTE_ADDR es siempre el del proxy: se usa la IP real del visitante si Cloudflare la manda.
    ip = request.META.get('HTTP_CF_CONNECTING_IP') or request.META.get('REMOTE_ADDR', '?')
    return 'login-fallos:' + ip[:64]


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
    logout(request)
    destino = request.POST.get('next', '')
    if destino and url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return redirect(destino)
    return redirect('index')


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
