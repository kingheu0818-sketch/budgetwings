# ⚠️ ARCHIVED (v2.0, 2026-04-21)

This directory was archived as part of the v1 → v2 migration.

- **v1 (archived)**: Deterministic crawler pipeline targeting specific flight/OTA APIs (Kiwi, etc.)
- **v2 (current)**: LLM-agent pipeline under `agents/`, `tools/`, `llm/`. See `ARCHITECTURE.md`.

These modules are kept for reference and git history only. They are **not imported by any runtime code** and are excluded from tests and packaging. Do not add new code here.

---

# Legacy Scrapers

The `scraper/` package is kept for compatibility with the original BudgetWings
v1 crawler design. New development should prefer the AI Agent architecture in
`agents/`, `tools/`, and `llm/`.

Legacy scrapers may still be useful as deterministic data sources, but they are
no longer the primary product direction.
