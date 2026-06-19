from __future__ import annotations

from collections.abc import Iterable

from src.core.models import Candle


def validate_candles(candles: Iterable[Candle]) -> list[Candle]:
    ordered = sorted(candles, key=lambda candle: candle.open_time)
    seen: set[int] = set()
    for candle in ordered:
        if candle.open_time in seen:
            raise ValueError(f"duplicate candle open_time: {candle.open_time}")
        if candle.high < max(candle.open, candle.close) or candle.low > min(candle.open, candle.close):
            raise ValueError("invalid OHLC relationship")
        seen.add(candle.open_time)
    return ordered
