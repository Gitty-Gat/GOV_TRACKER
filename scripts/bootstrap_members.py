from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.congress import CongressService


if __name__ == "__main__":
    CongressService().ensure_current_members(force=True)
    print("Current House and Senate members synced.")
