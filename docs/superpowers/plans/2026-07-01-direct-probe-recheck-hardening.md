# Direct To Probe Recheck Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the HIGH_BETA `DIRECT -> PROBE` downgrade loophole and add the minimum monitoring/risk controls needed for the next VPS dry-run.

**Architecture:** Keep the fix in `src/signals/entry_chain.py` so all callers get consistent action semantics. After any post-minimum downgrade to `PROBE`, re-run the Fib/PA PROBE conditions before sizing. Add budget diagnostics to decision metadata and keep config-only risk threshold changes in the dry-run Fib/PA profile.

**Tech Stack:** Python, pytest, JSON config, existing `EntryChainConfig`, `EntryChainContext`, and `EntryChainDecision`.

## Global Constraints

- Do not modify real exchange order submission or production live execution behavior.
- Do not introduce lookahead bias, future candle data, repaint signals, or same-bar fill assumptions.
- Strategy gates must use only current decision context, current config, and already known paper ledger state.
- Hypothesis: the 2026-07-01 HYPEUSDT loss was caused by a HIGH_BETA `DIRECT -> PROBE` downgrade that bypassed stricter PROBE Fib/HighBeta conditions.
- Expected regime: dry-run Fib/PA profile after emergency hardening, where strict PROBE gates should remain binding after downgrades.
- Failure mode: the fix may reduce already-low trade frequency; budget metadata must make that visible in `decisions.jsonl`.
- Verification command: `pytest tests/test_entry_chain.py tests/test_entry_chain_gates.py tests/test_entry_chain_config.py tests/test_dry_run_configs.py tests/test_live_dry_run.py -q`.

---

### Task 1: Recheck PROBE Conditions After Downgrades

**Files:**
- Modify: `src/signals/entry_chain.py`
- Test: `tests/test_entry_chain.py`

**Interfaces:**
- Consumes: `EntryChainContext.component_scores`, `EntryChainConfig.probe_conditions`, and post-minimum action.
- Produces: WATCH demotion reason `HIGH_BETA_DIRECT_TO_PROBE_FAILED_CONDITIONS` plus the concrete `HIGH_BETA_PROBE_BELOW_*` reason when a high-beta DIRECT is forced to PROBE but fails PROBE rules.

- [ ] **Step 1: Add failing test**

Add a test mirroring the HYPE loss: `symbol="HYPEUSDT"`, `direct_threshold=82`, Fib/PA architecture enabled, `fibonacci_location=9/18`, `risk_reward_geometry=5/8`, `cci=14/14`, `trend_ema=16.19/20`, and HIGH_BETA PROBE requires `min_fib_score=12`. Expected action: `WATCH`.

- [ ] **Step 2: Implement recheck helper**

After `HIGH_BETA_PROBE_ONLY` sets `action="PROBE"`, call `_apply_fib_pa_probe_minimums` with the same `scores`, `score`, `cfg`, `symbol`, and `side`. If it returns `WATCH`, append `HIGH_BETA_DIRECT_TO_PROBE_FAILED_CONDITIONS`.

- [ ] **Step 3: Verify Task 1**

Run: `pytest tests/test_entry_chain.py -q`

Expected: PASS.

### Task 2: Harden Dry-Run Fib/PA Config

**Files:**
- Modify: `configs/entry_chain.dry_run_fib_pa_v1.json`
- Test: `tests/test_dry_run_configs.py`
- Test: `tests/test_entry_chain_config.py`

**Interfaces:**
- Consumes: existing config fields.
- Produces: dry-run `fib_min_direct_score=9.0`, `portfolio_stop_circuit_count=2`, and `portfolio_stop_circuit_hours=2`.

- [ ] **Step 1: Update config assertions**

Update dry-run config tests to expect direct Fib minimum `9.0` and consecutive initial-stop circuit `2` stops / `2` hours.

- [ ] **Step 2: Update JSON config**

Set:
- `fib_min_direct_score: 9.0`
- `portfolio_stop_circuit_count: 2`
- `portfolio_stop_circuit_hours: 2`

- [ ] **Step 3: Verify Task 2**

Run: `pytest tests/test_dry_run_configs.py tests/test_entry_chain_config.py -q`

Expected: PASS.

### Task 3: Add Budget Diagnostics To Decision Metadata

**Files:**
- Modify: `src/signals/entry_chain.py`
- Test: `tests/test_entry_chain.py`

**Interfaces:**
- Produces metadata keys:
  - `daily_max_trades`
  - `daily_budget_detail.dynamic_limit`
  - `daily_budget_detail.used_today`
  - `daily_budget_detail.current_volatility_scale`
  - `daily_budget_detail.normal_volatility_scale`
  - `daily_budget_detail.min_daily_trades`
  - `daily_budget_detail.daily_profit_pct`

- [ ] **Step 1: Add metadata test**

Add a test that evaluates a context blocked by `DAILY_TRADE_BUDGET_USED` and asserts the metadata includes the dynamic limit and used count.

- [ ] **Step 2: Implement helper**

Create `_daily_budget_detail(context, cfg) -> dict[str, float | int]` and use it in `_daily_max_trades` and `_decision` metadata to avoid formula drift.

- [ ] **Step 3: Verify Task 3**

Run: `pytest tests/test_entry_chain.py tests/test_entry_chain_gates.py -q`

Expected: PASS.

### Task 4: Focused Verification

**Files:**
- No new source files.

**Interfaces:**
- Produces confidence for VPS upload.

- [ ] **Step 1: Run focused suite**

Run: `pytest tests/test_entry_chain.py tests/test_entry_chain_gates.py tests/test_entry_chain_config.py tests/test_dry_run_configs.py tests/test_live_dry_run.py -q`

Expected: PASS.

- [ ] **Step 2: Inspect diff**

Run: `git diff -- src/signals/entry_chain.py configs/entry_chain.dry_run_fib_pa_v1.json tests/test_entry_chain.py tests/test_dry_run_configs.py tests/test_entry_chain_config.py docs/superpowers/plans/2026-07-01-direct-probe-recheck-hardening.md`

Expected: only planned files changed for this task.
