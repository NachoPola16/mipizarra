from django import template

from ..idioma import IDIOMA_BASE, idioma_de
from ..textos_en import TEXTOS_EN

register = template.Library()


@register.simple_tag(takes_context=True)
def t(context, texto):
    """`{% t "Texto en español" %}`: el texto en inglés si la interfaz está en inglés y existe en el catálogo; si no, el
    texto original. Autoescapado como cualquier variable de plantilla."""
    request = context.get('request')
    if request is None or idioma_de(request) == IDIOMA_BASE:
        return texto
    return TEXTOS_EN.get(texto, texto)
