"""账本度量的口径测试。

这些用例锁的是**口径**，不是数值巧合：
- full-cost 与 close-only 的差必须等于建仓成本；
- 集中度两个分母必须给出不同且各自正确的数；
- 块 bootstrap 必须按 symbol|utc_date 分块且可复现；
- 样本不足必须判 INCONCLUSIVE，不允许用点估计冒充结论。
"""

from __future__ import annotations

import math

import pytest

from src.reporting import ledger_metrics as lm


def _open(pid: str, symbol: str, ts: int, *, fee: float, slip: float, notional: float = 1000.0) -> dict:
    return {
        "event": "PAPER_OPEN",
        "position_id": pid,
        "symbol": symbol,
        "side": "LONG",
        "timestamp": ts,
        "price": 1.0,
        "quantity": notional,
        "notional": notional,
        "leverage": 3,
        "stop_pct": 0.01,
        "fee": fee,
        "slippage": slip,
        "score": 80.0,
        "entry_channel": "main_probe",
        "source_quadrant": "Q1",
        "exit_mode": "legacy",
    }


def _close(pid: str, symbol: str, ts: int, *, net: float, reason: str = "TP2_HIT", fee: float = 0.1, slip: float = 0.1) -> dict:
    return {
        "event": "PAPER_CLOSE",
        "position_id": pid,
        "symbol": symbol,
        "timestamp": ts,
        "net_pnl": net,
        "gross_pnl": net + fee + slip,
        "fee": fee,
        "slippage": slip,
        "reason": reason,
    }


@pytest.fixture()
def three_positions() -> list[dict]:
    """3 笔：+30 / +10 / -5，建仓成本各 0.4，出场成本各 0.2。"""
    return [
        _open("A:1:LONG", "A", 1_000_000, fee=0.2, slip=0.2),
        _close("A:1:LONG", "A", 1_000_900, net=30.0),
        _open("B:2:LONG", "B", 1_000_100, fee=0.2, slip=0.2),
        _close("B:2:LONG", "B", 1_001_800, net=10.0, reason="TP1_HIT"),
        _open("C:3:LONG", "C", 1_000_200, fee=0.2, slip=0.2),
        _close("C:3:LONG", "C", 1_002_700, net=-5.0, reason="INITIAL_STOP_HIT"),
    ]


def test_rebuild_full_cost_equals_close_only_minus_entry(three_positions):
    records = lm.rebuild_positions(three_positions, ledger="main")
    assert len(records) == 3
    for r in records:
        assert r.net_full == pytest.approx(r.net_close_only - 0.4)
        assert r.total_cost == pytest.approx(0.6)


def test_summary_reports_both_bases(three_positions):
    records = lm.rebuild_positions(three_positions, ledger="main")
    s = lm.summary_metrics(records)
    assert s["net_close_only"] == pytest.approx(35.0)
    assert s["net_pnl_full"] == pytest.approx(35.0 - 1.2)
    assert s["full_minus_close_only"] == pytest.approx(-1.2)
    assert s["trade_count"] == 3
    assert s["wins"] == 2 and s["losses"] == 1
    assert s["win_rate"] == pytest.approx(2 / 3)


def test_concentration_uses_two_denominators(three_positions):
    records = lm.rebuild_positions(three_positions, ledger="main")
    c = lm.concentration_metrics(records)
    net = 33.8
    gross_profit = 29.6 + 9.6
    assert c["net_pnl_full"] == pytest.approx(net)
    assert c["top1_share_of_gross_profit"] == pytest.approx(29.6 / gross_profit)
    assert c["top1_share_of_net"] == pytest.approx(29.6 / net)
    # 两个分母必须不同，否则说明实现退化成一个
    assert c["top1_share_of_gross_profit"] != c["top1_share_of_net"]
    assert c["ex_top1_net_pnl"] == pytest.approx(net - 29.6)
    assert c["top_contributors"][0]["symbol"] == "A"


def test_hhi_equals_uniform_when_all_equal():
    events = []
    for i in range(4):
        events.append(_open(f"X:{i}:LONG", "X", 1_000_000 + i, fee=0.0, slip=0.0))
        events.append(_close(f"X:{i}:LONG", "X", 1_000_900 + i, net=5.0, fee=0.0, slip=0.0))
    records = lm.rebuild_positions(events, ledger="main")
    c = lm.concentration_metrics(records)
    assert c["hhi_abs"] == pytest.approx(0.25)
    assert c["hhi_uniform_benchmark"] == pytest.approx(0.25)


def test_wilson_interval_known_value():
    # 3/11 的 Wilson 95% 下界应在 0.09 附近，上界 0.57 附近
    lo, hi = lm.wilson_interval(3, 11)
    assert 0.09 < lo < 0.11
    assert 0.55 < hi < 0.58
    assert lm.wilson_interval(0, 0) is None


def test_block_bootstrap_is_deterministic_and_blocked():
    events = []
    for i in range(6):
        sym = f"S{i % 2}"
        events.append(_open(f"{sym}:{i}:LONG", sym, 1_700_000_000 + i * 900, fee=0.1, slip=0.1))
        events.append(_close(f"{sym}:{i}:LONG", sym, 1_700_000_900 + i * 900, net=(10.0 if i % 2 else -3.0)))
    records = lm.rebuild_positions(events, ledger="main")

    first = lm.block_bootstrap_ci(records, stat="expectancy", n_boot=500, seed=7)
    second = lm.block_bootstrap_ci(records, stat="expectancy", n_boot=500, seed=7)
    assert first == second, "同 seed 必须可复现"
    assert first["blocks"] == len({r.block_key for r in records})
    assert first["ci_low"] <= first["point"] <= first["ci_high"]


def test_block_metrics_counts_blocks_not_rows():
    events = []
    # 同 symbol 同 UTC 日 3 笔 → 1 个块
    for i in range(3):
        events.append(_open(f"Z:{i}:LONG", "Z", 1_700_000_000 + i * 900, fee=0.1, slip=0.1))
        events.append(_close(f"Z:{i}:LONG", "Z", 1_700_000_800 + i * 900, net=1.0))
    records = lm.rebuild_positions(events, ledger="main")
    m = lm.block_metrics(records)
    assert m["n_nominal"] == 3
    assert m["n_effective_blocks"] == 1
    assert m["max_positions_in_one_block"] == 3


def test_verdict_is_inconclusive_without_sample(three_positions):
    records = lm.rebuild_positions(three_positions, ledger="main")
    v = lm.decide_verdict(records, min_effective_blocks=30)
    assert v["sample_verdict"] == "INCONCLUSIVE"
    assert any("effective blocks" in r for r in v["reasons"])


def test_verdict_flags_one_sided_sample():
    events = []
    for i in range(40):
        events.append(_open(f"W:{i}:LONG", f"W{i}", 1_700_000_000 + i * 900, fee=0.0, slip=0.0))
        events.append(_close(f"W:{i}:LONG", f"W{i}", 1_700_000_800 + i * 900, net=1.0, fee=0.0, slip=0.0))
    records = lm.rebuild_positions(events, ledger="main")
    v = lm.decide_verdict(records, min_effective_blocks=30)
    assert v["sample_verdict"] == "INCONCLUSIVE"
    assert any("no losing trades" in r for r in v["reasons"])


def test_select_window_filters_by_entry_not_exit():
    events = [
        _open("OLD:1:LONG", "OLD", 1_000_000, fee=0.1, slip=0.1),
        _close("OLD:1:LONG", "OLD", 2_000_000, net=5.0),  # 建仓在窗口外，平仓在窗口内
    ]
    records = lm.rebuild_positions(events, ledger="main")
    window = lm.select_window(records, since_ts=1_500_000, closed_only=True)
    assert window == [], "按建仓时间筛选时，窗口外建仓的仓位不应计入"


def test_cost_metrics_split_entry_exit(three_positions):
    records = lm.rebuild_positions(three_positions, ledger="main")
    c = lm.cost_metrics(records)
    assert c["entry_fee"] == pytest.approx(0.6)
    assert c["entry_slippage"] == pytest.approx(0.6)
    assert c["exit_fee"] == pytest.approx(0.3)
    assert c["exit_slippage"] == pytest.approx(0.3)
    assert c["total_cost"] == pytest.approx(1.8)
    assert "funding" in c["note"]


def test_build_report_and_markdown_contract(three_positions):
    records = lm.rebuild_positions(three_positions, ledger="main")
    report = lm.build_report(records, ledger="main", window={"since": None, "until": None})
    for key in ("summary", "concentration", "cost", "sample", "verdict", "bootstrap", "by_side", "by_symbol", "trades"):
        assert key in report
    assert report["authoritative_field"] == "net_pnl_full"
    md = lm.render_markdown(report)
    for section in ("## 1. 汇总", "## 2. 集中度", "## 3. 成本", "## 4. 样本与不确定性", "## 5. 分组"):
        assert section in md
    assert "close-only" in md


def test_empty_positions_do_not_crash():
    report = lm.build_report([], ledger="main", window={})
    assert report["summary"]["trade_count"] == 0
    assert report["verdict"]["sample_verdict"] == "INCONCLUSIVE"
    assert math.isfinite(report["summary"]["net_pnl_full"])


def test_cost_stress_extra_cost_math():
    # 单笔 notional=1000，滑点 +50% → 额外 1000×5bps×0.5×2(进出) = 0.5
    events = [
        _open("S:1:LONG", "S", 1_700_000_000, fee=0.5, slip=0.5, notional=1000.0),
        _close("S:1:LONG", "S", 1_700_000_900, net=10.0),
    ]
    records = lm.rebuild_positions(events, ledger="main")
    stress = lm.cost_stress_metrics(records)
    by_name = {s["scenario"]: s for s in stress["scenarios"]}
    assert by_name["slippage_+50%"]["extra_cost"] == pytest.approx(0.5)
    assert by_name["fee_+25%"]["extra_cost"] == pytest.approx(0.25)
    assert by_name["combined_+50%"]["extra_cost"] == pytest.approx(1.0)
    assert by_name["slippage_+50%"]["net_pnl_full"] == pytest.approx(10.0 - 1.0 - 0.5)


def test_cost_stress_reports_ex_top1_separately(three_positions):
    records = lm.rebuild_positions(three_positions, ledger="main")
    stress = lm.cost_stress_metrics(records)
    assert stress["cost_inflation_to_breakeven"] is not None
    ex = stress["excluding_top1"]
    assert ex is not None
    # 剔除最大赢家后净额应等于 summary 的 ex_top1
    c = lm.concentration_metrics(records)
    assert ex["base_net_pnl_full"] == pytest.approx(c["ex_top1_net_pnl"])
    # 剔除后安全边际必须更薄（否则说明没真的剔除）
    assert ex["cost_inflation_to_breakeven"] < stress["cost_inflation_to_breakeven"]


def test_cost_stress_single_trade_has_no_ex_block():
    events = [
        _open("ONE:1:LONG", "ONE", 1_700_000_000, fee=0.1, slip=0.1),
        _close("ONE:1:LONG", "ONE", 1_700_000_900, net=1.0),
    ]
    records = lm.rebuild_positions(events, ledger="main")
    assert lm.cost_stress_metrics(records)["excluding_top1"] is None
