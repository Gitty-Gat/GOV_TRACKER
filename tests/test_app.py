from fastapi.testclient import TestClient

from app.main import app
from app.models import ActivitySummary, BillRecord, DeliveryScore, FinanceSummary, OfficialCard, OfficialDetail, PromiseItem
from app.routers import api, pages


def _seeded_detail_fixture() -> OfficialDetail:
    return OfficialDetail(
        member={"bioguideId": "A000370", "directOrderName": "Adams, Alma S."},
        card=OfficialCard(
            bioguide_id="A000370",
            name="Adams, Alma S.",
            chamber="House of Representatives",
            state="North Carolina",
            district=12,
            party="Democratic",
            truth_verdict=None,
            truth_badge_variant=None,
            efficiency_score=None,
            delivery_score=None,
            keeps_promises_score=None,
            last_refreshed_at="2026-03-25T12:00:00+00:00",
            data_readiness="seeded",
            finance_status="pending",
            activity_status="seeded",
            promises_status="pending",
            finance_available=False,
        ),
        activity=ActivitySummary(
            status="seeded",
            notes=[
                "This quick view uses cached counts while detailed bill activity is still loading.",
            ],
        ),
        finance=FinanceSummary(
            status="pending",
            available=False,
            warning="Showing cached directory finance while detailed finance loads.",
            total_raised=None,
            cash_on_hand=None,
            notes=["Directory-level finance cache is being shown because a live FEC refresh was unavailable."],
        ),
        promises=[],
        delivery_score=DeliveryScore(
            overall_score=None,
            label="Insufficient data",
            explanation="The score becomes meaningful after the dashboard has both issue priorities and recent legislative activity.",
        ),
        data_readiness="seeded",
        methodology_notes=[],
    )


def _enriched_detail_fixture() -> OfficialDetail:
    return OfficialDetail(
        member={"bioguideId": "B001299", "directOrderName": "Jim Banks"},
        card=OfficialCard(
            bioguide_id="B001299",
            name="Jim Banks",
            chamber="Senate",
            state="Indiana",
            party="Republican",
            total_raised=1256090.52,
            cash_on_hand=1088676.5,
            efficiency_score=59,
            delivery_score=34,
            keeps_promises_score=50,
            truth_verdict="Mixed",
            truth_badge_variant="mixed",
            last_refreshed_at="2026-03-25T12:00:00+00:00",
            top_donor_names=["WEISS, CHARLES BRADFORD"],
            finance_available=True,
            data_readiness="enriched",
            finance_status="enriched",
            activity_status="enriched",
            promises_status="enriched",
        ),
        activity=ActivitySummary(
            status="enriched",
            sponsored_count_total=12,
            cosponsored_count_total=21,
            recent_bills=[
                BillRecord(
                    title="HSA's For All Act",
                    bill_number="HR 7681",
                    congress=119,
                    policy_area="Taxation",
                    latest_action_text="Referred to committee",
                    stage="committee",
                    stage_weight=2.0,
                    sponsorship="sponsored",
                    impact_summary="Changes taxes for local families and employers.",
                )
            ],
        ),
        finance=FinanceSummary(
            status="enriched",
            available=True,
            total_raised=1256090.52,
            cash_on_hand=1088676.5,
            individual_contributions=476035.2,
            organized_committee_contributions=703150.0,
            pac_contributions=703150.0,
            transfer_contributions=62992.86,
            other_receipts=13912.46,
            constituent_share=0.41,
            in_state_share_basis_amount=960000.0,
            in_state_share_label="Indiana donors: $394,000 of $960,000 geocoded receipts",
            pac_share=0.56,
            coverage_end_date="2026-12-31",
        ),
        promises=[
            PromiseItem(
                title="Taxes & Budget",
                description="Tax focus",
                topic="Taxes & Budget",
                source_label="manual",
                confidence=0.9,
                evidence_label="Campaign platform",
                provenance="manual",
            )
        ],
        delivery_score=DeliveryScore(
            overall_score=34,
            label="Early or uneven",
            explanation="This index averages weighted follow-through across stated priorities.",
        ),
        data_readiness="enriched",
        methodology_notes=[],
    )


def test_healthz():
    client = TestClient(app)
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_cover_page_renders_ctas():
    client = TestClient(app)
    response = client.get("/")

    assert response.status_code == 200
    assert "Follow the money. Check the work." in response.text
    assert "Explore officeholders" in response.text
    assert "Learn the basics" in response.text


def test_officeholders_page_uses_collapsible_score_guide(monkeypatch):
    card = OfficialCard(
        bioguide_id="A000370",
        name="Adams, Alma S.",
        chamber="House of Representatives",
        state="North Carolina",
        district=12,
        party="Democratic",
        truth_verdict=None,
        truth_badge_variant=None,
        efficiency_score=None,
        delivery_score=None,
        data_readiness="seeded",
        finance_status="pending",
        activity_status="seeded",
        promises_status="pending",
    )
    monkeypatch.setattr(pages.service, "list_officials", lambda *args, **kwargs: [card])

    client = TestClient(app)
    response = client.get("/officeholders")

    assert response.status_code == 200
    assert "Search the people in office" in response.text
    assert "<details" in response.text
    assert "Needs more data" in response.text
    assert "Finance pending" in response.text


def test_definitions_page_renders_beginner_terms():
    client = TestClient(app)
    response = client.get("/definitions")

    assert response.status_code == 200
    assert "Truth verdict" in response.text
    assert "Home-state donor share" in response.text
    assert "Future news module" in response.text


def test_seeded_profile_does_not_render_fake_verdict_or_zero_finance(monkeypatch):
    monkeypatch.setattr(pages.service, "get_official_detail", lambda *args, **kwargs: _seeded_detail_fixture())

    client = TestClient(app)
    response = client.get("/officials/A000370")

    assert response.status_code == 200
    assert "Needs more data" in response.text
    assert "This profile was seeded for quick site launch." in response.text
    assert "Misleading" not in response.text
    assert "$0" not in response.text


def test_enriched_profile_renders_bill_summary_and_formula(monkeypatch):
    monkeypatch.setattr(pages.service, "get_official_detail", lambda *args, **kwargs: _enriched_detail_fixture())

    client = TestClient(app)
    response = client.get("/officials/B001299")

    assert response.status_code == 200
    assert "Formula: 60% promise coverage + 40% delivery quality." in response.text
    assert "Campaign platform" in response.text
    assert "Changes taxes for local families and employers." in response.text
    assert "$1,088,676" in response.text


def test_api_official_detail_exposes_readiness_and_nullable_verdict(monkeypatch):
    monkeypatch.setattr(api.service, "get_official_detail", lambda *args, **kwargs: _seeded_detail_fixture())

    client = TestClient(app)
    response = client.get("/api/officials/A000370")

    assert response.status_code == 200
    payload = response.json()
    assert payload["data_readiness"] == "seeded"
    assert payload["card"]["truth_verdict"] is None
    assert payload["card"]["delivery_score"] is None
    assert payload["finance"]["total_raised"] is None
    assert payload["delivery_score"]["overall_score"] is None
