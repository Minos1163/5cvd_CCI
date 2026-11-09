"""10-31 → 11-08 主账本对账口径的**特征化测试**（characterization test）。

它描述的是"当前已发生的事实"，按定义**首次运行就应当通过**。若首次就红，
说明基线事实与 `docs/analysis/2026-10-31_to_11-08_loss_attribution.md` 不符，
此时应停下来核查，而不是改测试迁就代码。

锁定三件事：
1. 权威口径是 `net_pnl_full`（含建仓成本摊分），合计 33.762404；
2. 头寸数是 11，按 `position_id` 聚合，不按事件行数；
3. 两种常见错误做法（跨天累加 `paper_summary.json`、拿 `net_pnl` 当权威）必须被显式否证。
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MAIN_LEDGER_DIRS = [
    ROOT / "logs" / "2026-10" / "2026-10-31",
    *(ROOT / "logs" / "2026-11" / f"2026-11-{day:02d}" for day in range(1, 9)),
]
SUMMARY_PATH = ROOT / "logs" / "2026-11" / "2026-11-08" / "paper_summary.json"
EXIT_EVENTS = {"PAPER_REDUCE", "PAPER_CLOSE"}
EXPECTED_TOTAL_NET_PNL_FULL = 33.762404
EXPECTED_POSITIONS = 11

# 关键：logs/ 在 .gitignore，`git ls-files logs` 为 0 条。
# 干净 clone / CI 上没有账本数据，此时必须**整文件 skip**（记 INCONCLUSIVE），
# 而不是红——否则本 Task 在换机后永远无法通过。
pytestmark = pytest.mark.skipif(
    not SUMMARY_PATH.exists(),
    reason="需要本机 10-31→11-08 账本数据；缺失记 INCONCLUSIVE，不等于 PASS",
)


def _iter_events() -> list[dict]:
    events: list[dict] = []
    for directory in MAIN_LEDGER_DIRS:
        path = directory / "paper_trades.jsonl"
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events


def _position_totals() -> dict[str, float]:
    totals: dict[str, float] = defaultdict(float)
    for event in _iter_events():
        if event.get("event") in EXIT_EVENTS:
            totals[event["position_id"]] += float(event["net_pnl_full"])
    return dict(totals)


def test_position_count_matches_summary():
    totals = _position_totals()
    assert len(totals) == EXPECTED_POSITIONS


def test_total_net_pnl_full_matches_summary():
    totals = _position_totals()
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    assert sum(totals.values()) == pytest.approx(EXPECTED_TOTAL_NET_PNL_FULL, abs=1e-6)
    assert sum(totals.values()) == pytest.approx(
        float(summary["realized_notional_pnl"]), abs=1e-9
    )


def test_net_pnl_is_not_used_as_authoritative():
    totals: dict[str, float] = defaultdict(float)
    for event in _iter_events():
        if event.get("event") in EXIT_EVENTS:
            totals[event["position_id"]] += float(event["net_pnl"])
    assert sum(totals.values()) != pytest.approx(EXPECTED_TOTAL_NET_PNL_FULL, abs=1e-3)


def test_cross_day_summation_would_be_wrong():
    daily: list[float] = []
    for directory in MAIN_LEDGER_DIRS:
        path = directory / "paper_summary.json"
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            daily.append(float(payload["realized_notional_pnl"]))
    assert len(daily) > 1
    assert sum(daily) != pytest.approx(EXPECTED_TOTAL_NET_PNL_FULL, abs=1e-6)


def test_deprecated_margin_field_is_not_the_authority():
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    margin = summary.get("realized_margin_pnl")
    if margin is None:
        pytest.skip("summary 未提供 realized_margin_pnl")
    assert float(margin) > EXPECTED_TOTAL_NET_PNL_FULL * 2


def test_top1_concentration_is_recorded():
    """盈利集中度必须作为**事实**被锁住，而不是留给人肉记忆。

    2026-10-31→11-08:NEARUSDT 单笔占 97.59%,剔 top1 后仅 +0.813862。
    这条断言不是为了判"策略好坏"（那是 P1-E1），而是防止口径漂移后
    "单笔占 97.59%" 这个前提被静默改写。
    """
    totals = _position_totals()
    ordered = sorted(totals.values(), reverse=True)
    top1 = ordered[0]
    total = sum(totals.values())
    assert top1 == pytest.approx(32.948542, abs=1e-6)
    assert top1 / total == pytest.approx(0.9759, abs=5e-4)
    assert total - top1 == pytest.approx(0.813862, abs=1e-6)
