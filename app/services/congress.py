from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

import requests
import yaml

from app.db import Database
from app.models import ActivitySummary, BillRecord, PolicyAreaStat
from app.services.scoring import summarize_bill_impact
from app.settings import get_settings


class CongressService:
    BASE_URL = "https://api.congress.gov/v3"
    FALLBACK_MEMBERS_URL = "https://raw.githubusercontent.com/unitedstates/congress-legislators/main/legislators-current.yaml"

    def __init__(self, db: Database | None = None) -> None:
        self.settings = get_settings()
        self.db = db or Database()

    def ensure_current_members(self, force: bool = False) -> None:
        last_sync = self.db.get_meta("officials_last_sync")
        if not force and self.db.official_count() >= 530 and last_sync:
            synced_at = datetime.fromisoformat(last_sync)
            if datetime.now(timezone.utc) - synced_at < timedelta(hours=self.settings.officials_sync_hours):
                return

        try:
            offset = 0
            while True:
                payload = self._request_json(
                    "/member",
                    {
                        "currentMember": "true",
                        "limit": 250,
                        "offset": offset,
                        "format": "json",
                    },
                )
                members = payload.get("members", [])
                if not members:
                    break
                for member in members:
                    self.db.upsert_official(self._normalize_member_summary(member))
                if len(members) < 250:
                    break
                offset += 250
        except requests.RequestException:
            for member in self._fallback_members():
                self.db.upsert_official(member)

        self.db.set_meta("officials_last_sync", datetime.now(timezone.utc).replace(microsecond=0).isoformat())

    def get_member_detail(self, bioguide_id: str, force: bool = False) -> dict[str, Any]:
        cached = self.db.load_snapshot("member_detail", bioguide_id)
        if cached and not force:
            payload, fetched_at = cached
            if datetime.now(timezone.utc) - fetched_at < timedelta(hours=self.settings.detail_cache_hours):
                return payload

        try:
            payload = self._request_json(f"/member/{bioguide_id}", {"format": "json"})
            member = payload["member"]
            member["detailReadiness"] = "enriched"
            self.db.upsert_official(self._normalize_member_detail(member))
            self.db.save_snapshot("member_detail", bioguide_id, member)
            return member
        except requests.RequestException:
            fallback = self._fallback_member_detail(bioguide_id)
            if fallback:
                self.db.save_snapshot("member_detail", bioguide_id, fallback)
                return fallback
            raise

    def load_cached_member_detail(self, bioguide_id: str) -> dict[str, Any] | None:
        cached = self.db.load_snapshot("member_detail", bioguide_id)
        if cached:
            payload, _ = cached
            return payload
        return self._fallback_member_detail(bioguide_id)

    def ensure_member_detail_snapshot(self, bioguide_id: str) -> dict[str, Any] | None:
        cached = self.db.load_snapshot("member_detail", bioguide_id)
        if cached:
            return cached[0]
        fallback = self._fallback_member_detail(bioguide_id)
        if fallback:
            self.db.save_snapshot("member_detail", bioguide_id, fallback)
        return fallback

    def build_activity_snapshot(self, bioguide_id: str, force: bool = False) -> ActivitySummary:
        cached = self.db.load_snapshot("activity", bioguide_id)
        if cached and not force:
            payload, fetched_at = cached
            if datetime.now(timezone.utc) - fetched_at < timedelta(hours=self.settings.activity_cache_hours):
                return ActivitySummary.model_validate(payload)

        member = self.load_cached_member_detail(bioguide_id)
        if not member:
            member = self.get_member_detail(bioguide_id, force=force)
        notes = [
            "Activity scores are computed from recent sponsored and cosponsored legislation sampled from Congress.gov.",
            "Sponsored bills are weighted more heavily than cosponsored bills.",
        ]
        detailed_available = True
        try:
            sponsored = self._fetch_legislation(bioguide_id, "sponsored-legislation", "sponsored", max_items=40)
            cosponsored = self._fetch_legislation(bioguide_id, "cosponsored-legislation", "cosponsored", max_items=40)
        except requests.RequestException:
            sponsored = []
            cosponsored = []
            detailed_available = False
            notes.append("Congress activity detail is temporarily unavailable under the demo rate limit.")
        policy_weights: Counter[str] = Counter()
        enacted_count = 0
        passed_count = 0
        committee_progress_count = 0

        all_bills = sponsored + cosponsored
        for bill in all_bills:
            policy_weights[bill.policy_area] += bill.stage_weight
            if bill.stage == "enacted":
                enacted_count += 1
            elif bill.stage == "passed":
                passed_count += 1
            elif bill.stage == "committee":
                committee_progress_count += 1

        top_policy_areas = [
            PolicyAreaStat(
                name=name,
                weight=round(weight, 2),
                bill_count=sum(1 for bill in all_bills if bill.policy_area == name),
            )
            for name, weight in policy_weights.most_common(6)
        ]
        summary = ActivitySummary(
            status="enriched" if detailed_available else "pending",
            sponsored_count_total=(member.get("sponsoredLegislation") or {}).get("count") or 0,
            cosponsored_count_total=(member.get("cosponsoredLegislation") or {}).get("count") or 0,
            enacted_count=enacted_count,
            passed_count=passed_count,
            committee_progress_count=committee_progress_count,
            sampled_sponsored_count=len(sponsored),
            sampled_cosponsored_count=len(cosponsored),
            top_policy_areas=top_policy_areas,
            recent_bills=sorted(
                all_bills,
                key=lambda bill: (bill.latest_action_date or "", bill.introduced_date or ""),
                reverse=True,
            )[:16],
            notes=notes,
        )
        self.db.save_snapshot("activity", bioguide_id, summary.model_dump(mode="json"))
        return summary

    def load_cached_activity_snapshot(self, bioguide_id: str) -> ActivitySummary | None:
        cached = self.db.load_snapshot("activity", bioguide_id)
        if not cached:
            return None
        payload, _ = cached
        return ActivitySummary.model_validate(payload)

    def build_lightweight_activity_snapshot(self, member: dict[str, Any], note: str | None = None) -> ActivitySummary:
        notes = [
            "This quick view uses cached counts while detailed bill activity is still loading.",
        ]
        if note:
            notes.append(note)
        return ActivitySummary(
            status="seeded",
            sponsored_count_total=(member.get("sponsoredLegislation") or {}).get("count") or 0,
            cosponsored_count_total=(member.get("cosponsoredLegislation") or {}).get("count") or 0,
            notes=notes,
        )

    def _fetch_legislation(
        self,
        bioguide_id: str,
        endpoint: str,
        sponsorship: str,
        max_items: int,
    ) -> list[BillRecord]:
        records: list[BillRecord] = []
        offset = 0
        per_page = 20
        while len(records) < max_items:
            payload = self._request_json(
                f"/member/{bioguide_id}/{endpoint}",
                {"format": "json", "limit": per_page, "offset": offset},
            )
            key = "sponsoredLegislation" if sponsorship == "sponsored" else "cosponsoredLegislation"
            items = payload.get(key, [])
            if not items:
                break
            for item in items:
                latest_action = item.get("latestAction") or {}
                if not isinstance(latest_action, dict):
                    latest_action = {}
                policy_area = item.get("policyArea") or {}
                if not isinstance(policy_area, dict):
                    policy_area = {}
                stage, weight = _derive_stage(latest_action.get("text", ""), sponsorship)
                number = item.get("number")
                bill_type = item.get("type") or item.get("amendmentType") or ""
                title = item.get("title") or "Untitled legislation"
                records.append(
                    BillRecord(
                        title=title,
                        bill_number=f"{bill_type} {number}".strip().upper(),
                        congress=int(item.get("congress", self.settings.current_congress)),
                        introduced_date=item.get("introducedDate"),
                        policy_area=(policy_area.get("name") or "Unspecified"),
                        latest_action_text=latest_action.get("text", ""),
                        latest_action_date=latest_action.get("actionDate"),
                        url=item.get("url"),
                        sponsorship=sponsorship,  # type: ignore[arg-type]
                        stage=stage,
                        stage_weight=weight,
                        impact_summary=summarize_bill_impact(
                            BillRecord(
                                title=title,
                                bill_number=f"{bill_type} {number}".strip().upper(),
                                congress=int(item.get("congress", self.settings.current_congress)),
                                introduced_date=item.get("introducedDate"),
                                policy_area=(policy_area.get("name") or "Unspecified"),
                                latest_action_text=latest_action.get("text", ""),
                                latest_action_date=latest_action.get("actionDate"),
                                url=item.get("url"),
                                sponsorship=sponsorship,  # type: ignore[arg-type]
                                stage=stage,
                                stage_weight=weight,
                            )
                        ),
                    )
                )
                if len(records) >= max_items:
                    break
            if len(items) < per_page:
                break
            offset += per_page
        return records

    def _normalize_member_summary(self, member: dict[str, Any]) -> dict[str, Any]:
        terms = member.get("terms", {}).get("item", []) if isinstance(member.get("terms"), dict) else member.get("terms", [])
        chamber = terms[-1].get("chamber", "Unknown") if terms else "Unknown"
        return {
            "bioguide_id": member["bioguideId"],
            "name": member.get("name") or member.get("directOrderName") or member.get("invertedOrderName"),
            "chamber": chamber,
            "state": member["state"],
            "district": member.get("district"),
            "party": _normalize_party(member.get("partyName")),
            "image_url": (member.get("depiction") or {}).get("imageUrl"),
            "image_fallback_url": _bioguide_photo_url(member["bioguideId"]),
            "website_url": member.get("officialWebsiteUrl"),
            "first_name": _parse_first_last(member.get("name") or "")[0],
            "last_name": _parse_first_last(member.get("name") or "")[1],
            "state_code": (terms[-1] or {}).get("stateCode") if terms else None,
            "terms": terms,
        }

    def _normalize_member_detail(self, member: dict[str, Any]) -> dict[str, Any]:
        party_history = member.get("partyHistory") or []
        current_party = party_history[-1]["partyName"] if party_history else None
        return {
            "bioguide_id": member["bioguideId"],
            "name": member.get("directOrderName") or member.get("invertedOrderName"),
            "chamber": (member.get("terms") or [{}])[-1].get("chamber", "Unknown"),
            "state": member.get("state"),
            "district": member.get("district"),
            "party": _normalize_party(current_party),
            "image_url": (member.get("depiction") or {}).get("imageUrl"),
            "image_fallback_url": _bioguide_photo_url(member["bioguideId"]),
            "website_url": member.get("officialWebsiteUrl"),
            "first_name": member.get("firstName"),
            "last_name": member.get("lastName"),
            "state_code": (member.get("terms") or [{}])[-1].get("stateCode"),
            "terms": member.get("terms"),
        }

    def _request_json(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        request_params = dict(params)
        request_params["api_key"] = self.settings.congress_api_key
        response = requests.get(
            f"{self.BASE_URL}{path}",
            params=request_params,
            timeout=self.settings.request_timeout_seconds,
        )
        response.raise_for_status()
        return response.json()

    def _fallback_members(self) -> list[dict[str, Any]]:
        response = requests.get(self.FALLBACK_MEMBERS_URL, timeout=self.settings.request_timeout_seconds)
        response.raise_for_status()
        current = yaml.safe_load(response.text)
        members: list[dict[str, Any]] = []
        for item in current:
            bioguide_id = item.get("id", {}).get("bioguide")
            if not bioguide_id:
                continue
            term = (item.get("terms") or [])[-1]
            chamber = "Senate" if term.get("type") == "sen" else "House of Representatives"
            state_code = term.get("state")
            state_name = STATE_NAMES.get(state_code, state_code)
            members.append(
                {
                    "bioguide_id": bioguide_id,
                    "name": item.get("name", {}).get("official_full") or f"{item.get('name', {}).get('first', '')} {item.get('name', {}).get('last', '')}".strip(),
                    "chamber": chamber,
                    "state": state_name,
                    "district": int(term["district"]) if term.get("district") else None,
                    "party": _normalize_party(term.get("party")),
                    "image_url": f"https://www.congress.gov/img/member/{bioguide_id.lower()}_200.jpg",
                    "image_fallback_url": _bioguide_photo_url(bioguide_id),
                    "website_url": term.get("url"),
                    "first_name": item.get("name", {}).get("first"),
                    "last_name": item.get("name", {}).get("last"),
                    "state_code": state_code,
                    "terms": [
                        {
                            "chamber": chamber,
                            "district": int(term["district"]) if term.get("district") else None,
                            "memberType": "Senator" if chamber == "Senate" else "Representative",
                            "startYear": int(str(term.get("start", ""))[:4]) if term.get("start") else None,
                            "endYear": int(str(term.get("end", ""))[:4]) if term.get("end") else None,
                            "stateCode": state_code,
                            "stateName": state_name,
                        }
                    ],
                }
            )
        return members

    def _fallback_member_detail(self, bioguide_id: str) -> dict[str, Any] | None:
        stored = self.db.get_official_payload(bioguide_id)
        if not stored:
            return None
        return {
            "bioguideId": bioguide_id,
            "detailReadiness": "seeded",
            "birthYear": None,
            "currentMember": True,
            "depiction": {"imageUrl": stored.get("image_url"), "attribution": "Congress.gov image"},
            "directOrderName": stored.get("name"),
            "invertedOrderName": f"{stored.get('last_name')}, {stored.get('first_name')}" if stored.get("last_name") else stored.get("name"),
            "firstName": stored.get("first_name"),
            "lastName": stored.get("last_name"),
            "district": stored.get("district"),
            "officialWebsiteUrl": stored.get("website_url"),
            "partyHistory": [{"partyName": _normalize_party(stored.get("party")), "partyAbbreviation": (stored.get("party") or "")[:1]}],
            "sponsoredLegislation": {"count": None, "url": None},
            "cosponsoredLegislation": {"count": None, "url": None},
            "state": stored.get("state"),
            "terms": stored.get("terms"),
            "updateDate": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        }


def _derive_stage(action_text: str, sponsorship: str) -> tuple[str, float]:
    text = action_text.lower()
    base = 1.0 if sponsorship == "sponsored" else 0.35
    if "became public law" in text or "signed by president" in text or "became law" in text:
        return "enacted", 14 * base
    if "passed senate" in text or "passed house" in text or "agreed to in senate" in text or "agreed to in house" in text:
        return "passed", 8 * base
    if "reported" in text or "ordered to be reported" in text or "placed on senate legislative calendar" in text:
        return "committee", 5 * base
    if "referred to the" in text or "committee on" in text:
        return "committee", 2 * base
    return "introduced", 1 * base


def _parse_first_last(name: str) -> tuple[str | None, str | None]:
    if "," in name:
        last, first = [part.strip() for part in name.split(",", 1)]
        return first or None, last or None
    parts = name.split()
    if not parts:
        return None, None
    return parts[0], parts[-1]


def _normalize_party(value: str | None) -> str | None:
    if not value:
        return value
    if value == "Democrat":
        return "Democratic"
    return value


def _bioguide_photo_url(bioguide_id: str) -> str:
    return f"https://bioguide.congress.gov/bioguide/photo/{bioguide_id[0].upper()}/{bioguide_id.upper()}.jpg"


STATE_NAMES = {
    "AK": "Alaska",
    "AL": "Alabama",
    "AR": "Arkansas",
    "AZ": "Arizona",
    "CA": "California",
    "CO": "Colorado",
    "CT": "Connecticut",
    "DC": "District of Columbia",
    "DE": "Delaware",
    "FL": "Florida",
    "GA": "Georgia",
    "HI": "Hawaii",
    "IA": "Iowa",
    "ID": "Idaho",
    "IL": "Illinois",
    "IN": "Indiana",
    "KS": "Kansas",
    "KY": "Kentucky",
    "LA": "Louisiana",
    "MA": "Massachusetts",
    "MD": "Maryland",
    "ME": "Maine",
    "MI": "Michigan",
    "MN": "Minnesota",
    "MO": "Missouri",
    "MS": "Mississippi",
    "MT": "Montana",
    "NC": "North Carolina",
    "ND": "North Dakota",
    "NE": "Nebraska",
    "NH": "New Hampshire",
    "NJ": "New Jersey",
    "NM": "New Mexico",
    "NV": "Nevada",
    "NY": "New York",
    "OH": "Ohio",
    "OK": "Oklahoma",
    "OR": "Oregon",
    "PA": "Pennsylvania",
    "RI": "Rhode Island",
    "SC": "South Carolina",
    "SD": "South Dakota",
    "TN": "Tennessee",
    "TX": "Texas",
    "UT": "Utah",
    "VA": "Virginia",
    "VT": "Vermont",
    "WA": "Washington",
    "WI": "Wisconsin",
    "WV": "West Virginia",
    "WY": "Wyoming",
}
