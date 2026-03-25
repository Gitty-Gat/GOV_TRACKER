from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.dashboard import DashboardService


if __name__ == "__main__":
    service = DashboardService()
    service.congress.ensure_current_members(force=False)
    service.fec.sync_directory_finance_metrics(force=True)
    service.sync_directory_efficiency_metrics(force_refresh=True, limit=120, full=False)
    for sort in ("name", "money_desc"):
        for card in service.list_officials(sort_by=sort)[:24]:
            try:
                member = service.congress.load_cached_member_detail(card.bioguide_id)
                if member:
                    service.fec.ensure_card_finance_summary(member, force=False, allow_search=False)
            except Exception:
                continue
    print("Directory finance, donors, and efficiency metrics refreshed.")
