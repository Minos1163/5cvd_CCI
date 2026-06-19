from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.signals.signal_engine import (
    ENTRY_MODES,
    INDICATOR_ROLES,
    SCORE_COMPONENTS,
    SIGNAL_DECISION_FLOW,
    SIGNAL_EVIDENCE_FIELDS,
    SIGNAL_FORBIDDEN_ACTIONS,
    SIGNAL_SIDES,
    SIGNAL_SUB_REASONS,
    SIGNAL_TYPES,
    STATE_MACHINE_MAPPING,
    TIMEFRAME_ROLES,
    generate_signal,
)


def main() -> None:
    sample = generate_signal(
        {
            "symbol": "BTCUSDT",
            "timestamp": 1,
            "market_state_4h": "BULL",
            "trend_state_1h": "LONG_ALLOWED",
            "confirm_state_30m": "LONG_CONFIRM",
            "trigger_state_15m": "LONG",
            "indicators_15m": {"cvd": "LONG", "rsi": "RECOVERY", "boll": "EXPANSION", "atr": "NORMAL"},
            "indicators_30m": {"macd": "LONG", "cci": "STRONG"},
            "indicators_1h": {},
            "indicators_4h": {},
            "risk_snapshot": {"risk_blocked": False},
            "position_snapshot": {},
            "cooldown_state": {"active": False},
            "quality_flag": True,
        }
    ).to_dict()
    payload = {
        "engine": "signal_engine",
        "responsibility": "generate_trade_intent_only",
        "allowed_outputs": {
            "signal_type": SIGNAL_TYPES,
            "signal_side": SIGNAL_SIDES,
            "entry_mode": ENTRY_MODES,
        },
        "decision_flow": SIGNAL_DECISION_FLOW,
        "timeframe_roles": TIMEFRAME_ROLES,
        "indicator_roles": INDICATOR_ROLES,
        "score_components": SCORE_COMPONENTS,
        "standard_sub_reasons": SIGNAL_SUB_REASONS,
        "state_machine_mapping": STATE_MACHINE_MAPPING,
        "evidence_fields": SIGNAL_EVIDENCE_FIELDS,
        "forbidden_actions": {
            "signal layer": SIGNAL_FORBIDDEN_ACTIONS,
            "execution layer": [
                "must_not_modify_signal_type",
                "must_not_rewrite_entry_mode",
                "must_not_promote_probe_to_direct",
                "must_not_change_side",
                "must_not_add_new_trade_reason",
            ],
        },
        "downgrade_policy": {
            "data_quality_failure": "NO_TRADE, WAIT, or no DIRECT",
            "cooldown_active": "NO_TRADE",
            "risk_blocked": "NO_TRADE",
            "flow_divergence": "downgrade from DIRECT to WAIT or NO_TRADE",
            "anti_chase": "RSI overheat or BOLL extension prevents DIRECT",
        },
        "sample_direct_long": sample,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
