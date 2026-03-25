from app.db import Database
from app.models import ActivitySummary, DeliveryScore, DirectoryMetric, FinanceSummary, OfficialDetail, PromiseItem
from app.services.dashboard import DashboardService


def _seed_official(db: Database) -> None:
    db.upsert_official(
        {
            "bioguide_id": "B001314",
            "name": "Aaron Bean",
            "chamber": "House of Representatives",
            "state": "Florida",
            "district": 4,
            "party": "Republican",
            "image_url": None,
            "image_fallback_url": None,
            "website_url": "https://bean.house.gov",
            "first_name": "Aaron",
            "last_name": "Bean",
            "state_code": "FL",
            "terms": [{"chamber": "House of Representatives", "stateCode": "FL", "startYear": 2023}],
        }
    )


def _detail_snapshot() -> OfficialDetail:
    return OfficialDetail(
        member={"bioguideId": "B001314", "state": "Florida", "terms": [{"stateCode": "FL"}]},
        card={
            "bioguide_id": "B001314",
            "name": "Aaron Bean",
            "chamber": "House of Representatives",
            "state": "Florida",
            "district": 4,
            "party": "Republican",
            "efficiency_score": 64,
            "delivery_score": 48,
            "keeps_promises_score": 52,
            "truth_verdict": "Mixed",
            "truth_badge_variant": "mixed",
        },
        activity=ActivitySummary(),
        finance=FinanceSummary(total_raised=1256090.52, cash_on_hand=1088676.5),
        promises=[
            PromiseItem(
                title="Jobs & Economy",
                description="Grow jobs.",
                topic="Jobs & Economy",
                source_label="Campaign page",
                confidence=0.9,
                evidence_label="Campaign platform",
                provenance="manual",
            )
        ],
        delivery_score=DeliveryScore(overall_score=48, label="Mixed but active", explanation=""),
        methodology_notes=[],
    )


def test_list_officials_uses_precomputed_metrics_without_live_sync(tmp_path, monkeypatch):
    db = Database(str(tmp_path / "test.db"))
    _seed_official(db)
    db.save_snapshot(
        "directory_metric",
        "B001314",
        DirectoryMetric(
            total_raised=1256090.52,
            cash_on_hand=1088676.5,
            efficiency_score=64,
            delivery_score=48,
            keeps_promises_score=52,
            truth_verdict="Mixed",
            truth_badge_variant="mixed",
            top_donor_names=["WEISS, CHARLES BRADFORD"],
        ).model_dump(mode="json"),
    )
    service = DashboardService(db)

    monkeypatch.setattr(service.congress, "ensure_current_members", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("unexpected live sync")))
    monkeypatch.setattr(service.fec, "sync_directory_finance_metrics", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("unexpected live sync")))

    officials = service.list_officials()

    assert len(officials) == 1
    assert officials[0].truth_verdict == "Mixed"
    assert officials[0].delivery_score == 48


def test_get_official_detail_prefers_cached_snapshot(tmp_path, monkeypatch):
    db = Database(str(tmp_path / "test.db"))
    _seed_official(db)
    detail = _detail_snapshot()
    db.save_snapshot("official_detail", "B001314", detail.model_dump(mode="json"))
    service = DashboardService(db)

    monkeypatch.setattr(service, "refresh_official_detail", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("unexpected refresh")))

    loaded = service.get_official_detail("B001314")

    assert loaded.card.name == "Aaron Bean"
    assert loaded.card.truth_verdict == "Mixed"


def test_get_official_detail_can_build_from_cached_component_snapshots(tmp_path, monkeypatch):
    db = Database(str(tmp_path / "test.db"))
    _seed_official(db)
    db.save_snapshot(
        "member_detail",
        "B001314",
        {
            "bioguideId": "B001314",
            "directOrderName": "Aaron Bean",
            "firstName": "Aaron",
            "lastName": "Bean",
            "state": "Florida",
            "district": 4,
            "partyHistory": [{"partyName": "Republican"}],
            "sponsoredLegislation": {"count": 3},
            "cosponsoredLegislation": {"count": 4},
            "terms": [{"chamber": "House of Representatives", "stateCode": "FL", "startYear": 2023}],
        },
    )
    db.save_snapshot("activity", "B001314", ActivitySummary(sponsored_count_total=3, cosponsored_count_total=4).model_dump(mode="json"))
    db.save_snapshot(
        "promises",
        "B001314",
        {
            "items": [
                {
                    "title": "Jobs & Economy",
                    "description": "Grow jobs.",
                    "topic": "Jobs & Economy",
                    "source_label": "Campaign page",
                    "confidence": 0.9,
                    "evidence_label": "Campaign platform",
                    "provenance": "manual",
                }
            ]
        },
    )
    db.save_snapshot("finance", "B001314", FinanceSummary(total_raised=1256090.52, cash_on_hand=1088676.5, available=True).model_dump(mode="json"))
    service = DashboardService(db)

    monkeypatch.setattr(service.congress, "get_member_detail", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("unexpected live detail fetch")))
    monkeypatch.setattr(service.fec, "build_finance_snapshot", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("unexpected finance fetch")))

    loaded = service.get_official_detail("B001314")

    assert loaded.card.name == "Aaron Bean"
    assert loaded.finance.total_raised == 1256090.52
