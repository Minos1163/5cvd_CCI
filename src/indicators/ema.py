from __future__ import annotations


def ema(values: list[float], period: int) -> list[float]:
    if period <= 0:
        raise ValueError("period must be positive")
    if len(values) < period:
        return []
    seed = sum(values[:period]) / period
    multiplier = 2 / (period + 1)
    results = [seed]
    previous = seed
    for value in values[period:]:
        previous = (float(value) - previous) * multiplier + previous
        results.append(previous)
    return results


def ema_latest(values: list[float], period: int) -> float | None:
    results = ema(values, period)
    return results[-1] if results else None


def normalized_ema_slope(ema_values: list[float], lookback: int = 5) -> float:
    if lookback <= 0:
        raise ValueError("lookback must be positive")
    if len(ema_values) <= lookback:
        return 0.0
    current = float(ema_values[-1])
    prior = float(ema_values[-1 - lookback])
    if prior == 0:
        return 0.0
    return (current - prior) / prior


def bars_since_cross(values: list[float], reference_values: list[float]) -> int | None:
    length = min(len(values), len(reference_values))
    if length < 2:
        return None
    pairs = list(zip(values[-length:], reference_values[-length:]))
    current_side = _side(pairs[-1][0], pairs[-1][1])
    if current_side == 0:
        return 0
    count = 0
    for value, reference in reversed(pairs[:-1]):
        if _side(value, reference) != current_side:
            return count
        count += 1
    return count


def _side(value: float, reference: float) -> int:
    if value > reference:
        return 1
    if value < reference:
        return -1
    return 0
