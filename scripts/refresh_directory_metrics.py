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
    service.sync_directory_efficiency_metrics(limit=160, full=False)
    warmed_ids: set[str] = set()
    for sort in ("name", "money_desc"):
        for card in service.list_officials(sort_by=sort)[:24]:
            if card.bioguide_id in warmed_ids:
                continue
            member = service.congress.get_member_detail(card.bioguide_id)
            service.fec.ensure_card_finance_summary(member, force=False, allow_search=False)
            warmed_ids.add(card.bioguide_id)
            time.sleep(0.02)
    print("Directory finance and efficiency metrics refreshed.")
