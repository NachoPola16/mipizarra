# AGENTS.md

Instrucciones para agentes de código (Claude Code, Codex, Cursor…).

## Commits
- **Claude nunca figura como autor ni contribuidor.** Sin línea `Co-Authored-By`, sin «Generated with Claude»
  en commits ni en descripciones de PR. Autor y committer: `NachoPola16 <nachopolac@gmail.com>`
  (comprobar `git config user.name` y `user.email` antes de commitear; nunca `Claude <noreply@anthropic.com>`).
- Antes de subir: `git log --format='%an <%ae> | %cn <%ce>' origin/main..HEAD` no debe mostrar a Claude ni a Anthropic.
- Lo comprueban los hooks de `claude-config/git-hooks/` (`pre-commit`, `commit-msg`, `pre-push`).
