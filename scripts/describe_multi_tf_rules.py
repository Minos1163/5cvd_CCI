from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.strategy_philosophy import TIMEFRAME_ROLES


def main() -> None:
    payload = {
        "roles": TIMEFRAME_ROLES,
        "outputs": ["DIRECT", "PROBE", "WAIT", "NO_TRADE"],
        "rule": "4h is reference only; 1h permission controls direction",
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
