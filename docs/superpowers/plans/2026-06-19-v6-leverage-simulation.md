# V6 Leverage Simulation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add research-only 3x-5x leverage simulation to the offline backtest pipeline and evaluate V5 combined under explicit leveraged accounting.

**Architecture:** Keep V5 entry and V3 lifecycle accounting frozen. Add opt-in leverage simulation in the backtest engine: signal notional remains margin notional, effective trade notional becomes `margin_notional * leverage`, and gross PnL, fees, slippage, and funding are computed from effective notional. The runner passes entry-chain-selected leverage into signals and exposes CLI controls for fixed 3x/4x/5x research runs. Live Binance connectivity and execution adapters remain untouched.

**Tech Stack:** Python, pytest, existing AI300 backtest engine, existing offline runner, Markdown reports.

---

## Success Criteria

- Leverage simulation is disabled by default; existing tests and unlevered V5 results remain comparable.
- `scripts/run_offline_backtest.py` supports `--enable-leverage-simulation`, `--fixed-leverage`, `--min-leverage`, and `--max-leverage`.
- Entry-chain offline signals include `leverage` from `EntryChainDecision`.
- `BacktestTrade` records `leverage`, `margin_notional`, `effective_notional`, and `margin_call_proxy`.
- When leverage simulation is enabled, quantity and all economic terms use effective notional.
- Focused tests prove unlevered behavior is unchanged and 3x leverage scales gross PnL, fees, slippage, and net PnL from effective notional.
- Latest 30D V5 combined is rerun at 3x, 4x, 5x, and dynamic 3-5x.
- A V6 report states whether leveraged V5 reaches the user's target and highlights drawdown / margin-call proxy risk.
- `src/api/binance_client.py` remains untouched.

## Research Hypothesis

- **Hypothesis:** V5 has enough fee-adjusted edge that 3x-5x leverage can lift nominal return while preserving trade count and win rate, but drawdown and tail loss will scale materially.
- **Expected regime:** 3x may approach a realistic aggressive monthly band, while 5x may expose unacceptable drawdown or margin-call proxy risk.
- **Failure mode:** Leveraged return may improve but risk-adjusted quality may degrade or margin-call proxy events may appear. If so, leverage should stay research-only.
- **Verification command:** Run V5 combined with frozen lifecycle controls under 3x, 4x, 5x, and signal-selected dynamic leverage.

## Frozen Controls

- Config: `configs/entry_chain.dry_run_v5_symbol_bucket_long_context.json`
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
- Default ATR pct: `0.010`
- Cooldown bars: `8`

## File Structure

- Modify: `src/backtest/engine.py`  
  Add leverage fields to `BacktestTrade`, leverage resolution helpers, effective-notional accounting, and margin-call proxy.
- Modify: `scripts/run_offline_backtest.py`  
  Add leverage CLI flags, pass leverage controls to `risk_constraints`, and include decision leverage in entry-chain signals.
- Modify: `tests/test_backtest_engine.py`  
  Add leverage accounting tests.
- Create: `docs/superpowers/reports/2026-06-19-v6-leverage-simulation-report.md`  
  Summarize leveraged V5 runs and target gap.

## Task 1: Backtest Leverage Accounting

**Files:**
- Modify: `src/backtest/engine.py`
- Modify: `tests/test_backtest_engine.py`

- [ ] **Step 1: Add failing leverage accounting test**

Add to `tests/test_backtest_engine.py`:

```python
def test_leverage_simulation_uses_effective_notional_for_economics():
    request = valid_request(
        risk_constraints={"enable_leverage_simulation": True, "fixed_leverage": 3},
        fee_model={"fee_bps": 5},
        slippage_model={"slippage_bps": 0},
    )
    bars = {"BTCUSDT": [bar(0, open=100, close=100), bar(900, open=100, close=101), bar(1800, open=110, close=110)]}

    result = run_backtest(request, bars, strategy_callback=always_long_direct)
    trade = result.trades[0]

    assert trade.leverage == 3
    assert trade.margin_notional == 1000
    assert trade.effective_notional == 3000
    assert round(trade.quantity, 6) == 29.97003
    assert trade.gross_pnl > 290
    assert trade.fees > 3
    assert trade.net_pnl == trade.gross_pnl - trade.fees - trade.slippage - trade.funding
```

- [ ] **Step 2: Add unchanged default test**

Add:

```python
def test_leverage_simulation_is_disabled_by_default():
    result = run_backtest(
        valid_request(),
        {"BTCUSDT": [bar(0, open=100, close=100), bar(900, open=100, close=101), bar(1800, open=110, close=110)]},
        strategy_callback=always_long_direct,
    )
    trade = result.trades[0]

    assert trade.leverage == 1
    assert trade.margin_notional == 1000
    assert trade.effective_notional == 1000
```

- [ ] **Step 3: Extend `BacktestTrade`**

Add fields with defaults:

```python
leverage: float = 1.0
margin_notional: float = 0.0
effective_notional: float = 0.0
margin_call_proxy: bool = False
```

- [ ] **Step 4: Implement leverage resolver**

Add helpers:

```python
def _resolve_leverage(request: BacktestRequest, signal: Mapping[str, Any]) -> float:
    if not bool(request.risk_constraints.get("enable_leverage_simulation", False)):
        return 1.0
    fixed = request.risk_constraints.get("fixed_leverage")
    if fixed is not None:
        leverage = float(fixed)
    else:
        leverage = float(signal.get("leverage", 1.0) or 1.0)
    minimum = float(request.risk_constraints.get("min_leverage", 1.0) or 1.0)
    maximum = float(request.risk_constraints.get("max_leverage", 5.0) or 5.0)
    return max(minimum, min(maximum, leverage))


def _margin_call_proxy(mae_pct: float, leverage: float, maintenance_margin_pct: float) -> bool:
    if leverage <= 1:
        return False
    liquidation_buffer = max(0.0, (1.0 / leverage) - maintenance_margin_pct)
    return abs(min(0.0, mae_pct)) >= liquidation_buffer
```

- [ ] **Step 5: Use effective notional**

In the trade construction block:

```python
margin_notional = float(signal.get("notional", request.capital_constraints.get("notional_per_trade", 100.0)) or 100.0)
leverage = _resolve_leverage(request, signal)
effective_notional = margin_notional * leverage
quantity = effective_notional / entry_price if entry_price > 0 else 0.0
gross_pnl = _trade_gross_pnl(...)
fees = _trade_fees(effective_notional, ...)
funding = fee(effective_notional, funding_bps)
```

Keep `margin_notional` for capital allocation reporting.

- [ ] **Step 6: Store margin-call proxy**

Compute `mfe_pct` and `mae_pct` once before `BacktestTrade`, then set:

```python
margin_call_proxy=_margin_call_proxy(mae_pct, leverage, float(request.risk_constraints.get("maintenance_margin_pct", 0.005) or 0.005))
```

- [ ] **Step 7: Verify Task 1**

Run:

```powershell
pytest tests/test_backtest_engine.py -q
```

Expected: tests pass.

## Task 2: Offline Runner Leverage Controls

**Files:**
- Modify: `scripts/run_offline_backtest.py`

- [ ] **Step 1: Add CLI flags**

Add:

```python
parser.add_argument("--enable-leverage-simulation", action="store_true")
parser.add_argument("--fixed-leverage", type=float, default=None)
parser.add_argument("--min-leverage", type=float, default=1.0)
parser.add_argument("--max-leverage", type=float, default=5.0)
parser.add_argument("--maintenance-margin-pct", type=float, default=0.005)
```

- [ ] **Step 2: Add validation**

In `validate_lifecycle_args()` or a new helper:

```python
if args.fixed_leverage is not None and args.fixed_leverage <= 0:
    raise ValueError("--fixed-leverage must be positive")
if args.min_leverage <= 0 or args.max_leverage < args.min_leverage:
    raise ValueError("--min-leverage/--max-leverage range is invalid")
if args.max_leverage > 5.0:
    raise ValueError("--max-leverage must be <= 5.0 for this research lane")
```

- [ ] **Step 3: Pass risk constraints**

Add to `risk_constraints`:

```python
"enable_leverage_simulation": args.enable_leverage_simulation,
"fixed_leverage": args.fixed_leverage,
"min_leverage": args.min_leverage,
"max_leverage": args.max_leverage,
"maintenance_margin_pct": args.maintenance_margin_pct,
```

- [ ] **Step 4: Include entry-chain leverage in signal**

In the executable signal mapping, add:

```python
"leverage": decision.leverage,
```

- [ ] **Step 5: Verify Task 2**

Run:

```powershell
python -m compileall scripts src
pytest tests/test_backtest_engine.py -q
```

Expected: compile succeeds and tests pass.

## Task 3: Latest 30D Leveraged V5 Runs

**Files:**
- Read/write under `reports/backtests/`.

- [ ] **Step 1: Run fixed 3x**

```powershell
python scripts/run_offline_backtest.py --data-dir data/raw/binance_futures/latest_30d --timeframe 15m --strategy entry-chain --entry-chain-config configs/entry_chain.dry_run_v5_symbol_bucket_long_context.json --exit-model atr_tp --atr-stop-mult 1.5 --tp-levels 1,2,3 --tp-fractions 0.4,0.35,0.25 --max-hold-bars 32 --default-atr-pct 0.010 --simulated-hold-bars 2 --cooldown-bars 8 --enable-leverage-simulation --fixed-leverage 3 --run-id latest_30d_v6_v5_combined_fixed_3x
```

- [ ] **Step 2: Run fixed 4x**

```powershell
python scripts/run_offline_backtest.py --data-dir data/raw/binance_futures/latest_30d --timeframe 15m --strategy entry-chain --entry-chain-config configs/entry_chain.dry_run_v5_symbol_bucket_long_context.json --exit-model atr_tp --atr-stop-mult 1.5 --tp-levels 1,2,3 --tp-fractions 0.4,0.35,0.25 --max-hold-bars 32 --default-atr-pct 0.010 --simulated-hold-bars 2 --cooldown-bars 8 --enable-leverage-simulation --fixed-leverage 4 --run-id latest_30d_v6_v5_combined_fixed_4x
```

- [ ] **Step 3: Run fixed 5x**

```powershell
python scripts/run_offline_backtest.py --data-dir data/raw/binance_futures/latest_30d --timeframe 15m --strategy entry-chain --entry-chain-config configs/entry_chain.dry_run_v5_symbol_bucket_long_context.json --exit-model atr_tp --atr-stop-mult 1.5 --tp-levels 1,2,3 --tp-fractions 0.4,0.35,0.25 --max-hold-bars 32 --default-atr-pct 0.010 --simulated-hold-bars 2 --cooldown-bars 8 --enable-leverage-simulation --fixed-leverage 5 --run-id latest_30d_v6_v5_combined_fixed_5x
```

- [ ] **Step 4: Run dynamic signal leverage**

```powershell
python scripts/run_offline_backtest.py --data-dir data/raw/binance_futures/latest_30d --timeframe 15m --strategy entry-chain --entry-chain-config configs/entry_chain.dry_run_v5_symbol_bucket_long_context.json --exit-model atr_tp --atr-stop-mult 1.5 --tp-levels 1,2,3 --tp-fractions 0.4,0.35,0.25 --max-hold-bars 32 --default-atr-pct 0.010 --simulated-hold-bars 2 --cooldown-bars 8 --enable-leverage-simulation --min-leverage 3 --max-leverage 5 --run-id latest_30d_v6_v5_combined_dynamic_3x5x
```

- [ ] **Step 5: Extract leveraged metrics**

For each run, extract:

- return
- trade count
- win rate
- PF
- max drawdown
- Sharpe
- Sortino
- expectancy
- gross PnL
- fees
- slippage
- cost/gross
- side split
- symbol split
- stop-hit count and net
- leverage distribution
- margin-call proxy count

## Task 4: V6 Leverage Report

**Files:**
- Create: `docs/superpowers/reports/2026-06-19-v6-leverage-simulation-report.md`

- [ ] **Step 1: Document accounting**

State explicitly:

- `notional` is treated as margin notional.
- `effective_notional = margin_notional * leverage`.
- PnL, fees, slippage, funding, quantity use effective notional.
- This is still not a full exchange liquidation engine.

- [ ] **Step 2: Compare unlevered and leveraged V5**

Include V5 unlevered, fixed 3x, fixed 4x, fixed 5x, and dynamic 3-5x.

- [ ] **Step 3: Target and safety conclusion**

Answer:

- Does any run reach `50%+` return?
- Does win rate reach `80%+`?
- Are margin-call proxy events present?
- Which leverage tier is the best research candidate?

## Task 5: Final Verification

**Files:**
- No intended changes to `src/api/binance_client.py`.

- [ ] **Step 1: Run verification**

```powershell
python -m compileall src scripts tests
pytest tests/test_backtest_engine.py tests/test_entry_chain.py tests/test_entry_chain_config.py tests/test_dry_run_configs.py tests/test_lifecycle_exit.py -q
git diff -- src/api/binance_client.py
```

Expected: compile succeeds, tests pass, and Binance client diff is empty.

- [ ] **Step 2: Final response**

Report best leveraged run, target status, risk caveat, and paths to V6 plan/report.
