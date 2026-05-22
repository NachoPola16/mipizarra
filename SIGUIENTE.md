# MiPizarra — siguiente sesión

> **Léeme al abrir un chat sobre MiPizarra**. Resume estado, próximo paso y decisiones ya tomadas.

## Qué es MiPizarra

Asistente local de entrenamiento de baloncesto. Genera sesiones (texto) y diagramas tácticos
(JSON → SVG via renderer determinista). Corre en LXC Proxmox con GTX 1060 6GB.

- LLM base: **Qwen2.5-3B-Instruct** en Ollama (Q4_K_M).
- Fine-tuning: **QLoRA** sobre el base con dataset propio.
- Modelo "profesor" para destilar dataset sintético: **qwen2.5:7b-instruct-q4_K_M**.
- Carpeta canónica del servicio: **`mipizarra/`** (antes `hoops-coach`).

## Estado actual (2026-05-15)

**Configuración ya optimizada para la 1060 6GB y aplicada en el repo:**
- num_ctx alineado a 4096/6144 según uso · fp16 activo · bitsandbytes==0.42.0 (Pascal-safe)
- LoRA rank 8 (alpha 16, dropout 0.05) · grad_acc 8 · paged_adamw_8bit · filtrado por longitud
- Wrapper `tools/finetune.sh` que libera Ollama durante el training
- Tabla canónica de coordenadas en [docs/coordenadas.md](docs/coordenadas.md)
- Dataset semilla: 15 ejercicios en [data/exercises.json](data/exercises.json) (13 con diagrama)
- 28 patrones únicos de diagrama, 15 descripciones únicas, `random.sample` sin reemplazo
- `--steps` default 100 (recalibrado para datasets pequeños)
- Script de evaluación base vs fine-tuned: [tools/evaluar_modelo.py](tools/evaluar_modelo.py)

**Pendiente del usuario antes de entrenar (en este orden):**

1. **Verificar visualmente los 13 SVG** generados desde `exercises.json` con
   `api/diagram_renderer.py`. Comando en `ENTRENAMIENTO_MODELO.md`. Si algún diagrama es raro,
   editar el JSON antes de entrenar.
2. (Opcional pero recomendado) Añadir más ejercicios reales propios a `data/exercises.json`
   hasta ≥30. Más vale 30 verificados que 200 sintéticos.
3. **Pull en el servidor**:
   ```bash
   docker exec -it mipizarra-ollama ollama pull qwen2.5:7b-instruct-q4_K_M
   docker exec -it mipizarra-ollama ollama pull qwen2.5:3b-instruct-q4_K_M
   docker exec -it mipizarra-ollama ollama pull nomic-embed-text
   ```
4. **Rebuild imagen finetune** (cambió el pin de bitsandbytes):
   ```bash
   docker compose build finetune
   ```
5. (Recomendado) **Probar el RAG con el modelo base sin fine-tuning** vía `curl` al endpoint
   `/generar`. Si la calidad ya vale, no entrenar.

## Flujo completo cuando todo esté listo

```bash
docker exec -it mipizarra-api python /app/tools/generar_dataset.py --todo   # ~15-25 min
# revisar data/dataset/para_revisar.jsonl y borrar ejemplos malos de train.jsonl
./tools/finetune.sh                                                          # ~12-22 min
docker compose run --rm finetune python tools/exportar_a_ollama.py \
  --lora outputs/mipizarra-v1/lora_adapters --nombre mipizarra              # ~15-20 min
docker exec -it mipizarra-api python /app/tools/evaluar_modelo.py \
  --base qwen2.5:3b-instruct-q4_K_M --finetuned mipizarra --n 15            # ~10 min
```

Regla: si `evaluar_modelo.py` reporta "⚠ no mejora claramente", **no** activar
`OLLAMA_MODEL=mipizarra`. Iterar sobre el dataset, no sobre `--steps`.

## Decisiones ya tomadas (no re-debatir)

- **Modelo base**: Qwen2.5-3B-Instruct (Qwen3-4B descartado: queda al filo de VRAM).
- **LoRA rank 8** mientras dataset < 500 ejemplos.
- **Modelo profesor 7B** en lugar de Llama3.2-3B (mejor destilación).
- **Diagramas = JSON → SVG**, no imágenes generativas. El modelo solo aprende coordenadas;
  el renderer (`api/diagram_renderer.py`) ya pinta pista FIBA + minibasket bien.
- **Conflicto GPU**: Ollama y el contenedor `finetune` no pueden tener un modelo cargado a
  la vez. El wrapper `tools/finetune.sh` lo gestiona automáticamente.

## Riesgos vivos

- Qwen2.5:7B Q4_K_M ocupa ~4.7 GB; con num_ctx alto puede paginar a CPU. Si `generar_dataset.py`
  va lentísimo, bajar `num_ctx` a 2048 en `llamar_ollama()`.
- Sin PDFs reales en `data/pdfs/`, el dataset es 100% sintético del 7B → calidad limitada.
  Si las sesiones generadas se parecen demasiado entre sí, el problema está en la diversidad
  de la lista de objetivos/edades/duraciones, no en los `--steps`.

## Documentos clave en este orden

1. Este archivo
2. [ENTRENAMIENTO_MODELO.md](ENTRENAMIENTO_MODELO.md) — flujo paso a paso
3. [docs/coordenadas.md](docs/coordenadas.md) — sistema de coordenadas
4. [docs/esquema-ejercicios.md](docs/esquema-ejercicios.md) — schema de `exercises.json`
