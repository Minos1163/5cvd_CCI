# Entry Chain Optimization Backtest Claude Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Calibrate the AI300 entry-chain backtest toward the requested 30D trade-count target, rerun latest-30D tests, attribute the result, and produce a Claude-reviewable live-entry/risk contract.

**Architecture:** Keep the change research-safe: backtest state must approximate position release without touching live execution or Binance connectivity. The offline runner will accept explicit entry-chain config/profile parameters, run several profiles on the same downloaded 30D dataset, and write an attribution report plus a separate live-chain review document.

**Tech Stack:** Python, pytest, existing AI300 backtest engine, existing entry-chain config/scoring modules, Markdown reports.

---

## Success Criteria

- The offline entry-chain backtest no longer permanently accumulates active symbols and exposure after synthetic one-bar exits.
- `scripts/run_offline_backtest.py` can load `configs/entry_chain.dry_run_conservative.json`, `balanced`, and `aggressive` profiles without changing live execution paths.
- Latest 30D data is rerun with at least one calibrated profile and compared with prior round1/round2/round3 results.
- A result attribution report records trade count, return, win rate, profit factor, max drawdown, Sharpe, Sortino, expectancy, side/mode/symbol breakdown, and remaining target gaps.
- A Claude review MD records the live opening chain, hard gates, score weights, thresholds, sizing, leverage, and risk logic.
- `src/api/binance_client.py` remains untouched.

## File Structure

- Modify: `src/signals/portfolio_state.py`  
  Add explicit `release_position()` and timestamp-based `expire_positions()` helpers for research backtests.
- Modify: `tests/test_portfolio_state.py`  
  Cover exposure release and active-symbol cleanup.
- Modify: `scripts/run_offline_backtest.py`  
  Add config/profile flags and synthetic position expiry before each signal evaluation.
- Create: `docs/superpowers/reports/2026-06-19-entry-chain-optimization-backtest-attribution.md`  
  Summarize latest calibrated backtest and root causes.
- Create: `docs/superpowers/reports/2026-06-19-claude-live-entry-chain-risk-review.md`  
  Provide Claude-reviewable live-entry/risk contract.

## Task 1: Portfolio State Release Model

**Files:**
- Modify: `src/signals/portfolio_state.py`
- Modify: `tests/test_portfolio_state.py`

- [ ] **Step 1: Write failing tests**

Add tests proving that released positions reduce symbol exposure, same-direction exposure, and active symbol count.

- [ ] **Step 2: Implement minimal release helpers**

Add `release_position(symbol, side, notional)` and `expire_positions(timestamp)` with clamped non-negative exposure.

- [ ] **Step 3: Verify**

Run:

```powershell
pytest tests/test_portfolio_state.py -q
```

Expected: all portfolio-state tests pass.

## Task 2: Offline Runner Profile Loading

**Files:**
- Modify: `scripts/run_offline_backtest.py`

- [ ] **Step 1: Add CLI flags**

Add:

```text
--entry-chain-config
--simulated-hold-bars
--cooldown-bars
```

Defaults should preserve a conservative research posture: default config from `EntryChainConfig()`, hold bars `2`, cooldown bars `16`.

- [ ] **Step 2: Load config only for entry-chain strategy**

When `--strategy entry-chain` is selected, pass loaded `EntryChainConfig` into `evaluate_entry_chain()`.

- [ ] **Step 3: Expire synthetic positions before evaluating each bar**

Before building `EntryChainContext`, release any positions whose synthetic exit timestamp is no later than the current completed bar timestamp.

- [ ] **Step 4: Verify**

Run:

```powershell
python -m compileall src scripts
pytest tests/test_portfolio_state.py tests/test_entry_chain_config.py tests/test_entry_chain.py -q
```

Expected: compile succeeds and focused tests pass.

## Task 3: Latest 30D Profile Backtests

**Files:**
- No code files expected after Task 2.
- Read/write under `reports/backtests/`.

- [ ] **Step 1: Run balanced profile**

```powershell
python scripts/run_offline_backtest.py --data-dir data/raw/binance_futures/latest_30d --timeframe 15m --strategy entry-chain --entry-chain-config configs/entry_chain.dry_run_balanced.json --simulated-hold-bars 2 --cooldown-bars 8 --run-id latest_30d_round4_entry_chain_balanced
```

- [ ] **Step 2: Run aggressive research profile if balanced remains below trade-count target**

```powershell
python scripts/run_offline_backtest.py --data-dir data/raw/binance_futures/latest_30d --timeframe 15m --strategy entry-chain --entry-chain-config configs/entry_chain.dry_run_aggressive.json --simulated-hold-bars 2 --cooldown-bars 4 --run-id latest_30d_round4_entry_chain_aggressive
```

- [ ] **Step 3: Extract result metrics**

Read each `reports/backtests/<run_id>/backtest_result.json` and compare against prior runs:

```text
latest_30d_round1
latest_30d_round2_entry_chain
latest_30d_round3_entry_chain_refined
```

## Task 4: Attribution Report

**Files:**
- Create: `docs/superpowers/reports/2026-06-19-entry-chain-optimization-backtest-attribution.md`

- [ ] **Step 1: Write result summary**

Include the calibrated run IDs, data range, symbols, fill/cost assumptions, and target comparison.

- [ ] **Step 2: Attribute result**

Explain whether losses or underperformance came from entry quality, trade count, fee/slippage drag, direction split, symbol concentration, probe/direct split, or synthetic exit limitations.

- [ ] **Step 3: State next engineering blocker**

Be explicit that the current engine still uses synthetic one-bar exits unless a fuller lifecycle engine is implemented.

## Task 5: Claude Review Contract

**Files:**
- Create: `docs/superpowers/reports/2026-06-19-claude-live-entry-chain-risk-review.md`

- [ ] **Step 1: Document exact opening chain**

List the sequential gates from universe/data quality through execution pre-check and protection order confirmation.

- [ ] **Step 2: Document score and thresholds**

Include weights, dynamic weight rules, direct/probe/watch thresholds, component minimums, and hard vetoes.

- [ ] **Step 3: Document sizing/risk**

Include 3x/4x/5x leverage selection, 20%-30% exposure target, max 5 active symbols, risk-per-trade, stop/TP ladder, daily/weekly stops, cooldowns, stress loss cap, and trade-budget control.

- [ ] **Step 4: Add Claude review questions**

Ask Claude to challenge target feasibility, threshold strictness, leverage/exposure safety, and required validation length.

## Task 6: Final Verification

**Files:**
- No intended changes to `src/api/binance_client.py`.

- [ ] **Step 1: Run focused verification**

```powershell
python -m compileall src scripts tests
pytest tests/test_portfolio_state.py tests/test_entry_chain.py tests/test_entry_chain_config.py tests/test_dry_run_configs.py -q
git diff -- src/api/binance_client.py
```

Expected: compile succeeds, focused tests pass, and the Binance client diff is empty.

- [ ] **Step 2: Final response**

Report which run is best, whether it meets target, the main attribution, and paths to both MD reports.

