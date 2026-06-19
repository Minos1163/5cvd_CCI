from __future__ import annotations

from collections.abc import Iterable

from src.core.models import Candle
from src.data.data_contract import CVDPoint, build_cvd_contract_points


def build_cvd(candles: Iterable[Candle]) -> list[float]:
    total = 0.0
    values: list[float] = []
    for candle in candles:
        sell_volume = max(candle.volume - candle.taker_buy_volume, 0.0)
        total += candle.taker_buy_volume - sell_volume
        values.append(total)
    return values


def build_cvd_points(candles: Iterable[Candle]) -> list[CVDPoint]:
    return build_cvd_contract_points(list(candles))
