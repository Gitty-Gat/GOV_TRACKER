from app.db import Database
from app.models import DirectoryMetric, FinanceSummary
from app.services.fec import FECService


def test_build_snapshot_normalizes_receipts_and_pac_trails(tmp_path, monkeypatch):
    db = Database(str(tmp_path / "test.db"))
    service = FECService(db)

    member = {
        "bioguideId": "B001314",
        "state": "Florida",
        "terms": [{"chamber": "House of Representatives", "stateCode": "FL"}],
    }

    candidate = {
        "candidate_id": "H2FL04211",
        "principal_committees": [
            {
                "designation": "P",
                "committee_id": "C00816983",
                "name": "AARON BEAN FOR CONGRESS",
            }
        ],
    }

    def fake_request_json(path, params):
        if path == "/candidate/H2FL04211/totals/":
            return {
                "results": [
                    {
                        "receipts": 1256090.52,
                        "individual_contributions": 476035.2,
                        "other_political_committee_contributions": 698150.0,
                        "political_party_committee_contributions": 5000.0,
                        "transfers_from_other_authorized_committee": 62992.86,
                        "other_receipts": 13912.46,
                        "last_cash_on_hand_end_period": 1088676.5,
                        "disbursements": 642135.01,
                        "individual_itemized_contributions": 472435.79,
                    }
                ]
            }
        if path == "/schedules/schedule_a/by_state/":
            return {"results": [{"state": "Florida", "total": 400000}]}
        if path == "/schedules/schedule_a/":
            committee_id = params["committee_id"]
            if committee_id == "C00816983":
                return {
                    "results": [
                        {
                            "contribution_receipt_amount": 20023.68,
                            "contributor_name": "AARON BEAN TEAM",
                            "contributor_id": "C00840876",
                            "contributor_state": "FL",
                            "entity_type_desc": "OTHER COMMITTEE",
                            "is_individual": False,
                            "contributor": {"committee_id": "C00840876", "name": "AARON BEAN TEAM", "committee_type_full": "PAC - Nonqualified"},
                        },
                        {
                            "contribution_receipt_amount": 18543.94,
                            "contributor_name": "AARON BEAN TEAM",
                            "contributor_id": "C00840876",
                            "contributor_state": "FL",
                            "entity_type_desc": "OTHER COMMITTEE",
                            "is_individual": False,
                            "contributor": {"committee_id": "C00840876", "name": "AARON BEAN TEAM", "committee_type_full": "PAC - Nonqualified"},
                        },
                        {
                            "contribution_receipt_amount": 1000.0,
                            "contributor_name": "WEISS, CHARLES BRADFORD",
                            "contributor_state": "FL",
                            "entity_type_desc": "INDIVIDUAL",
                            "is_individual": True,
                            "contributor": {},
                        },
                    ]
                }
            if committee_id == "C00840876":
                return {
                    "results": [
                        {
                            "contribution_receipt_amount": 25000.0,
                            "contributor_name": "DONOR PAC",
                            "contributor_id": "C90000001",
                            "entity_type_desc": "OTHER COMMITTEE",
                            "is_individual": False,
                            "contributor": {"committee_id": "C90000001", "name": "DONOR PAC", "committee_type_full": "PAC - Nonqualified"},
                        }
                    ]
                }
        if path == "/schedules/schedule_b/":
            return {
                "results": [
                    {
                        "recipient_name": "NRCC",
                        "disbursement_amount": 40000.0,
                        "committee_id": params["committee_id"],
                    }
                ]
            }
        raise AssertionError(f"Unexpected path {path}")

    monkeypatch.setattr(service, "_match_candidate", lambda member_payload: candidate)
    monkeypatch.setattr(service, "_request_json", fake_request_json)
    monkeypatch.setattr(service, "_safe_other_recipients", lambda name: [])

    summary = service._build_snapshot(member)

    assert summary.total_raised == 1256090.52
    assert summary.organized_committee_contributions == 703150.0
    assert round(
        summary.individual_contributions
        + summary.organized_committee_contributions
        + summary.transfer_contributions
        + summary.other_receipts,
        2,
    ) == round(summary.total_raised, 2)
    assert summary.top_pac_donors[0].name == "AARON BEAN TEAM"
    assert summary.pac_audit_trails[0].pac_committee_id == "C00840876"
    assert summary.pac_audit_trails[0].outbound_targets[0].name == "NRCC"


def test_partial_finance_summary_prefers_directory_metric_over_failed_cache(tmp_path):
    db = Database(str(tmp_path / "test.db"))
    service = FECService(db)
    member = {"bioguideId": "B001314"}

    db.save_snapshot(
        "finance",
        "B001314",
        FinanceSummary(
            available=False,
            warning="Old failed refresh",
            total_raised=0.0,
            cash_on_hand=0.0,
        ).model_dump(mode="json"),
    )
    db.save_snapshot(
        "directory_metric",
        "B001314",
        DirectoryMetric(
            finance_available=True,
            candidate_id="H2FL04211",
            principal_committee_id="C00816983",
            total_raised=1256090.52,
            cash_on_hand=1088676.5,
            top_donor_names=["WEISS, CHARLES BRADFORD"],
        ).model_dump(mode="json"),
    )

    summary = service.build_finance_snapshot(member, force=False)

    assert summary.total_raised == 1256090.52
    assert summary.cash_on_hand == 1088676.5
    assert summary.top_donors[0].name == "WEISS, CHARLES BRADFORD"
    assert "failed" in (summary.warning or "").lower() or "directory finance" in (summary.warning or "").lower()
