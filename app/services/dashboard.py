from __future__ import annotations

from app.db import Database
from app.models import DirectoryMetric, OfficialCard, OfficialDetail
from app.services.congress import CongressService
from app.services.fec import FECService
from app.services.promises import PromiseService
from app.services.scoring import compute_delivery_score


class DashboardService:
    def __init__(self, db: Database | None = None) -> None:
        self.db = db or Database()
        self.congress = CongressService(self.db)
        self.fec = FECService(self.db)
        self.promises = PromiseService(self.db)

    def list_officials(
        self,
        search: str | None = None,
        chamber: str | None = None,
        party: str | None = None,
        state: str | None = None,
        sort_by: str = "name",
        force_sync: bool = False,
    ):
        self.congress.ensure_current_members(force=force_sync)
        try:
            self.fec.sync_directory_finance_metrics(force=force_sync)
        except Exception:
            pass
        cards = self.db.list_officials(search=search, chamber=chamber, party=party, state=state)
        enriched = [self._enrich_card(card) for card in cards]
        return sorted(enriched, key=lambda card: _sort_key(card, sort_by))

    def warm_directory_cards(self, cards: list[OfficialCard], force_refresh: bool = False) -> list[OfficialCard]:
        warmed: list[OfficialCard] = []
        for card in cards:
            member = self.congress.get_member_detail(card.bioguide_id, force=force_refresh)
            metric = self._load_metric(card.bioguide_id) or DirectoryMetric()
            metric = self._ensure_efficiency_metric(card.bioguide_id, member, metric, force_refresh=force_refresh, full=False)
            warmed.append(self._apply_metric(card, metric))
        return warmed

    def get_official_detail(self, bioguide_id: str, force_refresh: bool = False) -> OfficialDetail:
        self.congress.ensure_current_members()
        member = self.congress.get_member_detail(bioguide_id, force=force_refresh)
        card = self.db.get_official_card(bioguide_id)
        if not card:
            raise KeyError(bioguide_id)

        activity = self.congress.build_activity_snapshot(bioguide_id, force=force_refresh)
        promises = self.promises.get_promises(member, force=force_refresh)
        finance = self.fec.build_finance_snapshot(member, force=force_refresh)
        delivery_score = compute_delivery_score(promises, activity)
        metric = self._load_metric(bioguide_id) or DirectoryMetric()
        metric.finance_available = finance.available
        metric.candidate_id = finance.candidate_id or metric.candidate_id
        metric.principal_committee_id = finance.principal_committee_id or metric.principal_committee_id
        metric.total_raised = finance.total_raised or metric.total_raised
        metric.cash_on_hand = finance.cash_on_hand or metric.cash_on_hand
        metric.pac_share = finance.pac_share if finance.pac_share is not None else metric.pac_share
        metric.top_donor_names = list(dict.fromkeys([donor.name for donor in finance.top_donors]))[:3] or metric.top_donor_names
        metric = self._ensure_efficiency_metric(bioguide_id, member, metric, force_refresh=force_refresh, full=True)
        metric.priority_commitment_score = delivery_score.overall_score
        if metric.pac_share is not None:
            metric.pac_alignment_signal = round((metric.pac_share * 100) * ((100 - delivery_score.overall_score) / 100))
        self.db.save_snapshot("directory_metric", bioguide_id, metric.model_dump(mode="json"))
        card = self._apply_metric(card, metric)

        return OfficialDetail(
            member=member,
            card=card,
            activity=activity,
            finance=finance,
            promises=promises,
            delivery_score=delivery_score,
            methodology_notes=[
                "Finance data comes from OpenFEC and legislative activity comes from Congress.gov.",
                "Campaign-platform coverage is strongest when manual promise curation is supplied; otherwise the app infers priority topics from official website language.",
                "This dashboard surfaces funding patterns and legislative activity; it does not assert causation between donors and policy outcomes.",
            ],
        )

    def sync_directory_efficiency_metrics(
        self,
        force_refresh: bool = False,
        limit: int | None = None,
        full: bool = False,
    ) -> None:
        self.congress.ensure_current_members(force=force_refresh)
        payloads = self.db.list_official_payloads()
        count = 0
        for payload in payloads:
            bioguide_id = payload["bioguide_id"]
            metric = self._load_metric(bioguide_id)
            if metric and metric.efficiency_score is not None and (metric.priority_commitment_score is not None or not full) and not force_refresh:
                continue
            member = self.congress.get_member_detail(bioguide_id, force=force_refresh)
            self._ensure_efficiency_metric(bioguide_id, member, metric, force_refresh=force_refresh, full=full)
            count += 1
            if limit and count >= limit:
                break

    def _enrich_card(self, card: OfficialCard) -> OfficialCard:
        metric = self._load_metric(card.bioguide_id)
        return self._apply_metric(card, metric)

    def _load_metric(self, bioguide_id: str) -> DirectoryMetric | None:
        cached = self.db.load_snapshot("directory_metric", bioguide_id)
        if not cached:
            return None
        payload, _ = cached
        return DirectoryMetric.model_validate(payload)

    def _apply_metric(self, card: OfficialCard, metric: DirectoryMetric | None) -> OfficialCard:
        if not metric:
            return card
        return card.model_copy(
            update={
                "total_raised": metric.total_raised,
                "cash_on_hand": metric.cash_on_hand,
                "top_donor_names": metric.top_donor_names,
                "efficiency_score": metric.efficiency_score,
                "priority_commitment_score": metric.priority_commitment_score,
                "pac_alignment_signal": metric.pac_alignment_signal,
                "pac_share": metric.pac_share,
                "finance_available": metric.finance_available,
            }
        )

    def _ensure_efficiency_metric(
        self,
        bioguide_id: str,
        member: dict,
        metric: DirectoryMetric | None = None,
        force_refresh: bool = False,
        full: bool = False,
    ) -> DirectoryMetric:
        metric = metric or self._load_metric(bioguide_id) or DirectoryMetric()
        if metric.efficiency_score is not None and (metric.priority_commitment_score is not None or not full) and not force_refresh:
            return metric

        sponsored = (member.get("sponsoredLegislation") or {}).get("count", 0)
        cosponsored = (member.get("cosponsoredLegislation") or {}).get("count", 0)
        terms = member.get("terms") or []
        first_start = terms[0].get("startYear") if terms else None
        current_start = terms[-1].get("startYear") if terms else None
        years_in_office = max(1, 2026 - int(first_start or current_start or 2026) + 1)
        throughput = (sponsored * 1.8 + cosponsored * 0.35) / years_in_office
        efficiency = min(100, round(min(72, throughput)))
        metric.efficiency_score = efficiency
        metric.years_in_office = years_in_office
        if metric.priority_commitment_score is None or force_refresh:
            metric.priority_commitment_score = max(0, min(100, round(efficiency * 0.82)))

        if full:
            try:
                activity = self.congress.build_activity_snapshot(bioguide_id, force=force_refresh)
                promises = self.promises.get_promises(member, force=force_refresh)
                delivery = compute_delivery_score(promises, activity)
                metric.priority_commitment_score = delivery.overall_score
                advancement_bonus = min(18, activity.passed_count * 3 + activity.enacted_count * 8)
                metric.efficiency_score = min(100, round(max(metric.efficiency_score or 0, efficiency + advancement_bonus)))
            except Exception:
                pass

        if metric.pac_share is not None:
            commitment = metric.priority_commitment_score if metric.priority_commitment_score is not None else metric.efficiency_score or 0
            metric.pac_alignment_signal = round((metric.pac_share * 100) * ((100 - commitment) / 100))

        self.db.save_snapshot("directory_metric", bioguide_id, metric.model_dump(mode="json"))
        return metric


def _sort_key(card: OfficialCard, sort_by: str):
    if sort_by == "money_desc":
        return (-(card.total_raised or -1), card.name)
    if sort_by == "efficiency_asc":
        return (card.efficiency_score is None, card.efficiency_score or 10_000, card.name)
    if sort_by == "commitment_asc":
        return (card.priority_commitment_score is None, card.priority_commitment_score or 10_000, card.name)
    if sort_by == "pac_alignment_desc":
        return (-(card.pac_alignment_signal or -1), card.name)
    return (card.name,)
