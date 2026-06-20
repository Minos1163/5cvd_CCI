# Entry State Machine Gap Fill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the refreshed `docs/05_entry_state_machine.md` into a clean, testable entry-state-machine contract.

**Architecture:** Keep the state machine as a pure coordination layer: it validates and records state transitions, but does not calculate indicators, final size, orders, exchange responses, or risk decisions. Preserve legacy helpers where possible, while adding explicit transition blockers, refreshed audit fields, rejected-order rollback, and multi-symbol isolation.

**Tech Stack:** Python dataclasses, enums, pure functions, pytest, JSON describe scripts, scaffold template synchronization.

---

## File Structure

Modify:

- `docs/05_entry_state_machine.md`
- `src/state_machine/entry_state_machine.py`
- `tests/test_entry_state_machine.py`
- `scripts/describe_entry_state_machine.py`
- `tests/test_describe_entry_state_machine.py`
- `scripts/scaffold_ai300_framework.py`
- `tests/test_framework_scaffold.py`

Do not modify:

- `src/api/binance_client.py`
- live exchange adapters
- risk sizing modules
- backtest fill model modules

---

## Tasks

### Task 1: Clean 05 Markdown

- [ ] Remove ChatGPT wrapper text from `docs/05_entry_state_machine.md`.
- [ ] Remove the outer ````md fence.
- [ ] Fix the first transition graph fence to close with normal triple backticks.
- [ ] Verify line 1 is `# Entry State Machine`.

### Task 2: Add Entry-State Contract Tests

- [ ] Extend `tests/test_entry_state_machine.py` to cover all refreshed transition categories:
  - `FLAT -> WATCH_LONG / WATCH_SHORT`
  - `WATCH -> PROBE`
  - `WATCH -> DIRECT`
  - `PROBE -> MANAGE`
  - `DIRECT -> MANAGE`
  - `MANAGE -> EXIT`
  - `EXIT -> FLAT`
  - `FLAT -> PROBE_* / DIRECT_*`
- [ ] Add tests for risk, data quality, cooldown, and executability blockers.
- [ ] Add tests for rejected-order rollback to `FLAT`.
- [ ] Add tests for required audit log fields.
- [ ] Add tests for same-symbol progression and multi-symbol isolation.

Expected command:

```powershell
pytest tests\test_entry_state_machine.py -q
```

### Task 3: Implement Entry-State Contract

- [ ] Update `ALLOWED_TRANSITIONS` to match the refreshed document.
- [ ] Add constants:
  - `ENTRY_STATE_VERSION`
  - `TRANSITION_LOG_FIELDS`
  - `TRANSITION_SOURCES`
  - `TRANSITION_BLOCKERS`
  - `ENTRY_STATE_FORBIDDEN_ACTIONS`
  - `ENTRY_STATE_CATEGORIES`
- [ ] Add `TransitionDecision`.
- [ ] Expand `EntryTransition` so `to_log_dict()` emits refreshed fields and legacy aliases.
- [ ] Add `evaluate_transition()` to check graph validity and blockers without mutating state.
- [ ] Update `apply_transition()` to use the evaluator and append audit records only when allowed.
- [ ] Update `apply_signal()` to understand both legacy `signal_type=DIRECT/PROBE` and newer `signal_type=LONG/SHORT` plus `entry_mode`.
- [ ] Add `rollback_rejected_order()`.
- [ ] Add `EntryStateStore` keyed by symbol.

### Task 4: Expand Describe Output

- [ ] Update `scripts/describe_entry_state_machine.py`.
- [ ] Update `tests/test_describe_entry_state_machine.py`.

Expected command:

```powershell
pytest tests\test_describe_entry_state_machine.py -q
```

### Task 5: Sync Scaffold

- [ ] Sync scaffold templates for `src/state_machine/entry_state_machine.py` and `scripts/describe_entry_state_machine.py`.
- [ ] Add scaffold assertions for refreshed constants and helpers.

Expected command:

```powershell
pytest tests\test_framework_scaffold.py -q
```

### Task 6: Final Verification

Run:

```powershell
pytest tests\test_entry_state_machine.py tests\test_describe_entry_state_machine.py tests\test_framework_scaffold.py -q
pytest -q
python -m compileall src scripts tests
git diff -- src\api\binance_client.py
```

Expected:

- Tests pass.
- Compile succeeds.
- Binance client diff is empty.

---

## Completion Criteria

- `docs/05_entry_state_machine.md` is clean canonical markdown.
- The transition graph matches the refreshed 05 document.
- Transition records expose the required audit fields.
- Risk/data/cooldown/executability blockers prevent mutation and explain why.
- Rejected order rollback is explicit.
- Same-symbol progression and multi-symbol isolation are covered by tests.
- Describe output and scaffold templates match the new contract.
- No changes to `src/api/binance_client.py`.
