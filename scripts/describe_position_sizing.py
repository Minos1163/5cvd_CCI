from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.risk.position_sizer import (
    ENTRY_MODE_MULTIPLIERS,
    MARKET_TIER_MULTIPLIERS,
    POSITION_DECISION_STEPS,
    POSITION_LOG_FIELDS,
    POSITION_REQUIRED_INPUTS,
    STATE_POSITION_POLICY,
    VOLATILITY_FACTORS,
    PositionSizingInput,
    calculate_position_size,
)


def _sample(signal_type: str) -> dict:
    result = calculate_position_size(
        PositionSizingInput(
            symbol="BTCUSDT",
            signal_type=signal_type,
            entry_mode=signal_type,
            equity=10_000,
            available_margin=5_000,
            price=50_000,
            leverage=5,
            stop_pct=0.02,
            atr=800,
            risk_pct=0.01,
            market_tier="B",
            current_open_exposure=0,
            portfolio_correlation=0.2,
            min_notional=5,
            max_total_exposure_pct=0.75,
            max_symbol_exposure_pct=0.75,
            max_correlation_group_exposure_pct=0.75,
        )
    )
    return {
        "decision": result.decision,
        "notional": result.notional,
        "quantity": result.quantity,
        "required_margin": result.required_margin,
    }


def main() -> None:
    payload = {
        "formula": "position_notional = risk_amount / stop_pct",
        "signal_multipliers": ENTRY_MODE_MULTIPLIERS,
        "entry_mode_multipliers": ENTRY_MODE_MULTIPLIERS,
        "market_tier_multipliers": MARKET_TIER_MULTIPLIERS,
        "volatility_factors": VOLATILITY_FACTORS,
        "minimum_notional_policy": "reject; never inflate",
        "no_trade_policy": "return NO_TRADE; never inflate or promote",
        "required_inputs": POSITION_REQUIRED_INPUTS,
        "decision_steps": POSITION_DECISION_STEPS,
        "log_fields": POSITION_LOG_FIELDS,
        "state_policy": STATE_POSITION_POLICY,
        "sample": {"direct": _sample("DIRECT"), "probe": _sample("PROBE")},
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
