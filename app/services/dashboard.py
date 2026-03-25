from __future__ import annotations

from app.db import Database, utc_now_iso
from app.models import ActivitySummary, DeliveryScore, DirectoryMetric, FinanceSummary, OfficialCard, OfficialDetail, PromiseItem
from app.services.congress import CongressService
from app.services.fec import FECService
from app.services.promises import PromiseService
from app.services.scoring import compute_delivery_score, compute_keeps_promises_score, compute_truth_verdict


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
        cards = self.db.list_officials(search=search, chamber=chamber, party=party, state=state)
        metrics = {
            key: DirectoryMetric.model_validate(payload)
            for key, (payload, _) in self.db.list_namespace_snapshots("directory_metric").items()
        }
        enriched = [self._apply_metric(card, metrics.get(card.bioguide_id)) for card in cards]
        return sorted(enriched, key=lambda card: _sort_key(card, sort_by))

    def warm_directory_cards(self, cards: list[OfficialCard], force_refresh: bool = False) -> list[OfficialCard]:
        return cards

    def get_official_detail(self, bioguide_id: str, force_refresh: bool = False) -> OfficialDetail:
        if force_refresh:
            return self.refresh_official_detail(bioguide_id)

        cached = self._load_detail_snapshot(bioguide_id)
        if cached:
            return cached
        return self._build_detail_from_cached_data(bioguide_id)

    def refresh_official_detail(self, bioguide_id: str, force_live: bool = True) -> OfficialDetail:
        member = self.congress.load_cached_member_detail(bioguide_id) or self.congress.get_member_detail(bioguide_id, force=force_live)
        card = self.db.get_official_card(bioguide_id)
        if not card:
            self.congress.ensure_current_members(force=True)
            card = self.db.get_official_card(bioguide_id)
            if not card:
                raise KeyError(bioguide_id)

        activity = self.congress.build_activity_snapshot(bioguide_id, force=force_live)
        cached_promises = self.promises.load_cached_promises(bioguide_id)
        promises = self.promises.get_promises(member, force=force_live or not cached_promises)
        finance = self.fec.build_finance_snapshot(member, force=force_live)
        return self._store_detail_snapshot(card, member, activity, promises, finance, persist=True)

    def refresh_all_precomputed_data(self, limit: int | None = None) -> dict[str, int]:
        self.congress.ensure_current_members(force=True)
        self.fec.sync_directory_finance_metrics(force=True)
        processed = 0
        failed = 0
        payloads = self.db.list_official_payloads()
        if limit:
            payloads = payloads[:limit]
        for payload in payloads:
            bioguide_id = payload["bioguide_id"]
            try:
                self.refresh_official_detail(bioguide_id, force_live=False)
                processed += 1
            except Exception:
                failed += 1
        self.db.set_meta("precomputed_refresh_at", utc_now_iso())
        return {"processed": processed, "failed": failed}

    def sync_directory_efficiency_metrics(
        self,
        force_refresh: bool = False,
        limit: int | None = None,
        full: bool = False,
    ) -> None:
        payloads = self.db.list_official_payloads()
        count = 0
        for payload in payloads:
            bioguide_id = payload["bioguide_id"]
            metric = self._load_metric(bioguide_id)
            if metric and metric.efficiency_score is not None and ((metric.keeps_promises_score is not None and metric.delivery_score is not None) or not full) and not force_refresh:
                continue
            member = self.congress.load_cached_member_detail(bioguide_id)
            if not member:
                continue
            activity = self.congress.load_cached_activity_snapshot(bioguide_id)
            promises = self.promises.load_cached_promises(bioguide_id) or []
            delivery = compute_delivery_score(promises, activity or ActivitySummary())
            keeps_promises = compute_keeps_promises_score(promises, activity or ActivitySummary())
            self._ensure_efficiency_metric(
                bioguide_id,
                member,
                metric,
                force_refresh=force_refresh,
                full=full,
                activity=activity,
                promises=promises,
                delivery_score=delivery,
                keeps_promises_score=keeps_promises,
            )
            count += 1
            if limit and count >= limit:
                break

    def _build_detail_from_cached_data(self, bioguide_id: str) -> OfficialDetail:
        member = self.congress.load_cached_member_detail(bioguide_id)
        card = self.db.get_official_card(bioguide_id)
        if not member or not card:
            raise KeyError(bioguide_id)

        activity = self.congress.load_cached_activity_snapshot(bioguide_id) or self.congress.build_lightweight_activity_snapshot(
            member,
            note="Detailed bill movement will appear after the next scheduled refresh.",
        )
        promises = self.promises.load_cached_promises(bioguide_id) or []
        finance = self.fec.load_cached_finance_snapshot(bioguide_id) or self.fec._partial_finance_summary(member, "")
        return self._store_detail_snapshot(card, member, activity, promises, finance, persist=False)

    def _store_detail_snapshot(
        self,
        card: OfficialCard,
        member: dict,
        activity: ActivitySummary,
        promises: list[PromiseItem],
        finance: FinanceSummary,
        persist: bool,
    ) -> OfficialDetail:
        delivery_score = compute_delivery_score(promises, activity)
        keeps_promises_score = compute_keeps_promises_score(promises, activity)
        metric = self._load_metric(card.bioguide_id) or DirectoryMetric()
        metric.finance_available = finance.available or metric.finance_available
        metric.candidate_id = finance.candidate_id or metric.candidate_id
        metric.principal_committee_id = finance.principal_committee_id or metric.principal_committee_id
        if finance.total_raised or metric.total_raised is None:
            metric.total_raised = finance.total_raised
        if finance.cash_on_hand or metric.cash_on_hand is None:
            metric.cash_on_hand = finance.cash_on_hand
        metric.pac_share = finance.pac_share if finance.pac_share is not None else metric.pac_share
        metric.top_donor_names = list(dict.fromkeys([donor.name for donor in finance.top_donors]))[:3] or metric.top_donor_names
        metric = self._ensure_efficiency_metric(
            card.bioguide_id,
            member,
            metric,
            force_refresh=True,
            full=True,
            activity=activity,
            promises=promises,
            delivery_score=delivery_score,
            keeps_promises_score=keeps_promises_score,
            persist=persist,
        )
        truth_verdict, truth_badge_variant = compute_truth_verdict(keeps_promises_score, delivery_score.overall_score)
        metric.delivery_score = delivery_score.overall_score
        metric.keeps_promises_score = keeps_promises_score
        metric.truth_verdict = truth_verdict
        metric.truth_badge_variant = truth_badge_variant
        if persist:
            metric.last_refreshed_at = utc_now_iso()
        metric.priority_commitment_score = keeps_promises_score
        if metric.pac_share is not None:
            metric.pac_alignment_signal = round((metric.pac_share * 100) * ((100 - keeps_promises_score) / 100))
        if persist:
            self.db.save_snapshot("directory_metric", card.bioguide_id, metric.model_dump(mode="json"))

        enriched_card = self._apply_metric(card, metric)
        detail = OfficialDetail(
            member=member,
            card=enriched_card,
            activity=activity,
            finance=finance,
            promises=promises,
            delivery_score=delivery_score,
            methodology_notes=[
                "Finance data comes from OpenFEC and legislative activity comes from Congress.gov.",
                "Issue priorities are strongest when they come from curated campaign-platform entries. Otherwise they are inferred from official website language.",
                "This dashboard shows funding patterns and visible activity side by side, but it does not claim donor money directly caused a policy result.",
            ],
        )
        if persist:
            self.db.save_snapshot("official_detail", card.bioguide_id, detail.model_dump(mode="json"))
        return detail

    def _load_detail_snapshot(self, bioguide_id: str) -> OfficialDetail | None:
        cached = self.db.load_snapshot("official_detail", bioguide_id)
        if not cached:
            return None
        payload, _ = cached
        return OfficialDetail.model_validate(payload)

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
                "delivery_score": metric.delivery_score,
                "keeps_promises_score": metric.keeps_promises_score,
                "truth_verdict": metric.truth_verdict,
                "truth_badge_variant": metric.truth_badge_variant,
                "last_refreshed_at": metric.last_refreshed_at,
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
        activity: ActivitySummary | None = None,
        promises: list[PromiseItem] | None = None,
        delivery_score: DeliveryScore | None = None,
        keeps_promises_score: int | None = None,
        persist: bool = True,
    ) -> DirectoryMetric:
        metric = metric or self._load_metric(bioguide_id) or DirectoryMetric()
        if metric.efficiency_score is not None and ((metric.keeps_promises_score is not None and metric.delivery_score is not None) or not full) and not force_refresh:
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
        if metric.keeps_promises_score is None or force_refresh:
            metric.keeps_promises_score = max(0, min(100, round(efficiency * 0.82)))
        metric.priority_commitment_score = metric.keeps_promises_score

        if full:
            activity = activity or ActivitySummary()
            promises = promises or []
            delivery = delivery_score or compute_delivery_score(promises, activity)
            keeps_promises = keeps_promises_score if keeps_promises_score is not None else compute_keeps_promises_score(promises, activity)
            metric.delivery_score = delivery.overall_score
            metric.keeps_promises_score = keeps_promises
            metric.priority_commitment_score = keeps_promises
            advancement_bonus = min(18, activity.passed_count * 3 + activity.enacted_count * 8)
            metric.efficiency_score = min(100, round(max(metric.efficiency_score or 0, efficiency + advancement_bonus)))

        if metric.pac_share is not None:
            commitment = metric.keeps_promises_score if metric.keeps_promises_score is not None else metric.efficiency_score or 0
            metric.pac_alignment_signal = round((metric.pac_share * 100) * ((100 - commitment) / 100))

        if persist:
            self.db.save_snapshot("directory_metric", bioguide_id, metric.model_dump(mode="json"))
        return metric


def _sort_key(card: OfficialCard, sort_by: str):
    if sort_by == "money_desc":
        return (-(card.total_raised or -1), card.name)
    if sort_by == "efficiency_asc":
        return (card.efficiency_score is None, card.efficiency_score or 10_000, card.name)
    if sort_by == "commitment_asc":
        commitment = card.keeps_promises_score if card.keeps_promises_score is not None else card.priority_commitment_score
        return (commitment is None, commitment or 10_000, card.name)
    if sort_by == "pac_alignment_desc":
        return (-(card.pac_alignment_signal or -1), card.name)
    return (card.name,)
