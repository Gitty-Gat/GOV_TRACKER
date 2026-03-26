from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.dashboard import DashboardService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed baseline precomputed data for House and Senate members.")
    parser.add_argument("--limit", type=int, default=None, help="Optional limit for local verification.")
    parser.add_argument("--force", action="store_true", help="Rebuild baseline snapshots even if they already exist.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    service = DashboardService()
    results = service.seed_baseline_data(force=args.force, limit=args.limit)
    print(
        "Baseline bootstrap completed. "
        f"Processed={results['processed']} Failed={results['failed']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
