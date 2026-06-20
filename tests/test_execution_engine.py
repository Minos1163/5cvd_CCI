import pytest

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
    build_execution_idempotency_key,
    normalize_order_status,
)


class FakeAdapter:
    def __init__(self, submit_response=None, submit_errors=None, cancel_response=None, sync_response=None, sync_error=None):
        self.submit_response = submit_response or {
            "order_id": "ord-1",
            "status": "filled",
            "filled_qty": 0.1,
            "avg_price": 50_000,
            "commission": 1,
            "latency_ms": 12,
        }
        self.submit_errors = list(submit_errors or [])
        self.cancel_response = cancel_response or {"status": "canceled", "client_order_id": "cli-cancel"}
        self.sync_response = sync_response or {"position": {"symbol": "BTCUSDT", "qty": 0.1}}
        self.sync_error = sync_error
        self.submit_calls = 0
        self.cancel_calls = 0
        self.sync_calls = 0

    def submit(self, instruction):
        self.submit_calls += 1
        if self.submit_errors:
            raise RuntimeError(self.submit_errors.pop(0))
        return self.submit_response

    def cancel(self, symbol, order_id):
        self.cancel_calls += 1
        if isinstance(self.cancel_response, Exception):
            raise self.cancel_response
        return self.cancel_response

    def sync(self, symbol=None):
        self.sync_calls += 1
        if self.sync_error is not None:
            raise RuntimeError(self.sync_error)
        return self.sync_response


def valid_request(**overrides):
    values = {
        "request_id": "req-1",
        "event_id": "evt-1",
        "trace_id": "trace-1",
        "correlation_id": "corr-1",
        "symbol": "BTCUSDT",
        "side": "BUY",
        "order_type": "MARKET",
        "quantity": 0.1,
        "price": 50_000,
        "reduce_only": False,
        "position_side": "LONG",
        "time_in_force": None,
        "stop_price": 49_000,
        "take_profit_price": 52_000,
        "entry_mode": "DIRECT",
        "strategy_state": "DIRECT_LONG",
        "strategy_version": "v1",
        "risk_tag": "entry",
        "expected_position_qty": 0.1,
        "expected_position_side": "LONG",
        "timestamp": 1_700_000_000,
        "risk_snapshot": {"allow_trade": True},
        "position_snapshot": {"position_side": "LONG"},
    }
    values.update(overrides)
    return ExecutionRequest(**values)


def entry_chain_snapshot(**overrides):
    values = {
        "action": "DIRECT",
        "side": "LONG",
        "risk_allowed": True,
        "notional_hint": 5_000.0,
        "max_symbol_exposure_pct": 0.30,
        "score": 88.0,
        "reasons": ["ALL_GATES_PASSED"],
    }
    values.update(overrides)
    return values


def test_submit_market_order_records_result_lifecycle_and_events():
    engine = ExecutionEngine(FakeAdapter())
    result = engine.submit_order(valid_request(entry_chain_snapshot=entry_chain_snapshot()))

    assert result.status == "filled"
    assert result.client_order_id == "BTCUSDT:evt-1:DIRECT_LONG:BUY:DIRECT"
    assert [item["state"] for item in result.lifecycle] == [
        "created",
        "validated",
        "submitted",
        "acknowledged",
        "filled",
    ]
    assert result.events == ["ORDER_SUBMITTED", "ORDER_FILLED", "POSITION_OPENED"]
    assert result.audit_log["module"] == "execution_engine"
    assert result.audit_log["raw_response"]["order_id"] == "ord-1"


def test_idempotent_duplicate_request_returns_cached_result():
    adapter = FakeAdapter()
    engine = ExecutionEngine(adapter)
    request = valid_request(entry_chain_snapshot=entry_chain_snapshot())
    first = engine.submit_order(request)
    second = engine.submit_order(request)

    assert first is second
    assert adapter.submit_calls == 1


def test_validation_rejects_without_adapter_submit():
    adapter = FakeAdapter()
    engine = ExecutionEngine(adapter)
    result = engine.submit_order(valid_request(quantity=0))

    assert result.status == "rejected"
    assert result.reject_reason == "quantity must be positive"
    assert result.events == ["ORDER_REJECTED"]
    assert adapter.submit_calls == 0


def test_partial_fill_is_reported_without_new_signal_or_auto_fill():
    adapter = FakeAdapter(
        submit_response={"order_id": "ord-2", "status": "partially_filled", "filled_qty": 0.04, "avg_price": 50_000}
    )
    engine = ExecutionEngine(adapter)
    result = engine.submit_order(valid_request(entry_chain_snapshot=entry_chain_snapshot()))

    assert result.status == "partially_filled"
    assert result.metadata["partial_fill"] == {
        "client_order_id": "BTCUSDT:evt-1:DIRECT_LONG:BUY:DIRECT",
        "order_qty": 0.1,
        "filled_qty": 0.04,
        "remaining_qty": 0.060000000000000005,
        "avg_price": 50_000.0,
        "status": "partially_filled",
    }
    assert result.events == ["ORDER_SUBMITTED", "ORDER_ACKNOWLEDGED"]


def test_rejected_exchange_response_is_normalized_and_counted():
    adapter = FakeAdapter(submit_response={"status": "rejected", "message": "-2019 margin insufficient"})
    engine = ExecutionEngine(adapter)
    result = engine.submit_order(valid_request(entry_chain_snapshot=entry_chain_snapshot()))

    assert result.status == "rejected"
    assert result.reject_reason == "INSUFFICIENT_MARGIN"
    assert result.events == ["ORDER_SUBMITTED", "ORDER_REJECTED"]


def test_cancel_order_success_and_failure_paths_are_explicit():
    success_engine = ExecutionEngine(FakeAdapter(cancel_response={"status": "canceled", "client_order_id": "cli-1"}))
    success = success_engine.cancel_order("req-cancel", "BTCUSDT", "ord-1", timestamp=2)
    assert success.status == "canceled"
    assert success.events == ["ORDER_CANCELED"]

    failure_engine = ExecutionEngine(FakeAdapter(cancel_response=RuntimeError("precision error")))
    failure = failure_engine.cancel_order("req-cancel", "BTCUSDT", "ord-1", timestamp=2)
    assert failure.status == "rejected"
    assert failure.reject_reason == "PRECISION_ERROR"
    assert failure.events == ["ORDER_REJECTED"]


def test_sync_failure_enters_protection_mode_after_threshold():
    engine = ExecutionEngine(FakeAdapter(sync_error="exchange unavailable"))

    assert engine.sync_position("BTCUSDT")["protection_mode"] is False
    assert engine.sync_position("BTCUSDT")["protection_mode"] is False
    third = engine.sync_position("BTCUSDT")
    assert third["passed"] is False
    assert third["protection_mode"] is True


def test_retry_reuses_same_instruction_for_retryable_error():
    adapter = FakeAdapter(submit_errors=["timeout waiting exchange"])
    engine = ExecutionEngine(adapter)
    result = engine.submit_order(valid_request(entry_chain_snapshot=entry_chain_snapshot()))

    assert result.status == "filled"
    assert result.metadata["retry_count"] == 1
    assert adapter.submit_calls == 2
    assert result.client_order_id == "BTCUSDT:evt-1:DIRECT_LONG:BUY:DIRECT"


def test_non_retryable_error_rejects_without_changing_intent():
    adapter = FakeAdapter(submit_errors=["precision over maximum"])
    engine = ExecutionEngine(adapter)
    result = engine.submit_order(valid_request(entry_chain_snapshot=entry_chain_snapshot()))

    assert result.status == "rejected"
    assert result.reject_reason == "PRECISION_ERROR"
    assert result.metadata["retry_count"] == 0
    assert adapter.submit_calls == 1


def test_execution_engine_public_contract_constants():
    assert EXECUTION_ENGINE_RESPONSIBILITIES[0] == "validate_request"
    assert "request_id" in EXECUTION_REQUEST_FIELDS
    assert "raw_response" in EXECUTION_RESULT_FIELDS
    assert EXECUTION_EVENT_TYPES[:3] == ["ORDER_SUBMITTED", "ORDER_ACKNOWLEDGED", "ORDER_FILLED"]
    assert EXECUTION_PRE_CHECKS[-1] == "symbol_cooldown"
    assert EXECUTION_RETRY_POLICY["max_retries"] == 2
    assert "rewrite_strategy_intent" in EXECUTION_FORBIDDEN_ENGINE_ACTIONS
    assert BINANCE_CLIENT_POLICY == "thin injected adapter only; do not modify stable client"
    assert build_execution_idempotency_key(valid_request()) == "BTCUSDT:evt-1:DIRECT_LONG:BUY:DIRECT"
    assert normalize_order_status("cancelled") == "canceled"


def test_live_entry_request_requires_entry_chain_approval():
    adapter = FakeAdapter()
    engine = ExecutionEngine(adapter)
    result = engine.submit_order(valid_request())

    assert result.status == "rejected"
    assert result.reject_reason == "entry chain approval is required for entry orders"
    assert adapter.submit_calls == 0


def test_execution_cannot_upgrade_probe_to_direct():
    adapter = FakeAdapter()
    engine = ExecutionEngine(adapter)
    result = engine.submit_order(
        valid_request(
            entry_mode="DIRECT",
            strategy_state="DIRECT_LONG",
            entry_chain_snapshot=entry_chain_snapshot(action="PROBE"),
        )
    )

    assert result.status == "rejected"
    assert result.reject_reason == "execution entry mode exceeds entry chain approval"
    assert adapter.submit_calls == 0


def test_execution_rejects_order_above_entry_chain_notional_hint():
    adapter = FakeAdapter()
    engine = ExecutionEngine(adapter)
    result = engine.submit_order(
        valid_request(
            quantity=0.2,
            price=50_000,
            entry_chain_snapshot=entry_chain_snapshot(notional_hint=5_000.0),
        )
    )

    assert result.status == "rejected"
    assert result.reject_reason == "entry order exceeds entry chain approved notional"
    assert adapter.submit_calls == 0


def test_unknown_lifecycle_status_is_not_accepted():
    engine = ExecutionEngine(FakeAdapter(submit_response={"status": "mystery"}))
    result = engine.submit_order(valid_request(entry_chain_snapshot=entry_chain_snapshot()))

    assert result.status == "rejected"
    assert result.events == ["ORDER_SUBMITTED", "ORDER_REJECTED"]


def test_no_src_api_binance_import_in_execution_engine():
    import src.execution.execution_engine as execution_engine

    assert "src.api.binance_client" not in str(execution_engine.__dict__)
