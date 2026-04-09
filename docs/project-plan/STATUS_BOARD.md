# Civic Ledger Status Board

_Last updated: 2026-04-09_

## Overall status
Launch-readiness validation. The product and governance layer are both real now; the main remaining work is executing verification and confirming live automation health instead of inferring it.

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
- `35a8e32` — add project status board
- `2c1c25c` — add operations runbook and link it from the repo front door

## This block shipped
- Tightened `docs/project-plan/OPERATIONS.md` against the actual repo surfaces instead of hand-wavy assumptions.
- Rechecked the runbook against the current repo on 2026-04-09 so the documented workflow order, directory repair bounds, and Render deploy defaults still match code.
- Recorded the scheduled workflow's real shape from `.github/workflows/refresh-data.yml`: checkout, Python `3.13`, install, baseline seed, then read-model refresh.
- Captured repo-backed operational specifics that were previously implicit: workflow-pinned environment values, the directory repair script's current warm-up scope, and the Render deploy script's encoded branch/plan/region defaults.
- Left the core blockers unchanged and explicit: fresh verification still needs network access, and live automation health still needs external observation.

## Strengths
- The application already presents a coherent product story instead of a demo stub.
- The scoring layer is explainable and has direct unit coverage.
- The repo has a clear separation between request-time reads and background data enrichment.
- Partial-data states are intentionally surfaced instead of being hidden behind fake certainty.

## Gaps blocking “MVP done”
1. The verification matrix now exists, but it has not been fully executed in a network-enabled environment.
2. Production automation health is defined in code/docs, but not freshly confirmed from this sandbox.

## Active slice tracker
- [x] Add `docs/project-plan/STATUS_BOARD.md`.
- [x] Add `docs/project-plan/ROADMAP.md`.
- [x] Add `docs/project-plan/DECISIONS.md`.
- [x] Add `docs/project-plan/OPERATIONS.md`.
- [x] Add verification matrix and executable checks.
- [x] Define MVP acceptance criteria and launch checklist.
- [ ] Execute the verification matrix in a network-enabled environment.
- [ ] Confirm GitHub Actions refresh health and Render production health.

## Current risks / blockers
- **Fresh verification blocker:** this sandbox cannot install dependencies or reach package indexes, so fresh pytest/runtime validation is blocked here until a network-enabled environment runs the matrix.
- **Automation visibility blocker:** GitHub Actions run health, Render runtime health, and production secret posture are not directly inspectable from this sandbox.

## Recommended next 30-minute slice
Run the verification matrix in a network-enabled environment and record dated results for:
- app smoke tests and data/scoring test suites
- baseline bootstrap and read-model refresh
- latest GitHub Actions refresh run
- Render `/healthz` and a sample live page
- any failures that block an honest MVP-done call
