from __future__ import annotations

from src.core.models import Candle


def cci(candles: list[Candle], period: int = 20) -> float | None:
    if len(candles) < period:
        return None
    typical = [(c.high + c.low + c.close) / 3 for c in candles[-period:]]
    avg = sum(typical) / period
    mean_dev = sum(abs(value - avg) for value in typical) / period
    if mean_dev == 0:
        return 0.0
    return (typical[-1] - avg) / (0.015 * mean_dev)
