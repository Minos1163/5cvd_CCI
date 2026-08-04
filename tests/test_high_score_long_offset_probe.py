# -*- coding: utf-8 -*-
"""HIGH_SCORE_LONG_OFFSET_PROBE 校准(quadrant 配置化 + min_score 82)的单测。

背景: 窗口诊断显示 probe 0 触发的根因是
  - quadrant==Q1 硬编码, 而 ≥85 的 LONG 样本在 Q3(如 BCH 87.3)
  - min_score=85 卡住 84.1/83.69/81.1
校准: quadrants 配置化为 ["Q1","Q3"], min_score=82, RR 门槛保持 2.0(护栏)。
"""
from dataclasses import replace

from src.signals.entry_chain_config import EntryChainConfig
from scripts.run_live_dry_run import _high_score_long_offset_probe_eligible

CONFIG = replace(
    EntryChainConfig(),
    scout_micro_targeted_long_symbols=["BCHUSDT", "SOLUSDT"],
    scout_micro_high_score_long_offset_min_score=82.0,
    scout_micro_high_score_long_offset_min_pa_score=18.0,
    scout_micro_high_score_long_offset_min_fib_score=15.0,
    scout_micro_high_score_long_offset_min_cvd_score=14.0,
    scout_micro_high_score_long_offset_min_rr_score=2.0,
    scout_micro_high_score_long_offset_quadrants=("Q1", "Q3"),
)


def _q3_long_near_miss(score=87.3, rr=2.5, **overrides):
    """构造 Q3(trend 轴不过 + momentum 轴过)+ LONG + SIDE阈值原因 的 near-miss。"""
    nm = {
        "symbol": "BCHUSDT",
        "intended_side": "LONG",
        "entry_price": 200.0,
        "score": score,
        "component_points": {
            "trend_ema_context": 10.0,   # <15 → trend 轴不过
            "price_action_structure": 21.0,  # >=18 probe 要求
            "flow_cvd_confirmation": 18.0,
            "cci_momentum_quality": 8.0,
            "fibonacci_location": 18.0,
            "risk_reward_geometry": rr,
        },
        "reasons": ["FIB_PA_ARCHITECTURE_WEIGHTS", "SIDE_THRESHOLD_OFFSET_LONG_10.00"],
        "scout_tags": [],
    }
    nm.update(overrides)
    return nm


def test_q3_long_high_score_eligible_after_calibration():
    # 校准核心: Q3 的 LONG 高分样本(SIDE阈值原因)应可触发
    assert _high_score_long_offset_probe_eligible("BCHUSDT", _q3_long_near_miss(), CONFIG) is True


def test_symbol_not_targeted_rejected():
    nm = _q3_long_near_miss(symbol="DOGEUSDT")
    assert _high_score_long_offset_probe_eligible("DOGEUSDT", nm, CONFIG) is False


def test_rr_below_guardrail_rejected():
    # RR 门槛 2.0 护栏保持: 位置差样本不放行
    nm = _q3_long_near_miss(rr=0.5)
    assert _high_score_long_offset_probe_eligible("BCHUSDT", nm, CONFIG) is False


def test_score_below_min_rejected():
    nm = _q3_long_near_miss(score=80.0)
    assert _high_score_long_offset_probe_eligible("BCHUSDT", nm, CONFIG) is False


def test_q4_rejected():
    # Q4(两轴均不过)不在 quadrants 列表
    nm = _q3_long_near_miss(
        component_points={
            "trend_ema_context": 10.0,
            "price_action_structure": 21.0,
            "flow_cvd_confirmation": 5.0,   # <14 → momentum 轴不过 → Q4
            "cci_momentum_quality": 3.0,
            "fibonacci_location": 18.0,
            "risk_reward_geometry": 2.5,
        }
    )
    assert _high_score_long_offset_probe_eligible("BCHUSDT", nm, CONFIG) is False


def test_missing_side_reason_rejected():
    nm = _q3_long_near_miss(reasons=["FIB_PA_ARCHITECTURE_WEIGHTS"])
    assert _high_score_long_offset_probe_eligible("BCHUSDT", nm, CONFIG) is False
