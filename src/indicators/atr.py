from __future__ import annotations

from src.core.models import Candle


def atr(candles: list[Candle], period: int = 14) -> float | None:
    if len(candles) < period + 1:
        return None
    ranges = []
    for prev, cur in zip(candles[-period - 1 : -1], candles[-period:]):
        ranges.append(max(cur.high - cur.low, abs(cur.high - prev.close), abs(cur.low - prev.close)))
    return sum(ranges) / period
