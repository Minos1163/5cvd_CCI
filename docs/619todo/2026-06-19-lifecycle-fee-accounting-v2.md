# Lifecycle Fee Accounting V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correct the ATR/TP lifecycle backtest so partial exits, fees, breakeven buffers, CLI validation, and reporting are auditable before using the lifecycle result as strategy evidence.

**Architecture:** Keep this offline-research-only and preserve the default synthetic exit behavior. `src/backtest/lifecycle_exit.py` will emit explicit partial exits; `src/backtest/engine.py` will compute gross PnL, fees, and slippage from those partial exits when `exit_model=atr_tp`; entry-chain Probe disabling will become a hard `NO_TRADE` rejection rather than a WATCH downgrade.

**Tech Stack:** Python, pytest, existing AI300 backtest engine, existing entry-chain config/evaluation modules, Markdown reports.

---

## Success Criteria

- ATR/TP lifecycle result includes explicit `partial_exits` with fraction, price, timestamp, bar offset, and reason.
- Lifecycle fees are calculated from actual partial exit notional, not from a single weighted exit.
- Breakeven after TP1 moves to `entry_price * (1 + buffer)` for LONG and `entry_price * (1 - buffer)` for SHORT.
- Default ATR/TP research parameters become `tp_fractions=(0.40,0.35,0.25)` and `max_hold_bars=16`.
- `scripts/verify_lifecycle_logic.py` proves the theoretical 65% win-rate expectancy is positive with corrected fees before running the full backtest.
- Runner CLI validates TP levels/fractions and exposes `--default-atr-pct`.
- Probe disabled returns `NO_TRADE` with reason `PROBE_DISABLED`, not `WATCH`.
- A corrected v2 latest-30D backtest report replaces the v1 conclusion with fee-audited results.
- `src/api/binance_client.py` remains untouched.

## Critical Clarification

The review correctly identifies that partial exits need explicit fee accounting. However, each TP fee must be charged on the **fractional exit notional**, not the whole original position three times. Correct lifecycle round-trip fee rate for full TP1/TP2/TP3 exit is:

```text
entry fee on 100% notional: 0.05%
TP1 fee on 40% notional:   0.02%
TP2 fee on 35% notional:   0.0175%
TP3 fee on 25% notional:   0.0125%
total:                     0.10%
```

The accounting bug is not that all three exits should each charge full notional; the bug is that the current result cannot prove whether fees were charged per partial fill. V2 must make that auditable.

## File Structure

- Create: `scripts/verify_lifecycle_logic.py`  
  Independent theoretical expectancy check before full backtest.
- Modify: `src/backtest/lifecycle_exit.py`  
  Add `PartialExit`, breakeven buffer, max hold default 16, TP fraction default 40/35/25, partial-exit metadata.
- Modify: `src/backtest/engine.py`  
  Carry lifecycle metadata through fill simulation and compute PnL/costs from partial exits.
- Modify: `tests/test_lifecycle_exit.py`  
  Add partial fees metadata, breakeven buffer, and timeout/hold bar assertions.
- Modify: `tests/test_backtest_engine.py`  
  Verify lifecycle fee accounting and partial exits in serialized trade output.
- Modify: `src/signals/entry_chain.py`  
  Make disabled Probe return `NO_TRADE`.
- Modify: `tests/test_entry_chain.py`  
  Update Probe disabled expectation.
- Modify: `scripts/run_offline_backtest.py`  
  Add CLI validation and `--default-atr-pct`; set v2 defaults.
- Modify: `configs/entry_chain.dry_run_ema_soft_lifecycle_hardened.json`  
  Keep Probe disabled/XRP blacklist/long offset; no live config changes.
- Create: `docs/superpowers/reports/2026-06-19-lifecycle-fee-accounting-v2-backtest-report.md`  
  Corrected result attribution.

## Task 0: Theory Check Before Implementation

**Files:**
- Create: `scripts/verify_lifecycle_logic.py`

- [ ] **Step 1: Add standalone expectancy script**

Implement a no-dependency script using:

```text
entry_price = 100
stop_pct = 1.5%
tp_levels = 1R/2R/3R
tp_fractions = 40%/35%/25%
fee_per_side = 5 bps
win_rate = 65%
```

Expected:

```text
avg_win_gross = 2.775%
avg_loss_gross = -1.5%
round_trip_fee = 0.10%
expectancy > 0
```

- [ ] **Step 2: Run**

```powershell
python scripts/verify_lifecycle_logic.py
```

Expected: prints positive expectancy and exits `0`.

## Task 1: Partial Exit Lifecycle Metadata

**Files:**
- Modify: `src/backtest/lifecycle_exit.py`
- Modify: `tests/test_lifecycle_exit.py`

- [ ] **Step 1: Add tests**

Add tests for:

```python
def test_partial_exits_are_recorded_for_full_tp_ladder()
def test_breakeven_price_includes_fee_buffer_for_long()
def test_breakeven_price_includes_fee_buffer_for_short()
def test_max_hold_records_bar_offset()
```

- [ ] **Step 2: Implement metadata**

Add:

```python
@dataclass(frozen=True)
class PartialExit:
    timestamp: int
    price: float
    fraction: float
    reason: str
    bar_offset: int
```

Extend `AtrTpExitResult` with:

```python
partial_exits: tuple[PartialExit, ...]
hold_bars: int
tp1_reached: bool
breakeven_active: bool
```

- [ ] **Step 3: Update defaults**

Use:

```python
tp_fractions=(0.40, 0.35, 0.25)
max_hold_bars=16
breakeven_buffer_pct=0.001
default_atr_pct=0.010
max_stop_pct=0.03
```

- [ ] **Step 4: Verify**

```powershell
pytest tests/test_lifecycle_exit.py -q
```

Expected: all lifecycle tests pass.

## Task 2: Engine Fee Accounting From Partial Exits

**Files:**
- Modify: `src/backtest/engine.py`
- Modify: `tests/test_backtest_engine.py`

- [ ] **Step 1: Add tests**

Add tests proving:

```text
full TP ladder produces 3 partial exits
fees = entry fee + sum(exit_fraction_notional fees)
BacktestTrade.partial_exits serializes to JSON
synthetic one_bar_exit still has partial_exits = []
```

- [ ] **Step 2: Extend trade model compatibly**

Add defaulted fields to `BacktestTrade`:

```python
partial_exits: tuple[dict[str, Any], ...] = ()
total_fees_pct: float = 0.0
tp1_reached: bool = False
breakeven_active: bool = False
hold_bars: int = 0
```

- [ ] **Step 3: Compute lifecycle PnL/costs from partial exits**

For lifecycle trades:

```text
gross_pnl = sum(gross for each partial quantity)
fees = entry notional fee + sum(exit partial notional fee)
slippage remains entry slippage only until explicit exit slippage is modeled
```

- [ ] **Step 4: Verify**

```powershell
pytest tests/test_lifecycle_exit.py tests/test_backtest_engine.py -q
```

Expected: tests pass.

## Task 3: Entry-Chain Probe Rejection

**Files:**
- Modify: `src/signals/entry_chain.py`
- Modify: `tests/test_entry_chain.py`

- [ ] **Step 1: Update test**

Change Probe-disabled expectation:

```python
assert decision.action == "NO_TRADE"
assert decision.risk_allowed is False
assert "PROBE_DISABLED" in decision.reasons
```

- [ ] **Step 2: Implement**

Make `_apply_probe_disable()` return `NO_TRADE` instead of `WATCH`.

- [ ] **Step 3: Verify**

```powershell
pytest tests/test_entry_chain.py -q
```

Expected: entry-chain tests pass.

## Task 4: Runner CLI Validation And Defaults

**Files:**
- Modify: `scripts/run_offline_backtest.py`

- [ ] **Step 1: Add validation**

Validate when `--exit-model atr_tp`:

```text
tp_levels length == tp_fractions length == 3
tp_fractions sum == 1.0
all tp_levels > 0
0 < atr_stop_mult <= 5
default_atr_pct > 0
max_hold_bars > 0
```

- [ ] **Step 2: Add v2 defaults**

Use:

```text
--tp-fractions default 0.4,0.35,0.25
--max-hold-bars default 16
--default-atr-pct default 0.010
```

- [ ] **Step 3: Pass default ATR**

Add `default_atr_pct` into `risk_constraints` and use it only if a signal lacks `atr_pct`.

- [ ] **Step 4: Verify**

```powershell
python -m compileall scripts src tests
pytest tests/test_lifecycle_exit.py tests/test_backtest_engine.py tests/test_entry_chain.py -q
```

Expected: compile and tests pass.

## Task 5: Corrected Latest 30D V2 Backtest

**Files:**
- Read/write under `reports/backtests/`
- Create: `docs/superpowers/reports/2026-06-19-lifecycle-fee-accounting-v2-backtest-report.md`

- [ ] **Step 1: Run theory check**

```powershell
python scripts/verify_lifecycle_logic.py
```

- [ ] **Step 2: Run corrected v2 backtest**

```powershell
python scripts/run_offline_backtest.py --data-dir data/raw/binance_futures/latest_30d --timeframe 15m --strategy entry-chain --entry-chain-config configs/entry_chain.dry_run_ema_soft_lifecycle_hardened.json --exit-model atr_tp --atr-stop-mult 1.5 --tp-levels 1,2,3 --tp-fractions 0.4,0.35,0.25 --max-hold-bars 16 --default-atr-pct 0.010 --simulated-hold-bars 2 --cooldown-bars 8 --run-id latest_30d_ema_soft_lifecycle_hardened_v2
```

- [ ] **Step 3: If trade count is below 30**

Do not tune silently. Record the failure and run one explicit comparison:

```text
latest_30d_ema_soft_lifecycle_hardened_v2_probe_tight
```

with Probe enabled and `probe_threshold >= 78`.

- [ ] **Step 4: Write report**

Include:

```text
fee accounting correction
partial exit distribution
TP1/TP2/TP3 hit distribution
average hold bars
cost/gross ratio
target gates yes/no
deployment decision
```

## Task 6: Final Verification

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

- This plan accepts the review's critical concern and fixes auditability.
- It does not claim v1 results are valid after the accounting concern; v2 rerun supersedes v1.
- It keeps all changes offline and research-only.
- It explicitly distinguishes partial-exit fee accounting from the incorrect idea of charging full notional on every TP batch.
