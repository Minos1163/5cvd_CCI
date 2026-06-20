# V5 Symbol Bucket Long Context Quality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Optimize the current V3 hold32 lifecycle baseline by isolating symbol-bucket value first, then testing a context-aware long-entry quality layer that penalizes chase-prone longs without using V4's blunt hard threshold tightening.

**Architecture:** Keep V3 lifecycle accounting frozen: ATR/TP exit, hold32, partial-exit fees, entry/exit slippage, MFE/MAE, Probe disabled, XRP blacklist, and next-bar-open fills. Add research-only entry controls in the entry-chain config and offline runner: one config for pure ADA/XMR watch-only, and one config that applies long-only score discounts from completed 15m bars before action selection. Do not modify live Binance connectivity or production execution paths.

**Tech Stack:** Python, pytest, existing AI300 entry-chain modules, existing offline backtest runner, Markdown reports.

---

## Success Criteria

- A V5 plan is saved under `docs/superpowers/plans/`.
- `configs/entry_chain.dry_run_v5_symbol_bucket_only.json` loads and differs from V3 only by `watch_only_symbols: ["ADAUSDT", "XMRUSDT"]`.
- `configs/entry_chain.dry_run_v5_long_context_discount.json` loads and enables long-only context discounts without V4 side-specific hard minima.
- Long context discounts use only completed 15m candles available at decision time; no future bars and no same-bar fill assumptions are introduced.
- Unit tests prove that long context discounts reduce relevant component scores, add reason codes, and do not affect shorts when enabled.
- Latest 30D backtests compare V3, V5 symbol-bucket-only, V5 long-context-only, and V5 combined if useful.
- A V5 report explains target gap, side/symbol attribution, stop-hit behavior, cost drag, and whether any V5 variant beats V3.
- `src/api/binance_client.py` remains untouched.

## File Structure

- Modify: `src/signals/entry_chain_config.py`  
  Add opt-in V5 long-context discount fields.
- Modify: `src/signals/entry_chain.py`  
  Add completed-bar-derived context flags to `EntryChainContext` and apply long-only score discounts before scoring.
- Modify: `src/signals/entry_chain_features.py`  
  Add small helpers to compute completed-bar-only long overextension, upper-wick, chase, and low-liquidity-session flags.
- Modify: `scripts/run_offline_backtest.py`  
  Populate the new `EntryChainContext` flags from completed 15m bars.
- Create: `configs/entry_chain.dry_run_v5_symbol_bucket_only.json`  
  V3 baseline plus ADA/XMR watch-only, no V4 long hard minima.
- Create: `configs/entry_chain.dry_run_v5_long_context_discount.json`  
  V3 baseline plus context-aware long discounts.
- Create: `configs/entry_chain.dry_run_v5_symbol_bucket_long_context.json`  
  Combined symbol bucket and long context discount for an interaction test.
- Modify: `tests/test_entry_chain.py`  
  Cover long-context discounts and short-side non-effect.
- Modify: `tests/test_entry_chain_config.py`  
  Cover JSON loading of V5 config fields.
- Modify: `tests/test_dry_run_configs.py`  
  Cover V5 config parseability and ensure V5 avoids V4 hard minima.
- Create: `docs/superpowers/reports/2026-06-19-v5-symbol-bucket-long-context-quality-report.md`  
  Summarize backtests and attribution.

## Research Hypothesis

- **Hypothesis:** V4 regressed because static long thresholds removed some useful long gross edge while failing to remove early stop-hit longs. V5 should preserve V3's base long threshold profile, then selectively penalize only chase-prone long contexts.
- **Expected regime:** V5 should help most in windows where altcoin longs fail shortly after overextended 15m moves or reversal-wick candles.
- **Failure mode:** V5 may reduce gross PnL more than it reduces costs or stop hits. If so, V3 remains the baseline and long-context filters must be redesigned around lifecycle diagnostics rather than score discounts.
- **Verification command:** Run the latest 30D V5 backtests with the frozen V3 lifecycle command set and compare return, win rate, PF, DD, expectancy, side/symbol attribution, cost/gross, MFE/MAE, and stop-hit counts.

## Frozen V3 Controls

- Data: `data/raw/binance_futures/latest_30d`
- Timeframe: `15m`
- Fill: `NEXT_BAR_OPEN`
- Exit model: `atr_tp`
- ATR stop multiplier: `1.5`
- TP levels: `1,2,3`
- TP fractions: `0.4,0.35,0.25`
- Max hold bars: `32`
- Default ATR pct: `0.010`
- Fee: `5 bps`
- Slippage: `5 bps`, including exit-side partial slippage
- Cooldown bars: `8`
- Probe: disabled
- Blacklist: `XRPUSDT`

## Task 1: V5 Config And Long Context Contract

**Files:**
- Modify: `src/signals/entry_chain_config.py`
- Modify: `tests/test_entry_chain_config.py`
- Create: `configs/entry_chain.dry_run_v5_symbol_bucket_only.json`
- Create: `configs/entry_chain.dry_run_v5_long_context_discount.json`
- Create: `configs/entry_chain.dry_run_v5_symbol_bucket_long_context.json`
- Modify: `tests/test_dry_run_configs.py`

- [ ] **Step 1: Add failing config loader test**

Add to `tests/test_entry_chain_config.py`:

```python
def test_load_v5_long_context_discount_fields(tmp_path):
    path = tmp_path / "entry_chain_v5.json"
    path.write_text(
        '{"enable_long_context_discounts": true, '
        '"long_overextension_quality_mult": 0.7, '
        '"long_upper_wick_trigger_mult": 0.6, '
        '"long_chase_trigger_mult": 0.75, '
        '"long_cvd_weak_mult": 0.8}',
        encoding="utf-8",
    )

    config = load_entry_chain_config(path)

    assert config.enable_long_context_discounts is True
    assert config.long_overextension_quality_mult == 0.7
    assert config.long_upper_wick_trigger_mult == 0.6
    assert config.long_chase_trigger_mult == 0.75
    assert config.long_cvd_weak_mult == 0.8
```

- [ ] **Step 2: Add config dataclass fields**

Add these fields to `EntryChainConfig`:

```python
enable_long_context_discounts: bool = False
long_overextension_quality_mult: float = 0.70
long_upper_wick_trigger_mult: float = 0.60
long_chase_trigger_mult: float = 0.75
long_cvd_weak_mult: float = 0.80
long_cvd_weak_threshold: float = 0.80
```

- [ ] **Step 3: Create V5 JSON configs**

Create `configs/entry_chain.dry_run_v5_symbol_bucket_only.json` as V3 plus only:

```json
"watch_only_symbols": ["ADAUSDT", "XMRUSDT"]
```

Create `configs/entry_chain.dry_run_v5_long_context_discount.json` as V3 plus:

```json
"enable_long_context_discounts": true,
"long_overextension_quality_mult": 0.70,
"long_upper_wick_trigger_mult": 0.60,
"long_chase_trigger_mult": 0.75,
"long_cvd_weak_mult": 0.80,
"long_cvd_weak_threshold": 0.80
```

Create `configs/entry_chain.dry_run_v5_symbol_bucket_long_context.json` as the combined V5 config.

- [ ] **Step 4: Add dry-run config test**

Add to `tests/test_dry_run_configs.py`:

```python
def test_v5_configs_load_without_v4_hard_long_minima():
    bucket = load_entry_chain_config("configs/entry_chain.dry_run_v5_symbol_bucket_only.json")
    context = load_entry_chain_config("configs/entry_chain.dry_run_v5_long_context_discount.json")
    combined = load_entry_chain_config("configs/entry_chain.dry_run_v5_symbol_bucket_long_context.json")

    assert bucket.watch_only_symbols == ("ADAUSDT", "XMRUSDT")
    assert bucket.long_threshold_offset == 10.0
    assert bucket.long_min_quality_direct_score is None
    assert context.enable_long_context_discounts is True
    assert context.long_threshold_offset == 10.0
    assert context.long_min_trigger_direct_score is None
    assert combined.watch_only_symbols == ("ADAUSDT", "XMRUSDT")
    assert combined.enable_long_context_discounts is True
```

- [ ] **Step 5: Verify Task 1**

Run:

```powershell
pytest tests/test_entry_chain_config.py tests/test_dry_run_configs.py -q
```

Expected: tests pass after implementation.

## Task 2: Long Context Discounts

**Files:**
- Modify: `src/signals/entry_chain.py`
- Modify: `tests/test_entry_chain.py`

- [ ] **Step 1: Add failing entry-chain tests**

Add tests proving:

```python
def test_long_context_discounts_reduce_scores_before_action_selection():
    base_scores = {
        "background_4h": 1.0,
        "direction_1h": 1.0,
        "quality_30m": 1.0,
        "trigger_15m": 1.0,
        "cvd_flow": 0.7,
        "volatility_stop": 1.0,
        "liquidity_execution": 1.0,
        "market_regime": 1.0,
        "ema_50_quality": 1.0,
        "ema_momentum": 1.0,
    }
    cfg = EntryChainConfig(
        use_ema_architecture=True,
        ema200_gate_mode="soft",
        direct_threshold=82,
        probe_threshold=70,
        enable_long_context_discounts=True,
    )

    decision = evaluate_entry_chain(
        candidate(
            side="LONG",
            component_scores=base_scores,
            long_overextension_active=True,
            long_upper_wick_risk_active=True,
            long_chase_risk_active=True,
            long_cvd_weak_active=True,
        ),
        cfg,
    )

    assert decision.component_points["quality_30m"] == 8.4
    assert decision.component_points["trigger_15m"] == 3.15
    assert decision.component_points["cvd_flow"] == 10.08
    assert "LONG_OVEREXTENSION_QUALITY_DISCOUNT" in decision.reasons
    assert "LONG_UPPER_WICK_TRIGGER_DISCOUNT" in decision.reasons
    assert "LONG_CHASE_TRIGGER_DISCOUNT" in decision.reasons
    assert "LONG_CVD_WEAK_DISCOUNT" in decision.reasons


def test_long_context_discounts_do_not_affect_shorts():
    cfg = EntryChainConfig(enable_long_context_discounts=True)
    short = evaluate_entry_chain(
        candidate(
            side="SHORT",
            long_overextension_active=True,
            long_upper_wick_risk_active=True,
            long_chase_risk_active=True,
            long_cvd_weak_active=True,
        ),
        cfg,
    )

    assert short.action == "DIRECT"
    assert not any(reason.startswith("LONG_") for reason in short.reasons)
```

- [ ] **Step 2: Add context flags**

Add these fields to `EntryChainContext` with `False` defaults:

```python
long_overextension_active: bool = False
long_upper_wick_risk_active: bool = False
long_chase_risk_active: bool = False
long_low_liquidity_session_active: bool = False
long_cvd_weak_active: bool = False
```

- [ ] **Step 3: Apply discounts before scoring**

In `evaluate_entry_chain()`, copy `context.component_scores` into a mutable dict, call a helper such as `_apply_long_context_discounts()`, then use the adjusted scores for `calculate_component_points()` and all component minimum checks.

Required behavior:

```python
if cfg.enable_long_context_discounts and side == "LONG":
    if context.long_overextension_active:
        scores["quality_30m"] *= cfg.long_overextension_quality_mult
        scores["ema_50_quality"] *= cfg.long_overextension_quality_mult
        reasons.append("LONG_OVEREXTENSION_QUALITY_DISCOUNT")
    if context.long_upper_wick_risk_active:
        scores["trigger_15m"] *= cfg.long_upper_wick_trigger_mult
        reasons.append("LONG_UPPER_WICK_TRIGGER_DISCOUNT")
    if context.long_chase_risk_active:
        scores["trigger_15m"] *= cfg.long_chase_trigger_mult
        reasons.append("LONG_CHASE_TRIGGER_DISCOUNT")
    if context.long_cvd_weak_active or scores.get("cvd_flow", 0.0) < cfg.long_cvd_weak_threshold:
        scores["cvd_flow"] *= cfg.long_cvd_weak_mult
        reasons.append("LONG_CVD_WEAK_DISCOUNT")
```

Clamp adjusted score values into `[0.0, 1.0]`.

- [ ] **Step 4: Verify Task 2**

Run:

```powershell
pytest tests/test_entry_chain.py tests/test_entry_chain_config.py -q
```

Expected: tests pass.

## Task 3: Completed-Bar Feature Injection

**Files:**
- Modify: `src/signals/entry_chain_features.py`
- Modify: `scripts/run_offline_backtest.py`

- [ ] **Step 1: Add feature helpers**

Add helpers that consume completed 15m bars only:

```python
def long_overextension_active(bars: Sequence[BacktestBar]) -> bool:
    ...

def long_upper_wick_risk_active(bars: Sequence[BacktestBar]) -> bool:
    ...

def long_chase_risk_active(bars: Sequence[BacktestBar], atr_pct_value: float) -> bool:
    ...

def long_low_liquidity_session_active(timestamp: int, bars: Sequence[BacktestBar]) -> bool:
    ...
```

Implementation constraints:

- `long_overextension_active`: use the latest completed 15m close against a 20-bar Bollinger upper band; do not use RSI.
- `long_upper_wick_risk_active`: latest completed 15m candle has upper wick at least 2x body.
- `long_chase_risk_active`: last 8 completed 15m bars moved up more than `2 * ATR pct`.
- `long_low_liquidity_session_active`: UTC hour is 22, 23, or 0 and last 8-bar average volume is below 80% of the prior 32-bar average volume.

- [ ] **Step 2: Wire helpers into offline runner**

In `scripts/run_offline_backtest.py`, after `scores = component_scores(...)`, get `bars_15m = completed["15m"]` and pass these flags into `EntryChainContext`:

```python
long_overextension_active=long_overextension_active(bars_15m),
long_upper_wick_risk_active=long_upper_wick_risk_active(bars_15m),
long_chase_risk_active=long_chase_risk_active(bars_15m, atr_pct_value),
long_low_liquidity_session_active=long_low_liquidity_session_active(current_bar.timestamp, bars_15m),
long_cvd_weak_active=scores.get("cvd_flow", 0.0) < cfg.long_cvd_weak_threshold,
```

- [ ] **Step 3: Low-liquidity session downgrade**

In `evaluate_entry_chain()`, if `enable_long_context_discounts` is true, side is `LONG`, and `long_low_liquidity_session_active` is true, cap the action at `WATCH` after component minimums are applied and add:

```text
LONG_LOW_LIQUIDITY_SESSION_WATCH
```

- [ ] **Step 4: Verify Task 3**

Run:

```powershell
python -m compileall src scripts
pytest tests/test_entry_chain.py tests/test_entry_chain_config.py tests/test_dry_run_configs.py -q
```

Expected: compile succeeds and focused tests pass.

## Task 4: Latest 30D V5 Backtests

**Files:**
- Read/write under `reports/backtests/`.

- [ ] **Step 1: Run symbol bucket only**

```powershell
python scripts/run_offline_backtest.py --data-dir data/raw/binance_futures/latest_30d --timeframe 15m --strategy entry-chain --entry-chain-config configs/entry_chain.dry_run_v5_symbol_bucket_only.json --exit-model atr_tp --atr-stop-mult 1.5 --tp-levels 1,2,3 --tp-fractions 0.4,0.35,0.25 --max-hold-bars 32 --default-atr-pct 0.010 --simulated-hold-bars 2 --cooldown-bars 8 --run-id latest_30d_v5_symbol_bucket_only
```

- [ ] **Step 2: Run long context only**

```powershell
python scripts/run_offline_backtest.py --data-dir data/raw/binance_futures/latest_30d --timeframe 15m --strategy entry-chain --entry-chain-config configs/entry_chain.dry_run_v5_long_context_discount.json --exit-model atr_tp --atr-stop-mult 1.5 --tp-levels 1,2,3 --tp-fractions 0.4,0.35,0.25 --max-hold-bars 32 --default-atr-pct 0.010 --simulated-hold-bars 2 --cooldown-bars 8 --run-id latest_30d_v5_long_context_discount
```

- [ ] **Step 3: Run combined V5 if either isolated variant does not collapse trade count**

```powershell
python scripts/run_offline_backtest.py --data-dir data/raw/binance_futures/latest_30d --timeframe 15m --strategy entry-chain --entry-chain-config configs/entry_chain.dry_run_v5_symbol_bucket_long_context.json --exit-model atr_tp --atr-stop-mult 1.5 --tp-levels 1,2,3 --tp-fractions 0.4,0.35,0.25 --max-hold-bars 32 --default-atr-pct 0.010 --simulated-hold-bars 2 --cooldown-bars 8 --run-id latest_30d_v5_symbol_bucket_long_context
```

- [ ] **Step 4: Extract metrics**

Read `backtest_result.json` for:

```text
latest_30d_lifecycle_v3_hold32
latest_30d_v4_side_split
latest_30d_v4_side_symbol_bucket
latest_30d_v5_symbol_bucket_only
latest_30d_v5_long_context_discount
latest_30d_v5_symbol_bucket_long_context
```

Extract:

- return
- trade count
- win rate
- profit factor
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
- exit reason split
- stop-hit count and net
- MFE/MAE where available

## Task 5: V5 Attribution Report

**Files:**
- Create: `docs/superpowers/reports/2026-06-19-v5-symbol-bucket-long-context-quality-report.md`

- [ ] **Step 1: Write frozen-control summary**

State that V3 lifecycle accounting remained frozen and V5 changed entry acceptance only.

- [ ] **Step 2: Compare V3/V4/V5**

Create headline, cost, side, symbol, and stop-hit tables.

- [ ] **Step 3: Attribute outcome**

Answer:

- Did pure symbol bucketing beat V3?
- Did long-context discounts reduce long stop hits?
- Did gross edge fall faster than costs?
- Did any variant meet `50%+` return, `80%+` win, and `90-120` trades?
- Which run should remain the baseline?

- [ ] **Step 4: State next blocker**

If V5 does not beat V3, state that score-discount rules are still too coarse and the next work should use lifecycle diagnostics: stop-hit preconditions, entry-bar morphology, and rolling windows before leverage or deployment.

## Task 6: Final Verification

**Files:**
- No intended changes to `src/api/binance_client.py`.

- [ ] **Step 1: Run focused verification**

```powershell
python -m compileall src scripts tests
pytest tests/test_entry_chain.py tests/test_entry_chain_config.py tests/test_dry_run_configs.py tests/test_lifecycle_exit.py tests/test_backtest_engine.py -q
git diff -- src/api/binance_client.py
```

Expected: compile succeeds, focused tests pass, and the Binance client diff is empty.

- [ ] **Step 2: Final response**

Report:

- Best V5 run and whether it beats V3.
- Whether target is met.
- Main attribution.
- Paths to the V5 plan and V5 report.
