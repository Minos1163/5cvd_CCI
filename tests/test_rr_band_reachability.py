"""RR 可达性锁死（P0 A3）：把"满分不可达"从一句文档变成会红的测试。

当前评分公式（`risk_reward_geometry_detail`，10bps 口径）：

    net_tp1_r = (stop_dist × 1.2 − close × 0.001) / stop_dist
              = 1.2 − 0.001 / stop_pct

而 RR 得分分档是 `>=1.3 → 5.0`、`>=1.1 → 3.5`、`>=0.9 → 2.0`、否则 0.0。

于是：

1. **1.3 在合法止损区间内不可达**。`1.2 − 0.001/stop_pct < 1.2` 恒成立，
   要 ≥1.3 需要 `0.001/stop_pct <= −0.1`，即 `stop_pct < 0`，物理上不存在。
   所以 8 分制 RR 分量的满分（5.0 档）**永远是 0 次**。
2. **上界 1.167**（`stop_pct = 3.0%` 时），远低于 1.3。
3. `>=1.1` 只在**宽止损**一侧可达：`1.2 − 0.001/stop_pct >= 1.1` ⟺ `stop_pct >= 1.0%`。
   注意方向——止损越**窄**，固定成本吃掉的 R 越多，净 R 越**低**；
   0.5% 止损的净 R 只有 1.000，反而够不到 1.1 档。
   （2026-11-14 评审文档与任务书曾把这一条写成"仅 stop_pct <= 1.0% 可达"，方向是反的；
   team-lead 已确认以本节推导与实测为准。）
4. `>=0.9` 在整个区间恒成立：最小 1.000（0.5% 止损）。

## 比"满分不可达"更该关注的方向性问题

RR 因子对止损宽度是**单调正向**的：止损越宽，`net_tp1_r` 越高、得分越高。
因此这个因子实际在奖励宽止损，而不是评估风险回报质量。

含义（同一条 K 线、同一份行情）：
- 同样的价格波动，只要 ATR 大一点把止损推到 2%–3%，RR 项就能自动从 2.0 档（5.0 分）跳到
  3.5 档（6.5 分），与"这笔交易的赔率是否真的更好"无关；
- 反之，低波动品种的窄止损（0.5%–1.0%）被系统性扣分——但窄止损恰恰意味着单位风险的名义
  暴露更大、成本占比更高，本该更严，而不是更松；
- 因此 RR 分量的实质是"波动率分档"的另一种写法，`risk_reward_geometry` 这个名字与实际
  语义不符。真正要修的不是把 1.3 阈值调到够得着，而是换掉 `net_tp1_r` 的构造方式
  （成本口径 + 对手结构距离 + 目标位质量），并重新校准全部入场阈值（82/77/72）。
  这属于 B 类（会改 score → 改 action），本轮只留诊断字段与这条测试。

**这组测试的作用**是锁死上面的事实。将来若修正公式（例如改成 20bps 往返成本并重设阈值），
这些断言会红——那是**故意**的：必须显式更新阈值与档位，而不是让分数口径悄悄漂移。
"""

from __future__ import annotations

import pytest

from src.signals.entry_chain_features import (
    RR_BAND_GE_1_1,
    RR_BAND_GE_1_3,
    RR_BAND_GE_0_9,
    RR_BAND_LT_0_9,
    risk_reward_geometry_detail,
    rr_band,
)
from src.signals.trade_geometry import TradeGeometry

CLOSE = 100.0
ATR_PCT = 0.02  # 落在 0.008–0.025 的"加分区间"，让 atr 项不干扰分档观察

# 0.5% → 3.0%，步长 0.1%，共 26 个采样点。
STOP_PCT_SWEEP = tuple(0.005 + index * 0.001 for index in range(26))


def scoring_net_tp1_r(stop_pct: float) -> float:
    """评分侧实际使用的净 TP1 R（与 `risk_reward_geometry_detail` 同一表达式）。

    直接复用 `TradeGeometry.stop_dist`（同一处定义、同一浮点路径），再按历史公式
    `(stop_dist×1.2 − close×0.001)/stop_dist` 求值，避免测试自己另写一套 clamp。
    """
    geometry = TradeGeometry(entry_price=CLOSE, side="LONG", atr=CLOSE * stop_pct / 1.5)
    stop_dist = geometry.stop_dist
    return (stop_dist * 1.2 - CLOSE * 0.001) / stop_dist


SAMPLES = tuple((stop_pct, scoring_net_tp1_r(stop_pct)) for stop_pct in STOP_PCT_SWEEP)


def test_sweep_covers_26_points() -> None:
    """采样完整性：0.5%–3.0% 共 26 点，别静默少测。"""
    assert len(STOP_PCT_SWEEP) == 26
    assert STOP_PCT_SWEEP[0] == pytest.approx(0.005)
    assert STOP_PCT_SWEEP[-1] == pytest.approx(0.030)


def test_top_band_is_unreachable_across_entire_stop_range() -> None:
    """① 没有任何一个采样点的净 R ≥ 1.3 —— 5.0 档永远打不出来。"""
    offenders = [(stop_pct, net_r) for stop_pct, net_r in SAMPLES if net_r >= 1.3]
    assert not offenders, f"净 R 竟然达到 1.3：{offenders}"
    assert all(rr_band(net_r) != RR_BAND_GE_1_3 for _stop_pct, net_r in SAMPLES)


def test_net_r_upper_bound_stays_below_one_point_one_seven() -> None:
    """② 上界严格小于 1.17（理论值 1.1667，出现在 3.0% 止损）。"""
    assert max(net_r for _stop_pct, net_r in SAMPLES) < 1.17


def test_ge_1_1_band_only_reachable_at_wide_stops() -> None:
    """③ ≥1.1 只在**宽止损**一侧可达（stop_pct ≥ 1.0%），窄止损反而够不到。

    `1.2 − 0.001/stop_pct >= 1.1` ⟺ `stop_pct >= 0.01`。0.5% 止损的净 R 恰好是 1.000。
    这是"RR 因子奖励宽止损"的直接证据，见模块 docstring 的方向性问题一节。
    """
    reachable = [(stop_pct, net_r) for stop_pct, net_r in SAMPLES if net_r >= 1.1]
    assert reachable, "若一条都不可达，说明公式或阈值被改过，必须显式更新本测试"
    for stop_pct, _net_r in reachable:
        assert stop_pct >= 0.010 - 1e-12, f"stop_pct={stop_pct} 竟然能进 1.1 档"
    # 反向：所有窄于 1.0% 的止损都进不了 1.1 档
    for stop_pct, net_r in SAMPLES:
        if stop_pct < 0.010 - 1e-12:
            assert net_r < 1.1
            assert rr_band(net_r) == RR_BAND_GE_0_9


def test_net_r_is_monotonically_increasing_in_stop_width() -> None:
    """RR 因子对止损宽度**单调正向**：止损越宽 → 净 R 越高 → 得分越高。

    这条是方向性问题的可执行表述：因子在奖励宽止损，而不是评估风险回报质量。
    详见模块 docstring「比满分不可达更该关注的方向性问题」。
    """
    net_rs = [net_r for _stop_pct, net_r in SAMPLES]
    assert all(later > earlier for earlier, later in zip(net_rs, net_rs[1:])), "净 R 不再对止损宽度单调递增"
    # 档位单调不降：窄端的 2.0 档 → 宽端的 3.5 档
    bands = [rr_band(net_r) for net_r in net_rs]
    assert bands.count(RR_BAND_GE_0_9) + bands.count(RR_BAND_GE_1_1) == len(bands)
    assert bands[0] == RR_BAND_GE_0_9, "最窄止损必须是 2.0 档"
    assert bands[-1] == RR_BAND_GE_1_1, "最宽止损必须是 3.5 档"


def test_wider_stop_scores_higher_than_narrower_stop_on_same_bars() -> None:
    """同一根 K 线换一个更宽的止损宽度（= 更高 ATR），RR 得分反而更高。

    这就是"奖励宽止损"的落地后果：更高波动（ATR）在同一条 K 线上自动换来更高 RR 分，
    与赔率是否真的更好无关。数值用 detail 的 score 而不是净 R，避免只测到中间量。
    """
    narrow = risk_reward_geometry_detail(
        close=CLOSE,
        side="LONG",
        atr_value=CLOSE * 0.005 / 1.5,  # 止损被 0.5% 下限兜住
        atr_pct_value=ATR_PCT,
        swings=[],
    )
    wide = risk_reward_geometry_detail(
        close=CLOSE,
        side="LONG",
        atr_value=CLOSE * 0.030 / 1.5,  # 止损被 3.0% 上限截断
        atr_pct_value=ATR_PCT,
        swings=[],
    )
    assert wide["score"] > narrow["score"]
    assert (narrow["rr_band"], wide["rr_band"]) == (RR_BAND_GE_0_9, RR_BAND_GE_1_1)


def test_ge_0_9_band_always_holds() -> None:
    """④ 整个止损区间内净 R 恒 ≥ 0.9：RR 分量至少能拿到 2.0 档。"""
    for stop_pct, net_r in SAMPLES:
        assert net_r >= 0.9, f"stop_pct={stop_pct} 的净 R={net_r} 掉到 0.9 以下"
        assert rr_band(net_r) in {RR_BAND_GE_1_1, RR_BAND_GE_0_9}


def test_min_band_never_used_on_current_formula() -> None:
    """推论：`LT_0_9` 在当前公式下同样是死档位（留档，便于将来对照）。"""
    assert all(rr_band(net_r) != RR_BAND_LT_0_9 for _stop_pct, net_r in SAMPLES)


@pytest.mark.parametrize("stop_pct", [0.005, 0.010, 0.020, 0.030])
def test_detail_exposes_consistent_rr_band(stop_pct: float) -> None:
    """`risk_reward_geometry_detail` 的 `rr_band` 必须与分数档位一一对应。"""
    geometry = TradeGeometry(entry_price=CLOSE, side="LONG", atr=CLOSE * stop_pct / 1.5)
    detail = risk_reward_geometry_detail(
        close=CLOSE,
        side="LONG",
        atr_value=geometry.atr,
        atr_pct_value=ATR_PCT,
        swings=[],
    )
    # 无对手结构的干净样本：score = 分档分 + 3.0（atr 在加分区间）
    assert detail["rr_band"] == rr_band(scoring_net_tp1_r(stop_pct))
    assert detail["rr_band"] in {RR_BAND_GE_1_1, RR_BAND_GE_0_9}
    expected_band_score = {RR_BAND_GE_1_3: 5.0, RR_BAND_GE_1_1: 3.5, RR_BAND_GE_0_9: 2.0, RR_BAND_LT_0_9: 0.0}
    assert detail["score"] == pytest.approx(min(8.0, expected_band_score[detail["rr_band"]] + 3.0), rel=0, abs=1e-9)
    # 20bps 口径的净 R 只作诊断，永远低于 10bps 口径
    assert detail["net_tp1_r_at_20bps"] < detail["net_tp1_r"]
    assert detail["cost_bps_used_by_score"] == 10.0
    assert detail["geometry_version"] == "1"


def test_invalid_input_detail_keeps_diagnostic_keys() -> None:
    """非法输入也返回完整键集，读取侧不会因为缺键炸掉。"""
    detail = risk_reward_geometry_detail(0.0, "LONG", 1.0, ATR_PCT, [])
    assert detail["rr_zero_reason"] == "INVALID_INPUT"
    assert detail["rr_band"] == RR_BAND_LT_0_9
    assert detail["net_tp1_r_at_20bps"] == 0.0
    assert detail["cost_bps_used_by_score"] == 10.0
    assert detail["geometry_version"] == "1"
