# DeepSeek Entry Chain Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert DeepSeek's review into a shared entry gate and scoring layer, wire it into offline backtest, and expose a live-safe execution pre-check path.

**Architecture:** Add a standalone `src/signals/entry_chain.py` module that evaluates hard gates, weighted scores, trade budgets, symbol caps, liquidity, cooldown, leverage caps, and sizing hints. The offline backtest script can choose `baseline` or `entry-chain`, preserving the first run for comparison. Live execution receives the same decision as an auditable snapshot and rejects entry orders that lack approval, exceed approved mode, or exceed approved notional; it does not auto-submit real exchange orders.

**Tech Stack:** Python dataclasses, pytest, existing `src.backtest.engine`, offline Binance Futures CSV data.

---

## Scope

This plan implements Phase 1 only:

- Add a DeepSeek-inspired `ChainOfGates` / `ScoreBoard` module.
- Preserve `src/api/binance_client.py` untouched.
- Do not modify live exchange adapters or production config paths.
- Add live-safe execution pre-checks so real entry requests must carry entry-chain approval.
- Add deterministic tests for hard gates, dynamic weights, thresholds, cooldown, exposure caps, and leverage caps.
- Add `--strategy entry-chain` to `scripts/run_offline_backtest.py`.
- Run a second latest-30D offline backtest and report whether trade count and loss profile improved.

Deferred to later phases:

- Full position lifecycle with ATR stop, TP ladder, breakeven, trailing stop, and time stop.
- Time-synchronized portfolio engine refactor.
- Depth-book based slippage; first phase uses available OHLCV fields and an explicit approximation.
- 6-12 month OOS, Monte Carlo, and sensitivity studies.
- Live exchange submission, live strategy scheduler, and gray launch controls.

## File Structure

- Create: `src/signals/entry_chain.py`
  - Owns DeepSeek hard gates, dynamic weights, score-to-action mapping, trade budget, symbol caps, leverage cap, and sizing hints.
- Create: `tests/test_entry_chain.py`
  - Focused unit tests for the new research module.
- Modify: `scripts/run_offline_backtest.py`
  - Adds `--strategy baseline|entry-chain`, multi-timeframe CSV loading for the entry-chain path, simple no-lookahead feature derivation, and summary fields.
- Modify: `src/execution/execution_engine.py`
  - Adds optional `entry_chain_snapshot` to `ExecutionRequest` and rejects entry orders that bypass or exceed entry-chain approval.
- Create: `src/execution/live_entry_chain_adapter.py`
  - Builds live-safe order drafts from `EntryChainDecision`; rejected decisions produce audit-only drafts.
- Create: `tests/test_live_entry_chain_adapter.py`
  - Verifies the live adapter produces requests only for approved `PROBE` / `DIRECT` decisions.
- Do not modify: `src/api/binance_client.py`

## Acceptance Criteria

- `pytest tests/test_entry_chain.py -q` passes.
- `python -m compileall src scripts tests` passes.
- `python scripts/run_offline_backtest.py --strategy entry-chain --run-id latest_30d_round2_entry_chain` completes.
- Entry requests submitted through `ExecutionEngine` require `entry_chain_snapshot`.
- `PROBE` approval cannot be upgraded to `DIRECT` by execution.
- Requested entry notional cannot exceed `entry_chain_snapshot["notional_hint"]`.
- The report clearly labels limitations:
  - entry-chain-v1-lite is still research-only;
  - current backtest engine is symbol-sequential, not fully portfolio time-synchronized;
  - exits are still synthetic one-bar exits until the backtest engine lifecycle is upgraded.
- `git diff -- src/api/binance_client.py` is empty.

## Task 1: Entry Chain Module

**Files:**
- Create: `src/signals/entry_chain.py`
- Test: `tests/test_entry_chain.py`

- [ ] **Step 1: Write failing tests for DeepSeek gates and weights**

Add tests covering:

```python
from src.signals.entry_chain import EntryChainConfig, EntryChainContext, evaluate_entry_chain


def candidate(**overrides):
    base = EntryChainContext(
        symbol="SOLUSDT",
        timestamp=1,
        side="LONG",
        component_scores={
            "background_4h": 1.0,
            "direction_1h": 1.0,
            "quality_30m": 1.0,
            "trigger_15m": 1.0,
            "cvd_flow": 1.0,
            "volatility_stop": 1.0,
            "liquidity_execution": 1.0,
            "market_regime": 1.0,
        },
        quote_volume_24h=200_000_000,
        atr_pct=0.018,
        expected_order_size=2_000,
        account_equity=10_000,
        available_margin=8_000,
    )
    return base.with_updates(**overrides)


def test_macro_daily_drop_blocks_direct_but_allows_probe():
    decision = evaluate_entry_chain(candidate(macro_daily_drop_pct=-0.06))
    assert decision.action == "PROBE"
    assert "MACRO_DAILY_RISK_DIRECT_BLOCK" in decision.reasons


def test_weekly_macro_drop_blocks_all_trades():
    decision = evaluate_entry_chain(candidate(macro_weekly_drop_pct=-0.16))
    assert decision.action == "NO_TRADE"
    assert "MACRO_WEEKLY_RISK" in decision.reasons


def test_high_volatility_uses_dynamic_weights():
    decision = evaluate_entry_chain(candidate(atr_pct=0.04))
    assert decision.weights["volatility_stop"] == 20
    assert decision.weights["cvd_flow"] == 10
    assert round(sum(decision.weights.values()), 6) == 100


def test_high_beta_symbol_is_probe_only_and_capped():
    decision = evaluate_entry_chain(candidate(symbol="HYPEUSDT"))
    assert decision.action == "PROBE"
    assert decision.max_symbol_exposure_pct == 0.10
    assert "HIGH_BETA_PROBE_ONLY" in decision.reasons
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `pytest tests/test_entry_chain.py -q`

Expected: FAIL because `src.signals.entry_chain` does not exist.

- [ ] **Step 3: Implement the module**

Implement:

```python
@dataclass(frozen=True)
class EntryChainConfig:
    direct_threshold: float = 82.0
    probe_threshold: float = 70.0
    watch_threshold: float = 60.0
    high_vol_atr_pct: float = 0.035
    low_vol_atr_pct: float = 0.010
    max_active_symbols: int = 5
    daily_max_trades_base: int = 4


@dataclass(frozen=True)
class EntryChainContext:
    symbol: str
    timestamp: int
    side: str
    component_scores: Mapping[str, float]
    quote_volume_24h: float
    atr_pct: float
    expected_order_size: float
    account_equity: float
    available_margin: float
    ...
```

The module must:

- Use DeepSeek weights: 4H 8, 1H 25, 30m 22, 15m 12, CVD 18, volatility 10, liquidity 3, market 2.
- For ATR% > 3.5%, set volatility weight to 20 and CVD weight to 10, then rescale the rest to sum to 100.
- For ATR% < 1.0%, set 15m trigger weight to 18 and rescale the rest while CVD stays at 18.
- Block direct on daily macro risk and all trades on weekly macro risk.
- Block current and next two bars for wick anomaly.
- Apply liquidity ratio gates: direct forbidden below 20, probe forbidden below 8.
- Enforce max active symbols, same-symbol daily trade budget, dynamic daily trade budget, cooldown, symbol exposure caps, and rolling-Sharpe leverage caps.
- Return a dict-compatible decision with action, side, score, score breakdown, weights, reasons, leverage, max exposure pct, notional hint, and `risk_allowed`.

- [ ] **Step 4: Run unit tests**

Run: `pytest tests/test_entry_chain.py -q`

Expected: PASS.

## Task 2: Offline Backtest Integration

**Files:**
- Modify: `scripts/run_offline_backtest.py`
- Test: `tests/test_entry_chain.py`

- [ ] **Step 1: Add strategy selector**

Add CLI:

```python
parser.add_argument("--strategy", default="baseline", choices=["baseline", "entry-chain"])
```

Use:

```python
strategy_callback = baseline_momentum_strategy
strategy_name = "ai300_offline_baseline"
strategy_version = "offline-baseline-v1"
if args.strategy == "entry-chain":
    strategy_callback = build_entry_chain_strategy(...)
    strategy_name = "ai300_deepseek_entry_chain"
    strategy_version = "entry-chain-v1-lite"
```

- [ ] **Step 2: Add no-lookahead multi-timeframe loading**

Load `15m`, `30m`, `1h`, and `4h` CSVs for each symbol when available. When evaluating a 15m bar, only use higher-timeframe bars with `timestamp <= current_bar.timestamp`.

- [ ] **Step 3: Build entry-chain callback**

The callback should:

- derive simple completed-bar features from prior bars only;
- compute side from 1H momentum;
- compute component scores from 4H/1H/30m/15m direction agreement, 15m trigger, volume proxy CVD, ATR%, and quote volume proxy;
- maintain a script-local research throttle state for daily count and per-symbol cooldown;
- call `evaluate_entry_chain`;
- return `NO_TRADE`, `WAIT`, `PROBE`, or `DIRECT` in the shape expected by `src.backtest.engine`.

- [ ] **Step 4: Preserve baseline**

Baseline behavior must remain available with:

```powershell
python scripts/run_offline_backtest.py --strategy baseline --run-id latest_30d_round1_recheck
```

- [ ] **Step 5: Run backtest**

Run:

```powershell
python scripts/run_offline_backtest.py --data-dir data/raw/binance_futures/latest_30d --timeframe 15m --strategy entry-chain --run-id latest_30d_round2_entry_chain
```

Expected: completes and writes `reports/backtests/latest_30d_round2_entry_chain`.

## Task 3: Verification And Report

**Files:**
- Inspect: `reports/backtests/latest_30d_round2_entry_chain/performance_summary.md`
- Inspect: `reports/backtests/latest_30d_round2_entry_chain/backtest_result.json`
- Inspect: `src/api/binance_client.py`

- [ ] **Step 1: Run verification**

Run:

```powershell
pytest tests/test_entry_chain.py -q
python -m compileall src scripts tests
git diff -- src/api/binance_client.py
```

Expected:

- tests pass;
- compileall passes;
- Binance client diff is empty.

- [ ] **Step 2: Compare metrics**

Compare Round 1 vs Round 2:

- trade count;
- win rate;
- profit factor;
- Sharpe;
- max drawdown;
- final equity;
- expectancy;
- cost drag if available.

- [ ] **Step 3: Final interpretation**

Report:

- whether trade frequency moved toward 90-120 trades per 30 days;
- whether win rate and profit factor improved;
- whether the user target is met or still not met;
- which limitations prevent live-readiness.

## Self-Review

- Spec coverage: DeepSeek's highest-priority chapters 2, 4, and 5 are covered in Phase 1. Exit optimization, Monte Carlo, OOS, and live gray launch are intentionally deferred.
- Placeholder scan: no task relies on undefined future work for the Phase 1 deliverable.
- Risk review: the plan avoids live execution, exchange adapters, and `src/api/binance_client.py`; the offline callback uses completed bars only and keeps same next-bar fill assumptions as the existing backtest engine.
