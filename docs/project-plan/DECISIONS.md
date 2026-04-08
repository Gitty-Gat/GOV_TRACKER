# Civic Ledger Decisions

_Last updated: 2026-04-08_

## Purpose
This file records the durable product and operating decisions that define Civic Ledger's MVP path. It exists so launch scope, partial-data rules, and deploy posture do not drift between stand-ups.

## Accepted decisions

### D-001 — MVP scope is an explainable federal officeholder dashboard
- **Status:** Accepted
- **Date:** 2026-04-08
- **Decision:** The MVP scope is the current House-and-Senate dashboard experience: cover page, definitions page, officeholder directory, official detail pages, JSON API endpoints, precomputed finance/activity/promise snapshots, and the explainable truth/delivery scoring layer.
- **Why:** This is already a coherent trust-focused product. The highest-value remaining work is operational clarity and launch discipline, not inventing a different product.
- **Consequences:** MVP work should improve trust, freshness, verification, and explainability. New modules only belong on the near-term path if they directly strengthen launch readiness.
- **Repo evidence:** `README.md`, `app/main.py`, `tests/test_app.py`, `tests/test_scoring.py`

### D-002 — Upstream Congress/FEC APIs stay off the request path
- **Status:** Accepted
- **Date:** 2026-04-08
- **Decision:** User-facing pages and JSON endpoints read from precomputed database snapshots, not live upstream API calls during requests. Data refresh belongs to batch scripts and scheduled jobs.
- **Why:** This keeps latency predictable, reduces rate-limit fragility, and makes the product's behavior explainable under partial or stale upstream conditions.
- **Consequences:** Operators must own refresh cadence and recovery. Documentation must make it obvious how baseline seeding and deeper enrichment interact.
- **Repo evidence:** `scripts/bootstrap_precomputed_data.py`, `scripts/refresh_all_data.py`, `scripts/refresh_read_model.py`, `.github/workflows/refresh-data.yml`

### D-003 — Partial data is acceptable only when it is labeled and non-deceptive
- **Status:** Accepted
- **Date:** 2026-04-08
- **Decision:** Civic Ledger may ship seeded or partial records, but only if the UI and API preserve readiness state honestly. The app should prefer transparent partial snapshots over fake completeness.
- **Why:** Trust is the product. A visibly partial answer is better than a fabricated complete one.
- **Consequences:**
  - `seeded`, `partial`, and `enriched` are first-class readiness states.
  - The directory should still render when Congress detail or FEC enrichment is incomplete.
  - Truth verdicts stay null until the app has enough promise and activity inputs.
  - Finance fallbacks should avoid fake zero values and expose warnings instead.
- **Repo evidence:** `app/models.py`, `app/services/dashboard.py`, `app/services/fec.py`, `tests/test_dashboard.py`, `tests/test_app.py`, `tests/test_fec.py`

### D-004 — Render is the primary deployment target; scheduled refresh runs in GitHub Actions
- **Status:** Accepted
- **Date:** 2026-04-08
- **Decision:** Render is the active deploy target for the MVP. Production should use `DATABASE_URL`, while local development may fall back to SQLite via `DATABASE_PATH`. Scheduled refresh is owned by `.github/workflows/refresh-data.yml`, which seeds baseline snapshots and then refreshes the read model with promise enrichment.
- **Why:** This matches the current repo's automation and keeps the web deploy lightweight while moving heavier refresh work outside request handling.
- **Consequences:** Reliable operation depends on GitHub secrets, a durable production database, and a documented recovery path when scheduled refresh fails. Vercel remains config-ready but is not the primary path today.
- **Repo evidence:** `README.md`, `scripts/deploy_render.py`, `.github/workflows/refresh-data.yml`, `app/settings.py`, `render.yaml`, `vercel.json`

### D-005 — Defer scope-expanding polish until the control and operations layer is complete
- **Status:** Accepted
- **Date:** 2026-04-08
- **Decision:** The future news/context module, richer frontend ambitions, and broader comparative analytics are explicitly deferred until the control docs, operations runbook, verification matrix, and MVP acceptance criteria are in place.
- **Why:** The repo already has meaningful product depth. The main launch risk is governance and operating clarity, not lack of ideas.
- **Consequences:** The next slices should stay focused on `OPERATIONS.md`, verification, and MVP acceptance criteria rather than new feature branches.
- **Repo evidence:** `README.md`, `docs/project-plan/ROADMAP.md`, `docs/project-plan/STATUS_BOARD.md`

## Review trigger
Revisit these decisions when one of the following changes:
- deployment target changes away from Render
- refresh cadence or ownership moves out of GitHub Actions
- the MVP scope expands beyond the current trust-and-activity dashboard
- the product no longer accepts partial-data states as part of normal operation
