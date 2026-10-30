# How to update the rules

The rules reach the AI through two complementary channels:

| Layer | Where | In the repository | Purpose |
|---|---|---|---|
| **`.md` summaries** | `data/reglamento/<scope>/*.md` | Yes | Short, curated text: what the model reads first (collection `reglamento_md`). |
| **Official PDF documents** | `data/pdfs/coleccion_reglamento/` | No (local folder, ignored by git) | Optional layer with the long detail (collection `reglamento`). |

The AI works with the `.md` files alone. The PDFs add precision but are not required, and are not published.

## Scopes: general or an autonomous community

The rules mode has a **scope** selector:

- **General** (`data/reglamento/general/`): FIBA and Spanish federation rules. Always used.
- **An autonomous community** (`data/reglamento/<community>/`, e.g. `aragon`): its regulations
  (school competitions, competition rules…). When chosen, the AI answers with that community's rules
  **and completes them with the general ones**. Where both differ, the community's prevail.

The selector is built automatically from the folders: **adding a community means creating its folder**
with at least one `.md`. The displayed name comes from `NOMBRES_AMBITO` in `api/config.py` (e.g.
`"aragon": "Aragón"`); if missing, it is derived from the folder name.

Local PDFs follow the same convention: loose PDFs in `data/pdfs/coleccion_reglamento/` are general, and
those of a community go in a subfolder with its name (`.../coleccion_reglamento/aragon/`).

### Adding an autonomous community

1. Create `data/reglamento/<community>/` (lowercase, no accents or spaces: `castilla_y_leon`).
2. Write one or more `.md` files in it with its rules, in your own words. Always state in the text which
   season it covers and remind readers that rules are updated every year.
3. (Optional) Add the accented name to `NOMBRES_AMBITO` and the local PDFs to its subfolder.
4. Reindex and restart (see below). The community appears in the selector by itself.

## Steps when a new version of the rules comes out

1. **Download the official document** (the international federation publishes the full rulebook and a
   summary of changes every summer, valid from 1 October; regional federations publish each season's
   competition rules) and put it in `data/pdfs/coleccion_reglamento/` (or in the community's subfolder).
   If the PDF is copy-protected, install `cryptography` in the project's virtual environment so it can be read.
2. **Write or update the summary in `data/reglamento/<scope>/`:** a file with the changes in your own
   words, stating since when they apply. Then fix the key rules where something has become obsolete.
3. **Update the `/reglamento` prompt** in `api/prompts.py` only if the change is large (for example, a
   foul that disappears): the small model tends to repeat the old rule if it sees both.
4. **Remove or set aside the old PDFs** that contradict the new rule, so they are not retrieved in searches.
5. **Reindex:** `docker exec mipizarra-api python /app/tools/indexar_colecciones.py` and restart the API.
6. **Protect the change with a test:** add a question to `CASOS_REGLAMENTO` in `tools/regresion.py` (with
   `"ambito"` if it belongs to a community) and adjust the counts in `tests/test_regresion_arnes.py`.

## What to keep and what not

- Keep only your own summaries in the repository. Do not copy literal paragraphs from the official rulebook.
- The PDFs are local: if you do not have them, the AI keeps working with the `.md` files.
- Always state the effective date in the text, so the model can tell the current rule from the previous one.
