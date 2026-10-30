# MiPizarra coordinate system

**Single reference** for diagram coordinates. If you change anything here, it must also be changed in the
3 SYSTEM prompts the model sees:

- `experimental/generar_dataset.py` → constant `SYSTEM_DIAGRAMA`
- `api/diagramas.py` → function `generar_coordenadas_ejercicio` (prompt text)
- `experimental/exportar_a_ollama.py` → constant `MODELFILE_TEMPLATE` (the Modelfile's SYSTEM)

Identifiers, position names and JSON values stay in Spanish because they are the data format the model
and the library use; the explanations are in English.

## Conventions

- Normalized coordinates: `(x, y) ∈ [0, 100]`.
- **X**: 0 = left sideline, 100 = right sideline, 50 = center.
- **Y** (half court): 0 = baseline (under the hoop), 100 = half-court line.
- **Y** (full court): 0 = attacking baseline (under our own hoop), 100 = defensive baseline (under the
  opponent's hoop). 50 = half-court line.
- Coordinates are mapped to pixels in `api/diagram_renderer.py:to_px`.

> **Left/right** — position names use the point of view of the attacking player facing the hoop from the
> top of the key. Their right hand is the low-x side (the left of the printed paper). In the diagram,
> "right" positions therefore appear on the visual left.

## Posiciones canónicas (media pista)

Canonical positions (half court). The first column is the Spanish label, the last one is the name used in the code.

| Posición                    | x  | y   | Notes                                              | Nombre (`pos`)                |
|-----------------------------|-----|-----|----------------------------------------------------|-------------------------------|
| Canasta / aro               | 50 | 11  | Center of the hoop                                 | `canasta`                     |
| Línea de fondo centro       | 50 |  5  | Under the hoop                                     | `linea_de_fondo_centro`       |
| Poste bajo derecho          | 38 | 18  | Next to the right edge of the paint, near the baseline | `poste_bajo_derecho`      |
| Poste bajo izquierdo        | 62 | 18  | Next to the left edge of the paint, near the baseline | `poste_bajo_izquierdo`     |
| Esquina triple derecha      |  6 | 22  | Right corner, FIBA three-point line                | `esquina_triple_derecha`      |
| Esquina triple izquierda    | 94 | 22  | Left corner, FIBA three-point line                 | `esquina_triple_izquierda`    |
| Esquina mini derecha        | 10 | 22  | Right corner, minibasket three-point line (U8-U12) | `esquina_mini_derecha`        |
| Esquina mini izquierda      | 90 | 22  | Left corner, minibasket three-point line (U8-U12)  | `esquina_mini_izquierda`      |
| Poste alto derecho          | 38 | 36  | Right edge of the paint, at free-throw-line height | `poste_alto_derecho`          |
| Poste alto izquierdo        | 62 | 36  | Left edge of the paint, at free-throw-line height  | `poste_alto_izquierdo`        |
| Codo derecho                | 35 | 41  | Right end of the free-throw line (elbow)           | `codo_derecho`                |
| Codo izquierdo              | 65 | 41  | Left end of the free-throw line (elbow)            | `codo_izquierdo`              |
| Línea TL (centro)           | 50 | 41  | Free-throw point                                   | `linea_tl_centro`             |
| Media distancia derecha     | 15 | 50  | Between the right elbow and the right 45°          | `media_distancia_derecha`     |
| Media distancia izquierda   | 85 | 50  | Between the left elbow and the left 45°            | `media_distancia_izquierda`   |
| 45° derecho                 | 25 | 50  | At 45° from the hoop, right side                   | `45_derecho`                  |
| 45° izquierdo               | 75 | 50  | At 45° from the hoop, left side                    | `45_izquierdo`                |
| Arco de triple (frontal)    | 50 | 60  | Top of the FIBA three-point arc                    | `arco_triple_frontal`         |
| Cabecera / Frontal          | 50 | 65  | Straight in front of the hoop, outside the arc     | `cabecera`                    |
| Medio campo derecha         | 25 | 95  |                                                    | `medio_campo_derecha`         |
| Medio campo izquierda       | 75 | 95  |                                                    | `medio_campo_izquierda`       |
| Centro medio campo          | 50 | 100 |                                                    | `centro_medio_campo`          |

### Named positions in the JSON

Besides `{"x": .., "y": ..}`, any point of the diagram can be given by the name in the "Nombre" column of
the table above. The dictionary lives in a single module, `api/posiciones.py` (`POSICIONES_CANONICAS`),
used by the renderer, the validator and the templates; `tests/test_posiciones.py` checks that it matches
this table.

| Where            | With coordinates               | With a name                         |
|------------------|--------------------------------|-------------------------------------|
| Player           | `{"id": "A1", "x": 35, "y": 41}` | `{"id": "A1", "pos": "codo_derecho"}` |
| Cone             | `{"x": 94, "y": 22}`           | `{"pos": "esquina_triple_izquierda"}` |
| `a_pos`          | `{"x": 38, "y": 18}`           | `"poste_bajo_derecho"` or `{"pos": "poste_bajo_derecho"}` |

- If a point carries both `x`/`y` and `pos`, `x` and `y` win.
- The name is normalized: case, accents, spaces and hyphens do not matter
  (`"Codo derecho"` = `"codo_derecho"`).
- A name that is not in the table is a clear error (`posición desconocida '...'`, with suggestions if it
  resembles a valid one): the validator rejects the diagram and the renderer raises
  `PosicionDesconocida` (a `ValueError`).
- In `pista_completa` the name is placed in the attacking half: the table's `y` is divided by two
  (`codo_derecho` → `(35, 20.5)`, `centro_medio_campo` → `(50, 50)`).

The model prompts and the JSON Schema it is asked for do **not** use names yet (they still ask for
`x`/`y`); for now names serve hand-written diagrams, templates and repairing model answers (see
"Validator repairs").

## Overlapping markers

Two players, or a player and a cone, closer than **8 units** overlap in the drawing. `api/solapes.py`
(`separar_puntos`) separates them minimally, stably and deterministically:

- Points are placed in order (attackers, defenders, cones): the first ones do not move and each later one
  moves aside to the nearest valid position (8 units from all those already placed), inside the court and
  no more than 8 units from where it was.
- Two cones together do not count as an overlap.
- If there is no room nearby, the point stays where it was.
- Distances are measured in 0-100 units, the same in half court and full court.

The **renderer** applies this separation only when drawing: the stored JSON does not change, and a diagram
without overlaps is drawn exactly as before. The movements of a displaced player start from its drawn position.

## Validator repairs

`_validar_diagrama` (`api/diagramas.py`) fixes in the diagram itself whatever has a deterministic solution
before rejecting it, and logs every fix:

1. **Missing `a_pos`** in `desplazamiento`, `bote` or `bloqueo`. It is only filled when the diagram says it
   unambiguously; coordinates are never invented:
   - `a` is a position: `{"x", "y"}` or a name from the table (`"a": "codo_derecho"`); it becomes `a_pos`
     and `a` is removed.
   - `bloqueo` with `a` = a defender's id: `a_pos` is where that defender is at that moment (taking its
     earlier movements into account).
   - The same player's next movement (by `orden`) says where it starts with the optional `desde` field
     (`{"x", "y"}` or a name): that point is the `a_pos`.

   A `bote`/`desplazamiento` "toward" another player (`"a": "A1"`) does not say where it ends and remains
   an error (`movimiento 'bote' sin 'a_pos'`), as does the case with no hint at all.
2. **Players closer than 8 units**: separated with `separar_puntos` (players only, the first declared stays).
   If any has no room within 8 units, nothing is touched and the `demasiado cerca` error remains.

## Lanes

Reference system for transition, fast break and recovery. The court is divided into vertical strips
regardless of length (it applies equally to half court and full court).

### 5 lanes

| No. | Name                      | Center X | X strip  |
|-----|---------------------------|----------|----------|
| 1   | Right wide lane           | 10       | 0 – 20   |
| 2   | Right inner lane          | 30       | 20 – 40  |
| 3   | Central lane              | 50       | 40 – 60  |
| 4   | Left inner lane           | 70       | 60 – 80  |
| 5   | Left wide lane            | 90       | 80 – 100 |

Typical fast-break occupation: central lane → rebounder/center; lanes 2 and 4 → ball handler; lanes 1 and
5 → shooters on the run.

### 3 lanes (simplified version)

| No. | Name             | Center X | X strip  |
|-----|------------------|----------|----------|
| A   | Right wing       | 17       | 0 – 33   |
| B   | Central lane     | 50       | 33 – 67  |
| C   | Left wing        | 83       | 67 – 100 |

### Reference positions in transition (full court, y = 0–100)

In `pista_completa`, y=50 is the half-court line. Key positions for placing players in each lane during
transition:

| Position                          | x  | y  | Notes                          |
|-----------------------------------|----|----|--------------------------------|
| Right wide, baseline              | 10 |  3 | Lane 1, baseline               |
| Right inner, baseline             | 30 |  3 | Lane 2                         |
| Left wide, baseline               | 90 |  3 | Lane 5                         |
| Left inner, baseline              | 70 |  3 | Lane 4                         |
| First third, right                | 10 | 33 | Lane 1, first third            |
| First third, right inner          | 30 | 33 | Lane 2                         |
| First third, central              | 50 | 33 | Lane 3                         |
| First third, left inner           | 70 | 33 | Lane 4                         |
| First third, left                 | 90 | 33 | Lane 5                         |
| Half court, right wide            | 10 | 50 | Lane 1, half-court line        |
| Half court, right inner           | 30 | 50 | Lane 2                         |
| Half court, central               | 50 | 50 | Lane 3                         |
| Half court, left inner            | 70 | 50 | Lane 4                         |
| Half court, left wide             | 90 | 50 | Lane 5                         |

## Player identifiers

- Offense: `A1`–`A5`. They are numeric labels to identify players in the diagram. The number **does not
  imply a playing role**: A1 need not be the point guard nor A5 the center. The coach assigns real players
  to each label according to the exercise.
- Defense: `D1`–`D5`. By convention the number matches the attacker they guard (D1 guards A1, etc.),
  although it is not mandatory.
- Cones: no id, just `{x, y}`.

## Movement types

| Type             | Required fields       | Visual                               | Tactical meaning                                |
|------------------|-----------------------|--------------------------------------|-------------------------------------------------|
| `desplazamiento` | `de`, `a_pos`, `orden`| Solid line with arrow                | Player moves without the ball (cut, reposition) |
| `pase`           | `de`, `a`, `orden`    | Dotted line with arrow               | Pass between two identified players             |
| `bote`           | `de`, `a_pos`, `orden`| Wavy line with arrow                 | Player advances dribbling (drive, progression)  |
| `tiro`           | `de`, `orden`         | Green arrow toward the hoop          | Shot at the hoop from the current position      |
| `bloqueo`        | `de`, `a_pos`, `orden`| Thin red line + thick perpendicular bar at the end | The screener moves to the defender and sets the screen |

`a_pos` also accepts a named position (see "Named positions in the JSON"). Any movement can carry the
optional `desde` field (the point where it starts); the renderer does not draw it, only the validator uses
it to deduce the `a_pos` of the same player's previous movement.

Note on `pase`: the `a` field is the receiving player's **id** (e.g. `"a": "A3"`), not a position. The
passer does not update their position after the pass. `bote` and `desplazamiento` do update the player's
position for the following movements.

**Terminology:** always use `bloqueo`, never `pantalla`, in outputs. The model may recognize "pantalla" in
input prompts, but in answers and in the JSON it always writes `bloqueo`.

**Screen restrictions by age category:**

| Category             | Ages (~years)  | Pick and roll    | Off-ball screen   | 1v1 / hand-off    |
|----------------------|----------------|------------------|-------------------|-------------------|
| Prebenjamín/Benjamín | U8, U10        | ✗                | ✗                 | ✓                 |
| Alevín               | U12            | ✗                | ✗                 | ✓                 |
| Infantil             | U14 (~13-14)   | ✗                | ✓                 | ✓                 |
| Cadete and above     | U16+ (~15+)    | ✓                | ✓                 | ✓                 |

- **U12 and below**: individual actions only (1v1, hand-off, dribbling).
- **U14 (Infantil)**: off-ball screens as normal; pick and roll only occasionally (depending on the team's
  level or in a specific play), not as central content.
- **U16 (Cadete) and above**: pick and roll and off-ball screens as normal.

**Low-post play**: it is not an illegal action in youth categories (U8-U12), but teaching it is not
recommended — it adds nothing at those ages. `vocabulario_tecnico()` in `sesion.py` already excludes "poste
bajo" and the screen vocabulary from the session prompt for these categories.

## Warm-up and cool-down templates

`api/plantillas.py` generates, without a model, half-court diagrams for the parts of the session that have
no card. `generar_plantilla(nombre, n_jugadores, n_conos=None)` returns the usual diagram JSON (numeric
`x`/`y`, ids `A1..An` and `D1..Dn`), valid for `_validar_diagrama` without repairs and without overlapping
markers. The "Moment" values are the ones used in the code.

| Template                  | Moment             | Players   | Cones (default) |
|---------------------------|--------------------|-----------|-----------------|
| `filas_esquinas`          | calentamiento      | 2-12      | 0-2 (0)         |
| `circuito_conos`          | calentamiento      | 2-12      | 3-10 (6)        |
| `rondo_circular`          | calentamiento      | 4-12      | 0-4 (4)         |
| `cuatro_esquinas`         | calentamiento      | 4-12      | 4 (4)           |
| `dos_filas_enfrentadas`   | calentamiento      | 2-12      | 0-2 (0)         |
| `zigzag_conos`            | calentamiento      | 2-12      | 3-8 (6)         |
| `pilla_pilla`             | calentamiento      | 3-12      | 0-4 (4)         |
| `pases_por_parejas`       | calentamiento      | 2-12      | 0-2 (0)         |
| `rueda_de_tiro`           | calentamiento      | 2-12      | 0-2 (2)         |
| `trote_en_circulo`        | vuelta a la calma  | 2-12      | 0-4 (0)         |
| `estiramientos_en_lineas` | vuelta a la calma  | 2-12      | 0-2 (0)         |
| `tiros_libres_rotacion`   | vuelta a la calma  | 2-12      | 0-2 (0)         |

An unknown name or an out-of-range number raises `ValueError`. In the rondo and the tag game the defenders
(`D`) are the ones who steal or tag. The templates are not yet used when generating sessions.

## Optional `curva` field

`desplazamiento`, `pase`, `bote` and `tiro` accept the `"curva"` field. `bloqueo` ignores it (always drawn straight).

The line is drawn as a curve instead of straight:

- `"curva": true` → sideways deviation of ~1 meter (default value, valid for most cases)
- `"curva": 60` → larger deviation (~1.3 m), to go around a defender more widely
- `"curva": 30` → gentle deviation (~0.7 m), for a slightly curved path
- `"curva": -40` → same curvature but to the opposite side

The direction of the deviation is relative to the movement: positive curves to the left of the player
according to their direction of travel; negative, to their right. For `bote`, the sine wave follows the curve.
