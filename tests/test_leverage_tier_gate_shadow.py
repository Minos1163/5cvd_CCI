# -*- coding: utf-8 -*-
"""4x 杠杆质量门控逻辑单测(08-31 评审 5.2)。

锁定 shadow 脚本的 gate 判定:4x 档要求 fib≥10 / pa≥7 / rr≥5。
三笔大额亏损(BCH/DOGE/SOL)MFE 0.36-0.75R,RR 几何质量差——
评审 5.2 指出这正是 4x 档被忽视的缺口。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.leverage_tier_gate_shadow import GATE_4X, gate_pass  # noqa: E402


def test_gate_spec_matches_review():
    assert GATE_4X == {"fibonacci_location": 10.0, "price_action_structure": 7.0, "risk_reward_geometry": 5.0}


def test_gate_pass_when_all_components_meet():
    assert gate_pass({"fibonacci_location": 18.0, "price_action_structure": 21.0, "risk_reward_geometry": 5.0}, GATE_4X)


def test_gate_fails_on_low_rr():
    # 三笔大额亏损的典型画像:RR 几何低
    assert not gate_pass({"fibonacci_location": 18.0, "price_action_structure": 21.0, "risk_reward_geometry": 2.0}, GATE_4X)


def test_gate_fails_on_low_fib_or_pa():
    assert not gate_pass({"fibonacci_location": 9.0, "price_action_structure": 21.0, "risk_reward_geometry": 6.0}, GATE_4X)
    assert not gate_pass({"fibonacci_location": 18.0, "price_action_structure": 6.0, "risk_reward_geometry": 6.0}, GATE_4X)


def test_missing_components_treated_as_zero():
    assert not gate_pass({}, GATE_4X)
