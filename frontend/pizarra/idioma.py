"""Idioma de la interfaz web: `es` (por defecto) o `en`.

Se elige con `?lang=en` (o `?lang=es`): el middleware guarda la elección en una cookie y redirige a la misma página sin el
parámetro. Sin parámetro manda la cookie; sin cookie, español. Las páginas legales (privacidad y aviso legal) solo existen
en español y no se traducen. La generación de sesiones y el reglamento siguen en español hasta que haya prompts y RAG por
idioma: la interfaz en inglés lo avisa."""
from urllib.parse import urlencode

from django.http import HttpResponseRedirect

IDIOMAS = ('es', 'en')
IDIOMA_BASE = 'es'
COOKIE = 'lang'
UN_ANIO = 60 * 60 * 24 * 365


def idioma_de(request):
    """Idioma válido de la petición (el del middleware; español si no lo ha pasado por él)."""
    return getattr(request, 'idioma', IDIOMA_BASE)


class IdiomaMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        pedido = request.GET.get('lang')
        if request.method == 'GET' and pedido in IDIOMAS:
            resto = [(k, v) for k, vs in request.GET.lists() for v in vs if k != 'lang']
            destino = request.path + (('?' + urlencode(resto)) if resto else '')
            respuesta = HttpResponseRedirect(destino)
            respuesta.set_cookie(COOKIE, pedido, max_age=UN_ANIO, samesite='Lax', secure=request.is_secure())
            return respuesta
        guardado = request.COOKIES.get(COOKIE)
        request.idioma = guardado if guardado in IDIOMAS else IDIOMA_BASE
        return self.get_response(request)


def contexto(request):
    """`lang`, `idioma_urls` (la página actual en cada idioma, conservando el resto de parámetros) y `ui_js` (los textos
    que usa el JavaScript, solo en inglés) en todas las plantillas."""
    from .textos_en import JS_EN
    lang = idioma_de(request)
    resto = [(k, v) for k, vs in request.GET.lists() for v in vs if k != 'lang']
    urls = {i: request.path + '?' + urlencode(resto + [('lang', i)]) for i in IDIOMAS}
    return {'lang': lang, 'idioma_urls': urls, 'ui_js': JS_EN if lang != IDIOMA_BASE else {}}
