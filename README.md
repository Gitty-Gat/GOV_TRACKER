# Civic Ledger

Civic Ledger is a House and Senate dashboard focused on two questions:

1. Who funds a federal elected official?
2. What has that official tangibly done in office relative to their stated priorities?

This MVP ships as a FastAPI application with a designed frontend, on-demand public-data aggregation, and a transparent scoring layer instead of a black-box ranking.

## Product shape

- Filterable House/Senate landing dashboard with member photos and search.
- Official detail view with war-chest metrics, major donors, PAC audit trails, state contribution mix, legislative activity, and a promise-to-action delivery index.
- JSON API endpoints for reuse by a richer frontend later.

## Data strategy

### Current implementation

- Congress member metadata and legislative activity: `Congress.gov` API.
- Current-member bootstrap fallback when the Congress demo key is exhausted: `unitedstates/congress-legislators`.
- Campaign finance totals and itemized donor/PAC data: `OpenFEC` API.
- Stated priorities:
  - Preferred: curated manual promises in `data/manual_promises.json`.
  - Fallback: inferred issue priorities from official member website language.

### Caching and rate limiting

- Current-member sync happens once per day by default and is stored in SQLite.
- If the Congress demo key rate-limits, the app falls back to a public current-member dataset so the main directory still works.
- Detail, activity, finance, and promise snapshots are cached independently with separate TTLs.
- The app is designed to work with `DEMO_KEY`, but finance endpoints degrade quickly under the FEC demo limit.
- For real usage, set personal `CONGRESS_API_KEY` and `FEC_API_KEY` values in `.env`.

### Truthfulness constraints

- The dashboard shows funding patterns and policy activity side by side.
- It does not claim causation between donations and outcomes.
- The promise score is explainable and evidence-backed, with methodology exposed in the UI.

## Stack

- Backend: FastAPI
- Frontend: Jinja templates, custom CSS, vanilla JS
- Storage and cache: SQLite
- Tests: pytest

## Local run

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python scripts\bootstrap_members.py
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

This repo is ready for a free-hosting handoff, but actual remote deployment still requires your account credentials. The cleanest target from here is Vercel or Render once the repo is pushed to GitHub.
