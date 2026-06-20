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
    assert (tmp_path / "paper_trades.jsonl").exists()
    assert (tmp_path / "paper_equity.json").exists()
    assert (tmp_path / "paper_summary.json").exists()


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

    assert events[0].startswith("PAPER_CLOSE:SOLUSDT:STOP_HIT")
    positions = json.loads((tmp_path / "paper_positions.json").read_text(encoding="utf-8"))
    summary = json.loads((tmp_path / "paper_summary.json").read_text(encoding="utf-8"))
    trade_rows = [json.loads(line) for line in (tmp_path / "paper_trades.jsonl").read_text(encoding="utf-8").splitlines()]
    assert positions == {}
    assert summary["trade_count"] == 1
    assert trade_rows[-1]["event"] == "PAPER_CLOSE"
    assert trade_rows[-1]["reason"] == "STOP_HIT"


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
        kline={"close": 105, "high": 105, "low": 100.5},
        timestamp=1900,
    )

    summary = json.loads((tmp_path / "paper_summary.json").read_text(encoding="utf-8"))
    assert summary["trade_count"] == 1
    assert summary["win_rate"] == 1.0
    assert summary["realized_pnl"] > 0
    assert summary["profit_factor"] > 0

