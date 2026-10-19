import json

from src.observability.paper_trading import (
    MAX_STOP_PCT,
    MIN_STOP_PCT,
    PaperTradingLedger,
)


def _decision(**overrides) -> dict:
    decision = {
        "action": "DIRECT",
        "side": "LONG",
        "score": 88,
        "leverage": 3,
        "entry_context": {"atr_pct": 0.01},
        "reasons": ["TEST_DIRECT"],
    }
    decision.update(overrides)
    return decision


DRAFT = {
    "approved": True,
    "request": {"position_side": "LONG", "quantity": 10, "price": 100},
}


def _open_events(tmp_path, decision) -> list[dict]:
    ledger = PaperTradingLedger(tmp_path)
    ledger.on_decision(
        symbol="SOLUSDT",
        decision_payload=decision,
        draft_payload=DRAFT,
        kline={"close": 100, "high": 100, "low": 100},
        timestamp=1000,
    )
    lines = (tmp_path / "paper_trades.jsonl").read_text(encoding="utf-8").strip().splitlines()
    return [json.loads(line) for line in lines]


def test_payload_stop_pct_overrides_atr_derived_stop(tmp_path):
    """策略侧算出的 stop_pct 必须被账本采用,否则建仓仓位与出场止损脱钩。"""
    events = _open_events(tmp_path, _decision(stop_pct=0.02))
    opened = next(e for e in events if e["event"] == "PAPER_OPEN")
    assert opened["stop_pct"] == 0.02
    assert opened["stop_source"] == "payload"
    assert opened["stop_price"] == 98.0
    assert opened["tp_prices"] == [102.4, 104.0, 106.0]


def test_missing_payload_stop_pct_falls_back_to_atr(tmp_path):
    events = _open_events(tmp_path, _decision())
    opened = next(e for e in events if e["event"] == "PAPER_OPEN")
    assert opened["stop_source"] == "atr"
    assert opened["stop_pct"] == 0.015


def test_risk_budget_stop_pct_is_used_when_top_level_missing(tmp_path):
    events = _open_events(tmp_path, _decision(metadata={"risk_budget": {"stop_pct": 0.012}}))
    opened = next(e for e in events if e["event"] == "PAPER_OPEN")
    assert opened["stop_source"] == "payload.risk_budget"
    assert opened["stop_pct"] == 0.012


def test_stop_pct_is_clamped_to_ledger_bounds(tmp_path):
    low = _open_events(tmp_path / "low", _decision(stop_pct=0.0001))
    assert next(e for e in low if e["event"] == "PAPER_OPEN")["stop_pct"] == MIN_STOP_PCT
    high = _open_events(tmp_path / "high", _decision(stop_pct=0.5))
    assert next(e for e in high if e["event"] == "PAPER_OPEN")["stop_pct"] == MAX_STOP_PCT


def test_zero_or_negative_override_is_ignored(tmp_path):
    for value in (0, -0.01, None):
        events = _open_events(tmp_path / str(value), _decision(stop_pct=value))
        opened = next(e for e in events if e["event"] == "PAPER_OPEN")
        assert opened["stop_source"] == "atr"
