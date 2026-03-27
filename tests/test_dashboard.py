from app.db import Database
from app.models import ActivitySummary, BillRecord, DeliveryScore, DirectoryMetric, FinanceSummary, OfficialDetail, PromiseItem
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
        member={"bioguideId": "B001314", "state": "Florida", "terms": [{"stateCode": "FL"}], "detailReadiness": "enriched"},
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
            "data_readiness": "enriched",
            "finance_status": "enriched",
            "activity_status": "enriched",
            "promises_status": "enriched",
        },
        activity=ActivitySummary(status="enriched"),
        finance=FinanceSummary(status="enriched", total_raised=1256090.52, cash_on_hand=1088676.5),
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
        data_readiness="enriched",
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
            data_readiness="enriched",
            finance_status="enriched",
            activity_status="enriched",
            promises_status="enriched",
        ).model_dump(mode="json"),
    )
    service = DashboardService(db)

    monkeypatch.setattr(service.congress, "ensure_current_members", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("unexpected live sync")))
    monkeypatch.setattr(service.fec, "sync_directory_finance_metrics", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("unexpected live sync")))

    officials = service.list_officials()

    assert len(officials) == 1
    assert officials[0].truth_verdict == "Mixed"
    assert officials[0].delivery_score == 48
    assert officials[0].data_readiness == "enriched"


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


def test_get_official_detail_can_build_seeded_snapshot_from_cached_components(tmp_path, monkeypatch):
    db = Database(str(tmp_path / "test.db"))
    _seed_official(db)
    db.save_snapshot(
        "member_detail",
        "B001314",
        {
            "bioguideId": "B001314",
            "detailReadiness": "seeded",
            "directOrderName": "Aaron Bean",
            "firstName": "Aaron",
            "lastName": "Bean",
            "state": "Florida",
            "district": 4,
            "partyHistory": [{"partyName": "Republican"}],
            "sponsoredLegislation": {"count": None},
            "cosponsoredLegislation": {"count": None},
            "terms": [{"chamber": "House of Representatives", "stateCode": "FL", "startYear": 2023}],
        },
    )
    db.save_snapshot("activity", "B001314", ActivitySummary(status="seeded").model_dump(mode="json"))
    db.save_snapshot("promises", "B001314", {"items": []})
    db.save_snapshot("finance", "B001314", FinanceSummary(status="pending", total_raised=None, cash_on_hand=None, available=False).model_dump(mode="json"))
    service = DashboardService(db)

    monkeypatch.setattr(service.congress, "get_member_detail", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("unexpected live detail fetch")))
    monkeypatch.setattr(service.fec, "build_finance_snapshot", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("unexpected finance fetch")))

    loaded = service.get_official_detail("B001314")

    assert loaded.card.name == "Aaron Bean"
    assert loaded.card.truth_verdict is None
    assert loaded.card.data_readiness == "seeded"
    assert loaded.finance.total_raised is None
    assert loaded.delivery_score.overall_score is None


def test_seed_baseline_data_creates_directory_and_detail_snapshots(tmp_path, monkeypatch):
    db = Database(str(tmp_path / "test.db"))
    _seed_official(db)
    service = DashboardService(db)

    monkeypatch.setattr(service.congress, "ensure_current_members", lambda force=False: None)
    monkeypatch.setattr(service.fec, "sync_directory_finance_metrics", lambda force=False: None)
    monkeypatch.setattr(
        service.congress,
        "ensure_member_detail_snapshot",
        lambda bioguide_id: {
            "bioguideId": bioguide_id,
            "detailReadiness": "seeded",
            "directOrderName": "Aaron Bean",
            "firstName": "Aaron",
            "lastName": "Bean",
            "state": "Florida",
            "district": 4,
            "officialWebsiteUrl": "https://bean.house.gov",
            "partyHistory": [{"partyName": "Republican"}],
            "sponsoredLegislation": {"count": None},
            "cosponsoredLegislation": {"count": None},
            "terms": [{"chamber": "House of Representatives", "stateCode": "FL", "startYear": 2023}],
        },
    )
    monkeypatch.setattr(
        service.congress,
        "build_lightweight_activity_snapshot",
        lambda member, note=None: ActivitySummary(status="seeded", notes=[note] if note else []),
    )
    monkeypatch.setattr(
        service.promises,
        "load_cached_promises",
        lambda bioguide_id: [
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
    )
    monkeypatch.setattr(
        service.fec,
        "load_cached_finance_snapshot",
        lambda bioguide_id: FinanceSummary(status="partial", available=False, total_raised=None, cash_on_hand=None, warning="Finance pending"),
    )
    monkeypatch.setattr(
        service.fec,
        "_partial_finance_summary",
        lambda member, error_text: FinanceSummary(status="pending", available=False, warning="Finance pending"),
    )

    results = service.seed_baseline_data(force=True)

    metric_payload, _ = db.load_snapshot("directory_metric", "B001314")
    detail_payload, _ = db.load_snapshot("official_detail", "B001314")
    assert results == {"processed": 1, "failed": 0}
    assert metric_payload["data_readiness"] == "partial"
    assert metric_payload["truth_verdict"] is None
    assert detail_payload["data_readiness"] == "partial"
    assert detail_payload["card"]["truth_verdict"] is None


def test_refresh_read_model_enriches_finance_and_promises_when_missing(tmp_path, monkeypatch):
    db = Database(str(tmp_path / "test.db"))
    _seed_official(db)
    db.save_snapshot(
        "member_detail",
        "B001314",
        {
            "bioguideId": "B001314",
            "detailReadiness": "enriched",
            "directOrderName": "Aaron Bean",
            "firstName": "Aaron",
            "lastName": "Bean",
            "state": "Florida",
            "district": 4,
            "officialWebsiteUrl": None,
            "partyHistory": [{"partyName": "Republican"}],
            "sponsoredLegislation": {"count": 12},
            "cosponsoredLegislation": {"count": 18},
            "terms": [{"chamber": "House of Representatives", "stateCode": "FL", "startYear": 2023}],
        },
    )
    service = DashboardService(db)

    monkeypatch.setattr(service.congress, "ensure_current_members", lambda force=False: None)
    monkeypatch.setattr(
        service.congress,
        "build_activity_snapshot",
        lambda bioguide_id, force=False: ActivitySummary(
            status="enriched",
            sponsored_count_total=12,
            cosponsored_count_total=18,
            recent_bills=[
                BillRecord(
                    title="Expand workforce training",
                    bill_number="HR 101",
                    congress=119,
                    policy_area="Jobs & Economy",
                    latest_action_text="Passed House",
                    sponsorship="sponsored",
                    stage="passed",
                    stage_weight=8,
                    impact_summary="Expands workforce training access.",
                )
            ],
        ),
    )
    monkeypatch.setattr(service.promises, "load_cached_promises", lambda bioguide_id: [])
    monkeypatch.setattr(
        service.promises,
        "get_promises",
        lambda member, force=False: [
            PromiseItem(
                title="Jobs & Economy",
                description="Expand workforce training.",
                topic="Jobs & Economy",
                source_label="Official website issue language",
                source_url="https://bean.house.gov",
                confidence=0.8,
                evidence_label="Moderate evidence",
                provenance="inferred",
            )
        ],
    )
    monkeypatch.setattr(service.fec, "ensure_directory_finance_metric", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        service.fec,
        "build_finance_snapshot",
        lambda member, force=False: FinanceSummary(
            status="enriched",
            available=True,
            total_raised=1256090.52,
            cash_on_hand=1088676.5,
            individual_contributions=476035.2,
            organized_committee_contributions=703150.0,
            transfer_contributions=62992.86,
            other_receipts=3912.46,
            pac_audit_trails=[],
        ),
    )

    results = service.refresh_read_model(refresh_promises=False)
    detail_payload, _ = db.load_snapshot("official_detail", "B001314")

    assert results == {"processed": 1, "failed": 0}
    assert detail_payload["finance"]["status"] == "enriched"
    assert detail_payload["card"]["truth_verdict"] is not None
    assert detail_payload["card"]["promises_status"] == "enriched"
