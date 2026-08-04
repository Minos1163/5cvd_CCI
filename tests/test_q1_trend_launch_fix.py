# -*- coding: utf-8 -*-
"""q1_trend_launch 修复(移除确认标签依赖 + 非极值追单检查)的单元测试。

覆盖:
  1) extreme_position_ratio 特征函数(close 在近 8 根极值区间的相对位置)
  2) _q1_trend_launch_eligible:
     - 无确认标签(Q2_PENDING_MOMENTUM_CONFIRMED / Q3_TO_Q1_CONFIRMED)也能通过 → 标签依赖已移除
     - 极值比例越界 → 拒绝(非极值追单检查)
     - LONG + overextension/wick/chase → 拒绝(防反转/追单)
     - 分数/PA/Fib/CVD/RR 条件保持
     - 非 Q1 / blacklist / near_miss=None → 拒绝
"""
from dataclasses import replace

import pytest

from src.backtest.engine import BacktestBar
from src.signals.entry_chain_config import EntryChainConfig
from src.signals.entry_chain_features import extreme_position_ratio

from scripts.run_live_dry_run import _q1_trend_launch_eligible

BASE_CONFIG = replace(
    EntryChainConfig(),
    dry_run_q1_trend_launch_enabled=True,
    dry_run_q1_trend_launch_min_score=82.0,
    dry_run_q1_trend_launch_min_pa_score=18.0,
    dry_run_q1_trend_launch_min_fib_score=15.0,
    dry_run_q1_trend_launch_min_cvd_score=16.0,
    dry_run_q1_trend_launch_min_rr_score=0.5,
    dry_run_q1_trend_launch_extreme_ratio_min=0.20,
    dry_run_q1_trend_launch_extreme_ratio_max=0.80,
)


def _component_points(**overrides):
    points = {
        "trend_ema_context": 16.0,
        "price_action_structure": 18.0,
        "flow_cvd_confirmation": 16.0,
        "cci_momentum_quality": 8.0,
        "fibonacci_location": 16.0,
        "risk_reward_geometry": 3.0,
    }
    points.update(overrides)
    return points


def _make_near_miss(**overrides):
    nm = {
        "symbol": "SOLUSDT",
        "intended_side": "SHORT",
        "entry_price": 100.0,
        "score": 90.0,
        "component_points": _component_points(),
        "entry_context": {
            "extreme_position_ratio": 0.5,
            "long_overextension_active": False,
            "long_upper_wick_risk_active": False,
            "long_chase_risk_active": False,
        },
        "scout_tags": [],
    }
    nm.update(overrides)
    return nm


# ---------- extreme_position_ratio ----------

def _bar(ts, close, open_, high, low):
    return BacktestBar("SOLUSDT", ts, open_, high, low, close, 10)


def test_extreme_position_ratio_mid_range():
    # 区间 [10, 20], close=15 → 0.5
    bars = [_bar(i * 900, 15.0, 15.0, 20.0, 10.0) for i in range(9)]
    assert extreme_position_ratio(bars) == pytest.approx(0.5)


def test_extreme_position_ratio_at_top():
    # close 贴近区间顶 → > 0.8
    bars = [_bar(i * 900, 15.0, 15.0, 20.0, 10.0) for i in range(8)] + [
        _bar(8 * 900, 19.0, 19.0, 20.0, 18.0)
    ]
    assert extreme_position_ratio(bars) > 0.8


def test_extreme_position_ratio_at_bottom():
    # close 贴近区间底 → < 0.2
    bars = [_bar(i * 900, 15.0, 15.0, 20.0, 10.0) for i in range(8)] + [
        _bar(8 * 900, 11.0, 11.0, 12.0, 10.0)
    ]
    assert extreme_position_ratio(bars) < 0.2


def test_extreme_position_ratio_insufficient_bars_is_neutral():
    assert extreme_position_ratio([_bar(1, 10.0, 10.0, 11.0, 9.0), _bar(2, 10.5, 10.5, 11.5, 10.0)]) == 0.5


# ---------- _q1_trend_launch_eligible ----------

def test_eligible_without_confirmation_tags():
    # 核心修复: 无任何确认标签也应通过(其余条件满足)
    nm = _make_near_miss()
    assert "Q2_PENDING_MOMENTUM_CONFIRMED" not in (nm.get("scout_tags") or [])
    assert "Q3_TO_Q1_CONFIRMED" not in (nm.get("scout_tags") or [])
    assert _q1_trend_launch_eligible(nm, BASE_CONFIG, "OK") is True


def test_eligible_with_deprecated_tags_still_passes():
    # 即便历史数据带旧标签, 也应通过(标签不再参与判定)
    nm = _make_near_miss(scout_tags=["Q2_PENDING_MOMENTUM_CONFIRMED"])
    assert _q1_trend_launch_eligible(nm, BASE_CONFIG, "OK") is True


def test_blocked_by_extreme_ratio_high():
    nm = _make_near_miss(entry_context={
        "extreme_position_ratio": 0.95,  # 追到区间顶
        "long_overextension_active": False,
        "long_upper_wick_risk_active": False,
        "long_chase_risk_active": False,
    })
    assert _q1_trend_launch_eligible(nm, BASE_CONFIG, "OK") is False


def test_blocked_by_extreme_ratio_zero():
    # 合法测量值 0.0(close 恰为窗口最低): 必须被极值下限拒绝, 不得被 or 回退成 0.5 放行
    nm = _make_near_miss(entry_context={
        "extreme_position_ratio": 0.0,
        "long_overextension_active": False,
        "long_upper_wick_risk_active": False,
        "long_chase_risk_active": False,
    })
    assert _q1_trend_launch_eligible(nm, BASE_CONFIG, "OK") is False


def test_missing_extreme_ratio_falls_back_neutral():
    # 字段缺失/None: 回退中性 0.5, 不阻断(其余条件满足)
    nm = _make_near_miss(entry_context={
        "long_overextension_active": False,
        "long_upper_wick_risk_active": False,
        "long_chase_risk_active": False,
    })
    assert _q1_trend_launch_eligible(nm, BASE_CONFIG, "OK") is True


def test_blocked_by_extreme_ratio_low():
    nm = _make_near_miss(entry_context={
        "extreme_position_ratio": 0.05,  # 追到区间底
        "long_overextension_active": False,
        "long_upper_wick_risk_active": False,
        "long_chase_risk_active": False,
    })
    assert _q1_trend_launch_eligible(nm, BASE_CONFIG, "OK") is False


def test_long_blocked_by_overextension():
    nm = _make_near_miss(
        intended_side="LONG",
        entry_context={
            "extreme_position_ratio": 0.5,
            "long_overextension_active": True,
            "long_upper_wick_risk_active": False,
            "long_chase_risk_active": False,
        },
    )
    assert _q1_trend_launch_eligible(nm, BASE_CONFIG, "OK") is False


def test_long_blocked_by_wick_or_chase():
    for flag in ("long_upper_wick_risk_active", "long_chase_risk_active"):
        nm = _make_near_miss(
            intended_side="LONG",
            entry_context={
                "extreme_position_ratio": 0.5,
                "long_overextension_active": False,
                "long_upper_wick_risk_active": flag == "long_upper_wick_risk_active",
                "long_chase_risk_active": flag == "long_chase_risk_active",
            },
        )
        assert _q1_trend_launch_eligible(nm, BASE_CONFIG, "OK") is False


def test_short_not_blocked_by_long_flags():
    # SHORT 方向不受 long_* 标志影响(由通用极值检查覆盖)
    nm = _make_near_miss(
        intended_side="SHORT",
        entry_context={
            "extreme_position_ratio": 0.5,
            "long_overextension_active": True,
            "long_upper_wick_risk_active": True,
            "long_chase_risk_active": True,
        },
    )
    assert _q1_trend_launch_eligible(nm, BASE_CONFIG, "OK") is True


def test_score_below_min_rejected():
    nm = _make_near_miss(score=80.0)
    assert _q1_trend_launch_eligible(nm, BASE_CONFIG, "OK") is False


def test_pa_below_min_rejected():
    nm = _make_near_miss(component_points=_component_points(price_action_structure=15.0))
    assert _q1_trend_launch_eligible(nm, BASE_CONFIG, "OK") is False


def test_non_q1_rejected():
    # 降低 trend/cvd 使象限滑出 Q1
    nm = _make_near_miss(component_points=_component_points(trend_ema_context=5.0, cci_momentum_quality=8.0))
    assert _q1_trend_launch_eligible(nm, BASE_CONFIG, "OK") is False


def test_blacklisted_symbol_rejected():
    cfg = replace(BASE_CONFIG, blacklist_symbols=["SOLUSDT"])
    assert _q1_trend_launch_eligible(_make_near_miss(), cfg, "OK") is False


def test_disabled_channel_rejected():
    cfg = replace(BASE_CONFIG, dry_run_q1_trend_launch_enabled=False)
    assert _q1_trend_launch_eligible(_make_near_miss(), cfg, "OK") is False


def test_none_near_miss_rejected():
    assert _q1_trend_launch_eligible(None, BASE_CONFIG, "OK") is False
