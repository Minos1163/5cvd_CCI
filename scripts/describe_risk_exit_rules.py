from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.risk.exit_engine import EXIT_PRIORITY


def main() -> None:
    payload = {
        "initial_stop_source": "ATR only",
        "exit_priority": [item.value for item in EXIT_PRIORITY],
        "take_profit": {"r_levels": [1.0, 2.0, 3.0], "reduce_pcts": [0.30, 0.40, 0.30]},
        "breakeven_buffer": ["fee", "slippage", "safety"],
        "cooldown": {"default_timeframe": "15m", "normal_stop_bars": [3, 6]},
        "forbidden": [
            "multiple active stop systems",
            "execution layer rewriting risk model",
            "lower-priority exit overriding higher-priority exit",
            "loss averaging",
        ],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
