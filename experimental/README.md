# Experimental

Esta carpeta **no forma parte del flujo actual** de MiPizarra. La aplicación funciona con el modelo
base de Ollama más recuperación de contexto (RAG) y no necesita nada de lo que hay aquí.

Contiene el pipeline de fine-tuning LoRA/QLoRA que se probó como mejora opcional. No se ejecuta en
los tests ni en el despliegue normal, y puede quedar desfasado respecto a `api/`.

| Fichero | Para qué sirve |
|---|---|
| `generar_dataset.py` | Construye el dataset de entrenamiento a partir de `data/exercises.json` y `data/teoria/`. |
| `finetune_qwen.py` | Entrena el adaptador LoRA (Unsloth o TRL). |
| `finetune.sh` | Envoltorio: para Ollama, lanza el entrenamiento en el contenedor `finetune` y reinicia Ollama. |
| `exportar_a_ollama.py` | Fusiona el adaptador, genera el GGUF y registra el modelo en Ollama. |
| `evaluar_modelo.py` | Compara el modelo entrenado con el base. |
| `docker/finetune/` | Imagen Docker del entrenamiento (servicio `finetune` del `docker-compose.yml`, perfil `training`). |

El procedimiento completo está en [`../ENTRENAMIENTO_MODELO.md`](../ENTRENAMIENTO_MODELO.md). Todos los
comandos se lanzan desde la raíz del repositorio.
