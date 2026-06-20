# Entry State Machine Gap Report

Date: 2026-06-19

Scope: reread the refreshed `docs/05_entry_state_machine.md` and compare it with current state-machine scripts, tests, describe output, and scaffold templates. This report is documentation only; code changes are covered by the follow-up implementation plan.

---

## 1. Executive Summary

`docs/05_entry_state_machine.md` now defines the entry state machine as the auditable centerline between signal, risk, position, execution, and backtest layers. The existing implementation is a useful first pass, but it is still too thin for the refreshed contract: allowed transitions are incomplete, transition records do not expose the required audit fields, risk/data/cooldown/executability blockers are not first-class, rejected orders do not have a rollback helper, and multi-symbol isolation is not modeled.

The safest next step is to extend `src/state_machine/entry_state_machine.py` as a pure contract layer. It should validate transitions and produce audit records, but it must not calculate indicators, size positions, generate orders, call Binance, or rewrite risk/execution decisions.

---

## 2. Files Reviewed

- `docs/05_entry_state_machine.md`
- `src/state_machine/entry_state_machine.py`
- `tests/test_entry_state_machine.py`
- `scripts/describe_entry_state_machine.py`
- `tests/test_describe_entry_state_machine.py`
- `scripts/scaffold_ai300_framework.py`
- `tests/test_framework_scaffold.py`
- `src/signals/signal_engine.py`
- `src/risk/risk_engine.py`
- `src/core/events.py`

---

## 3. Document Cleanliness Issue

The refreshed `docs/05_entry_state_machine.md` is not yet canonical markdown:

- It starts with ChatGPT wrapper text.
- It includes an outer ````md fence.
- One transition graph closes with four backticks instead of a normal inner text fence.

Normalize the file so line 1 is `# Entry State Machine` and all code fences are valid markdown.

---

## 4. Current Implementation Snapshot

Current `src/state_machine/entry_state_machine.py` provides:

- `EntryState`
- `ALLOWED_TRANSITIONS`
- `transition()`
- `EntryTransition`
- `EntryStateMachine`
- `apply_transition()`
- `apply_signal()`
- `maybe_upgrade_probe()`
- `exit_current()`

This should remain compatible where possible, but the transition graph and audit surface need to match the refreshed 05 document.

---

## 5. Major Gaps

### 5.1 Transition Graph Is Incomplete

The refreshed document allows:

- `FLAT -> WATCH_* / PROBE_* / DIRECT_*`
- `PROBE_* -> MANAGE_* / EXIT_* / FLAT`, with optional re-evaluated `DIRECT_*`
- `DIRECT_* -> MANAGE_* / EXIT_* / FLAT`
- `MANAGE_* -> EXIT_* / FLAT`

Current code blocks several of these and still requires `FLAT -> WATCH -> DIRECT/PROBE` for signal entries.

### 5.2 Required Audit Fields Are Missing

The document requires each transition to record:

- `symbol`
- `timestamp`
- `state_before`
- `state_after`
- `reason`
- `signal_type`
- `entry_mode`
- `risk_level`
- `quality_flag`
- `price`
- `version`

Current logs use legacy `from_state`, `to_state`, `ts`, `position_size`, and `risk_value` fields only.

### 5.3 Blocking Rules Are Not First-Class

The refreshed spec says transition must have signal, risk, data quality, and position executability support. Current code has no explicit gate for:

- risk blocked
- data quality invalid
- cooldown active
- position not executable

### 5.4 Rejected Order Rollback Is Missing

The document explicitly requires rejected orders to avoid entering a held-position state. Current implementation has no helper for `ORDER_REJECTED` style rollback.

### 5.5 Multi-Symbol Isolation Is Missing

The tests now need same-symbol continuous progression and multi-symbol isolation. Current code models a single machine only; there is no small store/registry keyed by symbol.

### 5.6 Describe Output Is Too Thin

`scripts/describe_entry_state_machine.py` should expose required log fields, transition sources, forbidden actions, blocker inputs, state categories, and the full allowed transition graph.

### 5.7 Scaffold Templates Are Stale

`scripts/scaffold_ai300_framework.py` still contains the first-pass 05 templates. Future scaffolding could recreate the old narrower state machine unless synced.

---

## 6. Recommended Priority

### P0: Clean Canonical Markdown

Clean `docs/05_entry_state_machine.md` so it is a valid spec file.

### P1: Contract Constants And Audit Records

Extend the state-machine module with required fields, sources, forbidden actions, blockers, and a transition record that can emit the refreshed audit schema while preserving legacy aliases.

### P2: Transition Evaluation And Blockers

Add a pure evaluation path that validates allowed transitions plus signal/risk/data/cooldown/executability inputs without mutating state when blocked.

### P3: Rollback And Multi-Symbol Isolation

Add rejected-order rollback helpers and a small `EntryStateStore` keyed by symbol.

### P4: Describe And Scaffold Sync

Update describe output and scaffold templates after implementation.

---

## 7. Risk Notes

- Do not modify `src/api/binance_client.py`.
- Do not modify live exchange access.
- Do not calculate indicators in the state machine.
- Do not calculate final position size in the state machine.
- Do not submit or cancel orders in the state machine.
- Do not create same-bar fill assumptions.
- Do not let execution or risk layers rewrite state without passing through the state machine contract.

---

## 8. Proposed Next Plan

Implement the follow-up in `docs/superpowers/plans/2026-06-19-entry-state-machine-gap-fill.md`.
