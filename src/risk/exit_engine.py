from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ExitActionType(str, Enum):
    FORCED_STOP = "FORCED_STOP"
    PORTFOLIO_RISK = "PORTFOLIO_RISK"
    DIRECTION_REVERSAL = "DIRECTION_REVERSAL"
    VOLATILITY_ANOMALY = "VOLATILITY_ANOMALY"
    TRAILING_STOP = "TRAILING_STOP"
    PARTIAL_TAKE_PROFIT = "PARTIAL_TAKE_PROFIT"


EXIT_PRIORITY = [
    ExitActionType.FORCED_STOP,
    ExitActionType.PORTFOLIO_RISK,
    ExitActionType.DIRECTION_REVERSAL,
    ExitActionType.VOLATILITY_ANOMALY,
    ExitActionType.TRAILING_STOP,
    ExitActionType.PARTIAL_TAKE_PROFIT,
]


@dataclass(frozen=True)
class ExitAction:
    action_type: ExitActionType
    reason: str
    reduce_pct: float = 1.0
    target_price: float | None = None
    stop_price: float | None = None


def select_highest_priority_action(actions: list[ExitAction]) -> ExitAction | None:
    if not actions:
        return None
    rank = {action_type: index for index, action_type in enumerate(EXIT_PRIORITY)}
    return sorted(actions, key=lambda action: rank[action.action_type])[0]


def plan_take_profit_actions(
    entry_price: float,
    stop_price: float,
    side: str,
    r_levels: tuple[float, ...] = (1.0, 2.0, 3.0),
    reduce_pcts: tuple[float, ...] = (0.30, 0.40, 0.30),
) -> list[ExitAction]:
    if len(r_levels) != len(reduce_pcts):
        raise ValueError("r_levels and reduce_pcts must have the same length")
    risk = _risk_unit(entry_price, stop_price)
    normalized_side = side.strip().upper()
    actions = []
    for r_level, reduce_pct in zip(r_levels, reduce_pcts):
        if normalized_side == "LONG":
            target = entry_price + risk * r_level
        elif normalized_side == "SHORT":
            target = entry_price - risk * r_level
        else:
            raise ValueError("side must be LONG or SHORT")
        actions.append(
            ExitAction(
                ExitActionType.PARTIAL_TAKE_PROFIT,
                f"take profit {r_level:g}R",
                reduce_pct=reduce_pct,
                target_price=target,
            )
        )
    return actions


def breakeven_stop(entry_price: float, side: str, fee_bps: float, slippage_bps: float, safety_bps: float) -> float:
    if entry_price <= 0:
        raise ValueError("entry_price must be positive")
    total_bps = fee_bps + slippage_bps + safety_bps
    if total_bps < 0:
        raise ValueError("buffers must be non-negative")
    buffer = entry_price * total_bps / 10000
    normalized_side = side.strip().upper()
    if normalized_side == "LONG":
        return entry_price + buffer
    if normalized_side == "SHORT":
        return entry_price - buffer
    raise ValueError("side must be LONG or SHORT")


def trailing_stop_from_structure(
    side: str,
    current_stop: float,
    structure_price: float,
    buffer_pct: float,
) -> ExitAction | None:
    if current_stop <= 0 or structure_price <= 0 or buffer_pct < 0:
        raise ValueError("prices must be positive and buffer_pct must be non-negative")
    normalized_side = side.strip().upper()
    if normalized_side == "LONG":
        candidate = structure_price * (1 - buffer_pct)
        if candidate <= current_stop:
            return None
    elif normalized_side == "SHORT":
        candidate = structure_price * (1 + buffer_pct)
        if candidate >= current_stop:
            return None
    else:
        raise ValueError("side must be LONG or SHORT")
    return ExitAction(ExitActionType.TRAILING_STOP, "structure trailing stop", stop_price=candidate)


def forced_exit_actions(
    stop_hit: bool = False,
    portfolio_risk: bool = False,
    direction_reversal: bool = False,
    volatility_anomaly: bool = False,
) -> list[ExitAction]:
    actions = []
    if stop_hit:
        actions.append(ExitAction(ExitActionType.FORCED_STOP, "initial stop hit", reduce_pct=1.0))
    if portfolio_risk:
        actions.append(ExitAction(ExitActionType.PORTFOLIO_RISK, "portfolio risk limit exceeded", reduce_pct=1.0))
    if direction_reversal:
        actions.append(ExitAction(ExitActionType.DIRECTION_REVERSAL, "direction reversal confirmed", reduce_pct=1.0))
    if volatility_anomaly:
        actions.append(ExitAction(ExitActionType.VOLATILITY_ANOMALY, "volatility anomaly protection", reduce_pct=0.50))
    return actions


def cooldown_until(now_ts: int, bars: int, timeframe_seconds: int = 900) -> int:
    if bars < 0 or timeframe_seconds <= 0:
        raise ValueError("bars must be non-negative and timeframe_seconds must be positive")
    return now_ts + bars * timeframe_seconds


def _risk_unit(entry_price: float, stop_price: float) -> float:
    if entry_price <= 0 or stop_price <= 0:
        raise ValueError("entry_price and stop_price must be positive")
    distance = abs(entry_price - stop_price)
    if distance <= 0:
        raise ValueError("stop distance must be positive")
    return distance
