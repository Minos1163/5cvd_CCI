from src.signals.signal_engine import (
    ENTRY_MODES,
    SIGNAL_EVIDENCE_FIELDS,
    SIGNAL_FORBIDDEN_ACTIONS,
    SIGNAL_TYPES,
    STATE_MACHINE_MAPPING,
    SignalEngineContext,
    generate_signal,
)


def base_context(**overrides):
    context = {
        "symbol": "BTCUSDT",
        "timestamp": 1,
        "market_state_4h": "BULL",
        "trend_state_1h": "LONG_ALLOWED",
        "confirm_state_30m": "LONG_CONFIRM",
        "trigger_state_15m": "LONG",
        "indicators_15m": {
            "cvd": "LONG",
            "rsi": "RECOVERY",
            "boll": "EXPANSION",
            "atr": "NORMAL",
        },
        "indicators_30m": {"macd": "LONG", "cci": "STRONG"},
        "indicators_1h": {},
        "indicators_4h": {},
        "risk_snapshot": {"risk_blocked": False},
        "position_snapshot": {},
        "cooldown_state": {"active": False},
        "quality_flag": True,
    }
    context.update(overrides)
    return context


def test_direct_long_records_evidence_and_required_state():
    result = generate_signal(base_context())

    assert result.signal_type == "LONG"
    assert result.signal_side == "LONG"
    assert result.entry_mode == "DIRECT"
    assert result.required_state == "DIRECT_LONG"
    assert result["side"] == "LONG"
    assert result.score >= 0.7
    assert "TREND_ALIGNED" in result.sub_reasons
    assert "FLOW_CONFIRMED" in result.sub_reasons
    assert result.metadata["evidence"]["trigger_state_15m"] == "LONG"


def test_direct_short_is_symmetric():
    result = generate_signal(
        base_context(
            market_state_4h="BEAR",
            trend_state_1h="SHORT_ALLOWED",
            confirm_state_30m="SHORT_CONFIRM",
            trigger_state_15m="SHORT",
            indicators_15m={"cvd": "SHORT", "rsi": "RECOVERY", "boll": "EXPANSION", "atr": "NORMAL"},
            indicators_30m={"macd": "SHORT", "cci": "STRONG"},
        )
    )

    assert result.signal_type == "SHORT"
    assert result.signal_side == "SHORT"
    assert result.entry_mode == "DIRECT"
    assert result.required_state == "DIRECT_SHORT"


def test_probe_when_trigger_is_partial():
    result = generate_signal(base_context(trigger_state_15m="LONG_PARTIAL"))

    assert result.signal_type == "LONG"
    assert result.signal_side == "LONG"
    assert result.entry_mode == "PROBE"
    assert result.required_state == "PROBE_LONG"


def test_wait_when_trigger_is_not_ready():
    result = generate_signal(base_context(trigger_state_15m="WAIT"))

    assert result.signal_type == "WAIT"
    assert result.signal_side == "NONE"
    assert result.entry_mode == "NONE"
    assert result.required_state == "WATCH_*"
    assert "TRIGGER_NOT_READY" in result.sub_reasons


def test_no_trade_for_data_quality_cooldown_risk_and_trend_conflict():
    assert generate_signal(base_context(quality_flag=False)).reason == "DATA_INVALID"
    assert generate_signal(base_context(cooldown_state={"active": True})).reason == "COOLDOWN_ACTIVE"
    assert generate_signal(base_context(risk_snapshot={"risk_blocked": True})).reason == "RISK_BLOCKED"
    assert generate_signal(base_context(market_state_4h="BEAR")).reason == "HIGHER_TIMEFRAME_CONFLICT"


def test_flow_divergence_downgrades_to_wait():
    result = generate_signal(base_context(indicators_15m={"cvd": "DIVERGENCE", "rsi": "RECOVERY"}))

    assert result.signal_type == "WAIT"
    assert result.entry_mode == "NONE"
    assert "FLOW_DIVERGENCE" in result.sub_reasons


def test_rsi_overheated_prevents_direct_long():
    result = generate_signal(base_context(indicators_15m={"cvd": "LONG", "rsi": "OVERHEATED", "boll": "EXPANSION"}))

    assert result.signal_type == "LONG"
    assert result.entry_mode == "PROBE"
    assert "RSI_OVERHEATED" in result.sub_reasons


def test_dataclass_context_is_supported():
    ctx = SignalEngineContext(**base_context())
    result = generate_signal(ctx)

    assert result.signal_type == "LONG"
    assert result.entry_mode == "DIRECT"


def test_signal_engine_public_contract_constants():
    assert SIGNAL_TYPES == ["LONG", "SHORT", "WAIT", "NO_TRADE"]
    assert ENTRY_MODES == ["PROBE", "DIRECT", "NONE"]
    assert STATE_MACHINE_MAPPING["PROBE"] == "PROBE_*"
    assert "call_exchange_adapter" in SIGNAL_FORBIDDEN_ACTIONS
    assert "cvd_state" in SIGNAL_EVIDENCE_FIELDS
