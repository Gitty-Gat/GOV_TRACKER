# Civic Ledger Verification Matrix

_Last updated: 2026-04-14_

## Purpose
This file is the single verification surface for Civic Ledger. It turns the repo's tests, scripts, routes, and production automation into one explicit checklist so MVP health is not inferred from scattered files.

## Status meanings
- **PASS** — explicitly covered by committed tests or a durable repo-backed verification surface. This means the repo already contains the test/workflow evidence; it does **not** mean this slice reran every command live.
- **DEFINED** — command, artifact, and pass rule are specified here, but this slice did not re-run it end to end.
- **EXTERNAL** — requires observing deployment or remote workflow state outside the local repo alone.

## Verification rows

| Area | Command / surface | Expected evidence | Pass rule | Current status |
|---|---|---|---|---|
| App + route smoke | `pytest -q tests/test_app.py` | passing route/UI smoke tests, including `/healthz` semantics | test exits `0` | **PASS** |
| Congress + fallback normalization | `pytest -q tests/test_congress.py` | passing fallback / normalization checks | test exits `0` | **PASS** |
| Read-model snapshot behavior | `pytest -q tests/test_dashboard.py` | passing cached-read / baseline-seed behavior checks | test exits `0` | **PASS** |
| FEC partial-data fallback | `pytest -q tests/test_fec.py` | passing finance normalization and partial-data checks | test exits `0` | **PASS** |
| Promise-source fallback behavior | `pytest -q tests/test_promises.py` | passing manual-promise / fallback behavior checks | test exits `0` | **PASS** |
| Scoring semantics | `pytest -q tests/test_scoring.py` | passing verdict / score semantics checks | test exits `0` | **PASS** |
| Baseline bootstrap | `python scripts/bootstrap_precomputed_data.py` | seeded baseline snapshots for current House + Senate members | command exits `0` and produces snapshot records without breaking the app read path | **DEFINED** |
| Directory metrics refresh | `python scripts/refresh_directory_metrics.py` | updated directory-card metrics for seeded members | command exits `0`; directory cards remain renderable with refreshed aggregates | **DEFINED** |
| Deep read-model refresh | `python scripts/refresh_read_model.py --refresh-promises` | refreshed legislative / finance / promise-enriched read model | command exits `0`; enriched member pages still render from precomputed data | **DEFINED** |
| Full refresh wrapper | `python scripts/refresh_all_data.py` | ordered baseline + enrichment refresh pass | command exits `0`; expected sub-steps complete without request-time dependency on live APIs | **DEFINED** |
| Scheduled production refresh | `.github/workflows/refresh-data.yml` | successful scheduled or manually-dispatched workflow run | observed green workflow run on GitHub with expected refresh steps | **EXTERNAL** |
| Deploy smoke | Render deployment plus `/healthz` and cover-page check | reachable deployed app with healthy status | deployed service responds successfully after release | **EXTERNAL** |

## Notes
- This matrix intentionally distinguishes repo-backed verification from deployment-backed verification.
- Committed local tests give strong confidence in the product surface and scoring semantics, but this file should not be read as a fresh execution log unless dated run results are appended.
- Repo-backed launch controls were rechecked on 2026-04-14 against the current files instead of carrying forward older governance text by inertia: `.github/workflows/refresh-data.yml` still runs daily at `0 10 * * *`, sets up Python `3.13`, installs requirements, seeds baseline snapshots, and then refreshes the read model with `--refresh-promises`; `scripts/refresh_directory_metrics.py` still refreshes up to 120 officials and warms 24 cards in both `name` and `money_desc`; `scripts/deploy_render.py` still targets branch `main`, plan `free`, region `oregon`, and `/healthz`.
- The main remaining verification gap is still operational observation of the production refresh/deploy path, not missing application structure.
