import pytest

from src.core.models import Candle
from src.data.cvd_builder import build_cvd_points
from src.data.data_contract import (
    ACCOUNT_SNAPSHOT_FIELDS,
    AGGREGATION_RULES,
    CACHE_CONTRACT_FIELDS,
    CVD_SOURCES,
    CVDPoint,
    DATA_CONTRACT_FORBIDDEN,
    DATA_LAYERS,
    DATA_SOURCES,
    EXECUTION_FIELDS,
    FULL_CANDLE_FIELDS,
    INDICATOR_CONTRACT_FIELDS,
    INDICATOR_REQUIRED_OUTPUTS,
    MarketCandle,
    POSITION_SNAPSHOT_FIELDS,
    QUALITY_FLAGS,
    REQUIRED_CANDLE_FIELDS,
    REQUIRED_DATA_TYPES,
    STORAGE_CONTRACT,
    STRATEGY_CONTEXT_FIELDS,
    STRATEGY_EVENT_FIELDS,
    STRATEGY_EVENT_TYPES,
    SUPPORTED_TIMEFRAMES,
    TIMEFRAME_ROLES,
    UNIVERSE_ITEM_FIELDS,
    VERSION_FIELDS,
    IndicatorResult,
    StrategyContext,
    build_cvd_contract_points,
    judge_cvd_divergence,
    quality_allows_direct_entry,
    validate_indicator_result,
    validate_indicator_input,
    validate_market_candle,
    validate_ohlcv_contract,
    validate_required_fields,
    validate_strategy_context,
    validate_timeframe_utc_alignment,
)


def candle(**overrides) -> Candle:
    values = {
        "symbol": "BTCUSDT",
        "timeframe": "15m",
        "open_time": 0,
        "close_time": 900,
        "open": 100.0,
        "high": 105.0,
        "low": 95.0,
        "close": 101.0,
        "volume": 10.0,
        "quote_volume": 1_000.0,
        "trade_count": 20,
        "taker_buy_volume": 6.0,
    }
    values.update(overrides)
    return Candle(**values)


def test_data_contract_constants_match_doc():
    assert REQUIRED_DATA_TYPES == [
        "kline",
        "volume",
        "active_buy_sell",
        "position_or_funding",
        "universe",
    ]
    assert REQUIRED_CANDLE_FIELDS == [
        "open_time",
        "close_time",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "quote_volume",
        "trade_count",
    ]
    assert SUPPORTED_TIMEFRAMES == ["15m", "30m", "1h", "4h"]
    assert TIMEFRAME_ROLES["15m"] == "execution"
    assert TIMEFRAME_ROLES["4h"] == "background"


def test_validate_ohlcv_contract_accepts_valid_candle():
    result = validate_ohlcv_contract(candle())
    assert result.passed is True
    assert result.reason == "candle contract approved"


def test_validate_ohlcv_contract_rejects_bad_timeframe_and_ohlc():
    result = validate_ohlcv_contract(candle(timeframe="5m", high=99))
    assert result.passed is False
    assert "timeframe" in result.reason


def test_validate_ohlcv_contract_rejects_missing_volume_fields():
    result = validate_ohlcv_contract(candle(quote_volume=0, trade_count=0))
    assert result.passed is False
    assert "quote_volume" in result.reason


def test_aggregation_rules_match_doc():
    assert AGGREGATION_RULES == {
        "30m": "15m",
        "1h": ("15m", "30m"),
        "4h": "1h",
    }


def test_validate_timeframe_utc_alignment_accepts_closed_15m_grid():
    result = validate_timeframe_utc_alignment(candle(open_time=900, close_time=1800), base_close_time=1800)
    assert result.passed is True


def test_validate_timeframe_utc_alignment_rejects_future_leakage():
    result = validate_timeframe_utc_alignment(candle(open_time=1800, close_time=2700), base_close_time=1800)
    assert result.passed is False
    assert "future" in result.reason


def test_validate_indicator_input_requires_uniform_symbol_timeframe_and_order():
    candles = [candle(open_time=900, close_time=1800), candle(open_time=0, close_time=900)]
    result = validate_indicator_input(candles)
    assert result.passed is False
    assert "ordered" in result.reason

    ok = validate_indicator_input([candle(open_time=0, close_time=900), candle(open_time=900, close_time=1800)])
    assert ok.passed is True


def test_cvd_sources_match_doc():
    assert CVD_SOURCES == ["trades", "taker_buy_sell_estimate", "exchange_active_buy_sell"]


def test_build_cvd_contract_points_outputs_value_delta_slope():
    candles = [
        candle(open_time=0, close_time=900, close=100, volume=10, taker_buy_volume=6),
        candle(open_time=900, close_time=1800, close=101, volume=10, taker_buy_volume=7),
    ]
    points = build_cvd_contract_points(candles)
    assert points == [
        CVDPoint(close_time=900, cumulative=2.0, delta=2.0, slope=0.0, divergence="NONE"),
        CVDPoint(close_time=1800, cumulative=6.0, delta=4.0, slope=4.0, divergence="NONE"),
    ]
    assert build_cvd_points(candles) == points


def test_judge_cvd_divergence_detects_price_up_cvd_down():
    assert judge_cvd_divergence(price_delta=1.0, cvd_delta=-2.0) == "BEARISH"
    assert judge_cvd_divergence(price_delta=-1.0, cvd_delta=2.0) == "BULLISH"
    assert judge_cvd_divergence(price_delta=1.0, cvd_delta=2.0) == "NONE"


def market_candle(**overrides) -> MarketCandle:
    values = {
        "symbol": "BTCUSDT",
        "timeframe": "15m",
        "open_time": 0,
        "close_time": 900,
        "open": 100.0,
        "high": 105.0,
        "low": 95.0,
        "close": 101.0,
        "volume": 10.0,
        "quote_volume": 1_000.0,
        "trade_count": 20,
        "taker_buy_base_volume": 6.0,
        "taker_buy_quote_volume": 600.0,
        "is_closed": True,
        "source": "binance",
        "quality_flag": True,
    }
    values.update(overrides)
    return MarketCandle(**values)


def test_completed_doc_data_layers_and_sources():
    assert DATA_LAYERS == [
        "raw_market_data",
        "normalized_market_data",
        "multi_timeframe_data",
        "indicator_result_data",
        "strategy_context_data",
    ]
    assert DATA_SOURCES == [
        "kline",
        "volume",
        "active_buy_sell",
        "funding_rate",
        "open_interest",
        "universe",
        "execution",
        "account_position_snapshot",
    ]


def test_full_market_candle_fields_match_completed_doc():
    assert FULL_CANDLE_FIELDS == [
        "symbol",
        "timeframe",
        "open_time",
        "close_time",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "quote_volume",
        "trade_count",
        "taker_buy_base_volume",
        "taker_buy_quote_volume",
        "is_closed",
        "source",
        "quality_flag",
    ]
    assert QUALITY_FLAGS == [True, False, "degraded", "stale"]


def test_validate_market_candle_requires_closed_quality_true_data():
    check = validate_market_candle(market_candle())
    assert check.passed is True
    assert quality_allows_direct_entry(True) is True
    assert quality_allows_direct_entry("degraded") is False
    assert quality_allows_direct_entry("stale") is False


def test_validate_market_candle_rejects_unclosed_or_bad_quality_data():
    result = validate_market_candle(market_candle(is_closed=False))
    assert result.passed is False
    assert "closed" in result.reason


def test_indicator_contract_fields_and_required_outputs_match_doc():
    assert INDICATOR_CONTRACT_FIELDS == [
        "name",
        "symbol",
        "timeframe",
        "value",
        "signal",
        "trend",
        "strength",
        "timestamp",
        "metadata",
        "quality_flag",
    ]
    assert INDICATOR_REQUIRED_OUTPUTS["MACD"] == ["macd_line", "signal_line", "histogram", "histogram_slope", "cross_state"]
    assert INDICATOR_REQUIRED_OUTPUTS["EMA"] == [
        "ema_9",
        "ema_21",
        "ema_50",
        "ema_200",
        "ema50_slope",
        "ema9_21_gap",
        "bars_since_ema50_cross",
        "bars_since_ema200_cross",
    ]
    assert INDICATOR_REQUIRED_OUTPUTS["ATR"] == ["atr", "atr_pct", "volatility_state"]


def test_validate_indicator_result_blocks_false_or_stale_quality():
    result = IndicatorResult(
        name="MACD",
        symbol="BTCUSDT",
        timeframe="15m",
        value={"macd_line": 1, "signal_line": 0, "histogram": 1, "histogram_slope": 0.1, "cross_state": "GOLDEN"},
        signal="LONG",
        trend="UP",
        strength=0.8,
        timestamp=900,
        metadata={},
        quality_flag=True,
    )
    assert validate_indicator_result(result).passed is True
    stale = IndicatorResult(**{**result.__dict__, "quality_flag": "stale"})
    assert validate_indicator_result(stale).passed is False


def test_strategy_context_fields_and_validation_match_doc():
    assert STRATEGY_CONTEXT_FIELDS[0] == "symbol"
    context = StrategyContext(
        symbol="BTCUSDT",
        timestamp=900,
        market_state_4h="BULL",
        trend_state_1h="LONG_ALLOWED",
        confirm_state_30m="CONFIRMED",
        trigger_state_15m="DIRECT",
        indicators_15m={},
        indicators_30m={},
        indicators_1h={},
        indicators_4h={},
        risk_snapshot={},
        position_snapshot={},
        cooldown_state={},
        signal_candidate={},
        quality_flag=True,
    )
    assert validate_strategy_context(context).passed is True
    bad = StrategyContext(**{**context.__dict__, "quality_flag": False})
    assert validate_strategy_context(bad).passed is False


def test_event_execution_account_position_and_universe_fields_match_doc():
    assert STRATEGY_EVENT_FIELDS == ["event_id", "symbol", "timeframe", "event_type", "state_before", "state_after", "reason", "score", "timestamp", "metadata"]
    assert "DATA_INVALID" in STRATEGY_EVENT_TYPES
    assert EXECUTION_FIELDS[:4] == ["order_id", "client_order_id", "symbol", "side"]
    assert ACCOUNT_SNAPSHOT_FIELDS[:3] == ["account_equity", "available_margin", "used_margin"]
    assert POSITION_SNAPSHOT_FIELDS[:4] == ["symbol", "side", "position_qty", "entry_price"]
    assert UNIVERSE_ITEM_FIELDS[-1] == "correlation_group"


def test_validate_required_fields_reports_missing_fields():
    check = validate_required_fields({"symbol": "BTCUSDT"}, ["symbol", "side"], "execution")
    assert check.passed is False
    assert "side" in check.reason
    ok = validate_required_fields({"symbol": "BTCUSDT", "side": "LONG"}, ["symbol", "side"], "execution")
    assert ok.passed is True


def test_cache_version_storage_and_forbidden_contracts_match_doc():
    assert CACHE_CONTRACT_FIELDS == ["ttl", "update_frequency", "hit_condition", "no_future_cache"]
    assert VERSION_FIELDS == ["raw_data_version", "aggregation_version", "indicator_version", "strategy_version", "risk_version", "execution_version"]
    assert STORAGE_CONTRACT["hot"] == ["recent_market", "current_position", "current_signal", "current_risk_state"]
    assert "let backtest and live use different field sets" in DATA_CONTRACT_FORBIDDEN
