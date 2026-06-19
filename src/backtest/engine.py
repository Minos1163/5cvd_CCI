from __future__ import annotations

from dataclasses import asdict, dataclass, field
from math import sqrt
from statistics import mean, pstdev
from typing import Any, Callable, Mapping, Sequence

from src.backtest.fee_model import fee
from src.backtest.fill_model import next_bar_market_fill
from src.backtest.metrics import profit_factor, win_rate
from src.core.models import Candle


BACKTEST_REQUIRED_INPUTS = [
    "run_id",
    "strategy_name",
    "strategy_version",
    "config_version",
    "data_version",
    "symbols",
    "timeframes",
    "start_time",
    "end_time",
    "initial_capital",
    "fee_model",
    "slippage_model",
    "funding_model",
    "fill_model",
    "capital_constraints",
    "risk_constraints",
    "entry_modes",
    "source",
]
BACKTEST_RESULT_FIELDS = [
    "run_id",
    "status",
    "final_equity",
    "total_return",
    "annual_return",
    "max_drawdown",
    "profit_factor",
    "sharpe",
    "sortino",
    "win_rate",
    "avg_win",
    "avg_loss",
    "expectancy",
    "trade_count",
    "symbol_breakdown",
    "side_breakdown",
    "entry_mode_breakdown",
    "summary_json",
    "report_path",
]
BACKTEST_STEP_ORDER = [
    "update_current_time_step_data",
    "update_indicators",
    "update_multi_timeframe_context",
    "update_current_position_state",
    "check_exits",
    "check_reductions",
    "check_additions",
    "check_entries",
    "simulate_order_submit_and_fill",
    "write_events_logs_snapshots",
    "advance",
]
BACKTEST_FILL_MODELS = ["NEXT_BAR_OPEN", "TRIGGER_PRICE", "CONSERVATIVE_LIMIT_FILL"]
BACKTEST_REQUIRED_EVENTS = [
    "BACKTEST_STEP_COMPLETED",
    "SIGNAL_CREATED",
    "RISK_BLOCKED",
    "ORDER_SUBMITTED",
    "ORDER_FILLED",
    "ORDER_REJECTED",
    "POSITION_OPENED",
    "POSITION_REDUCED",
    "POSITION_CLOSED",
    "STOP_HIT",
    "TP_HIT",
    "COOLDOWN_STARTED",
    "COOLDOWN_ENDED",
]
BACKTEST_ARTIFACTS = [
    "backtest_result.json",
    "trade_log.csv",
    "equity_curve.csv",
    "drawdown_curve.csv",
    "state_transitions.csv",
    "risk_events.csv",
    "signal_events.csv",
    "performance_summary.md",
    "performance_summary.html",
]
BACKTEST_FORBIDDEN_ACTIONS = [
    "use_future_bar",
    "use_unfinished_higher_timeframe_bar",
    "change_strategy_rules",
    "skip_fee_slippage_or_funding",
    "auto_fill_uncrossed_limit_order",
    "promote_probe_to_direct",
    "ignore_risk_block",
    "call_exchange_or_live_adapter",
]
BACKTEST_ANALYSIS_DIMENSIONS = [
    "symbol",
    "timeframe",
    "side",
    "entry_mode",
    "market_state",
    "volatility_state",
    "risk_level",
    "holding_time",
    "trading_session",
]
BACKTEST_FAILURE_SAMPLE_TYPES = [
    "signal_rejected",
    "risk_blocked",
    "position_rejected",
    "execution_rejected",
    "stop_hit",
    "cooldown_triggered",
]


@dataclass(frozen=True)
class BacktestRequest:
    run_id: str
    strategy_name: str
    strategy_version: str
    config_version: str
    data_version: str
    symbols: list[str]
    timeframes: list[str]
    start_time: int
    end_time: int
    initial_capital: float
    fee_model: Mapping[str, Any] = field(default_factory=dict)
    slippage_model: Mapping[str, Any] = field(default_factory=dict)
    funding_model: Mapping[str, Any] = field(default_factory=dict)
    fill_model: str = "NEXT_BAR_OPEN"
    capital_constraints: Mapping[str, Any] = field(default_factory=dict)
    risk_constraints: Mapping[str, Any] = field(default_factory=dict)
    entry_modes: list[str] = field(default_factory=lambda: ["PROBE", "DIRECT"])
    source: str = "historical"


@dataclass(frozen=True)
class BacktestValidation:
    status: str
    issues: list[str]
    degraded: list[str]


@dataclass(frozen=True)
class BacktestBar:
    symbol: str
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class BacktestTrade:
    symbol: str
    side: str
    entry_mode: str
    entry_time: int
    entry_price: float
    exit_time: int
    exit_price: float
    quantity: float
    gross_pnl: float
    fees: float
    slippage: float
    funding: float
    net_pnl: float
    reason_enter: str
    reason_exit: str


@dataclass(frozen=True)
class BacktestStepRecord:
    timestamp: int
    symbol: str
    step_order: list[str]
    events: list[str]
    equity: float


@dataclass(frozen=True)
class BacktestResult:
    run_id: str
    status: str
    final_equity: float
    total_return: float
    annual_return: float
    max_drawdown: float
    profit_factor: float | None
    sharpe: float | None
    sortino: float | None
    win_rate: float | None
    avg_win: float | None
    avg_loss: float | None
    expectancy: float | None
    trade_count: int
    symbol_breakdown: dict[str, dict[str, Any]]
    side_breakdown: dict[str, dict[str, Any]]
    entry_mode_breakdown: dict[str, dict[str, Any]]
    summary_json: dict[str, Any]
    report_path: str
    events: list[dict[str, Any]] = field(default_factory=list)
    trades: list[BacktestTrade] = field(default_factory=list)
    equity_curve: list[dict[str, Any]] = field(default_factory=list)
    drawdown_curve: list[dict[str, Any]] = field(default_factory=list)
    state_transitions: list[dict[str, Any]] = field(default_factory=list)
    risk_events: list[dict[str, Any]] = field(default_factory=list)
    signal_events: list[dict[str, Any]] = field(default_factory=list)
    failed_samples: list[dict[str, Any]] = field(default_factory=list)
    artifacts: dict[str, str] = field(default_factory=dict)
    degraded_assumptions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


StrategyCallback = Callable[[BacktestRequest, str, BacktestBar, Mapping[str, Any]], Mapping[str, Any] | None]


class BacktestEngine:
    def __init__(self, request: BacktestRequest | None = None, fill_model_name: str = "NEXT_BAR_OPEN") -> None:
        self.request = request
        self.fill_model_name = fill_model_name

    def run(
        self,
        bars_by_symbol: Mapping[str, Sequence[Any]] | None = None,
        strategy_callback: StrategyCallback | None = None,
    ) -> BacktestResult | dict[str, Any]:
        if self.request is None or bars_by_symbol is None:
            return {"status": "not_implemented", "fill_model": self.fill_model_name}
        return run_backtest(self.request, bars_by_symbol, strategy_callback=strategy_callback)


def validate_backtest_request(request: BacktestRequest, bars_by_symbol: Mapping[str, Sequence[Any]]) -> BacktestValidation:
    issues: list[str] = []
    degraded: list[str] = []
    if not request.run_id:
        issues.append("run_id is required")
    if not request.symbols:
        issues.append("symbols are required")
    if request.initial_capital <= 0:
        issues.append("initial_capital must be positive")
    if request.end_time <= request.start_time:
        issues.append("end_time must be greater than start_time")
    if request.fill_model not in BACKTEST_FILL_MODELS:
        issues.append(f"fill_model must be one of {BACKTEST_FILL_MODELS}")
    if not request.funding_model:
        degraded.append("funding_missing_approximate")

    step_seconds = _expected_step_seconds(request)
    for symbol in request.symbols:
        raw_bars = list(bars_by_symbol.get(symbol, []))
        if not raw_bars:
            issues.append(f"missing bars for {symbol}")
            continue
        normalized = sorted((_normalize_bar(item) for item in raw_bars), key=lambda item: item.timestamp)
        seen: set[int] = set()
        previous: BacktestBar | None = None
        for current in normalized:
            if current.symbol != symbol:
                issues.append(f"bar symbol mismatch for {symbol} at {current.timestamp}")
            if current.timestamp in seen:
                issues.append(f"duplicate timestamp for {symbol}: {current.timestamp}")
            seen.add(current.timestamp)
            if current.high < max(current.open, current.close) or current.low > min(current.open, current.close):
                issues.append(f"invalid OHLC for {symbol} at {current.timestamp}")
            if current.volume <= 0:
                issues.append(f"non-positive volume for {symbol} at {current.timestamp}")
            if previous is not None and current.timestamp != previous.timestamp + step_seconds:
                issues.append(f"gap before {symbol} {current.timestamp}")
            previous = current
    return BacktestValidation("rejected" if issues else "accepted", issues, degraded)


def assert_no_lookahead(current_ts: int, data_ts: int) -> None:
    if data_ts > current_ts:
        raise ValueError("future data is not allowed in backtest step")


def run_backtest(
    request: BacktestRequest,
    bars_by_symbol: Mapping[str, Sequence[Any]],
    *,
    strategy_callback: StrategyCallback | None = None,
) -> BacktestResult:
    validation = validate_backtest_request(request, bars_by_symbol)
    artifacts = build_artifact_manifest(request)
    if validation.status == "rejected":
        return _empty_result(request, "rejected", artifacts, validation.issues, validation.degraded)

    events: list[dict[str, Any]] = []
    trades: list[BacktestTrade] = []
    equity_curve: list[dict[str, Any]] = [{"timestamp": request.start_time, "equity": request.initial_capital}]
    drawdown_curve: list[dict[str, Any]] = [{"timestamp": request.start_time, "drawdown": 0.0}]
    failed_samples: list[dict[str, Any]] = []
    risk_events: list[dict[str, Any]] = []
    signal_events: list[dict[str, Any]] = []
    state_transitions: list[dict[str, Any]] = []
    equity = request.initial_capital
    peak_equity = request.initial_capital
    fee_bps = float(request.fee_model.get("fee_bps", request.fee_model.get("taker_bps", 0.0)) or 0.0)
    slippage_bps = float(request.slippage_model.get("slippage_bps", request.slippage_model.get("base_bps", 0.0)) or 0.0)
    funding_bps = float(request.funding_model.get("funding_bps", 0.0) or 0.0)

    for symbol in request.symbols:
        bars = sorted((_normalize_bar(item) for item in bars_by_symbol[symbol]), key=lambda item: item.timestamp)
        for index, current_bar in enumerate(bars):
            assert_no_lookahead(current_bar.timestamp, current_bar.timestamp)
            context = {
                "index": index,
                "equity": equity,
                "previous_bar": None if index == 0 else bars[index - 1],
                "step_order": BACKTEST_STEP_ORDER,
            }
            step_events = ["BACKTEST_STEP_COMPLETED"]
            signal = dict(strategy_callback(request, symbol, current_bar, context) or {}) if strategy_callback else {}
            if not _is_trade_signal(signal):
                sample = _failed_sample("signal_rejected", symbol, current_bar.timestamp, signal, "no executable signal")
                failed_samples.append(sample)
                signal_events.append(_event("SIGNAL_REJECTED", symbol, current_bar.timestamp, sample))
                events.append(_event("BACKTEST_STEP_COMPLETED", symbol, current_bar.timestamp, {"step_order": BACKTEST_STEP_ORDER}))
                continue

            signal_event = _event("SIGNAL_CREATED", symbol, current_bar.timestamp, signal)
            events.append(signal_event)
            signal_events.append(signal_event)
            step_events.append("SIGNAL_CREATED")

            if not bool(signal.get("risk_allowed", signal.get("allow_trade", True))):
                sample = _failed_sample(
                    "risk_blocked",
                    symbol,
                    current_bar.timestamp,
                    signal,
                    str(signal.get("risk_reason", "risk blocked")),
                )
                failed_samples.append(sample)
                risk_event = _event("RISK_BLOCKED", symbol, current_bar.timestamp, sample)
                events.append(risk_event)
                risk_events.append(risk_event)
                events.append(_event("BACKTEST_STEP_COMPLETED", symbol, current_bar.timestamp, {"step_order": BACKTEST_STEP_ORDER}))
                continue

            fill = _simulate_fill(request, signal, current_bar, bars, index, slippage_bps)
            events.append(_event("ORDER_SUBMITTED", symbol, current_bar.timestamp, {"signal": signal}))
            step_events.append("ORDER_SUBMITTED")
            if fill is None:
                sample = _failed_sample("execution_rejected", symbol, current_bar.timestamp, signal, "order did not fill")
                failed_samples.append(sample)
                events.append(_event("ORDER_REJECTED", symbol, current_bar.timestamp, sample))
                events.append(_event("BACKTEST_STEP_COMPLETED", symbol, current_bar.timestamp, {"step_order": BACKTEST_STEP_ORDER}))
                continue

            entry_time, entry_price, exit_time, exit_price = fill
            side = str(signal.get("signal_side", signal.get("side", signal.get("signal_type", "LONG")))).upper()
            entry_mode = str(signal.get("entry_mode", signal.get("mode", "DIRECT"))).upper()
            notional = float(signal.get("notional", request.capital_constraints.get("notional_per_trade", 100.0)) or 100.0)
            quantity = notional / entry_price if entry_price > 0 else 0.0
            gross_pnl = _gross_pnl(side, entry_price, exit_price, quantity)
            fees = fee(notional, fee_bps) + fee(abs(quantity * exit_price), fee_bps)
            explicit_slippage = abs(entry_price - _raw_reference_fill_price(request, signal, current_bar, bars, index)) * quantity
            funding = fee(notional, funding_bps)
            net_pnl = gross_pnl - fees - explicit_slippage - funding
            equity += net_pnl
            peak_equity = max(peak_equity, equity)
            drawdown = 0.0 if peak_equity == 0 else (peak_equity - equity) / peak_equity
            trade = BacktestTrade(
                symbol=symbol,
                side=side,
                entry_mode=entry_mode,
                entry_time=entry_time,
                entry_price=entry_price,
                exit_time=exit_time,
                exit_price=exit_price,
                quantity=quantity,
                gross_pnl=gross_pnl,
                fees=fees,
                slippage=explicit_slippage,
                funding=funding,
                net_pnl=net_pnl,
                reason_enter=str(signal.get("reason", "strategy_signal")),
                reason_exit="one_bar_exit",
            )
            trades.append(trade)
            equity_curve.append({"timestamp": exit_time, "equity": equity})
            drawdown_curve.append({"timestamp": exit_time, "drawdown": drawdown})
            state_transitions.append(
                {
                    "state_before": "FLAT",
                    "state_after": f"{entry_mode}_{side}",
                    "reason": trade.reason_enter,
                    "timestamp": entry_time,
                    "symbol": symbol,
                    "price": entry_price,
                }
            )
            events.extend(
                [
                    _event("ORDER_FILLED", symbol, entry_time, {"price": entry_price, "quantity": quantity}),
                    _event("POSITION_OPENED", symbol, entry_time, {"side": side, "entry_mode": entry_mode}),
                    _event("POSITION_CLOSED", symbol, exit_time, {"net_pnl": net_pnl}),
                    _event("BACKTEST_STEP_COMPLETED", symbol, current_bar.timestamp, {"step_order": BACKTEST_STEP_ORDER}),
                ]
            )
            step_events.extend(["ORDER_FILLED", "POSITION_OPENED", "POSITION_CLOSED", "BACKTEST_STEP_COMPLETED"])

    final_equity = equity
    net_pnls = [trade.net_pnl for trade in trades]
    symbol_breakdown = _breakdown(trades, "symbol")
    side_breakdown = _breakdown(trades, "side")
    entry_mode_breakdown = _breakdown(trades, "entry_mode")
    max_drawdown = max((row["drawdown"] for row in drawdown_curve), default=0.0)
    result = BacktestResult(
        run_id=request.run_id,
        status="completed",
        final_equity=final_equity,
        total_return=(final_equity - request.initial_capital) / request.initial_capital,
        annual_return=_annual_return(request, final_equity),
        max_drawdown=max_drawdown,
        profit_factor=profit_factor(net_pnls),
        sharpe=_sharpe(net_pnls),
        sortino=_sortino(net_pnls),
        win_rate=win_rate(net_pnls),
        avg_win=_avg([item for item in net_pnls if item > 0]),
        avg_loss=_avg([item for item in net_pnls if item < 0]),
        expectancy=_avg(net_pnls),
        trade_count=len(trades),
        symbol_breakdown=symbol_breakdown,
        side_breakdown=side_breakdown,
        entry_mode_breakdown=entry_mode_breakdown,
        summary_json={
            "run_id": request.run_id,
            "strategy_name": request.strategy_name,
            "strategy_version": request.strategy_version,
            "config_version": request.config_version,
            "data_version": request.data_version,
            "fill_model": request.fill_model,
            "fee_bps": fee_bps,
            "slippage_bps": slippage_bps,
            "funding_bps": funding_bps,
            "step_order": BACKTEST_STEP_ORDER,
        },
        report_path=artifacts["performance_summary.md"],
        events=events,
        trades=trades,
        equity_curve=equity_curve,
        drawdown_curve=drawdown_curve,
        state_transitions=state_transitions,
        risk_events=risk_events,
        signal_events=signal_events,
        failed_samples=failed_samples,
        artifacts=artifacts,
        degraded_assumptions=validation.degraded,
    )
    return result


def build_artifact_manifest(request: BacktestRequest) -> dict[str, str]:
    prefix = f"reports/backtests/{request.run_id}"
    return {name: f"{prefix}/{name}" for name in BACKTEST_ARTIFACTS}


def _empty_result(
    request: BacktestRequest,
    status: str,
    artifacts: dict[str, str],
    issues: list[str],
    degraded: list[str],
) -> BacktestResult:
    return BacktestResult(
        run_id=request.run_id,
        status=status,
        final_equity=request.initial_capital,
        total_return=0.0,
        annual_return=0.0,
        max_drawdown=0.0,
        profit_factor=None,
        sharpe=None,
        sortino=None,
        win_rate=None,
        avg_win=None,
        avg_loss=None,
        expectancy=None,
        trade_count=0,
        symbol_breakdown={},
        side_breakdown={},
        entry_mode_breakdown={},
        summary_json={"issues": issues},
        report_path=artifacts["performance_summary.md"],
        artifacts=artifacts,
        degraded_assumptions=degraded,
    )


def _simulate_fill(
    request: BacktestRequest,
    signal: Mapping[str, Any],
    current_bar: BacktestBar,
    bars: Sequence[BacktestBar],
    index: int,
    slippage_bps: float,
) -> tuple[int, float, int, float] | None:
    side = str(signal.get("signal_side", signal.get("side", signal.get("signal_type", "LONG")))).upper()
    if request.fill_model == "TRIGGER_PRICE":
        if index + 1 >= len(bars):
            return None
        entry_time = current_bar.timestamp
        entry_price = _apply_trigger_slippage(current_bar.close, side, slippage_bps)
        exit_bar = bars[index + 1]
        assert_no_lookahead(exit_bar.timestamp, exit_bar.timestamp)
        return entry_time, entry_price, exit_bar.timestamp, exit_bar.open
    if index + 2 >= len(bars):
        return None
    next_bar = bars[index + 1]
    assert_no_lookahead(next_bar.timestamp, next_bar.timestamp)
    if request.fill_model == "CONSERVATIVE_LIMIT_FILL":
        limit_price = float(signal.get("limit_price", signal.get("price", next_bar.open)) or next_bar.open)
        if side == "LONG" and next_bar.low > limit_price:
            return None
        if side == "SHORT" and next_bar.high < limit_price:
            return None
        entry_price = limit_price
    else:
        order_side = "BUY" if side == "LONG" else "SELL"
        entry_price = next_bar_market_fill(next_bar.open, order_side, slippage_bps)
    exit_bar = bars[index + 2]
    return next_bar.timestamp, entry_price, exit_bar.timestamp, exit_bar.open


def _raw_reference_fill_price(
    request: BacktestRequest,
    signal: Mapping[str, Any],
    current_bar: BacktestBar,
    bars: Sequence[BacktestBar],
    index: int,
) -> float:
    if request.fill_model == "TRIGGER_PRICE":
        return current_bar.close
    if index + 1 >= len(bars):
        return current_bar.close
    if request.fill_model == "CONSERVATIVE_LIMIT_FILL":
        return float(signal.get("limit_price", signal.get("price", bars[index + 1].open)) or bars[index + 1].open)
    return bars[index + 1].open


def _apply_trigger_slippage(price: float, side: str, slippage_bps: float) -> float:
    adjustment = price * slippage_bps / 10000
    return price + adjustment if side == "LONG" else price - adjustment


def _gross_pnl(side: str, entry_price: float, exit_price: float, quantity: float) -> float:
    if side == "SHORT":
        return (entry_price - exit_price) * quantity
    return (exit_price - entry_price) * quantity


def _is_trade_signal(signal: Mapping[str, Any]) -> bool:
    signal_type = str(signal.get("signal_type", signal.get("type", ""))).upper()
    side = str(signal.get("signal_side", signal.get("side", signal_type))).upper()
    entry_mode = str(signal.get("entry_mode", signal.get("mode", ""))).upper()
    if signal_type in {"", "NO_TRADE", "WAIT", "NONE"}:
        return False
    if side not in {"LONG", "SHORT"}:
        return False
    return entry_mode in {"PROBE", "DIRECT"}


def _breakdown(trades: Sequence[BacktestTrade], field_name: str) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[BacktestTrade]] = {}
    for trade in trades:
        groups.setdefault(str(getattr(trade, field_name)), []).append(trade)
    return {
        key: {
            "trade_count": len(items),
            "net_pnl": sum(item.net_pnl for item in items),
            "win_rate": win_rate([item.net_pnl for item in items]),
        }
        for key, items in groups.items()
    }


def _event(event_type: str, symbol: str, timestamp: int, payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "event_type": event_type,
        "symbol": symbol,
        "timestamp": timestamp,
        "source": "backtest_engine",
        "payload": dict(payload),
    }


def _failed_sample(
    sample_type: str,
    symbol: str,
    timestamp: int,
    payload: Mapping[str, Any],
    reason: str,
) -> dict[str, Any]:
    return {
        "type": sample_type,
        "symbol": symbol,
        "timestamp": timestamp,
        "reason": reason,
        "payload": dict(payload),
    }


def _annual_return(request: BacktestRequest, final_equity: float) -> float:
    total_return = (final_equity - request.initial_capital) / request.initial_capital
    duration_seconds = max(request.end_time - request.start_time, 1)
    year_seconds = 365 * 24 * 60 * 60
    return total_return * (year_seconds / duration_seconds)


def _sharpe(values: Sequence[float]) -> float | None:
    if len(values) < 2:
        return None
    deviation = pstdev(values)
    if deviation == 0:
        return None
    return mean(values) / deviation * sqrt(len(values))


def _sortino(values: Sequence[float]) -> float | None:
    downside = [value for value in values if value < 0]
    if not downside:
        return None
    deviation = pstdev(downside)
    if deviation == 0:
        return None
    return mean(values) / deviation * sqrt(len(values))


def _avg(values: Sequence[float]) -> float | None:
    if not values:
        return None
    return mean(values)


def _normalize_bar(item: Any) -> BacktestBar:
    if isinstance(item, BacktestBar):
        return item
    if isinstance(item, Candle):
        return BacktestBar(
            symbol=item.symbol,
            timestamp=item.open_time,
            open=item.open,
            high=item.high,
            low=item.low,
            close=item.close,
            volume=item.volume,
        )
    if isinstance(item, Mapping):
        return BacktestBar(
            symbol=str(item["symbol"]),
            timestamp=int(item.get("timestamp", item.get("open_time"))),
            open=float(item["open"]),
            high=float(item["high"]),
            low=float(item["low"]),
            close=float(item["close"]),
            volume=float(item["volume"]),
        )
    raise TypeError("bar must be BacktestBar, Candle, or mapping")


def _expected_step_seconds(request: BacktestRequest) -> int:
    base = request.timeframes[0] if request.timeframes else "15m"
    normalized = str(base).lower()
    if normalized.endswith("m"):
        return int(normalized[:-1]) * 60
    if normalized.endswith("h"):
        return int(normalized[:-1]) * 60 * 60
    return 900
