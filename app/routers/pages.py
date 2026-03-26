from __future__ import annotations

import math

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.services.dashboard import DashboardService, _sort_key
from app.services.scoring import summarize_finance_alignment

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory="app/templates")
service = DashboardService()

DEFINITION_ITEMS = [
    {
        "term": "Truth verdict",
        "body": "A plain-language signal showing whether visible work lines up with stated priorities. It only appears when the app has enough activity and promise data.",
    },
    {
        "term": "Delivery index",
        "body": "A score for how far matched bills actually moved. Higher means stronger visible follow-through, not just filing a bill.",
    },
    {
        "term": "Efficiency metric",
        "body": "A time-normalized measure of legislative output. It compares visible bill work to years in office.",
    },
    {
        "term": "PAC",
        "body": "A political action committee. These groups raise and spend money to support or oppose candidates and policy priorities.",
    },
    {
        "term": "War chest",
        "body": "A campaign's available money position, including total receipts, cash on hand, and where the money came from.",
    },
    {
        "term": "Cash on hand",
        "body": "Money still sitting in the campaign account at the end of the latest reporting period.",
    },
    {
        "term": "Total receipts",
        "body": "The total money reported as coming into the campaign during the cycle.",
    },
    {
        "term": "PAC share",
        "body": "The share of total receipts that came from organized committees and party committees.",
    },
    {
        "term": "Home-state donor share",
        "body": "The share of geocoded donations that came from the official's home state. It is a proxy, not a perfect measure of constituent support.",
    },
]

NEWS_INTEGRATION_NOTES = [
    "Add a future adapter layer that can pull headlines from neutral national outlets or official congressional reporting feeds.",
    "Render the headlines in a future cover-page or officeholder-page slot, with article image, source, and external link.",
    "Keep the first news release simple: headline feed only, without automatic bill-to-article matching.",
]


@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(
        request,
        "cover.html",
        {
            "show_sidebar": False,
            "news_integration_notes": NEWS_INTEGRATION_NOTES,
        },
    )


@router.get("/officeholders", response_class=HTMLResponse)
def officeholders(
    request: Request,
    search: str | None = Query(default=None),
    chamber: str | None = Query(default=None),
    party: str | None = Query(default=None),
    state: str | None = Query(default=None),
    sort: str = Query(default="name"),
    page: int = Query(default=1),
):
    all_officials = service.list_officials()
    officials = [
        official
        for official in all_officials
        if (not search or search.lower() in official.name.lower() or search.lower() in official.state.lower())
        and (not chamber or official.chamber == chamber)
        and (not party or official.party == party)
        and (not state or official.state == state)
    ]
    officials = sorted(officials, key=lambda official: _sort_key(official, sort))
    per_page = 24
    total_pages = max(1, math.ceil(len(officials) / per_page))
    current_page = min(max(page, 1), total_pages)
    start = (current_page - 1) * per_page
    page_cards = officials[start : start + per_page]
    states = sorted({official.state for official in all_officials})
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "show_sidebar": True,
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


@router.get("/definitions", response_class=HTMLResponse)
def definitions(request: Request):
    return templates.TemplateResponse(
        request,
        "definitions.html",
        {
            "show_sidebar": False,
            "definitions": DEFINITION_ITEMS,
            "news_integration_notes": NEWS_INTEGRATION_NOTES,
        },
    )


@router.get("/officials/{bioguide_id}", response_class=HTMLResponse)
def official_detail(request: Request, bioguide_id: str):
    detail = service.get_official_detail(bioguide_id)
    finance_signal = summarize_finance_alignment(detail.finance.constituent_share, detail.finance.pac_share)
    promise_delivery_rows = _build_promise_delivery_rows(detail)
    return templates.TemplateResponse(
        request,
        "official_detail.html",
        {
            "show_sidebar": True,
            "detail": detail,
            "finance_signal": finance_signal,
            "promise_delivery_rows": promise_delivery_rows,
        },
    )


def _build_promise_delivery_rows(detail):
    topic_scores = detail.delivery_score.topic_scores or []
    rows = []
    used_topics: set[str] = set()
    for promise in detail.promises:
        delivery = next((score for score in topic_scores if score.topic == promise.topic or score.promise_title == promise.title), None)
        if delivery:
            used_topics.add(delivery.topic)
        rows.append({"promise": promise, "delivery": delivery})
    for delivery in topic_scores:
        if delivery.topic in used_topics:
            continue
        rows.append({"promise": None, "delivery": delivery})
    return rows
