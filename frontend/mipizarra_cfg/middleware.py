from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.http import JsonResponse

_CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "font-src 'self' data:; "
    "img-src 'self' data: blob:; "
    "connect-src 'self'; "
    "frame-src 'self' blob:; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "object-src 'none';"
)


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=(), payment=()'
        response['Content-Security-Policy'] = _CSP
        return response


class LoginRequiredMiddleware:
    """Toda la web exige iniciar sesión: sin cuenta no se usa nada. Públicas: la pantalla de entrada y las páginas
    legales (aviso legal y privacidad); los estáticos los sirve WhiteNoise antes de llegar aquí. Las páginas redirigen
    al login; las llamadas del navegador (POST, /guardadas/, peticiones que piden JSON) reciben un 401 en JSON."""
    PUBLICAS = ('/cuenta/entrar/', '/privacidad/', '/aviso-legal/')

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated or request.path in self.PUBLICAS:
            return self.get_response(request)
        es_api = (request.method != 'GET' or request.path.startswith('/jugadas/guardadas/')
                  or 'application/json' in request.headers.get('Accept', ''))
        if es_api:
            return JsonResponse({'error': 'Tu sesión ha caducado o no has entrado. Recarga la página e inicia sesión.'}, status=401)
        return redirect_to_login(request.get_full_path(), settings.LOGIN_URL)
