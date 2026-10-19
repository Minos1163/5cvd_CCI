"""纸面账本事件字段:配对键(position_id)与成本口径(fee_bps/slippage_bps/cost_source)。

本文件只验证「字段补齐」这一纯增量改动,覆盖三件事:
1. OPEN / REDUCE / CLOSE 三类事件都带齐配对与成本口径字段,且彼此一致;
2. 补齐字段不改变任何 PnL 计算(断言硬编码的改动前基准数值);
3. 旧账本(缺新字段的事件行 / 仓位快照)仍可被读取与汇总,不抛异常。
"""

import json

import pytest

from src.observability.paper_trading import FEE_BPS, SLIPPAGE_BPS, PaperTradingLedger


def approved_decision() -> tuple[dict, dict]:
    decision = {
        "action": "DIRECT",
        "side": "LONG",
        "score": 88,
        "leverage": 3,
        "entry_context": {"atr_pct": 0.01},
        "reasons": ["TEST_DIRECT"],
    }
    draft = {
        "approved": True,
        "request": {
            "position_side": "LONG",
            "quantity": 10,
            "price": 100,
        },
    }
    return decision, draft


def replay_open_tp1_close(ledger: PaperTradingLedger) -> list[dict]:
    """开仓(100) → TP1 减仓(101.8) → 保本止损全平(100.1),返回事件行。"""
    decision, draft = approved_decision()
    ledger.on_decision(
        symbol="SOLUSDT",
        decision_payload=decision,
        draft_payload=draft,
        kline={"close": 100, "high": 100, "low": 100},
        timestamp=1000,
    )
    ledger.on_decision(
        symbol="SOLUSDT",
        decision_payload={"action": "NO_TRADE"},
        draft_payload={"approved": False},
        kline={"close": 101.8, "high": 101.8, "low": 100.5},
        timestamp=1900,
    )
    ledger.on_decision(
        symbol="SOLUSDT",
        decision_payload={"action": "NO_TRADE"},
        draft_payload={"approved": False},
        kline={"close": 100.0, "high": 100.2, "low": 99.9},
        timestamp=2800,
    )
    return ledger.trade_events()


def read_rows(tmp_path) -> list[dict]:
    return [
        json.loads(line)
        for line in (tmp_path / "paper_trades.jsonl").read_text(encoding="utf-8").splitlines()
    ]


OPEN_FIELDS = ("position_id", "entry_price", "entry_time", "fee_bps", "slippage_bps", "cost_source")


def test_open_event_carries_pairing_and_cost_fields(tmp_path):
    ledger = PaperTradingLedger(tmp_path)
    replay_open_tp1_close(ledger)

    opened = next(row for row in read_rows(tmp_path) if row["event"] == "PAPER_OPEN")

    for key in OPEN_FIELDS:
        assert key in opened, f"PAPER_OPEN 缺少字段 {key}"

    assert opened["position_id"] == "SOLUSDT:1000:LONG"
    assert opened["entry_price"] == 100.0
    assert opened["entry_time"] == 1000
    assert opened["fee_bps"] == 5.0
    assert opened["slippage_bps"] == 5.0
    assert opened["cost_source"] == "constant_assumption"
    # 成本金额仍按常量假设计算: 1000 notional × 5bps
    assert opened["fee"] == 0.5
    assert opened["slippage"] == 0.5


def test_reduce_and_close_events_pair_with_open_and_carry_cost_fields(tmp_path):
    ledger = PaperTradingLedger(tmp_path)
    rows = replay_open_tp1_close(ledger)

    opened = next(row for row in rows if row["event"] == "PAPER_OPEN")
    reduced = next(row for row in rows if row["event"] == "PAPER_REDUCE")
    closed = next(row for row in rows if row["event"] == "PAPER_CLOSE")

    assert reduced["reason"] == "TP1_HIT"
    assert closed["reason"] == "BREAKEVEN_STOP_HIT"

    for row in (reduced, closed):
        for key in OPEN_FIELDS + ("notional", "notional_fraction", "exit_notional"):
            assert key in row, f"{row['event']} 缺少字段 {key}"
        assert row["position_id"] == opened["position_id"]
        assert row["entry_price"] == opened["entry_price"] == 100.0
        assert row["entry_time"] == opened["entry_time"] == 1000
        assert row["notional"] == 1000.0
        assert row["exit_notional"] == abs(row["quantity"] * row["price"])
        assert row["notional_fraction"] == pytest.approx(1000.0 * row["fraction"])
        assert row["fee_bps"] == 5.0
        assert row["slippage_bps"] == 5.0
        assert row["cost_source"] == "constant_assumption"

    assert reduced["fraction"] == 0.4
    assert reduced["exit_notional"] == pytest.approx(407.2)
    assert closed["fraction"] == 0.6
    assert closed["exit_notional"] == pytest.approx(600.6)

    # 口径一致: 金额 = 对应 notional × bps
    assert reduced["fee"] == pytest.approx(reduced["exit_notional"] * reduced["fee_bps"] / 10000)
    assert reduced["slippage"] == pytest.approx(reduced["exit_notional"] * reduced["slippage_bps"] / 10000)
    assert closed["fee"] == pytest.approx(closed["exit_notional"] * closed["fee_bps"] / 10000)


def test_position_id_persisted_in_position_snapshot(tmp_path):
    ledger = PaperTradingLedger(tmp_path)
    decision, draft = approved_decision()
    ledger.on_decision(
        symbol="SOLUSDT",
        decision_payload=decision,
        draft_payload=draft,
        kline={"close": 100, "high": 100, "low": 100},
        timestamp=1000,
    )

    assert ledger.positions["SOLUSDT"].position_id == "SOLUSDT:1000:LONG"
    positions = json.loads((tmp_path / "paper_positions.json").read_text(encoding="utf-8"))
    assert positions["SOLUSDT"]["position_id"] == "SOLUSDT:1000:LONG"


def test_pnl_numbers_unchanged_vs_pre_change_baseline(tmp_path):
    """硬编码改动前(无新字段)同一回放的数值,证明纯增量改动零数值变化。"""
    ledger = PaperTradingLedger(tmp_path)
    rows = replay_open_tp1_close(ledger)

    opened = next(row for row in rows if row["event"] == "PAPER_OPEN")
    reduced = next(row for row in rows if row["event"] == "PAPER_REDUCE")
    closed = next(row for row in rows if row["event"] == "PAPER_CLOSE")

    # --- OPEN: 建仓成本 ---
    assert opened["notional"] == 1000.0
    assert opened["fee"] == 0.5
    assert opened["slippage"] == 0.5
    assert opened["notional_pnl"] == -1.0
    assert opened["margin_pnl"] == -3.0

    # --- TP1 减仓 ---
    assert reduced["quantity"] == 4.0
    assert reduced["gross_pnl"] == 7.199999999999989
    assert reduced["fee"] == 0.2036
    assert reduced["slippage"] == 0.2036
    assert reduced["net_pnl"] == 6.792799999999989
    assert reduced["notional_pnl"] == 6.792799999999989
    assert reduced["margin_pnl"] == 20.378399999999967
    assert reduced["position_realized_pnl"] == 5.792799999999989
    assert reduced["position_margin_realized_pnl"] == 17.378399999999967
    assert reduced["remaining_fraction"] == 0.6

    # --- 保本止损全平 ---
    assert closed["quantity"] == 6.0
    assert closed["gross_pnl"] == 0.5999999999999659
    assert closed["fee"] == 0.30029999999999996
    assert closed["slippage"] == 0.30029999999999996
    assert closed["net_pnl"] == -0.0006000000000340178
    assert closed["position_realized_pnl"] == 5.792199999999955
    assert closed["position_margin_realized_pnl"] == 17.376599999999865
    assert closed["remaining_fraction"] == 0.0

    # --- 账本汇总 ---
    assert ledger.realized_pnl == 5.792199999999955
    assert ledger.realized_margin_pnl == 17.376599999999865
    assert ledger.closed_trade_pnls == [5.792199999999955]
    assert ledger.closed_trade_margin_pnls == [17.376599999999865]

    summary = ledger.summary(2800)
    assert summary["realized_pnl"] == 5.792199999999955
    assert summary["realized_margin_pnl"] == 17.376599999999865
    assert summary["trade_count"] == 1


def test_legacy_event_rows_without_new_fields_still_load(tmp_path):
    """旧账本事件行没有 position_id/entry_price/fee_bps/notional 等键,读取与汇总不得抛异常。"""
    legacy_open = {
        "timestamp": 1000,
        "event": "PAPER_OPEN",
        "symbol": "SOLUSDT",
        "side": "LONG",
        "price": 100.0,
        "quantity": 10.0,
        "notional": 1000.0,
        "leverage": 3,
        "margin_used": 333.3333333333333,
        "fee": 0.5,
        "slippage": 0.5,
        "notional_pnl": -1.0,
        "margin_pnl": -3.0,
        "pnl_accounting_mode": "notional_primary_margin_reporting",
    }
    legacy_close = {
        "timestamp": 2800,
        "event": "PAPER_CLOSE",
        "symbol": "SOLUSDT",
        "side": "LONG",
        "reason": "INITIAL_STOP_HIT",
        "price": 98.5,
        "fraction": 1.0,
        "quantity": 10.0,
        "leverage": 3,
        "margin_used": 333.3333333333333,
        "gross_pnl": -15.0,
        "fee": 0.4925,
        "slippage": 0.4925,
        "net_pnl": -15.985,
        "notional_pnl": -15.985,
        "margin_pnl": -47.955,
        "position_realized_pnl": -16.985,
        "position_margin_realized_pnl": -50.955,
        "pnl_accounting_mode": "notional_primary_margin_reporting",
        "remaining_fraction": 0.0,
    }
    (tmp_path / "paper_trades.jsonl").write_text(
        "\n".join(json.dumps(row) for row in (legacy_open, legacy_close)) + "\n",
        encoding="utf-8",
    )

    ledger = PaperTradingLedger(tmp_path)

    assert ledger.trade_events() == [legacy_open, legacy_close]
    assert len(ledger.recent_closed_trades("SOLUSDT")) == 1
    assert len(ledger.recent_closed_trades_all()) == 1
    assert ledger.has_positive_closed_trade("SOLUSDT") is False
    assert ledger.closed_trade_pnls == [-16.985]
    assert ledger.summary(2800)["trade_count"] == 1
    snapshot = ledger.get_portfolio_state_snapshot(timestamp=1000)
    assert snapshot.daily_trades_by_symbol["SOLUSDT"] == 1


def test_legacy_position_snapshot_without_position_id_still_loads(tmp_path):
    """旧 paper_positions.json 无 position_id,PaperPosition 默认值兜底,不得抛异常。"""
    decision, draft = approved_decision()
    first = PaperTradingLedger(tmp_path)
    first.on_decision(
        symbol="SOLUSDT",
        decision_payload=decision,
        draft_payload=draft,
        kline={"close": 100, "high": 100, "low": 100},
        timestamp=1000,
    )
    positions_path = tmp_path / "paper_positions.json"
    positions = json.loads(positions_path.read_text(encoding="utf-8"))
    positions["SOLUSDT"].pop("position_id", None)
    positions_path.write_text(json.dumps(positions), encoding="utf-8")

    second = PaperTradingLedger(tmp_path)

    assert second.positions["SOLUSDT"].position_id == ""
    assert second.positions["SOLUSDT"].entry_price == 100.0
