# Civic Ledger MVP Acceptance and Launch Checklist

_Last updated: 2026-04-08_

## Purpose
This file defines what must be true before calling Civic Ledger "MVP done" or treating it as launch-ready. It exists to stop endless prelaunch drift and to prevent vague claims of readiness.

## MVP acceptance criteria

### 1) Core product surfaces work
The following routes must work in a verified environment:
- `/healthz`
- `/`
- `/officeholders`
- `/definitions`
- at least one representative official detail page
- at least one representative JSON detail endpoint

Acceptance rule:
- these routes render or return successfully without depending on live request-path Congress/FEC calls

### 2) Trust semantics stay honest
The product must preserve the repo's truthfulness rules:
- `seeded`, `partial`, and `enriched` remain meaningful readiness states
- `truth_verdict` stays `null` when promise/activity evidence is insufficient
- finance fallback behavior must prefer cached or warning-bearing partial output over fake zeroes
- the UI must not imply causal claims between donations and policy outcomes

Acceptance rule:
- tests and manual review confirm honest partial-data behavior

### 3) Data-refresh path is operationally clear
The intended operating flow must be documented and executable:
- baseline bootstrap via `scripts/bootstrap_precomputed_data.py`
- enrichment via `scripts/refresh_read_model.py --refresh-promises`
- directory repair via `scripts/refresh_directory_metrics.py`
- full rebuild via `scripts/refresh_all_data.py`
- scheduled refresh via `.github/workflows/refresh-data.yml`

Acceptance rule:
- an operator can explain which script to run and when without reading application code

### 4) Operations and launch checks exist
- operations runbook exists
- verification matrix exists
- launch blockers are explicit
- deploy and refresh health can be checked with a short list rather than tribal knowledge

Acceptance rule:
- `OPERATIONS.md`, `VERIFICATION.md`, `STATUS_BOARD.md`, and this file agree on current launch posture

## Still required before an honest MVP-done call
- [ ] observe one successful GitHub Actions refresh run
- [ ] observe one successful deploy smoke in the live host
- [ ] record any failures instead of inferring readiness from repo shape alone

## Launch posture right now
**Current posture:** product-ready in structure, governance-ready on paper, still awaiting observed production refresh/deploy proof.
