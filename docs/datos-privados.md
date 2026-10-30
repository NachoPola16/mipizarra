# Public code, private library

The code in this repository is open source under the [AGPL-3.0](../LICENSE). The **training library is not
part of it** and is not covered by that license:

| Path (git-ignored here) | Content |
|---|---|
| `data/exercises.json` | The curated exercise library (cards with diagrams) |
| `data/teoria/*.md` | The theory documents indexed by the RAG |
| `frontend/pizarra/static/pizarra/data/jugadas.json` | The play library |

What the repository does ship: `data/muestra_ejercicios.json` (5 sample cards), `data/reglamento/` (our own
summaries of the rules) and `data/teoria/.gitkeep`.

**Why.** The code is generic; the library is the part that took the work and the part that could be copied
into a competing service. It also contains material adapted from third-party sources that should not be
redistributed. Running MiPizarra against your own library is the intended way to use the open code: write
your own cards following [the exercise schema](esquema-ejercicios.md).

## Running without the library

- The API and the web app start with whatever is in `data/exercises.json`; point `EXERCISES_PATH` at
  `data/muestra_ejercicios.json` (or at your own file) to try it.
- A missing `jugadas.json` just gives an empty play library; missing `data/teoria/*.md` just means the
  RAG has no theory.
- `pytest` works without the library: the tests that depend on its content are skipped
  (`REQUIEREN_BIBLIOTECA` in `tests/conftest.py`).

## Maintainer setup: the private repository

The library lives in a separate private repository (`mipizarra-data`) tracked with a **second git directory
over the same working tree**, so paths, Docker mounts and the Fichas tab keep working unchanged:

```bash
# once, in the MiPizarra checkout (PC or server)
git clone --bare <private-url> .git-datos
git --git-dir=.git-datos config core.bare false
git --git-dir=.git-datos config core.worktree "$(pwd)"
git --git-dir=.git-datos config status.showUntrackedFiles no
git --git-dir=.git-datos --work-tree=. checkout -f main    # writes the three library paths into place
```

`.git-datos/` is git-ignored by the public repository. Use it with the helper `tools/gitd`
(`tools/gitd status`, `tools/gitd commit -am ...`, `tools/gitd push`). Library changes are committed there; code
changes are committed in the normal repository.

### Deploying (server)

`tools/desplegar.sh` updates both repositories and refuses to deploy if the server has Fichas-tab edits that
are not yet committed in the private repository. The check and the recovery steps are the ones described in
[Exercise administration](administracion-fichas.md), with `tools/gitd` instead of `git`.

**One-time migration of an existing server** (it still has the library as tracked files of the public
repository; the public history was rewritten, so a plain `git pull` will not work):

```bash
cd <install dir>
mkdir -p ../mipizarra-datos-backup && cp -a data/exercises.json data/teoria \
   frontend/pizarra/static/pizarra/data/jugadas.json ../mipizarra-datos-backup/    # keep the live files
git fetch origin && git reset --hard origin/main       # deletes the (now untracked-in-history) library files
cp -a ../mipizarra-datos-backup/exercises.json data/
cp -a ../mipizarra-datos-backup/teoria/. data/teoria/
cp -a ../mipizarra-datos-backup/jugadas.json frontend/pizarra/static/pizarra/data/
# then set up .git-datos as above; `tools/gitd status` should be clean or show only Fichas-tab edits
docker restart mipizarra-api && docker compose up -d --build frontend
```

## History rewrite (2026-10-30)

When the library was taken out of the public repository, the history of `main` was rewritten with
`git filter-repo` to remove those paths (and local agent/design files) from every commit. Consequences:
commit hashes changed, anyone with an old clone must re-clone, and GitHub may keep unreachable old objects
for a while (a repository fork or a cached view could still expose them; if that matters, ask GitHub Support to
run garbage collection). A full pre-rewrite backup exists only on the maintainer's machine.
