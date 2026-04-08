# Civic Ledger Status Board

_Last updated: 2026-04-08_

## Overall status
Active MVP hardening. The product is real, the read-model strategy is real, and the main remaining work is governance: project tracking, operations clarity, verification discipline, and launch definition.

## Current snapshot
- **Product shape:** FastAPI application with a cover page, searchable officeholder directory, definitions page, official detail pages, JSON API endpoints, and a health check.
- **Read path:** User-facing pages read precomputed snapshots instead of making live Congress/FEC calls during requests.
- **Data pipeline:** Baseline seeding, directory metric refresh, and deeper read-model enrichment all exist as separate scripts.
- **Deployment posture:** Render deployment automation exists, and GitHub Actions already runs a scheduled refresh workflow.

## What is already working
- Baseline snapshot seed: `scripts/bootstrap_precomputed_data.py`
- Full precomputed refresh wrapper: `scripts/refresh_all_data.py`
- Deep read-model enrichment: `scripts/refresh_read_model.py --refresh-promises`
- Directory-card refresh: `scripts/refresh_directory_metrics.py`
- Render deployment automation: `scripts/deploy_render.py`
- Scheduled refresh workflow: `.github/workflows/refresh-data.yml`

## Evidence in the repo
- **Route + UI smoke coverage:** `tests/test_app.py`
- **Congress fallback and normalization behavior:** `tests/test_congress.py`
- **Read-model caching and baseline-seed behavior:** `tests/test_dashboard.py`
- **FEC normalization and partial-data fallback behavior:** `tests/test_fec.py`
- **Promise-source fallback behavior:** `tests/test_promises.py`
- **Scoring semantics:** `tests/test_scoring.py`

## Recent momentum
Recent commits show steady product movement rather than churn:
- `0e7b261` — seed baseline snapshots and split entry pages
- `9f80839` — speed up baseline bootstrap build
- `dbaef49` — keep Render build fast and seed externally
- `0e6babc` — reuse DB connections for batch refresh scripts
- `7e08c7d` — backfill baseline finance and show partial activity counts
- `86a257a` — backfill finance and activity in the read model
- `d85954f` — restore profile finance and verdict sections
- `69bad6b` — add chairman stand-up completion plan
- `35a8e32` — add project status board (local commit; not yet on origin/main)

## This block shipped
- Added a durable status board so project state no longer lives only in commit history.
- Added `docs/project-plan/ROADMAP.md` so near-term MVP work is sequenced separately from future-state polish.
- Added `docs/project-plan/DECISIONS.md` to lock the MVP scope boundary, partial-data rules, deploy posture, and explicit deferrals into the repo.
- Added `docs/project-plan/OPERATIONS.md` as the first real runbook for refresh order, cadence, secrets, stale-data semantics, failure modes, and recovery.
- Linked the control docs from `README.md` so the governance layer is visible from the repo front door.
- Captured the next incomplete slices so future stand-ups can continue without archaeology.

## Strengths
- The application already presents a coherent product story instead of a demo stub.
- The scoring layer is explainable and has direct unit coverage.
- The repo has a clear separation between request-time reads and background data enrichment.
- Partial-data states are intentionally surfaced instead of being hidden behind fake certainty.

## Gaps blocking “MVP done”
1. Verification is still spread across README text, scripts, tests, and workflow files instead of one explicit matrix.
2. Launch acceptance criteria are still implicit.
3. Push/auth remains blocked on the execution host, so governance updates are landing locally before they can reach `origin/main`.

## Active slice tracker
- [x] Add `docs/project-plan/STATUS_BOARD.md`.
- [x] Add `docs/project-plan/ROADMAP.md`.
- [x] Add `docs/project-plan/DECISIONS.md`.
- [x] Add `docs/project-plan/OPERATIONS.md`.
- [ ] Add verification matrix and executable checks.
- [ ] Define MVP acceptance criteria and launch checklist.

## Current risks / blockers
- **Verification sprawl risk:** tests, scripts, workflow steps, and README notes still need one explicit verification surface before governance feels complete.
- **Freshness trust risk:** the repo now documents stale and partial data behavior, but operators still need a short executable check set to validate health quickly.
- **Git push blocker:** `git push origin main` failed again on 2026-04-08 with `git@github.com: Permission denied (publickey)`. Local commits including `35a8e32`, `bc5f9af`, `1fc2ad9`, and `4c2bf5b` remain ahead of `origin/main` until SSH credentials are fixed on the execution host.

## Recommended next 30-minute slice
Add a verification matrix covering:
- app smoke routes and `/healthz`
- bootstrap and read-model refresh commands
- directory-metric refresh behavior
- scoring/null-verdict semantics under seeded vs enriched data
- deploy smoke expectations after Render release
