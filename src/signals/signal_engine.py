from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from src.core.constants import SIDE_LONG, SIDE_NONE, SIDE_SHORT


SIGNAL_TYPES = ["LONG", "SHORT", "WAIT", "NO_TRADE"]
SIGNAL_SIDES = [SIDE_LONG, SIDE_SHORT, SIDE_NONE]
ENTRY_MODES = ["PROBE", "DIRECT", "NONE"]
SIGNAL_LEVELS = ["NO_TRADE", "WAIT", "PROBE", "DIRECT"]

SIGNAL_DECISION_FLOW = [
    "read_multi_timeframe_context",
    "check_data_quality",
    "check_cooldown_state",
    "check_portfolio_risk",
    "judge_4h_background",
    "judge_1h_direction",
    "judge_30m_confirmation",
    "judge_15m_trigger",
    "judge_cvd_flow",
    "judge_macd_cci_rsi_boll_structure",
    "summarize_signal_result",
    "output_wait_probe_direct_or_no_trade",
    "record_evidence_fields",
]

TIMEFRAME_ROLES = {
    "4h": "market_background",
    "1h": "direction_permission",
    "30m": "trend_quality_confirmation",
    "15m": "entry_trigger_only",
}

INDICATOR_ROLES = {
    "MACD": ["trend_direction", "momentum_change", "cross", "weakening"],
    "CCI": ["trend_strength", "extreme_deviation", "mean_reversion", "recovery"],
    "BOLL": ["squeeze", "expansion", "midline_retest", "breakout_structure"],
    "RSI": ["overbought_oversold", "pullback_quality", "midline_recovery", "overheat"],
    "CVD": ["active_flow", "flow_direction", "divergence", "accumulation_distribution"],
    "ATR": ["volatility", "risk_context_only", "no_direction_decision"],
}

SCORE_COMPONENTS = ["trend_score", "confirm_score", "trigger_score", "flow_score", "volatility_score"]

SIGNAL_SUB_REASONS = [
    "TREND_ALIGNED",
    "TREND_CONFLICT",
    "MOMENTUM_STRONG",
    "MOMENTUM_WEAK",
    "FLOW_CONFIRMED",
    "FLOW_DIVERGENCE",
    "VOLATILITY_TOO_HIGH",
    "VOLATILITY_TOO_LOW",
    "TRIGGER_READY",
    "TRIGGER_NOT_READY",
    "RSI_OVERHEATED",
    "RSI_RECOVERY",
    "CCI_STRONG",
    "CCI_EXTREME",
    "BOLL_EXPANSION",
    "BOLL_CONTRACTION",
    "COOLDOWN_ACTIVE",
    "RISK_BLOCKED",
    "DATA_INVALID",
]

STATE_MACHINE_MAPPING = {
    "WAIT": "WATCH_*",
    "PROBE": "PROBE_*",
    "DIRECT": "DIRECT_*",
    "NO_TRADE": "FLAT_OR_KEEP_CURRENT",
}

SIGNAL_FORBIDDEN_ACTIONS = [
    "calculate_final_position_size",
    "set_stop_loss_or_take_profit",
    "submit_or_cancel_orders",
    "sync_positions_or_balances",
    "make_final_risk_verdict",
    "call_exchange_adapter",
    "rewrite_entry_mode_in_execution_layer",
]

SIGNAL_EVIDENCE_FIELDS = [
    "symbol",
    "timestamp",
    "signal_type",
    "signal_side",
    "entry_mode",
    "score",
    "confidence",
    "market_state_4h",
    "trend_state_1h",
    "confirm_state_30m",
    "trigger_state_15m",
    "macd_state",
    "cci_state",
    "boll_state",
    "rsi_state",
    "cvd_state",
    "atr_state",
    "reason",
    "sub_reasons",
]


@dataclass(frozen=True)
class SignalEngineContext:
    symbol: str
    timestamp: Any
    market_state_4h: str
    trend_state_1h: str
    confirm_state_30m: str
    trigger_state_15m: str
    indicators_15m: Mapping[str, Any]
    indicators_30m: Mapping[str, Any]
    indicators_1h: Mapping[str, Any]
    indicators_4h: Mapping[str, Any]
    risk_snapshot: Mapping[str, Any]
    position_snapshot: Mapping[str, Any]
    cooldown_state: Mapping[str, Any]
    quality_flag: bool


@dataclass(frozen=True)
class SignalScoreBreakdown:
    trend_score: float = 0.0
    confirm_score: float = 0.0
    trigger_score: float = 0.0
    flow_score: float = 0.0
    volatility_score: float = 0.0

    @property
    def total(self) -> float:
        return round(
            self.trend_score
            + self.confirm_score
            + self.trigger_score
            + self.flow_score
            + self.volatility_score,
            2,
        )


@dataclass(frozen=True)
class SignalResult:
    symbol: str
    timestamp: Any
    signal_type: str
    signal_side: str
    entry_mode: str
    score: float
    confidence: float
    reason: str
    sub_reasons: tuple[str, ...]
    required_state: str
    quality_flag: bool
    metadata: dict[str, Any]

    def __getitem__(self, key: str) -> Any:
        legacy = {
            "side": self.signal_side,
            "mode": self.entry_mode,
        }
        if key in legacy:
            return legacy[key]
        return self.to_dict()[key]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["sub_reasons"] = list(self.sub_reasons)
        payload["side"] = self.signal_side
        return payload


def generate_signal(context: Any) -> SignalResult:
    normalized = _normalize_context(context)
    side = _direction_side(normalized["trend_state_1h"])
    sub_reasons: list[str] = []
    score = SignalScoreBreakdown()

    if not normalized["quality_flag"]:
        return _build_result(normalized, "NO_TRADE", SIDE_NONE, "NONE", score, "DATA_INVALID", ["DATA_INVALID"])

    if _is_active(normalized["cooldown_state"]):
        return _build_result(normalized, "NO_TRADE", SIDE_NONE, "NONE", score, "COOLDOWN_ACTIVE", ["COOLDOWN_ACTIVE"])

    if _risk_blocked(normalized["risk_snapshot"]):
        return _build_result(normalized, "NO_TRADE", SIDE_NONE, "NONE", score, "RISK_BLOCKED", ["RISK_BLOCKED"])

    if side == SIDE_NONE:
        return _build_result(normalized, "NO_TRADE", SIDE_NONE, "NONE", score, "DIRECTION_NOT_ALLOWED", ["TREND_CONFLICT"])

    if _background_conflicts(normalized["market_state_4h"], side):
        return _build_result(normalized, "NO_TRADE", SIDE_NONE, "NONE", score, "HIGHER_TIMEFRAME_CONFLICT", ["TREND_CONFLICT"])

    trend_score = 0.2 if normalized["market_state_4h"] in {"BULL", "BEAR"} else 0.1
    trend_score += 0.2
    score = SignalScoreBreakdown(trend_score=trend_score)
    sub_reasons.append("TREND_ALIGNED")

    if not _confirm_matches(normalized["confirm_state_30m"], side):
        score = _replace_score(score, confirm_score=0.05)
        sub_reasons.extend(["MOMENTUM_WEAK", "TRIGGER_NOT_READY"])
        return _build_result(normalized, "WAIT", SIDE_NONE, "NONE", score, "CONFIRMATION_NOT_READY", sub_reasons)

    score = _replace_score(score, confirm_score=0.2)
    sub_reasons.extend(["MOMENTUM_STRONG", "CCI_STRONG"])

    trigger_ready = _trigger_matches(normalized["trigger_state_15m"], side)
    trigger_partial = _is_partial_trigger(normalized["trigger_state_15m"], side)
    if trigger_ready:
        score = _replace_score(score, trigger_score=0.2)
        sub_reasons.append("TRIGGER_READY")
    elif trigger_partial:
        score = _replace_score(score, trigger_score=0.1)
        sub_reasons.append("TRIGGER_NOT_READY")
    else:
        score = _replace_score(score, trigger_score=0.0)
        sub_reasons.append("TRIGGER_NOT_READY")
        return _build_result(normalized, "WAIT", SIDE_NONE, "NONE", score, "DIRECTION_CONFIRMED_TRIGGER_NOT_READY", sub_reasons)

    cvd_state = _indicator_state(normalized, "cvd")
    if _is_divergence(cvd_state) or _flow_conflicts(cvd_state, side):
        score = _replace_score(score, flow_score=-0.2)
        sub_reasons.append("FLOW_DIVERGENCE")
        entry_mode = "NONE" if _is_divergence(cvd_state) else "PROBE"
        signal_type = "WAIT" if entry_mode == "NONE" else side
        return _build_result(normalized, signal_type, SIDE_NONE if entry_mode == "NONE" else side, entry_mode, score, "FLOW_DIVERGENCE", sub_reasons)

    flow_confirmed = _flow_confirms(cvd_state, side)
    score = _replace_score(score, flow_score=0.2 if flow_confirmed else 0.05)
    if flow_confirmed:
        sub_reasons.append("FLOW_CONFIRMED")

    atr_state = _indicator_state(normalized, "atr")
    boll_state = _indicator_state(normalized, "boll")
    volatility_score = 0.1
    if _contains_any(atr_state, {"TOO_HIGH", "HIGH", "EXPANDED"}):
        volatility_score = -0.1
        sub_reasons.append("VOLATILITY_TOO_HIGH")
    elif _contains_any(atr_state, {"TOO_LOW", "LOW", "SQUEEZE"}):
        volatility_score = 0.0
        sub_reasons.append("VOLATILITY_TOO_LOW")
    if _contains_any(boll_state, {"EXPANSION", "BREAKOUT"}):
        sub_reasons.append("BOLL_EXPANSION")
    if _contains_any(boll_state, {"CONTRACTION", "SQUEEZE"}):
        sub_reasons.append("BOLL_CONTRACTION")
    score = _replace_score(score, volatility_score=volatility_score)

    rsi_state = _indicator_state(normalized, "rsi")
    overheated = side == SIDE_LONG and _contains_any(rsi_state, {"OVERHEATED", "OVERBOUGHT"})
    overcold = side == SIDE_SHORT and _contains_any(rsi_state, {"OVERCOLD", "OVERSOLD"})
    if overheated or overcold:
        sub_reasons.append("RSI_OVERHEATED")
    elif _contains_any(rsi_state, {"RECOVERY", "RECLAIM"}):
        sub_reasons.append("RSI_RECOVERY")

    cci_state = _indicator_state(normalized, "cci")
    if _contains_any(cci_state, {"EXTREME", "OVERHEATED", "OVERCOLD"}):
        sub_reasons.append("CCI_EXTREME")

    far_without_flow = _contains_any(boll_state, {"FAR_FROM_MID", "EXTENDED"}) and not flow_confirmed
    direct_allowed = trigger_ready and flow_confirmed and not overheated and not overcold and not far_without_flow

    if direct_allowed and score.total >= 0.7:
        return _build_result(normalized, side, side, "DIRECT", score, "ALL_LAYERS_ALIGNED", sub_reasons)

    return _build_result(normalized, side, side, "PROBE", score, "HIGHER_TF_CONFIRMED_LOWER_TF_PARTIAL", sub_reasons)


def _normalize_context(context: Any) -> dict[str, Any]:
    if isinstance(context, SignalEngineContext):
        return {
            "symbol": context.symbol,
            "timestamp": context.timestamp,
            "market_state_4h": context.market_state_4h,
            "trend_state_1h": context.trend_state_1h,
            "confirm_state_30m": context.confirm_state_30m,
            "trigger_state_15m": context.trigger_state_15m,
            "indicators_15m": dict(context.indicators_15m),
            "indicators_30m": dict(context.indicators_30m),
            "indicators_1h": dict(context.indicators_1h),
            "indicators_4h": dict(context.indicators_4h),
            "risk_snapshot": dict(context.risk_snapshot),
            "position_snapshot": dict(context.position_snapshot),
            "cooldown_state": dict(context.cooldown_state),
            "quality_flag": context.quality_flag,
        }

    if hasattr(context, "signal_type") and hasattr(context, "side"):
        entry_mode = getattr(context, "signal_type")
        side = getattr(context, "side")
        trend = "LONG_ALLOWED" if side == SIDE_LONG else "SHORT_ALLOWED" if side == SIDE_SHORT else "NO_TRADE"
        return {
            "symbol": getattr(context, "symbol", ""),
            "timestamp": getattr(context, "timestamp", None),
            "market_state_4h": getattr(context, "context_4h", "NEUTRAL"),
            "trend_state_1h": getattr(context, "permission_1h", trend),
            "confirm_state_30m": getattr(context, "quality_30m", f"{side}_CONFIRM" if side != SIDE_NONE else "WAIT"),
            "trigger_state_15m": getattr(context, "trigger_15m", side),
            "indicators_15m": {"cvd": side if entry_mode == "DIRECT" else "NEUTRAL"},
            "indicators_30m": {},
            "indicators_1h": {},
            "indicators_4h": {},
            "risk_snapshot": {"risk_blocked": False},
            "position_snapshot": {},
            "cooldown_state": {"active": False},
            "quality_flag": entry_mode != "NO_TRADE",
        }

    if not isinstance(context, Mapping):
        raise TypeError("context must be a mapping, SignalEngineContext, or multi-timeframe decision object")

    return {
        "symbol": context.get("symbol", ""),
        "timestamp": context.get("timestamp"),
        "market_state_4h": context.get("market_state_4h", context.get("context_4h", "NEUTRAL")),
        "trend_state_1h": context.get("trend_state_1h", context.get("permission", context.get("permission_1h", "NO_TRADE"))),
        "confirm_state_30m": context.get("confirm_state_30m", context.get("quality", context.get("quality_30m", "WAIT"))),
        "trigger_state_15m": context.get("trigger_state_15m", context.get("trigger", context.get("trigger_15m", "WAIT"))),
        "indicators_15m": dict(context.get("indicators_15m", {})),
        "indicators_30m": dict(context.get("indicators_30m", {})),
        "indicators_1h": dict(context.get("indicators_1h", {})),
        "indicators_4h": dict(context.get("indicators_4h", {})),
        "risk_snapshot": dict(context.get("risk_snapshot", {})),
        "position_snapshot": dict(context.get("position_snapshot", {})),
        "cooldown_state": dict(context.get("cooldown_state", {})),
        "quality_flag": bool(context.get("quality_flag", True)),
    }


def _build_result(
    context: Mapping[str, Any],
    signal_type: str,
    side: str,
    entry_mode: str,
    score: SignalScoreBreakdown,
    reason: str,
    sub_reasons: list[str],
) -> SignalResult:
    normalized_score = max(0.0, min(1.0, round(score.total, 2)))
    evidence = {
        "symbol": context["symbol"],
        "timestamp": context["timestamp"],
        "signal_type": signal_type,
        "signal_side": side,
        "entry_mode": entry_mode,
        "score": normalized_score,
        "confidence": normalized_score,
        "market_state_4h": context["market_state_4h"],
        "trend_state_1h": context["trend_state_1h"],
        "confirm_state_30m": context["confirm_state_30m"],
        "trigger_state_15m": context["trigger_state_15m"],
        "macd_state": _indicator_state(context, "macd"),
        "cci_state": _indicator_state(context, "cci"),
        "boll_state": _indicator_state(context, "boll"),
        "rsi_state": _indicator_state(context, "rsi"),
        "cvd_state": _indicator_state(context, "cvd"),
        "atr_state": _indicator_state(context, "atr"),
        "reason": reason,
        "sub_reasons": list(dict.fromkeys(sub_reasons)),
    }
    return SignalResult(
        symbol=context["symbol"],
        timestamp=context["timestamp"],
        signal_type=signal_type,
        signal_side=side,
        entry_mode=entry_mode,
        score=normalized_score,
        confidence=normalized_score,
        reason=reason,
        sub_reasons=tuple(evidence["sub_reasons"]),
        required_state=_required_state(signal_type, side, entry_mode),
        quality_flag=bool(context["quality_flag"]),
        metadata={
            "score_breakdown": asdict(score),
            "evidence": evidence,
            "state_machine_mapping": STATE_MACHINE_MAPPING.get(entry_mode, STATE_MACHINE_MAPPING.get(signal_type)),
        },
    )


def _replace_score(score: SignalScoreBreakdown, **changes: float) -> SignalScoreBreakdown:
    values = asdict(score)
    values.update(changes)
    return SignalScoreBreakdown(**values)


def _direction_side(value: str) -> str:
    normalized = str(value).upper()
    if normalized in {"LONG_ALLOWED", "LONG", "BULL"}:
        return SIDE_LONG
    if normalized in {"SHORT_ALLOWED", "SHORT", "BEAR"}:
        return SIDE_SHORT
    return SIDE_NONE


def _background_conflicts(market_state: str, side: str) -> bool:
    state = str(market_state).upper()
    return (side == SIDE_LONG and state == "BEAR") or (side == SIDE_SHORT and state == "BULL")


def _confirm_matches(value: str, side: str) -> bool:
    normalized = str(value).upper()
    allowed = {"LONG": {"LONG_CONFIRM", "LONG_CONFIRMED", "LONG", "BULL", "POSITIVE"}, "SHORT": {"SHORT_CONFIRM", "SHORT_CONFIRMED", "SHORT", "BEAR", "NEGATIVE"}}
    return normalized in allowed.get(side, set())


def _trigger_matches(value: str, side: str) -> bool:
    normalized = str(value).upper()
    return normalized in {side, f"{side}_TRIGGER", f"{side}_READY", "READY", "TRIGGER_READY"}


def _is_partial_trigger(value: str, side: str) -> bool:
    normalized = str(value).upper()
    return normalized in {f"{side}_PARTIAL", "PARTIAL", "EARLY", "WATCH"}


def _risk_blocked(snapshot: Mapping[str, Any]) -> bool:
    return bool(
        snapshot.get("risk_blocked")
        or snapshot.get("blocked")
        or snapshot.get("portfolio_risk_blocked")
        or str(snapshot.get("status", "")).upper() in {"BLOCKED", "RISK_BLOCKED"}
    )


def _is_active(snapshot: Mapping[str, Any]) -> bool:
    return bool(snapshot.get("active") or snapshot.get("cooldown_active") or str(snapshot.get("state", "")).upper() == "ACTIVE")


def _indicator_state(context: Mapping[str, Any], key: str) -> str:
    for bucket in ("indicators_15m", "indicators_30m", "indicators_1h", "indicators_4h"):
        value = context[bucket].get(key)
        if value is not None:
            return str(value).upper()
    return "UNKNOWN"


def _flow_confirms(cvd_state: str, side: str) -> bool:
    return str(cvd_state).upper() in {side, f"{side}_CONFIRMED", "CONFIRMED", "FLOW_CONFIRMED"}


def _flow_conflicts(cvd_state: str, side: str) -> bool:
    state = str(cvd_state).upper()
    return (side == SIDE_LONG and state in {"SHORT", "SELL", "BEAR"}) or (
        side == SIDE_SHORT and state in {"LONG", "BUY", "BULL"}
    )


def _is_divergence(cvd_state: str) -> bool:
    return "DIVERGENCE" in str(cvd_state).upper()


def _contains_any(value: str, needles: set[str]) -> bool:
    state = str(value).upper()
    return any(needle in state for needle in needles)


def _required_state(signal_type: str, side: str, entry_mode: str) -> str:
    if entry_mode in {"DIRECT", "PROBE"} and side in {SIDE_LONG, SIDE_SHORT}:
        return f"{entry_mode}_{side}"
    if signal_type == "WAIT":
        return "WATCH_*"
    return "FLAT"
