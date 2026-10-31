# Roadmap

## Done
- [x] Docker Compose infrastructure + Ollama with GPU
- [x] Exercise library with diagrams (`data/exercises.json`)
- [x] RAG with separate collections (theory, planning, rules)
- [x] API: session, single exercise, exercise correction, rules
- [x] Half-court and full-court SVG renderer
- [x] Diagrams generated with JSON Schema + semantic validation + retry
- [x] Django frontend with PDF export
- [x] LoRA fine-tuning pipeline and evaluation script against the base model

## Next steps
- [ ] Evaluate newer base models against the current one
- [ ] Diagram templates for warm-ups and games without a half-court structure
- [ ] Canonical named positions in the diagram schema instead of free coordinates
- [ ] Converting hand drawings to diagram JSON with a multimodal model
- [ ] Grow the exercise library
- [ ] Bilingual library (Spanish and English versions of every exercise) with a language selector.
  Done so far: schema (`i18n`, `origen`), validation, `GET /ejercicios?lang=en`, and 6 reviewed cards in the
  library (ej_251-256). A second batch of 12 cards (ej_257-268) is in the library too (265 cards). Web UI: language selector (ES|EN,
  `?lang=en` + cookie) with the header, home page and sign-in page translated (`frontend/pizarra/idioma.py`,
  `textos_en.py`; add a string with `{% t "..." %}` / `tr('...')` and its English entry, a test checks the catalog).
  Left: Plays, Cards and the rest of the UI, English sessions, prompts and RAG per language
