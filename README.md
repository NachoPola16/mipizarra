# MiPizarra

> Work in progress — a personal learning project. The app and its training library are in Spanish
> (they target Spanish youth basketball); the documentation is in English.

A basketball coaching assistant running on a 100% local AI. Given a tactical goal, an age category and the available time, it generates a complete training session with exercises and tactical diagrams in SVG.

It uses no external API: the LLM, the embeddings and the vector database all run on your own hardware.

## How it works

1. The user describes the training goal (e.g. "Shooting, types of exits and fast break, 90 minutes").
2. RAG retrieves relevant exercises and theory from the JSON library + ChromaDB.
3. A local LLM writes the session.
4. A deterministic SVG renderer draws the tactical diagrams (half court / full court).

Besides complete sessions, it can produce a single exercise on request, correct exercises already generated, and answer rules questions.

## Stack

- **LLM:** Qwen3 family (4B) served with Ollama (LoRA fine-tuning is experimental, see `experimental/`)
- **Embeddings:** `nomic-embed-text` via Ollama
- **RAG:** exercise library in JSON + ChromaDB
- **Diagrams:** deterministic SVG renderer (pure Python, no graphics dependencies)
- **API:** FastAPI + rate limiting
- **Frontend:** Django
- **Infra:** Docker Compose with an NVIDIA GPU

## Quick start

Requires Docker with NVIDIA support.

```bash
cp .env.example .env
# Edit .env if you want to restrict BIND_IP to your local network
docker compose up -d
docker exec -it mipizarra-ollama ollama pull qwen3:4b-instruct
docker exec -it mipizarra-ollama ollama pull nomic-embed-text
```

## Using the API

```bash
curl -X POST http://localhost:8090/generar \
  -H "Content-Type: application/json" \
  -d '{"edad":"U16","duracion":90,"objetivo":"bloqueo directo"}'
```

## Regression tests

Two levels, to detect whether a model or prompt change makes quality worse:

**Offline tests** (`tests/`, no Ollama and no network): diagram validator, exercise filtering and
selection, session parsing (including N.1/N.2 variants), the SVG renderer over the whole library
and the invariants of `data/exercises.json`.

```bash
pip install -r requirements-dev.txt
pytest
```

**Live harness** (`tools/regresion.py`): runs 15 fixed cases (6 sessions, 2 exercises with a
diagram and 7 rules questions) against the real API and checks the session structure, the diagrams,
the age rules (≤U12) and that no sources are cited. It needs the API running with Ollama and a GPU.

```bash
python tools/regresion.py                                  # saves data/regresion/YYYY-MM-DD_HHMM.json
python tools/regresion.py --solo sesiones                  # sesiones | ejercicios | reglamento
python tools/regresion.py --comparar data/regresion/<previous>.json
```

It prints a table to the console and exits with code 1 if any hard criterion fails or if
`--comparar` detects a regression. Run a reference pass before changing the model or prompts and
compare afterwards. The `/generar` limit (10/hour per IP) only allows one full run per hour;
restarting the API container resets it. Results are not versioned (`data/regresion/` is in `.gitignore`).

## Documentation

- [Architecture](docs/arquitectura.md)
- [Model training](MODEL_TRAINING.md) (experimental, not part of the current flow)
- [Exercise schema](docs/esquema-ejercicios.md)
- [Exercise administration](docs/administracion-fichas.md) (the "Fichas" tab for editing exercises and diagrams)
- [Diagram coordinates](docs/coordenadas.md)
- [Security and deployment](SECURITY.md)
- [Roadmap](docs/fases.md)

## License

The code is licensed under the [GNU AGPL-3.0](LICENSE): if you run a modified version as a network service, you must offer its source to your users.

The training library (exercises, plays and theory documents) is **not** part of this repository and is not covered by that license; see [Public code, private library](docs/datos-privados.md).
