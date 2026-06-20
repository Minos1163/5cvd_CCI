import pytest

from src.state_machine.entry_state_machine import (
    EntryState,
    EntryStateMachine,
    EntryStateStore,
    TRANSITION_LOG_FIELDS,
    evaluate_transition,
    transition,
)


def test_initial_state_is_flat():
    machine = EntryStateMachine(symbol="BTCUSDT")
    assert machine.current_state == EntryState.FLAT


@pytest.mark.parametrize(
    ("source", "target"),
    [
        (EntryState.FLAT, EntryState.WATCH_LONG),
        (EntryState.FLAT, EntryState.WATCH_SHORT),
        (EntryState.FLAT, EntryState.PROBE_LONG),
        (EntryState.FLAT, EntryState.PROBE_SHORT),
        (EntryState.FLAT, EntryState.DIRECT_LONG),
        (EntryState.FLAT, EntryState.DIRECT_SHORT),
        (EntryState.WATCH_LONG, EntryState.PROBE_LONG),
        (EntryState.WATCH_SHORT, EntryState.PROBE_SHORT),
        (EntryState.WATCH_LONG, EntryState.DIRECT_LONG),
        (EntryState.WATCH_SHORT, EntryState.DIRECT_SHORT),
        (EntryState.PROBE_LONG, EntryState.MANAGE_LONG),
        (EntryState.PROBE_SHORT, EntryState.MANAGE_SHORT),
        (EntryState.DIRECT_LONG, EntryState.MANAGE_LONG),
        (EntryState.DIRECT_SHORT, EntryState.MANAGE_SHORT),
        (EntryState.MANAGE_LONG, EntryState.EXIT_LONG),
        (EntryState.MANAGE_SHORT, EntryState.EXIT_SHORT),
        (EntryState.EXIT_LONG, EntryState.FLAT),
        (EntryState.EXIT_SHORT, EntryState.FLAT),
    ],
)
def test_refreshed_allowed_transition_graph(source, target):
    assert transition(source, target) == target


def test_invalid_cross_side_jump_is_rejected():
    machine = EntryStateMachine(symbol="BTCUSDT")
    with pytest.raises(ValueError):
        machine.apply_transition(EntryState.MANAGE_LONG, reason="skip entry", ts=1, price=1)


def test_transition_records_required_audit_fields_and_legacy_aliases():
    machine = EntryStateMachine(symbol="BTCUSDT")
    record = machine.apply_transition(
        EntryState.WATCH_LONG,
        reason="potential long",
        ts="2026-06-19T00:00:00Z",
        price=101.5,
        position_size=0.0,
        risk_value=0.0,
        signal_type="WAIT",
        entry_mode="NONE",
        risk_level="NORMAL",
        quality_flag=True,
    )
    payload = record.to_log_dict()
    for field in TRANSITION_LOG_FIELDS:
        assert field in payload
    assert payload["state_before"] == "FLAT"
    assert payload["state_after"] == "WATCH_LONG"
    assert payload["from_state"] == "FLAT"
    assert payload["to_state"] == "WATCH_LONG"
    assert payload["ts"] == "2026-06-19T00:00:00Z"


def test_legacy_direct_long_signal_moves_flat_directly_to_direct():
    machine = EntryStateMachine(symbol="BTCUSDT")
    records = machine.apply_signal({"signal_type": "DIRECT", "side": "LONG", "reason": "confirmed"}, ts=10, price=100)
    assert [record.to_state for record in records] == [EntryState.DIRECT_LONG]
    assert machine.current_state == EntryState.DIRECT_LONG


def test_new_signal_shape_uses_signal_type_side_and_entry_mode():
    machine = EntryStateMachine(symbol="BTCUSDT")
    records = machine.apply_signal(
        {
            "signal_type": "SHORT",
            "signal_side": "SHORT",
            "entry_mode": "PROBE",
            "reason": "early short",
            "risk_level": "HIGH",
        },
        ts=10,
        price=100,
    )
    assert records[0].to_state == EntryState.PROBE_SHORT
    assert records[0].entry_mode == "PROBE"
    assert records[0].risk_level == "HIGH"


def test_wait_and_no_trade_do_not_change_state():
    machine = EntryStateMachine(symbol="BTCUSDT")
    assert machine.apply_signal({"signal_type": "WAIT", "side": "NONE", "reason": "missing"}, ts=10, price=100) == []
    assert machine.apply_signal({"signal_type": "NO_TRADE", "side": "NONE", "reason": "conflict"}, ts=11, price=101) == []
    assert machine.current_state == EntryState.FLAT


@pytest.mark.parametrize(
    ("kwargs", "blocker"),
    [
        ({"risk_allowed": False}, "risk_blocked"),
        ({"quality_flag": False}, "data_quality_blocked"),
        ({"cooldown_active": True}, "cooldown_active"),
        ({"position_executable": False}, "position_not_executable"),
    ],
)
def test_blockers_prevent_mutation(kwargs, blocker):
    machine = EntryStateMachine(symbol="BTCUSDT")
    decision = evaluate_transition(
        machine.current_state,
        EntryState.DIRECT_LONG,
        reason="blocked candidate",
        **kwargs,
    )
    assert decision.allowed is False
    assert blocker in decision.blockers
    with pytest.raises(ValueError):
        machine.apply_transition(EntryState.DIRECT_LONG, reason="blocked candidate", ts=1, price=100, **kwargs)
    assert machine.current_state == EntryState.FLAT
    assert machine.history == []


def test_missing_reason_blocks_transition():
    decision = evaluate_transition(EntryState.FLAT, EntryState.WATCH_LONG, reason="")
    assert decision.allowed is False
    assert "missing_reason" in decision.blockers


def test_probe_and_direct_move_to_manage_after_position_open():
    probe = EntryStateMachine(symbol="BTCUSDT")
    probe.apply_signal({"signal_type": "PROBE", "side": "LONG", "reason": "probe"}, ts=1, price=100)
    probe_record = probe.mark_position_opened("order filled", ts=2, price=101)
    assert probe_record is not None
    assert probe.current_state == EntryState.MANAGE_LONG

    direct = EntryStateMachine(symbol="ETHUSDT")
    direct.apply_signal({"signal_type": "DIRECT", "side": "SHORT", "reason": "direct"}, ts=1, price=100)
    direct_record = direct.mark_position_opened("order filled", ts=2, price=99)
    assert direct_record is not None
    assert direct.current_state == EntryState.MANAGE_SHORT


def test_probe_long_upgrades_to_direct_at_one_r():
    machine = EntryStateMachine(symbol="BTCUSDT")
    machine.apply_signal({"signal_type": "PROBE", "side": "LONG", "reason": "probe"}, ts=1, price=100)
    record = machine.maybe_upgrade_probe(r_multiple=1.0, ts=2, price=105)
    assert record is not None
    assert record.to_state == EntryState.DIRECT_LONG


def test_manage_failure_exits_to_flat():
    machine = EntryStateMachine(symbol="BTCUSDT")
    machine.apply_signal({"signal_type": "DIRECT", "side": "SHORT", "reason": "direct"}, ts=1, price=100)
    machine.mark_position_opened("order filled", ts=2, price=99)
    records = machine.exit_current(reason="stop hit", ts=3, price=105)
    assert [record.to_state for record in records] == [EntryState.EXIT_SHORT, EntryState.FLAT]
    assert machine.current_state == EntryState.FLAT


def test_rejected_order_rolls_back_to_flat_without_manage_state():
    machine = EntryStateMachine(symbol="BTCUSDT")
    machine.apply_signal({"signal_type": "DIRECT", "side": "LONG", "reason": "direct"}, ts=1, price=100)
    record = machine.rollback_rejected_order(reason="ORDER_REJECTED", ts=2, price=100)
    assert record is not None
    assert record.to_state == EntryState.FLAT
    assert machine.current_state == EntryState.FLAT
    assert EntryState.MANAGE_LONG not in [item.to_state for item in machine.history]


def test_same_symbol_progresses_continuously():
    store = EntryStateStore()
    btc = store.get("btcusdt")
    btc.apply_signal({"signal_type": "PROBE", "side": "LONG", "reason": "probe"}, ts=1, price=100)
    assert store.get("BTCUSDT").current_state == EntryState.PROBE_LONG
    btc.mark_position_opened("filled", ts=2, price=101)
    assert store.state_of("BTCUSDT") == EntryState.MANAGE_LONG


def test_multi_symbol_state_is_isolated():
    store = EntryStateStore()
    store.get("BTCUSDT").apply_signal({"signal_type": "DIRECT", "side": "LONG", "reason": "long"}, ts=1, price=100)
    store.get("ETHUSDT").apply_signal({"signal_type": "PROBE", "side": "SHORT", "reason": "short"}, ts=1, price=100)
    assert store.state_of("BTCUSDT") == EntryState.DIRECT_LONG
    assert store.state_of("ETHUSDT") == EntryState.PROBE_SHORT
