from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from src.risk.exit_engine import EXIT_PRIORITY, forced_exit_actions, plan_take_profit_actions, select_highest_priority_action
from src.risk.stop_engine import initial_atr_stop


RISK_LEVELS = ["LOW", "NORMAL", "HIGH", "EXTREME", "BLOCKED"]
RISK_DECISION_FLOW = [
    "check_data_quality",
    "check_cooldown",
    "check_account_risk",
    "check_portfolio_risk",
    "check_symbol_risk",
    "check_volatility_risk",
    "check_stop_distance",
    "check_position_executability",
    "check_add_reduce_exit",
    "output_risk_result",
]
RISK_SCORE_COMPONENTS = [
    "account_risk_score",
    "portfolio_risk_score",
    "symbol_risk_score",
    "volatility_risk_score",
    "cooldown_risk_score",
    "data_quality_risk_score",
]
RISK_REQUIRED_INPUTS = [
    "symbol",
    "timestamp",
    "signal_type",
    "signal_side",
    "entry_mode",
    "account_equity",
    "available_margin",
    "used_margin",
    "open_positions",
    "portfolio_exposure",
    "symbol_exposure",
    "daily_pnl",
    "weekly_pnl",
    "max_drawdown",
    "atr",
    "stop_pct",
    "quality_flag",
    "cooldown_state",
    "market_state_4h",
    "trend_state_1h",
    "confirm_state_30m",
    "trigger_state_15m",
]
RISK_OUTPUT_FIELDS = [
    "allow_trade",
    "allow_add",
    "allow_reduce",
    "allow_exit",
    "risk_level",
    "risk_reason",
    "risk_score",
    "position_size_factor",
    "stop_distance",
    "stop_pct",
    "take_profit_plan",
    "cooldown_required",
    "cooldown_bars",
    "portfolio_blocked",
    "metrics_snapshot",
    "metadata",
]
RISK_SNAPSHOT_FIELDS = [
    "symbol",
    "timestamp",
    "account_equity",
    "available_margin",
    "daily_pnl",
    "weekly_pnl",
    "max_drawdown",
    "portfolio_exposure",
    "symbol_exposure",
    "atr",
    "stop_pct",
    "risk_score",
    "risk_level",
    "allow_trade",
    "allow_add",
    "allow_reduce",
    "allow_exit",
    "risk_reason",
]
RISK_FORBIDDEN_ACTIONS = [
    "generate_trade_signal",
    "submit_or_cancel_orders",
    "change_signal_side",
    "promote_probe_to_direct",
    "calculate_exchange_precision_quantity",
    "maintain_exchange_connection",
    "use_different_live_and_backtest_rules",
]
DEFAULT_RISK_LIMITS = {
    "daily_loss_limit_pct": 0.05,
    "weekly_loss_limit_pct": 0.12,
    "max_drawdown_pct": 0.20,
    "max_symbol_exposure_pct": 0.20,
    "max_portfolio_exposure_pct": 0.75,
    "max_open_positions": 5,
    "risk_per_trade_pct": 0.01,
    "min_stop_pct": 0.005,
    "max_stop_pct": 0.08,
    "stop_atr_mult": 1.5,
    "normal_cooldown_bars": 4,
}
PROBE_POSITION_FACTOR = 0.25
DIRECT_POSITION_FACTOR = 1.0


@dataclass(frozen=True)
class RiskContext:
    symbol: str
    timestamp: Any
    signal_type: str
    signal_side: str
    entry_mode: str
    account_equity: float
    available_margin: float
    used_margin: float
    open_positions: int
    portfolio_exposure: float
    symbol_exposure: float
    daily_pnl: float
    weekly_pnl: float
    max_drawdown: float
    atr: float
    stop_pct: float
    quality_flag: bool
    cooldown_state: Mapping[str, Any]
    market_state_4h: str
    trend_state_1h: str
    confirm_state_30m: str
    trigger_state_15m: str
    entry_price: float = 100.0
    volatility_state: str = "NORMAL"
    stop_hit: bool = False
    direction_reversal: bool = False
    exchange_error: bool = False
    risk_limits: Mapping[str, float] | None = None


@dataclass(frozen=True)
class RiskScoreBreakdown:
    account_risk_score: int = 0
    portfolio_risk_score: int = 0
    symbol_risk_score: int = 0
    volatility_risk_score: int = 0
    cooldown_risk_score: int = 0
    data_quality_risk_score: int = 0

    @property
    def total(self) -> int:
        return sum(asdict(self).values())


@dataclass(frozen=True)
class RiskResult:
    allow_trade: bool
    allow_add: bool
    allow_reduce: bool
    allow_exit: bool
    risk_level: str
    risk_reason: str
    risk_score: int
    position_size_factor: float
    stop_distance: float
    stop_pct: float
    take_profit_plan: list[dict[str, Any]]
    cooldown_required: bool
    cooldown_bars: int
    portfolio_blocked: bool
    metrics_snapshot: dict[str, Any]
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_risk(context: RiskContext | Mapping[str, Any]) -> RiskResult:
    ctx = _normalize_context(context)
    limits = _risk_limits(ctx)
    score = RiskScoreBreakdown()
    stop_distance, effective_stop_pct = _stop_values(ctx, limits)

    if not ctx["quality_flag"]:
        score = _replace_score(score, data_quality_risk_score=8)
        return _blocked(ctx, score, "DATA_QUALITY_BLOCKED", stop_distance, effective_stop_pct, cooldown_required=True)

    if _cooldown_active(ctx["cooldown_state"]):
        score = _replace_score(score, cooldown_risk_score=8)
        return _blocked(ctx, score, "COOLDOWN_ACTIVE", stop_distance, effective_stop_pct, cooldown_required=False)

    account_reason = _account_block_reason(ctx, limits)
    if account_reason is not None:
        score = _replace_score(score, account_risk_score=8)
        return _blocked(ctx, score, account_reason, stop_distance, effective_stop_pct, cooldown_required=True)

    portfolio_reason = _portfolio_block_reason(ctx, limits)
    if portfolio_reason is not None:
        score = _replace_score(score, portfolio_risk_score=8)
        return _blocked(ctx, score, portfolio_reason, stop_distance, effective_stop_pct, cooldown_required=True, portfolio_blocked=True)

    symbol_reason = _symbol_block_reason(ctx, limits)
    if symbol_reason is not None:
        score = _replace_score(score, symbol_risk_score=8)
        return _blocked(ctx, score, symbol_reason, stop_distance, effective_stop_pct, cooldown_required=True)

    stop_reason = _stop_block_reason(ctx, limits, effective_stop_pct)
    if stop_reason is not None:
        score = _replace_score(score, volatility_risk_score=8)
        return _blocked(ctx, score, stop_reason, stop_distance, effective_stop_pct, cooldown_required=False)

    if ctx["available_margin"] <= 0:
        score = _replace_score(score, account_risk_score=8)
        return _blocked(ctx, score, "AVAILABLE_MARGIN_INSUFFICIENT", stop_distance, effective_stop_pct, cooldown_required=False)

    score = _score_soft_risk(ctx, limits, score)
    forced = select_highest_priority_action(
        forced_exit_actions(
            stop_hit=ctx["stop_hit"],
            portfolio_risk=ctx["portfolio_exposure"] >= limits["max_portfolio_exposure_pct"] * 0.95,
            direction_reversal=ctx["direction_reversal"],
            volatility_anomaly=_volatility_state(ctx) == "EXTREME",
        )
    )
    if forced is not None and forced.action_type.value in {"FORCED_STOP", "PORTFOLIO_RISK"}:
        score = _replace_score(score, portfolio_risk_score=max(score.portfolio_risk_score, 6))
        return _result(
            ctx,
            score,
            "EXTREME",
            "FORCED_EXIT_REQUIRED",
            False,
            False,
            True,
            True,
            0.0,
            stop_distance,
            effective_stop_pct,
            cooldown_required=True,
            portfolio_blocked=forced.action_type.value == "PORTFOLIO_RISK",
            exit_action=forced,
        )

    risk_level = _risk_level(score.total)
    position_factor = _position_factor(ctx, risk_level)
    allow_trade = risk_level not in {"EXTREME", "BLOCKED"} and position_factor > 0
    allow_reduce = risk_level in {"HIGH", "EXTREME"} or ctx["portfolio_exposure"] >= limits["max_portfolio_exposure_pct"] * 0.85
    allow_exit = bool(forced or risk_level in {"HIGH", "EXTREME"})

    if risk_level == "HIGH":
        reason = "TREND_OK_BUT_VOLATILITY_HIGH" if _volatility_state(ctx) == "HIGH" else "RISK_HIGH_POSITION_REDUCED"
    elif risk_level == "LOW":
        reason = "RISK_LOW"
    else:
        reason = "FULL_CONFIRMATION_AND_RISK_OK"

    return _result(
        ctx,
        score,
        risk_level,
        reason,
        allow_trade,
        _allow_add(ctx, risk_level),
        allow_reduce,
        allow_exit,
        position_factor,
        stop_distance,
        effective_stop_pct,
        cooldown_required=False,
        portfolio_blocked=False,
        exit_action=forced,
    )


def _normalize_context(context: RiskContext | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(context, RiskContext):
        data = asdict(context)
    else:
        data = dict(context)
    normalized = {field: data.get(field) for field in RISK_REQUIRED_INPUTS}
    normalized.update(
        {
            "entry_price": data.get("entry_price", 100.0),
            "volatility_state": data.get("volatility_state", "NORMAL"),
            "stop_hit": bool(data.get("stop_hit", False)),
            "direction_reversal": bool(data.get("direction_reversal", False)),
            "exchange_error": bool(data.get("exchange_error", False)),
            "risk_limits": dict(data.get("risk_limits") or {}),
        }
    )
    normalized["symbol"] = str(normalized.get("symbol") or "").upper()
    normalized["signal_type"] = str(normalized.get("signal_type") or "NO_TRADE").upper()
    normalized["signal_side"] = str(normalized.get("signal_side") or "NONE").upper()
    normalized["entry_mode"] = str(normalized.get("entry_mode") or "NONE").upper()
    normalized["cooldown_state"] = dict(normalized.get("cooldown_state") or {})
    normalized["quality_flag"] = bool(normalized.get("quality_flag"))
    for key in (
        "account_equity",
        "available_margin",
        "used_margin",
        "portfolio_exposure",
        "symbol_exposure",
        "daily_pnl",
        "weekly_pnl",
        "max_drawdown",
        "atr",
        "stop_pct",
        "entry_price",
    ):
        normalized[key] = float(normalized.get(key) or 0.0)
    normalized["open_positions"] = int(normalized.get("open_positions") or 0)
    return normalized


def _risk_limits(ctx: Mapping[str, Any]) -> dict[str, float]:
    limits = dict(DEFAULT_RISK_LIMITS)
    limits.update(ctx.get("risk_limits") or {})
    return limits


def _blocked(
    ctx: Mapping[str, Any],
    score: RiskScoreBreakdown,
    reason: str,
    stop_distance: float,
    stop_pct: float,
    cooldown_required: bool,
    portfolio_blocked: bool = False,
) -> RiskResult:
    return _result(
        ctx,
        score,
        "BLOCKED",
        reason,
        False,
        False,
        portfolio_blocked or reason in {"WEEKLY_LOSS_LIMIT_REACHED", "MAX_DRAWDOWN_LIMIT_REACHED"},
        True,
        0.0,
        stop_distance,
        stop_pct,
        cooldown_required=cooldown_required,
        portfolio_blocked=portfolio_blocked,
        exit_action=None,
    )


def _result(
    ctx: Mapping[str, Any],
    score: RiskScoreBreakdown,
    risk_level: str,
    risk_reason: str,
    allow_trade: bool,
    allow_add: bool,
    allow_reduce: bool,
    allow_exit: bool,
    position_size_factor: float,
    stop_distance: float,
    stop_pct: float,
    cooldown_required: bool,
    portfolio_blocked: bool,
    exit_action: Any,
) -> RiskResult:
    take_profit_plan = []
    if ctx["signal_side"] in {"LONG", "SHORT"} and stop_distance > 0 and ctx["entry_price"] > 0:
        stop_price = ctx["entry_price"] - stop_distance if ctx["signal_side"] == "LONG" else ctx["entry_price"] + stop_distance
        take_profit_plan = [
            {
                "action_type": action.action_type.value,
                "reason": action.reason,
                "reduce_pct": action.reduce_pct,
                "target_price": action.target_price,
            }
            for action in plan_take_profit_actions(ctx["entry_price"], stop_price, ctx["signal_side"])
        ]
    snapshot = {
        "symbol": ctx["symbol"],
        "timestamp": ctx["timestamp"],
        "account_equity": ctx["account_equity"],
        "available_margin": ctx["available_margin"],
        "daily_pnl": ctx["daily_pnl"],
        "weekly_pnl": ctx["weekly_pnl"],
        "max_drawdown": ctx["max_drawdown"],
        "portfolio_exposure": ctx["portfolio_exposure"],
        "symbol_exposure": ctx["symbol_exposure"],
        "atr": ctx["atr"],
        "stop_pct": stop_pct,
        "risk_score": score.total,
        "risk_level": risk_level,
        "allow_trade": allow_trade,
        "allow_add": allow_add,
        "allow_reduce": allow_reduce,
        "allow_exit": allow_exit,
        "risk_reason": risk_reason,
    }
    return RiskResult(
        allow_trade=allow_trade,
        allow_add=allow_add,
        allow_reduce=allow_reduce,
        allow_exit=allow_exit,
        risk_level=risk_level,
        risk_reason=risk_reason,
        risk_score=score.total,
        position_size_factor=position_size_factor,
        stop_distance=stop_distance,
        stop_pct=stop_pct,
        take_profit_plan=take_profit_plan,
        cooldown_required=cooldown_required,
        cooldown_bars=int(_risk_limits(ctx)["normal_cooldown_bars"]) if cooldown_required else 0,
        portfolio_blocked=portfolio_blocked,
        metrics_snapshot=snapshot,
        metadata={
            "decision_flow": RISK_DECISION_FLOW,
            "score_breakdown": asdict(score),
            "exit_action": None if exit_action is None else asdict(exit_action),
            "exit_priority": [item.value for item in EXIT_PRIORITY],
            "forbidden_actions": RISK_FORBIDDEN_ACTIONS,
        },
    )


def _stop_values(ctx: Mapping[str, Any], limits: Mapping[str, float]) -> tuple[float, float]:
    if ctx["entry_price"] <= 0 or ctx["atr"] <= 0 or ctx["signal_side"] not in {"LONG", "SHORT"}:
        return 0.0, ctx["stop_pct"]
    plan = initial_atr_stop(ctx["entry_price"], ctx["atr"], limits["stop_atr_mult"], ctx["signal_side"])
    effective_stop_pct = ctx["stop_pct"] if ctx["stop_pct"] > 0 else plan.stop_pct
    return ctx["entry_price"] * effective_stop_pct, effective_stop_pct


def _account_block_reason(ctx: Mapping[str, Any], limits: Mapping[str, float]) -> str | None:
    if ctx["account_equity"] <= 0:
        return "ACCOUNT_EQUITY_INVALID"
    if ctx["daily_pnl"] <= -ctx["account_equity"] * limits["daily_loss_limit_pct"]:
        return "DAILY_LOSS_LIMIT_REACHED"
    if ctx["weekly_pnl"] <= -ctx["account_equity"] * limits["weekly_loss_limit_pct"]:
        return "WEEKLY_LOSS_LIMIT_REACHED"
    if ctx["max_drawdown"] >= limits["max_drawdown_pct"]:
        return "MAX_DRAWDOWN_LIMIT_REACHED"
    return None


def _portfolio_block_reason(ctx: Mapping[str, Any], limits: Mapping[str, float]) -> str | None:
    if ctx["portfolio_exposure"] >= limits["max_portfolio_exposure_pct"]:
        return "PORTFOLIO_EXPOSURE_LIMIT_REACHED"
    if ctx["open_positions"] >= int(limits["max_open_positions"]):
        return "MAX_OPEN_POSITIONS_REACHED"
    return None


def _symbol_block_reason(ctx: Mapping[str, Any], limits: Mapping[str, float]) -> str | None:
    if ctx["symbol_exposure"] >= limits["max_symbol_exposure_pct"]:
        return "SYMBOL_EXPOSURE_LIMIT_REACHED"
    return None


def _stop_block_reason(ctx: Mapping[str, Any], limits: Mapping[str, float], stop_pct: float) -> str | None:
    if ctx["atr"] <= 0:
        return "ATR_UNAVAILABLE"
    if stop_pct <= 0:
        return "STOP_DISTANCE_INVALID"
    if stop_pct < limits["min_stop_pct"]:
        return "STOP_DISTANCE_TOO_SMALL"
    if stop_pct > limits["max_stop_pct"]:
        return "STOP_DISTANCE_TOO_LARGE"
    return None


def _score_soft_risk(ctx: Mapping[str, Any], limits: Mapping[str, float], score: RiskScoreBreakdown) -> RiskScoreBreakdown:
    account_score = 2
    portfolio_score = 0
    symbol_score = 0
    volatility_score = 0
    if ctx["daily_pnl"] < 0:
        account_score += 1
    if ctx["weekly_pnl"] < 0:
        account_score += 1
    if ctx["max_drawdown"] >= limits["max_drawdown_pct"] * 0.5:
        account_score += 1
    if ctx["portfolio_exposure"] >= limits["max_portfolio_exposure_pct"] * 0.85:
        portfolio_score += 2
    if ctx["symbol_exposure"] >= limits["max_symbol_exposure_pct"] * 0.75:
        symbol_score += 2
    volatility = _volatility_state(ctx)
    if volatility == "HIGH":
        volatility_score += 3
    elif volatility == "EXTREME":
        volatility_score += 5
    elif volatility == "LOW":
        volatility_score += 1
    return _replace_score(
        score,
        account_risk_score=account_score,
        portfolio_risk_score=portfolio_score,
        symbol_risk_score=symbol_score,
        volatility_risk_score=volatility_score,
    )


def _risk_level(score: int) -> str:
    if score <= 1:
        return "LOW"
    if score <= 3:
        return "NORMAL"
    if score <= 5:
        return "HIGH"
    if score <= 7:
        return "EXTREME"
    return "BLOCKED"


def _position_factor(ctx: Mapping[str, Any], risk_level: str) -> float:
    if risk_level in {"EXTREME", "BLOCKED"}:
        return 0.0
    base = PROBE_POSITION_FACTOR if ctx["entry_mode"] == "PROBE" else DIRECT_POSITION_FACTOR
    if risk_level == "HIGH":
        return min(base, PROBE_POSITION_FACTOR)
    if risk_level == "LOW" and ctx["entry_mode"] == "DIRECT":
        return DIRECT_POSITION_FACTOR
    return base


def _allow_add(ctx: Mapping[str, Any], risk_level: str) -> bool:
    if risk_level not in {"LOW", "NORMAL"}:
        return False
    if ctx["entry_mode"] != "DIRECT":
        return False
    if ctx["portfolio_exposure"] > DEFAULT_RISK_LIMITS["max_portfolio_exposure_pct"] * 0.5:
        return False
    return True


def _cooldown_active(cooldown_state: Mapping[str, Any]) -> bool:
    return bool(
        cooldown_state.get("active")
        or cooldown_state.get("cooldown_active")
        or str(cooldown_state.get("state", "")).upper() == "ACTIVE"
    )


def _volatility_state(ctx: Mapping[str, Any]) -> str:
    return str(ctx.get("volatility_state") or "NORMAL").upper()


def _replace_score(score: RiskScoreBreakdown, **changes: int) -> RiskScoreBreakdown:
    values = asdict(score)
    values.update(changes)
    return RiskScoreBreakdown(**values)
