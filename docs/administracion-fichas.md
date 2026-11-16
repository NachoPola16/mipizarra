# Exercise administration (the "Fichas" tab)

A tab only for the administrator account (the user name set in `JUGADAS_ADMIN` in `.env`; empty means nobody is administrator; the same one as the play
library button). It lives at `/fichas/` and the tab is shown in the header only to that account. It lets
you review exercises one by one and change **any field, diagram included**, without touching git or
redeploying.

## What you can do

- List with search (name, id, text), filters by age and category and "only modified"; Previous / Next.
- All fields of the [schema](esquema-ejercicios.md): name, category, subcategory, space, ages, duration,
  intensity, cognitive load, minimum players, goals, description, key points, material, cue, mistakes,
  what to observe and progression.
- Diagram: no diagram (the AI draws one when generating), free play, one or several (with titles). The
  preview is drawn by the server (the same one that sessions will show); you drag players, cones and
  movement targets on it, and there are tables for players/cones/ball/movements plus an advanced JSON view.
- **Undo / redo** while editing (buttons or Ctrl+Z / Ctrl+Y, as in the plays): each step is a snapshot of
  the whole form (fields and diagram); consecutive typing or dragging counts as one step. It resets when
  you open another exercise or save.
- Save (button or Ctrl+S), discard changes and "Go back to the previous saved version" (needs two clicks).
- **English tab** (`i18n.en`): the same fields as the Spanish card, with the Spanish text shown above each one for
  reference and a counter for the lists (they must have the same number of items as in Spanish; the API checks it).
  If you change the Spanish text in the same session, the English tab warns you to re-check it. The diagram and the
  numbers are shared between languages.
  **Stale English across sessions:** the English block keeps `i18n.en.es_hash`, a fingerprint of the Spanish text it was
  reviewed against (set by the API, never trusted from the browser). When the Spanish changes and the English does not,
  the card is flagged "● inglés desfasado" in the list (there is a filter for it) and the English tab shows a banner with a
  button "El inglés está al día" that stamps the current Spanish and is saved with the card. Saving a change to the English
  also stamps it. A vocabulary replacement in Spanish keeps an up-to-date card up to date. Cards without a stamp are never
  flagged; `python tools/marcar_ingles_al_dia.py [--aplicar]` reports or stamps them. The stamp is never sent to the public
  `/ejercicios?lang=en`.
- **Automatic warnings** under the form (the same checks as `tools/revisar_diagramas.py`, in `api/revision_mecanica.py`):
  ball holder, players quoted in the text that are not in the diagram, defenders contradicting the text, players out of
  the court, repeated move numbers. They are hints and never block saving. They refresh while you edit.
- **Find and replace** (the panel above the list): for vocabulary changes across the whole library, in Spanish,
  English or both, optionally whole word and case sensitive. First "Ver cambios" shows every change (field, before →
  after) without touching anything; then "Aplicar a las marcadas" changes only the cards you left ticked (second click to
  confirm). It makes ONE copy of the whole file and one previous version per card, so each card can still be undone
  with "Go back to the previous saved version". Cards that would end up invalid are skipped and listed. It never touches
  numbers, ids or diagrams. Without case sensitivity the capital initial is kept («Reversa» → «Reverso»).

## Where changes are stored

**Directly in the server's `data/exercises.json`** (the file is mounted writable in the API container).
They take effect immediately for generating sessions. Key order is preserved so `git diff` stays clean.

A **temporary** safety net (`api/fichas_edicion.py`) in case something goes wrong; once it is clearly not
needed it can be switched off with API environment variables (`FICHAS_COPIAS_MAX=0` and
`FICHAS_HISTORIAL_MAX=0`):

- Before every save: a copy of the whole `exercises.json` in `data/cambios/copias/` (the last
  `FICHAS_COPIAS_MAX` are kept, 20 by default).
- The previous version of the exercise goes to `data/cambios/ficha_historial.json` (up to
  `FICHAS_HISTORIAL_MAX`, 10 per exercise); "Go back to the previous saved version" reads from there.
  Without history (0) that button stops working.
- `tools/backup_data.py` includes `exercises.json` and the history, because the server's file can now be
  **ahead of git**.

### Bringing the edits into git (important when deploying)

**Always deploy with `bash tools/desplegar.sh`**: it checks whether the server has exercise edits not yet
pushed and, if so, refuses to deploy and prints the steps below; otherwise it does `git pull --ff-only`,
restarts the API and rebuilds the frontend. (A bare `git pull` without that check only warns when the
file changed on both sides.)

The exercise library lives in the private repository (see [Public code, private library](datos-privados.md)); use `tools/gitd` where this page says git for it. The server may have an `exercises.json` different from that repository's. Before deploying (`git pull` on the server)
those edits must be pushed, or the `pull` will refuse (if both touched the file) or leave the server's
file as it was:

```bash
# 1. are there unpushed edits? (on the server: cd <install dir>; git --git-dir=.git-datos --work-tree=. status --short data/exercises.json)
# 2. fetch the file, review and push
ssh <server> "cat <install dir>/data/exercises.json" > data/exercises.json
tools/gitd diff --stat data/exercises.json      # check which exercises changed
tools/gitd add data/exercises.json && tools/gitd commit -m "fichas: edits made from the Fichas tab" && tools/gitd push
# 3. ship the commit to the server (bundle, see docs/datos-privados.md); its file is then identical to the commit
```

If an exercise was edited on the server and that same exercise changed in git, merge by hand (`git diff` per exercise).

## Validation

Before saving, the API runs the exercise through `validar_ficha` (schema, age red lines, repeated names and
ids, duration/intensity limits…) and each diagram through diagram validation, which also repairs what is
deterministic (separating overlapping players, deducing `a_pos`): what is saved is what is drawn. If
anything fails nothing is saved and the response (422) carries the list of `problemas`. Saving without
changes writes nothing.

## API (internal secret only)

| Route | Purpose |
|---|---|
| `GET /admin/fichas` | All exercises and the ids that have a previous version (`modificadas`) |
| `PUT /admin/fichas/{id}` | `{ficha: {...}}` saves to exercises.json; 422 with `problemas` if invalid |
| `DELETE /admin/fichas/{id}` | Goes back to the previous version (404 if there is none) |
| `POST /admin/diagrama/vista` | `{diagrama}` → `{svg, diagrama}` or 422 with `problemas` |

The API has no users: the web app checks the permission (`frontend/pizarra/fichas_admin.py`: 404 on the page
and 403 on the data for other accounts; CSRF required when saving) and the API only accepts calls with
`X-Internal-Secret`.

## Batch diagrams (`tools/diagramas_lote.py`)

To draw or review several diagrams at once without going through the web: `listar ej_XXX ...` prints the
exercises, `comprobar PATCH.json` validates a `{id: {"diagrama": ...}}` patch, `hoja PATCH.json SHEET.html`
generates a contact sheet and `aplicar PATCH.json` writes it to `data/exercises.json` (with LF, leaving the
rest untouched). An exercise does not carry both `diagrama` and `diagramas`; with `diagramas`, each one has
a `titulo`.
