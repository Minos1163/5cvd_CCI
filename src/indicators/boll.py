from __future__ import annotations

import statistics


def bollinger(values: list[float], period: int = 20, std_mult: float = 2.0) -> tuple[float, float, float] | None:
    if len(values) < period:
        return None
    window = values[-period:]
    mid = sum(window) / period
    std = statistics.pstdev(window)
    return mid, mid + std_mult * std, mid - std_mult * std
