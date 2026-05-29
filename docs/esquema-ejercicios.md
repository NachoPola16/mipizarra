# Esquema de un ejercicio

Cada ejercicio en `data/exercises.json` sigue esta estructura.

## Campos obligatorios

| Campo              | Tipo       | Descripción                                      |
|--------------------|------------|--------------------------------------------------|
| `id`               | string     | Identificador único. Ej: `"ej_001"`              |
| `nombre`           | string     | Nombre del ejercicio                             |
| `categoria`        | string     | Ver categorías más abajo                         |
| `edades`           | string[]   | U12, U14, U16, U18, Senior                       |
| `duracion_min`     | int        | Duración en minutos                              |
| `intensidad`       | int 1-5    | Carga física (1=muy baja, 5=máxima)             |
| `carga_cognitiva`  | int 1-5    | Exigencia de toma de decisiones                  |
| `objetivos.tacticos` | string[] | Lista de tags tácticos                          |
| `descripcion`      | string     | Explicación del ejercicio en lenguaje natural    |

## Campos opcionales

| Campo              | Tipo     | Descripción                                        |
|--------------------|----------|----------------------------------------------------|
| `subcategoria`     | string   | Refinamiento de la categoría                       |
| `fase_temporada`   | string[] | pretemporada, temporada, playoffs                  |
| `jugadores_minimos`| int      | Mínimo para ejecutarlo                             |
| `variantes`        | string[] | IDs de ejercicios derivados                        |
| `diagrama`         | object   | Un único diagrama (ejercicios simples)             |
| `diagramas`        | object[] | Array de diagramas para ejercicios con varias fases. Cada objeto tiene `titulo` (string, breve) y los campos normales del diagrama. Usar cuando una sola imagen no es suficiente para explicar la jugada (ej. bloqueo directo: fase 1 = pantalla, fase 2 = continuación). |

## Categorías

- `ventaja_numerica` — 2c1, 3c2, fastbreak
- `bloqueo_directo` — pick & roll, acción y reacción. U14 solo de forma esporádica; pleno uso desde U16.
- `bloqueo_indirecto` — bloqueos alejados, caída hacia canasta. Desde U14 en adelante.
- `tiro` — mecánica, con oposición, en movimiento
- `1c1` — individual ofensivo y defensivo (mano a mano, penetración)
- `juego_equipo` — 5c5, sistemas, sets
- `fisico` — condición, pliometría, sprints
- `calentamiento` — movilidad, activación

## Escala de intensidad y carga cognitiva
