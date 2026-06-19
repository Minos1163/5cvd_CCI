from src.indicators.indicator_spec import (
    DEFAULT_INDICATOR_PARAMS,
    INDICATOR_PRIORITY,
    INDICATOR_RESPONSIBILITIES,
    classify_cci,
    classify_rsi,
    validate_indicator_usage,
)


def test_default_indicator_params_match_doc():
    assert DEFAULT_INDICATOR_PARAMS["MACD"] == {"fast": 12, "slow": 26, "signal": 9}
    assert DEFAULT_INDICATOR_PARAMS["RSI"] == {"period": 14}
    assert DEFAULT_INDICATOR_PARAMS["BOLL"] == {"period": 20, "std": 2.0}
    assert DEFAULT_INDICATOR_PARAMS["ATR"] == {"period": 14}


def test_priority_matches_doc():
    assert INDICATOR_PRIORITY == ("MACD", "CVD", "RSI", "CCI", "BOLL")


def test_atr_cannot_be_used_for_direction():
    ok, reason = validate_indicator_usage("ATR", "direction")
    assert ok is False
    assert "risk" in reason


def test_rsi_classification():
    assert classify_rsi(75) == "overheated"
    assert classify_rsi(25) == "oversold"
    assert classify_rsi(50) == "range"


def test_cci_classification():
    assert classify_cci(120) == "strong"
    assert classify_cci(-120) == "weak"
    assert classify_cci(0) == "neutral"
    assert INDICATOR_RESPONSIBILITIES["CVD"] == "fund_flow"
