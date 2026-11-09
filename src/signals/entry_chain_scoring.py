from __future__ import annotations

from typing import Mapping

from src.signals.entry_chain_config import EntryChainConfig


SCORE_COMPONENTS = (
    "background_4h",
    "direction_1h",
    "quality_30m",
    "trigger_15m",
    "cvd_flow",
    "volatility_stop",
    "liquidity_execution",
    "market_regime",
)

BASE_WEIGHTS = {
    "background_4h": 8.0,
    "direction_1h": 25.0,
    "quality_30m": 22.0,
    "trigger_15m": 12.0,
    "cvd_flow": 18.0,
    "volatility_stop": 10.0,
    "liquidity_execution": 3.0,
    "market_regime": 2.0,
}

EMA_WEIGHTS = {
    "background_4h": 5.0,
    "direction_1h": 18.0,
    "quality_30m": 12.0,
    "trigger_15m": 7.0,
    "ema_50_quality": 15.0,
    "ema_momentum": 10.0,
    "cvd_flow": 18.0,
    "volatility_stop": 10.0,
    "liquidity_execution": 3.0,
    "market_regime": 2.0,
}

FIB_PA_WEIGHTS = {
    "trend_ema_context": 20.0,
    "flow_cvd_confirmation": 18.0,
    "cci_momentum_quality": 14.0,
    "price_action_structure": 22.0,
    "fibonacci_location": 18.0,
    "risk_reward_geometry": 8.0,
}


# `resolve_architecture` 会为了可诊断性产出这两类标记，但它们**不是**权重来源的说明：
# - ARCHITECTURE_FLAGS_BOTH_TRUE 是告警
# - BASE_WEIGHTS 是"没走任何特化表"的标记，而动态权重函数历来对 base 返回空 reasons
# 二者都不得进入 `dynamic_weights` 的返回值，否则会改写 decision.reasons →
# payload.reasons → Task 6 的 leverage_reason，属于行为变更。
_NON_WEIGHT_REASONS = frozenset({"ARCHITECTURE_FLAGS_BOTH_TRUE", "BASE_WEIGHTS"})


def resolve_architecture(
    config: EntryChainConfig | None = None,
    atr_pct: float = 0.0,
) -> tuple[str, list[str]]:
    """把"当前在跑哪套评分架构"解析成**单值**。

    历史上 `use_fib_pa_architecture` 与 `use_ema_architecture` 同时为 true，
    靠 `dynamic_weights` 里的短路顺序"碰巧"选中 fib_pa，没有任何地方能直接回答
    "这套配置到底用哪组权重"。本函数把这个隐含事实显式化。

    返回 ``(name, reasons)``：
    - ``fib_pa`` / ``ema`` —— 由配置开关唯一决定
    - ``high_vol_dynamic`` / ``low_vol_dynamic`` / ``base`` —— 两个开关都关时按 atr_pct 决定
    - 两开关同 true 时 reasons 里带 ``ARCHITECTURE_FLAGS_BOTH_TRUE``（行为不变：
      仍然 fib_pa 优先，只是不再静默）
    """
    cfg = config or EntryChainConfig()
    reasons: list[str] = []
    if cfg.use_fib_pa_architecture and cfg.use_ema_architecture:
        reasons.append("ARCHITECTURE_FLAGS_BOTH_TRUE")
    if cfg.use_fib_pa_architecture:
        reasons.append("FIB_PA_ARCHITECTURE_WEIGHTS")
        return "fib_pa", reasons
    if cfg.use_ema_architecture:
        reasons.append("EMA_ARCHITECTURE_WEIGHTS")
        return "ema", reasons
    if atr_pct > cfg.high_vol_atr_pct:
        reasons.append("HIGH_VOL_DYNAMIC_WEIGHTS")
        return "high_vol_dynamic", reasons
    if atr_pct < cfg.low_vol_atr_pct:
        reasons.append("LOW_VOL_DYNAMIC_WEIGHTS")
        return "low_vol_dynamic", reasons
    reasons.append("BASE_WEIGHTS")
    return "base", reasons


def dynamic_weights(atr_pct: float, config: EntryChainConfig | None = None) -> tuple[dict[str, float], list[str]]:
    cfg = config or EntryChainConfig()
    name, architecture_reasons = resolve_architecture(cfg, atr_pct)
    # 只保留"权重从哪来"的说明，丢掉告警/base 标记——见 _NON_WEIGHT_REASONS。
    reasons = [reason for reason in architecture_reasons if reason not in _NON_WEIGHT_REASONS]
    if name == "fib_pa":
        return dict(FIB_PA_WEIGHTS), reasons
    if name == "ema":
        return dict(EMA_WEIGHTS), reasons
    if name == "high_vol_dynamic":
        fixed = {"volatility_stop": 20.0, "cvd_flow": 10.0}
        return rescale_weights(fixed), reasons
    if name == "low_vol_dynamic":
        fixed = {"trigger_15m": 18.0, "cvd_flow": 18.0}
        return rescale_weights(fixed), reasons
    return dict(BASE_WEIGHTS), reasons


def rescale_weights(fixed: Mapping[str, float]) -> dict[str, float]:
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


def component_points(component_scores: Mapping[str, float], weights: Mapping[str, float]) -> dict[str, float]:
    return {
        key: round(max(0.0, min(1.0, float(component_scores.get(key, 0.0)))) * weight, 4)
        for key, weight in weights.items()
    }
