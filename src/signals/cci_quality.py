from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Sequence

from src.backtest.engine import BacktestBar


@dataclass(frozen=True)
class CciQualityResult:
    score: float
    tag: str
    latest_cci: float | None
    details: dict[str, float | str | None]


def cci_series(bars: Sequence[BacktestBar], *, period: int = 20) -> list[float]:
    items = list(bars)
    if len(items) < period:
        return []
    typical_prices = [(bar.high + bar.low + bar.close) / 3.0 for bar in items]
    values: list[float] = []
    for index in range(period - 1, len(typical_prices)):
        window = typical_prices[index - period + 1 : index + 1]
        average = mean(window)
        mean_deviation = mean(abs(item - average) for item in window)
        if mean_deviation <= 0:
            values.append(0.0)
        else:
            values.append((typical_prices[index] - average) / (0.015 * mean_deviation))
    return values


def score_cci_momentum_quality(values: Sequence[float], side: str) -> CciQualityResult:
    series = [float(item) for item in values]
    if not series:
        return CciQualityResult(0.0, "CCI_MISSING", None, {})
    normalized = side.strip().upper()
    latest = series[-1]
    if normalized == "SHORT":
        return _score_short(series, latest)
    if normalized == "LONG":
        return _score_long(series, latest)
    return CciQualityResult(0.0, "CCI_SIDE_UNSUPPORTED", latest, {})


def _score_short(series: list[float], latest: float) -> CciQualityResult:
    if len(series) >= 4 and min(series[-5:]) < -150 and max(series[-4:-1]) > -80 and latest < series[-2]:
        return CciQualityResult(14.0, "CCI_SHORT_SECONDARY_WEAKNESS", latest, {})
    if min(series[-4:]) < -120 and latest > -80:
        return CciQualityResult(0.0, "CCI_SHORT_FAILED_CONTINUATION", latest, {})
    if latest < -150:
        score = max(0.0, min(3.0, 3.0 + (latest + 150.0) * 0.02))
        return CciQualityResult(round(score, 4), "CCI_SHORT_EXHAUSTION", latest, {})
    if -150 <= latest <= -100:
        return CciQualityResult(10.0, "CCI_SHORT_HEALTHY", latest, {})
    if -100 < latest < -50 and len(series) >= 2 and latest < series[-2]:
        return CciQualityResult(7.0, "CCI_SHORT_PULLBACK_WEAKENING", latest, {})
    return CciQualityResult(0.0, "CCI_SHORT_UNSUPPORTED", latest, {})


def _score_long(series: list[float], latest: float) -> CciQualityResult:
    if len(series) >= 4 and max(series[-5:]) > 150 and series[-2] < 80 and latest > series[-2]:
        return CciQualityResult(14.0, "CCI_LONG_SECONDARY_STRENGTH", latest, {})
    if max(series[-4:]) > 120 and latest < 80:
        return CciQualityResult(0.0, "CCI_LONG_FAILED_CONTINUATION", latest, {})
    if latest > 150:
        score = max(0.0, min(3.0, 3.0 - (latest - 150.0) * 0.02))
        return CciQualityResult(round(score, 4), "CCI_LONG_EXHAUSTION", latest, {})
    if 100 <= latest <= 150:
        return CciQualityResult(10.0, "CCI_LONG_HEALTHY", latest, {})
    if 50 < latest < 100 and len(series) >= 2 and latest > series[-2]:
        return CciQualityResult(7.0, "CCI_LONG_PULLBACK_STRENGTHENING", latest, {})
    return CciQualityResult(0.0, "CCI_LONG_UNSUPPORTED", latest, {})
