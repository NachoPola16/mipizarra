# MiPizarra

> Trabajo en progreso — proyecto personal de aprendizaje.

Asistente de entrenamiento de baloncesto con IA 100% local. Dado un objetivo táctico, una categoría de edad y la duración disponible, genera una sesión completa con ejercicios y diagramas tácticos en SVG.

No usa ninguna API externa: el LLM, los embeddings y la base de datos vectorial corren en tu propio hardware.

## Funcionamiento

1. El usuario describe el objetivo del entrenamiento (ej. "Entrenamiento de tiro, tipos de salidas y contraataque, 90 minutos").
2. El RAG recupera ejercicios y teoría relevantes de la biblioteca JSON + ChromaDB.
3. Un LLM local redacta la sesión.
4. El renderer SVG determinista genera los diagramas tácticos (media pista / pista completa).

Además de sesiones completas, permite pedir un ejercicio concreto, corregir ejercicios ya generados y consultar dudas de reglamento.

## Stack

- **LLM:** familia Qwen3 (4B) servida con Ollama, con opción de fine-tuning LoRA propio
- **Embeddings:** `nomic-embed-text` via Ollama
- **RAG:** biblioteca de ejercicios en JSON + ChromaDB
- **Diagramas:** renderer SVG determinista (Python puro, sin dependencias gráficas)
- **API:** FastAPI + rate limiting
- **Frontend:** Django
- **Infra:** Docker Compose con GPU NVIDIA

## Arranque rápido

Requiere Docker con soporte NVIDIA.

```bash
cp .env.example .env
# Edita .env si quieres restringir BIND_IP a tu red local
docker compose up -d
docker exec -it mipizarra-ollama ollama pull qwen3:4b-instruct
docker exec -it mipizarra-ollama ollama pull nomic-embed-text
```

## Uso de la API

```bash
curl -X POST http://localhost:8090/generar \
  -H "Content-Type: application/json" \
  -d '{"edad":"U16","duracion":90,"objetivo":"bloqueo directo"}'
```

## Tests de regresión

Dos niveles, para detectar si un cambio de modelo o de prompts empeora la calidad:

**Tests offline** (`tests/`, sin Ollama ni red): validador de diagramas, filtrado y
selección de ejercicios, parseo de sesiones (incluidas variantes N.1/N.2), renderer SVG
sobre toda la biblioteca e invariantes de `data/exercises.json`.

```bash
pip install -r requirements-dev.txt
pytest
```

**Arnés en vivo** (`tools/regresion.py`): lanza 13 casos fijos (6 sesiones, 2 ejercicios
con diagrama y 5 preguntas de reglamento) contra la API real y comprueba estructura de
la sesión, diagramas, reglas de edad (≤U12) y que no se citen fuentes. Necesita la API
levantada con Ollama y GPU.

```bash
python tools/regresion.py                                  # guarda data/regresion/AAAA-MM-DD_HHMM.json
python tools/regresion.py --solo sesiones                  # sesiones | ejercicios | reglamento
python tools/regresion.py --comparar data/regresion/<anterior>.json
```

Muestra una tabla en consola y devuelve código de salida 1 si falla algún criterio duro
o si `--comparar` detecta empeoramientos. Lanza una ejecución de referencia antes de
cambiar modelo o prompts y compara después. El límite de `/generar` (10/hora por IP)
solo permite una ejecución completa por hora; reiniciar el contenedor de la API lo
resetea. Los resultados no se versionan (`data/regresion/` está en `.gitignore`).

## Documentación

- [Arquitectura](docs/arquitectura.md)
- [Entrenamiento del modelo](ENTRENAMIENTO_MODELO.md)
- [Esquema de ejercicios](docs/esquema-ejercicios.md)
- [Coordenadas del diagrama](docs/coordenadas.md)
- [Seguridad y despliegue](SEGURIDAD.md)
- [Hoja de ruta](docs/fases.md)
