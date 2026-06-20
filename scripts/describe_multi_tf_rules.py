from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.context.multi_tf_rules import (
    TIMEFRAME_FORBIDDEN_ACTIONS,
    TIMEFRAME_OUTPUT_FIELDS,
    TIMEFRAME_PRIORITY,
    TIMEFRAME_ROLES,
    TIMEFRAME_STATE_SETS,
)


def main() -> None:
    payload = {
        "roles": TIMEFRAME_ROLES,
        "priority": TIMEFRAME_PRIORITY,
        "output_fields": TIMEFRAME_OUTPUT_FIELDS,
        "state_sets": TIMEFRAME_STATE_SETS,
        "outputs": ["DIRECT", "PROBE", "WAIT", "NO_TRADE"],
        "rule": "4h is reference only; 1h permission controls direction; 15m controls timing only",
        "conflict_policy": {
            "4h_vs_1h": "downgrade_direct_to_probe_or_wait",
            "1h_vs_30m": "weak_quality_cannot_direct",
            "30m_vs_15m": "wait_when_trigger_missing",
            "15m_vs_cvd": "divergence_downgrades_to_wait_or_no_trade",
        },
        "signal_mapping_examples": [
            {"4h": "NEUTRAL", "1h": "LONG_ALLOWED", "30m": "CONFIRMED", "15m": "DIRECT", "signal": "DIRECT_LONG"},
            {"4h": "BULL", "1h": "LONG_ALLOWED", "30m": "WEAK", "15m": "DIRECT", "signal": "PROBE_LONG"},
            {"4h": "BEAR", "1h": "NO_TRADE", "30m": "CONFIRMED", "15m": "DIRECT", "signal": "NO_TRADE"},
            {"4h": "NEUTRAL", "1h": "SHORT_ALLOWED", "30m": "TRANSITION", "15m": "WAIT", "signal": "WAIT_SHORT"},
        ],
        "forbidden_actions": TIMEFRAME_FORBIDDEN_ACTIONS,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
