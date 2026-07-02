# Dry-Run Quality And Volume Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve dry-run entry quality and cost awareness while tuning Fib/PA dry-run frequency toward `10-20` opens per rolling 24 hours.

**Architecture:** Keep all behavior inside dry-run / entry-chain research paths. Add explicit quality gates around Fib/PA component minimums, extend dry-run post-processing to weak-edge PROBE trades, and add a paper-ledger cost-breakeven exit so small stagnant positions stop consuming full max-hold time. Tune only `configs/entry_chain.dry_run_fib_pa_v1.json` for the new observation target.

**Tech Stack:** Python, pytest, JSON config, existing AI300 entry-chain and paper trading modules.

## Global Constraints

- Current mode is DRY-RUN; do not enable exchange mutation or submit/cancel/amend real orders.
- Do not modify live execution, live risk, or production config paths beyond dry-run order-draft validation already covered by tests.
- Never introduce lookahead bias, future candle data, repaint signals, or same-bar fill assumptions.
- Entry and exit logic must remain live-executable with explicit fee, slippage, latency, and candle-close assumptions.
- Strategy hypothesis: increasing daily trade budget to target `10-20` opens per 24h can be acceptable only if low PA/RR, chase-risk, high-beta weak setups, and weak-edge no-history PROBE trades are blocked.
- Expected market regime: 15m/30m crypto futures with enough intraday volatility for TP1/TP2 follow-through, not extremely flat chop.
- Failure mode: tighter quality gates may keep observed opens below `10/day`; looser volume budget may amplify cost drag if gates are insufficient.
- Verification command: `pytest tests/test_entry_chain.py tests/test_entry_chain_probe_conditions.py tests/test_live_dry_run.py tests/test_paper_trading.py tests/test_dry_run_configs.py -q`

---

### Task 1: Fib/PA Entry Quality Gates

**Files:**
- Modify: `src/signals/entry_chain.py`
- Modify: `configs/entry_chain.dry_run_fib_pa_v1.json`
- Modify: `tests/test_entry_chain.py`
- Modify: `tests/test_entry_chain_probe_conditions.py`
- Modify: `tests/test_dry_run_configs.py`

**Interfaces:**
- Consumes: `evaluate_entry_chain(context, config)` and `check_probe_conditions(score, side, component_points, rr_detail, config)`.
- Produces: stricter Fib/PA direct/probe quality decisions with reasons:
  - `DIRECT_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_...`
  - `PROBE_BELOW_PRICE_ACTION_STRUCTURE_MINIMUM_GAP_...`
  - `LONG_CHASE_WEAK_PA_WATCH`
  - `HIGH_BETA_PROBE_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_...`

- [ ] **Step 1: Write failing tests for stricter probe PA and high-beta RR**

Add tests that show:

```python
def test_probe_rejected_when_price_action_below_configured_minimum():
    allowed, reason = check_probe_conditions(
        score=80.0,
        side="LONG",
        component_points={
            "fibonacci_location": 18.0,
            "price_action_structure": 8.0,
            "risk_reward_geometry": 6.5,
        },
        rr_detail={"net_tp1_r": 1.1},
        config={
            "enabled": True,
            "min_score": 72.0,
            "min_fib_score": 12.0,
            "min_pa_score": 10.0,
            "min_rr_net_r": 0.9,
        },
    )

    assert allowed is False
    assert reason == "PROBE_BELOW_PRICE_ACTION_STRUCTURE_MINIMUM_GAP_2.0"
```

and in `tests/test_entry_chain.py`:

```python
def test_fib_pa_high_beta_probe_requires_extra_rr():
    cfg = EntryChainConfig(
        use_fib_pa_architecture=True,
        direct_threshold=82.0,
        probe_threshold=70.0,
        probe_conditions={
            "enabled": True,
            "min_score": 72.0,
            "min_fib_score": 12.0,
            "min_pa_score": 10.0,
            "min_rr_score": 2.0,
            "high_beta_min_pa_score": 12.0,
            "high_beta_min_rr_score": 3.0,
        },
    )

    decision = evaluate_entry_chain(
        candidate(
            symbol="HYPEUSDT",
            side="SHORT",
            component_scores=fib_pa_scores(
                trend_ema_context=18.0 / 20.0,
                flow_cvd_confirmation=1.0,
                cci_momentum_quality=10.0 / 14.0,
                price_action_structure=12.0 / 22.0,
                fibonacci_location=18.0 / 18.0,
                risk_reward_geometry=2.5 / 8.0,
            ),
        ),
        cfg,
    )

    assert decision.action == "WATCH"
    assert "HIGH_BETA_PROBE_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_0.5" in decision.reasons
```

- [ ] **Step 2: Run tests to verify RED**

Run: `pytest tests/test_entry_chain_probe_conditions.py tests/test_entry_chain.py -q`

Expected: FAIL because `check_probe_conditions` does not apply high-beta extra minimums and current tests/config still allow weak PA.

- [ ] **Step 3: Implement minimal quality gates**

Update `check_probe_conditions()` to accept optional `high_beta_min_pa_score` and `high_beta_min_rr_score`. Update `_apply_fib_pa_probe_minimums()` to pass `side=context.side` and symbol high-beta status through config-derived checks without changing public function signatures beyond optional config keys.

Add chase weak-PA cap inside `evaluate_entry_chain()` after component minimums:

```python
if cfg.use_fib_pa_architecture and side == "LONG" and context.long_chase_risk_active:
    pa_points = points.get("price_action_structure", 0.0)
    chase_min = float(dict(cfg.probe_conditions or {}).get("long_chase_min_pa_score", 12.0))
    if action in {"PROBE", "DIRECT"} and pa_points < chase_min:
        action = "WATCH"
        reasons.append("LONG_CHASE_WEAK_PA_WATCH")
```

Raise configured minimums in `configs/entry_chain.dry_run_fib_pa_v1.json`:

```json
"min_pa_score": 10.0,
"min_rr_net_r": 1.0,
"high_beta_min_pa_score": 12.0,
"high_beta_min_rr_score": 3.0,
"long_chase_min_pa_score": 12.0
```

Raise direct RR:

```json
"rr_min_direct_score": 4.0
```

- [ ] **Step 4: Run tests to verify GREEN**

Run: `pytest tests/test_entry_chain_probe_conditions.py tests/test_entry_chain.py tests/test_dry_run_configs.py -q`

Expected: PASS.

### Task 2: Weak-Edge PROBE Dry-Run Protection

**Files:**
- Modify: `src/signals/entry_chain_config.py`
- Modify: `scripts/run_live_dry_run.py`
- Modify: `configs/entry_chain.dry_run_fib_pa_v1.json`
- Modify: `tests/test_entry_chain_config.py`
- Modify: `tests/test_live_dry_run.py`

**Interfaces:**
- Consumes: `PaperTradingLedger.has_positive_closed_trade(symbol, until_ts=...)`.
- Produces: `_weak_edge_probe_without_positive_history(decision, config, paper, timestamp) -> bool`.

- [ ] **Step 1: Write failing tests**

In `tests/test_entry_chain_config.py`, assert new config fields parse:

```python
assert config.weak_edge_probe_min_score == 77
assert config.weak_edge_probe_max_score == 85
```

In `tests/test_live_dry_run.py`, add:

```python
def test_dry_run_decision_controls_demote_weak_edge_probe_without_positive_history(tmp_path):
    paper = PaperTradingLedger(tmp_path)
    config = EntryChainConfig(
        weak_edge_probe_min_score=77.0,
        weak_edge_probe_max_score=85.0,
    )
    decision = EntryChainDecision(
        action="PROBE",
        side="LONG",
        score=82.0,
        weights={},
        component_points={},
        reasons=("TEST_PROBE",),
        risk_allowed=True,
        leverage=3,
        max_symbol_exposure_pct=0.2,
        notional_hint=500.0,
        liquidity_ratio=100.0,
        metadata={"symbol": "SOLUSDT"},
    )

    controlled = apply_dry_run_decision_controls(
        decision,
        config=config,
        paper=paper,
        timestamp=2000,
    )

    assert controlled.action == "WATCH"
    assert "PROBE_WEAK_EDGE_DEMOTED" in controlled.reasons
```

- [ ] **Step 2: Run tests to verify RED**

Run: `pytest tests/test_entry_chain_config.py tests/test_live_dry_run.py -q`

Expected: FAIL because config has no weak-edge probe fields and no post-processor logic.

- [ ] **Step 3: Implement minimal logic**

Add to `EntryChainConfig`:

```python
weak_edge_probe_min_score: float = 77.0
weak_edge_probe_max_score: float = 85.0
```

Add `_weak_edge_probe_without_positive_history()` mirroring DIRECT logic but only for `decision.action == "PROBE"`. In `apply_dry_run_decision_controls()`, append `PROBE_WEAK_EDGE_DEMOTED` when true.

Set config values in `configs/entry_chain.dry_run_fib_pa_v1.json`:

```json
"weak_edge_probe_min_score": 77.0,
"weak_edge_probe_max_score": 85.0
```

- [ ] **Step 4: Run tests to verify GREEN**

Run: `pytest tests/test_entry_chain_config.py tests/test_live_dry_run.py -q`

Expected: PASS.

### Task 3: Paper Ledger Cost-Breakeven Exit

**Files:**
- Modify: `src/observability/paper_trading.py`
- Modify: `tests/test_paper_trading.py`

**Interfaces:**
- Consumes: existing `PaperPosition`, `PaperTradingLedger.on_decision()`, `_gross_pnl()`, `fee()`.
- Produces: new close reason `COST_BREAKEVEN_TIMEOUT` when a position reaches an early checkpoint without enough gross PnL to cover entry plus estimated exit costs.

- [ ] **Step 1: Write failing test**

Add to `tests/test_paper_trading.py`:

```python
def test_paper_trading_ledger_exits_stagnant_position_at_cost_checkpoint(tmp_path):
    ledger = PaperTradingLedger(tmp_path)
    decision, draft = approved_decision()
    ledger.on_decision(
        symbol="SOLUSDT",
        decision_payload=decision,
        draft_payload=draft,
        kline={"close": 100, "high": 100, "low": 100},
        timestamp=1000,
    )

    events = []
    for index in range(1, 11):
        events = ledger.on_decision(
            symbol="SOLUSDT",
            decision_payload={"action": "NO_TRADE"},
            draft_payload={"approved": False},
            kline={"close": 100.05, "high": 100.1, "low": 100.0},
            timestamp=1000 + index * 900,
        )
        if events:
            break

    assert events[0].startswith("PAPER_CLOSE:SOLUSDT:COST_BREAKEVEN_TIMEOUT")
    trade_rows = [json.loads(line) for line in (tmp_path / "paper_trades.jsonl").read_text(encoding="utf-8").splitlines()]
    assert trade_rows[-1]["reason"] == "COST_BREAKEVEN_TIMEOUT"
```

- [ ] **Step 2: Run test to verify RED**

Run: `pytest tests/test_paper_trading.py::test_paper_trading_ledger_exits_stagnant_position_at_cost_checkpoint -q`

Expected: FAIL because the stagnant position remains open until max hold.

- [ ] **Step 3: Implement minimal cost checkpoint**

Add constants:

```python
COST_BREAKEVEN_CHECK_BARS = MAX_HOLD_BARS // 3
COST_BREAKEVEN_BUFFER_MULT = 1.0
```

In `_update_position()`, after TP checks and before `MAX_HOLD_EXIT`, close remaining position when:

```python
position.hold_bars >= COST_BREAKEVEN_CHECK_BARS
and not position.tp_consumed
and _gross_pnl(position.side, position.entry_price, close, position.quantity * position.remaining_fraction)
    < _round_trip_cost_estimate(position, close) * COST_BREAKEVEN_BUFFER_MULT
```

Use reason `COST_BREAKEVEN_TIMEOUT`.

- [ ] **Step 4: Run tests to verify GREEN**

Run: `pytest tests/test_paper_trading.py -q`

Expected: PASS.

### Task 4: Tune Dry-Run Frequency Config To 10-20 Opens Per 24h

**Files:**
- Modify: `configs/entry_chain.dry_run_fib_pa_v1.json`
- Modify: `tests/test_dry_run_configs.py`

**Interfaces:**
- Consumes: `EntryChainConfig` parsing and dry-run budget logic.
- Produces: config target of `daily_max_trades_base=16`, per-symbol cap `2`, active symbol cap `8`, with stricter quality gates from Tasks 1-2.

- [ ] **Step 1: Write failing config test**

Update `test_fib_pa_dry_run_config_loads_and_is_dry_run_safe()`:

```python
assert config.daily_max_trades_base == 16
assert config.max_symbol_trades_per_day == 2
assert config.max_active_symbols == 8
assert config.probe_conditions["min_pa_score"] == 10.0
assert config.probe_conditions["high_beta_min_pa_score"] == 12.0
assert config.rr_min_direct_score == 4.0
```

- [ ] **Step 2: Run test to verify RED**

Run: `pytest tests/test_dry_run_configs.py::test_fib_pa_dry_run_config_loads_and_is_dry_run_safe -q`

Expected: FAIL on old budget and old minima.

- [ ] **Step 3: Apply config changes**

In `configs/entry_chain.dry_run_fib_pa_v1.json`:

```json
"daily_max_trades_base": 16,
"max_symbol_trades_per_day": 2,
"max_active_symbols": 8,
"max_total_exposure_pct": 1.6,
"max_same_direction_exposure_pct": 1.1
```

Keep dry-run symbol source and `exchange_mutation_enabled` unchanged.

- [ ] **Step 4: Run focused and broad verification**

Run:

```powershell
pytest tests/test_entry_chain.py tests/test_entry_chain_probe_conditions.py tests/test_live_dry_run.py tests/test_paper_trading.py tests/test_dry_run_configs.py -q
python scripts/run_live_dry_run.py --config configs/entry_chain.dry_run_fib_pa_v1.json --target-tier aggressive --market-data-source synthetic --once --output-dir reports/dry_run/local_quality_volume_smoke --symbols SOLUSDT,HYPEUSDT,LABUSDT
```

Expected: tests PASS; dry-run smoke writes decisions/order drafts/paper snapshots and reports `orders_submitted=0`.

