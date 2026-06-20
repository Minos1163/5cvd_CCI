from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from src.data.data_contract import INDICATOR_REQUIRED_OUTPUTS, QUALITY_FLAGS


DEFAULT_INDICATOR_PARAMS = {
    "MACD": {"fast": 12, "slow": 26, "signal": 9},
    "CCI": {"period": 20},
    "BOLL": {"period": 20, "std": 2.0},
    "EMA": {"fast": 9, "slow": 21, "trend": 50, "gate": 200, "slope_lookback": 5},
    "CVD": {},
    "ATR": {"period": 14},
}

INDICATOR_NAMES = ("MACD", "CCI", "BOLL", "EMA", "CVD", "ATR")
INDICATOR_RESPONSIBILITIES = {
    "MACD": "trend_momentum",
    "CCI": "strength_deviation_recovery",
    "BOLL": "volatility_structure",
    "EMA": "trend_direction_quality_momentum",
    "CVD": "active_buy_sell_pressure",
    "ATR": "volatility_stop_position_risk",
}
INDICATOR_INPUT_FIELDS = (
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
    "quality_flag",
)
INDICATOR_OUTPUT_FIELDS = (
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
INDICATOR_CONFLICT_PRIORITY = (
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
INDICATOR_PRIORITY = INDICATOR_CONFLICT_PRIORITY
TIMEFRAME_INDICATOR_MAP = {
    "4h": ("EMA", "MACD", "BOLL", "CCI"),
    "1h": ("EMA", "MACD", "CCI", "CVD"),
    "30m": ("EMA", "MACD", "BOLL", "CCI", "CVD"),
    "15m": ("EMA", "MACD", "CVD", "BOLL"),
}
INDICATOR_CACHE_FIELDS = ("version", "timestamp", "timeframe", "indicator", "quality_flag")
INDICATOR_FORBIDDEN_USAGES = {
    "MACD": ("sole_entry", "position_size", "unfinished_bar_final", "execution_reinterpretation"),
    "CCI": ("sole_direction", "risk_control", "only_trend_proof"),
    "BOLL": ("sole_direction", "position_size", "replace_trend_logic"),
    "EMA": ("sole_entry", "position_size", "countertrend_direct", "unfinished_bar_final"),
    "CVD": ("sole_direction", "replace_price_structure", "force_signal_without_data", "execution_priority"),
    "ATR": ("direction", "long_short_signal", "replace_trend", "non_risk_module_mixing"),
}
GLOBAL_FORBIDDEN_INDICATOR_ACTIONS = (
    "create_order",
    "final_position_size",
    "bypass_state_machine",
    "must_trade",
)


@dataclass(frozen=True)
class IndicatorSpecCheck:
    passed: bool
    reason: str


def required_outputs_for(indicator: str) -> tuple[str, ...]:
    return tuple(INDICATOR_REQUIRED_OUTPUTS.get(indicator.upper(), ()))


def quality_allows_signal_use(quality_flag: bool | str) -> bool:
    return quality_flag in (True, "degraded")


def validate_indicator_input_contract(payload: Mapping[str, object]) -> IndicatorSpecCheck:
    missing = sorted(field for field in INDICATOR_INPUT_FIELDS if field not in payload)
    if missing:
        return IndicatorSpecCheck(False, f"missing indicator input fields: {missing}")
    if payload["is_closed"] is not True:
        return IndicatorSpecCheck(False, "indicator input candle must be closed")
    if payload["quality_flag"] not in QUALITY_FLAGS:
        return IndicatorSpecCheck(False, "unsupported quality_flag")
    if not quality_allows_signal_use(payload["quality_flag"]):
        return IndicatorSpecCheck(False, "quality_flag cannot drive indicator signal use")
    return IndicatorSpecCheck(True, "indicator input contract approved")


def validate_indicator_usage(indicator: str, usage: str) -> tuple[bool, str]:
    key = indicator.upper()
    if key not in INDICATOR_NAMES:
        return False, f"unknown indicator: {indicator}"
    normalized_usage = usage.strip().lower()
    if normalized_usage in GLOBAL_FORBIDDEN_INDICATOR_ACTIONS:
        return False, f"{normalized_usage} is globally forbidden for indicator layer"
    if normalized_usage in INDICATOR_FORBIDDEN_USAGES.get(key, ()):
        return False, f"{key} usage forbidden: {normalized_usage}"
    return True, f"{key} allowed for {normalized_usage}"


def classify_rsi(value: float) -> str:
    if value > 70:
        return "overheated"
    if value < 30:
        return "oversold"
    if 40 <= value <= 60:
        return "range"
    return "neutral"


def classify_cci(value: float) -> str:
    if value > 100:
        return "strong"
    if value < -100:
        return "weak"
    return "neutral"
