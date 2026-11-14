"""`TradeGeometry` 守卫（P0 A2）。

`TradeGeometry` 的唯一职责是把"止损宽度 / 止损价 / TP 阶梯 / 净 R"收敛到一处定义，
让评分链、测试与将来的分析脚本不再各算一套。它**不改变任何交易行为**，因此这里最重要
的断言不是"算得对不对"，而是"跟重构前逐位一样"：

- `stop_dist` 必须与 `risk_reward_geometry_detail` 重构前那一行 clamp 逐位相同。
  这不是形式主义：`stop_dist` 直接进入 `net_tp1_r`，再与 1.3/1.1/0.9 三个评分阈值比较，
  1 ulp 的漂移在边界样本上足以翻转 `score` → 翻转 `action`。
  因此 `stop_dist` 刻意按价格空间写（`max(entry×min, min(entry×max, atr×mult))`），
  `stop_pct` 是它的派生量，而不是反过来。
- `net_tp1_r(20.0)` 与评分实际使用的 10bps 口径必须不同，且成本越高净 R 越低。
"""

from __future__ import annotations

import pytest

from src.signals.entry_chain_features import risk_reward_geometry_detail
from src.signals.trade_geometry import TradeGeometry

CLOSE = 100.0


def legacy_stop_dist(close: float, atr_value: float) -> float:
    """重构前 `risk_reward_geometry_detail` 内的止损 clamp，逐字复制自 HEAD f260b1a。"""
    return max(close * 0.005, min(close * 0.030, atr_value * 1.5))


def geometry_at_stop_pct(stop_pct: float, close: float = CLOSE, side: str = "LONG") -> TradeGeometry:
    """反解 atr，使未 clamp 的止损宽度恰好等于 `stop_pct`。"""
    return TradeGeometry(entry_price=close, side=side, atr=close * stop_pct / 1.5)


@pytest.mark.parametrize("stop_pct", [0.005, 0.010, 0.015, 0.020, 0.030])
def test_stop_dist_matches_legacy_clamp_bit_for_bit(stop_pct: float) -> None:
    """四个边界 + 中点的 `stop_dist` 与重构前一行 clamp 逐位相同。"""
    geometry = geometry_at_stop_pct(stop_pct)
    assert geometry.stop_dist == legacy_stop_dist(CLOSE, geometry.atr)
    assert geometry.stop_pct == pytest.approx(stop_pct, rel=0, abs=1e-12)


def test_stop_dist_matches_legacy_clamp_on_wide_grid() -> None:
    """网格上逐位相同——这是"零行为变化"的核心断言，不要放宽成 approx。"""
    closes = [0.0001234, 0.5, 1.0, 2.7, 17.3517, 99.99, 100.0, 4321.7, 67890.12, 100000.0]
    atr_pcts = [0.0, 0.0001, 0.004, 0.005, 0.008, 0.01, 0.02, 0.025, 0.0301, 0.05, 0.12]
    for close in closes:
        for atr_pct in atr_pcts:
            for multiplier in (0.2, 1.0, 1.5, 2.0, 3.333, 10.0):
                atr_value = close * atr_pct * multiplier
                geometry = TradeGeometry(entry_price=close, side="LONG", atr=atr_value)
                assert geometry.stop_dist == legacy_stop_dist(close, atr_value)


def test_clamp_binds_below_floor_and_above_cap() -> None:
    """atr 过小时止损被 0.5% 兜住，过大时被 3.0% 截断。"""
    tiny = TradeGeometry(entry_price=CLOSE, side="LONG", atr=0.01)  # 原始 0.015% ≪ 0.5%
    assert tiny.stop_pct == pytest.approx(0.005, rel=0, abs=1e-12)
    assert tiny.stop_dist == pytest.approx(0.5, rel=0, abs=1e-12)

    huge = TradeGeometry(entry_price=CLOSE, side="LONG", atr=50.0)  # 原始 75% ≫ 3%
    assert huge.stop_pct == pytest.approx(0.030, rel=0, abs=1e-12)
    assert huge.stop_dist == pytest.approx(3.0, rel=0, abs=1e-12)


@pytest.mark.parametrize("stop_pct", [0.005, 0.010, 0.020, 0.030])
def test_geometry_agrees_with_risk_reward_geometry_detail(stop_pct: float) -> None:
    """`risk_reward_geometry_detail` 报出来的 stop_pct / tp1_pct 与该几何自洽。

    detail 侧保留 4 位小数四舍五入，所以这里比的是四舍五入后的值。
    """
    geometry = geometry_at_stop_pct(stop_pct)
    detail = risk_reward_geometry_detail(
        close=CLOSE,
        side="LONG",
        atr_value=geometry.atr,
        atr_pct_value=0.02,
        swings=[],
    )
    assert detail["stop_pct"] == round(geometry.stop_pct, 4)
    assert detail["tp1_pct"] == round(geometry.stop_dist * 1.2 / CLOSE, 4)


def test_long_and_short_are_mirror_images() -> None:
    """LONG 的止损在下方、TP 在上方；SHORT 镜像；R 倍数不变。"""
    long_geometry = geometry_at_stop_pct(0.015, side="LONG")
    short_geometry = geometry_at_stop_pct(0.015, side="SHORT")

    assert long_geometry.stop_price == pytest.approx(CLOSE * (1 - 0.015), rel=0, abs=1e-9)
    assert short_geometry.stop_price == pytest.approx(CLOSE * (1 + 0.015), rel=0, abs=1e-9)
    assert long_geometry.stop_price < CLOSE < short_geometry.stop_price

    for long_price, short_price, level in zip(long_geometry.tp_prices, short_geometry.tp_prices, (1.2, 2.0, 3.0)):
        assert long_price == pytest.approx(CLOSE * (1 + 0.015 * level), rel=0, abs=1e-9)
        assert short_price == pytest.approx(CLOSE * (1 - 0.015 * level), rel=0, abs=1e-9)
        assert long_price > CLOSE > short_price

    assert long_geometry.gross_r_per_tp == short_geometry.gross_r_per_tp == (1.2, 2.0, 3.0)


def test_higher_cost_lowers_net_tp1_r() -> None:
    """成本越高净 R 越低；这是"净 R 必须带成本口径"的直接体现。"""
    for stop_pct in (0.005, 0.010, 0.020, 0.030):
        geometry = geometry_at_stop_pct(stop_pct)
        assert geometry.net_tp1_r(20.0) < geometry.net_tp1_r(10.0) < geometry.net_tp1_r(0.0)


def test_net_tp1_r_at_twenty_bps_differs_from_score_ten_bps() -> None:
    """0.5% 窄止损下 20bps 口径约 0.8、10bps 口径约 1.0 —— 旧口径系统性高估 0.2R。

    `1.2 − (bps/10000)/stop_pct`：0.5% 止损时 20bps 扣 0.4R，10bps 扣 0.2R。
    """
    geometry = geometry_at_stop_pct(0.005)
    assert geometry.net_tp1_r(20.0) == pytest.approx(0.8, rel=0, abs=1e-9)
    assert geometry.net_tp1_r(10.0) == pytest.approx(1.0, rel=0, abs=1e-9)
    assert geometry.net_tp1_r(20.0) - geometry.net_tp1_r(10.0) == pytest.approx(-0.2, rel=0, abs=1e-9)


def test_net_tp1_r_defaults_to_twenty_bps_round_trip() -> None:
    """默认成本口径是往返 20bps（不是评分侧的 10bps）。"""
    geometry = geometry_at_stop_pct(0.010)
    assert geometry.cost_bps_round_trip == 20.0
    assert geometry.net_tp1_r() == geometry.net_tp1_r(20.0)


def test_degenerate_inputs_do_not_raise() -> None:
    """退化输入不抛异常——决策链路上抛错等于停机，属于行为变更。"""
    zero_price = TradeGeometry(entry_price=0.0, side="LONG", atr=1.0)
    assert zero_price.stop_dist == 0.0
    assert zero_price.stop_pct == 0.0
    assert zero_price.net_tp1_r() == 0.0

    # atr=0 与历史 clamp 一致：落到 0.5% 下限，而不是 0（不要"顺手修"成 0）
    zero_atr = TradeGeometry(entry_price=CLOSE, side="LONG", atr=0.0)
    assert zero_atr.stop_dist == legacy_stop_dist(CLOSE, 0.0)
    assert zero_atr.stop_pct == pytest.approx(0.005, rel=0, abs=1e-12)
