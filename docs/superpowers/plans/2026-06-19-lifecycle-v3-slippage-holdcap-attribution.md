# Lifecycle V3 Slippage Holdcap Attribution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Test whether the V2 positive expectancy survives more realistic execution friction and hold-cap variation, then report why the strategy still does or does not reach the 50%+ return / 80% win-rate target.

**Architecture:** Freeze the entry chain, universe, Probe-disabled semantics, XRP blacklist, fee model, and TP fractions. Add exit-side slippage per partial exit, MFE/MAE and stop-hit timing attribution, then run controlled latest-30D experiments for hold caps `8`, `16`, `32` and a conservative slippage stress. This remains offline research-only and must not touch live Binance connectivity.

**Tech Stack:** Python, pytest, existing AI300 backtest engine, existing lifecycle exit model, existing offline runner, Markdown reports.

---

## Success Criteria

- Exit-side slippage is charged for every partial exit based on actual partial quantity and price.
- `BacktestTrade` records `entry_slippage`, `exit_slippage`, `mfe_pct`, `mae_pct`, and `stop_hit_bar_offset`.
- Synthetic exit default behavior remains backward compatible.
- Latest 30D experiments are run for hold caps `8`, `16`, and `32` with entry rules frozen.
- A conservative slippage stress run increases slippage by `25%`.
- Report includes per-side, per-symbol, per-exit-reason, TP sequence, stop bar-offset, MFE/MAE, fee/slippage drag, and target-gap attribution.
- `src/api/binance_client.py` remains untouched.

## Research Controls

- Keep entry config fixed: `configs/entry_chain.dry_run_ema_soft_lifecycle_hardened.json`.
- Keep Probe disabled.
- Keep XRPUSDT blacklisted.
- Keep TP levels `1,2,3`.
- Keep TP fractions `0.4,0.35,0.25`.
- Keep ATR stop multiplier `1.5`.
- Keep fee bps `5`.
- Change only hold cap and slippage stress in the experiment grid.

## File Structure

- Modify: `src/backtest/engine.py`  
  Add exit-side slippage accounting and trade attribution fields.
- Modify: `tests/test_backtest_engine.py`  
  Cover exit-side slippage and attribution serialization.
- Modify: `scripts/run_offline_backtest.py`  
  No new strategy logic; ensure run risk constraints retain slippage assumptions.
- Create: `docs/superpowers/reports/2026-06-19-lifecycle-v3-slippage-holdcap-attribution-report.md`  
  V3 result and attribution report.

## Task 1: Exit-Side Slippage Accounting

**Files:**
- Modify: `src/backtest/engine.py`
- Modify: `tests/test_backtest_engine.py`

- [ ] **Step 1: Add tests**

Add tests proving:

```text
entry slippage and exit slippage are separate fields
partial exits charge exit slippage per partial notional
net_pnl subtracts both entry and exit slippage
synthetic one_bar_exit keeps exit_slippage as zero unless exit slippage modeling is explicitly added later
```

- [ ] **Step 2: Implement**

Add defaulted fields to `BacktestTrade`:

```python
entry_slippage: float = 0.0
exit_slippage: float = 0.0
```

For lifecycle partial exits:

```text
exit_slippage = sum(abs(partial_quantity * partial_exit_price) * slippage_bps / 10000)
```

Keep existing entry slippage calculation as `entry_slippage`.

- [ ] **Step 3: Verify**

```powershell
pytest tests/test_backtest_engine.py -q
```

Expected: tests pass.

## Task 2: MFE/MAE And Stop Timing Attribution

**Files:**
- Modify: `src/backtest/engine.py`
- Modify: `tests/test_backtest_engine.py`

- [ ] **Step 1: Add tests**

Add tests proving:

```text
LONG MFE uses max high after entry until exit
LONG MAE uses min low after entry until exit
SHORT MFE uses min low after entry until exit
SHORT MAE uses max high after entry until exit
stop_hit_bar_offset is populated for atr_tp_stop_hit and breakeven stops
```

- [ ] **Step 2: Implement**

Add defaulted fields to `BacktestTrade`:

```python
mfe_pct: float = 0.0
mae_pct: float = 0.0
stop_hit_bar_offset: int | None = None
```

Use bars from entry through exit time only.

- [ ] **Step 3: Verify**

```powershell
pytest tests/test_backtest_engine.py -q
```

Expected: tests pass.

## Task 3: Hold-Cap Experiment Grid

**Files:**
- Read/write under `reports/backtests/`

- [ ] **Step 1: Run hold cap 8**

```powershell
python scripts/run_offline_backtest.py --data-dir data/raw/binance_futures/latest_30d --timeframe 15m --strategy entry-chain --entry-chain-config configs/entry_chain.dry_run_ema_soft_lifecycle_hardened.json --exit-model atr_tp --atr-stop-mult 1.5 --tp-levels 1,2,3 --tp-fractions 0.4,0.35,0.25 --max-hold-bars 8 --default-atr-pct 0.010 --simulated-hold-bars 2 --cooldown-bars 8 --run-id latest_30d_lifecycle_v3_hold8
```

- [ ] **Step 2: Run hold cap 16**

```powershell
python scripts/run_offline_backtest.py --data-dir data/raw/binance_futures/latest_30d --timeframe 15m --strategy entry-chain --entry-chain-config configs/entry_chain.dry_run_ema_soft_lifecycle_hardened.json --exit-model atr_tp --atr-stop-mult 1.5 --tp-levels 1,2,3 --tp-fractions 0.4,0.35,0.25 --max-hold-bars 16 --default-atr-pct 0.010 --simulated-hold-bars 2 --cooldown-bars 8 --run-id latest_30d_lifecycle_v3_hold16
```

- [ ] **Step 3: Run hold cap 32**

```powershell
python scripts/run_offline_backtest.py --data-dir data/raw/binance_futures/latest_30d --timeframe 15m --strategy entry-chain --entry-chain-config configs/entry_chain.dry_run_ema_soft_lifecycle_hardened.json --exit-model atr_tp --atr-stop-mult 1.5 --tp-levels 1,2,3 --tp-fractions 0.4,0.35,0.25 --max-hold-bars 32 --default-atr-pct 0.010 --simulated-hold-bars 2 --cooldown-bars 8 --run-id latest_30d_lifecycle_v3_hold32
```

- [ ] **Step 4: Run slippage stress**

Use the best hold cap from steps 1-3 and increase slippage bps by `25%`:

```text
5 bps -> 6.25 bps
```

Run id:

```text
latest_30d_lifecycle_v3_best_hold_slip125
```

## Task 4: V3 Attribution Report

**Files:**
- Create: `docs/superpowers/reports/2026-06-19-lifecycle-v3-slippage-holdcap-attribution-report.md`

- [ ] **Step 1: Extract metrics**

For each run, report:

```text
return
win rate
profit factor
max drawdown
Sharpe
Sortino
expectancy
trade count
gross PnL
fees
entry slippage
exit slippage
net PnL
cost/gross ratio
```

- [ ] **Step 2: Attribute**

Include:

```text
per-side performance
per-symbol performance
per-exit-reason performance
TP1/TP2/TP3 sequence counts
stop-hit bar-offset distribution
MFE/MAE by exit reason
cost stress result
target gap vs 50% / 80% / 90-120
```

- [ ] **Step 3: Decision**

State clearly:

```text
whether positive expectancy survives exit-side slippage
which hold cap is best in this 30D window
whether the strategy meets target
why it misses target if it misses
what one next experiment should be
```

## Task 5: Final Verification

**Files:**
- No intended changes to `src/api/binance_client.py`.

- [ ] **Step 1: Run verification**

```powershell
python -m compileall src scripts tests
pytest tests/test_lifecycle_exit.py tests/test_backtest_engine.py tests/test_entry_chain.py tests/test_entry_chain_config.py tests/test_dry_run_configs.py tests/test_ema_indicator.py tests/test_ema_scorer.py tests/test_indicator_engine.py tests/test_indicator_spec_rules.py tests/test_data_contract.py tests/test_entry_chain_features.py tests/test_entry_chain_scoring.py tests/test_config_schema.py -q
git diff -- src/api/binance_client.py
```

Expected: compile succeeds, focused tests pass, and Binance client diff is empty.

---

## Self-Review Notes

- This plan does not promise the aggressive target will be reached.
- It attempts the next honest path toward the target by closing execution-friction optimism first.
- It freezes entry rules for lifecycle experiments to avoid hidden tuning.
- It keeps the work offline and research-only.
