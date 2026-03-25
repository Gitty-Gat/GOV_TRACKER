from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.dashboard import DashboardService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh precomputed House and Senate data.")
    parser.add_argument("--limit", type=int, default=None, help="Optional limit for local verification.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    service = DashboardService()
    results = service.refresh_all_precomputed_data(limit=args.limit)
    print(
        "Precomputed refresh completed. "
        f"Processed={results['processed']} Failed={results['failed']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
