from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
from typing import Any

import requests

from app.db import Database
from app.models import DirectoryMetric, DonorRecipient, DonorRecord, FinanceSummary, PacAuditTrail, StateContribution
from app.settings import get_settings


class FECService:
    BASE_URL = "https://api.open.fec.gov/v1"

    def __init__(self, db: Database | None = None) -> None:
        self.settings = get_settings()
        self.db = db or Database()

    def build_finance_snapshot(self, member: dict[str, Any], force: bool = False) -> FinanceSummary:
        bioguide_id = member["bioguideId"]
        cached = self.db.load_snapshot("finance", bioguide_id)
        if cached and not force:
            payload, fetched_at = cached
            if datetime.now(timezone.utc) - fetched_at < timedelta(hours=self.settings.finance_cache_hours):
                return FinanceSummary.model_validate(payload)

        try:
            summary = self._build_snapshot(member)
        except requests.RequestException as exc:
            if cached:
                payload, _ = cached
                summary = FinanceSummary.model_validate(payload)
                summary.warning = f"Showing cached finance data because the latest refresh failed: {exc}"
            else:
                summary = self._partial_finance_summary(member, str(exc))

        self.db.save_snapshot("finance", bioguide_id, summary.model_dump(mode="json"))
        return summary

    def _build_snapshot(self, member: dict[str, Any]) -> FinanceSummary:
        candidate = self._match_candidate(member)
        if not candidate:
            return FinanceSummary(available=False, warning="No active FEC candidate filing was matched for this official.")

        totals_payload = self._request_json(f"/candidate/{candidate['candidate_id']}/totals/", {"cycle": self.settings.default_cycle})
        totals = (totals_payload.get("results") or [{}])[0]
        principal_committee = next(
            (committee for committee in candidate.get("principal_committees", []) if committee.get("designation") == "P"),
            (candidate.get("principal_committees") or [{}])[0],
        )
        committee_id = principal_committee.get("committee_id")

        donor_states = self._safe_state_breakdown(committee_id)
        top_donors = self._safe_top_donors(committee_id, individual_only=True)
        top_pac_donors = self._safe_top_pac_donors(committee_id)
        pac_trails = self._safe_pac_audit_trails(top_pac_donors)

        total_raised = float(totals.get("contributions") or 0)
        pac_contributions = float(totals.get("pac_contributions") or 0)
        individual_contributions = float(totals.get("individual_contributions") or 0)
        transfer_contributions = float(totals.get("transfers_from_other_authorized_committee") or 0)

        constituent_share = None
        if donor_states and total_raised:
            home_state = member.get("state")
            home_total = sum(item.amount for item in donor_states if item.state == home_state)
            constituent_share = round(home_total / total_raised, 3)
        pac_share = round(pac_contributions / total_raised, 3) if total_raised else None
        itemized_share = round(float(totals.get("individual_itemized_contributions") or 0) / individual_contributions, 3) if individual_contributions else None

        notes = []
        if self.settings.fec_api_key == "DEMO_KEY":
            notes.append("FEC data is running on DEMO_KEY; richer PAC tracing needs a personal API key for routine use.")
        if donor_states:
            notes.append("Constituent share is estimated using in-state donations as a proxy for district/state constituency.")

        return FinanceSummary(
            available=True,
            candidate_id=candidate["candidate_id"],
            principal_committee_id=committee_id,
            principal_committee_name=principal_committee.get("name"),
            cycle=self.settings.default_cycle,
            total_raised=total_raised,
            cash_on_hand=float(totals.get("last_cash_on_hand_end_period") or 0),
            disbursements=float(totals.get("disbursements") or 0),
            individual_contributions=individual_contributions,
            pac_contributions=pac_contributions,
            transfer_contributions=transfer_contributions,
            constituent_share=constituent_share,
            pac_share=pac_share,
            itemized_share=itemized_share,
            donor_state_totals=donor_states,
            top_donors=top_donors,
            top_pac_donors=top_pac_donors,
            pac_audit_trails=pac_trails,
            notes=notes,
        )

    def sync_directory_finance_metrics(self, force: bool = False) -> None:
        meta_key = "directory_finance_last_sync"
        last_sync = self.db.get_meta(meta_key)
        if not force and last_sync:
            synced_at = datetime.fromisoformat(last_sync)
            if datetime.now(timezone.utc) - synced_at < timedelta(hours=self.settings.finance_cache_hours):
                return

        officials = self.db.list_official_payloads()
        lookup = _build_official_lookup(officials)
        office_state_pairs = sorted(
            {
                (
                    "S" if (official.get("terms") or [{}])[-1].get("chamber") == "Senate" else "H",
                    (official.get("terms") or [{}])[-1].get("stateCode") or official.get("state_code"),
                )
                for official in officials
                if (official.get("terms") or [{}])[-1].get("stateCode") or official.get("state_code")
            }
        )
        for office, state_code in office_state_pairs:
            page = 1
            while True:
                try:
                    payload = self._request_json(
                        "/candidates/totals/",
                        {
                            "office": office,
                            "state": state_code,
                            "cycle": self.settings.default_cycle,
                            "is_active_candidate": "true",
                            "per_page": 100,
                            "page": page,
                        },
                    )
                except requests.RequestException:
                    self.db.set_meta(meta_key, datetime.now(timezone.utc).replace(microsecond=0).isoformat())
                    return
                results = payload.get("results", [])
                for item in results:
                    bioguide_id = _match_candidate_totals_row(item, lookup)
                    if not bioguide_id:
                        continue
                    existing = self._load_directory_metric(bioguide_id)
                    metric = existing or DirectoryMetric()
                    total_raised = float(item.get("receipts") or item.get("contributions") or 0)
                    pac_component = float(item.get("other_political_committee_contributions") or 0)
                    metric.finance_available = True
                    metric.candidate_id = item.get("candidate_id")
                    metric.total_raised = total_raised
                    metric.cash_on_hand = float(item.get("cash_on_hand_end_period") or 0)
                    metric.pac_share = round(pac_component / total_raised, 3) if total_raised else None
                    self.db.save_snapshot("directory_metric", bioguide_id, metric.model_dump(mode="json"))
                pagination = payload.get("pagination") or {}
                if page >= int(pagination.get("pages") or 0) or not results:
                    break
                page += 1

        self.db.set_meta(meta_key, datetime.now(timezone.utc).replace(microsecond=0).isoformat())

    def ensure_card_finance_summary(
        self,
        member: dict[str, Any],
        force: bool = False,
        allow_search: bool = True,
    ) -> DirectoryMetric:
        bioguide_id = member["bioguideId"]
        metric = self._load_directory_metric(bioguide_id) or DirectoryMetric()
        if metric.top_donor_names and not force:
            return metric

        if not metric.candidate_id and allow_search:
            candidate = self._match_candidate(member)
            if candidate:
                metric.candidate_id = candidate.get("candidate_id")
                principal = next(
                    (committee for committee in candidate.get("principal_committees", []) if committee.get("designation") == "P"),
                    (candidate.get("principal_committees") or [{}])[0],
                )
                metric.principal_committee_id = principal.get("committee_id")
        committee_id = metric.principal_committee_id
        if not committee_id:
            if metric.candidate_id:
                try:
                    committees_payload = self._request_json(
                        f"/candidate/{metric.candidate_id}/committees/",
                        {"cycle": self.settings.default_cycle},
                    )
                    committees = committees_payload.get("results", [])
                    principal = next(
                        (committee for committee in committees if committee.get("designation") == "P"),
                        committees[0] if committees else {},
                    )
                    committee_id = principal.get("committee_id")
                    metric.principal_committee_id = committee_id
                except requests.RequestException:
                    committee_id = None
            if not committee_id and allow_search:
                candidate = self._match_candidate(member)
                if candidate:
                    principal = next(
                        (committee for committee in candidate.get("principal_committees", []) if committee.get("designation") == "P"),
                        (candidate.get("principal_committees") or [{}])[0],
                    )
                    committee_id = principal.get("committee_id")
                    metric.principal_committee_id = committee_id
        if committee_id:
            donors = self._safe_top_donors(committee_id, individual_only=False)
            unique_names: list[str] = []
            for donor in donors:
                if donor.name not in unique_names:
                    unique_names.append(donor.name)
                if len(unique_names) == 3:
                    break
            metric.top_donor_names = unique_names

        self.db.save_snapshot("directory_metric", bioguide_id, metric.model_dump(mode="json"))
        return metric

    def _load_directory_metric(self, bioguide_id: str) -> DirectoryMetric | None:
        cached = self.db.load_snapshot("directory_metric", bioguide_id)
        if not cached:
            return None
        payload, _ = cached
        return DirectoryMetric.model_validate(payload)

    def _partial_finance_summary(self, member: dict[str, Any], error_text: str) -> FinanceSummary:
        metric = self._load_directory_metric(member["bioguideId"])
        donor_names = metric.top_donor_names if metric else []
        donors = [
            DonorRecord(name=name, amount=0.0, donor_type="Cached directory summary")
            for name in donor_names
        ]
        available = bool(metric and (metric.total_raised is not None or metric.cash_on_hand is not None or donor_names))
        notes = ["Directory-level finance cache is being shown because a live FEC refresh was unavailable."]
        if self.settings.fec_api_key == "DEMO_KEY":
            notes.append("Provide a personal data.gov key in FEC_API_KEY for higher throughput.")
        return FinanceSummary(
            available=available,
            warning=f"Live finance refresh failed: {error_text}",
            candidate_id=metric.candidate_id if metric else None,
            principal_committee_id=metric.principal_committee_id if metric else None,
            cycle=self.settings.default_cycle,
            total_raised=metric.total_raised or 0.0 if metric else 0.0,
            cash_on_hand=metric.cash_on_hand or 0.0 if metric else 0.0,
            pac_share=metric.pac_share if metric else None,
            top_donors=donors,
            notes=notes,
        )

    def _match_candidate(self, member: dict[str, Any]) -> dict[str, Any] | None:
        cache_key = member["bioguideId"]
        cached = self.db.load_snapshot("candidate_match", cache_key)
        if cached:
            return cached[0]

        office = "S" if (member.get("terms") or [{}])[-1].get("chamber") == "Senate" else "H"
        state_code = (member.get("terms") or [{}])[-1].get("stateCode")
        queries = _candidate_queries(member)
        results: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        for query in queries:
            payload = self._request_json(
                "/candidates/search/",
                {
                    "q": query,
                    "office": office,
                    "state": state_code,
                    "per_page": 8,
                    "is_active_candidate": "true",
                },
            )
            for candidate in payload.get("results", []):
                candidate_id = candidate.get("candidate_id")
                if candidate_id and candidate_id not in seen_ids:
                    seen_ids.add(candidate_id)
                    results.append(candidate)
            if results:
                break
        chosen = _pick_best_candidate(member, results)
        if chosen:
            self.db.save_snapshot("candidate_match", cache_key, chosen)
        return chosen

    def _safe_state_breakdown(self, committee_id: str | None) -> list[StateContribution]:
        if not committee_id:
            return []
        try:
            payload = self._request_json(
                "/schedules/schedule_a/by_state/",
                {
                    "committee_id": committee_id,
                    "two_year_transaction_period": self.settings.default_cycle,
                    "sort": "-total",
                    "per_page": 8,
                },
            )
        except requests.RequestException:
            return []
        states: list[StateContribution] = []
        for item in payload.get("results", []):
            state = item.get("state") or item.get("contributor_state")
            amount = item.get("total") or item.get("total_amount") or item.get("contribution_receipt_amount")
            if state and amount:
                states.append(StateContribution(state=state, amount=float(amount)))
        return states

    def _safe_top_donors(self, committee_id: str | None, individual_only: bool = False) -> list[DonorRecord]:
        if not committee_id:
            return []
        params: dict[str, Any] = {
            "committee_id": committee_id,
            "two_year_transaction_period": self.settings.default_cycle,
            "per_page": 12,
            "sort": "-contribution_receipt_amount",
        }
        if individual_only:
            params["is_individual"] = "true"
        try:
            payload = self._request_json("/schedules/schedule_a/", params)
        except requests.RequestException:
            return []
        donors: list[DonorRecord] = []
        for item in payload.get("results", []):
            donors.append(
                DonorRecord(
                    name=item.get("contributor_name") or "Unknown donor",
                    amount=float(item.get("contribution_receipt_amount") or 0),
                    donor_type=item.get("entity_type_desc") or ("Individual" if item.get("is_individual") else "Committee"),
                    city=item.get("contributor_city"),
                    state=item.get("contributor_state"),
                    employer=item.get("contributor_employer"),
                    occupation=item.get("contributor_occupation"),
                    contributor_id=(item.get("contributor") or {}).get("contributor_id") or item.get("contributor_id"),
                    source_url=item.get("pdf_url"),
                    other_recipients=self._safe_other_recipients(item.get("contributor_name")),
                )
            )
        return donors

    def _safe_top_pac_donors(self, committee_id: str | None) -> list[DonorRecord]:
        if not committee_id:
            return []
        try:
            payload = self._request_json(
                "/schedules/schedule_a/by_contributor/",
                {
                    "committee_id": committee_id,
                    "two_year_transaction_period": self.settings.default_cycle,
                    "sort": "-total",
                    "per_page": 8,
                },
            )
        except requests.RequestException:
            return []
        donors: list[DonorRecord] = []
        for item in payload.get("results", []):
            amount = item.get("total") or item.get("total_amount") or item.get("contribution_receipt_amount") or 0
            contributor = item.get("contributor") or {}
            donor_name = item.get("contributor_name") or contributor.get("name") or item.get("name")
            if donor_name:
                donors.append(
                    DonorRecord(
                        name=donor_name,
                        amount=float(amount),
                        donor_type=contributor.get("committee_type_full") or "Committee/PAC",
                        contributor_id=contributor.get("committee_id") or item.get("contributor_id"),
                    )
                )
        return donors

    def _safe_pac_audit_trails(self, donors: list[DonorRecord]) -> list[PacAuditTrail]:
        trails: list[PacAuditTrail] = []
        for donor in donors[:3]:
            committee_id = donor.contributor_id
            if not committee_id:
                continue
            trails.append(
                PacAuditTrail(
                    pac_name=donor.name,
                    pac_committee_id=committee_id,
                    amount_to_official=donor.amount,
                    inbound_sources=self._safe_top_donors(committee_id)[:4],
                    outbound_targets=self._safe_committee_disbursements(committee_id),
                )
            )
        return trails

    def _safe_committee_disbursements(self, committee_id: str) -> list[DonorRecipient]:
        try:
            payload = self._request_json(
                "/schedules/schedule_b/",
                {
                    "committee_id": committee_id,
                    "two_year_transaction_period": self.settings.default_cycle,
                    "sort": "-disbursement_amount",
                    "per_page": 5,
                },
            )
        except requests.RequestException:
            return []
        recipients: list[DonorRecipient] = []
        for item in payload.get("results", []):
            recipients.append(
                DonorRecipient(
                    name=item.get("recipient_name") or item.get("payee_name") or "Unknown recipient",
                    amount=float(item.get("disbursement_amount") or 0),
                    recipient=item.get("recipient_name"),
                    candidate_name=item.get("candidate_name"),
                    committee_id=item.get("committee_id"),
                )
            )
        return recipients

    def _safe_other_recipients(self, contributor_name: str | None) -> list[DonorRecipient]:
        if not contributor_name or self.settings.fec_api_key == "DEMO_KEY":
            return []
        try:
            payload = self._request_json(
                "/schedules/schedule_a/",
                {
                    "contributor_name": contributor_name,
                    "two_year_transaction_period": self.settings.default_cycle,
                    "sort": "-contribution_receipt_amount",
                    "per_page": 5,
                },
            )
        except requests.RequestException:
            return []
        recipients: list[DonorRecipient] = []
        for item in payload.get("results", []):
            committee = item.get("committee") or {}
            recipients.append(
                DonorRecipient(
                    name=committee.get("name") or item.get("committee_name") or "Unknown committee",
                    amount=float(item.get("contribution_receipt_amount") or 0),
                    recipient=committee.get("name") or item.get("committee_name"),
                    candidate_name=item.get("candidate_name"),
                    committee_id=committee.get("committee_id"),
                )
            )
        return recipients

    def _request_json(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        request_params = dict(params)
        request_params["api_key"] = self.settings.fec_api_key
        response = requests.get(f"{self.BASE_URL}{path}", params=request_params, timeout=self.settings.request_timeout_seconds)
        response.raise_for_status()
        return response.json()


def _pick_best_candidate(member: dict[str, Any], results: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not results:
        return None
    state_code = (member.get("terms") or [{}])[-1].get("stateCode")
    district = str(member.get("district") or 0).zfill(2)
    office = "S" if (member.get("terms") or [{}])[-1].get("chamber") == "Senate" else "H"
    member_first = _normalize_name_token(member.get("firstName") or "")
    member_last = _normalize_name_token(member.get("lastName") or "")

    def score(candidate: dict[str, Any]) -> tuple[int, int, int, int, int, int]:
        candidate_first, candidate_last = _candidate_name_parts(candidate.get("name") or "")
        return (
            1 if candidate.get("office") == office else 0,
            1 if candidate.get("state") == state_code else 0,
            1 if office == "S" or candidate.get("district") == district else 0,
            1 if candidate_last == member_last else 0,
            1 if candidate_first == member_first or candidate_first.startswith(member_first) or member_first.startswith(candidate_first) else 0,
            1 if candidate.get("has_raised_funds") else 0,
        )

    return sorted(results, key=score, reverse=True)[0]


def _candidate_queries(member: dict[str, Any]) -> list[str]:
    direct = str(member.get("directOrderName") or "").strip()
    first = str(member.get("firstName") or "").strip()
    last = str(member.get("lastName") or "").strip()
    queries = [query for query in [last, f"{first} {last}".strip(), direct] if query]
    unique: list[str] = []
    for query in queries:
        cleaned = re.sub(r"[^\w\s-]", "", query)
        if cleaned and cleaned not in unique:
            unique.append(cleaned)
    return unique


def _build_official_lookup(officials: list[dict[str, Any]]) -> dict[tuple[str, str, str, str, str], str]:
    lookup: dict[tuple[str, str, str, str, str], str] = {}
    for official in officials:
        terms = official.get("terms") or [{}]
        latest = terms[-1]
        office = "S" if latest.get("chamber") == "Senate" else "H"
        state_code = latest.get("stateCode") or official.get("state_code") or ""
        district = str(official.get("district") or 0).zfill(2)
        first = _normalize_name_token(official.get("first_name") or "")
        last = _normalize_name_token(official.get("last_name") or "")
        if last:
            lookup[(office, state_code, district, last, first)] = official["bioguide_id"]
    return lookup


def _match_candidate_totals_row(item: dict[str, Any], lookup: dict[tuple[str, str, str, str, str], str]) -> str | None:
    office = item.get("office") or ""
    state = item.get("state") or ""
    district = str(item.get("district") or 0).zfill(2)
    first, last = _candidate_name_parts(item.get("name") or "")
    candidates = [
        lookup.get((office, state, district, last, first)),
        lookup.get((office, state, district, last, "")),
        lookup.get((office, state, "00", last, first)),
        lookup.get((office, state, "00", last, "")),
    ]
    return next((candidate for candidate in candidates if candidate), None)


TITLE_TOKENS = {"mr", "mrs", "ms", "dr", "jr", "sr", "ii", "iii", "iv", "hon"}


def _candidate_name_parts(name: str) -> tuple[str, str]:
    if "," in name:
        last_raw, rest = [part.strip() for part in name.split(",", 1)]
    else:
        parts = name.split()
        if len(parts) < 2:
            return "", _normalize_name_token(name)
        rest = " ".join(parts[:-1])
        last_raw = parts[-1]
    rest_tokens = [_normalize_name_token(token) for token in rest.split()]
    rest_tokens = [token for token in rest_tokens if token and token not in TITLE_TOKENS and len(token) > 1]
    first = rest_tokens[0] if rest_tokens else ""
    last = _normalize_name_token(last_raw)
    return first, last


def _normalize_name_token(value: str) -> str:
    return re.sub(r"[^a-z]", "", value.lower())
