# V4 Side Symbol Entry Quality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce early stop-hit losses by testing side-specific entry confirmation and simple symbol buckets while keeping V3 lifecycle accounting frozen.

**Architecture:** Preserve lifecycle V3 economics: hold32, exit-side slippage, TP fractions, ATR stop, fees, Probe disabled, and XRP blacklist. Add research-only entry-chain config fields for side-specific component minimums and watch-only symbols, then compare latest-30D profiles without touching live execution or Binance connectivity.

**Tech Stack:** Python, pytest, existing AI300 entry-chain evaluator, existing offline backtest runner, Markdown reports.

---

## Success Criteria

- Entry-chain config can express side-specific direct component minimums for `direction_1h`, `quality_30m`, `trigger_15m`, and `cvd_flow`.
- Entry-chain config can mark symbols as watch-only, producing `NO_TRADE` with `SYMBOL_WATCH_ONLY`.
- Existing configs remain parseable and behavior-compatible.
- V4 research configs are versioned separately from V3.
- Latest 30D backtests are run with lifecycle V3 accounting fixed at hold32 and base slippage 5 bps.
- Report explains whether side split and symbol buckets reduce stop-hit losses, improve PF, improve win rate, or regress the strategy.
- `src/api/binance_client.py` remains untouched.

## Frozen Controls

- Exit model: `atr_tp`
- Hold cap: `32`
- TP levels: `1,2,3`
- TP fractions: `0.4,0.35,0.25`
- ATR stop multiplier: `1.5`
- Fee: `5 bps`
- Slippage: `5 bps`
- Probe: disabled
- XRPUSDT: blacklisted
- EMA200: soft
- Fill: next bar open

## File Structure

- Modify: `src/signals/entry_chain_config.py`  
  Add side-specific component minimum fields and `watch_only_symbols`.
- Modify: `src/signals/entry_chain_gates.py`  
  Hard-block watch-only symbols.
- Modify: `src/signals/entry_chain.py`  
  Apply side-specific component minimums before generic minimums.
- Modify: `tests/test_entry_chain_config.py`, `tests/test_entry_chain.py`, `tests/test_dry_run_configs.py`  
  Cover new config fields.
- Create: `configs/entry_chain.dry_run_v4_side_split.json`  
  Stricter long confirmation, short side close to V3.
- Create: `configs/entry_chain.dry_run_v4_side_symbol_bucket.json`  
  Side split plus ADA/XMR watch-only.
- Create: `docs/superpowers/reports/2026-06-19-v4-side-symbol-entry-quality-report.md`  
  V4 attribution report.

## Task 1: Side-Specific Component Minimums

**Files:**
- Modify: `src/signals/entry_chain_config.py`
- Modify: `src/signals/entry_chain.py`
- Modify: `tests/test_entry_chain_config.py`
- Modify: `tests/test_entry_chain.py`

- [ ] **Step 1: Add config fields**

Add default `None` overrides:

```python
long_min_direction_direct_score: float | None = None
long_min_quality_direct_score: float | None = None
long_min_trigger_direct_score: float | None = None
long_min_cvd_direct_score: float | None = None
short_min_direction_direct_score: float | None = None
short_min_quality_direct_score: float | None = None
short_min_trigger_direct_score: float | None = None
short_min_cvd_direct_score: float | None = None
```

- [ ] **Step 2: Apply overrides**

In `_apply_component_minimums()`, use side-specific direct minimums when present. Add reason:

```text
SIDE_COMPONENT_MINIMUMS_LONG
SIDE_COMPONENT_MINIMUMS_SHORT
```

- [ ] **Step 3: Verify**

```powershell
pytest tests/test_entry_chain_config.py tests/test_entry_chain.py -q
```

Expected: tests pass.

## Task 2: Watch-Only Symbol Bucket

**Files:**
- Modify: `src/signals/entry_chain_config.py`
- Modify: `src/signals/entry_chain_gates.py`
- Modify: `tests/test_entry_chain.py`

- [ ] **Step 1: Add config field**

Add:

```python
watch_only_symbols: tuple[str, ...] = ()
```

Normalize JSON lists to uppercase tuples.

- [ ] **Step 2: Apply gate**

In `hard_block_reason()`, after blacklist:

```python
if symbol in cfg.watch_only_symbols:
    return "SYMBOL_WATCH_ONLY"
```

- [ ] **Step 3: Verify**

```powershell
pytest tests/test_entry_chain_config.py tests/test_entry_chain.py -q
```

Expected: tests pass.

## Task 3: V4 Research Configs

**Files:**
- Create: `configs/entry_chain.dry_run_v4_side_split.json`
- Create: `configs/entry_chain.dry_run_v4_side_symbol_bucket.json`
- Modify: `tests/test_dry_run_configs.py`

- [ ] **Step 1: Side split config**

Base on lifecycle hardened config, with:

```json
"long_threshold_offset": 14.0,
"long_min_quality_direct_score": 0.80,
"long_min_trigger_direct_score": 0.95,
"long_min_cvd_direct_score": 0.70,
"short_threshold_offset": 0.0
```

- [ ] **Step 2: Side symbol bucket config**

Base on side split config, with:

```json
"watch_only_symbols": ["ADAUSDT", "XMRUSDT"]
```

- [ ] **Step 3: Verify parseability**

```powershell
pytest tests/test_dry_run_configs.py -q
```

Expected: configs load.

## Task 4: Latest 30D V4 Backtests

**Files:**
- Read/write under `reports/backtests/`

- [ ] **Step 1: Run V3 benchmark if needed**

Use existing run:

```text
latest_30d_lifecycle_v3_hold32
```

- [ ] **Step 2: Run side split**

```powershell
python scripts/run_offline_backtest.py --data-dir data/raw/binance_futures/latest_30d --timeframe 15m --strategy entry-chain --entry-chain-config configs/entry_chain.dry_run_v4_side_split.json --exit-model atr_tp --atr-stop-mult 1.5 --tp-levels 1,2,3 --tp-fractions 0.4,0.35,0.25 --max-hold-bars 32 --default-atr-pct 0.010 --simulated-hold-bars 2 --cooldown-bars 8 --run-id latest_30d_v4_side_split
```

- [ ] **Step 3: Run side plus symbol bucket**

```powershell
python scripts/run_offline_backtest.py --data-dir data/raw/binance_futures/latest_30d --timeframe 15m --strategy entry-chain --entry-chain-config configs/entry_chain.dry_run_v4_side_symbol_bucket.json --exit-model atr_tp --atr-stop-mult 1.5 --tp-levels 1,2,3 --tp-fractions 0.4,0.35,0.25 --max-hold-bars 32 --default-atr-pct 0.010 --simulated-hold-bars 2 --cooldown-bars 8 --run-id latest_30d_v4_side_symbol_bucket
```

## Task 5: V4 Attribution Report

**Files:**
- Create: `docs/superpowers/reports/2026-06-19-v4-side-symbol-entry-quality-report.md`

- [ ] **Step 1: Compare headline metrics**

Compare:

```text
latest_30d_lifecycle_v3_hold32
latest_30d_v4_side_split
latest_30d_v4_side_symbol_bucket
```

- [ ] **Step 2: Attribute side and symbol changes**

Report:

```text
long/short trade count, return, win rate, PF proxy, stop-hit count
symbol net PnL and cost drag
stop-hit bar offsets
MFE/MAE by side and exit reason
target gap
```

- [ ] **Step 3: Decision**

State whether V4:

```text
reduces early stop hits
improves long-side quality
preserves short-side edge
improves or regresses total expectancy
meets target or not
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

- This plan changes entry acceptance only; lifecycle accounting remains frozen.
- It does not use leverage to force target.
- It keeps V3 as the benchmark and makes V4 a controlled entry-quality experiment.
