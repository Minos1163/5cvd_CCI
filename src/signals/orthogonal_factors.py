# -*- coding: utf-8 -*-
"""五正交因子(F1-F5)—— P0 影子体系(2026-09-27 裁定报告实施)。

**P0 硬约束**:本模块产出的数值只写 `component_points_v2` 记录字段,
不参与 `total_score`、`component_points`、象限标注、通道门槛、杠杆选择
或任何 `action` 判定。由 `tests/test_five_factor_shadow_readonly.py` 强制校验。

设计依据:`docs/2026-09-27-five-orthogonal-factor-strategy-decision.md`

| 因子 | 测量维度 | 替代的旧因子 |
|---|---|---|
| F1 trend_persistence | 方向 + 强度(连续) | trend_ema_context(+ 并入 cci 的动能信息) |
| F2 structure_location | 去方向化的结构位置 | fibonacci_location |
| F3 payoff_geometry | 连续风险回报(无天花板) | risk_reward_geometry |
| F4 volatility_regime | 波动率状态(全新维度) | 无(旧体系 ATR% 只用于杠杆/止损 clamp) |
| F5 order_flow | 真实主动买卖失衡 | flow_cvd_confirmation(伪 CVD) |

**边界原则**(呼应 2026-08-13 教训):一切退化输入回退**中性值 0.5**,
不回退成"最低分",更不阻断决策——异常输入是"信息缺失"而非"负面信号"。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from statistics import pstdev
from typing import Mapping, Sequence

from src.backtest.engine import BacktestBar
from src.indicators.cvd import cvd_delta
from src.indicators.ema import ema
from src.signals.entry_chain_features import nearest_opposition_price
from src.signals.fib_location import detect_fractal_swings

SCHEMA_VERSION = "v2-p0-shadow"
NEUTRAL_VALUE = 0.5

FIVE_FACTOR_KEYS = (
    "trend_persistence",
    "structure_location",
    "payoff_geometry",
    "volatility_regime",
    "order_flow",
)

# component_points_v2 的键:F4 因双重定位拆为 score 与 leverage_mult 两项。
FIVE_FACTOR_POINT_KEYS = (
    "trend_persistence",
    "structure_location",
    "payoff_geometry",
    "volatility_regime_score",
    "order_flow",
)

# P0 占位权重:仅用于影子展示,P2 阶段改由单因子 IC 裁决(裁定报告第六节)。
FIVE_FACTOR_WEIGHTS = {
    "trend_persistence": 22.0,
    "structure_location": 18.0,
    "payoff_geometry": 18.0,
    "volatility_regime": 20.0,
    "order_flow": 22.0,
}

DONCHIAN_WINDOW = 20
EMA_TREND_PERIOD = 200
EMA_SLOPE_LOOKBACK = 10

STOP_ATR_MULT = 1.5
STOP_PCT_FLOOR = 0.005
STOP_PCT_CEIL = 0.030
COST_BUFFER_PCT = 0.001  # 2×taker fee(5bps)+ 滑点(5bps)
PAYOFF_R_FULL_SCORE = 3.0  # 3R 及以上满分(连续,无 1.3 式天花板)

VOLATILITY_PEAK_PERCENTILE = 0.60
# F4 双轨影子(2026-10-04 评审裁定第二节):clip v1 保持现役;高斯 v2 仅并行记录,
# 不替换现役公式。下一窗口对比零值占比 / IC / 与其余四因子的相关性后再裁决 σ。
GAUSS_SIGMA_GRID = (0.20, 0.25, 0.30)
GAUSS_SIGMA_DEFAULT = 0.25
LEVERAGE_DECAY_START = 0.70
LEVERAGE_DECAY_FLOOR = 0.40
ATR_PCT_WINDOW = 14
VOLATILITY_LOOKBACK_MAX_BARS = 1500  # 单次 klines 请求上限,约 15.6 天(15m)
# live 默认仅拉约 241 根 15m(≈2.5 天,见 --public-kline-limit 默认 240)。
# 提高取数会改变 EMA200 → 影响旧评分,违反 P0 红线,故按"可得历史内分位"设计;
# 实际窗口长度由 meta.volatility_lookback_bars / volatility_lookback_days 如实记录。
VOLATILITY_LOOKBACK_MIN_BARS = 200

ORDER_FLOW_WINDOW = 12


@dataclass(frozen=True)
class FactorValue:
    value: float
    fallback: bool = False
    detail: Mapping[str, float | bool | str] = field(default_factory=dict)


@dataclass(frozen=True)
class VolatilityRegimeResult:
    """F4 双重定位:评分分量(倒 U 型)与仓位调节分量(单调递减)互不干扰。"""

    score: float
    leverage_multiplier: float
    fallback: bool
    lookback_bars: int
    # F4 双轨:高斯型候选评分(σ 网格)仅记录,不参与现役评分
    gauss_scores: Mapping[str, float] = field(default_factory=dict)
    detail: Mapping[str, float | bool | str] = field(default_factory=dict)


def _clip(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _sigmoid(value: float) -> float:
    if value >= 0:
        return 1.0 / (1.0 + math.exp(-value))
    exp_value = math.exp(value)
    return exp_value / (1.0 + exp_value)


def _normalized_side(side: str) -> str:
    return str(side).strip().upper()


# ---------------------------------------------------------------------------
# F1 趋势持久性
# ---------------------------------------------------------------------------


def ema200_slope_z(bars: Sequence[BacktestBar], *, period: int = EMA_TREND_PERIOD) -> float:
    """EMA 斜率的显著性(t 型统计量),替代旧的 8/0 二值 gate 参与评分。"""
    closes = [float(bar.close) for bar in bars]
    series = ema(closes, period)
    if len(series) <= EMA_SLOPE_LOOKBACK + 1:
        return 0.0
    diffs = [series[index] - series[index - 1] for index in range(1, len(series))]
    recent = diffs[-EMA_SLOPE_LOOKBACK:]
    deviation = pstdev(recent) if len(recent) > 1 else 0.0
    if deviation <= 0:
        return 0.0
    return (sum(recent) / len(recent)) / deviation


def compute_trend_persistence(side: str, bars: Sequence[BacktestBar]) -> FactorValue:
    """F1:Donchian 通道位置(沿交易方向取号)+ EMA 斜率显著性。"""
    items = list(bars)
    if len(items) < DONCHIAN_WINDOW:
        return FactorValue(NEUTRAL_VALUE, True, {"reason": "insufficient_bars"})

    window = items[-DONCHIAN_WINDOW:]
    high_n = max(float(bar.high) for bar in window)
    low_n = min(float(bar.low) for bar in window)
    close = float(items[-1].close)
    fallback = False
    if high_n <= low_n:
        donchian_pos = NEUTRAL_VALUE
        fallback = True
    else:
        donchian_pos = _clip((close - low_n) / (high_n - low_n))

    directional = donchian_pos if _normalized_side(side) == "LONG" else 1.0 - donchian_pos
    slope_z = ema200_slope_z(items)
    value = round(0.5 * directional + 0.5 * _sigmoid(slope_z), 4)
    return FactorValue(
        value,
        fallback,
        {
            "donchian_pos": round(donchian_pos, 4),
            "directional_position": round(directional, 4),
            "ema200_slope_z": round(slope_z, 4),
        },
    )


# ---------------------------------------------------------------------------
# F2 结构位置(去方向化)
# ---------------------------------------------------------------------------


def compute_structure_location(bars: Sequence[BacktestBar], atr_value: float) -> FactorValue:
    """F2:价格在最近摆动结构中的百分位 —— **不依赖 side**(与方向解耦)。"""
    items = list(bars)
    if len(items) < 3 or atr_value <= 0:
        return FactorValue(NEUTRAL_VALUE, True, {"reason": "insufficient_input"})

    swings = detect_fractal_swings(items, atr=float(atr_value))
    highs = [float(item.price) for item in swings if item.kind == "HIGH"]
    lows = [float(item.price) for item in swings if item.kind == "LOW"]
    if not highs or not lows:
        return FactorValue(NEUTRAL_VALUE, True, {"reason": "no_swing_structure"})

    swing_high = max(highs[-3:])
    swing_low = min(lows[-3:])
    if swing_high <= swing_low:
        return FactorValue(NEUTRAL_VALUE, True, {"reason": "degenerate_range"})

    close = float(items[-1].close)
    position = _clip((close - swing_low) / (swing_high - swing_low))
    return FactorValue(
        round(position, 4),
        False,
        {"swing_high": round(swing_high, 8), "swing_low": round(swing_low, 8)},
    )


# ---------------------------------------------------------------------------
# F3 赔率几何(连续化,移除天花板)
# ---------------------------------------------------------------------------


def payoff_geometry_r(close: float, side: str, atr_value: float, swings: Sequence[object]) -> float | None:
    """到最近对手结构的净 R;无对手结构时返回 None(调用方回退中性)。"""
    if close <= 0 or atr_value <= 0:
        return None
    stop_dist = max(close * STOP_PCT_FLOOR, min(close * STOP_PCT_CEIL, float(atr_value) * STOP_ATR_MULT))
    opposition = nearest_opposition_price(close, side, swings)
    if opposition is None:
        return None
    if _normalized_side(side) == "SHORT":
        distance = close - float(opposition)
    else:
        distance = float(opposition) - close
    return (distance - close * COST_BUFFER_PCT) / stop_dist


def compute_payoff_geometry(
    close: float, side: str, atr_value: float, swings: Sequence[object]
) -> FactorValue:
    """F3:连续赔率映射 —— 旧版 `net_tp1_r >= 1.3 → 5.0` 的隐性天花板已移除。"""
    payoff_r = payoff_geometry_r(close, side, atr_value, swings)
    if payoff_r is None:
        return FactorValue(NEUTRAL_VALUE, True, {"reason": "no_counter_structure"})
    if payoff_r <= 0:
        return FactorValue(0.0, False, {"payoff_r": round(payoff_r, 4)})
    return FactorValue(
        round(_clip(payoff_r / PAYOFF_R_FULL_SCORE), 4),
        False,
        {"payoff_r": round(payoff_r, 4)},
    )


# ---------------------------------------------------------------------------
# F4 波动率状态(全新维度;双重定位)
# ---------------------------------------------------------------------------


def atr_pct_series(
    bars: Sequence[BacktestBar],
    *,
    window: int = ATR_PCT_WINDOW,
    max_lookback: int = VOLATILITY_LOOKBACK_MAX_BARS,
) -> list[float]:
    items = list(bars)
    if len(items) < window + 1:
        return []
    if len(items) > max_lookback:
        items = items[-max_lookback:]
    true_ranges: list[float] = []
    for index in range(1, len(items)):
        bar = items[index]
        previous_close = float(items[index - 1].close)
        true_ranges.append(
            max(
                float(bar.high) - float(bar.low),
                abs(float(bar.high) - previous_close),
                abs(float(bar.low) - previous_close),
            )
        )
    series: list[float] = []
    for index in range(window - 1, len(true_ranges)):
        window_ranges = true_ranges[index - window + 1 : index + 1]
        close = float(items[index + 1].close)
        if close > 0:
            series.append(sum(window_ranges) / window / close)
    return series


def percentile_rank(series: Sequence[float], value: float) -> float:
    if not series:
        return NEUTRAL_VALUE
    below = sum(1 for item in series if item <= value)
    return below / len(series)


def volatility_score_from_percentile(atr_percentile: float) -> float:
    """评分分量:倒 U 型 —— 峰值在 0.60 分位,两端衰减。"""
    return round(_clip(1.0 - abs(atr_percentile - VOLATILITY_PEAK_PERCENTILE) * 2.5), 4)


def volatility_score_gauss(
    atr_percentile: float, sigma: float = GAUSS_SIGMA_DEFAULT
) -> float:
    """F4 候选评分分量(高斯型,2026-10-04 评审裁定 2.2 节方案 B)。

    `exp(-((p-0.6)²)/(2σ²))` —— 渐近趋 0 而非硬夹断,消除现役 clip 版在
    `|p-0.6| ≥ 0.4` 时(约 31% 样本)恒为 0 的信息损失。**仅并行记录**。
    """
    if sigma <= 0:
        raise ValueError("sigma must be positive")
    deviation = float(atr_percentile) - VOLATILITY_PEAK_PERCENTILE
    return round(math.exp(-(deviation * deviation) / (2.0 * sigma * sigma)), 6)


def gauss_scores_for_percentile(atr_percentile: float) -> dict[str, float]:
    """σ 网格三档同时记录(最终取值由 P2 阶段 IC 数据裁决,不在此拍板)。"""
    return {
        f"sigma_{sigma:.2f}": volatility_score_gauss(atr_percentile, sigma)
        for sigma in GAUSS_SIGMA_GRID
    }


def leverage_multiplier_from_percentile(atr_percentile: float) -> float:
    """仓位调节分量:0.70 分位后单调递减,1.00 分位降至 0.40(与 4XGATE 方向一致)。"""
    if atr_percentile < LEVERAGE_DECAY_START:
        return 1.0
    span = max(1e-9, 1.0 - LEVERAGE_DECAY_START)
    ratio = _clip((atr_percentile - LEVERAGE_DECAY_START) / span)
    return round(1.0 - ratio * (1.0 - LEVERAGE_DECAY_FLOOR), 4)


def compute_volatility_regime(bars: Sequence[BacktestBar]) -> VolatilityRegimeResult:
    items = list(bars)
    series = atr_pct_series(items)
    if len(series) < VOLATILITY_LOOKBACK_MIN_BARS:
        return VolatilityRegimeResult(
            score=NEUTRAL_VALUE,
            leverage_multiplier=1.0,
            fallback=True,
            lookback_bars=len(series),
            gauss_scores={},
            detail={"reason": "insufficient_volatility_history"},
        )
    current = series[-1]
    atr_percentile = percentile_rank(series, current)
    return VolatilityRegimeResult(
        score=volatility_score_from_percentile(atr_percentile),
        leverage_multiplier=leverage_multiplier_from_percentile(atr_percentile),
        fallback=False,
        lookback_bars=len(series),
        gauss_scores=gauss_scores_for_percentile(atr_percentile),
        detail={
            "atr_pct": round(current, 6),
            "atr_percentile": round(atr_percentile, 4),
            "band_expansion": round(band_expansion(items), 4),
        },
    )


def band_expansion(bars: Sequence[BacktestBar], *, window: int = 20, lookback: int = 5) -> float:
    """布林带宽相对 lookback 根前的扩张率(诊断用)。"""
    items = list(bars)
    if len(items) < window + lookback:
        return 0.0
    widths: list[float] = []
    for offset in range(lookback + 1):
        end = len(items) - offset
        segment = [float(bar.close) for bar in items[end - window : end]]
        average = sum(segment) / len(segment)
        if average <= 0:
            widths.append(0.0)
            continue
        widths.append(2.0 * pstdev(segment) / average)
    prior = widths[-1]
    if prior <= 0:
        return 0.0
    return widths[0] / prior - 1.0


# ---------------------------------------------------------------------------
# F5 真实订单流(替换伪 CVD)
# ---------------------------------------------------------------------------


def slope_alignment(first: Sequence[float], second: Sequence[float]) -> float:
    """两个序列的斜率方向一致性 → [0,1](0.5 = 无法判定/中性)。"""
    slope_first = _series_slope(first)
    slope_second = _series_slope(second)
    if slope_first == 0.0 or slope_second == 0.0:
        return NEUTRAL_VALUE
    cosine = (slope_first * slope_second) / (abs(slope_first) * abs(slope_second))
    return round((cosine + 1.0) / 2.0, 4)


def _series_slope(values: Sequence[float]) -> float:
    items = [float(value) for value in values]
    if len(items) < 2:
        return 0.0
    return items[-1] - items[0]


def compute_order_flow(side: str, bars: Sequence[BacktestBar]) -> FactorValue:
    """F5:主动买占比 + CVD 斜率一致性。

    数据缺口(全部 taker_buy_volume 为 0)一律回退中性并标记 `data_gap`,
    **不得零填充** —— 零填充会伪造"无主动买盘"这一比不计分更危险的静默错误。
    """
    items = list(bars)
    if len(items) < ORDER_FLOW_WINDOW:
        return FactorValue(NEUTRAL_VALUE, True, {"reason": "insufficient_bars"})

    window = items[-ORDER_FLOW_WINDOW:]
    total_volume = sum(float(bar.volume) for bar in window)
    if total_volume <= 0:
        return FactorValue(NEUTRAL_VALUE, True, {"reason": "zero_volume"})

    taker_total = sum(float(getattr(bar, "taker_buy_volume", 0.0) or 0.0) for bar in window)
    if taker_total <= 0:
        return FactorValue(NEUTRAL_VALUE, True, {"reason": "order_flow_data_gap"})

    taker_ratio = _clip(taker_total / total_volume)
    directional = taker_ratio if _normalized_side(side) == "LONG" else 1.0 - taker_ratio

    deltas = [cvd_delta(float(bar.taker_buy_volume), float(bar.volume)) for bar in window]
    cumulative: list[float] = []
    running = 0.0
    for delta in deltas:
        running += delta
        cumulative.append(running)
    alignment = slope_alignment(cumulative, [float(bar.close) for bar in window])

    value = round(0.5 * directional + 0.5 * alignment, 4)
    return FactorValue(
        value,
        False,
        {
            "taker_ratio": round(taker_ratio, 4),
            "directional_taker_ratio": round(directional, 4),
            "slope_alignment": alignment,
        },
    )


# ---------------------------------------------------------------------------
# 聚合(P0 影子入口)
# ---------------------------------------------------------------------------


def five_factor_scores(
    side: str,
    completed: Mapping[str, Sequence[BacktestBar]],
    atr_pct_value: float,
) -> tuple[dict[str, float], dict[str, object]]:
    """计算五因子分量与元信息,返回 `(component_points_v2, meta)`。

    返回的字典**仅供记录**:调用方不得据此改变 action/score/门槛。
    `component_points_v2` 与旧 `component_points` 同口径(归一化值 × 权重 = 点数),
    `meta.normalized_values` 另存 0-1 原始分量供正交性/IC 分析使用。
    """
    bars_15m = list(completed.get("15m", []))
    latest_close = float(bars_15m[-1].close) if bars_15m else 0.0
    atr_value = latest_close * max(0.0, float(atr_pct_value))

    trend = compute_trend_persistence(side, bars_15m)
    structure = compute_structure_location(bars_15m, atr_value)
    swings = detect_fractal_swings(bars_15m, atr=atr_value) if bars_15m else []
    payoff = compute_payoff_geometry(latest_close, side, atr_value, swings)
    volatility = compute_volatility_regime(bars_15m)
    order_flow = compute_order_flow(side, bars_15m)

    component_points_v2 = {
        "trend_persistence": round(trend.value * FIVE_FACTOR_WEIGHTS["trend_persistence"], 4),
        "structure_location": round(structure.value * FIVE_FACTOR_WEIGHTS["structure_location"], 4),
        "payoff_geometry": round(payoff.value * FIVE_FACTOR_WEIGHTS["payoff_geometry"], 4),
        "volatility_regime_score": round(
            volatility.score * FIVE_FACTOR_WEIGHTS["volatility_regime"], 4
        ),
        "volatility_regime_leverage_mult": volatility.leverage_multiplier,
        "order_flow": round(order_flow.value * FIVE_FACTOR_WEIGHTS["order_flow"], 4),
    }
    meta: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "weights": dict(FIVE_FACTOR_WEIGHTS),
        "structure_fallback": structure.fallback,
        "order_flow_data_gap": order_flow.fallback,
        "volatility_fallback": volatility.fallback,
        "volatility_lookback_bars": volatility.lookback_bars,
        # 如实记录实际回看长度(受 --public-kline-limit 限制,通常远短于 30 天)
        "volatility_lookback_days": round(volatility.lookback_bars * 15 / (60 * 24), 2),
        # F4 双轨影子:clip v1 现役、gauss v2 候选(σ 网格)并行记录,互不覆盖
        "volatility_regime_clip_v1": volatility.score,
        "volatility_regime_gauss_v2": dict(volatility.gauss_scores),
        "trend_fallback": trend.fallback,
        "payoff_fallback": payoff.fallback,
        "normalized_values": {
            "trend_persistence": trend.value,
            "structure_location": structure.value,
            "payoff_geometry": payoff.value,
            "volatility_regime": volatility.score,
            "order_flow": order_flow.value,
        },
        "shadow_total": round(sum(component_points_v2[key] for key in FIVE_FACTOR_POINT_KEYS), 4),
    }
    return component_points_v2, meta
