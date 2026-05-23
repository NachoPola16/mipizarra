# Entrenamiento y re-entrenamiento del modelo MiPizarra

> ⚠️ **Conflicto GPU (solo si entrenas en el servidor)**: Ollama y el contenedor `finetune`
> comparten la GTX 1060 y no pueden tener un modelo cargado a la vez.
> Usa siempre el wrapper `./tools/finetune.sh` o, manualmente:
> ```bash
> docker compose stop ollama
> docker compose run --rm finetune python tools/finetune_qwen.py --steps 200
> docker compose start ollama
> ```
> Si entrenas en local (RTX 5060 Ti) no hay conflicto — el servidor sigue funcionando.

## Estructura de carpetas

data/pdfs/
  coleccion_entrenamientos/   ← Sesiones y ejercicios de baloncesto (PDFs)
  coleccion_teoria/           ← Metodología, técnica, táctica
  coleccion_reglamento/       ← Reglamento FIBA, normativas
  coleccion_planificacion/    ← Planificación de temporadas

data/dataset/
  from_pdfs.jsonl             ← Generado por indexar_entrenamientos.py
  from_conocimiento.jsonl     ← Generado por indexar_conocimiento.py
  from_web.jsonl              ← Generado por scraper_isportcoach.py
  train.jsonl                 ← Dataset final (generado por generar_dataset.py)
  para_revisar.jsonl          ← Copia legible para revisar manualmente

outputs/
  mipizarra-v1/
    lora_adapters/            ← Pesos LoRA tras el fine-tuning
    gguf/                     ← Modelo GGUF listo para Ollama

docker/
  finetune/
    Dockerfile                ← Dockerfile para construir la imagen de fine‑tuning

cache/                        ← Caché de HuggingFace (volumen para el contenedor)


## Requisitos previos (solo una vez)

### 1. Dockerfile para fine‑tuning (docker/finetune/Dockerfile)

Ya incluido en el repo. Versiones clave:
- CUDA 11.8 + PyTorch 2.5.1 (compat sm_61 = GTX 10xx)
- bitsandbytes==0.42.0 (versiones >=0.43 fallan en Pascal)
- peft, trl, datasets, transformers, accelerate
- llama.cpp construido para conversión HF→GGUF y cuantización Q4_K_M en CPU

### 2. Añade el servicio finetune a tu docker-compose.yml

  finetune:
    build:
      context: ./docker/finetune
      dockerfile: Dockerfile
    container_name: mipizarra-finetune
    profiles: ["training"]
    user: "0:0"                # root para permisos de escritura
    volumes:
      - ./:/workspace
      - ./cache:/workspace/.cache   # caché de HuggingFace escribible
    working_dir: /workspace
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    command: ["bash"]

### 3. Construye la imagen (solo la primera vez)

docker compose build finetune


## Flujo completo de extracción y entrenamiento

### Paso 1 – Extraer ejercicios y sesiones de los PDFs de entrenamiento

Ejecutar dentro del contenedor mipizarra-api:

docker exec -it mipizarra-api python /app/tools/indexar_entrenamientos.py --model qwen2.5:7b-instruct-q4_K_M

Qué hace:
- Lee data/pdfs/coleccion_entrenamientos/
- Detecta si cada PDF es una sesión completa o una colección de ejercicios
- Genera pares de entrenamiento
- Para ejercicios con posiciones (cabecera, codo, esquina…) genera también el diagrama JSON

Salida: data/dataset/from_pdfs.jsonl

### Paso 2 – Extraer conocimiento de teoría, reglamento y planificación

docker exec -it mipizarra-api python /app/tools/indexar_conocimiento.py --model qwen2.5:7b-instruct-q4_K_M

Qué hace:
- Lee los PDFs de coleccion_teoria/, coleccion_reglamento/ y coleccion_planificacion/
- Genera pares pregunta→respuesta sobre metodología, reglas y planificación

Salida: data/dataset/from_conocimiento.jsonl

### Paso 3 – Extraer ejercicios de la web (opcional)

docker exec -it mipizarra-api python /app/tools/scraper_isportcoach.py --model qwen2.5:7b-instruct-q4_K_M

Qué hace:
- Extrae ejercicios de isportcoach.com
- Los convierte en ejemplos de entrenamiento

Salida: data/dataset/from_web.jsonl

### Paso 4 – Generar dataset completo

docker exec -it mipizarra-api python /app/tools/generar_dataset.py --todo

Qué hace:
- Fusiona todas las fuentes en un único JSONL

Salidas:
- Entrenamiento: data/dataset/train.jsonl
- Para revisar: data/dataset/para_revisar.jsonl

⚠️ Importante: revisa para_revisar.jsonl y elimina ejemplos de mala calidad en train.jsonl antes de entrenar. Un dataset pequeño y limpio es mejor que uno grande con ruido.

### Paso 5 – Fine‑tuning

Usa el wrapper (libera Ollama y lo reinicia al terminar):

./tools/finetune.sh           # 100 pasos (default, recalibrado para datasets pequeños)
./tools/finetune.sh --steps 150

Equivalente manual:

docker compose stop ollama
docker compose run --rm finetune python tools/finetune_qwen.py
docker compose start ollama

Qué hace:
- Entrena Qwen3-4B con QLoRA 4-bit en la GTX 1060
- fp16 activo (Pascal sm_61 lo soporta; bf16 no)
- LoRA rank 8 por defecto, alpha 16, dropout 0.05 (anti-overfitting en datasets pequeños)
- Batch efectivo 8 (1 × grad_acc 8), optimizador paged_adamw_8bit
- Filtra ejemplos > seq_len en lugar de truncarlos (preserva calidad)
- Tiempo aproximado: ~12‑22 min para 100 pasos

Cuántos --steps según el tamaño del dataset (regla práctica: 5-8 epochs):

| Ejemplos en train.jsonl | --steps recomendado |
|-------------------------|---------------------|
| <  60                   | 50                  |
| 60-150                  | 100  (default)      |
| 150-300                 | 150                 |
| 300-500                 | 200                 |
| > 500                   | 250-300             |

Si la pérdida (training loss) baja de 0.5 antes de terminar → estás overfitting → baja --steps.
Si se queda > 1.5 al final → el dataset tiene ruido o es demasiado heterogéneo.

Opciones útiles:
- --rank 16: LoRA más grande (subir solo si el dataset supera ~500 ejemplos)
- --solo-atencion: LoRA solo en q/k/v/o (-50% params entrenables, ahorra VRAM si hay OOM)
- --seq-len 2048: longitud de secuencia (default)

Salida: outputs/mipizarra-v1/lora_adapters/

### Paso 6 – Exportar a Ollama

6.1 Ejecutar la exportación dentro del contenedor finetune

docker compose run --rm finetune python tools/exportar_a_ollama.py \
  --lora outputs/mipizarra-v1/lora_adapters \
  --nombre mipizarra

Esto fusiona los pesos LoRA con el modelo base y genera el archivo GGUF en la carpeta ollama/ del proyecto (es decir, en el host ~/docker/mipizarra/ollama/mipizarra.q4_k_m.gguf).

6.2 Copiar el GGUF al directorio de modelos de Ollama

mkdir -p ~/docker/mipizarra/ollama/models
cp ~/docker/mipizarra/ollama/mipizarra.q4_k_m.gguf \
   ~/docker/mipizarra/ollama/models/

6.3 Crear el modelo en Ollama a partir del GGUF

Primero, asegúrate de que el GGUF está accesible dentro del contenedor mipizarra-ollama (la carpeta montada ./ollama corresponde a /root/.ollama). Luego crea el modelo con un Modelfile:

docker exec -it mipizarra-ollama bash -c '
cat > /tmp/Modelfile << "EOF"
FROM /root/.ollama/models/mipizarra.q4_k_m.gguf

SYSTEM """Eres un entrenador experto en baloncesto. Diseñas sesiones estructuradas y prácticas. Usas terminología técnica española (codo TL, cabecera, baseline, poste alto/bajo). Siempre propones ejercicios con posiciones concretas."""

PARAMETER temperature 0.4
PARAMETER top_p 0.9
PARAMETER min_p 0.05
PARAMETER repeat_penalty 1.15
PARAMETER num_ctx 4096
PARAMETER num_gpu 99
PARAMETER num_thread 4
PARAMETER num_batch 256
PARAMETER stop "<|im_end|>"
PARAMETER stop "<|endoftext|>"
PARAMETER stop "<|im_start|>think"
EOF

ollama create mipizarra -f /tmp/Modelfile
'

Verifica que el modelo aparece listado:

docker exec -it mipizarra-ollama ollama list

### Paso 7 – Evaluar contra el modelo base

Antes de promover el modelo, mide si realmente mejora:

docker exec -it mipizarra-api python /app/tools/evaluar_modelo.py \
  --base qwen3:4b \
  --finetuned mipizarra \
  --n 15

Reporta % de sesiones con estructura correcta, 3 ejercicios, sin duplicados, nombres exactos
de la lista, JSON válido en diagramas, etc. Si el fine-tuned no supera al base en al menos
2 métricas críticas, revisa el dataset antes de promover.

### Paso 8 – Activar el modelo en la app

En docker-compose.yml, cambia la variable de entorno:

  api:
    environment:
      - OLLAMA_MODEL=mipizarra

Luego reinicia la API:

docker compose up -d api

### Paso 8 – Evaluar el modelo entrenado vs el base

Antes de dar por bueno el nuevo modelo, mide objetivamente si mejora respecto al base:

docker exec -it mipizarra-api python /app/tools/evaluar_modelo.py \
  --base qwen3:4b \
  --finetuned mipizarra \
  --n 20

Mide sobre 20 sesiones generadas con cada modelo:
- % con las 4 secciones obligatorias (CALENTAMIENTO, PARTE PRINCIPAL, VUELTA A LA CALMA, Fundamentos)
- % con exactamente 3 ejercicios
- % sin ejercicios duplicados
- % con nombres de ejercicios que existen en exercises.json
- Longitud media y tiempo de generación

Si el fine-tuned no mejora ≥ 10 % en formato y nombres correctos, descártalo: el dataset tiene ruido o
faltan ejemplos. Itera sobre el dataset, no sobre los steps.


## RE-ENTRENAMIENTO – Al añadir nuevos PDFs

### Si añadiste PDFs a coleccion_entrenamientos/

docker exec -it mipizarra-api python /app/tools/indexar_entrenamientos.py --model qwen2.5:7b-instruct-q4_K_M
docker exec -it mipizarra-api python /app/tools/generar_dataset.py --todo
docker compose run --rm finetune python tools/finetune_qwen.py --steps 250 --output outputs/mipizarra-v2
# Repite los pasos 6.1 a 6.3 con --lora outputs/mipizarra-v2/lora_adapters

### Si añadiste PDFs a las carpetas de teoría/reglamento/planificación

docker exec -it mipizarra-api python /app/tools/indexar_conocimiento.py --model qwen2.5:7b-instruct-q4_K_M
docker exec -it mipizarra-api python /app/tools/generar_dataset.py --todo
docker compose run --rm finetune python tools/finetune_qwen.py --steps 250 --output outputs/mipizarra-v2
# Repite los pasos 6.1 a 6.3 con --lora outputs/mipizarra-v2/lora_adapters

### Si añadiste PDFs a varias carpetas a la vez

docker exec -it mipizarra-api python /app/tools/indexar_entrenamientos.py --model qwen2.5:7b-instruct-q4_K_M
docker exec -it mipizarra-api python /app/tools/indexar_conocimiento.py --model qwen2.5:7b-instruct-q4_K_M
docker exec -it mipizarra-api python /app/tools/generar_dataset.py --todo
docker compose run --rm finetune python tools/finetune_qwen.py --steps 300 --output outputs/mipizarra-v2
# Repite los pasos 6.1 a 6.3 con --lora outputs/mipizarra-v2/lora_adapters


## Recomendaciones

Situación                    | --steps recomendado
Dataset pequeño (<100 ej.)    | 100–150
Dataset medio (100–300 ej.)   | 200–300
Dataset grande (>300 ej.)     | 300–500

Tips:
- Aumenta --steps con cada nueva versión, no bajes
- Si la pérdida al final es > 1.5, el dataset tiene ruido — revísalo
- Usa --nombre mipizarra-v2, v3, etc. para no sobreescribir versiones anteriores
- Guarda siempre los adaptadores LoRA (lora_adapters/) — son tu modelo entrenado


## Resumen rápido

Añadir PDFs → ejecutar indexar_* dentro de mipizarra-api
           → generar_dataset --todo dentro de mipizarra-api
           → docker compose run --rm finetune python tools/finetune_qwen.py --steps N
           → exportar_a_ollama.py dentro de finetune
           → copiar GGUF y crear modelo en Ollama
           → actualizar OLLAMA_MODEL y docker compose up -d api


---

## Entrenamiento local (sin Docker, GPU con ≥12 GB VRAM)

Con una GPU como la RTX 5060 Ti (16 GB) puedes entrenar directamente en tu PC sin el
contenedor `finetune`. El split óptimo:

| Paso | Dónde | Por qué |
|------|-------|---------|
| Generar dataset | local (llama al Ollama del servidor) | no llena RAM del servidor |
| **Fine-tuning** | **local con `--no-quantize`** | bf16 puro, más rápido, mejor calidad |
| Exportar GGUF | servidor (dentro del contenedor `finetune`) | llama.cpp ya compilado allí |
| Inferencia | servidor (Ollama + GTX 1060) | siempre encendido |

### 1. Configurar entorno Python (una sola vez)

```bash
# Crea el entorno (Windows CMD, PowerShell o WSL2)
conda create -n mipizarra python=3.11 -y
conda activate mipizarra

# PyTorch ≥2.6 con CUDA 12.6 (Blackwell RTX 5000 lo necesita)
pip install torch --index-url https://download.pytorch.org/whl/cu126

# Unsloth: 2× más rápido que TRL, -70% VRAM, soporte nativo Qwen3
pip install unsloth

# Resto de dependencias (bitsandbytes NO necesario con --no-quantize)
pip install transformers>=4.40 peft>=0.10 trl>=0.8 datasets accelerate
```

> **Nota Blackwell**: la RTX 5060 Ti usa arquitectura Blackwell (sm_100).
> PyTorch 2.6+ y CUDA 12.6+ son mínimo para soporte completo.
> Con la rueda `cu126` anterior, bf16 se activa automáticamente.
>
> **Unsloth**: el script `finetune_qwen.py` detecta Unsloth automáticamente al arrancar.
> Si está instalado lo usa; si no, cae en TRL estándar. No requiere cambios de comandos.

### 2. Generar el dataset (apuntando al Ollama del servidor)

Desde la carpeta `mipizarra/` del repo (en tu PC):

```bash
# Indexar PDFs de entrenamientos (necesita PDFs en data/pdfs/coleccion_entrenamientos/)
python tools/indexar_entrenamientos.py \
  --ollama http://<SERVER_IP>:11434 \
  --model qwen2.5:7b-instruct-q4_K_M

# Generar dataset final
python tools/generar_dataset.py --todo
# Revisar data/dataset/para_revisar.jsonl antes de continuar
```

O si prefieres generar el dataset en el servidor y copiarlo:

```bash
# En el servidor:
docker exec -it mipizarra-api python /app/tools/generar_dataset.py --todo

# En tu PC:
scp usuario@<SERVER_IP>:~/docker/mipizarra/data/dataset/train.jsonl data/dataset/
```

### 3. Entrenar localmente

```bash
# Desde la carpeta mipizarra/ (con el entorno mipizarra activado):
conda activate mipizarra
python tools/finetune_qwen.py --no-quantize

# Opciones útiles con 16 GB VRAM:
python tools/finetune_qwen.py --no-quantize --rank 16 --steps 150
```

El script auto-detecta bf16 (activado en Blackwell), elige `adamw_torch_fused` y muestra
la VRAM disponible. Estimado: ~3-5 min por 100 pasos en la RTX 5060 Ti.

### 4. Copiar adaptadores al servidor y exportar

```bash
# Desde tu PC — copia lora_adapters/ al servidor
scp -r outputs/mipizarra-v1/lora_adapters \
    usuario@<SERVER_IP>:~/docker/mipizarra/outputs/mipizarra-v1/

# En el servidor — exportar a GGUF dentro del contenedor finetune
docker compose run --rm finetune python tools/exportar_a_ollama.py \
  --lora outputs/mipizarra-v1/lora_adapters \
  --nombre mipizarra
```

Desde aquí, sigue los pasos 6.2-6.3 del flujo normal (copiar GGUF, crear modelo en Ollama).

### Comparativa de modos

| | GTX 1060 (servidor) | RTX 5060 Ti (local) |
|-|---------------------|---------------------|
| Modelo | Qwen3-4B | Qwen3-4B |
| Framework | TRL SFTTrainer | Unsloth + TRL |
| Modo | QLoRA 4-bit | LoRA puro bf16 |
| Flag | *(ninguno)* | `--no-quantize` |
| bitsandbytes | requerido (0.42.0 fijo) | no necesario |
| Precisión | fp16 | bf16 |
| ~100 pasos | ~12-22 min | ~2-4 min |
| VRAM usada | ~5.5 GB | ~9-11 GB |
| Calidad gradientes | buena | mejor |

---

## Notas técnicas

- Todos los scripts de extracción (indexar_*.py, generar_dataset.py) deben ejecutarse dentro del contenedor mipizarra-api porque requieren el modelo Ollama y las rutas /app/data/...

- El contenedor de fine‑tuning se construye con un Dockerfile especial que incluye CUDA 11.8, PyTorch 2.5.1 y bitsandbytes 0.42.0, compatibles con Pascal (sm_61, GTX 10xx)

- La primera vez que se ejecuta el fine‑tuning, el modelo base se descarga y cachea en el volumen ./cache (montado en /workspace/.cache)

- La exportación genera el GGUF en el volumen compartido ./ollama/. Para que Ollama lo reconozca, debes copiarlo manualmente a ./ollama/models/ y utilizar ollama create con un Modelfile adecuado

- Para detener el contenedor de fine‑tuning después del entrenamiento (si no usaste --rm), ejecuta docker compose down finetune
