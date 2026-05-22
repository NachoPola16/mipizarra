#!/usr/bin/env bash
# Wrapper para entrenar liberando la GPU de Ollama mientras dure el fine-tuning.
# Uso (en el host, desde ~/docker/mipizarra/):
#   ./tools/finetune.sh                       # 200 pasos, defaults
#   ./tools/finetune.sh --steps 300 --rank 8  # cualquier flag de finetune_qwen.py
set -euo pipefail

echo "▶ Parando contenedor mipizarra-ollama para liberar la GPU..."
docker compose stop ollama

trap 'echo "▶ Reiniciando mipizarra-ollama..."; docker compose start ollama' EXIT

echo "▶ Lanzando fine-tuning..."
docker compose run --rm finetune python tools/finetune_qwen.py "$@"

echo "✓ Fine-tuning terminado."
