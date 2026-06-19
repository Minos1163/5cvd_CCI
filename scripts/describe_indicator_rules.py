from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.indicators.indicator_spec import DEFAULT_INDICATOR_PARAMS, INDICATOR_PRIORITY, INDICATOR_RESPONSIBILITIES


def main() -> None:
    payload = {
        "params": DEFAULT_INDICATOR_PARAMS,
        "responsibilities": INDICATOR_RESPONSIBILITIES,
        "priority": INDICATOR_PRIORITY,
        "forbidden": ["ATR direction"],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
