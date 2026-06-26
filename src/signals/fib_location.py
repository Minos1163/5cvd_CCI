from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from src.backtest.engine import BacktestBar


@dataclass(frozen=True)
class SwingPoint:
    kind: str
    timestamp: int
    index: int
    price: float


@dataclass(frozen=True)
class FibLocationResult:
    score: float
    tag: str
    action_cap: str | None
    details: dict[str, float | str | None]


def compute_fib_levels(swing_high: float, swing_low: float, trend: str) -> dict[str, float]:
    high = float(swing_high)
    low = float(swing_low)
    diff = high - low
    normalized = trend.strip().upper()
    if diff <= 0:
        return {}
    if normalized == "DOWN":
        levels = {
            "r382": low + diff * 0.382,
            "r500": low + diff * 0.500,
            "r618": low + diff * 0.618,
            "r786": low + diff * 0.786,
            "e1000": low,
            "e1272": low - diff * 0.272,
            "e1618": low - diff * 0.618,
            "e2000": low - diff * 1.000,
        }
    else:
        levels = {
            "r382": high - diff * 0.382,
            "r500": high - diff * 0.500,
            "r618": high - diff * 0.618,
            "r786": high - diff * 0.786,
            "e1000": high,
            "e1272": high + diff * 0.272,
            "e1618": high + diff * 0.618,
            "e2000": high + diff * 1.000,
        }
    return {key: round(value, 8) for key, value in levels.items()}


def detect_fractal_swings(
    bars: Sequence[BacktestBar],
    *,
    k: int = 2,
    min_atr_mult: float = 1.2,
    min_spacing_bars: int = 6,
    atr: float = 0.0,
    lookback: int = 50,
) -> list[SwingPoint]:
    recent = list(bars)[-lookback:]
    if len(recent) < k * 2 + 1:
        return []
    swings: list[SwingPoint] = []
    min_move = max(0.0, float(atr) * float(min_atr_mult))
    for idx in range(k, len(recent) - k):
        item = recent[idx]
        left = recent[idx - k : idx]
        right = recent[idx + 1 : idx + 1 + k]
        peers = [*left, *right]
        is_high = all(item.high > peer.high for peer in peers)
        is_low = all(item.low < peer.low for peer in peers)
        if not is_high and not is_low:
            continue
        price = item.high if is_high else item.low
        if swings and idx - swings[-1].index < min_spacing_bars:
            continue
        if swings and abs(price - swings[-1].price) < min_move:
            continue
        swings.append(SwingPoint("HIGH" if is_high else "LOW", item.timestamp, idx, price))
    return swings


def score_fibonacci_location(
    *,
    close: float,
    side: str,
    fib_1h: Mapping[str, float] | None,
    fib_15m: Mapping[str, float] | None,
    atr: float,
) -> FibLocationResult:
    normalized = side.strip().upper()
    tolerance = max(0.0, float(atr) * 0.5)
    price = float(close)
    score = 9.0
    tag = "FIB_NEUTRAL"
    action_cap: str | None = None
    details: dict[str, float | str | None] = {"close": price, "tolerance": tolerance}

    if normalized == "SHORT":
        block = _short_extension_block(price, fib_1h, tolerance, "1H") or _short_extension_block(
            price, fib_15m, tolerance, "15M"
        )
        if block:
            return FibLocationResult(0.0, block, "NO_TRADE", details)
        score, tag = _short_location_score(price, fib_1h, tolerance, "1H")
        if fib_15m and 0 < price - float(fib_15m.get("e1000", price)) < tolerance:
            score -= 3.0
            tag += "_15M_SUPPORT_NEARBY"
    elif normalized == "LONG":
        block = _long_extension_block(price, fib_1h, tolerance, "1H") or _long_extension_block(
            price, fib_15m, tolerance, "15M"
        )
        if block:
            return FibLocationResult(0.0, block, "NO_TRADE", details)
        score, tag = _long_location_score(price, fib_1h, tolerance, "1H")

    return FibLocationResult(round(max(0.0, min(18.0, score)), 4), tag, action_cap, details)


def _short_extension_block(
    price: float, levels: Mapping[str, float] | None, tolerance: float, label: str
) -> str | None:
    if levels and price <= float(levels["e1618"]) + tolerance:
        return f"FIB_{label}_EXTENSION_EXHAUSTION_BLOCK"
    return None


def _long_extension_block(
    price: float, levels: Mapping[str, float] | None, tolerance: float, label: str
) -> str | None:
    if levels and price >= float(levels["e1618"]) - tolerance:
        return f"FIB_{label}_EXTENSION_EXHAUSTION_BLOCK"
    return None


def _short_location_score(
    price: float, levels: Mapping[str, float] | None, tolerance: float, label: str
) -> tuple[float, str]:
    if not levels:
        return 9.0, "FIB_NEUTRAL"
    if float(levels["r382"]) - tolerance <= price <= float(levels["r618"]) + tolerance:
        return 18.0, f"FIB_{label}_PULLBACK_OPTIMAL"
    if float(levels["r618"]) < price <= float(levels["r786"]) + tolerance:
        return 13.0, f"FIB_{label}_DEEP_PULLBACK"
    if float(levels["e1272"]) - tolerance <= price < float(levels["e1000"]):
        return 6.0, f"FIB_{label}_EXTENSION_1272"
    if price < float(levels["e1272"]) - tolerance:
        return 2.0, f"FIB_{label}_EXTENSION_ZONE_PENALTY"
    return 9.0, "FIB_NEUTRAL"


def _long_location_score(
    price: float, levels: Mapping[str, float] | None, tolerance: float, label: str
) -> tuple[float, str]:
    if not levels:
        return 9.0, "FIB_NEUTRAL"
    if float(levels["r618"]) - tolerance <= price <= float(levels["r382"]) + tolerance:
        return 18.0, f"FIB_{label}_PULLBACK_OPTIMAL"
    if float(levels["r786"]) - tolerance <= price < float(levels["r618"]):
        return 13.0, f"FIB_{label}_DEEP_PULLBACK"
    if float(levels["e1000"]) < price <= float(levels["e1272"]) + tolerance:
        return 6.0, f"FIB_{label}_EXTENSION_1272"
    if price > float(levels["e1272"]) + tolerance:
        return 2.0, f"FIB_{label}_EXTENSION_ZONE_PENALTY"
    return 9.0, "FIB_NEUTRAL"
