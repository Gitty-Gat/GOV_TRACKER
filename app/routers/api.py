from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.services.dashboard import DashboardService

router = APIRouter(prefix="/api", tags=["api"])
service = DashboardService()


@router.get("/officials")
def list_officials(
    search: str | None = Query(default=None),
    chamber: str | None = Query(default=None),
    party: str | None = Query(default=None),
    state: str | None = Query(default=None),
):
    officials = service.list_officials(search=search, chamber=chamber, party=party, state=state)
    return {"results": [official.model_dump(mode="json") for official in officials], "count": len(officials)}


@router.get("/officials/{bioguide_id}")
def get_official(bioguide_id: str, refresh: bool = False):
    try:
        detail = service.get_official_detail(bioguide_id, force_refresh=refresh)
    except (KeyError, IndexError) as exc:
        raise HTTPException(status_code=404, detail="Official not found") from exc
    return detail.model_dump(mode="json")
