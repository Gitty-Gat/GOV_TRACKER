from __future__ import annotations

import math

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.services.dashboard import DashboardService
from app.services.scoring import summarize_finance_alignment

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory="app/templates")
service = DashboardService()


@router.get("/", response_class=HTMLResponse)
def home(
    request: Request,
    search: str | None = Query(default=None),
    chamber: str | None = Query(default=None),
    party: str | None = Query(default=None),
    state: str | None = Query(default=None),
    sort: str = Query(default="name"),
    page: int = Query(default=1),
):
    all_officials = service.list_officials()
    officials = service.list_officials(search=search, chamber=chamber, party=party, state=state, sort_by=sort)
    per_page = 24
    total_pages = max(1, math.ceil(len(officials) / per_page))
    current_page = min(max(page, 1), total_pages)
    start = (current_page - 1) * per_page
    page_cards = service.warm_directory_cards(officials[start : start + per_page])
    states = sorted({official.state for official in all_officials})
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "officials": page_cards,
            "filters": {"search": search or "", "chamber": chamber or "", "party": party or "", "state": state or "", "sort": sort, "page": current_page},
            "state_options": states,
            "pagination": {"page": current_page, "total_pages": total_pages},
            "stats": {
                "official_count": len(officials),
                "house_count": sum(1 for official in all_officials if official.chamber == "House of Representatives"),
                "senate_count": sum(1 for official in all_officials if official.chamber == "Senate"),
            },
        },
    )


@router.get("/officials/{bioguide_id}", response_class=HTMLResponse)
def official_detail(request: Request, bioguide_id: str, refresh: bool = False):
    detail = service.get_official_detail(bioguide_id, force_refresh=refresh)
    finance_signal = summarize_finance_alignment(detail.finance.constituent_share, detail.finance.pac_share)
    return templates.TemplateResponse(
        request,
        "official_detail.html",
        {"detail": detail, "finance_signal": finance_signal},
    )
