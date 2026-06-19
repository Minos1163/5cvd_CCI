import pytest

from src.state_machine.entry_state_machine import EntryState, EntryStateMachine


def test_initial_state_is_flat():
    machine = EntryStateMachine(symbol="BTCUSDT")
    assert machine.current_state == EntryState.FLAT


def test_transition_records_required_debug_fields():
    machine = EntryStateMachine(symbol="BTCUSDT")
    record = machine.apply_transition(
        EntryState.WATCH_LONG,
        reason="potential long",
        ts=100,
        price=101.5,
        position_size=0.0,
        risk_value=0.0,
    )
    assert record.from_state == EntryState.FLAT
    assert record.to_state == EntryState.WATCH_LONG
    assert record.to_log_dict()["symbol"] == "BTCUSDT"
    assert record.to_log_dict()["risk_value"] == 0.0


def test_invalid_jump_is_rejected():
    machine = EntryStateMachine(symbol="BTCUSDT")
    with pytest.raises(ValueError):
        machine.apply_transition(EntryState.DIRECT_LONG, reason="skip watch", ts=1, price=1)


def test_direct_long_signal_moves_flat_to_watch_then_direct():
    machine = EntryStateMachine(symbol="BTCUSDT")
    records = machine.apply_signal({"signal_type": "DIRECT", "side": "LONG", "reason": "confirmed"}, ts=10, price=100)
    assert [record.to_state for record in records] == [EntryState.WATCH_LONG, EntryState.DIRECT_LONG]
    assert machine.current_state == EntryState.DIRECT_LONG


def test_probe_short_signal_moves_flat_to_watch_then_probe():
    machine = EntryStateMachine(symbol="BTCUSDT")
    records = machine.apply_signal({"signal_type": "PROBE", "side": "SHORT", "reason": "early"}, ts=10, price=100)
    assert [record.to_state for record in records] == [EntryState.WATCH_SHORT, EntryState.PROBE_SHORT]
    assert machine.current_state == EntryState.PROBE_SHORT


def test_wait_and_no_trade_do_not_change_state():
    machine = EntryStateMachine(symbol="BTCUSDT")
    assert machine.apply_signal({"signal_type": "WAIT", "side": "NONE", "reason": "missing"}, ts=10, price=100) == []
    assert machine.apply_signal({"signal_type": "NO_TRADE", "side": "NONE", "reason": "conflict"}, ts=11, price=101) == []
    assert machine.current_state == EntryState.FLAT


def test_probe_long_upgrades_to_direct_at_one_r():
    machine = EntryStateMachine(symbol="BTCUSDT")
    machine.apply_signal({"signal_type": "PROBE", "side": "LONG", "reason": "probe"}, ts=1, price=100)
    record = machine.maybe_upgrade_probe(r_multiple=1.0, ts=2, price=105)
    assert record is not None
    assert record.to_state == EntryState.DIRECT_LONG


def test_probe_failure_exits_immediately():
    machine = EntryStateMachine(symbol="BTCUSDT")
    machine.apply_signal({"signal_type": "PROBE", "side": "SHORT", "reason": "probe"}, ts=1, price=100)
    records = machine.exit_current(reason="stop hit", ts=2, price=105)
    assert [record.to_state for record in records] == [EntryState.EXIT_SHORT, EntryState.FLAT]
    assert machine.current_state == EntryState.FLAT
