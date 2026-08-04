# Four Quadrant Aggressive Dry-Run Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the existing four-quadrant labels into dry-run executable entry, scout, A/B sampling, and experiment-position exit behavior.

**Architecture:** Keep exchange mutation untouched. Add dry-run-only conversion logic in `scripts/run_live_dry_run.py`, extend `EntryChainConfig` for experiment controls, and add minimal per-position metadata in `PaperTradingLedger` so experiment positions can use trend capture and Q4 defensive exits. Persist pending quadrant confirmations as JSON under the paper state directory.

**Tech Stack:** Python 3, pytest, JSONL dry-run logs, existing `PaperTradingLedger`.

## Global Constraints

- Do not modify real exchange order submission or `src/api/binance_client.py`.
- No lookahead: Q2/Q3 pending confirmation uses only earlier pending state and the current closed candle decision.
- Main Q1 green channel is dry-run/paper only and still goes through `PaperTradingLedger`.
- Preserve existing hard safety controls: blacklist, data health, daily loss circuit, rolling cooldown, same-symbol open checks, portfolio exposure checks.
- Every experimental entry must include `experiment_id` and `entry_channel`.
- Verification commands: `pytest tests/test_entry_chain_config.py tests/test_dry_run_configs.py tests/test_live_dry_run.py tests/test_paper_trading.py -q`.

---

### Task 1: Add Dry-Run Experiment Config Fields

**Files:**
- Modify: `src/signals/entry_chain_config.py`
- Modify: `configs/entry_chain.dry_run_fib_pa_v1.json`
- Modify: `tests/test_entry_chain_config.py`
- Modify: `tests/test_dry_run_configs.py`

**Interfaces:**
- Produces config fields used by later tasks:
  - `dry_run_q1_green_channel_min_score: float`
  - `dry_run_q1_green_channel_min_pa_score: float`
  - `dry_run_q1_green_channel_min_cvd_score: float`
  - `dry_run_q1_green_channel_base_exposure_pct: float`
  - `dry_run_q1_green_channel_exit_mode: str`
  - `scout_micro_q1_rr_gap_min_cvd_score: float`
  - `scout_micro_q2_pending_enabled: bool`
  - `scout_micro_q2_pending_min_score: float`
  - `scout_micro_q2_pending_min_pa_score: float`
  - `scout_micro_q2_pending_confirm_bars: int`
  - `scout_micro_q2_pending_confirm_cci_score: float`
  - `quadrant_pending_state_enabled: bool`
  - `mirror_ab_include_q1_watch: bool`
  - `experiment_war_fund_loss_limit: float`
  - `experiment_daily_loss_limit: float`

- [ ] **Step 1: Add failing config assertions**

Add new values to the JSON string in `tests/test_entry_chain_config.py::test_load_entry_chain_config_from_json` and assert they load with the expected values.

- [ ] **Step 2: Implement dataclass fields**

Add the fields to `EntryChainConfig` with conservative defaults matching current behavior: green channel disabled, Q2 pending disabled, persistent pending enabled, A/B Q1 WATCH disabled.

- [ ] **Step 3: Enable active dry-run config**

Set `dry_run_q1_green_channel_enabled=true`, `mirror_ab_min_score=82.0`, `mirror_ab_include_q1_watch=true`, Q2 pending enabled, and Q1 RR gap CVD minimum to `16.0` in `configs/entry_chain.dry_run_fib_pa_v1.json`.

- [ ] **Step 4: Run config tests**

Run: `pytest tests/test_entry_chain_config.py tests/test_dry_run_configs.py -q`

---

### Task 2: Implement Q1 Main Paper Green Channel

**Files:**
- Modify: `scripts/run_live_dry_run.py`
- Modify: `tests/test_live_dry_run.py`

**Interfaces:**
- Produces `apply_q1_green_channel(...) -> tuple[EntryChainDecision, dict[str, Any]]`.
- Consumes quadrant helpers and active config fields from Task 1.

- [ ] **Step 1: Add tests**

Add tests that:
- A Q1 WATCH near-miss with score >=85, PA >=18, CVD >=16, non-blacklisted symbol, and RR gap reason converts to a paper `PROBE`.
- Converted decisions include `experiment_id="four_quadrant_aggressive_v1"`, `entry_channel="q1_green_channel"`, `exit_mode="trend_capture"`.
- Notional scales by `max(0.25, risk_reward_geometry / 8.0)` from `dry_run_q1_green_channel_base_exposure_pct`.
- Blacklisted symbols do not convert.

- [ ] **Step 2: Implement green-channel helper**

In `scripts/run_live_dry_run.py`, after quadrant annotation and near-miss construction, convert eligible near-misses into an approved paper-only `EntryChainDecision` before building the order draft. Do not change exchange mutation behavior.

- [ ] **Step 3: Update assumptions output**

Include the new green-channel thresholds and base exposure in `dry_run_assumptions()`.

- [ ] **Step 4: Run targeted tests**

Run: `pytest tests/test_live_dry_run.py::test_q1_green_channel_converts_rr_gap_watch_to_probe tests/test_live_dry_run.py::test_q1_green_channel_rejects_blacklisted_symbol -q`

---

### Task 3: Add Q2 Pending and Persistent Pending State

**Files:**
- Modify: `scripts/run_live_dry_run.py`
- Modify: `tests/test_live_dry_run.py`

**Interfaces:**
- Produces:
  - `build_q2_pending_candidate(...) -> dict[str, Any] | None`
  - `confirm_q2_to_q1_pending(...) -> dict[str, Any] | None`
  - `load_quadrant_pending_state(path: Path) -> dict[str, dict[str, Any]]`
  - `write_quadrant_pending_state(path: Path, pending: Mapping[str, Mapping[str, Any]]) -> None`

- [ ] **Step 1: Add tests**

Add tests for Q2 pending creation, Q2-to-Q1 confirmation, expiry, and persistence round-trip.

- [ ] **Step 2: Implement helper logic**

Create Q2 pending when quadrant is Q2, score >=85, PA >=18, and side is LONG/SHORT. Confirm only when the same symbol and side enters Q1 within `confirm_bars * 900` seconds and CCI >= configured threshold.

- [ ] **Step 3: Wire into main loop**

Load pending state from `paper_state_dir/quadrant_pending.json` before the run loop and write it after each cycle when enabled.

- [ ] **Step 4: Run targeted tests**

Run: `pytest tests/test_live_dry_run.py::test_q2_pending_confirmation_marks_scout_mission tests/test_live_dry_run.py::test_quadrant_pending_state_round_trips -q`

---

### Task 4: Expand SCOUT and Mirror A/B Routing

**Files:**
- Modify: `scripts/run_live_dry_run.py`
- Modify: `tests/test_live_dry_run.py`

**Interfaces:**
- Adds SCOUT mission `Q2_PENDING_MOMENTUM`.
- Adds `source_quadrant` to mirror A/B sample payloads.

- [ ] **Step 1: Add tests**

Add tests that:
- `Q1_RR_GAP_SCOUT` requires CVD >=16.
- Q2 confirmation returns `Q2_PENDING_MOMENTUM`.
- LONG offset Q1 probe still routes with high-beta notional halved.
- mirror A/B allows score >=82 Q1 WATCH when `mirror_ab_include_q1_watch=true`.
- mirror A/B payload includes `source_quadrant`.

- [ ] **Step 2: Implement mission routing**

Add `Q2_PENDING_MOMENTUM` before other generic missions. Add CVD check to Q1 RR gap.

- [ ] **Step 3: Expand mirror eligibility**

Allow Q1 WATCH samples by score threshold and include source quadrant metadata in synthetic payloads.

- [ ] **Step 4: Run targeted tests**

Run: `pytest tests/test_live_dry_run.py -q`

---

### Task 5: Add Experiment Metadata and Q4 Defensive Exit

**Files:**
- Modify: `src/observability/paper_trading.py`
- Modify: `tests/test_paper_trading.py`

**Interfaces:**
- `PaperPosition` stores:
  - `experiment_id: str | None`
  - `entry_channel: str | None`
  - `source_quadrant: str | None`
  - `q4_streak: int`
- `PaperTradingLedger.on_decision()` reads current `decision_payload["quadrant"]` for open experiment positions.

- [ ] **Step 1: Add tests**

Add tests that:
- experiment metadata persists into open/close trade events and `paper_positions.json`;
- an experiment position exits with `Q4_DEFENSIVE_EXIT` after two consecutive Q4 updates while unrealized PnL is negative;
- a non-experiment position does not exit from Q4 rule.

- [ ] **Step 2: Implement metadata fields**

Extend `PaperPosition`, `_open_position()`, close event payload, and `_load_positions()` defaults.

- [ ] **Step 3: Implement Q4 defensive exit**

Before TP/timeout logic, if a position has `experiment_id`, current quadrant is Q4 for two consecutive processed bars, and unrealized net PnL is negative, close remaining fraction at current close with reason `Q4_DEFENSIVE_EXIT`.

- [ ] **Step 4: Run targeted tests**

Run: `pytest tests/test_paper_trading.py -q`

---

### Task 6: Final Verification and Report

**Files:**
- Modify: `docs/superpowers/reports/2026-07-21-four-quadrant-aggressive-dry-run-implementation.md`

**Interfaces:**
- Produces implementation report for user/VPS replacement.

- [ ] **Step 1: Run full verification**

Run: `pytest tests/test_entry_chain_config.py tests/test_dry_run_configs.py tests/test_live_dry_run.py tests/test_paper_trading.py -q`

- [ ] **Step 2: Write implementation report**

Create a short MD report listing implemented changes, exact dry-run-only boundaries, verification output, and deployment notes for VPS script replacement.
