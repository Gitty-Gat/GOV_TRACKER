from __future__ import annotations

from app.db import Database, utc_now_iso
from app.models import ActivitySummary, DirectoryMetric, FinanceSummary, OfficialCard, OfficialDetail, PromiseItem
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
    ) -> list[OfficialCard]:
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

    def seed_baseline_data(self, force: bool = False, limit: int | None = None) -> dict[str, int]:
        self.congress.ensure_current_members(force=force)

        processed = 0
        failed = 0
        payloads = self.db.list_official_payloads()
        if limit:
            payloads = payloads[:limit]

        for payload in payloads:
            bioguide_id = payload["bioguide_id"]
            try:
                cached_member = self.congress.load_cached_member_detail(bioguide_id)
                needs_enriched_member = force or not cached_member or cached_member.get("detailReadiness") != "enriched"
                if needs_enriched_member:
                    try:
                        self.congress.get_member_detail(bioguide_id, force=True)
                    except Exception:
                        self.congress.ensure_member_detail_snapshot(bioguide_id)
            except Exception:
                continue

        try:
            self.fec.sync_directory_finance_metrics(force=force)
        except Exception:
            pass

        for payload in payloads:
            bioguide_id = payload["bioguide_id"]
            try:
                existing = self._load_detail_snapshot(bioguide_id)
                if existing and existing.data_readiness != "seeded" and not force:
                    processed += 1
                    continue

                cached_member = self.congress.load_cached_member_detail(bioguide_id)
                member = cached_member
                if not member:
                    member = self.congress.ensure_member_detail_snapshot(bioguide_id)
                card = self.db.get_official_card(bioguide_id)
                if not member or not card:
                    failed += 1
                    continue

                activity = self.congress.load_cached_activity_snapshot(bioguide_id) or self.congress.build_lightweight_activity_snapshot(
                    member,
                    note="Detailed bill movement will appear after the next scheduled refresh.",
                )
                promises = self.promises.load_cached_promises(bioguide_id)
                if promises is None:
                    promises = self.promises.get_promises(member, force=False)
                finance = self.fec.load_cached_finance_snapshot(bioguide_id) or self.fec._partial_finance_summary(member, "")
                self._store_detail_snapshot(card, member, activity, promises or [], finance, persist=True)
                processed += 1
            except Exception:
                failed += 1

        self.db.set_meta("baseline_bootstrap_at", utc_now_iso())
        return {"processed": processed, "failed": failed}

    def refresh_official_detail(self, bioguide_id: str) -> OfficialDetail:
        member = self.congress.get_member_detail(bioguide_id, force=True)
        card = self.db.get_official_card(bioguide_id)
        if not card:
            self.congress.ensure_current_members(force=True)
            card = self.db.get_official_card(bioguide_id)
            if not card:
                raise KeyError(bioguide_id)

        activity = self.congress.build_activity_snapshot(bioguide_id, force=True)
        promises = self.promises.get_promises(member, force=True)
        finance = self.fec.build_finance_snapshot(member, force=True)
        return self._store_detail_snapshot(card, member, activity, promises, finance, persist=True)

    def refresh_all_precomputed_data(self, limit: int | None = None) -> dict[str, int]:
        self.seed_baseline_data(force=False, limit=limit)
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
                self.refresh_official_detail(bioguide_id)
                processed += 1
            except Exception:
                failed += 1

        self.db.set_meta("precomputed_refresh_at", utc_now_iso())
        return {"processed": processed, "failed": failed}

    def refresh_read_model(
        self,
        limit: int | None = None,
        force: bool = False,
        refresh_promises: bool = False,
    ) -> dict[str, int]:
        self.congress.ensure_current_members(force=force)
        payloads = self.db.list_official_payloads()
        if limit:
            payloads = payloads[:limit]

        for payload in payloads:
            bioguide_id = payload["bioguide_id"]
            try:
                cached_member = self.congress.load_cached_member_detail(bioguide_id)
                if force or not cached_member or cached_member.get("detailReadiness") != "enriched":
                    try:
                        self.congress.get_member_detail(bioguide_id, force=True)
                    except Exception:
                        self.congress.ensure_member_detail_snapshot(bioguide_id)
            except Exception:
                continue

        processed = 0
        failed = 0
        for payload in payloads:
            bioguide_id = payload["bioguide_id"]
            try:
                member = self.congress.load_cached_member_detail(bioguide_id) or self.congress.ensure_member_detail_snapshot(bioguide_id)
                card = self.db.get_official_card(bioguide_id)
                if not member or not card:
                    failed += 1
                    continue

                activity = self.congress.build_activity_snapshot(bioguide_id, force=force)
                promises = self.promises.get_promises(member, force=refresh_promises) if refresh_promises else (self.promises.load_cached_promises(bioguide_id) or self.promises.get_promises(member, force=False))
                self.fec.ensure_directory_finance_metric(member, force=force, include_donor_names=True)
                finance = self.fec.load_cached_finance_snapshot(bioguide_id) or self.fec._partial_finance_summary(member, "")
                self._store_detail_snapshot(card, member, activity, promises or [], finance, persist=True)
                processed += 1
            except Exception:
                failed += 1

        self.db.set_meta("read_model_refresh_at", utc_now_iso())
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
            member = self.congress.load_cached_member_detail(bioguide_id)
            if not member:
                continue
            if metric and metric.efficiency_score is not None and not force_refresh:
                count += 1
                if limit and count >= limit:
                    break
                continue
            self._ensure_efficiency_metric(bioguide_id, member, metric, force_refresh=force_refresh, full=full)
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

        finance_status = _finance_status(finance)
        activity_status = _activity_status(activity)
        promises_status = "enriched" if promises else "pending"

        metric.data_readiness = _compose_readiness(finance_status, activity_status, promises_status)
        metric.finance_status = finance_status
        metric.activity_status = activity_status
        metric.promises_status = promises_status
        metric.finance_available = finance.available or finance_status != "pending" or metric.finance_available
        metric.candidate_id = finance.candidate_id or metric.candidate_id
        metric.principal_committee_id = finance.principal_committee_id or metric.principal_committee_id
        if finance.total_raised is not None or metric.total_raised is None:
            metric.total_raised = finance.total_raised
        if finance.cash_on_hand is not None or metric.cash_on_hand is None:
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
            persist=False,
        )

        if _has_truth_inputs(promises, activity):
            truth_verdict, truth_badge_variant = compute_truth_verdict(keeps_promises_score, delivery_score.overall_score)
            metric.delivery_score = delivery_score.overall_score
            metric.keeps_promises_score = keeps_promises_score
            metric.truth_verdict = truth_verdict
            metric.truth_badge_variant = truth_badge_variant
            metric.priority_commitment_score = keeps_promises_score
        else:
            delivery_score = delivery_score.model_copy(
                update={
                    "overall_score": None,
                    "label": "Insufficient data",
                    "explanation": "This score appears after the app has both clear priorities and deeper legislative detail.",
                }
            )
            metric.delivery_score = None
            metric.keeps_promises_score = None
            metric.truth_verdict = None
            metric.truth_badge_variant = None
            metric.priority_commitment_score = None

        if metric.pac_share is not None and metric.keeps_promises_score is not None:
            metric.pac_alignment_signal = round((metric.pac_share * 100) * ((100 - metric.keeps_promises_score) / 100))
        else:
            metric.pac_alignment_signal = None

        if persist:
            metric.last_refreshed_at = utc_now_iso()
            self.db.save_snapshot("directory_metric", card.bioguide_id, metric.model_dump(mode="json"))

        enriched_card = self._apply_metric(card, metric)
        detail = OfficialDetail(
            member=member,
            card=enriched_card,
            activity=activity,
            finance=finance,
            promises=promises,
            delivery_score=delivery_score,
            data_readiness=metric.data_readiness,
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
                "data_readiness": metric.data_readiness,
                "finance_status": metric.finance_status,
                "activity_status": metric.activity_status,
                "promises_status": metric.promises_status,
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
        delivery_score=None,
        keeps_promises_score: int | None = None,
        persist: bool = True,
    ) -> DirectoryMetric:
        metric = metric or self._load_metric(bioguide_id) or DirectoryMetric()
        if metric.efficiency_score is not None and not force_refresh:
            return metric

        sponsored = (member.get("sponsoredLegislation") or {}).get("count")
        cosponsored = (member.get("cosponsoredLegislation") or {}).get("count")
        if sponsored is None and cosponsored is None and member.get("detailReadiness") != "enriched":
            metric.efficiency_score = None
            metric.years_in_office = _years_in_office(member)
            if persist:
                self.db.save_snapshot("directory_metric", bioguide_id, metric.model_dump(mode="json"))
            return metric

        sponsored_count = int(sponsored or 0)
        cosponsored_count = int(cosponsored or 0)
        years_in_office = _years_in_office(member)
        throughput = (sponsored_count * 1.8 + cosponsored_count * 0.35) / years_in_office
        efficiency = min(100, round(min(72, throughput)))
        metric.efficiency_score = efficiency
        metric.years_in_office = years_in_office

        if full and activity and activity.status == "enriched":
            advancement_bonus = min(18, activity.passed_count * 3 + activity.enacted_count * 8)
            metric.efficiency_score = min(100, round(max(metric.efficiency_score or 0, efficiency + advancement_bonus)))

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


def _years_in_office(member: dict) -> int:
    terms = member.get("terms") or []
    first_start = terms[0].get("startYear") if terms else None
    current_start = terms[-1].get("startYear") if terms else None
    return max(1, 2026 - int(first_start or current_start or 2026) + 1)


def _finance_status(finance: FinanceSummary) -> str:
    if finance.status in {"pending", "partial", "enriched"}:
        return finance.status
    if finance.available and finance.top_donors:
        return "enriched"
    if finance.available or finance.total_raised is not None or finance.cash_on_hand is not None:
        return "partial"
    return "pending"


def _activity_status(activity: ActivitySummary) -> str:
    if activity.status in {"pending", "seeded", "partial", "enriched"}:
        return activity.status
    if activity.recent_bills:
        return "enriched"
    return "seeded"


def _compose_readiness(finance_status: str, activity_status: str, promises_status: str) -> str:
    if finance_status == "enriched" and activity_status == "enriched" and promises_status == "enriched":
        return "enriched"
    if finance_status in {"partial", "enriched"} or activity_status == "enriched" or promises_status == "enriched":
        return "partial"
    return "seeded"


def _has_truth_inputs(promises: list[PromiseItem], activity: ActivitySummary) -> bool:
    return bool(promises and activity.status == "enriched" and activity.recent_bills)
