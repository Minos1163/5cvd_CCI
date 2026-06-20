from __future__ import annotations

from dataclasses import dataclass


SLOPE_STEEP = 0.003
SLOPE_MILD = 0.001


@dataclass(frozen=True)
class EmaContext:
    close: float
    ema_9: float | None
    ema_21: float | None
    ema_50: float | None
    ema_200: float | None
    ema50_slope: float
    ema9_21_gap: float
    bars_since_ema50_cross: int | None
    bars_since_ema200_cross: int | None


@dataclass(frozen=True)
class EmaGateDecision:
    allowed: bool
    reason: str
    penalty: float = 0.0


def ema_direction_gate(
    side: str,
    context: EmaContext,
    *,
    mode: str = "hard",
    buffer_pct: float = 0.003,
    min_bars_stable: int = 3,
) -> EmaGateDecision:
    normalized_side = side.strip().upper()
    if context.ema_200 is None:
        return EmaGateDecision(False, "EMA200_UNAVAILABLE")
    upper = context.ema_200 * (1 + buffer_pct)
    lower = context.ema_200 * (1 - buffer_pct)
    in_buffer = lower <= context.close <= upper
    unstable = context.bars_since_ema200_cross is not None and context.bars_since_ema200_cross < min_bars_stable
    counter = (normalized_side == "LONG" and context.close < lower) or (
        normalized_side == "SHORT" and context.close > upper
    )
    if in_buffer or unstable or counter:
        if mode == "soft":
            return EmaGateDecision(True, "EMA200_SOFT_PENALTY", -0.20)
        return EmaGateDecision(False, "EMA200_COUNTER_DIRECTION" if counter else "EMA200_UNSTABLE")
    return EmaGateDecision(True, "PASS")


def score_ema50_quality(side: str, context: EmaContext) -> float:
    if context.ema_50 is None:
        return 0.0
    normalized_side = side.strip().upper()
    score = 0.0
    if normalized_side == "LONG":
        score += 0.80 if context.close > context.ema_50 else 0.20
        if context.ema50_slope > SLOPE_STEEP:
            score += 0.15
        elif context.ema50_slope > SLOPE_MILD:
            score += 0.07
        elif context.ema50_slope < -SLOPE_MILD:
            score -= 0.15
    elif normalized_side == "SHORT":
        score += 0.80 if context.close < context.ema_50 else 0.20
        if context.ema50_slope < -SLOPE_STEEP:
            score += 0.15
        elif context.ema50_slope < -SLOPE_MILD:
            score += 0.07
        elif context.ema50_slope > SLOPE_MILD:
            score -= 0.15
    if context.bars_since_ema50_cross is not None and context.bars_since_ema50_cross <= 2:
        score -= 0.20
    return round(max(0.0, min(1.0, score)), 4)


def score_ema_momentum(side: str, context: EmaContext) -> float:
    if context.ema_9 is None or context.ema_21 is None:
        return 0.0
    normalized_side = side.strip().upper()
    long_aligned = context.ema_9 > context.ema_21
    short_aligned = context.ema_9 < context.ema_21
    score = 0.0
    if normalized_side == "LONG" and long_aligned:
        score += 0.70
    elif normalized_side == "SHORT" and short_aligned:
        score += 0.70
    else:
        score -= 0.50
    if abs(context.ema9_21_gap) > 0.005:
        score += 0.10
    return round(max(0.0, min(1.0, score)), 4)


def ema_trend_state(side: str, context: EmaContext) -> str:
    quality = score_ema50_quality(side, context)
    momentum = score_ema_momentum(side, context)
    if quality >= 0.90 and momentum >= 0.80 and abs(context.ema50_slope) >= SLOPE_STEEP:
        return "STRONG_TREND"
    if quality >= 0.70 and momentum >= 0.70 and abs(context.ema50_slope) >= SLOPE_MILD:
        return "MILD_TREND"
    return "FLAT_OR_TRANSITION"
