"""账本标识守卫（P0 A6，2026-11-14 评审 §14）。

问题：五本账（main / ab_legacy / ab_trend_capture / ab_pure_ladder / scout_micro）
共用同一套 PAPER_* 事件 schema，合并分析时只能靠**目录名**区分。一旦文件被拷出目录
（VPS 汇总到本地、发给外部评审），某行属于哪本账就无从判断了。

做法：`PaperTradingLedger(..., ledger_id=...)`，在唯一写入口 `_append_trade_event`
里给每条事件补 `ledger_id`。**纯新增字段**，读取侧不依赖，也不参与任何盈亏计算。

本文件锁三件事：
1. 默认账本 id 是 `"main"`（不传参的老代码行为不变）；
2. OPEN / REDUCE / CLOSE 三类事件都带 `ledger_id`（不是只有 OPEN 带）；
3. 各账本的 id 与 `build_paper_exit_ab_ledgers` / scout_micro 的约定一致。
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.run_live_dry_run import build_paper_exit_ab_ledgers
from src.observability.paper_trading import PaperTradingLedger
from src.signals.entry_chain_config import EntryChainConfig


def _decision(action: str = "DIRECT") -> dict:
    return {
        "action": action,
        "side": "LONG",
        "score": 88,
        "leverage": 3,
        "entry_context": {"atr_pct": 0.01},
        "reasons": ["TEST_DIRECT"],
    }


def _draft() -> dict:
    return {"approved": True, "request": {"position_side": "LONG", "quantity": 10, "price": 100}}


def _events(output_dir: Path) -> list[dict]:
    path = output_dir / "paper_trades.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_default_ledger_id_is_main(tmp_path):
    """不传 ledger_id 的老调用点行为不变（默认 main）。"""
    ledger = PaperTradingLedger(tmp_path)
    assert ledger.ledger_id == "main"


def test_paper_open_event_carries_ledger_id(tmp_path):
    ledger = PaperTradingLedger(tmp_path, ledger_id="scout_micro")
    ledger.on_decision(
        symbol="SOLUSDT",
        decision_payload=_decision(),
        draft_payload=_draft(),
        kline={"close": 100, "high": 100, "low": 100},
        timestamp=1000,
    )

    rows = _events(tmp_path)
    assert [row["event"] for row in rows] == ["PAPER_OPEN"]
    assert rows[0]["ledger_id"] == "scout_micro"


def test_paper_close_event_carries_ledger_id(tmp_path):
    ledger = PaperTradingLedger(tmp_path, ledger_id="ab_legacy")
    ledger.on_decision(
        symbol="SOLUSDT",
        decision_payload=_decision(),
        draft_payload=_draft(),
        kline={"close": 100, "high": 100, "low": 100},
        timestamp=1000,
    )
    ledger.on_decision(
        symbol="SOLUSDT",
        decision_payload={"action": "NO_TRADE"},
        draft_payload={"approved": False},
        kline={"close": 100, "high": 103, "low": 98},
        timestamp=1900,
    )

    rows = _events(tmp_path)
    assert [row["event"] for row in rows] == ["PAPER_OPEN", "PAPER_CLOSE"]
    assert {row["ledger_id"] for row in rows} == {"ab_legacy"}


def test_paper_reduce_and_close_share_the_same_ledger_id(tmp_path):
    """TP1 触发 REDUCE、随后止损触发 CLOSE —— 两类事件都要带同一个 id。"""
    ledger = PaperTradingLedger(tmp_path, ledger_id="ab_trend_capture")
    ledger.on_decision(
        symbol="SOLUSDT",
        decision_payload=_decision(),
        draft_payload=_draft(),
        kline={"close": 100, "high": 100, "low": 100},
        timestamp=1000,
    )
    ledger.on_decision(
        symbol="SOLUSDT",
        decision_payload={"action": "NO_TRADE"},
        draft_payload={"approved": False},
        kline={"close": 102, "high": 102.2, "low": 99.9},
        timestamp=1900,
    )
    ledger.on_decision(
        symbol="SOLUSDT",
        decision_payload={"action": "NO_TRADE"},
        draft_payload={"approved": False},
        kline={"close": 98, "high": 99, "low": 97},
        timestamp=2800,
    )

    rows = _events(tmp_path)
    kinds = [row["event"] for row in rows]
    assert "PAPER_REDUCE" in kinds, f"本用例需要先触发减仓，实际事件={kinds}"
    assert kinds[-1] == "PAPER_CLOSE"
    assert {row["ledger_id"] for row in rows} == {"ab_trend_capture"}


def test_ab_ledgers_use_declared_ledger_ids(tmp_path):
    """AB 三臂的 id 约定：ab_legacy / ab_trend_capture / ab_pure_ladder。"""
    config = EntryChainConfig(paper_ab_pure_ladder_enabled=True)
    ledgers = build_paper_exit_ab_ledgers(tmp_path, tmp_path, config)

    assert {key: ledger.ledger_id for key, ledger in ledgers.items()} == {
        "legacy": "ab_legacy",
        "trend_capture": "ab_trend_capture",
        "pure_ladder": "ab_pure_ladder",
    }


def test_ab_ledgers_without_pure_ladder_still_have_ids(tmp_path):
    config = EntryChainConfig(paper_ab_pure_ladder_enabled=False)
    ledgers = build_paper_exit_ab_ledgers(tmp_path, tmp_path, config)

    assert set(ledgers) == {"legacy", "trend_capture"}
    assert ledgers["legacy"].ledger_id == "ab_legacy"
    assert ledgers["trend_capture"].ledger_id == "ab_trend_capture"


def test_ledger_id_does_not_change_pnl_fields(tmp_path):
    """纯新增字段：事件里的盈亏口径一个都不许变。"""
    ledger = PaperTradingLedger(tmp_path, ledger_id="main")
    ledger.on_decision(
        symbol="SOLUSDT",
        decision_payload=_decision(),
        draft_payload=_draft(),
        kline={"close": 100, "high": 100, "low": 100},
        timestamp=1000,
    )
    row = _events(tmp_path)[0]

    for key in ("notional_pnl", "margin_pnl", "pnl_accounting_mode", "notional", "leverage", "score"):
        assert key in row, key
    assert row["pnl_accounting_mode"] == "notional_primary_margin_reporting"
    assert row["ledger_id"] == "main"
