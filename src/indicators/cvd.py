from __future__ import annotations

from src.core.models import Candle


def cvd_delta(taker_buy_volume: float, total_volume: float) -> float:
    sell_volume = max(total_volume - taker_buy_volume, 0.0)
    return taker_buy_volume - sell_volume


def cumulative_cvd(candles: list[Candle]) -> list[float]:
    total = 0.0
    values: list[float] = []
    for candle in candles:
        total += cvd_delta(candle.taker_buy_volume, candle.volume)
        values.append(total)
    return values
