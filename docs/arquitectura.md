# System architecture

## Components

```
Browser ──▶ frontend (Django) ──▶ api (FastAPI) ──▶ ollama (LLM + embeddings)
                                      │
                                      ├──▶ ChromaDB (theory and rules collections)
                                      └──▶ data/exercises.json (exercise library)
```

| Component | Responsibility |
|---|---|
| `frontend/` | Web interface: session form, rules mode, PDF export, exercise correction. |
| `api/main.py` | HTTP endpoints (`/generar`, `/ejercicio`, `/reprompt_ejercicio`, `/reglamento`, `/ambitos_reglamento`, ...), rate limiting and internal authentication. |
| `api/rag_engine.py` | Facade: re-exports the public names of the modules below (used by `main.py`, the tools and the tests). No logic of its own. |
| `api/config.py` | Environment variables, models, paths, category mapping and rules-scope names. No heavy dependencies. |
| `api/ejercicios.py` | Exercise library: loading, filtering by age and goal, selection of the n exercises of the main part (opposition arc ending in even matchups), relevance threshold and exercise context for the prompt. |
| `api/contexto.py` | Retrieval (RAG): queries the ChromaDB collections, context budget per collection and rules scopes. |
| `api/sesion.py` | Mode 1: full session generation. Asks the plan how many exercises it has, picks the cards, asks the LLM only for what is not curated (warm-up if there is no card for the age, cool-down, fundamentals and gaps without a card), validates its red lines and assembles the final text. |
| `api/plan_sesion.py` | Time allocation: how many exercises (between 5 and 8 in total, counting warm-up and cool-down) and how long each lasts, by duration and age. Minibasket: more and shorter exercises. |
| `api/bloques.py` | Session blocks composed by code: the full curated card (description and key points from `exercises.json`), variant from the card's progression (if present) and splitting of the model's answer. |
| `api/lineas_rojas.py` | Lexical guard of age "red lines" for any model-generated text, and the equivalent instruction for the prompt. |
| `api/diagramas.py` | JSON coordinates of the diagrams (JSON Schema + semantic validator + retry). |
| `api/ejercicio_unico.py` | Mode 2: single exercise and reprompt (correction requested by the coach). |
| `api/reglamento.py` | Mode 3: rules questions and technical fundamentals, by scope. |
| `api/prompts.py` | System prompts shared by inference and training. |
| `api/diagram_renderer.py` | Turns a diagram's JSON into SVG deterministically. When drawing, it separates overlapping markers without changing the JSON. |
| `api/posiciones.py` | Single dictionary of named positions (`codo_derecho`, `poste_bajo_izquierdo`...) and reading of any diagram point (`x`/`y` or name). |
| `api/solapes.py` | Minimal, deterministic separation of markers closer than 8 units. Used by the renderer and the validator. |
| `api/plantillas.py` | Warm-up and cool-down diagram templates (rondo, four corners, cone zigzag...) generated without a model. |
| `tools/` | Collection indexing, regression harness and editable export/import of the library. |
| `experimental/` | Fine-tuning, export and model evaluation. Not part of the current flow (see `experimental/README.md`). |

### Dependencies between `api/` modules

```
config            (imports no other module)
ejercicios        → config
bloques           (imports no other module)
lineas_rojas      (imports no other module)
plan_sesion       (imports no other module)
contexto          → config
posiciones        (imports no other module)
solapes           (imports no other module)
plantillas        → posiciones
diagram_renderer  → posiciones, solapes
diagramas         → config, ejercicios, prompts, posiciones, solapes
ejercicio_unico   → config, ejercicios
sesion            → config, contexto, ejercicios, bloques, lineas_rojas, plan_sesion
reglamento        → config, contexto, prompts
rag_engine        → all of the above (facade)
main              → rag_engine, diagram_renderer
```

The graph is acyclic: no module imports `rag_engine` except `main.py`. `contexto` is the only module
that creates the ChromaDB client and the embedding model on import.

When patching a function in a test, patch it in the module where it lives (for example
`reglamento.consultar_coleccion` or `contexto.REGLAMENTO_DIR`), not in the `rag_engine` facade.

## Selecting library cards

`ejercicios.elegir_fichas` picks the cards for the main part. Why it changed: a U10 session requested as
"half-court defense, offensive advantage against defense" came out with full-court transitions and
passing drills, because any loose word in the goal ("court", "player", "half") made almost any card
relevant and the diagram weighed more than the topic. How it works now:

- **Words:** filler words are ignored (`_PALABRAS_VACIAS`: "pista", "jugador", "balón", "ataque",
  "ventaja", "divertida"…), common verbs and forms are interpreted (`_EQUIVALENTES`: botar→bote,
  tirar→tiro, defienden→defensa) and "se lo pasen bien" (have a good time) does not count as "pase" (pass).
  With "rebote" in the goal, "bloqueen" does not bring in pick and roll.
- **Topic score** (`puntuacion_tema`): each word (with its equivalents, once) is worth 3 if it is in the
  name, the tactical tags or the category/subcategory (not the generic `juego_equipo` and `calentamiento`)
  and 1 if only in the description; the diagram (0.5) only breaks ties.
- **Opposition arc:** still no opposition → reduced → even, but the topic weighs more (`PESO_NIVEL`): a
  card on the topic beats an unrelated one even if it skips a level.
- **Weak cards** (fewer than 3 points): they cannot take more than a third of the slots; the AI proposes
  the rest. If no relevant card names the topic (e.g. "bandeja", layup), they are not limited.
- **Space** (the card's `espacio` field: `media_pista`, `pista_completa`, `flexible`): if the goal asks for
  "media pista", "medio campo" or "una canasta" (half court / one basket), no `pista_completa` cards are
  chosen (not even in the warm-up) and the prompt warns the model for the gaps it proposes. "Pista
  completa" or "toda la pista" does not filter.
- **Phrases that ask for a type** (`CATEGORIAS_POR_FRASE`): "ventaja de ataque", "superioridad" bring the
  `ventaja_numerica` cards (2v1, 3v2) even if they do not use those words.
- **Warm-ups:** in U8–U12 they enter the main part (dribbling lives there); in older ages they are penalized.

Tests: `tests/test_relevancia_ejercicios.py` (real case, space, categories and 8 natural-language requests).
An offline sweep of 9 ages × 6 durations × 27 goals produced no errors. **Limits:** poorly covered topics
(pick and roll, positional attack, off-ball play) leave more gaps to the AI; the equivalents table is short;
"posicional" scores on "Shell Drill — posiciones defensivas". **Not tested with the real model** on the
server: generate a half-court defense session and one on a weak topic on a machine with a GPU.

## Flow of a session

1. The frontend sends category, duration and goal to the API.
2. `ejercicios` filters exercises by age and goals, and `contexto` retrieves relevant theory from ChromaDB (context budget per collection).
3. `plan_sesion` decides how many exercises the main part has and how long each lasts (the full session has between 5 and 8 counting warm-up and cool-down). Each slot uses a library card if it fits the goal (`es_relevante`); otherwise the AI proposes it and it is marked "Propuesto por la IA (sin revisar)" (proposed by the AI, unreviewed). Among equally suitable cards one is picked at random (`azar=` in `elegir_fichas`), without worsening slots or the opposition arc, so the same parameters do not always give the same session.
4. The code composes the exercises with the full curated card (description and key points as is) and, if the card has a progression and the exercise is long for that age, its N.2 variant. The warm-up comes from a library card (`categoria: calentamiento`, different from those of the main part) when there is one for the age; otherwise the LLM writes it. The LLM also writes the cool-down, fundamentals and the proposed slots, step by step (if it stops, the missing sections are requested); if something breaks the age's red lines it is retried once and, if it persists, that piece is omitted (it ends up in `avisos`). Whatever the coach explicitly asks for in the goal is done with a notice: `/generar` returns `avisos` and the interface shows them; the notice only says "done" if the term appears in the final session.
5. For each exercise the library diagram is used if it exists; otherwise one is generated from the description.
6. The session and the SVGs are returned to the frontend.

## Third-party PDFs are isolated

The AI only sees our own documents: the `.md` files in `data/teoria` and `data/reglamento` (rewritten by
the coach) and the `data/exercises.json` library. PDFs (`data/pdfs/`, ignored by git) are local working
material for writing new documents in one's own words, and stay outside the system:

- the API container **does not mount** `data/pdfs` (it mounts, one by one, only the folders it needs);
- there is no setting to enable them and `consultar_coleccion` blocks the collections that used to be built from them;
- `tools/indexar_colecciones.py` cannot read PDFs and, when run, deletes those collections from the database.

A test (`tests/test_aislamiento_pdf.py`) fails if anyone mounts the folder again or reads PDFs again.

## Reliable diagrams

The LLM never draws: it only produces coordinate JSON (see [coordenadas.md](coordenadas.md)).

- The output is constrained by a **JSON Schema** (grammar-guided decoding in Ollama).
- A **semantic validator** checks what the schema cannot express: references to declared players, known named positions, a number of attackers/defenders consistent with the name (`2c1`, `3c2`...), minimum distance between players.
- Before rejecting, the validator **repairs** whatever has a deterministic fix: extra players with respect to the name's AvB (removed, never added), the missing `a_pos` when the diagram itself implies it, and players too close together if they fit when pushed slightly apart (details in [coordenadas.md](coordenadas.md#validator-repairs)).
- If validation fails, it is retried once stating the error; if it fails again, "diagram not available" is returned instead of a wrong drawing.
- When drawing, the renderer separates markers that still overlap (for example, in the curated library) without modifying the JSON.
- The decoding schema requires `a_pos` for moves, dribbles and screens, and `a` for passes (`anyOf` by movement type): the model can no longer omit them.
- For warm-up and cool-down there are templates that produce a valid diagram without a model (`api/plantillas.py`), used when the game is standard.

## RAG collections

| Collection | Content |
|---|---|
| `teoria_md` | Curated theory documents in `data/teoria/` (priority). |
| `teoria` | Additional technical and methodological material. |
| `planificacion` | Season planning. |
| `reglamento_md` | Curated rules in `data/reglamento/<scope>/` (`general` = FIBA and the Spanish federation; one folder per autonomous community). Each document carries its scope as metadata. |
| `reglamento` | Official PDF documents (optional local layer), with the same scope convention. |

In rules mode the scope is chosen: with an autonomous community its regulations are retrieved first and
completed with the general ones, which are always used as the base. See `docs/actualizar_reglamento.md`.

Only `teoria_md` and `reglamento_md` are part of the repository; the rest of the reference material is not distributed.
