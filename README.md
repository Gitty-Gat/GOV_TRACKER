# Civic Ledger

Civic Ledger is a House and Senate dashboard focused on two questions:

1. Who funds a federal elected official?
2. What has that official tangibly done in office relative to their stated priorities?

This MVP ships as a FastAPI application with a designed frontend, precomputed public-data snapshots, and a transparent scoring layer instead of a black-box ranking.

## Product shape

- Cover page at `/` with a plain-language introduction and clear next-step buttons.
- Searchable officeholder dashboard at `/officeholders` with member photos, filters, and collapsible score guidance.
- Definitions page at `/definitions` for first-time users.
- Official detail view with war-chest metrics, major donors, PAC audit trails, state contribution mix, legislative activity, a truth verdict badge, and a promise-vs-delivery board.
- JSON API endpoints for reuse by a richer frontend later.

## Data strategy

### Current implementation

- Congress member metadata and legislative activity: `Congress.gov` API.
- Current-member bootstrap fallback when the Congress demo key is exhausted: `unitedstates/congress-legislators`.
- Campaign finance totals and itemized donor/PAC data: `OpenFEC` API.
- Stated priorities:
  - Preferred: curated manual promises in `data/manual_promises.json`.
  - Fallback: inferred issue priorities from official member website language.
- Read path:
  - Rendered pages and API routes read only from precomputed snapshots in the app database.
  - Upstream Congress/FEC sync is handled by batch refresh scripts, not by user requests.

### Precomputed storage and rate limiting

- Production is designed to use `DATABASE_URL` for hosted Postgres.
- Local development falls back to `DATABASE_PATH` SQLite.
- Render build now seeds a fast baseline snapshot set for every current House and Senate member.
- Deeper activity, finance, donor, PAC, and promise enrichment runs outside the request path.
- If the Congress API rate-limits, the app falls back to a public current-member dataset so the directory still works.
- The app is designed to work with `DEMO_KEY`, but meaningful finance depth requires real `CONGRESS_API_KEY` and `FEC_API_KEY` values.

### Truthfulness constraints

- The dashboard shows funding patterns and policy activity side by side.
- It does not claim causation between donations and outcomes.
- The truth verdict is explainable and evidence-backed, with methodology exposed in the UI.

## Stack

- Backend: FastAPI
- Frontend: Jinja templates, custom CSS, vanilla JS
- Storage and cache: Postgres via `DATABASE_URL` in production, SQLite fallback in local dev
- Tests: pytest

## Project control

- Status board: [`docs/project-plan/STATUS_BOARD.md`](docs/project-plan/STATUS_BOARD.md)
- Roadmap: [`docs/project-plan/ROADMAP.md`](docs/project-plan/ROADMAP.md)
- Decisions log: [`docs/project-plan/DECISIONS.md`](docs/project-plan/DECISIONS.md)
- Operations runbook: [`docs/project-plan/OPERATIONS.md`](docs/project-plan/OPERATIONS.md)
- Current stand-up plan: [`docs/project-plan/CHAIRMAN_STANDUP_PLAN_2026-04-08.md`](docs/project-plan/CHAIRMAN_STANDUP_PLAN_2026-04-08.md)

## Local run

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python scripts\bootstrap_precomputed_data.py
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`.

## Manual promise curation

Populate `data/manual_promises.json` with entries keyed by `bioguideId`:

```json
{
  "K000401": [
    {
      "title": "Cut taxes for small businesses",
      "description": "Lower tax pressure for small employers and founders.",
      "topic": "Taxes & Budget",
      "source_label": "Campaign platform",
      "source_url": "https://example.com/issues/taxes",
      "confidence": 0.95
    }
  ]
}
```

## Deployment

### Render

Render is the primary host for this app.

1. Add `RENDER_API_KEY` to `.env`.
2. Optionally add `RENDER_OWNER_ID` if your API key can access more than one workspace.
3. Add `DATABASE_URL` if you want persistent production data instead of SQLite fallback.
4. Run:

```powershell
.venv\Scripts\python scripts\deploy_render.py
```

The deployment script creates a `civic-ledger` web service if it does not exist, or triggers a new deploy if it already exists. The Render build now only installs dependencies so deploys stay fast:

```bash
pip install -r requirements.txt
```

The service uses `/healthz` as its health check.

Use the bootstrap script outside the web-service build when you need to seed a new database:

```powershell
python scripts\bootstrap_precomputed_data.py
```

### Scheduled refresh

Use `.github/workflows/refresh-data.yml` to seed baseline snapshots and then run the deep enrichment refresh on a schedule or by manual dispatch. This is the intended full precompute path for production, especially when `DATABASE_URL` is set.

Recommended GitHub secrets:

- `CONGRESS_API_KEY`
- `FEC_API_KEY`
- `DATABASE_URL`

### Vercel

Vercel is config-ready but not deployable with only `VERCEL_TEAM_ID`.

You still need:

- `VERCEL_PROJECT_ID`
- `VERCEL_TOKEN`

`VERCEL_TEAM_ID` only identifies the team scope. It does not authenticate deploys by itself.

## Future news module

The current release does not ship a live news carousel. The codebase only documents a future adapter layer for neutral-source or official congressional headlines so the cover page can later add current-events context without mixing that concern into the scoring system.
