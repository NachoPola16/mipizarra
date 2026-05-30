# Revisión independiente — MiPizarra

Eres un revisor técnico externo. Lee los archivos adjuntos y evalúa si el proyecto va por buen camino.
Busca en internet todo lo que necesites para dar una opinión fundamentada.

---

## El proyecto en una línea

**MiPizarra** es un asistente local de entrenamiento de baloncesto para entrenadores españoles
de categorías de formación (U8–U18). Corre 100 % en local en un servidor doméstico con
GTX 1060 6 GB (LXC Ubuntu, Docker Compose). El entrenador escribe en castellano y recibe:

- Sesiones de entrenamiento completas con ejercicios y tiempos.
- Ejercicios concretos con descripción + diagrama SVG de pista (generado desde JSON de coordenadas).
- Respuestas sobre reglamento y conceptos técnicos de baloncesto.

Stack: **FastAPI + Ollama (Qwen3-4B Q4_K_M) + ChromaDB (RAG) + LoRA fine-tuning (Unsloth)**.

Lee `SIGUIENTE.md` para el estado actual completo antes de responder.

---

## Tu tarea (en este orden)

### 1. Enfoque técnico — ¿vamos bien?

Busca en internet (2025-2026) y responde:

- **Modelo base**: ¿Es Qwen3-4B Q4_K_M una buena elección para esto en una 1060 6 GB?
  ¿Hay alternativas más adecuadas (Mistral, Llama3, Gemma, etc.) para un asistente de nicho en español?
- **RAG + fine-tuning**: ¿Tiene sentido la combinación para este caso de uso?
  ¿O RAG solo ya sería suficiente sin fine-tuning?
- **ChromaDB**: ¿Es la opción correcta para el volumen de documentos (~20 .md + 58 ejercicios JSON)?
  ¿Hay alternativas más ligeras que encajen mejor?
- **¿Existe ya algo parecido?** ¿Hay modelos o proyectos públicos de asistentes de baloncesto/coaching deportivo con LLM? ¿Datasets públicos de ejercicios de baloncesto?
- **Ollama**: ¿Sigue siendo la mejor opción para servir el modelo en local con GPU Pascal (CUDA 10.x)?

### 2. Dataset y fine-tuning — ¿es coherente?

Lee `generar_dataset.py` y los 5 ejercicios de muestra (`muestra_ejercicios.json`).

- **Volumen**: El pipeline genera ~135 ejemplos (60 sesiones + 20 diagramas + 15 ejercicios JSON + 40 reglamento).
  ¿Es suficiente para que LoRA rank 8 con 150 pasos mejore significativamente sobre el modelo base?
  ¿O estamos infraentrenando / sobreajustando con tan pocos ejemplos?
- **Formato del dataset**: Los ejemplos tienen `conversations: [{role, content}]`. ¿Es el formato correcto para Unsloth + Qwen3?
- **Calidad del sistema de prompts**: Hay 3 SYSTEM prompts diferenciados (sesión, ejercicio, reglamento).
  ¿Ves algún problema en la estrategia de separar modos con system prompts distintos?
- **Diagramas como JSON de coordenadas**: ¿Puede un LLM de 4B parámetros aprender a generar
  coordenadas (x, y) coherentes con solo ~20 ejemplos de diagrama en el fine-tuning?

### 3. Schema de ejercicios y coordenadas

Lee `esquema-ejercicios.md` y `coordenadas.md`.

- ¿El schema JSON es suficiente para representar drills de baloncesto reales?
  ¿Hay campos importantes que falten?
- ¿El sistema de coordenadas normalizadas (0-100) es razonable para una pista de baloncesto?
  ¿Hay algún estándar de facto en software de coaching deportivo?
- ¿Tiene sentido que el modelo genere el JSON de diagrama directamente,
  o sería mejor un enfoque distinto (ej. lenguaje de descripción → renderer separado)?

### 4. Riesgos y fallos de diseño

Sé directo y crítico. Si algo está mal, dilo. Si algo está bien, dilo también.

- ¿Hay algún fallo **fundamental** en la arquitectura que convenga corregir antes de entrenar?
- ¿Qué es lo más probable que falle cuando el entrenador use el asistente en producción?
- ¿El pipeline de fine-tuning (LoRA rank 8, alpha 16, dropout 0.05, 150 pasos, paged_adamw_8bit)
  tiene sentido para un dataset de ~135 ejemplos?
- ¿Merece la pena la complejidad del fine-tuning para este caso de uso, o hay un camino más corto
  (few-shot prompting, RAG mejorado, prompt engineering avanzado) que dé resultados parecidos
  con menos riesgo?

### 5. Recomendaciones concretas

Máximo **5 recomendaciones**, ordenadas por impacto real sobre la calidad del asistente.
Sin relleno. Solo las que cambiarían algo importante.

---

## Archivos adjuntos

| Archivo | Qué es |
|---|---|
| `SIGUIENTE.md` | Estado completo del proyecto, decisiones tomadas, próximos pasos |
| `generar_dataset.py` | Generación del dataset de fine-tuning (4 tipos de ejemplos) |
| `rag_engine.py` | RAG + los 3 modos de generación (sesión, ejercicio, reglamento) |
| `muestra_ejercicios.json` | 5 ejercicios representativos del schema |
| `esquema-ejercicios.md` | Documentación del schema de ejercicios |
| `coordenadas.md` | Sistema de coordenadas para diagramas SVG |

Puedes buscar en internet cualquier información adicional que necesites.
