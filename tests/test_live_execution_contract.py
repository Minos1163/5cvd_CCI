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
    ExecutionInstruction,
    ExecutionResponse,
    ExecutionValidation,
    LifecycleEvent,
    build_execution_log,
    build_idempotency_key,
    build_partial_fill_snapshot,
    lifecycle_transition,
    normalize_reject_reason,
    should_enter_protection_mode,
    validate_execution_instruction,
)


def valid_instruction(**overrides):
    values = {
        "symbol": "BTCUSDT",
        "side": "BUY",
        "order_type": "MARKET",
        "quantity": 0.1,
        "price": None,
        "reduce_only": False,
        "position_side": "LONG",
        "time_in_force": None,
        "stop_price": 95_000,
        "take_profit_price": 110_000,
        "client_order_id": "cli-1",
        "strategy_event_id": "evt-1",
        "strategy_state": "DIRECT_LONG",
        "expected_position_side": "LONG",
        "expected_risk_tag": "entry",
    }
    values.update(overrides)
    return ExecutionInstruction(**values)


def test_live_execution_contract_lists_doc_fields_and_boundaries():
    assert EXECUTION_RESPONSIBILITIES == [
        "create_order",
        "cancel_order",
        "query_order_status",
        "query_position_status",
        "sync_account_info",
        "sync_leverage_and_margin",
        "maintain_order_lifecycle_log",
        "return_raw_exchange_response",
        "standardize_execution_error",
    ]
    assert EXECUTION_INPUT_FIELDS == [
        "symbol",
        "side",
        "order_type",
        "quantity",
        "price",
        "reduce_only",
        "position_side",
        "time_in_force",
        "stop_price",
        "take_profit_price",
        "client_order_id",
        "strategy_event_id",
        "strategy_state",
        "expected_position_side",
        "expected_risk_tag",
    ]
    assert EXECUTION_OUTPUT_FIELDS == [
        "order_id",
        "client_order_id",
        "status",
        "filled_qty",
        "avg_price",
        "commission",
        "executed_notional",
        "reject_reason",
        "raw_response",
        "latency_ms",
        "ts",
    ]
    assert SUPPORTED_ORDER_TYPES == ["MARKET", "LIMIT", "IOC", "STOP_MARKET", "TAKE_PROFIT_MARKET"]
    assert ORDER_LIFECYCLE_STATES == [
        "created",
        "validated",
        "submitted",
        "acknowledged",
        "partially_filled",
        "filled",
        "canceled",
        "rejected",
        "expired",
        "reconciled",
    ]
    assert "execution layer changes order quantity" in EXECUTION_FORBIDDEN_ACTIONS
    assert "order_success_rate" in OBSERVABILITY_METRICS


def test_execution_records_round_trip_to_dict():
    instruction = valid_instruction()
    response = ExecutionResponse(
        order_id="1",
        client_order_id="cli-1",
        status="created",
        filled_qty=0,
        avg_price=0,
        commission=0,
        executed_notional=0,
        reject_reason="",
        raw_response={"ok": True},
        latency_ms=12,
        ts=1_700_000_000,
    )
    event = LifecycleEvent("cli-1", "created", 1_700_000_000, "instruction accepted")
    assert instruction.to_dict()["strategy_event_id"] == "evt-1"
    assert response.to_dict()["status"] == "created"
    assert event.to_dict()["state"] == "created"


def test_validate_execution_instruction_approves_clean_market_order():
    validation = validate_execution_instruction(
        valid_instruction(),
        tradable=True,
        in_trade_window=True,
        leverage_ready=True,
        min_notional=5,
        quantity_step=0.001,
        current_position_side="LONG",
        account_risk_allows=True,
        symbol_cooldown_active=False,
    )
    assert validation == ExecutionValidation(True, "validated")


def test_validate_execution_instruction_rejects_bad_side_type_qty_and_reduce_only():
    assert validate_execution_instruction(valid_instruction(side="HOLD")).passed is False
    assert validate_execution_instruction(valid_instruction(order_type="POST_ONLY")).passed is False
    assert validate_execution_instruction(valid_instruction(quantity=0)).passed is False
    assert validate_execution_instruction(
        valid_instruction(reduce_only=True, expected_risk_tag="entry")
    ).passed is False


def test_validate_execution_instruction_rejects_precision_min_notional_and_context_gates():
    assert validate_execution_instruction(
        valid_instruction(quantity=0.1005), quantity_step=0.001
    ).passed is False
    assert validate_execution_instruction(
        valid_instruction(quantity=0.001, price=100, order_type="LIMIT"), min_notional=5
    ).passed is False
    assert validate_execution_instruction(valid_instruction(), tradable=False).passed is False
    assert validate_execution_instruction(valid_instruction(), in_trade_window=False).passed is False
    assert validate_execution_instruction(valid_instruction(), leverage_ready=False).passed is False
    assert validate_execution_instruction(valid_instruction(), account_risk_allows=False).passed is False
    assert validate_execution_instruction(valid_instruction(), symbol_cooldown_active=True).passed is False


def test_idempotency_key_and_reject_normalization_are_stable():
    instruction = valid_instruction()
    assert build_idempotency_key(instruction) == "BTCUSDT:evt-1:DIRECT_LONG:BUY"
    assert normalize_reject_reason("-2019 margin insufficient") == "INSUFFICIENT_MARGIN"
    assert normalize_reject_reason("precision over maximum") == "PRECISION_ERROR"
    assert normalize_reject_reason("timeout waiting exchange") == "NETWORK_TIMEOUT"
    assert normalize_reject_reason("anything else") == "EXCHANGE_ERROR"


def test_lifecycle_transition_and_execution_log_fields_are_replayable():
    instruction = valid_instruction()
    response = ExecutionResponse(
        order_id="1",
        client_order_id="cli-1",
        status="acknowledged",
        filled_qty=0,
        avg_price=0,
        commission=0,
        executed_notional=0,
        reject_reason="",
        raw_response={"orderId": 1},
        latency_ms=20,
        ts=1_700_000_001,
    )
    event = lifecycle_transition("cli-1", "submitted", "acknowledged", 1_700_000_001, "exchange ack")
    assert event.state == "acknowledged"
    log = build_execution_log(instruction, response, action="create_order", module="execution")
    assert list(log) == EXECUTION_LOG_FIELDS
    assert log["raw_response"] == {"orderId": 1}


def test_lifecycle_transition_rejects_unknown_or_regressive_state():
    assert lifecycle_transition("cli-1", "created", "validated", 1, "ok").state == "validated"
    try:
        lifecycle_transition("cli-1", "submitted", "created", 1, "bad")
    except ValueError as exc:
        assert "regress" in str(exc)
    else:
        raise AssertionError("expected regression rejection")
    try:
        lifecycle_transition("cli-1", "created", "unknown", 1, "bad")
    except ValueError as exc:
        assert "unknown lifecycle state" in str(exc)
    else:
        raise AssertionError("expected unknown state rejection")


def test_partial_fill_snapshot_keeps_remaining_quantity_for_upper_layer():
    snapshot = build_partial_fill_snapshot(
        order_qty=1.0,
        filled_qty=0.4,
        avg_price=100,
        client_order_id="cli-1",
    )
    assert snapshot == {
        "client_order_id": "cli-1",
        "order_qty": 1.0,
        "filled_qty": 0.4,
        "remaining_qty": 0.6,
        "avg_price": 100,
        "status": "partially_filled",
    }


def test_protection_mode_triggers_on_consecutive_failures_and_unknown_state():
    assert PROTECTION_MODE_TRIGGERS == [
        "consecutive_rejects",
        "consecutive_sync_failures",
        "consecutive_protection_order_failures",
        "abnormal_position_state",
        "unknown_order_state",
        "exchange_unavailable",
    ]
    assert should_enter_protection_mode(consecutive_rejects=3).passed is True
    assert should_enter_protection_mode(consecutive_sync_failures=3).passed is True
    assert should_enter_protection_mode(consecutive_protection_order_failures=3).passed is True
    assert should_enter_protection_mode(abnormal_position_state=True).passed is True
    assert should_enter_protection_mode(unknown_order_state=True).passed is True
    assert should_enter_protection_mode(exchange_unavailable=True).passed is True
    assert should_enter_protection_mode().passed is False
