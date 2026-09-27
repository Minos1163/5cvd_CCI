# -*- coding: utf-8 -*-
"""T2-T6:五正交因子单测(F1-F5)。

对应裁定报告第十三节测试矩阵;每条验收点在函数 docstring 中标注。
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.backtest.engine import BacktestBar  # noqa: E402
from src.signals.fib_location import SwingPoint  # noqa: E402
from src.signals.orthogonal_factors import (  # noqa: E402
    FIVE_FACTOR_POINT_KEYS,
    FIVE_FACTOR_WEIGHTS,
    compute_order_flow,
    compute_payoff_geometry,
    compute_structure_location,
    compute_trend_persistence,
    compute_volatility_regime,
    five_factor_scores,
    leverage_multiplier_from_percentile,
    volatility_score_from_percentile,
)


def _bars(
    closes: list[float],
    *,
    volumes: list[float] | None = None,
    taker_ratios: list[float] | None = None,
    symbol: str = "TESTUSDT",
) -> list[BacktestBar]:
    bars: list[BacktestBar] = []
    for index, close in enumerate(closes):
        volume = volumes[index] if volumes else 100.0
        taker_ratio = taker_ratios[index] if taker_ratios else 0.5
        bars.append(
            BacktestBar(
                symbol=symbol,
                timestamp=index * 900,
                open=close,
                high=close * 1.001,
                low=close * 0.999,
                close=close,
                volume=volume,
                taker_buy_volume=volume * taker_ratio,
            )
        )
    return bars


def _swing(kind: str, price: float, index: int = 0) -> SwingPoint:
    return SwingPoint(kind=kind, timestamp=index * 900, index=index, price=price)


# ---------------------------------------------------------------------------
# F1 趋势持久性
# ---------------------------------------------------------------------------


def test_donchian_pos_direction_symmetry():
    bars = _bars([100.0 + index * 0.05 for index in range(260)])
    long_result = compute_trend_persistence("LONG", bars)
    short_result = compute_trend_persistence("SHORT", bars)
    assert long_result.detail["directional_position"] + short_result.detail[
        "directional_position"
    ] == pytest.approx(1.0)


def test_ema_slope_flat_market_neutral():
    bars = _bars([100.0] * 260)
    result = compute_trend_persistence("LONG", bars)
    assert result.detail["ema200_slope_z"] == 0.0
    assert result.value == pytest.approx(0.5)  # 无趋势 → 中性,不产生虚假信号


def test_trend_persistence_is_continuous():
    values = {
        compute_trend_persistence("LONG", _bars([100.0] * 19 + [100.0 + offset * 0.01])).value
        for offset in range(1, 21)
    }
    assert len(values) >= 10


def test_trend_persistence_insufficient_bars_fallback():
    result = compute_trend_persistence("LONG", _bars([100.0] * 5))
    assert result.value == 0.5
    assert result.fallback is True


# ---------------------------------------------------------------------------
# F2 结构位置(去方向化)
# ---------------------------------------------------------------------------


def test_structure_location_side_invariance():
    """去方向化的直接证据:同一批 K 线,LONG/SHORT 下 F2 取值完全一致。"""
    completed = {"15m": _bars([100.0 + (index % 7) * 0.3 for index in range(120)])}
    long_points, _ = five_factor_scores("LONG", completed, 0.01)
    short_points, _ = five_factor_scores("SHORT", completed, 0.01)
    assert long_points["structure_location"] == short_points["structure_location"]


def test_structure_fallback_neutral_not_zero():
    result = compute_structure_location(_bars([100.0] * 30), 0.0)
    assert result.value == 0.5
    assert result.fallback is True


# ---------------------------------------------------------------------------
# F3 赔率几何
# ---------------------------------------------------------------------------


def test_payoff_r_no_ceiling():
    """旧实现 net_tp1_r>=1.3 即封顶 5.0/8;新实现必须继续随赔率上升。"""
    moderate = compute_payoff_geometry(100.0, "SHORT", 1.5, [_swing("LOW", 100.0 - 2.1)])
    strong = compute_payoff_geometry(100.0, "SHORT", 1.5, [_swing("LOW", 100.0 - 6.1)])
    extreme = compute_payoff_geometry(100.0, "SHORT", 1.5, [_swing("LOW", 100.0 - 8.1)])
    assert moderate.detail["payoff_r"] < strong.detail["payoff_r"] < extreme.detail["payoff_r"]
    assert moderate.value < strong.value < extreme.value
    assert extreme.value == 1.0


def test_payoff_r_negative_clip():
    result = compute_payoff_geometry(100.0, "SHORT", 1.5, [_swing("LOW", 99.99)])
    assert result.value == 0.0
    assert result.fallback is False


def test_payoff_geometry_is_continuous():
    values = {
        compute_payoff_geometry(100.0, "SHORT", 1.5, [_swing("LOW", 100.0 - 0.1 * step)]).value
        for step in range(1, 21)
    }
    assert len(values) >= 10


def test_payoff_geometry_no_counter_structure_fallback():
    result = compute_payoff_geometry(100.0, "SHORT", 1.5, [])
    assert result.value == 0.5
    assert result.fallback is True


# ---------------------------------------------------------------------------
# F4 波动率状态
# ---------------------------------------------------------------------------


def test_vol_score_peak_near_60th_pctile():
    assert volatility_score_from_percentile(0.60) == 1.0
    assert volatility_score_from_percentile(0.60) > volatility_score_from_percentile(0.30)
    assert volatility_score_from_percentile(0.60) > volatility_score_from_percentile(0.90)


def test_leverage_multiplier_monotonic_decay():
    values = [leverage_multiplier_from_percentile(step / 100.0) for step in range(70, 101)]
    assert all(earlier >= later for earlier, later in zip(values, values[1:]))
    assert values[0] == 1.0
    assert leverage_multiplier_from_percentile(1.0) == 0.4
    assert leverage_multiplier_from_percentile(0.60) == 1.0  # 评分峰值区间不缩仓


def test_volatility_regime_insufficient_history_fallback():
    result = compute_volatility_regime(_bars([100.0] * 100))
    assert result.fallback is True
    assert result.score == 0.5
    assert result.leverage_multiplier == 1.0


def test_volatility_regime_active_with_available_history():
    """live 默认只拉约 241 根 15m → 必须产出真实分位,而非永久中性回退。"""
    bars = _bars([100.0 + (index % 9) * 0.5 for index in range(260)])
    result = compute_volatility_regime(bars)
    assert result.fallback is False
    assert result.lookback_bars >= 200
    assert "atr_percentile" in result.detail
    assert 0.0 <= float(result.detail["atr_percentile"]) <= 1.0


# ---------------------------------------------------------------------------
# F5 真实订单流
# ---------------------------------------------------------------------------


def test_order_flow_data_gap_fallback():
    """字段缺失必须回退中性并标记,不得零填充(零填充会伪造"无主动买盘")。"""
    bars = [
        BacktestBar(
            symbol="TESTUSDT",
            timestamp=index * 900,
            open=100.0,
            high=100.1,
            low=99.9,
            close=100.0,
            volume=100.0,
            taker_buy_volume=0.0,
        )
        for index in range(12)
    ]
    result = compute_order_flow("LONG", bars)
    assert result.value == 0.5
    assert result.fallback is True
    assert result.detail["reason"] == "order_flow_data_gap"


def test_order_flow_uses_real_taker_volume():
    bars = _bars([100.0 + index * 0.01 for index in range(12)], taker_ratios=[0.8] * 12)
    result = compute_order_flow("LONG", bars)
    assert result.detail["taker_ratio"] == pytest.approx(0.8)
    assert result.value > 0.5  # 主动买占优 + 与价格同向 → 高于中性


def test_order_flow_short_mirrors_long():
    bars = _bars([100.0] * 12, taker_ratios=[0.8] * 12)
    long_result = compute_order_flow("LONG", bars)
    short_result = compute_order_flow("SHORT", bars)
    assert long_result.detail["directional_taker_ratio"] == pytest.approx(
        1.0 - short_result.detail["directional_taker_ratio"]
    )


# ---------------------------------------------------------------------------
# 聚合契约
# ---------------------------------------------------------------------------


def test_five_factor_scores_contract():
    completed = {"15m": _bars([100.0 + (index % 11) * 0.2 for index in range(260)])}
    points, meta = five_factor_scores("LONG", completed, 0.01)
    assert set(points) == set(FIVE_FACTOR_POINT_KEYS) | {"volatility_regime_leverage_mult"}
    assert meta["schema_version"] == "v2-p0-shadow"
    assert sum(meta["weights"].values()) == 100.0
    assert set(meta["normalized_values"]) == {
        "trend_persistence",
        "structure_location",
        "payoff_geometry",
        "volatility_regime",
        "order_flow",
    }
    expected_total = sum(points[key] for key in FIVE_FACTOR_POINT_KEYS)
    assert meta["shadow_total"] == pytest.approx(expected_total)


def test_five_factor_scores_handles_empty_input():
    points, meta = five_factor_scores("LONG", {}, 0.01)
    assert all(isinstance(value, float) for value in points.values())
    assert meta["shadow_total"] >= 0.0
