from fastapi.testclient import TestClient

from app.main import app
from app.models import ActivitySummary, BillRecord, DeliveryScore, FinanceSummary, OfficialCard, OfficialDetail, PromiseItem
from app.routers import api, pages


def _detail_fixture() -> OfficialDetail:
    return OfficialDetail(
        member={"bioguideId": "B001299"},
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
        ),
        activity=ActivitySummary(
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
        methodology_notes=[],
    )


def test_healthz():
    client = TestClient(app)
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_dashboard_html_shows_new_score_labels(monkeypatch):
    card = OfficialCard(
        bioguide_id="B001314",
        name="Aaron Bean",
        chamber="House of Representatives",
        state="Florida",
        district=4,
        party="Republican",
        total_raised=1256090.52,
        efficiency_score=59,
        delivery_score=34,
        keeps_promises_score=50,
        truth_verdict="Mixed",
        truth_badge_variant="mixed",
        last_refreshed_at="2026-03-25T12:00:00+00:00",
        top_donor_names=["WEISS, CHARLES BRADFORD"],
        finance_available=True,
    )
    monkeypatch.setattr(pages.service, "list_officials", lambda *args, **kwargs: [card])
    monkeypatch.setattr(pages.service, "warm_directory_cards", lambda cards, force_refresh=False: cards)

    client = TestClient(app)
    response = client.get("/")

    assert response.status_code == 200
    assert "Is your representative really working for you?" in response.text
    assert "Delivery index" in response.text
    assert "Mixed" in response.text
    assert "Keeps promises index 50" not in response.text


def test_official_detail_html_renders_explainers_and_impact_summary(monkeypatch):
    monkeypatch.setattr(pages.service, "get_official_detail", lambda *args, **kwargs: _detail_fixture())

    client = TestClient(app)
    response = client.get("/officials/B001299")

    assert response.status_code == 200
    assert "Truth verdict" in response.text
    assert "Efficiency metric" in response.text
    assert "Delivery index" in response.text
    assert "Formula: 60% promise coverage + 40% delivery quality." in response.text
    assert "Campaign platform" in response.text
    assert "Changes taxes for local families and employers." in response.text
    assert "$1,088,676" in response.text


def test_api_official_detail_returns_mocked_payload(monkeypatch):
    monkeypatch.setattr(api.service, "get_official_detail", lambda *args, **kwargs: _detail_fixture())

    client = TestClient(app)
    response = client.get("/api/officials/B001299")

    assert response.status_code == 200
    payload = response.json()
    assert payload["card"]["delivery_score"] == 34
    assert payload["card"]["keeps_promises_score"] == 50
    assert payload["card"]["truth_verdict"] == "Mixed"
