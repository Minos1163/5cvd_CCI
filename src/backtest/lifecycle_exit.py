from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence


class ExitBar(Protocol):
    timestamp: int
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class PartialExit:
    timestamp: int
    price: float
    fraction: float
    reason: str
    bar_offset: int


@dataclass(frozen=True)
class AtrTpExitConfig:
    atr_stop_mult: float = 1.5
    min_stop_pct: float = 0.005
    max_stop_pct: float = 0.03
    default_atr_pct: float = 0.010
    tp_levels: tuple[float, float, float] = (1.0, 2.0, 3.0)
    tp_fractions: tuple[float, float, float] = (0.40, 0.35, 0.25)
    max_hold_bars: int = 16
    breakeven_after_tp1: bool = True
    breakeven_buffer_pct: float = 0.001
    adverse_reduce_enabled: bool = False
    adverse_reduce_r: float = 0.6
    adverse_reduce_fraction: float = 0.5
    adverse_volume_spike_mult: float = 1.5
    adverse_volume_lookback: int = 20
    time_reduce_enabled: bool = False
    time_reduce_bars: int = 12
    time_reduce_min_profit_r: float = 0.3
    time_reduce_fraction: float = 0.5


@dataclass(frozen=True)
class AtrTpExitResult:
    exit_time: int
    average_exit_price: float
    reason_exit: str
    events: tuple[str, ...]
    partial_exits: tuple[PartialExit, ...] = ()
    hold_bars: int = 0
    tp1_reached: bool = False
    breakeven_active: bool = False


def simulate_atr_tp_exit(
    *,
    side: str,
    entry_time: int,
    entry_price: float,
    bars_after_entry: Sequence[ExitBar],
    atr_pct: float,
    config: AtrTpExitConfig | None = None,
) -> AtrTpExitResult | None:
    cfg = config or AtrTpExitConfig()
    bars = list(bars_after_entry[: max(1, cfg.max_hold_bars)])
    if entry_price <= 0 or not bars:
        return None
    if atr_pct <= 0:
        atr_pct = cfg.default_atr_pct
    normalized_side = side.strip().upper()
    if normalized_side not in {"LONG", "SHORT"}:
        raise ValueError("side must be LONG or SHORT")

    stop_pct = max(cfg.min_stop_pct, min(cfg.max_stop_pct, atr_pct * cfg.atr_stop_mult))
    risk_distance = entry_price * stop_pct
    stop_price = entry_price - risk_distance if normalized_side == "LONG" else entry_price + risk_distance
    tp_prices = _tp_prices(normalized_side, entry_price, risk_distance, cfg.tp_levels)
    tp_fractions = _normalized_fractions(cfg.tp_fractions)

    remaining = 1.0
    weighted_exit = 0.0
    next_tp = 0
    events: list[str] = []
    partial_exits: list[PartialExit] = []
    breakeven_active = False
    adverse_reduce_done = False
    time_reduce_done = False

    for offset, bar in enumerate(bars, start=1):
        if _stop_hit(normalized_side, bar, stop_price):
            weighted_exit += remaining * stop_price
            reason = "STOP_HIT" if next_tp == 0 else "BREAKEVEN_STOP_HIT"
            events.append(reason)
            partial_exits.append(PartialExit(bar.timestamp, stop_price, remaining, reason, offset))
            return AtrTpExitResult(
                exit_time=bar.timestamp,
                average_exit_price=round(weighted_exit, 10),
                reason_exit="atr_tp_" + events[-1].lower(),
                events=tuple(events),
                partial_exits=tuple(partial_exits),
                hold_bars=offset,
                tp1_reached=next_tp > 0,
                breakeven_active=breakeven_active,
            )

        if (
            cfg.adverse_reduce_enabled
            and not adverse_reduce_done
            and next_tp == 0
            and remaining > 0
            and _adverse_reduce_hit(normalized_side, bar, entry_price, risk_distance, cfg)
            and _volume_spike(bars, offset - 1, cfg.adverse_volume_lookback, cfg.adverse_volume_spike_mult)
        ):
            adverse_price = _adverse_reduce_price(normalized_side, entry_price, risk_distance, cfg.adverse_reduce_r)
            fraction = min(remaining, cfg.adverse_reduce_fraction)
            weighted_exit += fraction * adverse_price
            remaining = round(remaining - fraction, 10)
            adverse_reduce_done = True
            events.append("ADVERSE_REDUCE_0_6R")
            partial_exits.append(PartialExit(bar.timestamp, adverse_price, fraction, "ADVERSE_REDUCE_0_6R", offset))

        if (
            cfg.time_reduce_enabled
            and not time_reduce_done
            and next_tp == 0
            and remaining > 0
            and offset >= cfg.time_reduce_bars
            and _profit_r(normalized_side, entry_price, bar.close, risk_distance) < cfg.time_reduce_min_profit_r
        ):
            fraction = min(remaining, cfg.time_reduce_fraction)
            weighted_exit += fraction * bar.close
            remaining = round(remaining - fraction, 10)
            time_reduce_done = True
            events.append("TIME_REDUCE_STALLED")
            partial_exits.append(PartialExit(bar.timestamp, bar.close, fraction, "TIME_REDUCE_STALLED", offset))

        while next_tp < len(tp_prices) and _tp_hit(normalized_side, bar, tp_prices[next_tp]):
            fraction = min(remaining, tp_fractions[next_tp])
            weighted_exit += fraction * tp_prices[next_tp]
            remaining = round(remaining - fraction, 10)
            reason = f"TP{next_tp + 1}_HIT"
            events.append(reason)
            partial_exits.append(PartialExit(bar.timestamp, tp_prices[next_tp], fraction, reason, offset))
            if next_tp == 0 and cfg.breakeven_after_tp1:
                stop_price = _breakeven_price(normalized_side, entry_price, cfg.breakeven_buffer_pct)
                breakeven_active = True
                events.append("STOP_MOVED_TO_BREAKEVEN")
            next_tp += 1
            if remaining <= 0:
                return AtrTpExitResult(
                    exit_time=bar.timestamp,
                    average_exit_price=round(weighted_exit, 10),
                    reason_exit="atr_tp_tp_ladder_complete",
                    events=tuple(events),
                    partial_exits=tuple(partial_exits),
                    hold_bars=offset,
                    tp1_reached=True,
                    breakeven_active=breakeven_active,
                )

    timeout_bar = bars[-1]
    weighted_exit += max(0.0, remaining) * timeout_bar.close
    partial_exits.append(PartialExit(timeout_bar.timestamp, timeout_bar.close, max(0.0, remaining), "MAX_HOLD_EXIT", len(bars)))
    events.append("MAX_HOLD_EXIT")
    return AtrTpExitResult(
        exit_time=timeout_bar.timestamp,
        average_exit_price=round(weighted_exit, 10),
        reason_exit="atr_tp_max_hold_exit",
        events=tuple(events),
        partial_exits=tuple(partial_exits),
        hold_bars=len(bars),
        tp1_reached=next_tp > 0,
        breakeven_active=breakeven_active,
    )


def _tp_prices(side: str, entry_price: float, risk_distance: float, levels: Sequence[float]) -> tuple[float, ...]:
    if side == "SHORT":
        return tuple(entry_price - risk_distance * level for level in levels)
    return tuple(entry_price + risk_distance * level for level in levels)


def _normalized_fractions(fractions: Sequence[float]) -> tuple[float, ...]:
    values = tuple(max(0.0, float(item)) for item in fractions)
    total = sum(values)
    if total <= 0:
        raise ValueError("tp_fractions must contain a positive total")
    return tuple(item / total for item in values)


def _breakeven_price(side: str, entry_price: float, buffer_pct: float) -> float:
    if side == "SHORT":
        return entry_price * (1 - buffer_pct)
    return entry_price * (1 + buffer_pct)


def _stop_hit(side: str, bar: ExitBar, stop_price: float) -> bool:
    if side == "SHORT":
        return bar.high >= stop_price
    return bar.low <= stop_price


def _tp_hit(side: str, bar: ExitBar, tp_price: float) -> bool:
    if side == "SHORT":
        return bar.low <= tp_price
    return bar.high >= tp_price


def _adverse_reduce_price(side: str, entry_price: float, risk_distance: float, adverse_reduce_r: float) -> float:
    if side == "SHORT":
        return entry_price + risk_distance * adverse_reduce_r
    return entry_price - risk_distance * adverse_reduce_r


def _adverse_reduce_hit(
    side: str,
    bar: ExitBar,
    entry_price: float,
    risk_distance: float,
    cfg: AtrTpExitConfig,
) -> bool:
    price = _adverse_reduce_price(side, entry_price, risk_distance, cfg.adverse_reduce_r)
    if side == "SHORT":
        return bar.high >= price
    return bar.low <= price


def _volume_spike(bars: Sequence[ExitBar], index: int, lookback: int, spike_mult: float) -> bool:
    if index < 0 or index >= len(bars):
        return False
    current_volume = bars[index].volume
    start = max(0, index - max(1, lookback))
    history = bars[start:index]
    if not history:
        return True
    average = sum(bar.volume for bar in history) / len(history)
    return average > 0 and current_volume >= average * spike_mult


def _profit_r(side: str, entry_price: float, price: float, risk_distance: float) -> float:
    if risk_distance <= 0:
        return 0.0
    if side == "SHORT":
        return (entry_price - price) / risk_distance
    return (price - entry_price) / risk_distance
