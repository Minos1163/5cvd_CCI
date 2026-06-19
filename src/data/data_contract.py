from __future__ import annotations

from dataclasses import dataclass

from src.core.models import Candle


REQUIRED_DATA_TYPES = ["kline", "volume", "active_buy_sell", "position_or_funding", "universe"]
DATA_LAYERS = [
    "raw_market_data",
    "normalized_market_data",
    "multi_timeframe_data",
    "indicator_result_data",
    "strategy_context_data",
]
DATA_SOURCES = [
    "kline",
    "volume",
    "active_buy_sell",
    "funding_rate",
    "open_interest",
    "universe",
    "execution",
    "account_position_snapshot",
]
REQUIRED_CANDLE_FIELDS = [
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
FULL_CANDLE_FIELDS = [
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
SUPPORTED_TIMEFRAMES = ["15m", "30m", "1h", "4h"]
TIMEFRAME_SECONDS = {"15m": 900, "30m": 1800, "1h": 3600, "4h": 14400}
TIMEFRAME_ROLES = {"15m": "execution", "30m": "confirmation", "1h": "direction", "4h": "background"}
AGGREGATION_RULES = {"30m": "15m", "1h": ("15m", "30m"), "4h": "1h"}
CVD_SOURCES = ["trades", "taker_buy_sell_estimate", "exchange_active_buy_sell"]
QUALITY_FLAGS = [True, False, "degraded", "stale"]

INDICATOR_CONTRACT_FIELDS = [
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
INDICATOR_REQUIRED_OUTPUTS = {
    "MACD": ["macd_line", "signal_line", "histogram", "histogram_slope", "cross_state"],
    "RSI": ["rsi", "rsi_slope", "overbought_flag", "oversold_flag", "midline_state"],
    "CCI": ["cci", "cci_slope", "extreme_flag", "recovery_flag"],
    "BOLL": [
        "middle_band",
        "upper_band",
        "lower_band",
        "band_width",
        "band_expansion_flag",
        "band_contraction_flag",
        "price_position",
    ],
    "CVD": ["cvd", "cvd_delta", "cvd_slope", "cvd_divergence_flag", "buy_pressure", "sell_pressure"],
    "ATR": ["atr", "atr_pct", "volatility_state"],
}
STRATEGY_CONTEXT_FIELDS = [
    "symbol",
    "timestamp",
    "market_state_4h",
    "trend_state_1h",
    "confirm_state_30m",
    "trigger_state_15m",
    "indicators_15m",
    "indicators_30m",
    "indicators_1h",
    "indicators_4h",
    "risk_snapshot",
    "position_snapshot",
    "cooldown_state",
    "signal_candidate",
    "quality_flag",
]
STRATEGY_EVENT_FIELDS = [
    "event_id",
    "symbol",
    "timeframe",
    "event_type",
    "state_before",
    "state_after",
    "reason",
    "score",
    "timestamp",
    "metadata",
]
STRATEGY_EVENT_TYPES = [
    "SIGNAL_CREATED",
    "WATCH_ENTERED",
    "PROBE_ENTERED",
    "DIRECT_ENTERED",
    "POSITION_MANAGED",
    "EXIT_TRIGGERED",
    "RISK_BLOCKED",
    "DATA_INVALID",
]
EXECUTION_FIELDS = [
    "order_id",
    "client_order_id",
    "symbol",
    "side",
    "order_type",
    "quantity",
    "price",
    "reduce_only",
    "position_side",
    "status",
    "filled_qty",
    "avg_price",
    "commission",
    "latency_ms",
    "reject_reason",
    "raw_response",
]
ACCOUNT_SNAPSHOT_FIELDS = [
    "account_equity",
    "available_margin",
    "used_margin",
    "unrealized_pnl",
    "realized_pnl",
    "max_drawdown",
    "daily_pnl",
    "weekly_pnl",
]
POSITION_SNAPSHOT_FIELDS = [
    "symbol",
    "side",
    "position_qty",
    "entry_price",
    "mark_price",
    "unrealized_pnl",
    "leverage",
    "stop_price",
    "take_profit_price",
    "position_age",
]
UNIVERSE_ITEM_FIELDS = [
    "symbol",
    "base_asset",
    "quote_asset",
    "market_cap_rank",
    "volume_rank",
    "tier",
    "tradable",
    "listed_time",
    "delisting_flag",
    "correlation_group",
]
CACHE_CONTRACT_FIELDS = ["ttl", "update_frequency", "hit_condition", "no_future_cache"]
VERSION_FIELDS = [
    "raw_data_version",
    "aggregation_version",
    "indicator_version",
    "strategy_version",
    "risk_version",
    "execution_version",
]
STORAGE_CONTRACT = {
    "hot": ["recent_market", "current_position", "current_signal", "current_risk_state"],
    "warm": ["recent_trades", "recent_strategy_events", "recent_execution_logs"],
    "cold": ["historical_backtest_data", "long_term_trade_audit", "historical_performance_report"],
}
DATA_CONTRACT_FORBIDDEN = [
    "mix timezones",
    "reuse same field name with different meaning",
    "let indicators read raw exchange responses",
    "let strategy bypass normalized objects",
    "use presentation data as strategy data",
    "use patch fields in main decisions",
    "let backtest and live use different field sets",
]


@dataclass(frozen=True)
class ContractCheck:
    name: str
    passed: bool
    reason: str


@dataclass(frozen=True)
class MarketCandle:
    symbol: str
    timeframe: str
    open_time: int
    close_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    quote_volume: float
    trade_count: int
    taker_buy_base_volume: float
    taker_buy_quote_volume: float
    is_closed: bool
    source: str
    quality_flag: bool | str = True


@dataclass(frozen=True)
class IndicatorResult:
    name: str
    symbol: str
    timeframe: str
    value: dict
    signal: str
    trend: str
    strength: float
    timestamp: int
    metadata: dict
    quality_flag: bool | str = True


@dataclass(frozen=True)
class StrategyContext:
    symbol: str
    timestamp: int
    market_state_4h: str
    trend_state_1h: str
    confirm_state_30m: str
    trigger_state_15m: str
    indicators_15m: dict
    indicators_30m: dict
    indicators_1h: dict
    indicators_4h: dict
    risk_snapshot: dict
    position_snapshot: dict
    cooldown_state: dict
    signal_candidate: dict
    quality_flag: bool | str = True


@dataclass(frozen=True)
class CVDPoint:
    close_time: int
    cumulative: float
    delta: float
    slope: float
    divergence: str


def normalize_timeframe(timeframe: str) -> str:
    return timeframe.strip().lower()


def market_candle_to_candle(market_candle: MarketCandle) -> Candle:
    return Candle(
        symbol=market_candle.symbol,
        timeframe=market_candle.timeframe,
        open_time=market_candle.open_time,
        close_time=market_candle.close_time,
        open=market_candle.open,
        high=market_candle.high,
        low=market_candle.low,
        close=market_candle.close,
        volume=market_candle.volume,
        quote_volume=market_candle.quote_volume,
        trade_count=market_candle.trade_count,
        taker_buy_volume=market_candle.taker_buy_base_volume,
    )


def validate_ohlcv_contract(candle: Candle) -> ContractCheck:
    timeframe = normalize_timeframe(candle.timeframe)
    if timeframe not in SUPPORTED_TIMEFRAMES:
        return ContractCheck("ohlcv_contract", False, f"unsupported timeframe: {candle.timeframe}")
    if candle.close_time <= candle.open_time:
        return ContractCheck("ohlcv_contract", False, "close_time must be greater than open_time")
    if candle.high < max(candle.open, candle.close) or candle.low > min(candle.open, candle.close):
        return ContractCheck("ohlcv_contract", False, "invalid OHLC relationship")
    if min(candle.open, candle.high, candle.low, candle.close) <= 0:
        return ContractCheck("ohlcv_contract", False, "prices must be positive")
    if candle.volume <= 0:
        return ContractCheck("ohlcv_contract", False, "volume must be positive")
    if candle.quote_volume <= 0:
        return ContractCheck("ohlcv_contract", False, "quote_volume must be positive")
    if candle.trade_count <= 0:
        return ContractCheck("ohlcv_contract", False, "trade_count must be positive")
    return ContractCheck("ohlcv_contract", True, "candle contract approved")


def validate_market_candle(market_candle: MarketCandle) -> ContractCheck:
    if not market_candle.is_closed:
        return ContractCheck("market_candle", False, "market candle must be closed")
    if market_candle.quality_flag not in QUALITY_FLAGS:
        return ContractCheck("market_candle", False, "unsupported quality_flag")
    if not market_candle.source:
        return ContractCheck("market_candle", False, "source must be present")
    return validate_ohlcv_contract(market_candle_to_candle(market_candle))


def quality_allows_direct_entry(quality_flag: bool | str) -> bool:
    return quality_flag is True


def validate_indicator_result(result: IndicatorResult) -> ContractCheck:
    if result.quality_flag in {False, "stale"}:
        return ContractCheck("indicator_result", False, "indicator quality does not allow main-chain use")
    missing = sorted(set(INDICATOR_REQUIRED_OUTPUTS.get(result.name.upper(), [])) - set(result.value))
    if missing:
        return ContractCheck("indicator_result", False, f"missing indicator fields: {missing}")
    return ContractCheck("indicator_result", True, "indicator result approved")


def validate_strategy_context(context: StrategyContext) -> ContractCheck:
    if context.quality_flag in {False, "stale"}:
        return ContractCheck("strategy_context", False, "strategy context quality does not allow direct entry")
    if not context.symbol or context.timestamp <= 0:
        return ContractCheck("strategy_context", False, "symbol and positive timestamp are required")
    return ContractCheck("strategy_context", True, "strategy context approved")


def validate_required_fields(payload: dict, required_fields: list[str], name: str) -> ContractCheck:
    missing = sorted(field for field in required_fields if field not in payload)
    if missing:
        return ContractCheck(name, False, f"missing required fields: {missing}")
    return ContractCheck(name, True, f"{name} fields approved")


def validate_timeframe_utc_alignment(candle: Candle, base_close_time: int) -> ContractCheck:
    timeframe = normalize_timeframe(candle.timeframe)
    if timeframe not in TIMEFRAME_SECONDS:
        return ContractCheck("timeframe_alignment", False, f"unsupported timeframe: {candle.timeframe}")
    seconds = TIMEFRAME_SECONDS[timeframe]
    if candle.open_time % seconds != 0 or candle.close_time % seconds != 0:
        return ContractCheck("timeframe_alignment", False, "candle is not aligned to UTC timeframe grid")
    if candle.close_time > base_close_time:
        return ContractCheck("timeframe_alignment", False, "future data leakage is not allowed")
    return ContractCheck("timeframe_alignment", True, "candle is UTC aligned and closed")


def validate_indicator_input(candles: list[Candle]) -> ContractCheck:
    if not candles:
        return ContractCheck("indicator_input", False, "candles must not be empty")
    first_symbol = candles[0].symbol
    first_timeframe = normalize_timeframe(candles[0].timeframe)
    previous_open_time = -1
    for item in candles:
        if item.symbol != first_symbol:
            return ContractCheck("indicator_input", False, "candles must use one symbol")
        if normalize_timeframe(item.timeframe) != first_timeframe:
            return ContractCheck("indicator_input", False, "candles must use one timeframe")
        if item.open_time <= previous_open_time:
            return ContractCheck("indicator_input", False, "candles must be ordered by open_time")
        check = validate_ohlcv_contract(item)
        if not check.passed:
            return ContractCheck("indicator_input", False, check.reason)
        previous_open_time = item.open_time
    return ContractCheck("indicator_input", True, "candles: list[OHLCV] approved")


def judge_cvd_divergence(price_delta: float, cvd_delta: float) -> str:
    if price_delta > 0 and cvd_delta < 0:
        return "BEARISH"
    if price_delta < 0 and cvd_delta > 0:
        return "BULLISH"
    return "NONE"


def build_cvd_contract_points(candles: list[Candle]) -> list[CVDPoint]:
    total = 0.0
    previous_cumulative = 0.0
    previous_close = None
    points = []
    for item in candles:
        sell_volume = max(item.volume - item.taker_buy_volume, 0.0)
        delta = item.taker_buy_volume - sell_volume
        total += delta
        slope = total - previous_cumulative if points else 0.0
        price_delta = 0.0 if previous_close is None else item.close - previous_close
        points.append(
            CVDPoint(
                close_time=item.close_time,
                cumulative=total,
                delta=delta,
                slope=slope,
                divergence=judge_cvd_divergence(price_delta, delta),
            )
        )
        previous_cumulative = total
        previous_close = item.close
    return points
