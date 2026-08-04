import json

from src.observability.paper_trading import PaperExitConfig, PaperTradingLedger


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
    assert positions["SOLUSDT"]["max_favorable_r_observed"] == 0.0
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


def test_paper_trading_ledger_defaults_to_legacy_breakeven_after_tp1(tmp_path):
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

    assert round(ledger.positions["SOLUSDT"].stop_price, 4) == 100.1
    assert ledger.positions["SOLUSDT"].exit_mode == "legacy"


def test_paper_trading_ledger_trend_capture_trails_after_trigger_r(tmp_path):
    ledger = PaperTradingLedger(
        tmp_path,
        exit_config=PaperExitConfig(mode="trend_capture", trend_trigger_r=1.5, trailing_r_mult=1.0),
    )
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
        kline={"close": 102.8, "high": 102.8, "low": 101.6},
        timestamp=1900,
    )

    assert round(ledger.positions["SOLUSDT"].stop_price, 4) == 101.3
    assert ledger.positions["SOLUSDT"].exit_mode == "trend_capture"
    assert round(ledger.positions["SOLUSDT"].max_favorable_r_observed, 4) == 1.8667
    trade_rows = [json.loads(line) for line in (tmp_path / "paper_trades.jsonl").read_text(encoding="utf-8").splitlines()]
    assert trade_rows[-1]["exit_mode"] == "trend_capture"
    assert round(trade_rows[-1]["max_favorable_r_observed"], 4) == 1.8667


def test_paper_trading_summary_includes_payoff_health_metrics(tmp_path):
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
        kline={"close": 105, "high": 105, "low": 103},
        timestamp=1900,
    )
    ledger.on_decision(
        symbol="SOLUSDT",
        decision_payload={"action": "NO_TRADE"},
        draft_payload={"approved": False},
        kline={"close": 105, "high": 105, "low": 103},
        timestamp=2800,
    )
    ledger.on_decision(
        symbol="SOLUSDT",
        decision_payload={"action": "NO_TRADE"},
        draft_payload={"approved": False},
        kline={"close": 105, "high": 105, "low": 103},
        timestamp=3700,
    )
    second_decision, second_draft = approved_decision()
    ledger.on_decision(
        symbol="BNBUSDT",
        decision_payload=second_decision,
        draft_payload=second_draft,
        kline={"close": 100, "high": 100, "low": 100},
        timestamp=4600,
    )
    ledger.on_decision(
        symbol="BNBUSDT",
        decision_payload={"action": "NO_TRADE"},
        draft_payload={"approved": False},
        kline={"close": 98, "high": 100, "low": 98},
        timestamp=5500,
    )

    summary = json.loads((tmp_path / "paper_summary.json").read_text(encoding="utf-8"))

    assert summary["avg_win"] > 0
    assert summary["avg_loss"] > 0
    assert summary["actual_payoff_ratio"] > 0
    assert summary["breakeven_payoff_ratio"] > 0
    assert "payoff_ratio_health" in summary
    assert summary["exit_mode"] == "legacy"


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


def test_paper_trading_ledger_loads_legacy_position_without_trend_diagnostics(tmp_path):
    state_dir = tmp_path / "state" / "paper"
    state_dir.mkdir(parents=True)
    decision, draft = approved_decision()
    first = PaperTradingLedger(tmp_path / "day-one", state_dir=state_dir)
    first.on_decision(
        symbol="SOLUSDT",
        decision_payload=decision,
        draft_payload=draft,
        kline={"close": 100, "high": 100, "low": 100},
        timestamp=1000,
    )
    positions_path = state_dir / "paper_positions.json"
    positions = json.loads(positions_path.read_text(encoding="utf-8"))
    del positions["SOLUSDT"]["best_price"]
    del positions["SOLUSDT"]["max_favorable_r_observed"]
    del positions["SOLUSDT"]["exit_mode"]
    positions_path.write_text(json.dumps(positions), encoding="utf-8")

    second = PaperTradingLedger(tmp_path / "day-two", state_dir=state_dir)

    assert second.positions["SOLUSDT"].best_price == 100
    assert second.positions["SOLUSDT"].max_favorable_r_observed == 0.0
    assert second.positions["SOLUSDT"].exit_mode == "legacy"


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


def test_paper_trading_ledger_exits_stagnant_position_at_cost_checkpoint(tmp_path):
    ledger = PaperTradingLedger(tmp_path)
    decision, draft = approved_decision()
    ledger.on_decision(
        symbol="SOLUSDT",
        decision_payload=decision,
        draft_payload=draft,
        kline={"close": 100, "high": 100, "low": 100},
        timestamp=1000,
    )

    events = []
    exit_index = None
    for index in range(1, 9):
        events = ledger.on_decision(
            symbol="SOLUSDT",
            decision_payload={"action": "NO_TRADE"},
            draft_payload={"approved": False},
            kline={"close": 100.05, "high": 100.1, "low": 100.0},
            timestamp=1000 + index * 900,
        )
        if events:
            exit_index = index
            break

    assert exit_index == 8
    assert events[0].startswith("PAPER_CLOSE:SOLUSDT:COST_BREAKEVEN_TIMEOUT")
    trade_rows = [json.loads(line) for line in (tmp_path / "paper_trades.jsonl").read_text(encoding="utf-8").splitlines()]
    assert trade_rows[-1]["reason"] == "COST_BREAKEVEN_TIMEOUT"


def test_paper_trading_ledger_reads_recent_closed_trades_across_symbols(tmp_path):
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
        kline={"close": 99, "high": 100, "low": 98},
        timestamp=1900,
    )
    ledger.on_decision(
        symbol="BNBUSDT",
        decision_payload=decision,
        draft_payload=draft,
        kline={"close": 100, "high": 100, "low": 100},
        timestamp=2800,
    )
    ledger.on_decision(
        symbol="BNBUSDT",
        decision_payload={"action": "NO_TRADE"},
        draft_payload={"approved": False},
        kline={"close": 99, "high": 100, "low": 98},
        timestamp=3700,
    )

    rows = ledger.recent_closed_trades_all(reason="INITIAL_STOP_HIT", since_ts=1000, until_ts=4000)

    assert [row["symbol"] for row in rows] == ["SOLUSDT", "BNBUSDT"]


def test_paper_trading_ledger_persists_experiment_metadata(tmp_path):
    ledger = PaperTradingLedger(tmp_path)
    decision, draft = approved_decision()
    decision = {
        **decision,
        "exit_mode": "trend_capture",
        "experiment_id": "four_quadrant_navigation_v1",
        "entry_channel": "q1_green_channel",
        "source_quadrant": "Q1",
    }

    ledger.on_decision(
        symbol="SOLUSDT",
        decision_payload=decision,
        draft_payload=draft,
        kline={"close": 100, "high": 100, "low": 100},
        timestamp=1000,
    )

    positions = json.loads((tmp_path / "paper_positions.json").read_text(encoding="utf-8"))
    assert positions["SOLUSDT"]["exit_mode"] == "trend_capture"
    assert positions["SOLUSDT"]["experiment_id"] == "four_quadrant_navigation_v1"
    assert positions["SOLUSDT"]["entry_channel"] == "q1_green_channel"
    assert positions["SOLUSDT"]["source_quadrant"] == "Q1"

    rows = [json.loads(line) for line in (tmp_path / "paper_trades.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows[-1]["experiment_id"] == "four_quadrant_navigation_v1"
    assert rows[-1]["entry_channel"] == "q1_green_channel"


def test_paper_trading_ledger_q4_defensive_exit_closes_losing_experiment_position(tmp_path):
    ledger = PaperTradingLedger(tmp_path)
    decision, draft = approved_decision()
    decision = {
        **decision,
        "experiment_id": "four_quadrant_navigation_v1",
        "entry_channel": "q1_green_channel",
        "source_quadrant": "Q1",
    }
    ledger.on_decision(
        symbol="SOLUSDT",
        decision_payload=decision,
        draft_payload=draft,
        kline={"close": 100, "high": 100, "low": 100},
        timestamp=1000,
    )

    first = ledger.on_decision(
        symbol="SOLUSDT",
        decision_payload={"action": "NO_TRADE", "quadrant": "Q4"},
        draft_payload={"approved": False},
        kline={"close": 99.9, "high": 100, "low": 99.9},
        timestamp=1900,
    )
    second = ledger.on_decision(
        symbol="SOLUSDT",
        decision_payload={"action": "NO_TRADE", "quadrant": "Q4"},
        draft_payload={"approved": False},
        kline={"close": 99.8, "high": 100, "low": 99.8},
        timestamp=2800,
    )

    assert first == []
    assert second[0].startswith("PAPER_CLOSE:SOLUSDT:Q4_DEFENSIVE_EXIT")
    rows = [json.loads(line) for line in (tmp_path / "paper_trades.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows[-1]["reason"] == "Q4_DEFENSIVE_EXIT"
    assert rows[-1]["experiment_id"] == "four_quadrant_navigation_v1"


def test_paper_trading_ledger_q2_tightens_experiment_stop_to_breakeven(tmp_path):
    ledger = PaperTradingLedger(tmp_path)
    decision, draft = approved_decision()
    decision = {
        **decision,
        "experiment_id": "four_quadrant_navigation_v1",
        "entry_channel": "q1_trend_launch",
        "source_quadrant": "Q1",
    }
    ledger.on_decision(
        symbol="SOLUSDT",
        decision_payload=decision,
        draft_payload=draft,
        kline={"close": 100, "high": 100, "low": 100},
        timestamp=1000,
    )

    ledger.on_decision(
        symbol="SOLUSDT",
        decision_payload={"action": "NO_TRADE", "quadrant": "Q2"},
        draft_payload={"approved": False},
        kline={"close": 100.5, "high": 101, "low": 100.2},
        timestamp=1900,
    )

    assert round(ledger.positions["SOLUSDT"].stop_price, 4) == 100.1


def test_paper_trading_ledger_q3_defensive_reduce_once_for_experiment_position(tmp_path):
    ledger = PaperTradingLedger(tmp_path)
    decision, draft = approved_decision()
    decision = {
        **decision,
        "experiment_id": "four_quadrant_navigation_v1",
        "entry_channel": "q1_trend_launch",
        "source_quadrant": "Q1",
    }
    ledger.on_decision(
        symbol="SOLUSDT",
        decision_payload=decision,
        draft_payload=draft,
        kline={"close": 100, "high": 100, "low": 100},
        timestamp=1000,
    )

    first = ledger.on_decision(
        symbol="SOLUSDT",
        decision_payload={"action": "NO_TRADE", "quadrant": "Q3"},
        draft_payload={"approved": False},
        kline={"close": 100.5, "high": 101, "low": 100.2},
        timestamp=1900,
    )
    second = ledger.on_decision(
        symbol="SOLUSDT",
        decision_payload={"action": "NO_TRADE", "quadrant": "Q3"},
        draft_payload={"approved": False},
        kline={"close": 100.6, "high": 101, "low": 100.3},
        timestamp=2800,
    )

    assert first[0].startswith("PAPER_REDUCE:SOLUSDT:Q3_DEFENSIVE_REDUCE")
    assert second == []
    assert ledger.positions["SOLUSDT"].remaining_fraction == 0.5
    rows = [json.loads(line) for line in (tmp_path / "paper_trades.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows[-1]["reason"] == "Q3_DEFENSIVE_REDUCE"
    assert rows[-1]["remaining_fraction"] == 0.5


def test_paper_trading_ledger_q4_rule_ignores_non_experiment_position(tmp_path):
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
        decision_payload={"action": "NO_TRADE", "quadrant": "Q4"},
        draft_payload={"approved": False},
        kline={"close": 99.9, "high": 100, "low": 99.9},
        timestamp=1900,
    )
    events = ledger.on_decision(
        symbol="SOLUSDT",
        decision_payload={"action": "NO_TRADE", "quadrant": "Q4"},
        draft_payload={"approved": False},
        kline={"close": 99.8, "high": 100, "low": 99.8},
        timestamp=2800,
    )

    assert events == []
    assert "SOLUSDT" in ledger.positions


# ---------- Phase 3 payoff 试点: early breakeven ----------

def test_early_breakeven_moves_stop_to_cost_after_plus1r_before_tp(tmp_path):
    """试点开启: 未 TP 时达 +1R(101.5)后止损移到成本(100.1), 回落触发 BREAKEVEN 而非 INITIAL_STOP。"""
    ledger = PaperTradingLedger(
        tmp_path,
        exit_config=PaperExitConfig(mode="legacy", early_breakeven_enabled=True, early_breakeven_trigger_r=1.0),
    )
    decision, draft = approved_decision()
    ledger.on_decision(
        symbol="SOLUSDT",
        decision_payload=decision,
        draft_payload=draft,
        kline={"close": 100, "high": 100, "low": 100},
        timestamp=1000,
    )
    # 达 +1R(>101.5)但未达 TP1(101.8): 止损应上移到成本 100.1
    ledger.on_decision(
        symbol="SOLUSDT",
        decision_payload={"action": "NO_TRADE"},
        draft_payload={"approved": False},
        kline={"close": 101.6, "high": 101.6, "low": 100.4},
        timestamp=1900,
    )
    assert round(ledger.positions["SOLUSDT"].stop_price, 4) == 100.1
    # 回落到 99.8: 止损(已在成本 100.1)触发, 收益≈0(而非初始止损 -1.5%)
    events = ledger.on_decision(
        symbol="SOLUSDT",
        decision_payload={"action": "NO_TRADE"},
        draft_payload={"approved": False},
        kline={"close": 99.8, "high": 100.2, "low": 99.8},
        timestamp=2800,
    )
    assert events and events[0].startswith("PAPER_CLOSE:SOLUSDT:INITIAL_STOP_HIT:")
    pnl = float(events[0].rsplit(":", 1)[1])
    assert abs(pnl) < 0.05  # 保本止损: 收益≈0, 而非初始止损的 -1.5%


def test_early_breakeven_disabled_by_default(tmp_path):
    """默认(试点关): 达 +1R 后止损保持初始值, 不移动。"""
    ledger = PaperTradingLedger(tmp_path)  # 默认 early_breakeven_enabled=False
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
        kline={"close": 101.6, "high": 101.6, "low": 100.4},
        timestamp=1900,
    )
    assert round(ledger.positions["SOLUSDT"].stop_price, 4) == 98.5  # 未移动


def test_early_breakeven_not_triggered_below_1r(tmp_path):
    """未达 +1R: 止损不移动。"""
    ledger = PaperTradingLedger(
        tmp_path,
        exit_config=PaperExitConfig(mode="legacy", early_breakeven_enabled=True, early_breakeven_trigger_r=1.0),
    )
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
        kline={"close": 101.0, "high": 101.0, "low": 99.9},  # 0.67R < 1.0R
        timestamp=1900,
    )
    assert round(ledger.positions["SOLUSDT"].stop_price, 4) == 98.5


def test_early_breakeven_skips_after_tp_consumed(tmp_path):
    """已 TP1: 早保本不覆盖 post_tp_stop 的结果(止损仍为 TP 后行为)。"""
    ledger = PaperTradingLedger(
        tmp_path,
        exit_config=PaperExitConfig(mode="legacy", early_breakeven_enabled=True, early_breakeven_trigger_r=1.0),
    )
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
        kline={"close": 101.8, "high": 101.8, "low": 100.5},  # 触发 TP1
        timestamp=1900,
    )
    # 已 TP1, legacy 模式 post_tp 止损=breakeven; 早保本不应改变
    assert round(ledger.positions["SOLUSDT"].stop_price, 4) == 100.1
