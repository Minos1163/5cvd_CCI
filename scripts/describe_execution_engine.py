from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.execution.execution_engine import (
    BINANCE_CLIENT_POLICY,
    EXECUTION_ENGINE_RESPONSIBILITIES,
    EXECUTION_EVENT_TYPES,
    EXECUTION_FORBIDDEN_ENGINE_ACTIONS,
    EXECUTION_PRE_CHECKS,
    EXECUTION_REQUEST_FIELDS,
    EXECUTION_RESULT_FIELDS,
    EXECUTION_RETRY_POLICY,
    ExecutionEngine,
    ExecutionRequest,
)
from src.execution.live_execution_contract import (
    EXECUTION_LOG_FIELDS,
    OBSERVABILITY_METRICS,
    ORDER_LIFECYCLE_STATES,
    PROTECTION_MODE_TRIGGERS,
    SUPPORTED_ORDER_TYPES,
)


class _DescribeAdapter:
    def submit(self, instruction):
        return {"order_id": "ord-1", "status": "filled", "filled_qty": 0.1, "avg_price": 50_000}

    def cancel(self, symbol, order_id):
        return {"status": "canceled", "client_order_id": f"cancel:{symbol}:{order_id}"}

    def sync(self, symbol=None):
        return {"position": {"symbol": symbol, "qty": 0.1}}


def _sample_result():
    request = ExecutionRequest(
        request_id="req-1",
        event_id="evt-1",
        trace_id="trace-1",
        correlation_id="corr-1",
        symbol="BTCUSDT",
        side="BUY",
        order_type="MARKET",
        quantity=0.1,
        price=50_000,
        reduce_only=False,
        position_side="LONG",
        time_in_force=None,
        stop_price=49_000,
        take_profit_price=52_000,
        entry_mode="DIRECT",
        strategy_state="DIRECT_LONG",
        strategy_version="v1",
        risk_tag="entry",
        expected_position_qty=0.1,
        expected_position_side="LONG",
        timestamp=1,
        risk_snapshot={"allow_trade": True},
        position_snapshot={"position_side": "LONG"},
    )
    return ExecutionEngine(_DescribeAdapter()).submit_order(request).to_dict()


def main() -> None:
    payload = {
        "engine": "execution_engine",
        "responsibility": "execute_already_confirmed_trade_actions",
        "responsibilities": EXECUTION_ENGINE_RESPONSIBILITIES,
        "request_fields": EXECUTION_REQUEST_FIELDS,
        "result_fields": EXECUTION_RESULT_FIELDS,
        "order_lifecycle_states": ORDER_LIFECYCLE_STATES,
        "supported_order_types": SUPPORTED_ORDER_TYPES,
        "pre_execution_checks": EXECUTION_PRE_CHECKS,
        "idempotency_key": "symbol + event_id + strategy_state + side + entry_mode",
        "retry_policy": EXECUTION_RETRY_POLICY,
        "protection_mode_triggers": PROTECTION_MODE_TRIGGERS,
        "event_types": EXECUTION_EVENT_TYPES,
        "log_fields": EXECUTION_LOG_FIELDS,
        "observability_metrics": OBSERVABILITY_METRICS,
        "forbidden_actions": EXECUTION_FORBIDDEN_ENGINE_ACTIONS,
        "binance_client_policy": BINANCE_CLIENT_POLICY,
        "sample_result": _sample_result(),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
