from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from src.core.models import IndicatorSnapshot


class TimeframeDecision(str, Enum):
    BULL = "BULL"
    BEAR = "BEAR"
    NEUTRAL = "NEUTRAL"
    LONG_ALLOWED = "LONG_ALLOWED"
    SHORT_ALLOWED = "SHORT_ALLOWED"
    NO_TRADE = "NO_TRADE"
    LONG_CONFIRM = "LONG_CONFIRM"
    SHORT_CONFIRM = "SHORT_CONFIRM"
    WEAK = "WEAK"
    LONG_TRIGGER = "LONG_TRIGGER"
    SHORT_TRIGGER = "SHORT_TRIGGER"
    WAIT = "WAIT"


@dataclass(frozen=True)
class MultiTimeframeDecision:
    symbol: str
    signal_type: str
    side: str
    context_4h: str
    permission_1h: str
    quality_30m: str
    trigger_15m: str
    reason: str


def evaluate_4h_context(snapshot: IndicatorSnapshot) -> TimeframeDecision:
    if (snapshot.macd or 0) > 0 and (snapshot.cci or 0) > 100 and (snapshot.cvd_delta or 0) >= 0:
        return TimeframeDecision.BULL
    if (snapshot.macd or 0) < 0 and (snapshot.cci or 0) < -100 and (snapshot.cvd_delta or 0) <= 0:
        return TimeframeDecision.BEAR
    return TimeframeDecision.NEUTRAL


def evaluate_1h_permission(snapshot: IndicatorSnapshot) -> TimeframeDecision:
    if (snapshot.macd or 0) > 0 and (snapshot.cci or 0) > 100 and (snapshot.cvd_delta or 0) > 0:
        return TimeframeDecision.LONG_ALLOWED
    if (snapshot.macd or 0) < 0 and (snapshot.cci or 0) < -100 and (snapshot.cvd_delta or 0) < 0:
        return TimeframeDecision.SHORT_ALLOWED
    return TimeframeDecision.NO_TRADE


def evaluate_30m_quality(snapshot: IndicatorSnapshot) -> TimeframeDecision:
    if (snapshot.cci or 0) > 100:
        return TimeframeDecision.LONG_CONFIRM
    if (snapshot.cci or 0) < -100:
        return TimeframeDecision.SHORT_CONFIRM
    return TimeframeDecision.WEAK


def evaluate_15m_trigger(snapshot: IndicatorSnapshot, previous_rsi: float | None = None) -> TimeframeDecision:
    rsi = snapshot.rsi
    cvd_delta = snapshot.cvd_delta or 0
    if rsi is None or previous_rsi is None:
        return TimeframeDecision.WAIT
    if previous_rsi <= 50 < rsi and cvd_delta > 0:
        return TimeframeDecision.LONG_TRIGGER
    if previous_rsi >= 50 > rsi and cvd_delta < 0:
        return TimeframeDecision.SHORT_TRIGGER
    return TimeframeDecision.WAIT


def build_multi_tf_decision(
    tf_4h: IndicatorSnapshot,
    tf_1h: IndicatorSnapshot,
    tf_30m: IndicatorSnapshot,
    tf_15m: IndicatorSnapshot,
    previous_15m_rsi: float | None = None,
) -> MultiTimeframeDecision:
    context = evaluate_4h_context(tf_4h)
    permission = evaluate_1h_permission(tf_1h)
    quality = evaluate_30m_quality(tf_30m)
    trigger = evaluate_15m_trigger(tf_15m, previous_rsi=previous_15m_rsi)

    if permission == TimeframeDecision.LONG_ALLOWED:
        if quality == TimeframeDecision.SHORT_CONFIRM:
            return _decision(tf_15m.symbol, "NO_TRADE", "NONE", context, permission, quality, trigger, "direction conflict")
        if quality == TimeframeDecision.LONG_CONFIRM and trigger == TimeframeDecision.LONG_TRIGGER:
            return _decision(tf_15m.symbol, "DIRECT", "LONG", context, permission, quality, trigger, "long direct confirmed")
        if quality == TimeframeDecision.LONG_CONFIRM:
            return _decision(tf_15m.symbol, "PROBE", "LONG", context, permission, quality, trigger, "long higher timeframes confirmed")
        return _decision(tf_15m.symbol, "WAIT", "NONE", context, permission, quality, trigger, "waiting for 30m/15m confirmation")

    if permission == TimeframeDecision.SHORT_ALLOWED:
        if quality == TimeframeDecision.LONG_CONFIRM:
            return _decision(tf_15m.symbol, "NO_TRADE", "NONE", context, permission, quality, trigger, "direction conflict")
        if quality == TimeframeDecision.SHORT_CONFIRM and trigger == TimeframeDecision.SHORT_TRIGGER:
            return _decision(tf_15m.symbol, "DIRECT", "SHORT", context, permission, quality, trigger, "short direct confirmed")
        if quality == TimeframeDecision.SHORT_CONFIRM:
            return _decision(tf_15m.symbol, "PROBE", "SHORT", context, permission, quality, trigger, "short higher timeframes confirmed")
        return _decision(tf_15m.symbol, "WAIT", "NONE", context, permission, quality, trigger, "waiting for 30m/15m confirmation")

    return _decision(tf_15m.symbol, "NO_TRADE", "NONE", context, permission, quality, trigger, "1h direction not allowed")


def _decision(
    symbol: str,
    signal_type: str,
    side: str,
    context: TimeframeDecision,
    permission: TimeframeDecision,
    quality: TimeframeDecision,
    trigger: TimeframeDecision,
    reason: str,
) -> MultiTimeframeDecision:
    return MultiTimeframeDecision(
        symbol=symbol,
        signal_type=signal_type,
        side=side,
        context_4h=context.value,
        permission_1h=permission.value,
        quality_30m=quality.value,
        trigger_15m=trigger.value,
        reason=reason,
    )
