# Exit Lifecycle Probe Symbol Side Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the research backtest's synthetic two-bar exit with an ATR stop plus three-stage TP lifecycle, then rerun the latest 30D EMA Soft strategy with Probe, XRPUSDT, and long-side hardening.

**Architecture:** Keep this research-safe and offline-only. The live Binance client and real execution path must remain untouched; the backtest engine gets an optional ATR/TP exit model selected through `BacktestRequest.risk_constraints`, while default behavior remains the existing synthetic exit. Entry-chain hardening is implemented as explicit config fields so the runner, reports, and dry-run configs can reproduce the same thresholds.

**Tech Stack:** Python, pytest, existing AI300 backtest engine, existing entry-chain config/evaluation modules, Markdown reports.

---

## Success Criteria

- Default backtests still use the existing `one_bar_exit` behavior unless `exit_model = atr_tp` is explicitly passed in `risk_constraints`.
- ATR/TP lifecycle uses only bars after the next-bar entry fill and ATR/stop inputs known at signal time.
- Lifecycle exit supports LONG and SHORT, initial stop, TP1/TP2/TP3 partial exits, breakeven after TP1, conservative same-bar ordering, and max-hold fallback.
- Entry-chain config can disable Probe, blacklist symbols such as `XRPUSDT`, and apply side-specific score threshold offsets.
- A hardened EMA Soft research config exists and is parseable.
- Latest 30D offline backtest is rerun with the hardened ATR/TP profile.
- A report compares the new lifecycle run with `latest_30d_ema_exp_c_soft`, attributes remaining gaps, and clearly states whether the user target is met.
- `src/api/binance_client.py` remains untouched.

## Risk Assumptions

- Hypothesis: EMA Soft improved entry quality, but the synthetic two-bar exit realizes too little gross profit to overcome fees and slippage.
- Expected helpful regime: directional continuation after 15m trigger where winners can reach 1R-3R.
- Failure modes: chop hits ATR stops before TP1; partial-exit approximation overstates execution quality; disabling Probe and blacklisting XRP reduces trade count below target.
- Verification command: run focused pytest, compile, then rerun latest 30D with the new `atr_tp` exit model.

## File Structure

- Create: `src/backtest/lifecycle_exit.py`  
  Pure ATR/TP exit simulation with no live dependencies.
- Create: `tests/test_lifecycle_exit.py`  
  Unit coverage for long/short TP, stop, same-bar stop-first, breakeven, and timeout.
- Modify: `src/backtest/engine.py`  
  Route optional `risk_constraints.exit_model == "atr_tp"` through lifecycle exit while preserving current default.
- Modify: `src/signals/entry_chain_config.py`  
  Add research-safe config fields: `disable_probe`, `blacklist_symbols`, `long_threshold_offset`, `short_threshold_offset`.
- Modify: `src/signals/entry_chain_gates.py`  
  Hard-block configured blacklist symbols.
- Modify: `src/signals/entry_chain.py`  
  Apply side-specific threshold offsets and optional Probe disable after base scoring.
- Modify: `tests/test_entry_chain_config.py`, `tests/test_entry_chain.py`, `tests/test_dry_run_configs.py`  
  Cover new config fields and action mapping.
- Create: `configs/entry_chain.dry_run_ema_soft_lifecycle_hardened.json`  
  EMA Soft plus Probe disabled, XRPUSDT blacklist, long threshold +10 points.
- Modify: `scripts/run_offline_backtest.py`  
  Add CLI flags for `--exit-model`, `--atr-stop-mult`, `--tp-levels`, `--tp-fractions`, `--max-hold-bars`; pass these through `risk_constraints`.
- Create: `docs/superpowers/reports/2026-06-19-exit-lifecycle-probe-hardening-backtest-report.md`  
  Attribution report after rerun.

## Task 1: ATR/TP Exit Model

**Files:**
- Create: `src/backtest/lifecycle_exit.py`
- Create: `tests/test_lifecycle_exit.py`

- [ ] **Step 1: Write failing tests**

Add tests for:

```python
def test_long_hits_tp_ladder_weighted_exit()
def test_short_hits_tp_ladder_weighted_exit()
def test_initial_stop_closes_remaining_position()
def test_same_bar_stop_and_tp_uses_conservative_stop_first()
def test_tp1_moves_stop_to_breakeven_for_remaining_position()
def test_timeout_closes_remaining_at_last_close()
```

- [ ] **Step 2: Implement minimal lifecycle simulator**

Implement:

```python
@dataclass(frozen=True)
class AtrTpExitConfig:
    atr_stop_mult: float = 1.5
    min_stop_pct: float = 0.005
    max_stop_pct: float = 0.04
    tp_levels: tuple[float, float, float] = (1.0, 2.0, 3.0)
    tp_fractions: tuple[float, float, float] = (0.30, 0.40, 0.30)
    max_hold_bars: int = 96
    breakeven_after_tp1: bool = True

@dataclass(frozen=True)
class AtrTpExitResult:
    exit_time: int
    average_exit_price: float
    reason_exit: str
    events: tuple[str, ...]
```

Use conservative same-bar order:

```text
If a bar can hit both current stop and the next TP, assume stop hits first.
```

- [ ] **Step 3: Verify**

Run:

```powershell
pytest tests/test_lifecycle_exit.py -q
```

Expected: all lifecycle tests pass.

## Task 2: Backtest Engine Exit Routing

**Files:**
- Modify: `src/backtest/engine.py`
- Modify: `tests/test_backtest_engine.py`

- [ ] **Step 1: Add engine tests**

Add one test proving default behavior remains `one_bar_exit`, and one test proving `risk_constraints={"exit_model": "atr_tp"}` can exit via TP or stop with `reason_exit` beginning `atr_tp_`.

- [ ] **Step 2: Route optional lifecycle exit**

In `_simulate_fill()`, keep existing entry fill logic. After entry fill, when `risk_constraints.exit_model == "atr_tp"`, call `simulate_atr_tp_exit()` with:

```text
side from signal
entry_price after entry slippage
bars after entry
atr_pct from signal["atr_pct"] or risk_constraints["default_atr_pct"]
config values from risk_constraints
```

Return an exit reason along with entry and exit data. Default return reason remains `one_bar_exit`.

- [ ] **Step 3: Verify**

Run:

```powershell
pytest tests/test_lifecycle_exit.py tests/test_backtest_engine.py -q
```

Expected: lifecycle and engine tests pass.

## Task 3: Entry-Chain Research Hardening

**Files:**
- Modify: `src/signals/entry_chain_config.py`
- Modify: `src/signals/entry_chain_gates.py`
- Modify: `src/signals/entry_chain.py`
- Modify: `tests/test_entry_chain_config.py`
- Modify: `tests/test_entry_chain.py`
- Modify: `tests/test_dry_run_configs.py`
- Create: `configs/entry_chain.dry_run_ema_soft_lifecycle_hardened.json`

- [ ] **Step 1: Add config tests**

Assert new fields load from JSON:

```json
{
  "disable_probe": true,
  "blacklist_symbols": ["XRPUSDT"],
  "long_threshold_offset": 10.0,
  "short_threshold_offset": 0.0
}
```

- [ ] **Step 2: Implement config fields**

Add defaults:

```python
disable_probe: bool = False
blacklist_symbols: tuple[str, ...] = ()
long_threshold_offset: float = 0.0
short_threshold_offset: float = 0.0
```

Normalize JSON lists into tuples in `from_mapping()`.

- [ ] **Step 3: Apply blacklist in gates**

In `hard_block_reason()`, block symbols whose normalized name is in `cfg.blacklist_symbols` with reason `SYMBOL_BLACKLISTED`.

- [ ] **Step 4: Apply side thresholds and Probe disable**

In `evaluate_entry_chain()`, after base weighted score:

```text
LONG applies +long_threshold_offset to direct/probe/watch threshold checks.
SHORT applies +short_threshold_offset.
```

If `disable_probe` is true, downgrade `PROBE` to `WATCH` with reason `PROBE_DISABLED`.

- [ ] **Step 5: Add hardened config**

Create `configs/entry_chain.dry_run_ema_soft_lifecycle_hardened.json` using EMA Soft plus:

```json
"disable_probe": true,
"blacklist_symbols": ["XRPUSDT"],
"long_threshold_offset": 10.0,
"short_threshold_offset": 0.0
```

- [ ] **Step 6: Verify**

Run:

```powershell
pytest tests/test_entry_chain_config.py tests/test_entry_chain.py tests/test_dry_run_configs.py -q
```

Expected: config and entry-chain tests pass.

## Task 4: Offline Runner Exit Flags

**Files:**
- Modify: `scripts/run_offline_backtest.py`

- [ ] **Step 1: Add CLI flags**

Add:

```text
--exit-model synthetic|atr_tp
--atr-stop-mult
--tp-levels
--tp-fractions
--max-hold-bars
```

Defaults must preserve current behavior:

```text
exit_model=synthetic
atr_stop_mult=1.5
tp_levels=1,2,3
tp_fractions=0.3,0.4,0.3
max_hold_bars=96
```

- [ ] **Step 2: Pass risk constraints**

Write these values into `BacktestRequest.risk_constraints`. Also include the existing simulated hold and cooldown values for comparison.

- [ ] **Step 3: Pass signal ATR**

In the entry-chain strategy return payload, include:

```python
"atr_pct": atr_pct_value
```

- [ ] **Step 4: Verify**

Run:

```powershell
python -m compileall src scripts tests
pytest tests/test_lifecycle_exit.py tests/test_backtest_engine.py tests/test_entry_chain_config.py tests/test_entry_chain.py tests/test_dry_run_configs.py -q
```

Expected: compile succeeds and focused tests pass.

## Task 5: Latest 30D Hardened Backtest

**Files:**
- Read/write under `reports/backtests/`

- [ ] **Step 1: Run hardened lifecycle profile**

Run:

```powershell
python scripts/run_offline_backtest.py --data-dir data/raw/binance_futures/latest_30d --timeframe 15m --strategy entry-chain --entry-chain-config configs/entry_chain.dry_run_ema_soft_lifecycle_hardened.json --exit-model atr_tp --atr-stop-mult 1.5 --tp-levels 1,2,3 --tp-fractions 0.3,0.4,0.3 --max-hold-bars 96 --simulated-hold-bars 2 --cooldown-bars 8 --run-id latest_30d_ema_soft_lifecycle_hardened
```

- [ ] **Step 2: If trade count drops below 60, run Probe-tightened variant**

Only if needed, create a temporary research run with Probe enabled but stricter:

```text
probe_threshold >= 78
long_threshold_offset = 10
blacklist_symbols = ["XRPUSDT"]
```

Use run id:

```text
latest_30d_ema_soft_lifecycle_probe_tight
```

- [ ] **Step 3: Extract metrics**

Compare against:

```text
latest_30d_ema_exp_c_soft
```

Record trade count, return, win rate, profit factor, max drawdown, Sharpe, Sortino, expectancy, side/mode/symbol breakdown, gross PnL, fees, slippage, and costs.

## Task 6: Attribution Report And Final Verification

**Files:**
- Create: `docs/superpowers/reports/2026-06-19-exit-lifecycle-probe-hardening-backtest-report.md`

- [ ] **Step 1: Write report**

Include:

```text
data range
symbols
entry profile
exit model
cost assumptions
comparison to EMA Soft synthetic run
target gap versus 50% return / 80% win rate / 90-120 trades
loss or underperformance attribution
remaining engine limitations
deployment decision
```

- [ ] **Step 2: Final verification**

Run:

```powershell
python -m compileall src scripts tests
pytest tests/test_lifecycle_exit.py tests/test_backtest_engine.py tests/test_entry_chain.py tests/test_entry_chain_config.py tests/test_dry_run_configs.py tests/test_ema_indicator.py tests/test_ema_scorer.py tests/test_indicator_engine.py tests/test_indicator_spec_rules.py tests/test_data_contract.py tests/test_entry_chain_features.py tests/test_entry_chain_scoring.py tests/test_config_schema.py -q
git diff -- src/api/binance_client.py
```

Expected: compile succeeds, focused tests pass, and Binance client diff is empty.

---

## Self-Review Notes

- This plan does not touch live execution, live Binance connectivity, or production order submission.
- The lifecycle model is still an approximation because `BacktestTrade` stores one weighted average exit price instead of multiple child fills.
- The plan intentionally rejects EMA200 hard gate promotion until rolling 6-12 month validation exists.
- User-provided `0.62/0.60` Probe threshold language appears normalized; this codebase uses 0-100 score thresholds, so this plan uses an explicit `disable_probe` first and a fallback tightened threshold of `78` if trade count collapses.
