# P0 Paper State And TP1 Engineering Fix Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make dry-run entry decisions aware of current paper positions and raise Fib/PA RR geometry TP1 from 1.0R to 1.2R.

**Architecture:** Add a small paper portfolio snapshot API on `PaperTradingLedger`, inject it into live dry-run `EntryChainContext` before `evaluate_entry_chain`, and keep the existing ledger as the execution source of truth. Update the RR scoring formula and paper TP ladder constants so diagnostic TP1 and simulated paper exits use the same 1.2R assumption.

**Tech Stack:** Python dataclasses, pytest, existing AI300 dry-run scripts and signal modules.

## Global Constraints

- This is DRY-RUN engineering work only; do not add exchange mutation or live execution behavior.
- Do not tune strategy thresholds beyond TP1 changing from `1.0R` to `1.2R`.
- State回填 must make duplicate same-symbol paper opens fail before draft approval, not silently inside paper ledger.
- Keep changes surgical and match existing style; do not refactor adjacent strategy logic.
- Existing uncommitted changes in this workspace are treated as user work and must not be reverted.
- Verification commands must include targeted tests for live dry-run, paper trading, and RR geometry.

---

### Task 1: Paper Portfolio Snapshot

**Files:**
- Modify: `src/observability/paper_trading.py`
- Modify: `tests/test_paper_trading.py`

**Interfaces:**
- Produces: `PortfolioStateSnapshot` dataclass with fields consumed by live dry-run context injection.
- Produces: `PaperTradingLedger.get_portfolio_state_snapshot(timestamp: int | None = None) -> PortfolioStateSnapshot`.

- [ ] **Step 1: Write failing tests**

Add tests that open one paper position, call `get_portfolio_state_snapshot`, and assert:

```python
snapshot.active_symbols == {"SOLUSDT"}
snapshot.open_position_count == 1
snapshot.total_exposure_pct > 0
snapshot.same_direction_long_pct > 0
snapshot.same_direction_short_pct == 0
snapshot.symbol_exposure_pct["SOLUSDT"] > 0
snapshot.daily_trades_by_symbol["SOLUSDT"] == 1
snapshot.portfolio_trades_today == 1
```

- [ ] **Step 2: Implement minimal snapshot API**

Add `PortfolioStateSnapshot` beside `PaperPosition` and compute exposure from current `positions` using remaining notional divided by `initial_equity`. Count daily opens from `paper_trades.jsonl` using the optional timestamp's UTC day when provided.

- [ ] **Step 3: Verify**

Run: `pytest tests/test_paper_trading.py -q`

Expected: PASS.

### Task 2: Inject Paper State Into Entry Context

**Files:**
- Modify: `scripts/run_live_dry_run.py`
- Modify: `tests/test_live_dry_run.py`

**Interfaces:**
- Consumes: `PaperTradingLedger.get_portfolio_state_snapshot`.
- Produces: `apply_paper_state_to_context(context: EntryChainContext, paper: PaperTradingLedger, timestamp: int) -> EntryChainContext`.

- [ ] **Step 1: Write failing tests**

Add a test that opens a `LABUSDT` paper position, builds a high-score second `LABUSDT` context, applies paper state, evaluates the chain, and asserts `SYMBOL_DAILY_TRADE_BUDGET_USED` or another paper-state gate appears before any draft approval path.

- [ ] **Step 2: Implement context injection**

Before `evaluate_entry_chain` in the live dry-run scan loop, call `apply_paper_state_to_context`. Populate:

```python
active_symbols
portfolio_trades_today
symbol_trades_today
daily_profit_pct
symbol_exposure_pct
total_exposure_pct
same_direction_exposure_pct
account_equity
available_margin
```

Use long or short same-direction exposure according to `context.side`.

- [ ] **Step 3: Verify**

Run: `pytest tests/test_live_dry_run.py -q`

Expected: PASS.

### Task 3: Raise TP1 From 1.0R To 1.2R

**Files:**
- Modify: `src/signals/entry_chain_features.py`
- Modify: `src/observability/paper_trading.py`
- Modify: `tests/test_risk_reward_geometry_detail.py`
- Modify: `tests/test_paper_trading.py`

**Interfaces:**
- Produces: `risk_reward_geometry_detail(...): dict` where `tp1_pct` is `stop_pct * 1.2`.
- Produces: paper positions where `tp_prices[0]` is `1.2R` from entry.

- [ ] **Step 1: Write failing tests**

Update RR test expectations so a 1.0% stop yields `tp1_pct == 0.012` and improves `net_tp1_r` according to `1.2R` after fees.

- [ ] **Step 2: Implement TP1 multiplier**

Introduce a named constant for TP1 multiplier in `entry_chain_features.py` and set `tp1_dist = stop_dist * 1.2`. Change paper ledger `TP_LEVELS` to `(1.2, 2.0, 3.0)` only; do not change fractions or stop logic.

- [ ] **Step 3: Verify**

Run: `pytest tests/test_risk_reward_geometry_detail.py tests/test_paper_trading.py -q`

Expected: PASS.

### Task 4: Final Targeted Verification

**Files:**
- No production file changes expected.

- [ ] **Step 1: Run focused suite**

Run:

```powershell
pytest tests/test_risk_reward_geometry_detail.py tests/test_paper_trading.py tests/test_live_dry_run.py tests/test_entry_chain.py tests/test_entry_chain_probe_conditions.py -q
```

Expected: PASS.

- [ ] **Step 2: Inspect diff**

Run:

```powershell
git diff -- docs/superpowers/plans/2026-06-27-p0-paper-state-tp1.md src/observability/paper_trading.py scripts/run_live_dry_run.py src/signals/entry_chain_features.py tests/test_paper_trading.py tests/test_live_dry_run.py tests/test_risk_reward_geometry_detail.py
```

Expected: Only P0 paper-state and TP1 engineering changes.
