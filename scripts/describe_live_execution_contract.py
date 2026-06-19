from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.execution.live_execution_contract import (
    EXECUTION_FORBIDDEN_ACTIONS,
    EXECUTION_INPUT_FIELDS,
    EXECUTION_LOG_FIELDS,
    EXECUTION_OUTPUT_FIELDS,
    EXECUTION_RESPONSIBILITIES,
    OBSERVABILITY_METRICS,
    ORDER_LIFECYCLE_STATES,
    PROTECTION_MODE_TRIGGERS,
    SUPPORTED_ORDER_TYPES,
)


def main() -> None:
    payload = {
        "responsibilities": EXECUTION_RESPONSIBILITIES,
        "input_fields": EXECUTION_INPUT_FIELDS,
        "output_fields": EXECUTION_OUTPUT_FIELDS,
        "supported_order_types": SUPPORTED_ORDER_TYPES,
        "lifecycle_states": ORDER_LIFECYCLE_STATES,
        "idempotency_key": "symbol + strategy_event_id + strategy_state + side",
        "pre_execution_checks": [
            "tradable",
            "trade_window",
            "leverage_ready",
            "quantity_precision",
            "minimum_notional",
            "reduce_only",
            "position_side",
            "current_position_side",
            "account_risk",
            "symbol_cooldown",
        ],
        "log_fields": EXECUTION_LOG_FIELDS,
        "observability_metrics": OBSERVABILITY_METRICS,
        "protection_mode_triggers": PROTECTION_MODE_TRIGGERS,
        "forbidden": EXECUTION_FORBIDDEN_ACTIONS,
        "binance_client_policy": "thin adapter only; do not modify strategy, risk, state, or sizing logic",
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
