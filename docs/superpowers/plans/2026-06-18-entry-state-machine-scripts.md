# Entry State Machine Scripts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the scripts required by `docs/05_entry_state_machine.md` as pure entry-state transition utilities.

**Architecture:** Extend `src/state_machine/entry_state_machine.py` from a transition table into a small state machine with typed transition records, signal-driven entry transitions, probe upgrade/failure handling, and debug log payloads. The state machine does not calculate stops, size positions, place orders, or call Binance.

**Tech Stack:** Python standard library, dataclasses, enums, pytest.

---

## File Structure

- Modify: `src/state_machine/entry_state_machine.py` - add `EntryTransition`, `EntryStateMachine`, signal handling, probe upgrade/failure helpers, and log payload generation.
- Create: `scripts/describe_entry_state_machine.py` - prints state names, allowed transitions, and rule summary as JSON.
- Create: `tests/test_entry_state_machine.py` - tests initial state, signal-driven transitions, probe upgrade/failure, illegal jumps, and required log fields.
- Create: `tests/test_describe_entry_state_machine.py` - tests CLI JSON output.
- Preserve: `src/api/binance_client.py` - do not modify the stable Binance client.

---

### Task 1: Typed Transition Records

**Files:**

- Modify: `src/state_machine/entry_state_machine.py`
- Create: `tests/test_entry_state_machine.py`

- [ ] **Step 1: Write failing tests for initial state, legal transition, and log fields**

```python
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
```

- [ ] **Step 2: Run test to verify failure**

Run: `pytest tests/test_entry_state_machine.py -q`

Expected: FAIL because `EntryStateMachine` does not exist.

- [ ] **Step 3: Implement transition record and machine shell**

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class EntryTransition:
    symbol: str
    from_state: EntryState
    to_state: EntryState
    reason: str
    ts: int
    price: float
    position_size: float = 0.0
    risk_value: float = 0.0

    def to_log_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "from_state": self.from_state.value,
            "to_state": self.to_state.value,
            "reason": self.reason,
            "ts": self.ts,
            "price": self.price,
            "position_size": self.position_size,
            "risk_value": self.risk_value,
        }


class EntryStateMachine:
    def __init__(self, symbol: str, initial_state: EntryState = EntryState.FLAT):
        self.symbol = symbol
        self.current_state = initial_state
        self.history: list[EntryTransition] = []

    def apply_transition(...):
        ...
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_entry_state_machine.py -q`

Expected: PASS for initial transition tests; signal tests will be added in Task 2.

---

### Task 2: Signal-Driven State Transitions

**Files:**

- Modify: `src/state_machine/entry_state_machine.py`
- Modify: `tests/test_entry_state_machine.py`

- [ ] **Step 1: Add failing tests for DIRECT, PROBE, WAIT, and NO_TRADE**

```python
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
```

- [ ] **Step 2: Implement `apply_signal`**

```python
def apply_signal(self, signal: dict, ts: int, price: float, position_size: float = 0.0, risk_value: float = 0.0) -> list[EntryTransition]:
    signal_type = str(signal.get("signal_type", "")).upper()
    side = str(signal.get("side", "")).upper()
    reason = str(signal.get("reason", signal_type))
    if signal_type in {"WAIT", "NO_TRADE"}:
        return []
    if signal_type == "DIRECT" and side == "LONG":
        return [self.apply_transition(EntryState.WATCH_LONG, reason, ts, price, position_size, risk_value), self.apply_transition(EntryState.DIRECT_LONG, reason, ts, price, position_size, risk_value)]
    ...
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/test_entry_state_machine.py -q`

Expected: PASS.

---

### Task 3: Probe Upgrade and Exit Helpers

**Files:**

- Modify: `src/state_machine/entry_state_machine.py`
- Modify: `tests/test_entry_state_machine.py`

- [ ] **Step 1: Add failing tests for probe upgrade and stop exit**

```python
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
```

- [ ] **Step 2: Implement helpers**

```python
def maybe_upgrade_probe(self, r_multiple: float, ts: int, price: float) -> EntryTransition | None:
    if r_multiple < 1.0:
        return None
    if self.current_state == EntryState.PROBE_LONG:
        return self.apply_transition(EntryState.DIRECT_LONG, "probe reached 1R", ts, price)
    if self.current_state == EntryState.PROBE_SHORT:
        return self.apply_transition(EntryState.DIRECT_SHORT, "probe reached 1R", ts, price)
    return None


def exit_current(self, reason: str, ts: int, price: float) -> list[EntryTransition]:
    ...
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/test_entry_state_machine.py -q`

Expected: PASS.

---

### Task 4: CLI Summary

**Files:**

- Create: `scripts/describe_entry_state_machine.py`
- Create: `tests/test_describe_entry_state_machine.py`

- [ ] **Step 1: Write failing CLI test**

```python
import json
import subprocess
import sys


def test_describe_entry_state_machine_outputs_json():
    result = subprocess.run(
        [sys.executable, "scripts/describe_entry_state_machine.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    assert payload["initial_state"] == "FLAT"
    assert "PROBE_LONG" in payload["states"]
    assert payload["probe_upgrade_r"] == 1.0
```

- [ ] **Step 2: Implement CLI**

```python
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.state_machine.entry_state_machine import ALLOWED_TRANSITIONS, EntryState


def main() -> None:
    payload = {
        "initial_state": EntryState.FLAT.value,
        "states": [state.value for state in EntryState],
        "probe_upgrade_r": 1.0,
        "allowed_transitions": {state.value: sorted(target.value for target in targets) for state, targets in ALLOWED_TRANSITIONS.items()},
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/test_describe_entry_state_machine.py tests/test_entry_state_machine.py -q`

Expected: PASS.

---

## Verification

Run:

```powershell
pytest tests/test_entry_state_machine.py tests/test_describe_entry_state_machine.py -q
pytest tests/test_multi_tf_rules.py tests/test_describe_multi_tf_rules.py tests/test_indicator_spec_rules.py tests/test_indicator_engine.py tests/test_describe_indicator_rules.py tests/test_project_spec.py tests/test_strategy_philosophy.py tests/test_market_universe.py tests/test_describe_project_rules.py tests/test_framework_scaffold.py -q
python -m compileall src scripts tests
python scripts/describe_entry_state_machine.py
git diff -- src/api/binance_client.py
```

Expected:

- all tests pass
- compile succeeds
- CLI prints valid JSON
- `src/api/binance_client.py` diff is empty

