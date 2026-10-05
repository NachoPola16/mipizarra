# api/rag_engine.py
"""Fachada: reexporta los nombres públicos que usan main.py, las herramientas y los tests.

La lógica vive en módulos independientes (ver docs/arquitectura.md):
  config.py          configuración y variables de entorno
  ejercicios.py      biblioteca de ejercicios, filtrado y selección
  contexto.py        recuperación (RAG) y ámbitos de reglamento
  sesion.py          modo 1: sesión completa
  diagramas.py       coordenadas JSON de diagramas y su validación
  ejercicio_unico.py modo 2: ejercicio suelto y reprompt
  reglamento.py      modo 3: dudas de reglamento

Al parchear una función en un test hay que hacerlo en el módulo donde vive, no aquí.
"""
from config import (  # noqa: F401
    AMBITO_GENERAL, CHROMA_DB_DIR, EDAD_A_CATEGORIA, EMBED_MODEL, EXERCISES_PATH,
    MODEL, MODEL_REGLAMENTO, MODEL_SESION, NOMBRES_AMBITO, OLLAMA_URL, REGLAMENTO_DIR, _AMBITO_RE,
)
from ejercicios import (  # noqa: F401
    COMPONENTES_ANALITICOS, cargar_ejercicios, filtrar_ejercicios,
    seleccionar_tres_ejercicios, construir_contexto_ejercicios,
    _extraer_conteo_nc_m, _nivel_oposicion, _palabras_objetivo,
)
from contexto import (  # noqa: F401
    nombre_ambito, listar_ambitos, normalizar_ambito,
    consultar_coleccion, construir_contexto_teoria,
)
from sesion import (  # noqa: F401
    CATEGORIAS_SIN_POSTE_NI_BLOQUEO, MAX_BLOQUE_POR_EDAD, MAX_BLOQUE_DEFECTO,
    vocabulario_tecnico, generar_sesion,
    _eliminar_secciones_duplicadas, _redondear_5, _bloque_ejercicio,
)
from diagramas import (  # noqa: F401
    generar_diagrama_desde_texto, generar_coordenadas_ejercicio,
    _DIAGRAMA_JSON_SCHEMA, _validar_diagrama,
)
from ejercicio_unico import generar_ejercicio_unico, reprompt_ejercicio  # noqa: F401
from reglamento import responder_duda_reglamento  # noqa: F401
from prompts import SYSTEM_SESION, SYSTEM_EJERCICIO, SYSTEM_DIAGRAMA, SYSTEM_REGLAMENTO  # noqa: F401
