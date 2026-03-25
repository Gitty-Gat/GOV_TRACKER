from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.dashboard import DashboardService


if __name__ == "__main__":
    service = DashboardService()
    service.list_officials()
    service.sync_directory_efficiency_metrics(limit=80, full=False)
    warmed_ids: set[str] = set()
    for sort in ("name", "money_desc"):
        for card in service.list_officials(sort_by=sort)[:24]:
            if card.bioguide_id in warmed_ids:
                continue
            member = service.congress.get_member_detail(card.bioguide_id)
            try:
                service.fec.ensure_card_finance_summary(member, force=False, allow_search=False)
            except Exception:
                pass
            warmed_ids.add(card.bioguide_id)
            time.sleep(0.02)
    for bioguide_id in list(warmed_ids)[:16]:
        try:
            service.get_official_detail(bioguide_id, force_refresh=False)
        except Exception:
            pass
    priority_ids = {card.bioguide_id for card in service.list_officials(sort_by="money_desc")[:2]}
    priority_ids.update({"B001314", "G000565"})
    for bioguide_id in priority_ids:
        try:
            member = service.congress.get_member_detail(bioguide_id)
            service.fec.build_finance_snapshot(member, force=True)
            service.get_official_detail(bioguide_id, force_refresh=False)
        except Exception:
            pass
    print("Directory finance and efficiency metrics refreshed.")
