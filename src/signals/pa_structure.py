from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from src.backtest.engine import BacktestBar
from src.signals.fib_location import SwingPoint


@dataclass(frozen=True)
class PriceActionResult:
    score: float
    structure_tag: str
    structure_score: float
    candle_score: float
    swing_score: float
    reasons: tuple[str, ...]


def score_price_action_structure(
    bars: Sequence[BacktestBar],
    side: str,
    swings: Sequence[SwingPoint],
    *,
    atr: float,
) -> PriceActionResult:
    recent = list(bars)
    normalized = side.strip().upper()
    if len(recent) < 2:
        return PriceActionResult(0.0, "NO_STRUCTURE", 0.0, 0.0, 0.0, ("PA_INSUFFICIENT_BARS",))

    structure_score, structure_tag = _structure_score(recent, normalized, list(swings), atr)
    candle_score, candle_reasons = _candle_score(recent[-1], normalized, atr)
    swing_score = _swing_trend_score(list(swings), normalized)
    total = max(0.0, min(22.0, structure_score + candle_score + swing_score))
    return PriceActionResult(
        round(total, 4),
        structure_tag,
        structure_score,
        candle_score,
        swing_score,
        tuple(candle_reasons),
    )


def _structure_score(
    bars: list[BacktestBar],
    side: str,
    swings: list[SwingPoint],
    atr: float,
) -> tuple[float, str]:
    if side == "SHORT":
        if _detect_lower_high_retest(bars, swings, side):
            return 12.0, "LOWER_HIGH_RETEST"
        if _detect_breakdown_retest(bars, swings, atr, side):
            return 9.0, "BREAKDOWN_RETEST"
        if _detect_continuation(bars, side, atr):
            return 6.0, "CONTINUATION"
    if side == "LONG":
        if _detect_lower_high_retest(bars, swings, side):
            return 12.0, "HIGHER_LOW_RETEST"
        if _detect_breakdown_retest(bars, swings, atr, side):
            return 9.0, "BREAKOUT_RETEST"
        if _detect_continuation(bars, side, atr):
            return 6.0, "CONTINUATION"
    return 0.0, "NO_STRUCTURE"


def _detect_lower_high_retest(
    bars: list[BacktestBar],
    swings: list[SwingPoint],
    side: str,
) -> bool:
    highs = [item for item in swings if item.kind == "HIGH"]
    lows = [item for item in swings if item.kind == "LOW"]
    if side == "SHORT" and len(highs) >= 2:
        return highs[-1].price < highs[-2].price and bars[-1].close < bars[-2].close
    if side == "LONG" and len(lows) >= 2:
        return lows[-1].price > lows[-2].price and bars[-1].close > bars[-2].close
    return False


def _detect_breakdown_retest(
    bars: list[BacktestBar],
    swings: list[SwingPoint],
    atr: float,
    side: str,
) -> bool:
    if len(bars) < 4:
        return False
    tolerance = max(0.0, atr * 0.6)
    if side == "SHORT":
        supports = [item.price for item in swings if item.kind == "LOW"]
        if not supports:
            return False
        support = min(supports[-2:] if len(supports) >= 2 else supports)
        retested = any(abs(item.high - support) <= tolerance for item in bars[-3:-1])
        return retested and bars[-1].close < support

    resistances = [item.price for item in swings if item.kind == "HIGH"]
    if not resistances:
        return False
    resistance = max(resistances[-2:] if len(resistances) >= 2 else resistances)
    retested = any(abs(item.low - resistance) <= tolerance for item in bars[-3:-1])
    return retested and bars[-1].close > resistance


def _detect_continuation(bars: list[BacktestBar], side: str, atr: float) -> bool:
    if len(bars) < 3 or atr <= 0:
        return False
    move = bars[-1].close - bars[-3].close
    if side == "SHORT":
        return -atr * 2.2 < move < -atr * 0.8
    return atr * 0.8 < move < atr * 2.2


def _candle_score(bar: BacktestBar, side: str, atr: float) -> tuple[float, list[str]]:
    body = abs(bar.close - bar.open)
    upper_wick = bar.high - max(bar.open, bar.close)
    lower_wick = min(bar.open, bar.close) - bar.low
    reasons: list[str] = []
    min_body = max(0.0, atr * 0.3)

    if side == "SHORT":
        if upper_wick > max(body, 1e-12) * 1.5:
            reasons.append("REVERSAL_WICK")
            return -4.0, reasons
        if bar.close < bar.open and body > min_body:
            return 6.0, reasons
    if side == "LONG":
        if lower_wick > max(body, 1e-12) * 1.5:
            reasons.append("REVERSAL_WICK")
            return -4.0, reasons
        if bar.close > bar.open and body > min_body:
            return 6.0, reasons
    return 0.0, reasons


def _swing_trend_score(swings: list[SwingPoint], side: str) -> float:
    highs = [item for item in swings if item.kind == "HIGH"]
    lows = [item for item in swings if item.kind == "LOW"]
    if side == "SHORT" and len(highs) >= 2 and highs[-1].price < highs[-2].price:
        return 3.0
    if side == "LONG" and len(lows) >= 2 and lows[-1].price > lows[-2].price:
        return 3.0
    return 0.0
