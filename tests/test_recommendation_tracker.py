# -*- coding: utf-8 -*-
"""recommendation_tracker.py 的单元测试。"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from recommendation_tracker import (  # noqa: E402
    Recommendation,
    check_blocking,
    parse_tracking_table,
)

SAMPLE_TABLE = """\
| 建议ID | 报告日期 | 优先级 | 内容摘要 | 目标代码位置 | 实施状态 | 验证结果 |
|---|---|---|---|---|---|---|
| A | 2026-08-02 | P0 | 移除标签 | run_live_dry_run.py:888 | PENDING | 无 |
| B | 2026-08-02 | P0 | 阈值校准 | config.json | VERIFIED | 通过 |
| C | 2026-08-04 | P1 | SCOUT 多样化 | run_live_dry_run.py:1071 | IN_PROGRESS | 诊断中 |
"""


def test_parse_tracking_table():
    recs = parse_tracking_table(SAMPLE_TABLE)
    assert len(recs) == 3
    assert recs[0].id == "A"
    assert recs[0].status == "PENDING"
    assert recs[0].priority == "P0"


def test_parse_ignores_header_and_separator():
    recs = parse_tracking_table("| 建议ID | x |\n|---|---|\n| A | y |")
    assert len(recs) == 0  # 表头被跳过; 少列行被跳过


def test_check_blocking_only_p0_unresolved():
    recs = [
        Recommendation(id="A", report_date="d", priority="P0", description="x", target="t", status="PENDING"),
        Recommendation(id="B", report_date="d", priority="P0", description="x", target="t", status="VERIFIED"),
        Recommendation(id="C", report_date="d", priority="P0", description="x", target="t", status="ABANDONED"),
        Recommendation(id="D", report_date="d", priority="P1", description="x", target="t", status="PENDING"),
    ]
    blocking = check_blocking(recs)
    assert [r.id for r in blocking] == ["A"]


def test_is_resolved():
    assert Recommendation(id="x", report_date="d", priority="P0", description="d", target="t", status="DEPLOYED").is_resolved
    assert not Recommendation(id="x", report_date="d", priority="P0", description="d", target="t", status="PENDING").is_resolved
