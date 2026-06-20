from src.data.data_contract import INDICATOR_REQUIRED_OUTPUTS
from src.indicators.indicator_spec import (
    DEFAULT_INDICATOR_PARAMS,
    GLOBAL_FORBIDDEN_INDICATOR_ACTIONS,
    INDICATOR_CACHE_FIELDS,
    INDICATOR_CONFLICT_PRIORITY,
    INDICATOR_FORBIDDEN_USAGES,
    INDICATOR_INPUT_FIELDS,
    INDICATOR_NAMES,
    INDICATOR_OUTPUT_FIELDS,
    INDICATOR_RESPONSIBILITIES,
    TIMEFRAME_INDICATOR_MAP,
    classify_cci,
    classify_rsi,
    quality_allows_signal_use,
    required_outputs_for,
    validate_indicator_input_contract,
    validate_indicator_usage,
)


def test_default_indicator_params_match_doc():
    assert DEFAULT_INDICATOR_PARAMS["MACD"] == {"fast": 12, "slow": 26, "signal": 9}
    assert DEFAULT_INDICATOR_PARAMS["CCI"] == {"period": 20}
    assert DEFAULT_INDICATOR_PARAMS["BOLL"] == {"period": 20, "std": 2.0}
    assert DEFAULT_INDICATOR_PARAMS["EMA"] == {"fast": 9, "slow": 21, "trend": 50, "gate": 200, "slope_lookback": 5}
    assert DEFAULT_INDICATOR_PARAMS["ATR"] == {"period": 14}
    assert DEFAULT_INDICATOR_PARAMS["CVD"] == {}


def test_indicator_names_responsibilities_and_contract_fields_match_doc():
    assert INDICATOR_NAMES == ("MACD", "CCI", "BOLL", "EMA", "CVD", "ATR")
    assert INDICATOR_RESPONSIBILITIES == {
        "MACD": "trend_momentum",
        "CCI": "strength_deviation_recovery",
        "BOLL": "volatility_structure",
        "EMA": "trend_direction_quality_momentum",
        "CVD": "active_buy_sell_pressure",
        "ATR": "volatility_stop_position_risk",
    }
    assert "is_closed" in INDICATOR_INPUT_FIELDS
    assert "quality_flag" in INDICATOR_INPUT_FIELDS
    assert INDICATOR_OUTPUT_FIELDS == (
        "name",
        "symbol",
        "timeframe",
        "timestamp",
        "value",
        "signal",
        "trend",
        "strength",
        "quality_flag",
        "metadata",
    )


def test_required_outputs_are_reused_from_data_contract():
    assert required_outputs_for("MACD") == tuple(INDICATOR_REQUIRED_OUTPUTS["MACD"])
    assert required_outputs_for("CVD") == tuple(INDICATOR_REQUIRED_OUTPUTS["CVD"])
    assert required_outputs_for("ATR") == tuple(INDICATOR_REQUIRED_OUTPUTS["ATR"])


def test_conflict_priority_and_timeframe_map_match_doc():
    assert INDICATOR_CONFLICT_PRIORITY == (
        "data_quality",
        "cvd_divergence",
        "ema200_direction_gate",
        "macd_trend_direction",
        "ema50_trend_quality",
        "cci_strength",
        "boll_structure",
        "ema9_21_momentum",
        "atr_risk",
    )
    assert TIMEFRAME_INDICATOR_MAP["4h"] == ("EMA", "MACD", "BOLL", "CCI")
    assert TIMEFRAME_INDICATOR_MAP["1h"] == ("EMA", "MACD", "CCI", "CVD")
    assert TIMEFRAME_INDICATOR_MAP["30m"] == ("EMA", "MACD", "BOLL", "CCI", "CVD")
    assert TIMEFRAME_INDICATOR_MAP["15m"] == ("EMA", "MACD", "CVD", "BOLL")


def test_forbidden_usage_rules_are_explicit():
    ok, reason = validate_indicator_usage("ATR", "direction")
    assert ok is False
    assert "forbidden" in reason
    ok, reason = validate_indicator_usage("MACD", "sole_entry")
    assert ok is False
    assert "forbidden" in reason
    ok, reason = validate_indicator_usage("EMA", "trend_quality")
    assert ok is True
    assert reason == "EMA allowed for trend_quality"
    assert "must_trade" in GLOBAL_FORBIDDEN_INDICATOR_ACTIONS
    assert "countertrend_direct" in INDICATOR_FORBIDDEN_USAGES["EMA"]
    assert "sole_direction" in INDICATOR_FORBIDDEN_USAGES["CVD"]


def test_quality_signal_semantics_are_conservative():
    assert quality_allows_signal_use(True) is True
    assert quality_allows_signal_use("degraded") is True
    assert quality_allows_signal_use(False) is False
    assert quality_allows_signal_use("stale") is False


def test_validate_indicator_input_contract_requires_closed_quality_fields():
    required = {field: 1 for field in INDICATOR_INPUT_FIELDS}
    required["is_closed"] = True
    required["quality_flag"] = True
    assert validate_indicator_input_contract(required).passed is True

    missing_closed = dict(required)
    missing_closed.pop("is_closed")
    assert validate_indicator_input_contract(missing_closed).passed is False

    unfinished = dict(required)
    unfinished["is_closed"] = False
    assert validate_indicator_input_contract(unfinished).passed is False

    stale = dict(required)
    stale["quality_flag"] = "stale"
    assert validate_indicator_input_contract(stale).passed is False


def test_rsi_and_cci_classification():
    assert classify_rsi(75) == "overheated"
    assert classify_rsi(25) == "oversold"
    assert classify_rsi(50) == "range"
    assert classify_cci(120) == "strong"
    assert classify_cci(-120) == "weak"
    assert classify_cci(0) == "neutral"


def test_cache_fields_match_doc():
    assert INDICATOR_CACHE_FIELDS == ("version", "timestamp", "timeframe", "indicator", "quality_flag")
