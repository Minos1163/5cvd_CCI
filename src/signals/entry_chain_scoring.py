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

# 评分修复 v2 的权重表（2026-11-21 评审 P1-1）。与 V1 的差异只有三项：
#   risk_reward_geometry   8 → 12（+4，RR 改成两段式、不再是止损宽度的纯代理）
#   flow_cvd_confirmation 18 → 14（−4，成交量分量在成交样本上方差为 0）
#   price_action_structure 22 → 20（−2）
#
# **已知未决（必须由评审裁定，不由回测侧擅自补平）**：三项增量净 −2，
# 本表合计 **98** 而不是 100（V1 是 100）。后果：同一组分量下 V2 的总分比 V1 低约 2 分，
# 因此 82/77/72 这套入场阈值**不能直接套用到 V2**。
# 在裁定前 `scoring_repair_v2="on"` 只可用于离线对照，**不要上线**；
# tests/test_scoring_repair_v2.py 里有一条断言把 98 钉住，改表时会被强制看见。
# 补平的三种候选（都属评分决策，留给评审）：把 RR 提到 14（+6 净 0）、
# 把 PA 回收成 22（不降）、或按比例把 6 项缩放到 100。
#
# **只有 `scoring_repair_v2 == "on"` 才会被用到**；"shadow"/"off" 一律返回 V1 表，
# 保证 action 不变（见 `dynamic_weights`）。
FIB_PA_WEIGHTS_V2 = {
    "trend_ema_context": 20.0,
    "flow_cvd_confirmation": 14.0,
    "cci_momentum_quality": 14.0,
    "price_action_structure": 20.0,
    "fibonacci_location": 18.0,
    "risk_reward_geometry": 12.0,
}


# `resolve_architecture` 会为了可诊断性产出这几类标记，但它们**不是**权重来源的说明：
# - ARCHITECTURE_FLAGS_BOTH_TRUE 是告警
# - BASE_WEIGHTS 是"没走任何特化表"的标记，而动态权重函数历来对 base 返回空 reasons
# - SCORING_ARCHITECTURE_EXPLICIT_* 是"架构由枚举字段显式指定"的出处说明；
#   与之对应的**权重来源**说明仍由 FIB_PA_ARCHITECTURE_WEIGHTS / EMA_ARCHITECTURE_WEIGHTS
#   给出，保持 `dynamic_weights` 的 reasons 与引入枚举前逐字相同。
# 这些标记都不得进入 `dynamic_weights` 的返回值，否则会改写 decision.reasons →
# payload.reasons → Task 6 的 leverage_reason，属于行为变更。
_NON_WEIGHT_REASONS = frozenset({
    "ARCHITECTURE_FLAGS_BOTH_TRUE",
    "BASE_WEIGHTS",
    "SCORING_ARCHITECTURE_EXPLICIT_FIB_PA",
    "SCORING_ARCHITECTURE_EXPLICIT_EMA",
    "SCORING_ARCHITECTURE_EXPLICIT_BASE",
})

_AUTO_SCORING_ARCHITECTURES = frozenset({"", "auto"})
_AUTO_ARCHITECTURE = "auto"


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

    ``cfg.scoring_architecture`` 非 ``"auto"``（且非空）时**以它为准**，忽略两个布尔开关；
    此时 reasons 里除 ``SCORING_ARCHITECTURE_EXPLICIT_<NAME>`` 外还带一条与 auto 路径
    **完全相同**的权重来源标记，从而保证 `dynamic_weights` 的 reasons 不因改配置而变。
    注意 ``"base"`` 显式值直接返回 ``base``，**不经过 atr_pct 的高/低波动分支**。
    """
    cfg = config or EntryChainConfig()
    reasons: list[str] = []
    if cfg.use_fib_pa_architecture and cfg.use_ema_architecture:
        reasons.append("ARCHITECTURE_FLAGS_BOTH_TRUE")
    explicit = (cfg.scoring_architecture or _AUTO_ARCHITECTURE).strip().lower()
    if explicit not in _AUTO_SCORING_ARCHITECTURES:
        if explicit == "fib_pa":
            reasons.append("SCORING_ARCHITECTURE_EXPLICIT_FIB_PA")
            reasons.append("FIB_PA_ARCHITECTURE_WEIGHTS")
            return "fib_pa", reasons
        if explicit == "ema":
            reasons.append("SCORING_ARCHITECTURE_EXPLICIT_EMA")
            reasons.append("EMA_ARCHITECTURE_WEIGHTS")
            return "ema", reasons
        if explicit == "base":
            reasons.append("SCORING_ARCHITECTURE_EXPLICIT_BASE")
            reasons.append("BASE_WEIGHTS")
            return "base", reasons
        raise ValueError(f"unknown scoring_architecture: {explicit!r}")
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
    """权重表 + "从哪来"的 reasons。

    `scoring_repair_v2` 只在 `"on"` 时切到 `FIB_PA_WEIGHTS_V2`；`"shadow"`/`"off"` 一律用 V1 表，
    这是"影子模式不得改 action"的机械保证（`shadow` 的新分数由
    `repair_v2_score()` 单独算，不进这里）。
    """
    cfg = config or EntryChainConfig()
    name, architecture_reasons = resolve_architecture(cfg, atr_pct)
    # 只保留"权重从哪来"的说明，丢掉告警/base 标记——见 _NON_WEIGHT_REASONS。
    reasons = [reason for reason in architecture_reasons if reason not in _NON_WEIGHT_REASONS]
    if name == "fib_pa":
        if _repair_v2_mode(cfg) == "on":
            reasons.append("FIB_PA_WEIGHTS_V2")
            return dict(FIB_PA_WEIGHTS_V2), reasons
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


def _repair_v2_mode(cfg: EntryChainConfig) -> str:
    """把 `scoring_repair_v2` 归一成 `off|shadow|on`（空串/未知值一律按 off）。"""
    mode = str(getattr(cfg, "scoring_repair_v2", "off") or "off").strip().lower()
    return mode if mode in {"off", "shadow", "on"} else "off"


def repair_v2_enabled(cfg: EntryChainConfig) -> bool:
    """是否需要计算 v2 分量（`shadow` 与 `on` 都要算；`off` 完全不碰，省掉重复计算）。"""
    return _repair_v2_mode(cfg) in {"shadow", "on"}


def repair_v2_score(
    component_scores: Mapping[str, float],
    config: EntryChainConfig | None = None,
) -> tuple[float, dict[str, float]]:
    """用 V2 权重把（v2 口径的）分量算成总分，返回 `(score, points)`。

    纯函数、不改任何状态：`shadow` 模式下调用它只为了写 payload 诊断字段，
    调用方**不得**把结果写回 `score`。`on` 模式下 `dynamic_weights` 已返回 V2 表，
    主链路自然会算出同一个值，这里主要用于对照与测试。
    """
    cfg = config or EntryChainConfig()
    points = component_points(component_scores, FIB_PA_WEIGHTS_V2)
    return round(sum(points.values()), 4), points


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
