# api/i18n_fichas.py
"""Fichas bilingües: el texto de una ficha puede traer un bloque `i18n` con una traducción por idioma.

Los campos de nivel raíz (`nombre`, `descripcion`...) son siempre el texto en español, que es lo que lee el resto del
código. `i18n` solo añade idiomas: `{"i18n": {"en": {"nombre": ..., "descripcion": ..., ...}}}`. Los números, el
diagrama, las edades y las variantes se comparten entre idiomas. Si falta el idioma pedido o un campo concreto, se
cae al español."""
from copy import deepcopy

IDIOMAS = ("es", "en")
IDIOMA_BASE = "es"
# Campos de texto traducibles (mismos nombres que en el nivel raíz).
CAMPOS_TEXTO = ("nombre", "descripcion", "material", "consigna")
CAMPOS_LISTA = ("puntos_clave", "errores_frecuentes", "que_observar")
CAMPOS_TRADUCIBLES = CAMPOS_TEXTO + CAMPOS_LISTA + ("progresion",)
ORIGEN_TIPOS = ("original", "abierta")


def localizar(ficha: dict, idioma: str = IDIOMA_BASE) -> dict:
    """Copia de la ficha con los textos en `idioma` (o en español si no hay traducción). Sin `i18n` en la salida."""
    salida = deepcopy(ficha)
    traduccion = (salida.pop("i18n", None) or {}).get(idioma) if idioma != IDIOMA_BASE else None
    if isinstance(traduccion, dict):
        for campo in CAMPOS_TRADUCIBLES:
            if traduccion.get(campo):
                salida[campo] = deepcopy(traduccion[campo])
        _aplicar_titulos(salida, traduccion)
    salida.pop("i18n", None)
    salida["idioma"] = idioma if isinstance(traduccion, dict) else IDIOMA_BASE
    return salida


def _aplicar_titulos(salida: dict, traduccion: dict) -> None:
    """Aplica `titulos_diagramas` (lista de títulos, uno por diagrama) si la traducción lo trae."""
    titulos = traduccion.get("titulos_diagramas")
    diagramas = salida.get("diagramas")
    if isinstance(titulos, list) and isinstance(diagramas, list):
        for d, t in zip(diagramas, titulos):
            if isinstance(d, dict) and isinstance(t, str) and t.strip():
                d["titulo"] = t


def idiomas_de(ficha: dict) -> list[str]:
    """Idiomas en los que la ficha está completa (siempre el español)."""
    i18n = ficha.get("i18n")
    extra = [i for i in IDIOMAS if i != IDIOMA_BASE and isinstance(i18n, dict) and isinstance(i18n.get(i), dict)]
    return [IDIOMA_BASE, *extra]
