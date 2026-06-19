from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.risk.risk_engine import (
    DEFAULT_RISK_LIMITS,
    RISK_DECISION_FLOW,
    RISK_FORBIDDEN_ACTIONS,
    RISK_LEVELS,
    RISK_OUTPUT_FIELDS,
    RISK_REQUIRED_INPUTS,
    RISK_SCORE_COMPONENTS,
    RISK_SNAPSHOT_FIELDS,
    evaluate_risk,
)


def _sample(**overrides):
    context = {
        "symbol": "BTCUSDT",
        "timestamp": 1,
        "signal_type": "LONG",
        "signal_side": "LONG",
        "entry_mode": "DIRECT",
        "account_equity": 10_000,
        "available_margin": 5_000,
        "used_margin": 1_000,
        "open_positions": 1,
        "portfolio_exposure": 0.20,
        "symbol_exposure": 0.05,
        "daily_pnl": 0,
        "weekly_pnl": 0,
        "max_drawdown": 0.05,
        "atr": 100,
        "stop_pct": 0.02,
        "quality_flag": True,
        "cooldown_state": {"active": False},
        "market_state_4h": "BULL",
        "trend_state_1h": "LONG_ALLOWED",
        "confirm_state_30m": "LONG_CONFIRM",
        "trigger_state_15m": "LONG",
        "entry_price": 50_000,
        "volatility_state": "NORMAL",
    }
    context.update(overrides)
    return evaluate_risk(context).to_dict()


def main() -> None:
    payload = {
        "engine": "risk_engine",
        "responsibility": "pre_trade_risk_gate_and_risk_constraints",
        "risk_levels": RISK_LEVELS,
        "decision_flow": RISK_DECISION_FLOW,
        "required_inputs": RISK_REQUIRED_INPUTS,
        "output_fields": RISK_OUTPUT_FIELDS,
        "default_limits": DEFAULT_RISK_LIMITS,
        "score_components": RISK_SCORE_COMPONENTS,
        "snapshot_fields": RISK_SNAPSHOT_FIELDS,
        "relationships": {
            "signal engine": "provides direction, entry mode, evidence, and candidate intent",
            "position module": "calculates final_notional and final_qty",
            "execution layer": "turns confirmed risk and position decisions into orders and logs",
        },
        "forbidden_actions": {
            "risk layer": RISK_FORBIDDEN_ACTIONS,
            "execution layer": [
                "must_not_modify_stop",
                "must_not_modify_position_size",
                "must_not_recalculate_risk",
                "must_not_infer_trade_continuation",
            ],
        },
        "sample": {
            "direct": _sample(),
            "probe": _sample(entry_mode="PROBE"),
            "blocked": _sample(daily_pnl=-600),
            "high_volatility": _sample(volatility_state="HIGH"),
        },
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
