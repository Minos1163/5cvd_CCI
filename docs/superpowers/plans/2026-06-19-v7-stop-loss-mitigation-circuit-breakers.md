# V7 Stop Loss Mitigation Circuit Breakers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce leveraged stop-loss damage by adding research-only partial de-risk exits and daily/weekly loss circuit breakers, then rerun V5 combined under dynamic 3x-5x leverage.

**Architecture:** Keep V5 entry acceptance and V6 leverage accounting frozen. Extend the ATR/TP lifecycle simulator with optional 0.6R adverse partial reduction and 12-bar time partial reduction. Extend the backtest engine with opt-in daily/weekly realized-loss entry blocking. Live execution and Binance connectivity remain untouched.

**Tech Stack:** Python, pytest, existing AI300 backtest/lifecycle engine, existing offline runner, Markdown reports.

---

## Success Criteria

- V7 plan is saved under `docs/superpowers/plans/`.
- Lifecycle de-risk rules are disabled by default; existing lifecycle tests remain compatible.
- Optional `0.6R` adverse partial reduction closes 50% when adverse excursion reaches `0.6R` and volume spike criteria is met.
- Optional 12-bar time reduction closes 50% when TP1 has not been reached and unrealized profit is below `0.3R`.
- Backtest engine supports opt-in daily and weekly realized-loss circuit breakers.
- Offline runner exposes CLI flags for the lifecycle and circuit-breaker research controls.
- V7 latest-30D dynamic 3x-5x run is compared against V6 dynamic 3x-5x.
- Report states whether V7 crosses 50% / 80% and whether drawdown improves.
- `src/api/binance_client.py` remains untouched.

## Research Hypothesis

- **Hypothesis:** V6 misses the return target mainly because leveraged stop-hit losses consume too much gross edge. Partial de-risk exits should reduce stop net loss and drawdown, but may also reduce later recoveries and TP ladder completions.
- **Expected regime:** V7 should help when stop-hit trades show adverse pressure and volume spike before full stop.
- **Failure mode:** Partial reductions may cut positions that would have recovered, lowering gross PnL and win rate. If so, V6 remains the better research baseline.
- **Verification command:** Compare `latest_30d_v6_v5_combined_dynamic_3x5x` with V7 dynamic 3x-5x using identical V5 entry and V6 leverage accounting.

## Frozen Controls

- Config: `configs/entry_chain.dry_run_v5_symbol_bucket_long_context.json`
- Leverage: dynamic signal leverage clamped 3x-5x
- Data: `data/raw/binance_futures/latest_30d`
- Timeframe: `15m`
- Fill: `NEXT_BAR_OPEN`
- Exit model: `atr_tp`
- Hold cap: `32`
- Fee: `5 bps`
- Slippage: `5 bps`
- TP levels: `1,2,3`
- TP fractions: `0.4,0.35,0.25`
- ATR stop multiplier: `1.5`
- Probe: disabled
- Blacklist: `XRPUSDT`

## File Structure

- Modify: `src/backtest/lifecycle_exit.py`  
  Add optional de-risk settings and partial-exit logic.
- Modify: `tests/test_lifecycle_exit.py`  
  Cover adverse partial reduction and time partial reduction.
- Modify: `src/backtest/engine.py`  
  Add daily/weekly realized-loss circuit breaker state and risk events.
- Modify: `tests/test_backtest_engine.py`  
  Cover daily loss breaker blocking new entries.
- Modify: `scripts/run_offline_backtest.py`  
  Add V7 CLI flags and pass them into `risk_constraints`.
- Create: `docs/superpowers/reports/2026-06-19-v7-stop-loss-mitigation-circuit-breakers-report.md`

## Task 1: Lifecycle Partial De-Risk Exits

**Files:**
- Modify: `src/backtest/lifecycle_exit.py`
- Modify: `tests/test_lifecycle_exit.py`

- [ ] **Step 1: Add adverse partial reduction test**

Add to `tests/test_lifecycle_exit.py`:

```python
def test_adverse_volume_spike_reduces_half_before_stop():
    result = simulate_atr_tp_exit(
        side="LONG",
        entry_time=0,
        entry_price=100.0,
        bars_after_entry=[
            bar(900, high=100.2, low=99.35, close=99.5, volume=40.0),
            bar(1800, high=99.7, low=98.8, close=99.0, volume=20.0),
        ],
        atr_pct=0.01,
        config=AtrTpExitConfig(
            atr_stop_mult=1.0,
            min_stop_pct=0.01,
            max_stop_pct=0.01,
            adverse_reduce_enabled=True,
            adverse_reduce_r=0.6,
            adverse_reduce_fraction=0.5,
            adverse_volume_spike_mult=1.5,
            adverse_volume_lookback=1,
        ),
    )

    assert result is not None
    assert result.partial_exits[0].reason == "ADVERSE_REDUCE_0_6R"
    assert result.partial_exits[0].fraction == 0.5
    assert result.partial_exits[-1].reason == "STOP_HIT"
    assert result.average_exit_price == 99.075
```

- [ ] **Step 2: Add time partial reduction test**

Add:

```python
def test_time_reduce_closes_half_when_trade_stalls_before_tp1():
    result = simulate_atr_tp_exit(
        side="LONG",
        entry_time=0,
        entry_price=100.0,
        bars_after_entry=[
            bar(900, high=100.2, low=99.9, close=100.1),
            bar(1800, high=100.2, low=99.9, close=100.15),
        ],
        atr_pct=0.01,
        config=AtrTpExitConfig(
            atr_stop_mult=1.0,
            min_stop_pct=0.01,
            max_stop_pct=0.01,
            max_hold_bars=2,
            time_reduce_enabled=True,
            time_reduce_bars=2,
            time_reduce_min_profit_r=0.3,
            time_reduce_fraction=0.5,
        ),
    )

    assert result is not None
    assert result.partial_exits[0].reason == "TIME_REDUCE_STALLED"
    assert result.partial_exits[0].fraction == 0.5
```

- [ ] **Step 3: Extend `ExitBar` protocol**

Add `volume: float` to `ExitBar` so volume spike checks are explicit.

- [ ] **Step 4: Add config fields**

Add to `AtrTpExitConfig`:

```python
adverse_reduce_enabled: bool = False
adverse_reduce_r: float = 0.6
adverse_reduce_fraction: float = 0.5
adverse_volume_spike_mult: float = 1.5
adverse_volume_lookback: int = 20
time_reduce_enabled: bool = False
time_reduce_bars: int = 12
time_reduce_min_profit_r: float = 0.3
time_reduce_fraction: float = 0.5
```

- [ ] **Step 5: Implement adverse reduction**

Inside the lifecycle loop, after stop check and before TP checks, if no TP has hit and adverse reduction has not fired:

```python
if _adverse_reduce_hit(...):
    fraction = min(remaining, cfg.adverse_reduce_fraction)
    weighted_exit += fraction * adverse_price
    remaining = round(remaining - fraction, 10)
    partial_exits.append(PartialExit(bar.timestamp, adverse_price, fraction, "ADVERSE_REDUCE_0_6R", offset))
    events.append("ADVERSE_REDUCE_0_6R")
```

Use adverse trigger price:

- LONG: `entry_price - risk_distance * adverse_reduce_r`
- SHORT: `entry_price + risk_distance * adverse_reduce_r`

- [ ] **Step 6: Implement time reduction**

Before timeout exit, when offset reaches `time_reduce_bars`, no TP1 has hit, remaining is above zero, and current profit R is below threshold, close `time_reduce_fraction` at bar close with reason `TIME_REDUCE_STALLED`.

- [ ] **Step 7: Verify Task 1**

Run:

```powershell
pytest tests/test_lifecycle_exit.py -q
```

Expected: lifecycle tests pass.

## Task 2: Daily And Weekly Loss Circuit Breakers

**Files:**
- Modify: `src/backtest/engine.py`
- Modify: `tests/test_backtest_engine.py`

- [ ] **Step 1: Add daily breaker test**

Add to `tests/test_backtest_engine.py`:

```python
def test_daily_loss_breaker_blocks_new_entries_after_threshold():
    request = valid_request(
        risk_constraints={"daily_hard_loss_pct": 0.01},
        fee_model={"fee_bps": 0},
        slippage_model={"slippage_bps": 0},
    )
    bars = {
        "BTCUSDT": [
            bar(0, open=100, close=100),
            bar(900, open=100, close=90),
            bar(1800, open=90, close=90),
            bar(2700, open=90, close=95),
        ]
    }

    result = run_backtest(request, bars, strategy_callback=always_long_direct)

    assert result.trade_count == 1
    assert any(item["payload"].get("reason") == "DAILY_HARD_LOSS_CIRCUIT" for item in result.risk_events)
```

- [ ] **Step 2: Track realized loss windows**

Inside `run_backtest()`, maintain:

```python
realized_pnl_by_day: dict[int, float] = {}
realized_pnl_by_week: dict[int, float] = {}
```

Use UTC bucket helpers:

```python
def _day_bucket(timestamp: int) -> int: return timestamp // 86400
def _week_bucket(timestamp: int) -> int: return timestamp // (7 * 86400)
```

- [ ] **Step 3: Block entries before fill simulation**

Before `_simulate_fill()`, call:

```python
breaker_reason = _circuit_breaker_reason(request, current_bar.timestamp, request.initial_capital, realized_pnl_by_day, realized_pnl_by_week)
if breaker_reason:
    risk_event = _event("RISK_BLOCKED", symbol, current_bar.timestamp, {"reason": breaker_reason, "signal": signal})
    risk_events.append(risk_event)
    events.append(risk_event)
    continue
```

- [ ] **Step 4: Update realized PnL buckets after close**

After `net_pnl` is computed:

```python
realized_pnl_by_day[_day_bucket(exit_time)] += net_pnl
realized_pnl_by_week[_week_bucket(exit_time)] += net_pnl
```

- [ ] **Step 5: Implement breaker helper**

```python
def _circuit_breaker_reason(...):
    daily = float(request.risk_constraints.get("daily_hard_loss_pct", 0.0) or 0.0)
    weekly = float(request.risk_constraints.get("weekly_hard_loss_pct", 0.0) or 0.0)
    if daily > 0 and realized_pnl_by_day.get(_day_bucket(timestamp), 0.0) <= -initial_capital * daily:
        return "DAILY_HARD_LOSS_CIRCUIT"
    if weekly > 0 and realized_pnl_by_week.get(_week_bucket(timestamp), 0.0) <= -initial_capital * weekly:
        return "WEEKLY_HARD_LOSS_CIRCUIT"
    return None
```

- [ ] **Step 6: Verify Task 2**

Run:

```powershell
pytest tests/test_backtest_engine.py -q
```

Expected: tests pass.

## Task 3: Runner Flags For V7 Controls

**Files:**
- Modify: `scripts/run_offline_backtest.py`

- [ ] **Step 1: Add lifecycle flags**

Add CLI flags:

```python
parser.add_argument("--adverse-reduce-enabled", action="store_true")
parser.add_argument("--adverse-reduce-r", type=float, default=0.6)
parser.add_argument("--adverse-reduce-fraction", type=float, default=0.5)
parser.add_argument("--adverse-volume-spike-mult", type=float, default=1.5)
parser.add_argument("--adverse-volume-lookback", type=int, default=20)
parser.add_argument("--time-reduce-enabled", action="store_true")
parser.add_argument("--time-reduce-bars", type=int, default=12)
parser.add_argument("--time-reduce-min-profit-r", type=float, default=0.3)
parser.add_argument("--time-reduce-fraction", type=float, default=0.5)
```

- [ ] **Step 2: Add circuit breaker flags**

Add:

```python
parser.add_argument("--daily-hard-loss-pct", type=float, default=0.0)
parser.add_argument("--weekly-hard-loss-pct", type=float, default=0.0)
```

- [ ] **Step 3: Pass risk constraints**

Add all V7 fields to `risk_constraints`.

- [ ] **Step 4: Wire lifecycle config**

In `_simulate_lifecycle_exit()`, pass the V7 risk constraints into `AtrTpExitConfig`.

- [ ] **Step 5: Verify Task 3**

Run:

```powershell
python -m compileall src scripts
pytest tests/test_lifecycle_exit.py tests/test_backtest_engine.py -q
```

Expected: compile succeeds and tests pass.

## Task 4: Latest 30D V7 Backtests

**Files:**
- Read/write under `reports/backtests/`.

- [ ] **Step 1: Run adverse reduce only**

```powershell
python scripts/run_offline_backtest.py --data-dir data/raw/binance_futures/latest_30d --timeframe 15m --strategy entry-chain --entry-chain-config configs/entry_chain.dry_run_v5_symbol_bucket_long_context.json --exit-model atr_tp --atr-stop-mult 1.5 --tp-levels 1,2,3 --tp-fractions 0.4,0.35,0.25 --max-hold-bars 32 --default-atr-pct 0.010 --simulated-hold-bars 2 --cooldown-bars 8 --enable-leverage-simulation --min-leverage 3 --max-leverage 5 --adverse-reduce-enabled --run-id latest_30d_v7_dynamic_3x5x_adverse_reduce
```

- [ ] **Step 2: Run time reduce only**

```powershell
python scripts/run_offline_backtest.py --data-dir data/raw/binance_futures/latest_30d --timeframe 15m --strategy entry-chain --entry-chain-config configs/entry_chain.dry_run_v5_symbol_bucket_long_context.json --exit-model atr_tp --atr-stop-mult 1.5 --tp-levels 1,2,3 --tp-fractions 0.4,0.35,0.25 --max-hold-bars 32 --default-atr-pct 0.010 --simulated-hold-bars 2 --cooldown-bars 8 --enable-leverage-simulation --min-leverage 3 --max-leverage 5 --time-reduce-enabled --run-id latest_30d_v7_dynamic_3x5x_time_reduce
```

- [ ] **Step 3: Run combined V7 with circuit breakers**

```powershell
python scripts/run_offline_backtest.py --data-dir data/raw/binance_futures/latest_30d --timeframe 15m --strategy entry-chain --entry-chain-config configs/entry_chain.dry_run_v5_symbol_bucket_long_context.json --exit-model atr_tp --atr-stop-mult 1.5 --tp-levels 1,2,3 --tp-fractions 0.4,0.35,0.25 --max-hold-bars 32 --default-atr-pct 0.010 --simulated-hold-bars 2 --cooldown-bars 8 --enable-leverage-simulation --min-leverage 3 --max-leverage 5 --adverse-reduce-enabled --time-reduce-enabled --daily-hard-loss-pct 0.05 --weekly-hard-loss-pct 0.12 --run-id latest_30d_v7_dynamic_3x5x_derisk_circuit
```

- [ ] **Step 4: Extract metrics**

Compare against:

```text
latest_30d_v6_v5_combined_dynamic_3x5x
```

Extract:

- return
- win rate
- PF
- max DD
- Sharpe
- Sortino
- expectancy
- stop count and stop net
- adverse/time reduction counts
- risk block counts
- cost/gross
- target gap

## Task 5: V7 Attribution Report

**Files:**
- Create: `docs/superpowers/reports/2026-06-19-v7-stop-loss-mitigation-circuit-breakers-report.md`

- [ ] **Step 1: Document frozen controls**

State that V5 entry and V6 leverage accounting were frozen.

- [ ] **Step 2: Compare V6 and V7**

Include headline, stop-loss, partial-exit, and risk-block tables.

- [ ] **Step 3: Decide**

Answer:

- Did V7 cross 50%?
- Did V7 reach 80% win rate?
- Did stop net loss improve?
- Did drawdown improve?
- Did de-risking cut too much gross upside?

## Task 6: Final Verification

**Files:**
- No intended changes to `src/api/binance_client.py`.

- [ ] **Step 1: Run verification**

```powershell
python -m compileall src scripts tests
pytest tests/test_lifecycle_exit.py tests/test_backtest_engine.py tests/test_entry_chain.py tests/test_entry_chain_config.py tests/test_dry_run_configs.py -q
git diff -- src/api/binance_client.py
```

Expected: compile succeeds, tests pass, and Binance client diff is empty.

- [ ] **Step 2: Final response**

Report V7 best run, whether target was met, main attribution, and paths to plan/report.
