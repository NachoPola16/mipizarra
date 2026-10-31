# Exercise schema

Every exercise in `data/exercises.json` follows this structure. The administrator can change any field
(diagram included) from the "Fichas" tab: see [Exercise administration](administracion-fichas.md).
Field names and values stay in Spanish, as does the library content.

## Required fields

| Field              | Type       | Description                                      |
|--------------------|------------|--------------------------------------------------|
| `id`               | string     | Unique identifier. E.g. `"ej_001"`               |
| `nombre`           | string     | Exercise name                                    |
| `categoria`        | string     | See categories below                             |
| `edades`           | string[]   | U12, U14, U16, U18, Senior                       |
| `duracion_min`     | int        | Duration in minutes                              |
| `intensidad`       | int 1-5    | Physical load (1=very low, 5=maximum)            |
| `carga_cognitiva`  | int 1-5    | Decision-making demand                           |
| `objetivos.tacticos` | string[] | List of tactical tags                            |
| `descripcion`      | string     | Natural-language explanation of the exercise     |

## Optional fields

| Field              | Type     | Description                                        |
|--------------------|----------|----------------------------------------------------|
| `subcategoria`     | string   | Refinement of the category                         |
| `fase_temporada`   | string[] | pretemporada, temporada, playoffs                  |
| `espacio`          | string   | `media_pista` (played at a single basket), `pista_completa` (needs the other basket or the whole court) or `flexible` (either works). If the coach asks for "half court", `pista_completa` exercises are not chosen. |
| `jugadores_minimos`| int      | Minimum players to run it                          |
| `variantes`        | string[] | IDs of derived exercises                           |
| `puntos_clave`     | string[] | Technical cues for the coach during the exercise (what to watch, what to correct, what to emphasize) |
| `material`         | string   | Balls, cones, hoops and space needed. Shown as is in the session. |
| `consigna`         | string   | Short phrase for the player (the exercise's "mantra"). |
| `errores_frecuentes` | string[] | What most often needs correcting.                |
| `que_observar`     | string[] | Measurable criteria for the coach (operational goals). |
| `progresion`       | object   | `facilitar` and/or `complicar` (text). If it has `complicar`, the session's N.2 variant comes from here; otherwise from the PROGRESIÓN/VARIANTES section of the description. |
| `diagrama`         | object   | A single diagram (simple exercises)                |
| `diagramas`        | object[] | Array of diagrams for multi-phase exercises. Each object has `titulo` (short string) and the normal diagram fields. Use it when one picture is not enough to explain the play (e.g. pick and roll: phase 1 = screen, phase 2 = continuation). |

## Bilingual cards and provenance

Cards can carry an English translation and a record of where they come from. Both are optional for existing
cards and required for new ones (`tools/validar_candidatos.py --bilingue`).

| Field    | Type   | Description |
|----------|--------|-------------|
| `i18n`   | object | `{"en": {...}}`. Translated text using the **same field names** as the root: `nombre`, `descripcion`, `puntos_clave`, `errores_frecuentes`, `que_observar`, `material`, `consigna`, `progresion`, plus `titulos_diagramas` (one title per entry of `diagramas`). Lists must have the same number of items as the Spanish ones. Spanish is always the root text, so it is not repeated in `i18n`. |
| `origen` | object | Provenance. `{"tipo": "original"}` for cards written and drawn from scratch; `{"tipo": "abierta", "url", "autor", "licencia", "consultado"}` for cards adapted (rewritten in our own words, diagrams redrawn) from material whose license allows it, with the attribution data. |

Numbers, ages, diagrams and `variantes` are shared by both languages. `GET /ejercicios?lang=en` returns the English
text where it exists and the Spanish text otherwise (`api/i18n_fichas.py`, `localizar`). Session generation, the RAG
and the web UI still work in Spanish only. If the Spanish text of a card is edited from the Fichas tab, its
`i18n.en` has to be updated by hand.

## Categories

- `ventaja_numerica` — 2v1, 3v2, fast break
- `bloqueo_directo` — pick & roll, action and reaction. From U16/Cadete. In U14/Infantil, only occasionally (team level or a specific play); otherwise, off-ball screens.
- `bloqueo_indirecto` — off-ball screens, roll toward the basket. From U14 onwards.
- `tiro` — mechanics, with opposition, on the move
- `1c1` — individual offense and defense (hand-off, drive)
- `juego_equipo` — 5v5, systems, sets
- `fisico` — conditioning, plyometrics, sprints
- `calentamiento` — mobility, activation
