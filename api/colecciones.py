# api/colecciones.py
"""Colecciones de ChromaDB que NUNCA se usan: las que antes se construían con PDF de terceros.

Los PDF están aislados del sistema: la API no los monta, no hay forma de activar su uso y el indexador no sabe
leerlos. Lo que ve la IA sale solo de documentos propios (.md) y de la biblioteca de ejercicios, reescritos por
el entrenador. Estos nombres se conservan para bloquear su consulta y para eliminarlos de una base antigua.
No tiene dependencias: lo usan la API y las herramientas."""

COLECCIONES_PDF = frozenset({"teoria", "planificacion", "reglamento"})


def colecciones_a_indexar(todas: dict) -> dict:
    """Las colecciones que se indexan: solo las de documentos propios."""
    return {n: c for n, c in todas.items() if n not in COLECCIONES_PDF}
