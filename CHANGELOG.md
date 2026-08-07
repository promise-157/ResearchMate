# Changelog

## Unreleased

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
- Added generic material, asset, extraction, relation, and collection-job schemas with idempotent workspace migration.
- Added concise Codex startup guidance (`AGENTS.md`), product/architecture contracts, and a verified current roadmap.
- Disabled generic HTML collection by default and allowlisted the supported arXiv adapter.
- Kept UI-entered AI keys in process memory, removed direct browser-to-provider requests, and narrowed local API CORS.
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
