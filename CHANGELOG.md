# Changelog

## Unreleased

- Rebuilt the repository landing README around the owner's established rabbit logo and open-source template style, while preserving every copyable clean-machine command in a dedicated Windows + WSL from-scratch guide.
- Added a Git-ignored Windows + WSL install configuration and one-command PowerShell `Install` flow that always checks, writes and displays a plan before applying, so later host updates do not require re-entering paths.
- Aligned the source launcher port probe with the supervisor/server `SO_REUSEADDR` behavior so closing and immediately reopening the fixed-port Windows desktop does not mistake `TIME_WAIT` connections for a live listener.
- Embedded the owner-supplied ResearchMate ICO in the Windows host and added an origin-checked desktop-only Settings picker for validated, persistent custom shortcut icons and explicit default restoration; the separate rabbit image is used only for the GitHub README.

- Added read-only installation ownership and uninstall information to Settings for Windows + WSL, native Linux and source/browser modes. Fixed the Windows host shutdown/relaunch race by allowing a new process to acquire the mutex when activation collides with the previous instance exiting, with offline and real-host restart coverage.
- Reorganized the repository README into a concise platform chooser and shortest-path guide, with detailed Windows + WSL, native Linux, development, verification and uninstall instructions linked as dedicated documents.
- Reframed the product as a local-first general material assistant with paper, job, and Debug templates.
- Added the first generic text-material vertical slice: normalized import, exact deduplication, local type suggestions, search/filter/detail, persisted status, and workspace counts.
- Added explicit single-material AI classification and field extraction with confirmed input scope, bounded text, validated suggestions, reusable successes, and persisted audit/error history.
- Completed M2 with auditable comparison of 2–20 explicitly selected materials and per-item truncation rules.
- Completed M3 with bounded image import, local asset storage and deduplication, guarded preview, and auditable optional Tesseract OCR.
- Completed M4 with controlled single-public-URL HTML import, SSRF/robots/size/timeout guards, persistent jobs, and an explicit candidate accept/reject workflow.
- Completed M5 with idempotent `papers.item_id` migration and transactional mapping of new arXiv records into the generic material core while preserving paper views.
- Completed the first M6 vertical slice with a versioned Debug template, deterministic audited extraction, user-confirmed overrides, dedicated error filtering, and explainable local near-text relations.
- Completed the first M7 discovery slice with bounded arXiv API search, persistent multi-candidate jobs, review-before-import, provenance, and offline Atom fixtures.
- Completed M8 with explicit OCR preview/acceptance into an independent deterministic extraction layer, opt-in accepted-text search/AI scopes, and offline Playwright coverage for refresh and workspace switching.
- Completed M9 with a versioned job template, audited local extraction, confirmation-preserving reprocessing, company/role/application-status filtering, and a shared template registry/renderer proven by Debug and job use cases.
- Completed M10 with named DeepSeek OpenAI-compatible Chat Completions, JSON Output plus local schema validation, redacted actionable errors, explicit connection testing, provider metadata audit fields, offline provider/API/browser fixtures, and an authorization-gated real smoke test for classification, extraction, comparison and persisted usage metadata.
- Hardened `run.py` port recovery with permission-aware bind checks, exact Linux listener termination, WSL/Windows PowerShell fallback, post-termination verification, actionable fallback guidance, and corrected Vite readiness detection.
- Reprioritized the post-M9 roadmap around a DeepSeek-first external API path, followed by unified auditable paper/material/chat AI, OCR quality and controlled real-network validation; local model runtimes remain optional and unbundled.
- Added generic material, asset, extraction, relation, and collection-job schemas with idempotent workspace migration.
- Added concise Codex startup guidance (`AGENTS.md`), product/architecture contracts, and a verified current roadmap.
- Disabled generic HTML collection by default and allowlisted the supported arXiv adapter.
- Kept UI-entered AI keys in process memory, removed direct browser-to-provider requests, and narrowed local API CORS.
- Added an explicit Key storage choice: safe session-only mode by default, or opt-in plaintext `config.yaml` convenience mode with path/risk disclosure, `0600` permissions, restart loading, and one-click removal.
- Added workspace-local audited paper chat sessions with bounded explicit attachments/history, persistent success/failure and provider metadata, refresh recovery, and workspace isolation.
- Migrated single and batch cart paper analysis to schema-v10 workspace-local `paper_ai_runs`, with bounded title/abstract scope, per-paper success or redacted failure, provider metadata, refresh/workspace isolation, explicit partial-batch status, and read-only legacy `papers.ai_*` display without mutating paper facts.
- Completed M11 workspace reviews with explicit confirmation of 2–20 ordered paper IDs and bounded title/abstract fields, one audited `workspace_review` run per request, strict structured results or redacted failures, refresh/workspace isolation, read-only legacy review history, and a shared paper AI run-history component.
- Completed the M12 M3-I1 slice with full PNG/JPEG/WebP decoding before persistence, 10 MiB/dimension/pixel/decompression-bomb limits, schema-v11 image dimensions, preview/OCR integrity rechecks, zero-residue rejection tests, offline browser coverage, and local Tesseract English/Chinese verification.
- Completed M13's M4-I1 slice with controlled real DNS/TLS/robots/redirect/UTF-8 checks, per-path robots enforcement across redirects, strict HTTP/BOM/meta charset decoding, decoded-size and peer regression tests, and an offline browser candidate review flow.
- Completed M13's M7-I1 slice with one controlled real arXiv Atom query, streaming decompressed-size and response-contract guards, complete provenance, startup recovery of interrupted collection jobs, and an offline browser discovery/review/isolation flow.
- Completed M14's M3-I2 slice with versioned portable workspace ZIPs containing a consistent SQLite snapshot and verified image assets, guarded atomic import with path rewriting, legacy asset-free DB compatibility, isolated clear/delete cleanup tests, and browser-visible archive errors.
- Completed M14's explicit image OCR reprocessing slice: every user-triggered request now creates a fresh audited success or failure instead of reusing an identical successful run, while source facts, assets, run history, workspace isolation, and the previously accepted OCR remain unchanged until explicit re-acceptance.
- Completed M14 startup recovery across every persistent running lifecycle by adding interrupted `extraction_runs` to the existing workspace-wide recovery for collection jobs, chat turns, and paper AI runs; recovered failures are visible through existing history APIs and UI without changing terminal records or source data.
- Completed M15's reproducible offline search evaluation at 10,000 and 50,000 multilingual workspace-shaped records. Current LIKE search remained below roughly 22 ms median at 50,000 records, while FTS5 trigram increased database size by about 164% and still required short-query fallback, so migration and embedding were explicitly deferred pending real scale or semantic-recall evidence.
- Closed M6-I1 with an offline Debug browser loop covering import, deterministic fields, confirmation precedence, explicit re-extraction and readable audit history, effective-value filtering, explainable similarity, refresh, and workspace isolation.
- Completed M16's first evidence-to-action workbench: users can create a workspace-local action project from 1–20 explicitly selected materials, persist their objective, notes, next action and status, maintain an ordered evidence list, return to source details, and preserve the whole workflow across refresh, workspace switching, clearing and portable archive round trips.
- Completed the bounded Windows + WSL desktop-host technical prototype with a .NET 10 WinForms WebView2 shell, explicit WSL/Conda configuration, private instance-bound supervisor protocol, single-instance activation, graceful window-owned shutdown, exact process-group escalation, redacted local logs, offline contract tests, and real local WSL probes for EOF, port conflicts, supervisor crashes and visible WebView lifecycle. Added a self-contained x64 publish path, read-only dependency check, auditable JSON plan/apply guide, config-driven path-free shortcut, staged current-user installation, uninstall registration, host/config rollback, ownership manifest and data-preserving uninstall guide; this remains source-backed delivery rather than a standalone public release.
- Added the source-backed native Linux desktop slice: a GTK 3/WebKitGTK window over the shared Vue/FastAPI application, config-driven private supervisor ownership, user-socket single-instance activation, XDG-scoped command/application entry/config/logs, transparent check-plan-apply setup, staged rollback, ownership manifest, and data-preserving uninstall.
- Hardened native Linux packaging for custom XDG paths and paths containing spaces, plan-time environment/port validation, manifest-driven optional-state removal, portable examples, and an explicit M17 handoff with native Windows deferred until real demand.
- Hardened workspace transitions with pinned SQLite connections, destructive-action leases, startup recovery of interrupted chat/paper AI runs, a shared frontend generation coordinator, stale-response guards, and repository-owned paper queries.
- Made AI attachments explicit and bounded; fixed synchronous completion reporting for shortlist analysis.
- Fixed source/task provenance, refresh-mode metadata updates, workspace counts, settings persistence, CSV export, and several placeholder controls.
- Added core safety and data-flow contract tests.
- Added backend Ruff, frontend ESLint, CI checks, and a dependency audit with zero known npm vulnerabilities.

## v1.1.2

### Added or Changed
- Change license to Unlicense; releasing the project fully into the public domain
- Add simplified project cover image


## v1.1.1

### Added or Changed
- Fixed back to top alignment (revert changes)


## v1.1.0

### Added or Changed
- Fixed back to top link alignment deprecated tag, use CSS style instead
- Added contrib.rocks to show top contributors


## v1.0.0

### Added or Changed
- Added this changelog :)
- Fixed typos in both templates
- Back to top links
- Added more "Built With" frameworks/libraries
- Changed table of contents to start collapsed
- Added checkboxes for major features on roadmap

### Removed

- Some packages/libraries from acknowledgements I no longer use
