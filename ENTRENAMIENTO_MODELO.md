# Entrenamiento del modelo

> 🧪 **Experimental**: el fine-tuning no forma parte del flujo actual de MiPizarra. Los scripts viven
> en [`experimental/`](experimental/README.md) y no se mantienen al ritmo del resto del proyecto.

El fine-tuning es **opcional**: MiPizarra funciona con el modelo base + RAG.
Entrena solo si la evaluación muestra que el modelo base no basta.

> ⚠️ **GPU compartida**: si entrenas en la misma máquina que sirve Ollama y la
> GPU no tiene memoria para ambos, para Ollama durante el entrenamiento. El
> wrapper `./experimental/finetune.sh` lo hace automáticamente.

## Estructura de carpetas

```
data/pdfs/                  ← Material local (no incluido en el repo)
data/dataset/
  train.jsonl               ← Dataset final (generado por generar_dataset.py)
  para_revisar.jsonl        ← Copia legible para revisar manualmente
outputs/<version>/
  lora_adapters/            ← Pesos LoRA tras el fine-tuning
experimental/docker/finetune/Dockerfile  ← Imagen de fine-tuning
cache/                      ← Caché de HuggingFace
```

## Flujo

### 1. Construir la imagen de fine-tuning (una vez)

```bash
docker compose build finetune
```

### 2. Generar el dataset

El dataset se genera a partir de `data/exercises.json` y de los `.md` de `data/teoria/`. Se puede
fusionar con conjuntos de datos adicionales locales (`data/dataset/extra_*.jsonl`) con
`--incluir-entrenamientos`, `--incluir-conocimiento` o `--incluir-externo`:

```bash
docker exec -it mipizarra-api python /app/experimental/generar_dataset.py --todo
```

⚠️ Revisa `para_revisar.jsonl` y elimina ejemplos malos de `train.jsonl` antes
de entrenar. Un dataset pequeño y limpio es mejor que uno grande con ruido.

### 3. Fine-tuning

```bash
./experimental/finetune.sh               # 100 pasos por defecto
./experimental/finetune.sh --steps 150
```

- QLoRA 4-bit por defecto; `--no-quantize` para LoRA en bf16 si la GPU tiene memoria suficiente.
- Usa Unsloth si está instalado; si no, TRL estándar.
- LoRA rank 8, alpha 16, dropout 0.05; ejemplos más largos que `--seq-len` se descartan en vez de truncarse.

Pasos orientativos según tamaño del dataset (≈5-8 epochs):

| Ejemplos en train.jsonl | --steps |
|---|---|
| < 60 | 50 |
| 60-150 | 100 |
| 150-300 | 150 |
| 300-500 | 200 |
| > 500 | 250-300 |

Si la loss baja de 0.5 antes de terminar → sobreajuste, baja `--steps`.
Si se queda por encima de 1.5 → el dataset tiene ruido o es demasiado heterogéneo.

Opciones: `--rank 16` (solo con >500 ejemplos), `--solo-atencion` (menos VRAM),
`--seq-len 2048`, `--output outputs/<version>`.

### 4. Exportar a Ollama

```bash
docker compose run --rm finetune python experimental/exportar_a_ollama.py \
  --lora outputs/mipizarra-v1/lora_adapters --nombre mipizarra
```

Fusiona los adaptadores con el modelo base, genera un GGUF Q4_K_M y registra
el modelo en Ollama. Si el registro automático falla, el script imprime el
comando `ollama create` equivalente.

### 5. Evaluar contra el modelo base

```bash
docker exec -it mipizarra-api python /app/experimental/evaluar_modelo.py \
  --base qwen3:4b-instruct --finetuned mipizarra --n 20
```

Mide estructura de la sesión, número de ejercicios, duplicados, nombres de
ejercicios existentes en la biblioteca, JSON de diagrama válido, longitud y
tiempo. Si el modelo entrenado no mejora claramente, no lo actives: itera sobre
el dataset, no sobre `--steps`.

### 6. Activar el modelo

En `.env`: `OLLAMA_MODEL=mipizarra` y `docker compose up -d api`.

## Consejos

- Versiona las salidas (`mipizarra-v2`, `v3`...) para no sobrescribir modelos anteriores.
- Guarda siempre los `lora_adapters/`: son el modelo entrenado.
- El primer entrenamiento descarga el modelo base en `./cache`.
