from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from app.db import Database
from app.models import DonorRecipient, DonorRecord, FinanceSummary, PacAuditTrail, StateContribution
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
            summary = FinanceSummary(
                available=False,
                warning=f"Finance refresh hit the FEC API limit or returned an error: {exc}",
                notes=[
                    "Provide a personal data.gov key in FEC_API_KEY for higher throughput.",
                    "The public DEMO_KEY is capped at 40 calls/hour according to FEC error responses.",
                ],
            )

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

    def _match_candidate(self, member: dict[str, Any]) -> dict[str, Any] | None:
        cache_key = member["bioguideId"]
        cached = self.db.load_snapshot("candidate_match", cache_key)
        if cached:
            return cached[0]

        office = "S" if (member.get("terms") or [{}])[-1].get("chamber") == "Senate" else "H"
        q = member.get("directOrderName") or member.get("invertedOrderName") or ""
        payload = self._request_json(
            "/candidates/search/",
            {
                "q": q,
                "office": office,
                "state": (member.get("terms") or [{}])[-1].get("stateCode"),
                "per_page": 6,
                "is_active_candidate": "true",
            },
        )
        results = payload.get("results", [])
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
    expected_last_name = str(member.get("lastName") or "").lower()

    def score(candidate: dict[str, Any]) -> tuple[int, int, int, int]:
        return (
            1 if candidate.get("office") == office else 0,
            1 if candidate.get("state") == state_code else 0,
            1 if office == "S" or candidate.get("district") == district else 0,
            1 if expected_last_name and expected_last_name in str(candidate.get("name") or "").lower() else 0,
        )

    return sorted(results, key=score, reverse=True)[0]
