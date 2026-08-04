# Four Quadrant Navigation Offense Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the existing four-quadrant dry-run map into a minimally observable navigation system that can generate controlled paper/scout samples without touching real exchange execution.

**Architecture:** Keep the current `scripts/run_live_dry_run.py` orchestration and `PaperTradingLedger` state model. Add small, explicit dry-run config fields, SCOUT decision audit output, a Q1 trend-launch replacement for the old broad green channel, a reversal pivot SCOUT mission, and quadrant-aware position actions in the paper ledger.

**Tech Stack:** Python stdlib, existing entry-chain config dataclass, existing paper ledger JSONL outputs, pytest.

## Global Constraints

- Do not touch real exchange mutation or `src/api/binance_client.py`.
- All new entry behavior must be dry-run / paper / SCOUT only.
- No lookahead signals: live decisions may use only the current decision payload and prior persisted state.
- Preserve existing CLI arguments.
- Preserve existing paper fee/slippage accounting.
- Existing user/worktree changes must not be reverted.
- Verification command: `python -m pytest tests/test_live_dry_run.py tests/test_paper_trading.py tests/test_entry_chain_config.py tests/test_dry_run_configs.py -q`.

---

### Task 1: SCOUT Decision Audit

**Files:**
- Modify: `src/observability/decision_audit.py`
- Modify: `scripts/run_live_dry_run.py`
- Test: `tests/test_decision_audit.py`
- Test: `tests/test_live_dry_run.py`

**Interfaces:**
- Produces `DecisionAuditWriter.write_scout_decision(row: Mapping[str, object]) -> None` writing `scout_decisions.jsonl`.
- Produces `build_scout_decision_audit(...) -> dict[str, Any]` with `candidate`, `accepted`, `mission`, `reject_reason`, `budget_state`, `mission_stop_circuit_state`, `cooldown_state`, `position_conflict_state`, `war_fund_state`.

**Steps:**
- [x] Add a `scout_decisions.jsonl` handle to `DecisionAuditWriter`, flush on write and close it in `close()`.
- [x] Refactor `should_open_scout_micro` so rejection reasons can be obtained without guessing.
- [x] Write a scout audit row for every non-null near-miss, including accepted and rejected candidates.
- [x] Add tests for accepted mission and rejected data-health / no-mission cases.

### Task 2: Q1 Trend Launch Confirmation Engine

**Files:**
- Modify: `src/signals/entry_chain_config.py`
- Modify: `configs/entry_chain.dry_run_fib_pa_v1.json`
- Modify: `scripts/run_live_dry_run.py`
- Test: `tests/test_entry_chain_config.py`
- Test: `tests/test_dry_run_configs.py`
- Test: `tests/test_live_dry_run.py`

**Interfaces:**
- Add config fields prefixed `dry_run_q1_trend_launch_*`.
- Replace broad `q1_green_channel` conversion with `q1_trend_launch` conversion.
- Keep `build_q1_green_channel_decision` as a compatibility wrapper if tests/imports expect it, but make the new eligibility require trend-launch confirmation.

**Steps:**
- [x] Add config fields for enabling trend launch, min score, min PA/Fib/CVD/RR, allowed source quadrants, max prior Q2/Q3 age bars, exposure multiplier, exit mode.
- [x] Store pending Q2/Q3 pullback candidates and confirm only when the symbol returns to Q1 with the same side.
- [x] Require Fib/PA structure and non-zero RR; do not allow pure RR-gap Q1 chase entries.
- [x] Mark metadata `entry_channel=q1_trend_launch`, `experiment_id=four_quadrant_navigation_v1`, and `exit_mode=trend_capture`.
- [x] Add tests proving direct Q1 RR-gap chase is rejected and Q2/Q3-to-Q1 confirmation is converted.

### Task 3: Reversal Pivot SCOUT Mission

**Files:**
- Modify: `src/signals/entry_chain_config.py`
- Modify: `configs/entry_chain.dry_run_fib_pa_v1.json`
- Modify: `scripts/run_live_dry_run.py`
- Test: `tests/test_live_dry_run.py`

**Interfaces:**
- Add config fields prefixed `scout_micro_reversal_pivot_*`.
- Add mission name `REVERSAL_PIVOT_SCOUT`.
- Use only current near-miss diagnostics and current component scores. No future bars.

**Steps:**
- [x] Detect exhaustion using Fib exhaustion or `OPPOSITION_STRUCTURE_TOO_CLOSE`, high Fib score or extension block, and weakening flow/CCI thresholds.
- [x] Flip the intended side for the scout payload only when the reversal mission is selected.
- [x] Use 25 USDT notional by default, 1x leverage, `trend_capture` exit mode.
- [x] Add tests for eligible reversal mission, side flip, and non-eligible continuation cases.

### Task 4: Four-Quadrant Position State Machine

**Files:**
- Modify: `src/observability/paper_trading.py`
- Test: `tests/test_paper_trading.py`

**Interfaces:**
- Existing Q4 defensive exit remains for experiment positions.
- Add Q3 50% defensive reduction for experiment positions.
- Add Q2 tighter stop behavior for experiment positions.
- Persist new state needed to avoid repeated Q3 reductions.

**Steps:**
- [x] Add position field `q3_reduced` with backward-compatible load default.
- [x] On Q2 for experiment positions, tighten stop to breakeven if it improves risk.
- [x] On Q3 for experiment positions, reduce 50% once and record reason `Q3_DEFENSIVE_REDUCE`.
- [x] Keep Q4 two-bar losing-position exit unchanged.
- [x] Add tests for Q2 stop tightening, one-time Q3 reduce, and Q4 still closing.

## Execution Verification

- 2026-07-27: Verified with `python -m pytest tests/test_live_dry_run.py tests/test_paper_trading.py tests/test_entry_chain_config.py tests/test_dry_run_configs.py tests/test_decision_audit.py -q` -> 122 passed.
