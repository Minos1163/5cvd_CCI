from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from src.core.models import IndicatorSnapshot


TIMEFRAME_ROLES = {
    "4h": "background_reference",
    "1h": "direction_confirmation",
    "30m": "trend_quality_confirmation",
    "15m": "execution_trigger",
}
TIMEFRAME_PRIORITY = (
    "data_quality",
    "risk_constraints",
    "4h_background",
    "1h_direction",
    "30m_quality",
    "15m_trigger",
    "position_executability",
    "execution_layer",
)
TIMEFRAME_OUTPUT_FIELDS = (
    "symbol",
    "timeframe",
    "timestamp",
    "state",
    "confidence",
    "reason",
    "sub_reasons",
    "quality_flag",
    "metadata",
)
TIMEFRAME_FORBIDDEN_ACTIONS = (
    "4h_hard_veto",
    "15m_direction_override",
    "independent_timeframe_commands",
    "unfinished_high_tf_final_signal",
    "nested_patch_conditions",
    "execution_reinterprets_context",
)
TIMEFRAME_STATE_SETS = {
    "4h": ("BULL", "BEAR", "NEUTRAL"),
    "1h": ("LONG_ALLOWED", "SHORT_ALLOWED", "NO_TRADE"),
    "30m": ("CONFIRMED", "WEAK", "INVALID", "TRANSITION"),
    "15m": ("DIRECT", "PROBE", "WAIT", "NO_TRADE"),
}


class TimeframeDecision(str, Enum):
    BULL = "BULL"
    BEAR = "BEAR"
    NEUTRAL = "NEUTRAL"
    LONG_ALLOWED = "LONG_ALLOWED"
    SHORT_ALLOWED = "SHORT_ALLOWED"
    NO_TRADE = "NO_TRADE"
    CONFIRMED = "CONFIRMED"
    INVALID = "INVALID"
    TRANSITION = "TRANSITION"
    LONG_CONFIRM = "LONG_CONFIRM"
    SHORT_CONFIRM = "SHORT_CONFIRM"
    WEAK = "WEAK"
    LONG_TRIGGER = "LONG_TRIGGER"
    SHORT_TRIGGER = "SHORT_TRIGGER"
    DIRECT = "DIRECT"
    PROBE = "PROBE"
    WAIT = "WAIT"


@dataclass(frozen=True)
class TimeframeRuleCheck:
    passed: bool
    reason: str


@dataclass(frozen=True)
class TimeframeResult:
    symbol: str
    timeframe: str
    timestamp: int
    state: str
    confidence: float
    reason: str
    sub_reasons: tuple[str, ...]
    quality_flag: bool | str
    metadata: dict[str, Any]


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
    quality_flag: bool | str = True
    timeframe_results: tuple[TimeframeResult, ...] = ()


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


def evaluate_30m_quality_state(snapshot: IndicatorSnapshot) -> TimeframeDecision:
    directional = evaluate_30m_quality(snapshot)
    if directional in {TimeframeDecision.LONG_CONFIRM, TimeframeDecision.SHORT_CONFIRM}:
        return TimeframeDecision.CONFIRMED
    if (snapshot.macd_hist is not None and abs(snapshot.macd_hist) < 0.000001) or snapshot.cci is None:
        return TimeframeDecision.TRANSITION
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


def build_timeframe_results(
    tf_4h: IndicatorSnapshot,
    tf_1h: IndicatorSnapshot,
    tf_30m: IndicatorSnapshot,
    tf_15m: IndicatorSnapshot,
    previous_15m_rsi: float | None = None,
    quality_flags: Mapping[str, bool | str] | None = None,
) -> tuple[TimeframeResult, ...]:
    flags = dict(quality_flags or {})
    context = evaluate_4h_context(tf_4h)
    permission = evaluate_1h_permission(tf_1h)
    quality = evaluate_30m_quality_state(tf_30m)
    trigger = evaluate_15m_trigger(tf_15m, previous_rsi=previous_15m_rsi)

    return (
        _timeframe_result(tf_4h, "4h", context.value, _confidence_from_snapshot(tf_4h), "4h_background", ("BACKGROUND",), flags.get("4h", True)),
        _timeframe_result(tf_1h, "1h", permission.value, _confidence_from_snapshot(tf_1h), "1h_direction", ("DIRECTION",), flags.get("1h", True)),
        _timeframe_result(
            tf_30m,
            "30m",
            quality.value,
            _confidence_from_snapshot(tf_30m),
            "30m_quality",
            (evaluate_30m_quality(tf_30m).value,),
            flags.get("30m", True),
            {"directional_quality": evaluate_30m_quality(tf_30m).value},
        ),
        _timeframe_result(tf_15m, "15m", _trigger_state_for_result(trigger), _confidence_from_snapshot(tf_15m), "15m_trigger", (trigger.value,), flags.get("15m", True)),
    )


def validate_timeframe_result(result: TimeframeResult) -> TimeframeRuleCheck:
    if result.timeframe not in TIMEFRAME_ROLES:
        return TimeframeRuleCheck(False, f"unsupported timeframe: {result.timeframe}")
    if result.quality_flag in {False, "stale"}:
        return TimeframeRuleCheck(False, "timeframe result quality cannot drive context")
    if result.state not in TIMEFRAME_STATE_SETS[result.timeframe]:
        return TimeframeRuleCheck(False, f"unsupported state for {result.timeframe}: {result.state}")
    if not 0 <= result.confidence <= 1:
        return TimeframeRuleCheck(False, "confidence must be between 0 and 1")
    return TimeframeRuleCheck(True, "timeframe result approved")


def build_multi_tf_decision(
    tf_4h: IndicatorSnapshot,
    tf_1h: IndicatorSnapshot,
    tf_30m: IndicatorSnapshot,
    tf_15m: IndicatorSnapshot,
    previous_15m_rsi: float | None = None,
    quality_flags: Mapping[str, bool | str] | None = None,
) -> MultiTimeframeDecision:
    results = build_timeframe_results(tf_4h, tf_1h, tf_30m, tf_15m, previous_15m_rsi, quality_flags)
    invalid = [item for item in results if not validate_timeframe_result(item).passed]
    context = evaluate_4h_context(tf_4h)
    permission = evaluate_1h_permission(tf_1h)
    quality = evaluate_30m_quality(tf_30m)
    trigger = evaluate_15m_trigger(tf_15m, previous_rsi=previous_15m_rsi)

    if invalid:
        return _decision(tf_15m.symbol, "NO_TRADE", "NONE", context, permission, quality, trigger, "data quality invalid", False, results)

    if permission == TimeframeDecision.LONG_ALLOWED:
        if quality == TimeframeDecision.SHORT_CONFIRM:
            return _decision(tf_15m.symbol, "NO_TRADE", "NONE", context, permission, quality, trigger, "direction conflict", True, results)
        if quality == TimeframeDecision.LONG_CONFIRM and trigger == TimeframeDecision.LONG_TRIGGER:
            if _background_conflicts(context, "LONG"):
                return _decision(tf_15m.symbol, "PROBE", "LONG", context, permission, quality, trigger, "4h conflict downgraded direct", True, results)
            return _decision(tf_15m.symbol, "DIRECT", "LONG", context, permission, quality, trigger, "long direct confirmed", True, results)
        if quality == TimeframeDecision.LONG_CONFIRM:
            return _decision(tf_15m.symbol, "PROBE", "LONG", context, permission, quality, trigger, "long higher timeframes confirmed", True, results)
        return _decision(tf_15m.symbol, "WAIT", "NONE", context, permission, quality, trigger, "waiting for 30m/15m confirmation", True, results)

    if permission == TimeframeDecision.SHORT_ALLOWED:
        if quality == TimeframeDecision.LONG_CONFIRM:
            return _decision(tf_15m.symbol, "NO_TRADE", "NONE", context, permission, quality, trigger, "direction conflict", True, results)
        if quality == TimeframeDecision.SHORT_CONFIRM and trigger == TimeframeDecision.SHORT_TRIGGER:
            if _background_conflicts(context, "SHORT"):
                return _decision(tf_15m.symbol, "PROBE", "SHORT", context, permission, quality, trigger, "4h conflict downgraded direct", True, results)
            return _decision(tf_15m.symbol, "DIRECT", "SHORT", context, permission, quality, trigger, "short direct confirmed", True, results)
        if quality == TimeframeDecision.SHORT_CONFIRM:
            return _decision(tf_15m.symbol, "PROBE", "SHORT", context, permission, quality, trigger, "short higher timeframes confirmed", True, results)
        return _decision(tf_15m.symbol, "WAIT", "NONE", context, permission, quality, trigger, "waiting for 30m/15m confirmation", True, results)

    return _decision(tf_15m.symbol, "NO_TRADE", "NONE", context, permission, quality, trigger, "1h direction not allowed", True, results)


def _timeframe_result(
    snapshot: IndicatorSnapshot,
    timeframe: str,
    state: str,
    confidence: float,
    reason: str,
    sub_reasons: tuple[str, ...],
    quality_flag: bool | str,
    metadata: dict[str, Any] | None = None,
) -> TimeframeResult:
    return TimeframeResult(
        symbol=snapshot.symbol,
        timeframe=timeframe,
        timestamp=snapshot.close_time,
        state=state,
        confidence=max(0.0, min(confidence, 1.0)),
        reason=reason,
        sub_reasons=sub_reasons,
        quality_flag=quality_flag,
        metadata=metadata or {},
    )


def _trigger_state_for_result(trigger: TimeframeDecision) -> str:
    if trigger in {TimeframeDecision.LONG_TRIGGER, TimeframeDecision.SHORT_TRIGGER}:
        return TimeframeDecision.DIRECT.value
    return TimeframeDecision.WAIT.value


def _confidence_from_snapshot(snapshot: IndicatorSnapshot) -> float:
    score = 0.0
    if snapshot.macd is not None:
        score += 0.25
    if snapshot.cci is not None:
        score += 0.25
    if snapshot.cvd_delta is not None:
        score += 0.25
    if snapshot.rsi is not None or snapshot.boll_mid is not None:
        score += 0.25
    return min(score, 1.0)


def _background_conflicts(context: TimeframeDecision, side: str) -> bool:
    return (side == "LONG" and context == TimeframeDecision.BEAR) or (
        side == "SHORT" and context == TimeframeDecision.BULL
    )


def _decision(
    symbol: str,
    signal_type: str,
    side: str,
    context: TimeframeDecision,
    permission: TimeframeDecision,
    quality: TimeframeDecision,
    trigger: TimeframeDecision,
    reason: str,
    quality_flag: bool | str,
    timeframe_results: tuple[TimeframeResult, ...],
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
        quality_flag=quality_flag,
        timeframe_results=timeframe_results,
    )
