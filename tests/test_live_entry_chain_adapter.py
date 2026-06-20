from src.execution.live_entry_chain_adapter import (
    LiveEntryOrderDraft,
    build_live_entry_order_draft,
    build_rejected_live_entry_order_draft,
)
from src.signals.entry_chain import EntryChainContext, evaluate_entry_chain


def context(**overrides):
    values = {
        "symbol": "BNBUSDT",
        "timestamp": 1_766_000_000,
        "side": "LONG",
        "component_scores": {
            "background_4h": 1.0,
            "direction_1h": 1.0,
            "quality_30m": 1.0,
            "trigger_15m": 1.0,
            "cvd_flow": 1.0,
            "volatility_stop": 1.0,
            "liquidity_execution": 1.0,
            "market_regime": 1.0,
        },
        "quote_volume_24h": 300_000_000.0,
        "atr_pct": 0.012,
        "expected_order_size": 2_000.0,
        "account_equity": 10_000.0,
        "available_margin": 8_000.0,
    }
    values.update(overrides)
    return EntryChainContext(**values)


def test_live_entry_adapter_builds_execution_request_with_entry_chain_snapshot():
    decision = evaluate_entry_chain(context())
    draft = build_live_entry_order_draft(
        decision,
        event_id="evt-entry",
        trace_id="trace-entry",
        correlation_id="corr-entry",
        price=500.0,
        timestamp=1_766_000_000,
        strategy_version="entry-chain-v1-live-safe",
    )

    assert isinstance(draft, LiveEntryOrderDraft)
    assert draft.approved is True
    assert draft.request is not None
    assert draft.request.entry_mode == decision.action
    assert draft.request.entry_chain_snapshot["action"] == decision.action
    assert draft.request.risk_snapshot["allow_trade"] is True
    assert draft.request.quantity * 500.0 <= decision.notional_hint


def test_live_entry_adapter_refuses_watch_or_no_trade_without_request():
    decision = evaluate_entry_chain(context(component_scores={"direction_1h": 0.1}))
    draft = build_live_entry_order_draft(
        decision,
        event_id="evt-entry",
        trace_id="trace-entry",
        correlation_id="corr-entry",
        price=500.0,
        timestamp=1_766_000_000,
        strategy_version="entry-chain-v1-live-safe",
    )

    assert draft.approved is False
    assert draft.request is None
    assert "entry chain action does not allow live order draft" in draft.reason


def test_rejected_live_entry_order_draft_keeps_full_audit_snapshot():
    decision = evaluate_entry_chain(context(macro_weekly_drop_pct=-0.16))
    draft = build_rejected_live_entry_order_draft(decision)

    assert draft.approved is False
    assert draft.request is None
    assert draft.audit["action"] == "NO_TRADE"
    assert "MACRO_WEEKLY_RISK" in draft.audit["reasons"]

