from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.dashboard import DashboardService


if __name__ == "__main__":
    service = DashboardService()
    service.list_officials(force_sync=True)
    service.sync_directory_efficiency_metrics(force_refresh=True)
    warmed_ids: set[str] = set()
    for sort in ("name", "money_desc"):
        for card in service.list_officials(sort_by=sort)[:60]:
            if card.bioguide_id in warmed_ids:
                continue
            member = service.congress.get_member_detail(card.bioguide_id)
            service.fec.ensure_card_finance_summary(member, force=False)
            warmed_ids.add(card.bioguide_id)
            time.sleep(0.55)
    print("Directory finance and efficiency metrics refreshed.")
