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
| `api/rag_engine.py` | Recuperación de contexto (RAG) y llamadas al LLM para cada modo. |
| `api/prompts.py` | System prompts compartidos por inferencia y generación de dataset. |
| `api/diagram_renderer.py` | Convierte el JSON de un diagrama en SVG de forma determinista. |
| `tools/` | Indexación de colecciones, generación de dataset, fine-tuning, exportación y evaluación del modelo. |

## Flujo de una sesión

1. El frontend envía categoría, duración y objetivo a la API.
2. `rag_engine` filtra ejercicios por edad y objetivos, y recupera teoría relevante de ChromaDB (presupuesto de contexto por colección).
3. El LLM redacta la sesión con una plantilla fija (calentamiento, parte principal, vuelta a la calma, fundamentos).
4. Para cada ejercicio se usa el diagrama de la biblioteca si existe; si no, se genera uno desde la descripción.
5. La sesión y los SVG se devuelven al frontend.

## Diagramas fiables

El LLM nunca dibuja: solo produce JSON de coordenadas (ver [coordenadas.md](coordenadas.md)).

- La salida se restringe con un **JSON Schema** (decodificación guiada por gramática en Ollama).
- Un **validador semántico** comprueba lo que el schema no puede expresar: referencias a jugadores declarados, número de atacantes/defensores coherente con el nombre (`2c1`, `3c2`...), distancia mínima entre jugadores.
- Si la validación falla, se reintenta una vez indicando el error; si vuelve a fallar, se devuelve "diagrama no disponible" en lugar de un dibujo incorrecto.

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
