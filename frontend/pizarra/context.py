from .cuentas import _es_admin


def admin(request):
    """`es_admin` en todas las plantillas: enseña la pestaña «Fichas» solo a la cuenta administradora."""
    return {'es_admin': _es_admin(request)}
