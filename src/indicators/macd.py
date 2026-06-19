from __future__ import annotations


def ema(values: list[float], period: int) -> list[float]:
    if not values:
        return []
    alpha = 2 / (period + 1)
    result = [values[0]]
    for value in values[1:]:
        result.append(alpha * value + (1 - alpha) * result[-1])
    return result


def macd(values: list[float], fast: int = 12, slow: int = 26, signal: int = 9) -> tuple[float, float, float] | None:
    if len(values) < slow:
        return None
    fast_ema = ema(values, fast)
    slow_ema = ema(values, slow)
    line = [f - s for f, s in zip(fast_ema, slow_ema)]
    signal_line = ema(line, signal)
    return line[-1], signal_line[-1], line[-1] - signal_line[-1]
