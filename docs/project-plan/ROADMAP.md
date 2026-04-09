# Civic Ledger Roadmap

_Last updated: 2026-04-08_

## Purpose
This roadmap is the durable execution view for Civic Ledger. It separates what must land for a trustworthy MVP from what is valuable later but should not keep the product in permanent prelaunch.

## Current phase
**Launch-readiness validation.**

The application and control docs are now in place. The near-term roadmap is no longer about inventing governance; it is about running the verification matrix, confirming live automation health, and then either declaring MVP done or cutting a short failure punch list.

## Now — required before calling MVP done

### 1) Project control surface
Create and keep current the small set of operating docs that let future contributors continue without archaeology:
- `docs/project-plan/STATUS_BOARD.md`
- `docs/project-plan/ROADMAP.md`
- `docs/project-plan/DECISIONS.md`
- `docs/project-plan/OPERATIONS.md`

**Why this matters:** project state should live in the repo, not only in commit history or stand-up notes.

### 2) Data operations hardening
Document and verify the intended refresh path:
- baseline seed via `scripts/bootstrap_precomputed_data.py`
- full wrapper via `scripts/refresh_all_data.py`
- read-model enrichment via `scripts/refresh_read_model.py --refresh-promises`
- directory refresh via `scripts/refresh_directory_metrics.py`
- scheduled production refresh via `.github/workflows/refresh-data.yml`

**Exit condition:** an operator can explain cadence, secrets, expected outputs, partial-data behavior, and recovery steps without reading application code.

### 3) Execute the verification matrix
Run the checks captured in `docs/project-plan/VERIFICATION.md` instead of assuming the repo is healthy because the code shape looks good.

**Exit condition:** dated verification results exist for static checks, pytest coverage, core route smoke, data refresh commands, and production-adjacent health checks where environment access allows.

### 4) Confirm live automation and deploy health
Validate the actual operating path instead of just the intended one.

**Must be explicit about:**
- latest GitHub Actions refresh success
- required secrets actually present
- Render health status and sample live route checks
- durable production storage via `DATABASE_URL`

## Next — important immediately after MVP hardening
These are strong follow-ons once the control/ops layer is in place:
- extend the existing verification matrix with a dated release-results appendix for deploy smoke and refresh smoke
- improve freshness visibility in the product and/or operator docs
- tighten manual-promise enrichment workflow so curated promise coverage can expand cleanly
- reduce ambiguity around stale-data and partial-enrichment presentation in the UI

## Later — valuable, but not launch-blocking
These should stay out of the MVP critical path unless they directly improve launch trustworthiness:
- future news/context module referenced in the README
- richer frontend or client-side application layer beyond the current server-rendered MVP
- broader comparative analytics across members, states, caucuses, or issue cohorts
- additional public-data integrations that expand scope beyond the current trust-and-activity story

## Explicit MVP non-goals
To avoid scope drift, the following are **not** required for MVP launch:
- real-time congressional or finance ingestion on the request path
- exhaustive promise coverage for every current member
- causal claims between donations and legislative outcomes
- launching future modules simply because the repo has a placeholder for them

## Current execution order
1. [x] Add `docs/project-plan/STATUS_BOARD.md`.
2. [x] Add `docs/project-plan/ROADMAP.md`.
3. [x] Add `docs/project-plan/DECISIONS.md`.
4. [x] Add `docs/project-plan/OPERATIONS.md`.
5. [x] Add verification matrix and executable checks.
6. [x] Define MVP acceptance criteria and launch checklist.
7. [ ] Execute the verification matrix in a network-enabled environment.
8. [ ] Confirm GitHub Actions refresh health and Render production health.
