# PROBE Defense Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden dry-run PROBE admission and paper risk controls after the 2026-06-29/30 loss window so the next VPS run blocks low RR, overextended long, high beta weak-momentum, repeated stop, and portfolio loss spirals.

**Architecture:** Keep the change surgical and configuration-driven. Entry-chain rejects bad candidates before order drafting; dry-run controls apply ledger-aware symbol/global cooldowns; paper trading exits stagnant positions earlier. No live exchange mutation path is changed.

**Tech Stack:** Python, pytest, JSON config, existing `EntryChainConfig`, `EntryChainDecision`, and `PaperTradingLedger`.

## Global Constraints

- Do not modify real exchange order submission or production live execution behavior.
- Do not introduce lookahead bias, future candle data, repaint signals, or same-bar fill assumptions.
- All new strategy gates must be live-executable from current decision context or already closed paper trades.
- Hypothesis: the 24h loss was dominated by low-quality PROBE entries, especially low RR, weak high-beta momentum/trend context, overextended longs, and repeated initial stops.
- Expected regime: noisy/fake-breakout or overextended intraday market where weak PROBE entries reverse before TP1.
- Failure mode: filters may reduce trade count below 10-20/day or miss genuine momentum breakouts; logs must preserve explicit reasons for review.
- Verification command: `pytest tests/test_entry_chain_probe_conditions.py tests/test_entry_chain.py tests/test_entry_chain_gates.py tests/test_entry_chain_config.py tests/test_live_dry_run.py tests/test_paper_trading.py tests/test_dry_run_configs.py -q`.

---

### Task 1: Entry-Chain PROBE Admission Hardening

**Files:**
- Modify: `src/signals/entry_chain_config.py`
- Modify: `src/signals/entry_chain_gates.py`
- Modify: `src/signals/entry_chain.py`
- Modify: `configs/entry_chain.dry_run_fib_pa_v1.json`
- Test: `tests/test_entry_chain_probe_conditions.py`
- Test: `tests/test_entry_chain.py`
- Test: `tests/test_entry_chain_gates.py`
- Test: `tests/test_entry_chain_config.py`
- Test: `tests/test_dry_run_configs.py`

**Interfaces:**
- Consumes: `EntryChainContext.component_scores`, `long_overextension_active`, `long_chase_risk_active`, and `probe_conditions`.
- Produces: explicit demotion reasons including `LONG_OVEREXTENSION_OR_CHASE_RISK_WATCH`, `HIGH_BETA_PROBE_BELOW_CCI_MOMENTUM_QUALITY_MINIMUM_GAP_*`, and `HIGH_BETA_PROBE_BELOW_TREND_EMA_CONTEXT_MINIMUM_GAP_*`.

- [ ] **Step 1: Add failing tests for stricter PROBE rules**

Add tests that assert:
- PROBE rejects `risk_reward_geometry < min_rr_score`.
- HIGH_BETA PROBE requires configured RR, CCI, and EMA point minimums.
- configured overextended/chase LONG caps PROBE/DIRECT to WATCH.
- `min_daily_trades` prevents low-volatility dynamic budget from shrinking below the configured floor.

- [ ] **Step 2: Implement config fields and gates**

Add `min_daily_trades`, `long_overextension_watch_enabled`, and `long_chase_watch_enabled` to `EntryChainConfig`. Apply `min_daily_trades` in both `src/signals/entry_chain_gates.py::daily_max_trades` and the local `_daily_max_trades` helper in `src/signals/entry_chain.py`.

- [ ] **Step 3: Implement PROBE component hardening**

Extend `check_probe_conditions` to support `high_beta_min_cci_score` and `high_beta_min_ema_score`, measured as points out of 14 and 20 respectively. Keep existing reason style and high-beta reason prefix.

- [ ] **Step 4: Harden dry-run Fib/PA config**

Set dry-run Fib/PA values:
- `probe_conditions.min_rr_net_r = 1.3`
- `probe_conditions.min_rr_score = 4.0`
- `probe_conditions.high_beta_min_rr_score = 5.0`
- `probe_conditions.high_beta_min_cci_score = 9.0`
- `probe_conditions.high_beta_min_ema_score = 12.0`
- `long_overextension_watch_enabled = true`
- `long_chase_watch_enabled = true`
- `min_daily_trades = 2`

- [ ] **Step 5: Verify Task 1**

Run: `pytest tests/test_entry_chain_probe_conditions.py tests/test_entry_chain.py tests/test_entry_chain_gates.py tests/test_entry_chain_config.py tests/test_dry_run_configs.py -q`

Expected: PASS.

### Task 2: Dry-Run Ledger-Aware Cooldown And Circuit Breakers

**Files:**
- Modify: `src/signals/entry_chain_config.py`
- Modify: `scripts/run_live_dry_run.py`
- Modify: `configs/entry_chain.dry_run_fib_pa_v1.json`
- Test: `tests/test_live_dry_run.py`
- Test: `tests/test_entry_chain_config.py`

**Interfaces:**
- Consumes: closed `PAPER_CLOSE` rows from `PaperTradingLedger.recent_closed_trades`.
- Produces: WATCH demotions with `SYMBOL_POST_INITIAL_STOP_COOLDOWN`, `PORTFOLIO_CONSECUTIVE_INITIAL_STOP_CIRCUIT_BREAKER`, and `PORTFOLIO_DAILY_LOSS_CIRCUIT_BREAKER`.

- [ ] **Step 1: Add failing tests for one-stop symbol cooldown and portfolio breakers**

Add tests proving:
- one `INITIAL_STOP_HIT` blocks the same symbol for configured hours.
- three recent `INITIAL_STOP_HIT` closes block all new entries for configured hours.
- daily realized loss below configured threshold blocks entries.

- [ ] **Step 2: Add config fields**

Add:
- `post_initial_stop_cooldown_enabled: bool = False`
- `post_initial_stop_cooldown_hours: int = 4`
- `portfolio_stop_circuit_enabled: bool = False`
- `portfolio_stop_circuit_count: int = 3`
- `portfolio_stop_circuit_hours: int = 4`
- `portfolio_daily_loss_circuit_enabled: bool = False`
- `portfolio_daily_loss_limit: float = -30.0`

- [ ] **Step 3: Implement helpers in dry-run control layer**

Use only already closed paper trades. Do not inspect future candles. Cap decisions to WATCH using existing `_cap_decision_to_watch`.

- [ ] **Step 4: Enable dry-run Fib/PA config**

Set one-stop cooldown to 4h, portfolio stop circuit to 3 stops/4h, and daily loss circuit to `-30.0`.

- [ ] **Step 5: Verify Task 2**

Run: `pytest tests/test_live_dry_run.py tests/test_entry_chain_config.py -q`

Expected: PASS.

### Task 3: Paper Cost-Breakeven Exit Tightening

**Files:**
- Modify: `src/observability/paper_trading.py`
- Test: `tests/test_paper_trading.py`

**Interfaces:**
- Consumes: current paper position, current close, elapsed closed 15m bars.
- Produces: earlier `COST_BREAKEVEN_TIMEOUT` close after 8 bars when remaining gross PnL cannot cover half estimated round-trip cost.

- [ ] **Step 1: Add/adjust test for 2h cost checkpoint**

Update stagnant-position test to expect exit on the 8th 15m bar, not around the previous 10th/11th bar.

- [ ] **Step 2: Implement constants**

Set:
- `COST_BREAKEVEN_CHECK_BARS = MAX_HOLD_BARS // 4`
- `COST_BREAKEVEN_BUFFER_MULT = 0.5`

- [ ] **Step 3: Verify Task 3**

Run: `pytest tests/test_paper_trading.py -q`

Expected: PASS.

### Task 4: Full Focused Verification

**Files:**
- No new source files.

**Interfaces:**
- Produces final evidence for VPS upload.

- [ ] **Step 1: Run focused suite**

Run: `pytest tests/test_entry_chain_probe_conditions.py tests/test_entry_chain.py tests/test_entry_chain_gates.py tests/test_entry_chain_config.py tests/test_live_dry_run.py tests/test_paper_trading.py tests/test_dry_run_configs.py -q`

Expected: PASS.

- [ ] **Step 2: Inspect diff**

Run: `git diff -- src/signals/entry_chain.py src/signals/entry_chain_config.py src/signals/entry_chain_gates.py src/observability/paper_trading.py scripts/run_live_dry_run.py configs/entry_chain.dry_run_fib_pa_v1.json tests/test_entry_chain_probe_conditions.py tests/test_entry_chain.py tests/test_entry_chain_gates.py tests/test_entry_chain_config.py tests/test_live_dry_run.py tests/test_paper_trading.py tests/test_dry_run_configs.py docs/superpowers/plans/2026-06-30-probe-defense-hardening.md`

Expected: only planned files changed.
