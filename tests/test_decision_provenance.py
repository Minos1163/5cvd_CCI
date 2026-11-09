from __future__ import annotations

from src.signals.decision_provenance import annotate_replacement, decision_id


def _decision(**kwargs):
    base = {"symbol": "BTCUSDT", "timestamp": 1793889000, "side": "SHORT",
            "action": "DIRECT", "score": 89.25, "leverage": 4,
            "exit_mode": "legacy", "entry_channel": "main_direct"}
    base.update(kwargs)
    return base


def test_decision_id_is_stable():
    first = decision_id(_decision(), {"quadrant": "Q1"})
    second = decision_id(_decision(), {"quadrant": "Q1"})
    assert first == second


def test_accepts_decision_object():
    class Decision:
        symbol = "ETHUSDT"
        timestamp = 1793900000
        side = "LONG"
        action = "DIRECT"
        score = 85.0
        leverage = 2
        exit_mode = "legacy"
        entry_channel = "main_direct"

    payload = {"quadrant": "Q2"}
    assert decision_id(Decision(), payload) == "ETHUSDT:1793900000:LONG"
    _, merged = annotate_replacement(Decision(), payload, None, None)
    assert merged["decision_origin"] == "primary"


def test_snapshot_falls_back_to_payload_for_missing_fields():
    """真实 EntryChainDecision 没有 exit_mode/entry_channel/symbol，必须由 payload 兜底。"""
    base_decision = _decision()
    base_payload = {
        "quadrant": "Q1",
        "exit_mode": "legacy",
        "entry_channel": "main_direct",
    }
    new_decision = _decision(action="PROBE")
    new_payload = {"quadrant": "Q1"}
    _, merged = annotate_replacement(base_decision, base_payload, new_decision, new_payload)
    assert merged["replaced_snapshot"]["exit_mode"] == "legacy"
    assert merged["replaced_snapshot"]["entry_channel"] == "main_direct"


def test_snapshot_fallback_works_on_real_decision_shape():
    """本条用**真的** EntryChainDecision 形状：没有 symbol/timestamp/exit_mode/entry_channel。

    生产上这四个字段只在 payload 里（src/signals/entry_chain.py:63-75 的字段清单）。
    不兜底的话 `replaced_snapshot.exit_mode` 会恒为 None——留痕等于没留。
    """
    from src.signals.entry_chain import EntryChainDecision

    real = EntryChainDecision(
        action="WATCH",
        side="LONG",
        score=71.0,
        weights={},
        component_points={},
        reasons=(),
        risk_allowed=True,
        leverage=1,
        max_symbol_exposure_pct=0.05,
        notional_hint=100.0,
        liquidity_ratio=1.0,
        metadata={},
    )
    payload = {
        "quadrant": "Q1",
        "symbol": "BTCUSDT",
        "timestamp": 1793889000,
        "exit_mode": "legacy",
        "entry_channel": "main_direct",
    }
    _, merged = annotate_replacement(real, payload, {"action": "PROBE"}, {"quadrant": "Q1"})
    snapshot = merged["replaced_snapshot"]
    assert snapshot["exit_mode"] == "legacy"
    assert snapshot["entry_channel"] == "main_direct"
    assert merged["replaced_decision_id"] == "BTCUSDT:1793889000:LONG"


def test_replacement_records_before_and_after():
    base_decision = _decision(action="WATCH", score=71.0)
    base_payload = {"quadrant": "Q1", "entry_price": 100.0}
    new_decision = _decision(action="PROBE", score=88.0, leverage=1,
                             exit_mode="trend_capture",
                             entry_channel="q1_trend_launch")
    new_payload = {"quadrant": "Q1", "entry_price": 101.0}

    merged_decision, merged_payload = annotate_replacement(
        base_decision, base_payload, new_decision, new_payload,
        origin="q1_green_channel",
    )

    assert merged_decision is new_decision
    assert merged_payload["decision_origin"] == "q1_green_channel"
    assert merged_payload["replaced_decision_id"] == decision_id(base_decision, base_payload)
    snapshot = merged_payload["replaced_snapshot"]
    assert snapshot["action"] == "WATCH"
    assert snapshot["score"] == 71.0
    assert snapshot["quadrant"] == "Q1"
    assert snapshot["exit_mode"] == "legacy"


def test_no_replacement_leaves_origin_primary():
    decision = _decision()
    payload = {"quadrant": "Q1"}
    _, merged_payload = annotate_replacement(decision, payload, None, None)
    assert merged_payload["decision_origin"] == "primary"
    assert "replaced_decision_id" not in merged_payload


def test_replacement_does_not_mutate_inputs():
    base_decision = _decision()
    base_payload = {"quadrant": "Q1"}
    new_decision = _decision(action="PROBE")
    new_payload = {"quadrant": "Q2"}
    annotate_replacement(base_decision, base_payload, new_decision, new_payload)
    assert "decision_origin" not in base_payload
    assert "decision_origin" not in new_payload
