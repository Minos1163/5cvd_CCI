from __future__ import annotations

from dataclasses import dataclass

from src.core.models import Candle


BACKTEST_PROCESSING_ORDER = [
    "update_history",
    "update_indicators",
    "update_multi_timeframe_context",
    "update_state",
    "check_exit",
    "check_reduce",
    "check_add",
    "check_entry",
    "record_events",
]

REQUIRED_TRADE_FIELDS = [
    "symbol",
    "side",
    "entry_time",
    "entry_price",
    "exit_time",
    "exit_price",
    "size",
    "leverage",
    "stop_price",
    "take_profit_price",
    "pnl",
    "pnl_pct",
    "reason_enter",
    "reason_exit",
    "state_before",
    "state_after",
]

REQUIRED_PERFORMANCE_FIELDS = [
    "total_return",
    "annualized_return",
    "max_drawdown",
    "win_rate",
    "profit_factor",
    "sharpe",
    "sortino",
    "average_rr",
    "average_holding_time",
    "symbol_performance",
    "portfolio_performance",
    "probe_vs_direct",
    "long_vs_short",
]

DATA_QUALITY_CHECKS = [
    "time_continuity",
    "missing_bar",
    "long_wick",
    "extreme_gap",
    "price_precision",
    "zero_volume",
    "duplicate_timestamp",
]

REQUIRED_STATE_TRANSITION_FIELDS = [
    "current_state",
    "target_state",
    "reason",
    "transition_time",
    "transition_price",
    "timeframe",
]

STRATIFIED_ANALYSIS_DIMENSIONS = [
    "symbol",
    "timeframe",
    "market_regime",
    "side",
    "signal_type",
    "single_vs_portfolio",
    "volatility_regime",
]

REQUIRED_OUTPUT_ARTIFACTS = [
    "equity_curve",
    "trade_detail",
    "performance_summary",
    "drawdown_summary",
    "state_machine_stats",
    "rejection_stats",
    "failure_samples",
    "strategy_version",
    "parameter_snapshot",
]


@dataclass(frozen=True)
class ProtocolCheck:
    name: str
    passed: bool
    reason: str


@dataclass(frozen=True)
class WalkForwardWindow:
    train_start: int
    train_end: int
    validation_start: int
    validation_end: int


def validate_processing_order(order: list[str]) -> ProtocolCheck:
    if order == BACKTEST_PROCESSING_ORDER:
        return ProtocolCheck("processing_order", True, "fixed processing order approved")
    return ProtocolCheck("processing_order", False, "must use fixed processing order with exits before entries")


def validate_candle_continuity(candles: list[Candle], timeframe_seconds: int) -> list[ProtocolCheck]:
    if timeframe_seconds <= 0:
        raise ValueError("timeframe_seconds must be positive")
    results = []
    seen = set()
    sorted_candles = sorted(candles, key=lambda item: item.open_time)
    for index, item in enumerate(sorted_candles):
        if item.open_time in seen:
            results.append(ProtocolCheck("duplicate_timestamp", False, f"duplicate timestamp {item.open_time}"))
        seen.add(item.open_time)
        if item.volume <= 0:
            results.append(ProtocolCheck("zero_volume", False, f"zero volume at {item.open_time}"))
        if item.high < max(item.open, item.close) or item.low > min(item.open, item.close):
            results.append(ProtocolCheck("ohlc_integrity", False, f"invalid OHLC at {item.open_time}"))
        if index > 0:
            expected = sorted_candles[index - 1].open_time + timeframe_seconds
            if item.open_time != expected:
                results.append(ProtocolCheck("time_gap", False, f"gap before {item.open_time}"))
    if not results:
        results.append(ProtocolCheck("candle_continuity", True, "candles are continuous"))
    return results


def validate_data_quality(
    candles: list[Candle],
    timeframe_seconds: int,
    max_wick_ratio: float = 0.80,
    max_gap_pct: float = 0.20,
    max_price_decimals: int = 8,
) -> list[ProtocolCheck]:
    results = validate_candle_continuity(candles, timeframe_seconds)
    sorted_candles = sorted(candles, key=lambda item: item.open_time)
    previous_close = None
    for item in sorted_candles:
        body = abs(item.close - item.open)
        candle_range = item.high - item.low
        if candle_range <= 0:
            results.append(ProtocolCheck("ohlc_integrity", False, f"invalid range at {item.open_time}"))
        elif body > 0:
            upper_wick = item.high - max(item.open, item.close)
            lower_wick = min(item.open, item.close) - item.low
            if max(upper_wick, lower_wick) / candle_range > max_wick_ratio:
                results.append(ProtocolCheck("long_wick", False, f"long wick at {item.open_time}"))
        if previous_close is not None and previous_close > 0:
            gap_pct = abs(item.open - previous_close) / previous_close
            if gap_pct > max_gap_pct:
                results.append(ProtocolCheck("extreme_gap", False, f"extreme gap at {item.open_time}"))
        for field_name in ("open", "high", "low", "close"):
            if _decimal_places(getattr(item, field_name)) > max_price_decimals:
                results.append(ProtocolCheck("price_precision", False, f"price precision too high at {item.open_time}"))
                break
        previous_close = item.close
    if all(result.passed for result in results):
        return [ProtocolCheck("data_quality", True, "data quality approved")]
    return results


def validate_timeframe_alignment(
    base_close_time: int,
    higher_close_time: int,
    higher_timeframe_seconds: int,
) -> ProtocolCheck:
    if higher_timeframe_seconds <= 0:
        raise ValueError("higher_timeframe_seconds must be positive")
    if higher_close_time > base_close_time:
        return ProtocolCheck("timeframe_alignment", False, "future higher timeframe bar is not allowed")
    if higher_close_time % higher_timeframe_seconds != 0:
        return ProtocolCheck("timeframe_alignment", False, "higher timeframe close is misaligned")
    return ProtocolCheck("timeframe_alignment", True, "higher timeframe uses completed UTC-aligned bar")


def validate_state_transition_fields(fields: set[str]) -> ProtocolCheck:
    missing = sorted(set(REQUIRED_STATE_TRANSITION_FIELDS) - fields)
    if missing:
        return ProtocolCheck("state_transition_fields", False, f"missing state transition fields: {missing}")
    return ProtocolCheck("state_transition_fields", True, "state transition fields complete")


def validate_stratified_analysis_dimensions(dimensions: set[str]) -> ProtocolCheck:
    missing = sorted(set(STRATIFIED_ANALYSIS_DIMENSIONS) - dimensions)
    if missing:
        return ProtocolCheck("stratified_analysis", False, f"missing analysis dimensions: {missing}")
    return ProtocolCheck("stratified_analysis", True, "stratified analysis dimensions complete")


def validate_output_artifacts(artifacts: set[str]) -> ProtocolCheck:
    missing = sorted(set(REQUIRED_OUTPUT_ARTIFACTS) - artifacts)
    if missing:
        return ProtocolCheck("output_artifacts", False, f"missing output artifacts: {missing}")
    return ProtocolCheck("output_artifacts", True, "output artifacts complete")


def generate_walk_forward_windows(
    start_ts: int,
    end_ts: int,
    train_seconds: int,
    validation_seconds: int,
    step_seconds: int,
) -> list[WalkForwardWindow]:
    if end_ts <= start_ts:
        raise ValueError("end_ts must be greater than start_ts")
    if min(train_seconds, validation_seconds, step_seconds) <= 0:
        raise ValueError("window sizes must be positive")
    windows = []
    cursor = start_ts
    while cursor + train_seconds + validation_seconds <= end_ts:
        train_start = cursor
        train_end = cursor + train_seconds
        validation_start = train_end
        validation_end = validation_start + validation_seconds
        windows.append(WalkForwardWindow(train_start, train_end, validation_start, validation_end))
        cursor += step_seconds
    return windows


def validate_backtest_protocol(
    fee_bps: float,
    slippage_bps: float,
    fill_model: str,
    uses_position_sizer: bool,
    trade_fields: set[str],
    performance_fields: set[str],
) -> list[ProtocolCheck]:
    checks = [
        ProtocolCheck("fee", fee_bps > 0, "fee bps must be included"),
        ProtocolCheck("slippage", slippage_bps > 0, "slippage bps must be included"),
        ProtocolCheck(
            "fill_model",
            fill_model in {"next_bar_open", "trigger_price", "conservative_limit"},
            "approved fill model required",
        ),
        ProtocolCheck("position_model", uses_position_sizer, "backtest must use live position sizing model"),
    ]
    missing_trade = sorted(set(REQUIRED_TRADE_FIELDS) - trade_fields)
    checks.append(
        ProtocolCheck(
            "trade_fields",
            not missing_trade,
            f"missing trade fields: {missing_trade}" if missing_trade else "trade fields complete",
        )
    )
    missing_perf = sorted(set(REQUIRED_PERFORMANCE_FIELDS) - performance_fields)
    checks.append(
        ProtocolCheck(
            "performance_fields",
            not missing_perf,
            f"missing performance fields: {missing_perf}" if missing_perf else "performance fields complete",
        )
    )
    checks.append(validate_processing_order(BACKTEST_PROCESSING_ORDER))
    return checks


def _decimal_places(value: float) -> int:
    text = f"{value:.12f}".rstrip("0").rstrip(".")
    if "." not in text:
        return 0
    return len(text.split(".", 1)[1])
