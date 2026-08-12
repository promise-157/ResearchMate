# ResearchMate agent guide

## Start every session here

Before proposing or changing code:

1. Read `docs/PRODUCT.md`, `docs/ARCHITECTURE.md`, and `docs/ROADMAP.md` completely.
2. Run `git status --short`; preserve all existing user changes and local data.
3. Identify the smallest current milestone and trace its full `UI -> API -> storage` path.
4. State acceptance criteria before implementation and update `docs/ROADMAP.md` when reality changes.

`docs/ROADMAP.md` is deliberately compact. Completed detail lives in `CHANGELOG.md` and Git history; read either only when the current task depends on older behavior. Do not bulk-read every document, test, or source directory as session initialization.

Do not use chat memory, ignored drafts, `CLAUDE.md`, or `src/temp/` as project truth.

## Context discipline

- Start from the current ROADMAP slice, then use targeted `rg` searches and narrow line ranges. Avoid dumping whole files or whole-tree diffs when a symbol or route trace is enough.
- Keep tool output bounded and exclude `src/backend/config.yaml`, `src/data/`, generated output, and unrelated history from searches.
- Delegate only independent implementation or verification work. Give sub-agents the smallest necessary context and file scope; do not make multiple agents repeat the same repository trace or reread the full project history.
- Keep `docs/ROADMAP.md` focused on verified baseline, active acceptance criteria, live debt, and the next handoff. Put durable release history in `CHANGELOG.md` instead of appending session transcripts.
- Prefer an existing service/repository boundary before reading or changing route internals. If a legacy route mixes workflow, provider I/O, and SQL, extract that boundary as part of the active vertical slice rather than spreading new logic through the route.

## Product contract

ResearchMate is a local-first personal information workspace, not a paper-only assistant:

`import/discover -> candidate -> minimal extraction -> organize/link -> explicit AI -> action`

- A material can be text, a user-provided image, a public URL result, or a normalized record from a named source adapter.
- Store useful extracted information and provenance, not internet archives. Do not download paper PDFs or mirror remote sites by default.
- Papers, jobs, and debug records are domain templates over one generic material core.
- Deterministic local processing works without AI. AI is actively used for classification, structured extraction, comparison, and synthesis, but external calls are explicit and auditable.

## Safety and privacy

- Never inspect, print, commit, or expose credentials. Keys may come from environment variables or the settings UI. Settings default to session-only storage; an explicit convenience mode may persist the Key in ignored `src/backend/config.yaml` only after showing the plaintext risk and path. Switching back to safe mode or clearing the Key must remove that disk copy. Never persist Keys in SQLite, logs, audit records, test fixtures containing real secrets, or tracked files.
- The frontend calls only `/api/*`; source and AI provider requests stay in the backend.
- Never silently send a workspace or local asset to an external AI. Show and bound the selected scope.
- Prefer user imports, documented public APIs, RSS, and normal public-page access. Do not bypass authentication, paywalls, CAPTCHAs, robots rules, rate limits, or access controls.
- Generic web collection is disabled by default. A new source requires a named adapter, provenance, limits, fixtures, and failure reporting.
- Tests must not use live collection, paid AI calls, real keys, or files under `src/data/`.

## Engineering rules

- Complete vertical slices only: request model, service logic, storage, API, UI, error state, tests, and docs must agree.
- No placeholder buttons, silent `except`, fabricated success, hard-coded user paths/ports/credentials, or production behavior implemented only in browser state.
- Preserve immutable source facts. Store deterministic extraction, AI inference, and user-confirmed values separately; reprocessing must not overwrite user confirmation.
- Keep external I/O behind adapters and domain logic out of route handlers.
- Use idempotent, tested schema migrations. Never delete or rewrite user data as a migration shortcut.
- Extract an abstraction after a second real use case appears, not in anticipation of one.
- Do not modify git remotes or global configuration, and do not add `Co-Authored-By` trailers.

## Architecture map

- `src/backend/api/routes/`: validation and HTTP boundary.
- `src/backend/services/`: application workflows and transaction boundaries.
- `src/backend/storage/`: schema, repositories, and migrations.
- `src/backend/crawlers/`: current public-source adapters; migrate deliberately when a second generic collector justifies it.
- `src/backend/processors/`: deterministic and optional AI extraction.
- `src/frontend/src/api/`: the frontend's only network boundary.
- `docs/PRODUCT.md`: stable product intent and scope.
- `docs/ARCHITECTURE.md`: invariants and component boundaries.
- `docs/ROADMAP.md`: current truth, acceptance criteria, and next milestone.

Legacy `crawlers/` and paper-specific routes remain compatibility code until migrated deliberately.

## Verification

Use the existing environment; do not install dependencies without approval.

```bash
PYTHONDONTWRITEBYTECODE=1 conda run -n researchmate python -m unittest discover -s tests -v
PYTHONDONTWRITEBYTECODE=1 conda run -n researchmate python -m compileall -q src/backend
conda run -n researchmate ruff check src/backend tests
cd src/frontend && npm run lint && npm run build
git diff --check
```

A successful build alone is not evidence that a user workflow works.
