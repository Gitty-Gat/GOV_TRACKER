from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.dashboard import DashboardService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Populate the live read model with finance totals, donor summaries, and legislative activity.")
    parser.add_argument("--limit", type=int, default=None, help="Optional limit for local verification.")
    parser.add_argument("--force", action="store_true", help="Refresh existing read-model records.")
    parser.add_argument("--refresh-promises", action="store_true", help="Also refresh issue-priority inference from official websites.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    service = DashboardService()
    with service.db.persistent_connection():
        results = service.refresh_read_model(limit=args.limit, force=args.force, refresh_promises=args.refresh_promises)
    print(
        "Read-model refresh completed. "
        f"Processed={results['processed']} Failed={results['failed']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
