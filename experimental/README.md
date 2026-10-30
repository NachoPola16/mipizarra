# Experimental

This folder is **not part of the current flow** of MiPizarra. The application works with the Ollama
base model plus context retrieval (RAG) and needs nothing in here.

It holds the LoRA/QLoRA fine-tuning pipeline that was tried as an optional improvement. It is not run
by the tests or the normal deployment, and it may fall behind `api/`.

| File | Purpose |
|---|---|
| `generar_dataset.py` | Builds the training dataset from `data/exercises.json` and `data/teoria/`. |
| `finetune_qwen.py` | Trains the LoRA adapter (Unsloth or TRL). |
| `finetune.sh` | Wrapper: stops Ollama, runs the training in the `finetune` container and restarts Ollama. |
| `exportar_a_ollama.py` | Merges the adapter, produces the GGUF and registers the model in Ollama. |
| `evaluar_modelo.py` | Compares the trained model with the base one. |
| `docker/finetune/` | Training Docker image (the `finetune` service of `docker-compose.yml`, `training` profile). |

The full procedure is in [`../MODEL_TRAINING.md`](../MODEL_TRAINING.md). All commands are run from
the repository root.
