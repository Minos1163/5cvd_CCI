from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StopPlan:
    stop_price: float
    stop_distance: float
    stop_pct: float
    reason: str


def atr_stop(entry_price: float, atr: float, atr_mult: float, side: str) -> float:
    if entry_price <= 0 or atr <= 0 or atr_mult <= 0:
        raise ValueError("entry_price, atr, and atr_mult must be positive")
    distance = atr * atr_mult
    if side.upper() == "LONG":
        return entry_price - distance
    if side.upper() == "SHORT":
        return entry_price + distance
    raise ValueError("side must be LONG or SHORT")


def initial_atr_stop(entry_price: float, atr: float, atr_mult: float, side: str) -> StopPlan:
    stop_price = atr_stop(entry_price, atr, atr_mult, side)
    stop_distance = abs(entry_price - stop_price)
    return StopPlan(
        stop_price=stop_price,
        stop_distance=stop_distance,
        stop_pct=stop_distance / entry_price,
        reason="initial ATR stop",
    )
