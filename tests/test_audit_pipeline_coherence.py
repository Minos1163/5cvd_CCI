# -*- coding: utf-8 -*-
"""audit_pipeline_coherence 单测(08-11 报告 3.2 规格)。

覆盖:象限特定 BLOCKING(Q2 70<82)、非象限特定 WARNING(REVERSAL 70<82)、
门槛达标 OK、coherent 汇总判定、主配置全量输出。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.signals.entry_chain_config import EntryChainConfig  # noqa: E402

from scripts.audit_pipeline_coherence import (  # noqa: E402
    audit_pipeline_coherence,
    load_entry_chain_config,
)


def _cfg(**overrides) -> EntryChainConfig:
    return EntryChainConfig(**overrides)


def test_q2_pending_blocking():
    cfg = _cfg(scout_micro_q2_pending_min_score=70.0)
    res = audit_pipeline_coherence(cfg, near_miss_min_score=82.0)
    q2 = next(i for i in res["issues"] if i["mission"] == "Q2_PENDING_MOMENTUM")
    assert q2["severity"] == "BLOCKING"
    assert q2["mission_min_score"] == 70.0
    assert "永久截断" in q2["explanation"]
    assert res["coherent"] is False


def test_q3_confirmation_not_truncated():
    # Q3→Q1 门槛 85 >= 82:不受上游截断(08-11 报告 3.3:创建条件≥全局阈值,可能不受影响)
    cfg = _cfg(scout_micro_q3_to_q1_min_score=85.0)
    res = audit_pipeline_coherence(cfg, near_miss_min_score=82.0)
    q3 = next(i for i in res["issues"] if i["mission"] == "Q3_TO_Q1_CONFIRMATION")
    assert q3["severity"] == "OK"


def test_reversal_pivot_warning_not_blocking():
    cfg = _cfg(scout_micro_reversal_pivot_min_score=70.0)
    res = audit_pipeline_coherence(cfg, near_miss_min_score=82.0)
    rv = next(i for i in res["issues"] if i["mission"] == "REVERSAL_PIVOT_SCOUT")
    assert rv["severity"] == "WARNING"
    assert "门槛冗余" in rv["explanation"]


def test_ok_when_threshold_at_or_above():
    cfg = _cfg(scout_micro_high_score_long_offset_min_score=82.0)
    res = audit_pipeline_coherence(cfg, near_miss_min_score=82.0)
    item = next(i for i in res["issues"] if i["mission"] == "HIGH_SCORE_LONG_OFFSET_PROBE")
    assert item["severity"] == "OK"
    assert res["coherent"] is False  # 仍有 Q2/Q3 BLOCKING


def test_all_ok_config():
    cfg = _cfg(
        scout_micro_q2_pending_min_score=82.0,
        scout_micro_q3_to_q1_min_score=82.0,
        scout_micro_reversal_pivot_min_score=82.0,
    )
    res = audit_pipeline_coherence(cfg, near_miss_min_score=82.0)
    assert res["coherent"] is True
    assert all(i["severity"] in {"OK", "WARNING"} for i in res["issues"])


def test_main_config_full_output():
    cfg = load_entry_chain_config("configs/entry_chain.dry_run_fib_pa_v1.json")
    res = audit_pipeline_coherence(cfg, 82.0)
    missions = {i["mission"] for i in res["issues"]}
    assert missions == {
        "REVERSAL_PIVOT_SCOUT", "Q2_PENDING_MOMENTUM", "Q3_TO_Q1_CONFIRMATION",
        "Q1_RR_GAP_SCOUT", "HIGH_SCORE_LONG_OFFSET_PROBE", "FIB_CONTINUATION_SCOUT",
        "WATCH_ONLY_SYMBOL_PROMOTION_TEST", "SCOUT_ONLY_HIGH_SCORE",
    }
    blocking = [i for i in res["issues"] if i["severity"] == "BLOCKING"]
    assert {i["mission"] for i in blocking} == {"Q2_PENDING_MOMENTUM"}
