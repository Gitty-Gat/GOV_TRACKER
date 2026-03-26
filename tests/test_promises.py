from app.db import Database
from app.services.promises import PromiseService


def test_get_promises_falls_back_to_stored_website_url(tmp_path, monkeypatch):
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
    service = PromiseService(db)
    seen = {"url": None}

    def fake_infer(url):
        seen["url"] = url
        return []

    monkeypatch.setattr(service, "_infer_from_official_site", fake_infer)

    service.get_promises(
        {
            "bioguideId": "A000370",
            "officialWebsiteUrl": None,
        },
        force=True,
    )

    assert seen["url"] == "https://adams.house.gov"
