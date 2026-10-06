# Arquitectura del sistema

## Componentes

```
Navegador ──▶ frontend (Django) ──▶ api (FastAPI) ──▶ ollama (LLM + embeddings)
                                        │
                                        ├──▶ ChromaDB (colecciones de teoría y reglamento)
                                        └──▶ data/exercises.json (biblioteca de ejercicios)
```

| Componente | Responsabilidad |
|---|---|
| `frontend/` | Interfaz web: formulario de sesión, modo reglamento, exportación a PDF, corrección de ejercicios. |
| `api/main.py` | Endpoints HTTP (`/generar`, `/ejercicio`, `/reprompt_ejercicio`, `/reglamento`, `/ambitos_reglamento`, ...), rate limiting y autenticación interna. |
| `api/rag_engine.py` | Fachada: reexporta los nombres públicos de los módulos de abajo (la usan `main.py`, las herramientas y los tests). Sin lógica propia. |
| `api/config.py` | Variables de entorno, modelos, rutas, mapeo de categorías y nombres de ámbito de reglamento. Sin dependencias pesadas. |
| `api/ejercicios.py` | Biblioteca de ejercicios: carga, filtrado por edad y objetivo, selección de los n ejercicios de la parte principal (con el arco sin oposición → igualada), umbral de relevancia y contexto de ejercicios para el prompt. |
| `api/contexto.py` | Recuperación (RAG): consulta a las colecciones de ChromaDB, presupuesto de contexto por colección y ámbitos de reglamento. |
| `api/sesion.py` | Modo 1: generación de la sesión completa. Pide al plan cuántos ejercicios lleva, elige las fichas, pide al LLM solo lo que no está curado (calentamiento, vuelta a la calma, fundamentos y huecos sin ficha), valida sus líneas rojas y ensambla el texto final. |
| `api/plan_sesion.py` | Reparto de tiempo: cuántos ejercicios (entre 5 y 8 en total, contando calentamiento y vuelta a la calma) y cuánto dura cada uno según duración y edad. Minibasket: más ejercicios y más cortos. |
| `api/bloques.py` | Bloques de la sesión que compone el código: ficha curada íntegra (descripción y puntos clave de `exercises.json`), variante desde la progresión de la ficha (si la trae) y troceado de la respuesta del modelo. |
| `api/lineas_rojas.py` | Guardia léxica de líneas rojas por edad para todo texto generado por el modelo, e instrucción equivalente para el prompt. |
| `api/diagramas.py` | Coordenadas JSON de los diagramas (JSON Schema + validador semántico + reintento). |
| `api/ejercicio_unico.py` | Modo 2: ejercicio suelto y reprompt (corrección pedida por el entrenador). |
| `api/reglamento.py` | Modo 3: dudas de reglamento y fundamentos técnicos, por ámbito. |
| `api/prompts.py` | System prompts compartidos por la inferencia y el entrenamiento. |
| `api/diagram_renderer.py` | Convierte el JSON de un diagrama en SVG de forma determinista. Separa al dibujar los marcadores solapados sin cambiar el JSON. |
| `api/posiciones.py` | Diccionario único de posiciones con nombre (`codo_derecho`, `poste_bajo_izquierdo`...) y lectura de cualquier punto de un diagrama (`x`/`y` o nombre). |
| `api/solapes.py` | Separación mínima y determinista de marcadores a menos de 8 unidades. La usan el renderer y el validador. |
| `api/plantillas.py` | Plantillas de diagrama de calentamiento y vuelta a la calma (rondo, cuatro esquinas, zigzag de conos...) generadas sin modelo. |
| `tools/` | Indexación de colecciones, arnés de regresión y exportación/importación editable de la biblioteca. |
| `experimental/` | Fine-tuning, exportación y evaluación del modelo. No forma parte del flujo actual (ver `experimental/README.md`). |

### Dependencias entre módulos de `api/`

```
config            (no importa a ningún otro módulo)
ejercicios        → config
bloques           (no importa a ningún otro módulo)
lineas_rojas      (no importa a ningún otro módulo)
plan_sesion       (no importa a ningún otro módulo)
contexto          → config
posiciones        (no importa a ningún otro módulo)
solapes           (no importa a ningún otro módulo)
plantillas        → posiciones
diagram_renderer  → posiciones, solapes
diagramas         → config, ejercicios, prompts, posiciones, solapes
ejercicio_unico   → config, ejercicios
sesion            → config, contexto, ejercicios, bloques, lineas_rojas, plan_sesion
reglamento        → config, contexto, prompts
rag_engine        → todos los anteriores (fachada)
main              → rag_engine, diagram_renderer
```

El grafo es acíclico: ningún módulo importa a `rag_engine` salvo `main.py`.
`contexto` es el único módulo que crea el cliente de ChromaDB y el modelo de embeddings al importarse.

Al parchear una función en un test hay que hacerlo en el módulo donde vive (por ejemplo,
`reglamento.consultar_coleccion` o `contexto.REGLAMENTO_DIR`), no en la fachada `rag_engine`.

## Flujo de una sesión

1. El frontend envía categoría, duración y objetivo a la API.
2. `ejercicios` filtra ejercicios por edad y objetivos, y `contexto` recupera teoría relevante de ChromaDB (presupuesto de contexto por colección).
3. `plan_sesion` decide cuántos ejercicios lleva la parte principal y cuánto dura cada uno (la sesión completa tiene entre 5 y 8 contando calentamiento y vuelta a la calma). Cada hueco usa una ficha de la biblioteca si encaja con el objetivo (`es_relevante`); si no, lo propone la IA y se marca «Propuesto por la IA (sin revisar)».
4. El código compone los ejercicios con la ficha curada íntegra (descripción y puntos clave tal cual) y, si la ficha trae progresión y el ejercicio es largo para esa edad, su variante N.2. El LLM redacta solo calentamiento, vuelta a la calma, fundamentos y los huecos propuestos, paso a paso (si se detiene, se le piden los apartados que faltan); si algo incumple las líneas rojas de la edad se reintenta una vez y, si persiste, se omite esa pieza (queda en `avisos`).
5. Para cada ejercicio se usa el diagrama de la biblioteca si existe; si no, se genera uno desde la descripción.
6. La sesión y los SVG se devuelven al frontend.

## Los PDF de terceros están aislados

La IA solo ve documentos propios: los `.md` de `data/teoria` y `data/reglamento` (reescritos por el entrenador) y la
biblioteca `data/exercises.json`. Los PDF (`data/pdfs/`, ignorada por git) son material de trabajo en local para
escribir documentos nuevos con palabras propias, y quedan fuera del sistema:

- el contenedor de la API **no monta** `data/pdfs` (solo monta, una a una, las carpetas que necesita);
- no hay ningún ajuste para activarlos y `consultar_coleccion` bloquea las colecciones que antes se construían con ellos;
- `tools/indexar_colecciones.py` no sabe leer PDF y, al ejecutarse, elimina esas colecciones de la base.

Un test (`tests/test_aislamiento_pdf.py`) falla si alguien vuelve a montar la carpeta o a leer PDF.

## Diagramas fiables

El LLM nunca dibuja: solo produce JSON de coordenadas (ver [coordenadas.md](coordenadas.md)).

- La salida se restringe con un **JSON Schema** (decodificación guiada por gramática en Ollama).
- Un **validador semántico** comprueba lo que el schema no puede expresar: referencias a jugadores declarados, posiciones con nombre conocidas, número de atacantes/defensores coherente con el nombre (`2c1`, `3c2`...), distancia mínima entre jugadores.
- Antes de rechazar, el validador **repara** lo que tiene arreglo determinista: el `a_pos` que falta cuando el propio diagrama lo indica y los jugadores demasiado cerca si caben separándolos un poco (detalle en [coordenadas.md](coordenadas.md#reparación-en-el-validador)).
- Si la validación falla, se reintenta una vez indicando el error; si vuelve a fallar, se devuelve "diagrama no disponible" en lugar de un dibujo incorrecto.
- Al dibujar, el renderer separa los marcadores que siguen solapados (por ejemplo, en la biblioteca curada) sin modificar el JSON.
- Para calentamiento y vuelta a la calma hay plantillas que producen un diagrama válido sin modelo (`api/plantillas.py`); todavía no están conectadas a la generación de sesiones.

## Colecciones RAG

| Colección | Contenido |
|---|---|
| `teoria_md` | Documentos de teoría curados en `data/teoria/` (prioritarios). |
| `teoria` | Material técnico y metodológico adicional. |
| `planificacion` | Planificación de temporada. |
| `reglamento_md` | Reglamento curado en `data/reglamento/<ámbito>/` (`general` = FIBA y federación española; una carpeta por comunidad autónoma). Cada documento lleva su ámbito como metadato. |
| `reglamento` | Documentos oficiales en PDF (capa local opcional), con la misma convención de ámbitos. |

En el modo reglamento se elige el ámbito: con una comunidad autónoma se recupera primero su normativa y se
completa con la general, que se usa siempre como base. Véase `docs/actualizar_reglamento.md`.

Solo `teoria_md` y `reglamento_md` forman parte del repositorio; el resto de material de referencia no se distribuye.
