# Chairman Stand-up Plan — 2026-04-08

## Project
Civic Ledger / GOV_TRACKER

## Goal / outline
Deliver a transparent House-and-Senate dashboard that shows who funds an elected official, what they have tangibly done in office, and how that compares with stated priorities using explainable public-data scoring.

## Current progress
- This is a real FastAPI application, not a stub.
- The repo has app code, tests, deployment config, bootstrap/refresh scripts, and a precomputed read-model strategy.
- Recent commits show meaningful product movement: baseline seeding, faster builds, read-model backfills, finance/activity restoration, and dashboard enrichment.
- The README is already sharper and more product-specific than many MVP repos.

## Remaining to complete
1. Make the data-refresh and read-model pipeline more visibly governed and auditable.
2. Add a durable roadmap and tracker so status does not live only in commits and memory.
3. Strengthen coverage around scoring semantics, enrichment readiness, and stale-data handling.
4. Document production operations clearly: refresh cadence, secrets, failure modes, and recovery.
5. Clarify what “MVP done” means versus what remains future-state polish.

## Candid critique / contradictions
- The repo is ahead of the director workspace that is supposed to coordinate it; the software is more real than the management layer around it.
- Product direction is fairly clear, but the project still lacks an explicit control surface for decisions, blockers, and next actions.
- There is a risk of shipping a trustworthy product with untrustworthy project hygiene — the app is explainable, but the execution layer is not yet equally transparent.

## Improvement opportunities
- Add a concise roadmap and decision log.
- Add explicit data-refresh operating docs and failure/recovery notes.
- Add a verification matrix for bootstrap, refresh, directory page, detail page, scoring, and deployment smoke.
- Add one current status board so future stand-ups do not require archaeology.

## Completion plan

### Milestone 1 — Project control layer
- Add status, roadmap, decisions, and blockers files.
- Link them from the README.

### Milestone 2 — Data operations hardening
- Document refresh order, failure handling, and expected outputs.
- Add missing guardrails around stale or partial data states.

### Milestone 3 — Product verification
- Verify key routes, read-model refresh scripts, and scoring behavior with explicit commands.
- Capture what is seeded, partial, and enriched.

### Milestone 4 — MVP closeout
- Define exact MVP acceptance criteria.
- Cut remaining “future module” scope from near-term execution unless it directly supports launch.

## 30-minute execution cadence
Each block should:
- read current status,
- close one app/data/ops/documentation slice,
- update the tracker,
- commit and push if coherent.

Use 5/20/5 minutes:
- 5 min orient,
- 20 min execute,
- 5 min document and commit.

## Commit / push rule
Push narrow, reviewable changes often. If a block reveals a blocker instead of shipping code, commit the blocker documentation only if it sharpens future execution.

## Immediate next slices
1. Add `docs/project-plan/STATUS_BOARD.md`.
2. Add `docs/project-plan/ROADMAP.md`.
3. Add `docs/project-plan/DECISIONS.md`.
4. Add `docs/project-plan/OPERATIONS.md` covering refresh/deploy flow.
