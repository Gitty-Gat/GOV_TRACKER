# Civic Ledger Operations

_Last updated: 2026-04-08_

## Purpose
This runbook explains how Civic Ledger is supposed to refresh, what "healthy" looks like, which secrets matter, and how to recover when upstream data or deployment automation misbehaves.

The key operating rule is simple: **the app serves precomputed snapshots from its database. Congress.gov and OpenFEC are batch-refresh dependencies, not request-time dependencies.**

## Operating model

### Read path
User-facing pages and API responses should read cached database snapshots only:
- `directory_metric`
- `official_detail`
- `member_detail`
- `activity`
- `finance`
- `promises`

This means:
- slow or rate-limited upstream APIs should degrade freshness, not page availability
- a null verdict or partial finance view can be normal during refresh gaps
- operators should think in terms of **snapshot freshness and readiness states**, not "is the API live right this second"

### Readiness semantics
These states are part of normal operation and should be interpreted deliberately:
- **`seeded`** — baseline/member shell exists, but deep enrichment is not ready yet
- **`partial`** — some real enrichment is present, but not enough for a fully trustworthy profile
- **`enriched`** — finance, activity, and promises have enough depth for the full dashboard experience

Important trust rule from the code:
- `truth_verdict` stays `null` until the app has both promise inputs and enriched activity with recent bills
- finance fallbacks should prefer cached values and warnings over fake zeroes

## Required secrets and environment

### Production/scheduled-refresh minimum
- `CONGRESS_API_KEY`
- `FEC_API_KEY`
- `DATABASE_URL`

### Local development minimum
- `CONGRESS_API_KEY` (optional for baseline fallback behavior, but strongly preferred)
- `FEC_API_KEY` (optional, but richer finance depth needs a real key)
- `DATABASE_PATH` for SQLite when `DATABASE_URL` is unset

### Deploy automation
- `RENDER_API_KEY`
- `RENDER_OWNER_ID` when the API key can see multiple workspaces
- `RENDER_SERVICE_ID` optionally, if the service should be targeted explicitly

### Important defaults
From `app/settings.py` and `.env.example`:
- `CURRENT_CONGRESS=119`
- `DEFAULT_CYCLE=2026`
- `OFFICIALS_SYNC_HOURS=24`
- `DETAIL_CACHE_HOURS=24`
- `ACTIVITY_CACHE_HOURS=12`
- `FINANCE_CACHE_HOURS=18`
- `PROMISE_CACHE_HOURS=48`

### Environment assumptions
- Production is meant to use Postgres via `DATABASE_URL`.
- Local dev may use SQLite via `DATABASE_PATH=data/civic_ledger.db`.
- If production runs without `DATABASE_URL`, the app can fall back to SQLite semantics, which is not a durable hosted-data posture.
- `DEMO_KEY` is tolerated for development, but routine finance depth and refresh reliability are materially better with real Congress/FEC credentials.

## Canonical refresh order

### 1) Baseline bootstrap
Command:

```bash
python scripts/bootstrap_precomputed_data.py
```

What it does:
1. refreshes the current House/Senate member list
2. attempts to enrich `member_detail` snapshots, but falls back to seeded member shells when Congress detail fetches fail
3. attempts a directory-level finance sync
4. builds cached `official_detail` and `directory_metric` snapshots for each official
5. stamps `app_meta.baseline_bootstrap_at`

Expected result:
- the directory should render for current members
- profile pages should exist even if some fields are incomplete
- many records may still be `seeded` or `partial`
- `truth_verdict` may remain `null`

Use when:
- seeding a new database
- recovering after data loss or environment reset
- restoring a minimally usable product before deeper enrichment

### 2) Read-model enrichment
Command:

```bash
python scripts/refresh_read_model.py --refresh-promises
```

What it does:
1. refreshes/backfills member detail snapshots as needed
2. rebuilds detailed activity snapshots from Congress.gov
3. refreshes finance snapshots and directory finance metrics from OpenFEC
4. refreshes promises from `data/manual_promises.json` or, when needed, from official website inference
5. rebuilds `official_detail` and `directory_metric`
6. stamps `app_meta.read_model_refresh_at`

Expected result:
- more records move from `seeded`/`partial` toward `enriched`
- top donors, PAC share, activity summaries, and delivery scoring populate where upstream data exists
- truth verdicts appear only for profiles with both promise inputs and enriched activity evidence

Use when:
- scheduled daily refresh runs
- data looks stale but baseline shells already exist
- manual promise curation has changed

### 3) Directory-card repair / refresh
Command:

```bash
python scripts/refresh_directory_metrics.py
```

What it does:
- refreshes current members if needed
- forces directory finance metrics refresh
- recomputes directory efficiency metrics for up to 120 officials in the current pass
- warms donor-name summaries for the first 24 cards in both `name` and `money_desc` sorts

Expected result:
- `/officeholders` card metrics improve even if full profile enrichment is lagging
- this mainly affects `directory_metric`, not the whole deep profile surface

Use when:
- the directory looks stale or sparse
- profile-level refresh is too heavy for the immediate fix
- you need a quick card-level repair pass

### 4) Full precomputed refresh wrapper
Command:

```bash
python scripts/refresh_all_data.py
```

What it does:
1. runs baseline bootstrap
2. force-refreshes current members and directory finance metrics
3. refreshes every official detail deeply
4. stamps `app_meta.precomputed_refresh_at`

Expected result:
- strongest one-shot local rebuild path
- heavier than the scheduled workflow

Use when:
- doing an end-to-end local refresh/rebuild
- debugging data consistency across baseline + detail layers
- validating a fresh environment outside GitHub Actions

## Scheduled production cadence
GitHub Actions owns the normal production refresh path.

Workflow:
- `.github/workflows/refresh-data.yml`

Current cadence:
- daily at `0 10 * * *` (10:00 UTC)

Current workflow order:
1. check out the repo
2. set up Python `3.13`
3. install dependencies with `pip install -r requirements.txt`
4. seed baseline snapshots
5. refresh live read model with `--refresh-promises`

Workflow-pinned environment:
- `CURRENT_CONGRESS=119`
- `DEFAULT_CYCLE=2026`
- `DATABASE_PATH=data/civic_ledger.db`
- `DATABASE_URL` is still expected when production should use durable hosted storage instead of local-file fallback semantics

Required GitHub secrets:
- `CONGRESS_API_KEY`
- `FEC_API_KEY`
- `DATABASE_URL`

Operational expectation:
- baseline seeding ensures the product stays renderable even if deeper enrichment later degrades
- read-model refresh is the step that makes verdicts, donor detail, and richer activity views trustworthy
- this workflow does not perform deploys; refresh health and deploy health are separate checks

## Deployment operations

### Render deploy
Command:

```bash
python scripts/deploy_render.py
```

What it does:
- discovers the Git remote URL
- chooses a Render owner/workspace
- creates or updates the `civic-ledger` web service
- targets branch `main` with Python runtime settings from the script
- syncs environment variables
- triggers a deploy
- waits for terminal deploy state
- checks `/healthz`

Expected healthy state:
- Render deploy finishes with status `live`
- the service responds successfully on `/healthz`

### Build/runtime shape
- build command: `pip install -r requirements.txt`
- start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- health check: `/healthz`
- deploy target encoded in the script today: plan `free`, region `oregon`, branch `main`

## Known failure modes and what they mean

### 1) Congress.gov detail fetch fails or rate-limits
Observed behavior in code:
- current-member sync falls back to `unitedstates/congress-legislators`
- member detail may be saved as a seeded fallback snapshot
- activity refresh can drop to limited or pending detail

What users may see:
- directory still loads
- profile exists but has lighter activity detail
- readiness remains `seeded` or `partial`

Recovery:
1. verify `CONGRESS_API_KEY`
2. rerun baseline bootstrap if member shells are missing
3. rerun read-model refresh after Congress access stabilizes

### 2) OpenFEC fails, 429s, or returns partial coverage
Observed behavior in code:
- FEC requests retry on 429 up to five times using `Retry-After` when available
- directory metrics may keep cached totals and donor names
- detail finance falls back to cached values or a partial finance summary with warnings
- fake zero-dollar finance should not be treated as healthy output

What users may see:
- cached totals with a warning
- donor/PAC detail missing or thinner than normal
- readiness stays `partial` or `pending`

Recovery:
1. verify `FEC_API_KEY`
2. rerun `python scripts/refresh_directory_metrics.py` for card-level repair
3. rerun `python scripts/refresh_read_model.py --refresh-promises` for full detail recovery
4. if using `DEMO_KEY`, expect lower throughput and thinner donor tracing until a real key is supplied

### 3) Promise enrichment is empty
Observed behavior in code:
- manual promises from `data/manual_promises.json` win when present
- otherwise promise inference only happens on forced refresh against the official website
- if no manual data exists and the official site is unreachable or unhelpful, promises can stay empty

What users may see:
- no promises listed
- `truth_verdict` remains `null`
- delivery scoring remains insufficient/non-final

Recovery:
1. add or improve `data/manual_promises.json`
2. rerun `python scripts/refresh_read_model.py --refresh-promises`
3. treat missing verdicts as a data-readiness issue, not automatically as a rendering bug

### 4) Production database is not durable
Observed risk:
- the repo is designed for hosted Postgres in production
- without `DATABASE_URL`, production can drift toward local-file semantics

What users may see:
- refresh state disappears across redeploys or environment resets
- snapshots feel randomly stale or missing after deploy events

Recovery:
1. provision a persistent Postgres database
2. set `DATABASE_URL`
3. run baseline bootstrap
4. run read-model refresh

### 5) Render deploy automation fails
Likely causes:
- missing `RENDER_API_KEY`
- multiple Render workspaces without `RENDER_OWNER_ID`
- bad repo remote metadata
- deploy reaches terminal non-`live` state

Recovery:
1. verify Render credentials and owner selection
2. rerun `python scripts/deploy_render.py`
3. confirm `/healthz` after deploy
4. if deploy succeeded but data looks stale, remember deploy and data refresh are separate operations

## Recovery playbooks

### A) New database or wiped environment
Run in this order:

```bash
python scripts/bootstrap_precomputed_data.py
python scripts/refresh_read_model.py --refresh-promises
```

### B) Directory looks stale, but profiles mostly work
Run:

```bash
python scripts/refresh_directory_metrics.py
```

### C) Profiles exist, but verdicts/donor detail/activity depth are stale
Run:

```bash
python scripts/refresh_read_model.py --refresh-promises
```

### D) End-to-end local rebuild
Run:

```bash
python scripts/refresh_all_data.py
```

### E) After deploying a fresh production database
Run in this order:

```bash
python scripts/bootstrap_precomputed_data.py
python scripts/refresh_read_model.py --refresh-promises
python scripts/deploy_render.py
```

If the web app is already deployed, data refresh may be enough; do not redeploy just to repair stale data unless code or environment changed.

## What to check before calling the system healthy
- `/healthz` returns success
- scheduled refresh has recent success in GitHub Actions
- the database has recent `baseline_bootstrap_at` and/or `read_model_refresh_at` metadata
- directory cards show non-empty member coverage
- sample enriched profiles have finance/activity/promise readiness beyond `seeded`
- null verdicts only appear where readiness genuinely does not support scoring yet

## Non-goals for operators
- Do not treat request-time upstream access as a requirement; the app is designed specifically to avoid that.
- Do not "fix" incomplete profiles by forcing fake zeroes into finance or verdict fields.
- Do not assume the directory and deep profile surfaces refresh at the same depth; they intentionally have different recovery paths.
