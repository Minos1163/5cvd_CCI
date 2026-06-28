import json

from src.observability.paper_trading import PaperTradingLedger


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


def test_paper_trading_ledger_opens_position_and_writes_snapshots(tmp_path):
    ledger = PaperTradingLedger(tmp_path)
    decision, draft = approved_decision()

    events = ledger.on_decision(
        symbol="SOLUSDT",
        decision_payload=decision,
        draft_payload=draft,
        kline={"close": 100, "high": 100, "low": 100},
        timestamp=1000,
    )

    assert events == ["PAPER_OPEN:SOLUSDT:LONG@100.00000000"]
    positions = json.loads((tmp_path / "paper_positions.json").read_text(encoding="utf-8"))
    assert positions["SOLUSDT"]["entry_price"] == 100
    assert positions["SOLUSDT"]["tp_consumed"] == []
    assert (tmp_path / "paper_trades.jsonl").exists()
    assert (tmp_path / "paper_equity.json").exists()
    assert (tmp_path / "paper_summary.json").exists()
    equity = json.loads((tmp_path / "paper_equity.json").read_text(encoding="utf-8"))
    summary = json.loads((tmp_path / "paper_summary.json").read_text(encoding="utf-8"))
    assert equity["latest_kline_timestamp"] == 1000
    assert summary["latest_kline_timestamp"] == 1000
    assert "updated_at" in equity
    assert "updated_at" in summary
    assert summary["pnl_accounting_mode"] == "notional_primary_margin_reporting"
    assert "realized_notional_pnl" in summary
    assert "realized_margin_pnl" in summary


def test_paper_trading_ledger_exposes_portfolio_state_snapshot(tmp_path):
    ledger = PaperTradingLedger(tmp_path)
    decision, draft = approved_decision()
    ledger.on_decision(
        symbol="SOLUSDT",
        decision_payload=decision,
        draft_payload=draft,
        kline={"close": 100, "high": 100, "low": 100},
        timestamp=1000,
    )

    snapshot = ledger.get_portfolio_state_snapshot(timestamp=1000)

    assert snapshot.active_symbols == {"SOLUSDT"}
    assert snapshot.open_position_count == 1
    assert snapshot.total_exposure_pct > 0
    assert snapshot.same_direction_long_pct > 0
    assert snapshot.same_direction_short_pct == 0
    assert snapshot.symbol_exposure_pct["SOLUSDT"] > 0
    assert snapshot.daily_trades_by_symbol["SOLUSDT"] == 1
    assert snapshot.portfolio_trades_today == 1


def test_paper_trading_ledger_sets_tp1_at_one_point_two_r(tmp_path):
    ledger = PaperTradingLedger(tmp_path)
    decision, draft = approved_decision()
    ledger.on_decision(
        symbol="SOLUSDT",
        decision_payload=decision,
        draft_payload=draft,
        kline={"close": 100, "high": 100, "low": 100},
        timestamp=1000,
    )

    position = ledger.positions["SOLUSDT"]

    assert round(position.tp_prices[0], 4) == 101.8


def test_paper_trading_ledger_closes_on_conservative_stop_before_tp(tmp_path):
    ledger = PaperTradingLedger(tmp_path)
    decision, draft = approved_decision()
    ledger.on_decision(
        symbol="SOLUSDT",
        decision_payload=decision,
        draft_payload=draft,
        kline={"close": 100, "high": 100, "low": 100},
        timestamp=1000,
    )

    events = ledger.on_decision(
        symbol="SOLUSDT",
        decision_payload={"action": "NO_TRADE"},
        draft_payload={"approved": False},
        kline={"close": 100, "high": 103, "low": 98},
        timestamp=1900,
    )

    assert events[0].startswith("PAPER_CLOSE:SOLUSDT:INITIAL_STOP_HIT")
    positions = json.loads((tmp_path / "paper_positions.json").read_text(encoding="utf-8"))
    summary = json.loads((tmp_path / "paper_summary.json").read_text(encoding="utf-8"))
    trade_rows = [json.loads(line) for line in (tmp_path / "paper_trades.jsonl").read_text(encoding="utf-8").splitlines()]
    assert positions == {}
    assert summary["trade_count"] == 1
    assert trade_rows[-1]["event"] == "PAPER_CLOSE"
    assert trade_rows[-1]["reason"] == "INITIAL_STOP_HIT"


def test_paper_trading_ledger_classifies_stop_after_tp1_as_breakeven(tmp_path):
    ledger = PaperTradingLedger(tmp_path)
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

    events = ledger.on_decision(
        symbol="SOLUSDT",
        decision_payload={"action": "NO_TRADE"},
        draft_payload={"approved": False},
        kline={"close": 100.1, "high": 100.2, "low": 99.9},
        timestamp=2800,
    )

    assert events[0].startswith("PAPER_CLOSE:SOLUSDT:BREAKEVEN_STOP_HIT")
    trade_rows = [json.loads(line) for line in (tmp_path / "paper_trades.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [row.get("reason") for row in trade_rows if row["event"] in {"PAPER_REDUCE", "PAPER_CLOSE"}] == [
        "TP1_HIT",
        "BREAKEVEN_STOP_HIT",
    ]


def test_paper_trading_ledger_tracks_tp_ladder_profit_factor(tmp_path):
    ledger = PaperTradingLedger(tmp_path)
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
        kline={"close": 103, "high": 103, "low": 101.5},
        timestamp=2800,
    )
    ledger.on_decision(
        symbol="SOLUSDT",
        decision_payload={"action": "NO_TRADE"},
        draft_payload={"approved": False},
        kline={"close": 105, "high": 105, "low": 103},
        timestamp=3700,
    )

    summary = json.loads((tmp_path / "paper_summary.json").read_text(encoding="utf-8"))
    assert summary["trade_count"] == 1
    assert summary["win_rate"] == 1.0
    assert summary["realized_pnl"] > 0
    assert summary["profit_factor"] > 0
    trade_rows = [json.loads(line) for line in (tmp_path / "paper_trades.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [row.get("reason") for row in trade_rows if row["event"] in {"PAPER_REDUCE", "PAPER_CLOSE"}] == [
        "TP1_HIT",
        "TP2_HIT",
        "TP3_HIT",
    ]


def test_paper_trading_ledger_does_not_repeat_consumed_tp_level(tmp_path):
    ledger = PaperTradingLedger(tmp_path)
    decision, draft = approved_decision()
    ledger.on_decision(
        symbol="SOLUSDT",
        decision_payload=decision,
        draft_payload=draft,
        kline={"close": 100, "high": 100, "low": 100},
        timestamp=1000,
    )

    first = ledger.on_decision(
        symbol="SOLUSDT",
        decision_payload={"action": "NO_TRADE"},
        draft_payload={"approved": False},
        kline={"close": 101.8, "high": 101.8, "low": 100.5},
        timestamp=1900,
    )
    second = ledger.on_decision(
        symbol="SOLUSDT",
        decision_payload={"action": "NO_TRADE"},
        draft_payload={"approved": False},
        kline={"close": 101.8, "high": 101.8, "low": 100.5},
        timestamp=2800,
    )

    assert first[0].startswith("PAPER_REDUCE:SOLUSDT:TP1_HIT")
    assert second == []
    positions = json.loads((tmp_path / "paper_positions.json").read_text(encoding="utf-8"))
    assert positions["SOLUSDT"]["remaining_fraction"] == 0.6
    assert positions["SOLUSDT"]["tp_consumed"] == [0]


def test_paper_trading_ledger_loads_positions_from_persistent_state_dir(tmp_path):
    state_dir = tmp_path / "state" / "paper"
    day_one = tmp_path / "logs" / "2026-06" / "2026-06-20"
    day_two = tmp_path / "logs" / "2026-06" / "2026-06-21"
    decision, draft = approved_decision()

    first = PaperTradingLedger(day_one, state_dir=state_dir)
    first.on_decision(
        symbol="SOLUSDT",
        decision_payload=decision,
        draft_payload=draft,
        kline={"close": 100, "high": 100, "low": 100},
        timestamp=1000,
    )

    second = PaperTradingLedger(day_two, state_dir=state_dir)
    assert "SOLUSDT" in second.positions
    second.on_decision(
        symbol="SOLUSDT",
        decision_payload={"action": "NO_TRADE"},
        draft_payload={"approved": False},
        kline={"close": 100.1, "high": 100.1, "low": 100},
        timestamp=1900,
    )

    state_positions = json.loads((state_dir / "paper_positions.json").read_text(encoding="utf-8"))
    day_two_positions = json.loads((day_two / "paper_positions.json").read_text(encoding="utf-8"))
    assert state_positions["SOLUSDT"]["hold_bars"] == 1
    assert day_two_positions["SOLUSDT"]["hold_bars"] == 1


def test_paper_trading_ledger_records_margin_pnl_labels(tmp_path):
    ledger = PaperTradingLedger(tmp_path)
    decision, draft = approved_decision()
    ledger.on_decision(
        symbol="SOLUSDT",
        decision_payload=decision,
        draft_payload=draft,
        kline={"close": 100, "high": 100, "low": 100},
        timestamp=1000,
    )

    trade_rows = [json.loads(line) for line in (tmp_path / "paper_trades.jsonl").read_text(encoding="utf-8").splitlines()]
    assert trade_rows[0]["pnl_accounting_mode"] == "notional_primary_margin_reporting"
    assert trade_rows[0]["margin_used"] == trade_rows[0]["notional"] / trade_rows[0]["leverage"]
    assert trade_rows[0]["margin_pnl"] == trade_rows[0]["notional_pnl"] * trade_rows[0]["leverage"]


def test_paper_trading_ledger_exposes_recent_initial_stops_and_positive_history(tmp_path):
    ledger = PaperTradingLedger(tmp_path)
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
        kline={"close": 100, "high": 103, "low": 98},
        timestamp=1900,
    )
    ledger.on_decision(
        symbol="TONUSDT",
        decision_payload=decision,
        draft_payload=draft,
        kline={"close": 100, "high": 100, "low": 100},
        timestamp=2000,
    )
    ledger.on_decision(
        symbol="TONUSDT",
        decision_payload={"action": "NO_TRADE"},
        draft_payload={"approved": False},
        kline={"close": 103, "high": 103, "low": 101.5},
        timestamp=2900,
    )
    ledger.on_decision(
        symbol="TONUSDT",
        decision_payload={"action": "NO_TRADE"},
        draft_payload={"approved": False},
        kline={"close": 105, "high": 105, "low": 103},
        timestamp=3800,
    )
    ledger.on_decision(
        symbol="TONUSDT",
        decision_payload={"action": "NO_TRADE"},
        draft_payload={"approved": False},
        kline={"close": 106, "high": 106, "low": 104},
        timestamp=4700,
    )

    recent_stops = ledger.recent_closed_trades(
        "SOLUSDT",
        reason="INITIAL_STOP_HIT",
        since_ts=1000,
        until_ts=2000,
    )

    assert len(recent_stops) == 1
    assert recent_stops[0]["reason"] == "INITIAL_STOP_HIT"
    assert ledger.has_positive_closed_trade("TONUSDT", until_ts=5000) is True
    assert ledger.has_positive_closed_trade("SOLUSDT", until_ts=5000) is False


def test_paper_trading_ledger_deduplicates_hold_bars_by_kline_timestamp(tmp_path):
    ledger = PaperTradingLedger(tmp_path)
    decision, draft = approved_decision()
    ledger.on_decision(
        symbol="SOLUSDT",
        decision_payload=decision,
        draft_payload=draft,
        kline={"close": 100, "high": 100, "low": 100},
        timestamp=1000,
    )

    for _ in range(3):
        ledger.on_decision(
            symbol="SOLUSDT",
            decision_payload={"action": "NO_TRADE"},
            draft_payload={"approved": False},
            kline={"close": 100.1, "high": 100.1, "low": 100},
            timestamp=1900,
        )

    positions = json.loads((tmp_path / "paper_positions.json").read_text(encoding="utf-8"))
    assert positions["SOLUSDT"]["hold_bars"] == 1
    assert positions["SOLUSDT"]["last_processed_kline_ts"] == 1900

    ledger.on_decision(
        symbol="SOLUSDT",
        decision_payload={"action": "NO_TRADE"},
        draft_payload={"approved": False},
        kline={"close": 100.2, "high": 100.2, "low": 100},
        timestamp=2800,
    )

    positions = json.loads((tmp_path / "paper_positions.json").read_text(encoding="utf-8"))
    assert positions["SOLUSDT"]["hold_bars"] == 2
