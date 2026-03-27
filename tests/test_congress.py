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


def test_ensure_current_members_backfills_website_url_from_fallback(tmp_path, monkeypatch):
    db = Database(str(tmp_path / "test.db"))
    service = CongressService(db)

    monkeypatch.setattr(
        service,
        "_request_json",
        lambda path, params: {
            "members": [
                {
                    "bioguideId": "A000370",
                    "name": "Adams, Alma S.",
                    "state": "North Carolina",
                    "district": 12,
                    "partyName": "Democratic",
                    "officialWebsiteUrl": None,
                    "depiction": {"imageUrl": "https://example.com/a000370.jpg"},
                    "terms": [{"chamber": "House of Representatives", "stateCode": "NC"}],
                }
            ]
        },
    )
    monkeypatch.setattr(
        service,
        "_fallback_members",
        lambda: [
            {
                "bioguide_id": "A000370",
                "name": "Adams, Alma S.",
                "chamber": "House of Representatives",
                "state": "North Carolina",
                "district": 12,
                "party": "Democratic",
                "image_url": "https://example.com/a000370.jpg",
                "image_fallback_url": "https://bioguide.congress.gov/bioguide/photo/A/A000370.jpg",
                "website_url": "https://adams.house.gov",
                "first_name": "Alma",
                "last_name": "Adams",
                "state_code": "NC",
                "terms": [{"chamber": "House of Representatives", "stateCode": "NC", "startYear": 2014}],
            }
        ],
    )

    service.ensure_current_members(force=True)

    payload = db.get_official_payload("A000370")

    assert payload is not None
    assert payload["website_url"] == "https://adams.house.gov"


def test_normalize_member_detail_preserves_existing_website_url(tmp_path):
    db = Database(str(tmp_path / "test.db"))
    db.upsert_official(
        {
            "bioguide_id": "A000370",
            "name": "Adams, Alma S.",
            "chamber": "House of Representatives",
            "state": "North Carolina",
            "district": 12,
            "party": "Democratic",
            "image_url": None,
            "image_fallback_url": None,
            "website_url": "https://adams.house.gov",
            "first_name": "Alma",
            "last_name": "Adams",
            "state_code": "NC",
            "terms": [{"chamber": "House of Representatives", "stateCode": "NC", "startYear": 2014}],
        }
    )
    service = CongressService(db)

    normalized = service._normalize_member_detail(
        {
            "bioguideId": "A000370",
            "directOrderName": "Adams, Alma S.",
            "firstName": "Alma",
            "lastName": "Adams",
            "state": "North Carolina",
            "district": 12,
            "officialWebsiteUrl": None,
            "partyHistory": [{"partyName": "Democratic"}],
            "terms": [{"chamber": "House of Representatives", "stateCode": "NC"}],
            "depiction": {"imageUrl": "https://example.com/a000370.jpg"},
        }
    )

    assert normalized["website_url"] == "https://adams.house.gov"
