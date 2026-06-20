from src.context.multi_tf_rules import (
    TIMEFRAME_FORBIDDEN_ACTIONS,
    TIMEFRAME_OUTPUT_FIELDS,
    TIMEFRAME_PRIORITY,
    TIMEFRAME_ROLES,
    TimeframeResult,
    build_multi_tf_decision,
    build_timeframe_results,
    evaluate_15m_trigger,
    evaluate_1h_permission,
    evaluate_30m_quality,
    evaluate_30m_quality_state,
    evaluate_4h_context,
    validate_timeframe_result,
)
from src.core.models import IndicatorSnapshot


def snap(timeframe: str, **kwargs) -> IndicatorSnapshot:
    return IndicatorSnapshot(symbol="BTCUSDT", timeframe=timeframe, close_time=1, **kwargs)


def test_timeframe_contract_constants_match_doc():
    assert TIMEFRAME_ROLES == {
        "4h": "background_reference",
        "1h": "direction_confirmation",
        "30m": "trend_quality_confirmation",
        "15m": "execution_trigger",
    }
    assert TIMEFRAME_PRIORITY == (
        "data_quality",
        "risk_constraints",
        "4h_background",
        "1h_direction",
        "30m_quality",
        "15m_trigger",
        "position_executability",
        "execution_layer",
    )
    assert TIMEFRAME_OUTPUT_FIELDS == (
        "symbol",
        "timeframe",
        "timestamp",
        "state",
        "confidence",
        "reason",
        "sub_reasons",
        "quality_flag",
        "metadata",
    )
    assert "15m_direction_override" in TIMEFRAME_FORBIDDEN_ACTIONS
    assert "execution_reinterprets_context" in TIMEFRAME_FORBIDDEN_ACTIONS


def test_4h_is_reference_context_only():
    assert evaluate_4h_context(snap("4h", macd=1, cci=120, cvd_delta=10)).value == "BULL"
    assert evaluate_4h_context(snap("4h", macd=-1, cci=-120, cvd_delta=-10)).value == "BEAR"
    assert evaluate_4h_context(snap("4h", macd=0, cci=0, cvd_delta=0)).value == "NEUTRAL"


def test_1h_permission_uses_macd_cci_cvd():
    assert evaluate_1h_permission(snap("1h", macd=1, cci=120, cvd_delta=5)).value == "LONG_ALLOWED"
    assert evaluate_1h_permission(snap("1h", macd=-1, cci=-120, cvd_delta=-5)).value == "SHORT_ALLOWED"
    assert evaluate_1h_permission(snap("1h", macd=1, cci=-120, cvd_delta=5)).value == "NO_TRADE"


def test_30m_quality_exposes_legacy_direction_and_generic_state():
    assert evaluate_30m_quality(snap("30m", cci=120)).value == "LONG_CONFIRM"
    assert evaluate_30m_quality(snap("30m", cci=-120)).value == "SHORT_CONFIRM"
    assert evaluate_30m_quality(snap("30m", cci=0)).value == "WEAK"
    assert evaluate_30m_quality_state(snap("30m", cci=120)).value == "CONFIRMED"
    assert evaluate_30m_quality_state(snap("30m", cci=None)).value == "TRANSITION"


def test_15m_trigger_uses_rsi_reclaim_and_cvd():
    assert evaluate_15m_trigger(snap("15m", rsi=55, cvd_delta=5), previous_rsi=45).value == "LONG_TRIGGER"
    assert evaluate_15m_trigger(snap("15m", rsi=45, cvd_delta=-5), previous_rsi=55).value == "SHORT_TRIGGER"
    assert evaluate_15m_trigger(snap("15m", rsi=50, cvd_delta=0), previous_rsi=50).value == "WAIT"


def test_build_timeframe_results_returns_standard_contracts():
    results = build_timeframe_results(
        tf_4h=snap("4h", macd=1, cci=120, cvd_delta=10),
        tf_1h=snap("1h", macd=1, cci=120, cvd_delta=5),
        tf_30m=snap("30m", macd=1, macd_hist=0.2, cci=130, cvd_delta=3),
        tf_15m=snap("15m", rsi=55, cvd_delta=5),
        previous_15m_rsi=45,
    )
    by_tf = {item.timeframe: item for item in results}
    assert isinstance(by_tf["1h"], TimeframeResult)
    assert by_tf["1h"].state == "LONG_ALLOWED"
    assert by_tf["30m"].state == "CONFIRMED"
    assert by_tf["30m"].metadata["directional_quality"] == "LONG_CONFIRM"
    assert by_tf["15m"].state == "DIRECT"
    assert all(validate_timeframe_result(item).passed for item in results)


def test_validate_timeframe_result_rejects_stale_and_invalid_state():
    result = TimeframeResult("BTCUSDT", "1h", 1, "LONG_ALLOWED", 0.8, "ok", ("DIRECTION",), True, {})
    assert validate_timeframe_result(result).passed is True
    stale = TimeframeResult("BTCUSDT", "1h", 1, "LONG_ALLOWED", 0.8, "ok", ("DIRECTION",), "stale", {})
    assert validate_timeframe_result(stale).passed is False
    invalid = TimeframeResult("BTCUSDT", "15m", 1, "LONG_ALLOWED", 0.8, "bad", (), True, {})
    assert validate_timeframe_result(invalid).passed is False


def test_direct_long_downgrades_to_probe_when_4h_conflicts():
    decision = build_multi_tf_decision(
        tf_4h=snap("4h", macd=-1, cci=-120, cvd_delta=-10),
        tf_1h=snap("1h", macd=1, cci=120, cvd_delta=5),
        tf_30m=snap("30m", macd=1, cci=130),
        tf_15m=snap("15m", rsi=55, cvd_delta=5),
        previous_15m_rsi=45,
    )
    assert decision.signal_type == "PROBE"
    assert decision.side == "LONG"
    assert decision.context_4h == "BEAR"
    assert "downgraded" in decision.reason


def test_direct_long_requires_all_confirmations_without_conflict():
    decision = build_multi_tf_decision(
        tf_4h=snap("4h", macd=1, cci=120, cvd_delta=10),
        tf_1h=snap("1h", macd=1, cci=120, cvd_delta=5),
        tf_30m=snap("30m", macd=1, cci=130),
        tf_15m=snap("15m", rsi=55, cvd_delta=5),
        previous_15m_rsi=45,
    )
    assert decision.signal_type == "DIRECT"
    assert decision.side == "LONG"


def test_probe_when_15m_trigger_is_missing_but_higher_tfs_confirm():
    decision = build_multi_tf_decision(
        tf_4h=snap("4h", macd=0, cci=0, cvd_delta=0),
        tf_1h=snap("1h", macd=1, cci=120, cvd_delta=5),
        tf_30m=snap("30m", macd=1, cci=130),
        tf_15m=snap("15m", rsi=52, cvd_delta=1),
        previous_15m_rsi=52,
    )
    assert decision.signal_type == "PROBE"
    assert decision.side == "LONG"


def test_no_trade_on_direction_conflict():
    decision = build_multi_tf_decision(
        tf_4h=snap("4h", macd=1, cci=120, cvd_delta=5),
        tf_1h=snap("1h", macd=1, cci=120, cvd_delta=5),
        tf_30m=snap("30m", cci=-130),
        tf_15m=snap("15m", rsi=55, cvd_delta=5),
        previous_15m_rsi=45,
    )
    assert decision.signal_type == "NO_TRADE"
    assert "direction conflict" in decision.reason


def test_stale_timeframe_quality_blocks_decision():
    decision = build_multi_tf_decision(
        tf_4h=snap("4h", macd=1, cci=120, cvd_delta=5),
        tf_1h=snap("1h", macd=1, cci=120, cvd_delta=5),
        tf_30m=snap("30m", cci=130),
        tf_15m=snap("15m", rsi=55, cvd_delta=5),
        previous_15m_rsi=45,
        quality_flags={"1h": "stale"},
    )
    assert decision.signal_type == "NO_TRADE"
    assert decision.quality_flag is False
    assert decision.reason == "data quality invalid"
