# CODEBUDDY.md

This file provides guidance to CodeBuddy Code when working with code in this repository.

## What this repo is

AI300 — a multi-timeframe trend trading system for Binance USDT perpetuals (top-20 by market cap). Runtime is **dry-run / paper only**: the production VPS runs `scripts/run_live_dry_run.py` in dry-run mode and no real orders are placed. A second, increasingly important half of the repo is an **offline research layer** (`scripts/analysis/`), whose current focus is the forward-label library `fwdlib` (branch `feat/fwdlib-labeler-v2`). Authoritative prose lives in `REASONIX.md` (Chinese, always read it first) and the numbered spec docs `docs/00_project_overview.md` … `docs/19_backtest_engine.md`; for strategy numbers, `logs/analysis/strategy-audit-2026-10-19.md` is the code-level audit this file summarises.

## Commands

```bash
# Setup — runtime deps are tiny: requests + urllib3, pytest for tests
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt   # Linux: .venv/bin/pip

# Full test suite (~54s, 839 tests → 838 passed, 1 known failure); one file / one test:
python -m pytest tests/ -q --ignore=tests/test_verify_five_factor_orthogonality.py
python -m pytest tests/test_entry_chain_scoring.py -q
python -m pytest tests/test_fwdlib_labeler_parity.py::test_cost_bps_shifts_r_net_only -q

# Dry-run, single offline cycle (no network, ~3s) — smoke test
python scripts/run_live_dry_run.py --config configs/entry_chain.dry_run_fib_pa_v1.json \
  --target-tier aggressive --market-data-source synthetic --once --log-root logs/_smoke
# prints {"status": "dry_run_completed", "orders_submitted": 0}

# VPS-style invocation. This is what systemd actually runs: BOTH deploy/systemd/ai300-dry-run.service
# and deploy/systemd/aibot.service have ExecStart pointing at configs/entry_chain.dry_run_highest_win.json.
python scripts/run_live_dry_run.py --config configs/entry_chain.dry_run_highest_win.json \
  --target-tier aggressive --market-data-source public-binance --log-root logs \
  --align-to-kline-close --post-close-delay-seconds 5

# Backtests (share the dry-run decision chain; data must be downloaded first).
# Also scripts/run_rolling_backtest.py for the rolling variant.
python scripts/download_latest_30d_market_data.py
python scripts/run_offline_backtest.py --strategy entry-chain --entry-chain-config configs/entry_chain.dry_run.json

# Forward-label v2 report (the current research line). Outputs to reports/analysis/<slug>/
# FWD_LOGS / FWD_REPORTS env vars override the default log/report roots (useful from a worktree)
python scripts/analysis/fwd_label_v2_20261019.py --logs logs --months 2026-09,2026-10 --out reports/analysis/fwd-label-v2-20261019

# Post-deploy / audit helpers
python scripts/verify_q1_trend_launch_fix.py --mode online --log-root logs --hours 24
python scripts/evaluate_offense_fixes.py
python scripts/recommendation_tracker.py check          # exit 1 = unresolved P0
python scripts/audit_duplicate_json_keys.py <config.json>

# NOTE: numpy is NOT in requirements.txt, yet scripts/verify_five_factor_orthogonality.py and its
# test import it — without numpy, collection aborts. Install numpy or add
# --ignore=tests/test_verify_five_factor_orthogonality.py
```

**Two config regimes — do not mix them.** `configs/entry_chain.dry_run_highest_win.json` is the VPS production-dry-run config (EMA architecture, `disable_probe: true`); `configs/entry_chain.dry_run_fib_pa_v1.json` is the **local analysis / research** config (fib_pa architecture, probe enabled, wider exposure budgets). Their effective thresholds differ by up to 10 points, so every number below is stated per config.

## Architecture

### Layer map (`src/`)

`src/core/module_spec.py` freezes the allowed layers and each layer's responsibilities — treat it as the architectural contract: `config, data, indicators, context, signals, state_machine, risk, execution, portfolio, backtest, reporting, observability, deployment, utils`. Cross-layer reach-through and circular imports are explicitly forbidden patterns.

### The live/dry-run loop (`scripts/run_live_dry_run.py`, ~3.1k lines)

One cycle, per symbol: `build_context` (241 closed bars per TF for `4h`/`1h`/`30m`/`15m`, indicators, per-symbol history) → `evaluate_entry_chain` (the decision core, see *Strategy pipeline*) → `apply_dry_run_decision_controls` (it wraps the entry chain directly, RUN:178) → four-quadrant annotation (Q1–Q4) and channel gates (`q1_green_channel`, `q1_trend_launch`, `q2_pending`, `q3_to_q1`, plus disabled `reversal_pivot` / `q1_rr_gap`) → experimental paths (SCOUT micro ledger, A/B mirror ledgers where `mirror_ab_mode=shadow_only` records but adds no exposure) → paper ledger update (`src/observability/paper_trading.py`) with its JSONL audit writes.

Everything observable goes through `src/observability/decision_audit.py::DecisionAuditWriter` — it is the single writer for `decisions.jsonl`, `order_drafts.jsonl`, `attribution.jsonl`, `near_misses.jsonl`, `scout_decisions.jsonl`, `gate_rejections.jsonl/.csv`. Do not open those files elsewhere. Log layout: `<log_root>/<YYYY-MM>/<YYYY-MM-DD>/…` for daily JSONL + `paper_*` + `runtime.out.HH.log`; rolling paper state at `<log_root>/../state/paper/` (main, `scout_micro/`, `paper_ab/{legacy,trend_capture}/`, `quadrant_pending.json`). Backtest parity: `src/backtest/engine.py` is deliberately isomorphic to this loop (same entry chain, same exit lifecycle), `BacktestBar.taker_buy_volume` comes from klines column 10 and is the only data entry for F5 order flow, and protocol constants live in `src/backtest/protocol.py`.

### Five-factor shadow (P0 contract — read before touching signals)

`src/signals/orthogonal_factors.py` (F1–F5: trend_persistence, structure_location, payoff_geometry, volatility_regime, order_flow) is **shadow-only**: it is written into `decisions.jsonl` as `component_points_v2` + `component_points_v2_meta` by `attach_five_factor_shadow`, and must never feed `total_score`, quadrant, channel gate, leverage or action. `tests/test_five_factor_shadow_readonly.py` enforces this with source-level assertions. Disabling = `five_factor_shadow_enabled: false`. Never raise `--public-kline-limit` to widen the F4 lookback window — it shifts EMA200 and therefore the legacy score.

The only place a shadow number is ever read is `shadow_total → build_gate_features.shadow_pct` (RUN:1090, entry_gate.py:148-149), and `apply_entry_gates` returns immediately when `entry_gates` is empty (RUN:1083-1084) — neither dry-run config sets `entry_gates`, so today the shadow score has **zero** behavioural effect. If someone ever configures `entry_gates`, the shadow score becomes a gate feature; do not do that without an explicit decision record.

### Research layer: `scripts/analysis/fwdlib/`

Forward labeling ("did this decision actually make money?") refactored out of one-off scripts: `config.py` (frozen `LabelConfig` + `fingerprint()`, 12-char sha1, used in result dirs); `labeler.py` (`build_bars` / `resolve_stop` / `label_barrier` / `label_ladder` / `label_at_horizons` / `run_labeling` / `timeout_profile` — bit-for-bit parity with the legacy script, including float operation order, is a hard requirement); `cost.py` (`maker_6` / `hybrid_10` / `taker_20`, `cost_r(bps, stop_pct)`); `baseline.py` (per-decision **matched placebo** — same symbol, UTC day, side, stop_pct — plus `lift_summary` block bootstrap); `stats.py` (Spearman/partial Spearman, block bootstrap, MDE/effective-n, cross-sectional & pooled IC, BH adjustment, `TestLedger` keyed on `(family, label)`, rejects NaN/Inf); `ledger.py` (FIFO leg attribution over `paper_trades.jsonl`); `features.py` (decision-log loading — `profile="six_factor"` matters, ten-factor era rows have different semantics — price-level rebuild, coverage).

Three subtleties that bite:

- **Dual import path.** Scripts first try `from fwdlib…` (works as `python scripts/analysis/x.py`), then fall back to `from scripts.analysis.fwdlib…`. Tests always use the `scripts.analysis.fwdlib` form.
- **Parameter precedence.** `labeler._pick` treats "value equals the legacy default" as "caller did not override", so `cfg` supplies the baseline. Passing the same number as the old default will *not* override the config.
- **`scripts/analysis/fwd_label_20261019.py` is now a thin shim** kept for 7 downstream scripts. It reads its own module-level `ROUND_TRIP_BPS` at call time; importing that name directly would silently label everything at 20bps.

### Spec-as-code and configuration

Each numbered spec doc has a machine-readable twin: `src/**/*_spec.py` (e.g. `src/indicators/indicator_spec.py`) plus a `scripts/describe_*.py` that prints the spec as JSON, plus `tests/test_describe_*.py` asserting the doc contract — changing a spec constant means touching spec module, doc and test together.
- **Runtime config is JSON**: `configs/entry_chain.*.json`, loaded by `src/signals/entry_chain_config.py::load_entry_chain_config` into the frozen `EntryChainConfig` dataclass.
- **`configs/*.yaml` are schema-era artifacts** validated only by `src/config/config_schema.py` and `tests/test_config_schema.py`; nothing loads them at runtime.
- Config edits must be mirrored in `tests/test_dry_run_configs.py` assertions (tier ordering, per-config invariants). There is no CLI override for strategy constants — editing a default in `src/signals/entry_chain_config.py` silently changes **both** dry-run configs.

## Strategy pipeline at a glance

One decision, data → order draft. Read top to bottom; every stage after #4 can only *keep or lower* the action.

| # | Stage | Function / artifact | Where |
|---|---|---|---|
| 1 | Context + aux features | 241 closed bars per TF, 6 indicators, `atr_pct`, `quote_volume_24h`, `extreme_position_ratio`, wick/overextension/chase flags | RUN:2425-2462; FEAT:296-378 |
| 2 | Component scores | `component_scores` → 8 BASE keys **or** 6 fib_pa keys | FEAT:35-71 |
| 3 | Weights | `dynamic_weights(atr_pct)` (BASE) / `EMA_WEIGHTS` / `FIB_PA_WEIGHTS` | ECS:19-83 |
| 4 | Total score | `points[c] = round(clamp(score_c,0,1) × w_c, 4)`, `score = round(Σ points, 4)` → 0–100 | EC:95-96; ECS:86-90 |
| 5 | Fib exhaustion cap | fib_pa only: `fib_action_cap <= 0` → NO_TRADE `FIB_EXTENSION_EXHAUSTION_BLOCK` | EC:99-110 |
| 6 | Hard gates | `hard_block_reason` → NO_TRADE (15 gates, below) | GATE:38-70 |
| 7 | Action + minimums | `_score_to_action` + side offset → WATCH/PROBE/DIRECT; component minimums and `check_probe_conditions` downgrade one step | EC:116-121, 282-296, 351-600 |
| 8 | LONG risk modifiers | overextension / chase / chase with PA<12 / low-liquidity session → cap at WATCH | EC:123-143 |
| 9 | Liquidity, context and sizing caps | `liquidity_ratio` vs 8/20; macro drop → DIRECT→PROBE; ws reconnect → WATCH; high-beta DIRECT→PROBE + re-run probe check; +3% day caps; `symbol_exposure_pct >= cap` → NO_TRADE; `_select_leverage` → 0/2/3/4/5; `_notional_hint` = min of three caps | EC:145-181, 621-754; GATE:82-87 |
| 10 | Controls + order draft | `apply_dry_run_decision_controls` → WATCH; `LiveEntryChainAdapter` → ledger + audit | RUN:2017-2044; LEA:37-65; PT:202-226 |

## Indicators

`src/indicators/indicator_spec.py` is the contract; `compute_indicator_results` returns exactly 6 `IndicatorResult`s in the hard-coded order `("MACD","CCI","BOLL","EMA","CVD","ATR")` (SPEC:18, ENG:68-75).

| Indicator | Params (code defaults) | Role (SPEC:19-26) | Required output keys (DC:74-98) |
|---|---|---|---|
| MACD | fast 12 / slow 26 / signal 9 | trend_momentum | macd_line, signal_line, histogram, histogram_slope, cross_state |
| CCI | period 20 | strength_deviation_recovery | cci, cci_slope, extreme_flag, recovery_flag |
| BOLL | period 20 / std_mult 2.0 | volatility_structure | middle, upper/lower_band, band_width, band_expansion_flag, band_contraction_flag, price_position |
| EMA | 9 / 21 / 50 / 200, slope_lookback 5 | trend_direction_quality_momentum | ema_9/21/50/200, ema50_slope, ema9_21_gap, bars_since_ema50_cross, bars_since_ema200_cross |
| CVD | none | active_buy_sell_pressure | cvd, cvd_delta, cvd_slope, cvd_divergence_flag, buy_pressure, sell_pressure |
| ATR | period 14 | volatility_stop_position_risk | atr, atr_pct, volatility_state |

**Per-TF enable sets** (SPEC:68-73): `4h` = EMA/MACD/BOLL/CCI; `1h` = EMA/MACD/CCI/CVD; `30m` = EMA/MACD/BOLL/CCI/CVD; `15m` = EMA/MACD/CVD/BOLL — no TF has all six (15m has no CCI, 4h has no CVD), and missing any required key fails `validate_indicator_result` (DC:338-344) while bars with `is_closed is not True` are rejected outright (SPEC:109-110). `quality_flag` may be `True`/`"degraded"` for signal use but **direct entry only accepts `True`** (DC:334-335). **Conflict priority** (SPEC:56-66, alias `INDICATOR_PRIORITY`), highest first: `data_quality → cvd_divergence → ema200_direction_gate → macd_trend_direction → ema50_trend_quality → cci_strength → boll_structure → ema9_21_momentum → atr_risk`. **Forbidden uses** (SPEC:75-88, enforced by `validate_indicator_usage`): MACD/EMA never `sole_entry`; CCI/BOLL/CVD never `sole_direction`; MACD/BOLL/EMA never drive `position_size`; EMA never `countertrend_direct`; ATR never produces direction; globally banned at indicator level: `create_order`, `final_position_size`, `bypass_state_machine`, `must_trade`.

**Where direction actually comes from (hard fact).** `direction_from_history` is fed `histories["1h"]` (RUN:2581) — the live chain's direction is a 1h close-vs-4-bars-ago move with a ±0.3% threshold, falling back to 15m's last 3 bars when 1h returns NONE (RUN:2582-2583). `src/context/multi_tf_rules.py` (the 4h/1h/30m/15m role + veto rule engine, MTF:10-50) is **not referenced by the live chain at all** — only `scripts/describe_multi_tf_rules.py` and the scaffold import it. `src/context/multi_tf_context.py:3` does import the MTF rules, but that module is itself unused, so the conclusion is unchanged. What actually runs is `agreement_score`'s kline-percentage approximation, `clamp(0.5 + ret×50)` for LONG and `0.5 - ret×50` for SHORT, over lookbacks of 3 bars (4h), 4 bars (1h), 6 bars (30m) (FEAT:22-47, 264-270) — editing MTF rules changes nothing on the live path. Two further live-vs-spec drifts: BOLL never scores (`market_regime` is the constant `0.8`, FEAT:52), and `cvd_flow` is not real taker CVD — it is `direction × 15m volume` summed over 6 bars, mapped to `1.0 / 0.2 / 0.5` (FEAT:49, 282-293), feeding `flow_cvd_confirmation` unchanged (FEAT:107).

## Entry chain: stages and gates

`evaluate_entry_chain` (EC:86-205) is a strict 22-step sequence:

| Block | Steps | What happens | Where |
|---|---|---|---|
| Pre-flight | 0–4 | symbol exposure cap; `dynamic_weights(atr_pct)`; LONG context discounts; `points`; `score` | EC:91-96 |
| Fib exhaustion + hard gates | 6–7 | fib_pa only: `fib_action_cap <= 0` → NO_TRADE; then `hard_block_reason` → NO_TRADE, first hit wins | EC:99-114; GATE:38-70 |
| Score → action | 8 | `direct/probe/watch` thresholds + side offset | EC:116, 282-296 |
| Minimums + probe | 9–10 | component minimums downgrade; `disable_probe`; `check_probe_conditions` | EC:117-121, 351-485 |
| LONG risk caps | 11–13 | overextension/chase → WATCH; chase with PA<12 → WATCH; low-liquidity session → WATCH | EC:123-143 |
| Macro / data health | 14–15 | macro daily drop or USDT anomaly: DIRECT→PROBE (**not** a block); ws reconnect → WATCH | EC:145-152 |
| Liquidity | 16–17 | `< probe_ratio` → NO_TRADE; `< direct_ratio` and DIRECT → PROBE | EC:154-159 |
| High-beta / daily profit | 18–19 | high-beta DIRECT→PROBE + re-run probe check → WATCH on failure; +3% day: PROBE→WATCH, DIRECT<score+3→PROBE | EC:161-178 |
| Sizing | 20–22 | exposure cap → NO_TRADE; `_select_leverage`; `_notional_hint`; assemble decision | EC:180-205 |

| # | reason (GATE:38-70, evaluated in order) | Condition | Default |
|---|---|---|---|
| 1 | SYMBOL_BLACKLISTED | symbol ∈ `blacklist_symbols` | config: both shipped configs XRPUSDT/ZECUSDT; class default empty |
| 2 | SYMBOL_WATCH_ONLY | symbol ∈ `watch_only_symbols` | config: both ADAUSDT/XMRUSDT |
| 3 | MACRO_WEEKLY_RISK | `macro_weekly_drop_pct <= macro_weekly_drop_block_pct` | −0.15 |
| 4 | DATA_WICK_ANOMALY | `wick_anomaly_active` (high/low > 1.05 and volume < 0.5× prev) | — |
| 5 | DATA_POLLUTION_COOLDOWN | `timestamp <= polluted_until_ts` | — |
| 6 | SYMBOL_POSITION_ALREADY_OPEN | symbol ∈ `active_symbol_names` | — |
| 7 | MAX_ACTIVE_SYMBOLS | `active_symbols >= max_active_symbols` | 5 / **8** (fib_pa_v1) |
| 8 | DAILY_TRADE_BUDGET_USED | `portfolio_trades_today >= daily_max_trades` | `4 × vol_ratio`, floor 1 / **16, floor 2** |
| 9 | SYMBOL_DAILY_TRADE_BUDGET_USED | `symbol_trades_today >= max_symbol_trades_per_day` | 1 / **2** |
| 10 | SYMBOL_COOLDOWN_ACTIVE | `timestamp < cooldown_until_ts` | — |
| 11 | TOTAL_EXPOSURE_CAP | `total_exposure_pct >= max_total_exposure_pct` | 1.50 / **1.6** / **1.2** |
| 12 | SAME_DIRECTION_EXPOSURE_CAP | `same_direction_exposure_pct >= max_same_direction_exposure_pct` | 1.20 / **1.1** / **0.9** |
| 13 | MARGIN_BUFFER_TOO_LOW | `available_margin < equity × margin_buffer_pct` | 0.20 / **0.30** both |
| 14 | ACCOUNT_EQUITY_INVALID | `account_equity <= 0` | — |
| 15 | SIDE_NOT_ALLOWED | side ∉ {LONG, SHORT} | — |

Daily budget formula: `max(min_daily_trades, floor(daily_max_trades_base × current_vol/normal_vol))`, halved again after a +3% day (GATE:73-79). Per-config values above are shown as class default / fib_pa_v1 / highest_win where they differ.

**Do not use the duplicate implementations.** EC:232-259 holds a local `_hard_block_reason` that is **missing the blacklist and watch_only gates**, plus dead `_liquidity_ratio`/`_symbol_exposure_cap` (EC:603-618) and `_rescale_weights`/`_component_points` (EC:212-229). `evaluate_entry_chain` calls the GATE/ECS versions (EC:91-97, 112), so editing the EC copies silently changes nothing — and the local gate list is *wrong*, so never "fix" a gate there.

**Channels** (all in RUN): `q1_green_channel` and `q1_trend_launch` are the same implementation (RUN:1014-1064, 873-935) — data health OK, symbol not blacklisted/watch_only/observation_only, quadrant Q1, `0.20 <= extreme_position_ratio <= 0.80`, LONG triple-risk flags clear, `score ≥ 82`, PA ≥ 18, fib ≥ 15, CVD ≥ 16, RR ≥ 0.5. `q2_pending` needs Q2 + `score ≥ 70` + PA ≥ 18, valid 6×900s, confirmed by momentum + CCI ≥ 9 (RUN:1566-1650). `q3_to_q1` needs source Q3 + `score ≥ 85` + CVD ≥ 16, valid 3×900s, confirmed by quadrant flipping to Q1 with PA ≥ 15 (RUN:1543-1617). `reversal_pivot` and `q1_rr_gap` are **intentionally disabled**. Two channel traps: (a) `q2_pending` builds its entry from the **profit-side (target-side) price band**, while `q1_trend_launch` builds from the **fib retracement zone** — the two band builders are not interchangeable, and mixing them puts the entry on the wrong side of the structure; (b) `q1_trend_launch` sizing is a *second overlay*: `exposure_pct = 0.025 × clamp(rr_points/8, 0.25, 1.0)`, then min() against `_notional_cap_diagnostics`, leverage forced to 1 (RUN:886-900, 931-933) — it is **not** the `raw_notional` path, so never estimate its size with the `_notional_hint` formula.

## Scores, thresholds and weights

### Three architectures coexist (and one early-return disables the other)

`use_ema_architecture` / `use_fib_pa_architecture` select *which scoring architecture* runs; `ema200_gate_mode` only decides whether the EMA200 gate blocks or penalises.

| `use_ema_arch` | `use_fib_pa_arch` | `ema200_gate_mode` | Weights | EMA200 gate | EMA50 minimum | Shipped as |
|---|---|---|---|---|---|---|
| False | False | any | BASE 3-tier (`dynamic_weights`) | **never fires** — `ema_200_gate` key absent, `scores.get(...,1.0)` → 1.0 (EC:372) | skipped | class default |
| True | False | hard | `EMA_WEIGHTS` | `score <= 0` → **NO_TRADE** (EC:372-374) | direct 0.60 / probe 0.40 (EC:390-397) | — |
| True | False | soft | `EMA_WEIGHTS` | allowed, penalty −0.20 (ema_scorer.py:49-51) | direct 0.60 / probe 0.40 | **highest_win** |
| True | True | soft | `FIB_PA_WEIGHTS` | **skipped** — fib_pa early-return (EC:366-371, ECS:56-61); EMA200 only feeds `trend_ema_context` (8 of 20 pts) | **skipped** | **fib_pa_v1** |
| True | True | hard | `FIB_PA_WEIGHTS` | skipped as a gate, but `trend_ema_context` zeroes the whole 20-pt component when the gate fails (FEAT:106, 116-124) | skipped | not used |

So "the EMA200 hard gate" only truly exists in row 2. Under `fib_pa` both the EMA200 block and the EMA50 minimum are unreachable; anyone "tightening the EMA200 gate" on the live config is editing dead logic.

### Class defaults (`EntryChainConfig`)

| Group | Field | Default | Where |
|---|---|---|---|
| Action thresholds | `direct_threshold` / `probe_threshold` / `watch_threshold` | 82.0 / 70.0 / 60.0 | CFG:27-29 |
| Component minimums, direct | `min_direction_direct_score` / `min_quality_direct_score` / `min_trigger_direct_score` / `min_cvd_direct_score` | 0.64 / 0.73 / 0.92 / 0.61 | CFG:30-33 |
| Component minimums, probe | `min_direction_probe_score` / `min_quality_probe_score` / `min_trigger_probe_score` / `min_cvd_probe_score` | 0.56 / 0.45 / 0.67 / 0.45 | CFG:34-37 |
| Volatility bands | `low_vol_atr_pct` / `high_vol_atr_pct` | 0.010 / 0.035 | CFG:38-39 |
| Macro | `macro_daily_drop_block_pct` / `macro_weekly_drop_block_pct` | −0.05 / −0.15 | CFG:40-41 |
| Liquidity | `direct_liquidity_ratio` / `probe_liquidity_ratio` | 20.0 / 8.0 | CFG:42-43 |

### What the two configs override (key deltas only)

| Field | Class default | fib_pa_v1 (research) | highest_win (VPS) |
|---|---|---|---|
| `watch_threshold` | 60.0 | **62.0** | 60.0 |
| `long_threshold_offset` | 0.0 | **10.0** | **10.0** |
| `probe_conditions.enabled` | None | **true** (min_score 72, min_fib 12, min_pa 10, min_rr_score 4) | not configured |
| `probe_conditions.long_threshold_offset` | — | **7.0** | — |
| `disable_probe` | False | false | **true** |
| `use_ema_architecture` / `use_fib_pa_architecture` / `ema200_gate_mode` | F / F / hard | **T / T / soft** | **T / F / soft** |
| `fib_min_direct_score` / `rr_min_direct_score` | 6.0 / 2.0 | **9.0 / 4.0** | 6.0 / 2.0 |
| `direct_risk_pct` / `probe_risk_pct` | 0.008 / 0.003 | **0.006 / 0.0015** | **0.006 / 0.0025** |
| `enable_long_context_discounts` | False | False | **true** (0.70 / 0.60 / 0.75 / 0.80) |

### Effective LONG / SHORT thresholds

| Config | LONG direct | LONG probe | LONG watch | SHORT direct | SHORT probe | SHORT watch |
|---|---|---|---|---|---|---|
| Class default | 82.0 | 70.0 | 60.0 | 82.0 | 70.0 | 60.0 |
| fib_pa_v1 | **92.0** | **77.0** | **72.0** | 82.0 | 70.0 | 62.0 |
| highest_win | **92.0** | 80.0 (`disable_probe` → NO_TRADE) | **70.0** | 82.0 | 70.0 (same) | 60.0 |

The two layers **replace, they do not add** (EC:282-317): `_side_threshold_offset` picks `long_threshold_offset` (10.0); `_probe_threshold_offset` *overrides* it with `probe_conditions.long_threshold_offset` (7.0) when `probe_conditions.enabled` is true and that key exists (EC:310). That is why LONG probe lands at 77.0 — **3 points below** the LONG side offset — and why "7 + 10 = 17" is wrong. SHORT layers are both 0. The applied offset is recorded as `SIDE_THRESHOLD_OFFSET_{side}_{offset:.2f}` (EC:284-285) and is the admission key for `HIGH_SCORE_LONG_OFFSET_PROBE` (RUN:1368).

### Weights

`FIB_PA_WEIGHTS` (ECS:43-50, used by fib_pa_v1) — six components, sum 100; the normalisation denominators in FEAT:108-111 match these weights one-for-one:

| Component | Weight | Normaliser |
|---|---|---|
| `trend_ema_context` | 20 | (gate 8 + ema50×7 + momentum×5)/20 |
| `flow_cvd_confirmation` | 18 | = `cvd_flow` |
| `cci_momentum_quality` | 14 | `min(1, cci_score/14)` |
| `price_action_structure` | 22 | `min(1, pa_score/22)` |
| `fibonacci_location` | 18 | `min(1, fib_score/18)` |
| `risk_reward_geometry` | 8 | `min(1, rr_score/8)` |

`BASE` three-tier `dynamic_weights` (ECS:19-28, only when **both** architecture switches are false) — only four cells are pinned, everything marked *rescaled* is `_rescale_weights` linear scaling of the BASE proportion with drift given to `background_4h` (ECS:73-83), sum always 100.000000:

| Component | base (0.010 ≤ atr% ≤ 0.035) | low vol (< 0.010) | high vol (> 0.035) |
|---|---|---|---|
| `background_4h` | 8.0 | rescaled | rescaled |
| `direction_1h` | 25.0 | rescaled | rescaled |
| `quality_30m` | 22.0 | rescaled | rescaled |
| `trigger_15m` | 12.0 | **fixed 18.0** | rescaled |
| `cvd_flow` | 18.0 | **fixed 18.0** | **fixed 10.0** |
| `volatility_stop` | 10.0 | rescaled | **fixed 20.0** |
| `liquidity_execution` | 3.0 | rescaled | rescaled |
| `market_regime` | 2.0 | rescaled | rescaled |

`EMA_WEIGHTS` (ECS:30-41): background 5 / direction 18 / quality 12 / trigger 7 / **ema_50_quality 15 / ema_momentum 10** / cvd 18 / vol 10 / liquidity 3 / regime 2.

### fib_pa component minimums and probe conditions

Direct minimums compare **points**, not normalised scores (EC:438-447):

| Stage | Component | Weight | Minimum points | Source |
|---|---|---|---|---|
| direct | `price_action_structure` | 22.0 | 6.0 | CFG:181 |
| direct | `fibonacci_location` | 18.0 | **9.0** (default 6.0) | fib_pa_v1:187 |
| direct | `risk_reward_geometry` | 8.0 | **4.0** (default 2.0) | fib_pa_v1:188 |

Failure degrades direct → PROBE (EC:450-452), probe → WATCH (EC:483-485); with `probe_conditions.enabled=false` the fib_pa probe minimums return input unchanged (EC:465-467). `check_probe_conditions` (EC:513-600), in order: (1) `enabled` else `PROBE_DISABLED`; (2) total `min_score` = 72.0; (3) structure minimums fib ≥ 12.0, pa ≥ 10.0 (high-beta variant pa 12 / rr 5 / cci 9 / ema 12); (4) low-score quality veto — score < 75 and (ema < 10 or cci < 7) → reject; (5) ema < 10 **and** cci < 9 → reject; (6) elite rule — score ≥ 75 and ((pa ≥ 18 and fib ≥ 15) or (ema ≥ 15 and pa+fib ≥ 30)); (7) RR — `min_rr_score` = 4.0.

### Dead switches and no-op config

- `probe_conditions.min_rr_net_r` (1.3) — the live chain passes `rr_detail=None` (EC:480, hard-coded), so the `net_tp1_r` branch never runs; only `min_rr_score` matters.
- `max_active_probes` — no reader at all; the gate uses `max_active_symbols`.
- `dry_run_q1_green_channel_*` (7 fields: `enabled` / `notional_mult` / `min_score` / `min_pa_score` / `min_cvd_score` / `base_exposure_pct` / `exit_mode`, CFG:139-145) — `q1_green_channel` is the same code path as `q1_trend_launch`, which reads the `dry_run_q1_trend_launch_*` fields (RUN:984-993).
- `base_direct_exposure_pct` (0.20) — defined on the dataclass, never consumed on the live path.
- `enable_long_context_discounts` on fib_pa: `_apply_long_context_discounts` (EC:320-343) scales `quality_30m` and `ema_50_quality` ×0.70 on overextension, `trigger_15m` ×0.60 (upper wick) / ×0.75 (chase), `cvd_flow` ×0.80 (weak CVD), then clamps [0,1]. **None of those four keys exists in `FIB_PA_WEIGHTS`**, so it is a no-op on fib_pa_v1 and only bites in BASE/EMA architecture — i.e. only `highest_win` among the two shipped configs, which turns it on.

## Position sizing

Two paths exist and they do not talk to each other. **Path A — live (what actually sizes an order)** is `_notional_hint` (EC:669-754):

| Term | Formula | Where |
|---|---|---|
| `stop_pct` | `context.stop_pct`, else `clamp(atr×1.5, 0.005, 0.04)` | EC:696-698 |
| `raw_notional` | `equity × risk_pct / stop_pct` | EC:723-724 |
| `leveraged_cap_notional` | `equity × max_single_trade_risk_pct(0.0075) / (stop_pct × leverage)` | EC:725-727 |
| `remaining_exposure_notional` | `max(0, (max_symbol_exposure_pct − symbol_exposure_pct) × equity)` | EC:728-730 |
| `final_notional` | `min()` of the three; `binding_cap` names the winner | EC:746-747 |

Worked dry-run case (fib_pa_v1's `direct_risk_pct = 0.006`; with the class default 0.008 `raw_notional` would be 2666.67 instead of 2000): equity 10000, `stop_pct` 0.03, DIRECT leverage 4, ETH cap 0.30 → raw 2000, leveraged_cap 625, remaining 3000 → **final 625**, `binding_cap=leveraged_cap_notional`. A second cap is applied when the decision is assembled (EC:783-794); a non-PROBE/DIRECT action returns all zeros (EC:677-686). Then `quantity = notional_hint / price` (LEA:46). `min_quantity` defaults to **0.0** (LEA:34) and RUN never passes it (RUN:312-320), so the exchange minimum order size is **never validated** — `quantity > 0` is the only check (LEA:37-48). MARKET orders only, `reduce_only=False` (LEA:51-65).

**Path B — `src/risk/position_sizer.py`: spec only, not wired.** It implements DIRECT/PROBE multipliers (1.0 / 0.25), tier multipliers (A 2.0 / B 1.0 / C 0.75), volatility multipliers (NORMAL 1.0 / HIGH 0.5 / EXTREME 0.0), `standard = equity×risk_pct / stop_pct`, `quantity_step` floor rounding, 7 NO_TRADE gates and four exposure caps (total / symbol 0.20 / side 0.75 / correlation 0.50) — none of it runs on the live path. Do not describe it as a production risk layer, and do not "fix" sizing there.

### Leverage (`_select_leverage`, EC:621-642, short-circuit order) and stop-width trap

| # | Condition | Leverage |
|---|---|---|
| 1 | action ∉ {PROBE, DIRECT} | 0 |
| 2 | `rolling_sharpe_20 < 0` | **2** (`ROLLING_SHARPE_LEVERAGE_CAP`) |
| 3 | `atr_pct > 0.03` | **3** |
| 4 | `atr_pct > 0.015` | DIRECT → 4, PROBE → 3 |
| 5 | `score ≥ 90` and DIRECT | 5 if `_fib_pa_5x_requirements_met` (fib ≥ 13/18, pa ≥ 9/22, cci ≥ 7/14, rr ≥ 4/8), else 4 |
| 6 | fallback | DIRECT → 4, PROBE → 3 |

The exposure cap behind `remaining_exposure_notional` is 0.30 large-cap / 0.20 mainstream / 0.10 high-beta (GATE:90-98). `q1_trend_launch` bypasses the whole table with a hard leverage of 1 (RUN:931-933).

**The `0.005–0.04` / `0.03` trap.** `_notional_hint`'s `raw_notional` denominator is the **entry-side** `stop_pct`, clamped to `[min_stop_pct=0.005, max_stop_pct=0.04]` (CFG:58-59; RUN:2616) — *not* `paper_trading`'s `MAX_STOP_PCT = 0.03` dataclass default. Mixing them puts notional and stop distance 33% apart. Before touching any stop constant anywhere, run `grep -n "0.03\|0.04"` across `src/` and `scripts/` and check which side of the entry/exit boundary you are on.

## Risk and exits

### Where each constraint lives (three layers)

The outer layers cannot override each other: `entry_chain` blocks with `NO_TRADE` before a draft exists (the adapter then returns `approved=False`, LEA:37-40); `apply_dry_run_decision_controls` can only **downgrade an already-approved decision** to WATCH, zeroing leverage/notional; the paper ledger owns everything after the fill. Nothing downstream can un-downgrade or un-block.

| Constraint | Effective value | Layer | Where | Failure mode |
|---|---|---|---|---|
| per-trade risk `direct/probe risk_pct`, then `max_single_trade_risk_pct` | 0.006 / 0.0015 (fib_pa_v1), default 0.008 / 0.003; hard cap 0.0075 | entry_chain — `raw_notional`, then `leveraged_cap_notional` | EC:723-727 | no block; sets the notional ceiling, then usually binds it |
| symbol exposure cap | 0.30 / 0.20 / 0.10 | entry_chain (remaining min) **and** hard gate | EC:728-730; EC:180-181 | NO_TRADE `SYMBOL_EXPOSURE_CAP` |
| portfolio total / same-direction exposure | 1.6 · 1.1 (fib_pa_v1), 1.2 · 0.9 (highest_win); default 1.50 · 1.20 | hard gates | GATE:60-63 | NO_TRADE `TOTAL_EXPOSURE_CAP` / `SAME_DIRECTION_EXPOSURE_CAP` |
| margin buffer | 0.30 both configs (default 0.20), compared against `available_margin = 0.8×initial_equity − Σ(notional×remaining/leverage)` | hard gate | GATE:64-65; RUN:2055, 2968-2969 | NO_TRADE `MARGIN_BUFFER_TOO_LOW` |
| position count / trades per day | 8 / 5 concurrent; 2 / 1 per symbol per day; 16× / 4× volatility ratio total, floors 2 / 1 | hard gates, counted from the paper snapshot | GATE:52-57, 73-79; PT:570-582 | NO_TRADE `MAX_ACTIVE_SYMBOLS` / `*_TRADE_BUDGET_USED` |
| portfolio cooldown / circuit / weak-edge | see the breaker table below | dry-run controls (outside entry_chain) | RUN:2017-2044 → 2088-2097 | whole decision → WATCH with leverage/notional zeroed, except the war-fund and scout rows which reject at the experiment/scout entry |
| hold time / cost breakeven / TP rhythm | 32 bars / 8 bars / 1.2-2-3R | paper ledger, decoupled from the entry decision | PT:18-22 | close or scale out |

Practical consequence for a code change: locate the layer first. A **strategy** threshold edited in `src/signals/entry_chain_config.py` moves the entry_chain rows and the gate rows; the breaker rows have their own fields in the same dataclass (`post_initial_stop_cooldown_hours` CFG:215, `rolling_symbol_cooldown_*` CFG:192-195, `portfolio_stop_circuit_*` CFG:216-218, `portfolio_daily_loss_limit` CFG:220, `weak_edge_*` CFG:188-191), so check both groups before assuming which layer you touched. Editing `apply_dry_run_decision_controls` changes nothing about what the paper ledger does to an open position. Note also that both `entry_chain` rows for the symbol cap are live: `remaining_exposure_notional` shrinks the size and the hard gate can still refuse the trade outright.

### Paper exit lifecycle (`src/observability/paper_trading.py`)

`PaperTradingLedger._update_position` (PT:287-351, entered from `on_decision` PT:176) runs per bar; the first matching step wins:

| # | Trigger | Action | Where |
|---|---|---|---|
| 0–1 | not newer than entry / last_processed → skip; else update `best_price` / MFE-R | idempotence, then MFE bookkeeping | PT:294-299, 722-734 |
| 2 | MFE ≥ 1.0 R, no TP yet, early breakeven enabled | stop → breakeven (pilot, see note) | PT:300, 786-804; RUN:583-589 |
| 3 | a TP already filled | `_apply_post_tp_stop` | PT:301-302 |
| 4 | stop crossed by high/low | full exit `INITIAL_STOP_HIT` / `BREAKEVEN_STOP_HIT` | PT:306-310 |
| 5 | Q2 → stop to breakeven; Q4 with `streak >= 2` and net loss | full exit `Q4_DEFENSIVE_EXIT` | PT:312-318 |
| 6 | quadrant Q3, first time | halve the position `Q3_DEFENSIVE_REDUCE` | PT:319-326 |
| 7 | TP hit (`1.2R/2.0R/3.0R`) | reduce `TP{n}_HIT` by 40% / 35% / 25%; after TP1 stop → breakeven; 0 remaining → drop | PT:327-342 |
| 8–9 | timeout exits: `COST_BREAKEVEN_TIMEOUT` (≥ 8 bars, never TP'd, gross < 0.5× round-trip cost) or `MAX_HOLD_EXIT` (≥ 32 bars = 8h) | full exit | PT:343-350, 705-719 |

**Scope and three facts.** Steps 5 and 6 only apply when `position.experiment_id` is set (PT:748, 761, 771) — **quadrant defence is reserved for experiment-ledger positions** (`q1_trend_launch` / `scout_micro` / mirror), while main PROBE/DIRECT positions get no Q2/Q3/Q4 protection. (a) Early breakeven is **not** "never enabled": the main ledger runs it off (RUN:555-570 never passes the flag), but the AB research ledger's `trend_capture` branch turns it on via `config.mirror_ab_payoff_pilot_enabled` (RUN:583-589), which fib_pa_v1 sets to true (:114) with trigger 1.0R (:115) — so those research positions move to breakeven at 1.0R while main-ledger positions do not. (b) `MAX_HOLD_BARS = 32` and the cost-breakeven rule (8 bars, `buffer 0.5`) are **hard-coded constants** (PT:18-20); neither config can override them, so there is no config knob for holding time. (c) 32 bars is documented as 8 hours, confirming the bar unit is 15m.

**Do not touch position/exit logic before grepping the assignment site.** Q3 halving depends on `q4_streak` / `q3_reduced` on `PaperPosition` (PT:117-118) and on `decision_payload["quadrant"]`, which `run_live_dry_run` re-supplies every cycle. `consecutive_negative_bars` does not exist — grepping it returns nothing, so never code against it. If the re-supply stops, defence silently never triggers — no error, just no halving. Start with `grep -n "q4_streak\|decision_payload.get(\"quadrant\")" src/observability/paper_trading.py scripts/run_live_dry_run.py`.

Post-TP stops (PT:807-825): non-`trend_capture` → always breakeven. `trend_capture` → breakeven while MFE-R < 1.5, then trail at `best_price ∓ risk_distance × 1.0`, tighten-only. Breakeven price is `entry × 1.001 / 0.999` (10bps buffer). Exit mode comes from `paper_exit_config()` (RUN:555-570): main ledger `paper_exit_mode` (default `legacy`), scout ledger `scout_micro_exit_mode` (fib_pa_v1 = `trend_capture`), A/B ledgers force both modes. Stop width resolves in three steps (PT:25-56): `decision_payload["stop_pct"]` (the live chain does not produce it) → `metadata.risk_budget.stop_pct` (**this is what actually hits**, written at EC:750) → fallback `atr_pct × 1.5` clamped to `[min_stop_pct, max_stop_pct]` with missing ATR defaulting to 0.01. The runtime clamps 0.005–0.04 because `PaperExitConfig(min_stop_pct=..., max_stop_pct=...)` is built from the entry-chain config (RUN:555-570), overriding the `MAX_STOP_PCT = 0.03` dataclass default; PT:32-38 records the historical 3%-vs-4% bug in a comment.

### Portfolio cooldowns and circuit breakers (all in `run_live_dry_run.py`)

All rows except the last three go through `_cap_decision_to_watch`; the war-fund breaker and the two scout rows reject at the experiment/scout entry instead (`entry_near_miss = None` when the circuit is active, RUN:235-241; RUN:1418-1438, 1441-1462).

| Mechanism | Condition | fib_pa_v1 |
|---|---|---|
| Observation-only symbol | symbol ∈ `observation_only_symbols` → `SYMBOL_OBSERVATION_ONLY` (RUN:2028-2029) | config: XLMUSDT/TONUSDT (highest_win: XLMUSDT; class default empty) |
| Per-symbol post-stop cooldown | symbol had `INITIAL_STOP_HIT` within 4h | on, 4h |
| Rolling cooldown | ≥2 stops in 48h → 24h cooldown | on (2 / 48 / 24) |
| Consecutive-stop breaker | last N trades all `INITIAL_STOP_HIT` → H hours no new entries | on (2 / 2h) |
| Daily loss breaker | day Σ`position_realized_pnl` ≤ −30 | on |
| Weak-edge downgrade | DIRECT 82–85 / PROBE 77–82 with no profit history on that symbol → WATCH | 82-85 / 77-82 |
| Experiment war-fund breaker | same `experiment_id`: cumulative ≤ −150 or day ≤ −200 | on |
| Scout cooldown | same direction 2h; after a stop 6h | on |
| Scout mission breaker | 3 consecutive stops in one mission → 12h pause | on |

For those capping rows, downgrade is applied by `_cap_decision_to_watch`: `action=WATCH`, `side=NONE`, `risk_allowed=False`, `leverage=0`, `notional_hint=0` (RUN:2088-2097). It is the last writer, so nothing downstream can resurrect a capped decision. `apply_dry_run_decision_controls` (RUN:2017-2044) has **no equivalent in `src/`** — backtests and any non-dry-run caller do not get these protections.

### `src/risk/` is largely not wired (read this before assuming a safety net)

Only `net_beta_exposure_model` and `stress_simulator` are imported by the live chain (RUN:27-32), and **both are pure observation**:

- **net beta** — static beta table (BTC 1.00, ETH 1.05, SOL 1.25, HYPE/LAB/CC 1.80, unknown 1.20; NBE:7-26), `net_beta = Σ signed × beta × notional × remaining / equity` (NBE:45), cap `0.50` with `static_v1_observation_only` (NBE:27-28). RUN only writes a summary (RUN:808-823); `net_beta_exposure_within_limit` (NBE:49-50) is **never called**.
- **stress** — `stress_loss_pct = exposure_pct × leverage × adverse_move_pct` (SS:4-5). The exposure passed in is `decision.max_symbol_exposure_pct` (**the symbol cap**, not this trade's notional/equity), adverse 0.20, max 0.25 (RUN:303-308, 432-433). It emits `action="BLOCK"` over the cap, but **no code reads `stress["action"]` to decide an order** — BTC 0.30×4×0.20 = 0.24 → ALLOW; leverage 5 → 0.30 > 0.25 → BLOCK that still executes.

`position_sizer`, `risk_engine`, `exit_engine`, `stop_engine`, `portfolio_guard`, `cooldown_guard` are referenced only by `scripts/describe_*.py`, `tests/` and `scripts/scaffold_ai300_framework.py`; `exit_engine`/`stop_engine` are additionally called *internally by* `risk_engine` (RE:227-234, 384, 435), which does not make them live. `portfolio_guard.exposure_allowed` and `cooldown_guard.is_cooldown_active` have no callers at all — their jobs are done by GATE:60-61 and GATE:58-59. Label all of these **"spec only, not wired"**. Two spec-vs-implementation forks prove the point: `risk_engine.take_profit_plan` uses **1.0/2.0/3.0R at 30/40/30%** while the live paper ledger uses **1.2/2.0/3.0R at 40/35/25%** (exit_engine.py:42-69, RE:374-385 vs PT:20-22), and its legal stop ceiling is **0.08** against the live clamp of **0.04** (RE:466-475 vs CFG:59). `risk_engine`'s other constants (daily loss 5% / weekly 12% / max drawdown 20% / single-symbol 20%, RE:102-114) likewise describe intent, not behaviour.

**`entry_chain` is the only position source.** RUN imports the private `_notional_cap_diagnostics` directly (RUN:33) and calls it at 3 sites — `q1_trend_launch` (RUN:891), `scout_micro` (RUN:1769), `mirror_ab` (RUN:1879) — so every channel, including the experiments, sizes through the same function. There is no second sizing implementation running in parallel; `position_sizer` is a document-level spec, not a shadow layer. One known *looseness* to keep in mind: the scout and q1 channels rebuild `EntryChainContext` by hand (`_experimental_risk_context` RUN:1710-1744, `_q1_risk_context_from_near_miss` RUN:938-965) and set `available_margin` straight to `current_equity` (RUN:1741, 959) instead of the main ledger's `0.8×initial_equity − Σ occupied` — so their margin-buffer gate is looser by the 0.8 factor. Whether that is intended cannot be determined from the code.

**Exposure denominators.** `get_portfolio_state_snapshot` computes every exposure and the daily return against **`initial_equity`** (PT:561-563, 592), and RUN then scales by `exposure_scale = initial_equity / current_equity` (RUN:2073-2083) — profitable accounts get more conservative, losing accounts get looser. Any new exposure metric must use the same denominator or it will not be comparable to the gates.

## Conventions that matter

- **Time.** Data and logs use real UTC; reports and analysis prose use Beijing time (UTC+8). In `decisions.jsonl`, top-level `timestamp` = decision moment, `kline.timestamp` = bar open; daily archiving keys off the top-level timestamp.
- **PnL.** Account-level result = `notional_pnl` / `position_realized_pnl`; `margin_pnl` is the leverage-inflated margin-report view. Never mix them in one table.
- **Tests.** New logic ships with pytest. Anything touching risk/offense must first be validated through dry-run / paper / SCOUT / A-B before being called a fix.
- **Config changes are test-anchored.** `tests/test_dry_run_configs.py` is the assertion surface for every config JSON (tier ordering, per-config invariants). Changing a threshold without updating it leaves the suite red — that is the intended tripwire, not an obstacle.
- **`stop_pct` has one source on both sides of the trade.** Entry sizing and exit stop placement must resolve the same value (entry-side clamp 0.005–0.04, exit-side `PaperExitConfig` built from the same config). The historical bug — `paper_trading` clamping at 0.03 while the entry chain allowed 0.04 — is why positions sized on a 4% stop could exit on a 3% stop. Never change one side alone.
- **Do not** globally relax risk-reward geometry gates or remove symbols from the blacklist (XRPUSDT/ZECUSDT) without an explicit decision record. **New channels get their own experiment ledger**, never the main one — they must set `experiment_id` so quadrant defence and war-fund breakers scope correctly.
- **Sample discipline.** `<10` trades: no "works/doesn't work" verdict. `<20`: no parameter tuning or resource reallocation (`scripts/channel_cumulative_tracker.py` constants). Minor-window `lift` results are likewise not decision-grade — round reports go to `docs/` (Chinese), status is tracked in `docs/recommendations_tracking.md`, run `recommendation_tracker.py check` at the start and flip status to DEPLOYED/VERIFIED at the end, with conclusions bound to the pre-registered full-sample window (`docs/analysis/fwd_label_v2_2026-10-19.md` §3.2).
- **Deliverable discipline.** Analysis scripts live in `scripts/` / `scripts/analysis/`; no inline `python -c` for deliverables; intermediate artifacts go to `logs/analysis/` or `reports/` (both git-ignored).
- **Before merging a strategy change**, run at minimum `python -m pytest tests/test_dry_run_configs.py tests/test_entry_chain.py tests/test_paper_trading.py -q`. A source-level audit (like the 2026-10-19 one) only verifies hunk by hunk; these three files are the behavioural net.
- **Deployment.** Code is delivered locally and the user syncs the VPS (`docs/runbooks/offense-fix-deploy.md`); after a systemd restart, run the online verification script before calling it done.
- **Git.** Branches are topic/date named (`09-27-5factor`, `workbuddy/feat-…`). If github.com is unreachable: `git -c http.proxy=http://127.0.0.1:12334 push`. Never commit `.reasonix/`, `.pytest_tmp_*`, `docs/80-07-00.txt` (historical leftovers). `logs/`, `data/`, `reports/`, `.env*`, keys are ignored.

## Known baseline issues (do not "fix" by accident)

- `python -m pytest tests/ -q --ignore=tests/test_verify_five_factor_orthogonality.py` currently reports **838 passed, 1 failed** (839 collected, ~54s): `test_describe_indicator_rules.py` — known EMA/RSI indicator-names contract drift (spec says `EMA`, doc-era test expects `RSI`). The two `test_verify_q1_trend_launch_fix` cases pass now that `logs/` exists; without numpy the ignored file aborts collection instead (see Commands).
- `stop_pct` clamp inconsistency (0.04 in `EntryChainConfig` vs 0.03 in `paper_trading` / `fwdlib/config.py`) is **known and deliberately unfixed** — see the matching Conventions bullet for the two-sided rule and the disclosure in `docs/analysis/fwd_label_v2_2026-10-19.md` §3.5.
- `mirror_ab` runs `shadow_only` only under fib_pa_v1 (`mirror_ab_enabled: true` + `mirror_ab_mode: "shadow_only"`, :112-113); highest_win has no `mirror_ab` block at all (default `mirror_ab_enabled=false`). `reversal_pivot` and `q1_rr_gap` channels are intentionally disabled. The LONG-side `long_threshold_offset` two-layer offset (7.0 replaces 10.0 — not additive) is intentional.
- Two classes of dead code, detailed in the sections above: the duplicate `_hard_block_reason` / `_liquidity_ratio` / `_symbol_exposure_cap` / `_rescale_weights` / `_component_points` in `entry_chain.py` (see *Entry chain: stages and gates*), and the dead config keys `min_rr_net_r`, `max_active_probes`, `base_direct_exposure_pct` plus the seven `dry_run_q1_green_channel_*` fields (see *Dead switches and no-op config*).
