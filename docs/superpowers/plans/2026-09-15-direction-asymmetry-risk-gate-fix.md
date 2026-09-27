# 方向非对称与单笔风险硬上限修复计划

## Global Constraints

- Add `max_single_trade_risk_pct=0.0075` and cap final notional with the selected leverage.
- Keep existing direct/probe risk percentages and total exposure caps.
- Apply blacklist, watch-only, and observation-only policies to the Q1 specialized entry path.
- Keep bullish-regime SHORT gating and 4x quality gating shadow-only.
- Do not change `short_threshold_offset` or 4x leverage tier selection.
- Use completed candles only; no lookahead, repaint, or same-candle fill assumptions.
- Preserve existing user changes, including `src/observability/paper_trading.py`.

## Tasks

### Task 1: Single-trade leveraged risk cap

Update `src/signals/entry_chain_config.py`, `src/signals/entry_chain.py`,
`configs/entry_chain.dry_run_fib_pa_v1.json`, and
`tests/test_entry_chain_risk_budget.py`.

The raw notional is `equity * risk_pct / stop_pct`. The leveraged cap is
`equity * max_single_trade_risk_pct / (stop_pct * selected_leverage)`. The
final notional is the minimum of raw notional, leveraged cap, and remaining
exposure. Use the actual selected leverage and expose cap diagnostics.

### Task 2: Q1 symbol-policy enforcement

Update `scripts/run_live_dry_run.py` and `tests/test_q1_trend_launch_fix.py`.
The Q1 specialized path must reject blacklist, watch-only, and
observation-only symbols with distinct reasons, while preserving normal
action semantics and routing through centralized risk policy.

### Task 3: Shadow observability, audit, and implementation report

Extend the existing regime SHORT shadow without changing live action. Record
completed-candle regime evidence, Q1 SHORT candidates, shadow offsets 5/10,
reversal confirmation, and counterfactual blocks. Add a read-only 4x SHORT/Q1
cross-audit. Write
`docs/superpowers/reports/2026-09-15-direction-asymmetry-risk-gate-implementation.md`
covering evidence, live changes, shadow-only changes, nominal and leveraged
PnL, and verification constraints.

## Verification

- Run the focused pytest files for risk budget, Q1 eligibility, regime shadow,
  and leverage shadow.
- Run related signal, adapter, and paper-ledger tests.
- Run the read-only 4x SHORT/Q1 audit.
- Run `git diff --check` and inspect all entry/draft paths for bypasses.
