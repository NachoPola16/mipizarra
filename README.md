# MiPizarra

> Trabajo en progreso — proyecto personal de aprendizaje.

Asistente de entrenamiento de baloncesto con IA 100% local. Dado un objetivo táctico, una categoría de edad y la duración disponible, genera una sesión completa con ejercicios y diagramas tácticos en SVG.

No usa ninguna API externa: el LLM, los embeddings y la base de datos vectorial corren en tu propio hardware.

## Funcionamiento

1. El usuario describe el objetivo del entrenamiento (ej. "bloqueo directo Cadete, 90 minutos").
2. El RAG recupera ejercicios relevantes de la biblioteca JSON + ChromaDB.
3. Un LLM fine-tuned (`mipizarra`, QLoRA sobre Qwen2.5-3B) redacta la sesión.
4. El renderer SVG determinista genera los diagramas tácticos (media pista / pista completa).

## Stack

- **LLM fine-tuned:** `mipizarra` (QLoRA sobre Qwen2.5-3B-Instruct via Ollama)
- **LLM profesor (dataset sintético):** `qwen2.5:7b-instruct-q4_K_M`
- **Embeddings:** `nomic-embed-text` via Ollama
- **RAG:** biblioteca de ejercicios en JSON + ChromaDB
- **Diagramas:** renderer SVG determinista (Python puro, sin dependencias gráficas)
- **API:** FastAPI + rate limiting
- **Frontend:** Django
- **Infra:** Docker Compose, GPU NVIDIA, Proxmox

## Arranque rapido

Requiere Docker con soporte NVIDIA y Ollama.

```bash
cp .env.example .env
# Edita .env si quieres restringir BIND_IP a tu LAN
docker compose up -d
docker exec -it mipizarra-ollama ollama pull qwen2.5:3b-instruct-q4_K_M
docker exec -it mipizarra-ollama ollama pull nomic-embed-text
```

## Uso de la API

```bash
curl -X POST http://localhost:8090/generar \
  -H "Content-Type: application/json" \
  -d '{"edad":"U16","duracion":90,"objetivo":"bloqueo directo"}'
```

## Documentacion

- [Arquitectura](docs/arquitectura.md)
- [Entrenamiento del modelo](ENTRENAMIENTO_MODELO.md)
- [Esquema de ejercicios](docs/esquema-ejercicios.md)
- [Coordenadas del diagrama](docs/coordenadas.md)
- [Seguridad y despliegue](SEGURIDAD.md)
