"""硬闸门机制化控制样本(阴性 + 阳性),对应 scripts/audit_entry_gate_controls.py。

目的:把「闸门从未触发」和「闸门正常工作」区分开。生产日志里两者完全同形,
只有构造一条只触发该闸门的上下文,才能证明它真的会拒绝。
"""

from __future__ import annotations

import pytest

from scripts.audit_entry_gate_controls import (
    build_baseline_context,
    effective_thresholds,
    gate_cases,
    run_gate_controls,
)
from src.signals.entry_chain_config import load_entry_chain_config

FIB_PA_CONFIG = "configs/entry_chain.dry_run_fib_pa_v1.json"


@pytest.fixture(scope="module")
def cfg():
    return load_entry_chain_config(FIB_PA_CONFIG)


def test_all_fifteen_gates_reject_with_expected_reason(cfg) -> None:
    report = run_gate_controls(cfg)
    failures = [row for row in report["gates"] if not row["ok"]]
    assert failures == [], f"闸门控制失败: {failures}"
    assert len(report["gates"]) == 15
    assert report["failed"] == 0


def test_each_gate_is_isolated(cfg) -> None:
    """每条样本只触发目标闸门——若基线本身就会命中,测到的其实是更早的闸门。"""
    baseline = build_baseline_context()
    for case in gate_cases(cfg):
        ctx = build_baseline_context(**case.updates)
        assert ctx.symbol == baseline.symbol or case.gate in {"blacklist", "watch_only"}
        assert case.expected  # 每个样本必须声明期望 reason


def test_positive_control_can_open_a_position(cfg) -> None:
    """干净上下文必须能产出入场动作;否则门槛在结构上不可达,所有"严格"都是空的。"""
    positive = run_gate_controls(cfg)["positive_control"]
    assert positive["hard_block_reason"] is None
    assert positive["action"] == "DIRECT"
    assert positive["leverage"] > 0
    assert positive["notional_hint"] > 0


def test_effective_thresholds_replace_not_add(cfg) -> None:
    """LONG 的两层偏移是替换:probe 用 7.0 覆盖 side 的 10.0,不是 17.0。"""
    long_thresholds = effective_thresholds(cfg, "LONG")
    short_thresholds = effective_thresholds(cfg, "SHORT")
    assert long_thresholds == {"direct": 92.0, "probe": 77.0, "watch": 72.0}
    assert short_thresholds == {"direct": 82.0, "probe": 70.0, "watch": 62.0}


def test_thresholds_follow_config_offsets() -> None:
    cfg = load_entry_chain_config("configs/entry_chain.dry_run_highest_win.json")
    long_thresholds = effective_thresholds(cfg, "LONG")
    # highest_win 没有 probe_conditions,probe 偏移回退为 side offset(10.0)
    assert long_thresholds == {"direct": 92.0, "probe": 80.0, "watch": 70.0}
