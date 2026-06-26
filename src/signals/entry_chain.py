from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from math import floor
from typing import Any, Mapping

from src.signals.entry_chain_config import EntryChainConfig
from src.signals.entry_chain_gates import (
    HIGH_BETA_SYMBOLS,
    daily_max_trades,
    hard_block_reason,
    liquidity_ratio as calculate_liquidity_ratio,
    symbol_exposure_cap,
)
from src.signals.entry_chain_scoring import (
    BASE_WEIGHTS,
    SCORE_COMPONENTS,
    component_points as calculate_component_points,
    dynamic_weights as calculate_dynamic_weights,
)

@dataclass(frozen=True)
class EntryChainContext:
    symbol: str
    timestamp: int
    side: str
    component_scores: Mapping[str, float]
    quote_volume_24h: float
    atr_pct: float
    expected_order_size: float
    account_equity: float
    available_margin: float
    macro_daily_drop_pct: float = 0.0
    macro_weekly_drop_pct: float = 0.0
    usdt_premium_abnormal: bool = False
    wick_anomaly_active: bool = False
    polluted_until_ts: int | None = None
    websocket_reconnect_recent: bool = False
    active_symbols: int = 0
    portfolio_trades_today: int = 0
    symbol_trades_today: int = 0
    current_volatility_scale: float = 1.0
    normal_volatility_scale: float = 1.0
    daily_profit_pct: float = 0.0
    cooldown_until_ts: int | None = None
    symbol_exposure_pct: float = 0.0
    total_exposure_pct: float = 0.0
    same_direction_exposure_pct: float = 0.0
    rolling_sharpe_20: float | None = None
    stop_pct: float | None = None
    long_overextension_active: bool = False
    long_upper_wick_risk_active: bool = False
    long_chase_risk_active: bool = False
    long_low_liquidity_session_active: bool = False
    long_cvd_weak_active: bool = False

    def with_updates(self, **updates: Any) -> "EntryChainContext":
        return replace(self, **updates)


@dataclass(frozen=True)
class EntryChainDecision:
    action: str
    side: str
    score: float
    weights: dict[str, float]
    component_points: dict[str, float]
    reasons: tuple[str, ...]
    risk_allowed: bool
    leverage: int
    max_symbol_exposure_pct: float
    notional_hint: float
    liquidity_ratio: float
    metadata: dict[str, Any]

    def __getitem__(self, key: str) -> Any:
        return self.to_dict()[key]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["reasons"] = list(self.reasons)
        return payload


def evaluate_entry_chain(context: EntryChainContext, config: EntryChainConfig | None = None) -> EntryChainDecision:
    cfg = config or EntryChainConfig()
    reasons: list[str] = []
    symbol = context.symbol.strip().upper()
    side = context.side.strip().upper()
    max_symbol_exposure_pct = symbol_exposure_cap(symbol, cfg)
    weights, weight_reasons = dynamic_weights(context.atr_pct, cfg)
    reasons.extend(weight_reasons)
    scores = _apply_long_context_discounts(context.component_scores, context, cfg, side, reasons)
    points = calculate_component_points(scores, weights)
    score = round(sum(points.values()), 4)
    ratio = calculate_liquidity_ratio(context)

    if cfg.use_fib_pa_architecture and float(scores.get("fib_action_cap", 1.0)) <= 0.0:
        return _decision(
            context,
            cfg,
            "NO_TRADE",
            score,
            weights,
            points,
            reasons + ["FIB_EXTENSION_EXHAUSTION_BLOCK"],
            max_symbol_exposure_pct,
            ratio,
        )

    hard_block = hard_block_reason(context, cfg)
    if hard_block is not None:
        return _decision(context, cfg, "NO_TRADE", score, weights, points, reasons + [hard_block], max_symbol_exposure_pct, ratio)

    action = _score_to_action(score, cfg, side, reasons)
    action = _apply_probe_disable(_apply_component_minimums(action, context.with_updates(component_scores=scores), cfg, reasons), cfg, reasons)

    if cfg.enable_long_context_discounts and side == "LONG" and context.long_low_liquidity_session_active:
        action = _min_action(action, "WATCH")
        reasons.append("LONG_LOW_LIQUIDITY_SESSION_WATCH")

    if context.macro_daily_drop_pct <= cfg.macro_daily_drop_block_pct or context.usdt_premium_abnormal:
        if action == "DIRECT":
            action = "PROBE"
            reasons.append("MACRO_DAILY_RISK_DIRECT_BLOCK")

    if context.websocket_reconnect_recent:
        action = _min_action(action, "WATCH")
        reasons.append("WEBSOCKET_RECONNECT_WATCH")

    if ratio < cfg.probe_liquidity_ratio:
        return _decision(context, cfg, "NO_TRADE", score, weights, points, reasons + ["LIQUIDITY_PROBE_BLOCK"], max_symbol_exposure_pct, ratio)
    if ratio < cfg.direct_liquidity_ratio and action == "DIRECT":
        action = "PROBE"
        reasons.append("LIQUIDITY_DIRECT_BLOCK")
        action = _apply_probe_disable(action, cfg, reasons)

    if symbol in HIGH_BETA_SYMBOLS and action == "DIRECT":
        action = "PROBE"
        reasons.append("HIGH_BETA_PROBE_ONLY")
        action = _apply_probe_disable(action, cfg, reasons)

    if context.daily_profit_pct > 0.03:
        if action == "PROBE":
            action = "WATCH"
            reasons.append("PROFIT_DAY_PROBE_DISABLED")
        if action == "DIRECT" and score < cfg.direct_threshold + 3:
            action = "PROBE"
            reasons.append("PROFIT_DAY_DIRECT_PLUS_THREE")
            action = _apply_probe_disable(action, cfg, reasons)

    if context.symbol_exposure_pct >= max_symbol_exposure_pct:
        return _decision(context, cfg, "NO_TRADE", score, weights, points, reasons + ["SYMBOL_EXPOSURE_CAP"], max_symbol_exposure_pct, ratio)

    leverage = _select_leverage(action, score, context, cfg, reasons)
    notional_hint = _notional_hint(action, score, context, cfg, max_symbol_exposure_pct)

    return _decision(
        context,
        cfg,
        action,
        score,
        weights,
        points,
        reasons,
        max_symbol_exposure_pct,
        ratio,
        leverage=leverage,
        notional_hint=notional_hint,
    )


def dynamic_weights(atr_pct: float, config: EntryChainConfig | None = None) -> tuple[dict[str, float], list[str]]:
    return calculate_dynamic_weights(atr_pct, config)


def _rescale_weights(fixed: Mapping[str, float]) -> dict[str, float]:
    remaining_keys = [key for key in SCORE_COMPONENTS if key not in fixed]
    fixed_total = sum(fixed.values())
    base_remaining_total = sum(BASE_WEIGHTS[key] for key in remaining_keys)
    scale = (100.0 - fixed_total) / base_remaining_total
    weights = {key: round(BASE_WEIGHTS[key] * scale, 6) for key in remaining_keys}
    weights.update({key: float(value) for key, value in fixed.items()})
    drift = 100.0 - sum(weights.values())
    first_key = remaining_keys[0] if remaining_keys else next(iter(weights))
    weights[first_key] = round(weights[first_key] + drift, 6)
    return {key: weights[key] for key in SCORE_COMPONENTS}


def _component_points(component_scores: Mapping[str, float], weights: Mapping[str, float]) -> dict[str, float]:
    return {
        key: round(max(0.0, min(1.0, float(component_scores.get(key, 0.0)))) * weight, 4)
        for key, weight in weights.items()
    }


def _hard_block_reason(context: EntryChainContext, cfg: EntryChainConfig) -> str | None:
    if context.macro_weekly_drop_pct <= cfg.macro_weekly_drop_block_pct:
        return "MACRO_WEEKLY_RISK"
    if context.wick_anomaly_active:
        return "DATA_WICK_ANOMALY"
    if context.polluted_until_ts is not None and context.timestamp <= context.polluted_until_ts:
        return "DATA_POLLUTION_COOLDOWN"
    if context.active_symbols >= cfg.max_active_symbols:
        return "MAX_ACTIVE_SYMBOLS"
    if context.portfolio_trades_today >= _daily_max_trades(context, cfg):
        return "DAILY_TRADE_BUDGET_USED"
    if context.symbol_trades_today >= cfg.max_symbol_trades_per_day:
        return "SYMBOL_DAILY_TRADE_BUDGET_USED"
    if context.cooldown_until_ts is not None and context.timestamp < context.cooldown_until_ts:
        return "SYMBOL_COOLDOWN_ACTIVE"
    if context.total_exposure_pct >= cfg.max_total_exposure_pct:
        return "TOTAL_EXPOSURE_CAP"
    if context.same_direction_exposure_pct >= cfg.max_same_direction_exposure_pct:
        return "SAME_DIRECTION_EXPOSURE_CAP"
    if context.available_margin < context.account_equity * cfg.margin_buffer_pct:
        return "MARGIN_BUFFER_TOO_LOW"
    if context.account_equity <= 0:
        return "ACCOUNT_EQUITY_INVALID"
    if context.side.strip().upper() not in {"LONG", "SHORT"}:
        return "SIDE_NOT_ALLOWED"
    return None


def _daily_max_trades(context: EntryChainContext, cfg: EntryChainConfig) -> int:
    normal = max(context.normal_volatility_scale, 1e-9)
    dynamic_limit = max(1, floor(cfg.daily_max_trades_base * (context.current_volatility_scale / normal)))
    if context.daily_profit_pct > 0.03:
        return max(1, dynamic_limit // 2)
    return dynamic_limit


def _score_to_action(score: float, cfg: EntryChainConfig, side: str = "", reasons: list[str] | None = None) -> str:
    offset = _side_threshold_offset(side, cfg)
    if offset and reasons is not None:
        reasons.append(f"SIDE_THRESHOLD_OFFSET_{side}_{offset:.2f}")
    direct_threshold = cfg.direct_threshold + offset
    probe_threshold = cfg.probe_threshold + offset
    watch_threshold = cfg.watch_threshold + offset
    if score >= direct_threshold:
        return "DIRECT"
    if score >= probe_threshold:
        return "PROBE"
    if score >= watch_threshold:
        return "WATCH"
    return "NO_TRADE"


def _side_threshold_offset(side: str, cfg: EntryChainConfig) -> float:
    normalized = side.strip().upper()
    if normalized == "LONG":
        return float(cfg.long_threshold_offset)
    if normalized == "SHORT":
        return float(cfg.short_threshold_offset)
    return 0.0


def _apply_long_context_discounts(
    component_scores: Mapping[str, float],
    context: EntryChainContext,
    cfg: EntryChainConfig,
    side: str,
    reasons: list[str],
) -> dict[str, float]:
    scores = {key: float(value) for key, value in component_scores.items()}
    if not cfg.enable_long_context_discounts or side != "LONG":
        return scores
    if context.long_overextension_active:
        _multiply_score(scores, "quality_30m", cfg.long_overextension_quality_mult)
        _multiply_score(scores, "ema_50_quality", cfg.long_overextension_quality_mult)
        reasons.append("LONG_OVEREXTENSION_QUALITY_DISCOUNT")
    if context.long_upper_wick_risk_active:
        _multiply_score(scores, "trigger_15m", cfg.long_upper_wick_trigger_mult)
        reasons.append("LONG_UPPER_WICK_TRIGGER_DISCOUNT")
    if context.long_chase_risk_active:
        _multiply_score(scores, "trigger_15m", cfg.long_chase_trigger_mult)
        reasons.append("LONG_CHASE_TRIGGER_DISCOUNT")
    if context.long_cvd_weak_active or scores.get("cvd_flow", 0.0) < cfg.long_cvd_weak_threshold:
        _multiply_score(scores, "cvd_flow", cfg.long_cvd_weak_mult)
        reasons.append("LONG_CVD_WEAK_DISCOUNT")
    return {key: max(0.0, min(1.0, value)) for key, value in scores.items()}


def _multiply_score(scores: dict[str, float], key: str, multiplier: float) -> None:
    if key in scores:
        scores[key] = scores[key] * multiplier


def _apply_probe_disable(action: str, cfg: EntryChainConfig, reasons: list[str]) -> str:
    if cfg.disable_probe and action == "PROBE":
        reasons.append("PROBE_DISABLED")
        return "NO_TRADE"
    return action


def _apply_component_minimums(action: str, context: EntryChainContext, cfg: EntryChainConfig, reasons: list[str]) -> str:
    scores = context.component_scores
    if cfg.use_fib_pa_architecture:
        if action == "DIRECT":
            return _apply_fib_pa_direct_minimums(action, scores, cfg, reasons)
        return action
    if cfg.use_ema_architecture and cfg.ema200_gate_mode == "hard" and float(scores.get("ema_200_gate", 1.0)) <= 0.0:
        reasons.append("EMA200_HARD_GATE_FAILED")
        return "NO_TRADE"
    if action == "DIRECT":
        direct_checks = _direct_component_minimums(context.side, cfg, reasons)
        if any(float(scores.get(key, 0.0)) < value for key, value in direct_checks.items()):
            reasons.append("DIRECT_COMPONENT_MINIMUM_FAILED")
            action = "PROBE"
    if action == "PROBE":
        probe_checks = {
            "direction_1h": cfg.min_direction_probe_score,
            "quality_30m": cfg.min_quality_probe_score,
            "trigger_15m": cfg.min_trigger_probe_score,
            "cvd_flow": cfg.min_cvd_probe_score,
        }
        if any(float(scores.get(key, 0.0)) < value for key, value in probe_checks.items()):
            reasons.append("PROBE_COMPONENT_MINIMUM_FAILED")
            action = "WATCH"
    if cfg.use_ema_architecture and action == "DIRECT":
        if float(scores.get("ema_50_quality", 0.0)) < cfg.ema50_min_for_direct:
            reasons.append("EMA50_DIRECT_MINIMUM_FAILED")
            action = "PROBE"
    if cfg.use_ema_architecture and action == "PROBE":
        if float(scores.get("ema_50_quality", 0.0)) < cfg.ema50_min_for_probe:
            reasons.append("EMA50_PROBE_MINIMUM_FAILED")
            action = "WATCH"
    return action


def _direct_component_minimums(side: str, cfg: EntryChainConfig, reasons: list[str]) -> dict[str, float]:
    checks = {
        "direction_1h": cfg.min_direction_direct_score,
        "quality_30m": cfg.min_quality_direct_score,
        "trigger_15m": cfg.min_trigger_direct_score,
        "cvd_flow": cfg.min_cvd_direct_score,
    }
    normalized = side.strip().upper()
    if normalized == "LONG":
        overrides = {
            "direction_1h": cfg.long_min_direction_direct_score,
            "quality_30m": cfg.long_min_quality_direct_score,
            "trigger_15m": cfg.long_min_trigger_direct_score,
            "cvd_flow": cfg.long_min_cvd_direct_score,
        }
        if any(value is not None for value in overrides.values()):
            reasons.append("SIDE_COMPONENT_MINIMUMS_LONG")
            checks.update({key: float(value) for key, value in overrides.items() if value is not None})
    if normalized == "SHORT":
        overrides = {
            "direction_1h": cfg.short_min_direction_direct_score,
            "quality_30m": cfg.short_min_quality_direct_score,
            "trigger_15m": cfg.short_min_trigger_direct_score,
            "cvd_flow": cfg.short_min_cvd_direct_score,
        }
        if any(value is not None for value in overrides.values()):
            reasons.append("SIDE_COMPONENT_MINIMUMS_SHORT")
            checks.update({key: float(value) for key, value in overrides.items() if value is not None})
    return checks


def _apply_fib_pa_direct_minimums(
    action: str,
    scores: Mapping[str, float],
    cfg: EntryChainConfig,
    reasons: list[str],
) -> str:
    minimums = {
        "price_action_structure": (cfg.pa_min_direct_score / 22.0, "PRICE_ACTION_STRUCTURE_BELOW_DIRECT_MINIMUM"),
        "fibonacci_location": (cfg.fib_min_direct_score / 18.0, "FIBONACCI_LOCATION_BELOW_DIRECT_MINIMUM"),
        "risk_reward_geometry": (cfg.rr_min_direct_score / 8.0, "RISK_REWARD_GEOMETRY_BELOW_DIRECT_MINIMUM"),
    }
    for component, (minimum, reason) in minimums.items():
        if float(scores.get(component, 0.0)) < minimum:
            reasons.append(reason)
            return "PROBE"
    return action


def _liquidity_ratio(context: EntryChainContext) -> float:
    volatility_multiplier = max(1.0, context.atr_pct * 100.0)
    base = volatility_multiplier * context.expected_order_size
    if base <= 0:
        return 0.0
    return context.quote_volume_24h / base


def _symbol_exposure_cap(symbol: str, cfg: EntryChainConfig) -> float:
    if symbol in LARGE_CAP_SYMBOLS:
        return cfg.max_large_cap_exposure_pct
    if symbol in MAINSTREAM_SYMBOLS:
        return cfg.max_mainstream_exposure_pct
    if symbol in HIGH_BETA_SYMBOLS:
        return cfg.max_high_beta_exposure_pct
    return cfg.max_mainstream_exposure_pct


def _select_leverage(
    action: str,
    score: float,
    context: EntryChainContext,
    cfg: EntryChainConfig,
    reasons: list[str],
) -> int:
    if action not in {"PROBE", "DIRECT"}:
        return 0
    if context.rolling_sharpe_20 is not None and context.rolling_sharpe_20 < 0:
        reasons.append("ROLLING_SHARPE_LEVERAGE_CAP")
        return 2
    if context.atr_pct > 0.03:
        return 3
    if context.atr_pct > 0.015:
        return 4 if action == "DIRECT" else 3
    if score >= 90 and action == "DIRECT":
        if cfg.use_fib_pa_architecture and not _fib_pa_5x_requirements_met(context.component_scores, cfg):
            reasons.append("FIB_PA_5X_REQUIREMENTS_FAILED")
            return 4
        return 5
    return 4 if action == "DIRECT" else 3


def _fib_pa_5x_requirements_met(scores: Mapping[str, float], cfg: EntryChainConfig) -> bool:
    requirements = {
        "fibonacci_location": cfg.leverage_5x_fib_min / 18.0,
        "price_action_structure": cfg.leverage_5x_pa_min / 22.0,
        "cci_momentum_quality": cfg.leverage_5x_cci_min / 14.0,
        "risk_reward_geometry": cfg.leverage_5x_rr_min / 8.0,
    }
    return all(float(scores.get(component, 0.0)) >= minimum for component, minimum in requirements.items())


def _notional_hint(
    action: str,
    score: float,
    context: EntryChainContext,
    cfg: EntryChainConfig,
    max_symbol_exposure_pct: float,
) -> float:
    if action not in {"PROBE", "DIRECT"}:
        return 0.0
    exposure_pct = cfg.base_direct_exposure_pct
    if action == "DIRECT":
        exposure_pct += max(0.0, min(0.10, (score - cfg.direct_threshold) / 100.0))
    else:
        exposure_pct *= cfg.probe_fraction
    exposure_pct = min(exposure_pct, max_symbol_exposure_pct)
    score_based = context.account_equity * exposure_pct
    stop_pct = context.stop_pct or max(cfg.min_stop_pct, min(cfg.max_stop_pct, context.atr_pct * 1.5))
    risk_pct = cfg.direct_risk_pct if action == "DIRECT" else cfg.probe_risk_pct
    risk_based = context.account_equity * risk_pct / stop_pct
    cap_remaining = max(0.0, (max_symbol_exposure_pct - context.symbol_exposure_pct) * context.account_equity)
    return round(max(0.0, min(score_based, risk_based, cap_remaining)), 4)


def _min_action(action: str, cap: str) -> str:
    order = {"NO_TRADE": 0, "WATCH": 1, "PROBE": 2, "DIRECT": 3}
    inverse = {value: key for key, value in order.items()}
    return inverse[min(order[action], order[cap])]


def _decision(
    context: EntryChainContext,
    cfg: EntryChainConfig,
    action: str,
    score: float,
    weights: Mapping[str, float],
    component_points: Mapping[str, float],
    reasons: list[str],
    max_symbol_exposure_pct: float,
    liquidity_ratio: float,
    *,
    leverage: int | None = None,
    notional_hint: float | None = None,
) -> EntryChainDecision:
    unique_reasons = tuple(dict.fromkeys(reasons))
    resolved_leverage = leverage if leverage is not None else _select_leverage(action, score, context, cfg, reasons)
    resolved_notional = (
        notional_hint
        if notional_hint is not None
        else _notional_hint(action, score, context, cfg, max_symbol_exposure_pct)
    )
    return EntryChainDecision(
        action=action,
        side=context.side.strip().upper() if action in {"PROBE", "DIRECT"} else "NONE",
        score=score,
        weights=dict(weights),
        component_points=dict(component_points),
        reasons=unique_reasons,
        risk_allowed=action in {"PROBE", "DIRECT"},
        leverage=resolved_leverage,
        max_symbol_exposure_pct=max_symbol_exposure_pct,
        notional_hint=resolved_notional,
        liquidity_ratio=round(liquidity_ratio, 4),
        metadata={
            "strategy_contract": "entry-chain-v1-lite",
            "daily_max_trades": daily_max_trades(context, cfg),
            "symbol": context.symbol.strip().upper(),
        },
    )
