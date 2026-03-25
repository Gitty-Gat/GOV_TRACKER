from app.db import Database
from app.services.congress import CongressService


def test_fetch_legislation_handles_null_latest_action(tmp_path, monkeypatch):
    db = Database(str(tmp_path / "test.db"))
    service = CongressService(db)

    def fake_request_json(path, params):
        return {
            "sponsoredLegislation": [
                {
                    "number": "101",
                    "type": "hr",
                    "latestAction": None,
                    "policyArea": None,
                    "title": None,
                    "congress": 119,
                    "url": "https://example.com/bill",
                }
            ]
        }

    monkeypatch.setattr(service, "_request_json", fake_request_json)

    records = service._fetch_legislation("B001299", "sponsored-legislation", "sponsored", max_items=5)

    assert len(records) == 1
    assert records[0].title == "Untitled legislation"
    assert records[0].latest_action_text == ""
    assert records[0].policy_area == "Unspecified"
    assert records[0].impact_summary
