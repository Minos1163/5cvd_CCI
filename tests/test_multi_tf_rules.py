from src.context.multi_tf_rules import (
    build_multi_tf_decision,
    evaluate_15m_trigger,
    evaluate_1h_permission,
    evaluate_30m_quality,
    evaluate_4h_context,
)
from src.core.models import IndicatorSnapshot


def snap(timeframe: str, **kwargs) -> IndicatorSnapshot:
    return IndicatorSnapshot(symbol="BTCUSDT", timeframe=timeframe, close_time=1, **kwargs)


def test_4h_is_reference_context_only():
    assert evaluate_4h_context(snap("4h", macd=1, cci=120, cvd_delta=10)).value == "BULL"
    assert evaluate_4h_context(snap("4h", macd=-1, cci=-120, cvd_delta=-10)).value == "BEAR"
    assert evaluate_4h_context(snap("4h", macd=0, cci=0, cvd_delta=0)).value == "NEUTRAL"


def test_1h_permission_uses_macd_cci_cvd():
    assert evaluate_1h_permission(snap("1h", macd=1, cci=120, cvd_delta=5)).value == "LONG_ALLOWED"
    assert evaluate_1h_permission(snap("1h", macd=-1, cci=-120, cvd_delta=-5)).value == "SHORT_ALLOWED"
    assert evaluate_1h_permission(snap("1h", macd=1, cci=-120, cvd_delta=5)).value == "NO_TRADE"


def test_30m_quality_uses_cci():
    assert evaluate_30m_quality(snap("30m", cci=120)).value == "LONG_CONFIRM"
    assert evaluate_30m_quality(snap("30m", cci=-120)).value == "SHORT_CONFIRM"
    assert evaluate_30m_quality(snap("30m", cci=0)).value == "WEAK"


def test_15m_trigger_uses_rsi_reclaim_and_cvd():
    assert evaluate_15m_trigger(snap("15m", rsi=55, cvd_delta=5), previous_rsi=45).value == "LONG_TRIGGER"
    assert evaluate_15m_trigger(snap("15m", rsi=45, cvd_delta=-5), previous_rsi=55).value == "SHORT_TRIGGER"
    assert evaluate_15m_trigger(snap("15m", rsi=50, cvd_delta=0), previous_rsi=50).value == "WAIT"


def test_direct_long_requires_all_confirmations():
    decision = build_multi_tf_decision(
        tf_4h=snap("4h", macd=-1, cci=-120, cvd_delta=-10),
        tf_1h=snap("1h", macd=1, cci=120, cvd_delta=5),
        tf_30m=snap("30m", cci=130),
        tf_15m=snap("15m", rsi=55, cvd_delta=5),
        previous_15m_rsi=45,
    )
    assert decision.signal_type == "DIRECT"
    assert decision.side == "LONG"
    assert decision.context_4h == "BEAR"


def test_probe_when_15m_trigger_is_missing_but_higher_tfs_confirm():
    decision = build_multi_tf_decision(
        tf_4h=snap("4h", macd=0, cci=0, cvd_delta=0),
        tf_1h=snap("1h", macd=1, cci=120, cvd_delta=5),
        tf_30m=snap("30m", cci=130),
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
