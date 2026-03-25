from __future__ import annotations

from app.db import Database
from app.models import OfficialDetail
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
        force_sync: bool = False,
    ):
        self.congress.ensure_current_members(force=force_sync)
        return self.db.list_officials(search=search, chamber=chamber, party=party, state=state)

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
