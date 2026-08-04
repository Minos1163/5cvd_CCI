# Four Quadrant Offense Experiment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a dry-run-only, aggressive but controlled four-quadrant offense experiment that increases labeled paper/SCOUT/A-B samples without changing exchange mutation behavior.

**Architecture:** Keep production/live order submission untouched. Add reusable quadrant classification and dry-run experiment gating in `scripts/run_live_dry_run.py`, with config fields in `EntryChainConfig`. Main paper green-channel behavior is gated behind explicit config flags; mirror A/B samples are tagged separately so they do not masquerade as normal main ledger entries.

**Tech Stack:** Python dataclasses, JSON config, existing `PaperTradingLedger`, pytest.

## Global Constraints

- Dry-run only: do not edit `src/api/binance_client.py`, `src/execution/binance_adapter.py`, or live exchange mutation code.
- No lookahead: Q3-to-Q1 confirmation may only use the current decision and persisted earlier pending state; no future candle data in the same cycle.
- No same-bar optimistic fills beyond existing paper ledger assumptions; mirror samples use current closed kline price and normal paper stop/TP logic.
- Existing main paper ledger metrics must remain distinguishable from mirror A/B samples through explicit reasons/metadata.
- Default behavior must remain conservative unless enabled through config fields.
- Strategy hypothesis: four-quadrant routing can increase dry-run sample count in Q1/Q3 transition regimes while preserving hard risk controls.
- Expected regime: intraday crypto trend attempts where Q1 is sparse and many high-score signals are rejected by RR gap, watch-only, or LONG offset rules.
- Failure mode: more samples expose negative expectancy; SCOUT/mirror budget and mission tags must make this measurable instead of hidden.
- Verification command: `pytest tests/test_entry_chain_config.py tests/test_live_dry_run.py tests/test_paper_trading.py -q`.

---

## File Structure

- Modify `src/signals/entry_chain_config.py`: add config fields for quadrant thresholds, Q1 RR gap SCOUT, Q3 pending confirmation, mirror A/B samples, and optional dry-run main green channel.
- Modify `configs/entry_chain.dry_run_fib_pa_v1.json`: enable dry-run experiment defaults for the VPS dry-run config.
- Modify `scripts/run_live_dry_run.py`: add quadrant helpers, Q3 pending state, SCOUT mission routing, mirror A/B sample injection, summary assumptions.
- Modify `tests/test_entry_chain_config.py`: assert new config fields load and reject unknown keys as before.
- Modify `tests/test_live_dry_run.py`: cover quadrant classification, Q1 RR gap SCOUT mission, Q3 pending confirmation, mirror A/B sample open, and dry-run assumptions.

---

### Task 1: Config Surface

**Files:**
- Modify: `src/signals/entry_chain_config.py`
- Modify: `configs/entry_chain.dry_run_fib_pa_v1.json`
- Test: `tests/test_entry_chain_config.py`

**Interfaces:**
- Produces:
  - `EntryChainConfig.quadrant_trend_ema_min: float`
  - `EntryChainConfig.quadrant_price_action_min: float`
  - `EntryChainConfig.quadrant_flow_cvd_min: float`
  - `EntryChainConfig.quadrant_cci_min: float`
  - `EntryChainConfig.scout_micro_q1_rr_gap_enabled: bool`
  - `EntryChainConfig.scout_micro_q1_rr_gap_min_score: float`
  - `EntryChainConfig.scout_micro_q3_to_q1_enabled: bool`
  - `EntryChainConfig.scout_micro_q3_to_q1_min_score: float`
  - `EntryChainConfig.scout_micro_q3_to_q1_min_cvd_score: float`
  - `EntryChainConfig.scout_micro_q3_to_q1_confirm_bars: int`
  - `EntryChainConfig.scout_micro_q3_to_q1_confirm_pa_score: float`
  - `EntryChainConfig.mirror_ab_enabled: bool`
  - `EntryChainConfig.mirror_ab_min_score: float`
  - `EntryChainConfig.mirror_ab_notional: float`
  - `EntryChainConfig.mirror_ab_allowed_reasons: tuple[str, ...]`
  - `EntryChainConfig.dry_run_q1_green_channel_enabled: bool`
  - `EntryChainConfig.dry_run_q1_green_channel_notional_mult: float`

- [ ] **Step 1: Write failing config test**

Add a test asserting the new fields load from JSON and symbol/reason tuples normalize where applicable.

Run: `pytest tests/test_entry_chain_config.py -q`

Expected before implementation: FAIL with unknown config keys or missing attributes.

- [ ] **Step 2: Add dataclass fields**

Add the fields listed above to `EntryChainConfig` with defaults:

```python
quadrant_trend_ema_min: float = 15.0
quadrant_price_action_min: float = 10.0
quadrant_flow_cvd_min: float = 14.0
quadrant_cci_min: float = 7.0
scout_micro_q1_rr_gap_enabled: bool = False
scout_micro_q1_rr_gap_min_score: float = 82.0
scout_micro_q3_to_q1_enabled: bool = False
scout_micro_q3_to_q1_min_score: float = 85.0
scout_micro_q3_to_q1_min_cvd_score: float = 16.0
scout_micro_q3_to_q1_confirm_bars: int = 3
scout_micro_q3_to_q1_confirm_pa_score: float = 15.0
mirror_ab_enabled: bool = False
mirror_ab_min_score: float = 85.0
mirror_ab_notional: float = 50.0
mirror_ab_allowed_reasons: tuple[str, ...] = ()
dry_run_q1_green_channel_enabled: bool = False
dry_run_q1_green_channel_notional_mult: float = 0.5
```

Normalize `mirror_ab_allowed_reasons` as an uppercase string tuple without symbol formatting.

- [ ] **Step 3: Enable dry-run config**

In `configs/entry_chain.dry_run_fib_pa_v1.json`, set:

```json
"scout_micro_q1_rr_gap_enabled": true,
"scout_micro_q1_rr_gap_min_score": 82.0,
"scout_micro_q3_to_q1_enabled": true,
"scout_micro_q3_to_q1_min_score": 85.0,
"scout_micro_q3_to_q1_min_cvd_score": 16.0,
"scout_micro_q3_to_q1_confirm_bars": 3,
"scout_micro_q3_to_q1_confirm_pa_score": 15.0,
"mirror_ab_enabled": true,
"mirror_ab_min_score": 85.0,
"mirror_ab_notional": 50.0,
"mirror_ab_allowed_reasons": [
  "BELOW_RISK_REWARD_GEOMETRY",
  "SYMBOL_WATCH_ONLY",
  "SIDE_THRESHOLD_OFFSET_LONG",
  "FIB_EXTENSION_EXHAUSTION_BLOCK"
],
"dry_run_q1_green_channel_enabled": false,
"dry_run_q1_green_channel_notional_mult": 0.5
```

- [ ] **Step 4: Verify config tests**

Run: `pytest tests/test_entry_chain_config.py -q`

Expected: PASS.

---

### Task 2: Quadrant Helpers and SCOUT Missions

**Files:**
- Modify: `scripts/run_live_dry_run.py`
- Test: `tests/test_live_dry_run.py`

**Interfaces:**
- Produces:
  - `class QuadrantState(str, Enum)` is not required; use string constants `Q1`, `Q2`, `Q3`, `Q4`.
  - `decision_quadrant(payload_or_near_miss, config) -> str`
  - `annotate_quadrant(payload, config) -> dict[str, Any]`
  - `scout_micro_mission(...)` returns new missions `Q1_RR_GAP_SCOUT` and `Q3_TO_Q1_CONFIRMATION`.

- [ ] **Step 1: Write failing tests**

Add tests:

```python
def test_decision_quadrant_classifies_q1_and_q3():
    config = EntryChainConfig()
    assert decision_quadrant({"component_points": {
        "trend_ema_context": 15.0,
        "price_action_structure": 10.0,
        "flow_cvd_confirmation": 14.0,
        "cci_momentum_quality": 7.0,
    }}, config) == "Q1"
    assert decision_quadrant({"component_points": {
        "trend_ema_context": 14.0,
        "price_action_structure": 9.0,
        "flow_cvd_confirmation": 16.0,
        "cci_momentum_quality": 10.0,
    }}, config) == "Q3"
```

Add tests that `scout_micro_mission` returns:

- `Q1_RR_GAP_SCOUT` for Q1, score >=82, RR gap reason.
- `Q3_TO_Q1_CONFIRMATION` for a near-miss tagged as confirmed from pending Q3.

Run: `pytest tests/test_live_dry_run.py::test_decision_quadrant_classifies_q1_and_q3 -q`

Expected before implementation: import error or function missing.

- [ ] **Step 2: Implement quadrant helpers**

Implement helpers near `_component_point`:

```python
def decision_quadrant(payload: Mapping[str, Any], config: EntryChainConfig) -> str:
    trend_ok = (
        _component_point(payload, "trend_ema_context") >= float(config.quadrant_trend_ema_min)
        and _component_point(payload, "price_action_structure") >= float(config.quadrant_price_action_min)
    )
    flow_ok = (
        _component_point(payload, "flow_cvd_confirmation") >= float(config.quadrant_flow_cvd_min)
        and _component_point(payload, "cci_momentum_quality") >= float(config.quadrant_cci_min)
    )
    if trend_ok and flow_ok:
        return "Q1"
    if trend_ok:
        return "Q2"
    if flow_ok:
        return "Q3"
    return "Q4"
```

`annotate_quadrant` should return a copy with `quadrant`, `trend_structure_axis_ok`, and `flow_momentum_axis_ok`.

- [ ] **Step 3: Add Q1 RR gap eligibility**

In `scout_micro_mission`, check `_q1_rr_gap_scout_eligible` before legacy mission checks.

Eligibility:

- `config.scout_micro_q1_rr_gap_enabled` is true.
- `decision_quadrant(near_miss, config) == "Q1"`.
- `score >= config.scout_micro_q1_rr_gap_min_score`.
- `_has_rr_gap_reason(near_miss)` is true.
- side is LONG or SHORT.

- [ ] **Step 4: Add Q3 confirmed mission marker**

Return `Q3_TO_Q1_CONFIRMATION` when near-miss contains scout tag `Q3_TO_Q1_CONFIRMED` and `config.scout_micro_q3_to_q1_enabled` is true.

- [ ] **Step 5: Verify focused tests**

Run: `pytest tests/test_live_dry_run.py -q`

Expected: PASS.

---

### Task 3: Q3-to-Q1 Pending State

**Files:**
- Modify: `scripts/run_live_dry_run.py`
- Test: `tests/test_live_dry_run.py`

**Interfaces:**
- Produces:
  - `build_q3_pending_candidate(near_miss, config, timestamp) -> dict[str, Any] | None`
  - `confirm_q3_to_q1_pending(symbol, near_miss, config, pending, timestamp) -> dict[str, Any] | None`

- [ ] **Step 1: Write failing tests**

Add tests for:

- Q3 score >=85 and CVD >=16 creates a pending candidate with expiry timestamp `timestamp + confirm_bars * 900`.
- Later Q1 near-miss with PA >=15 confirms and adds `Q3_TO_Q1_CONFIRMED` tag.
- Expired pending state returns `None`.

- [ ] **Step 2: Implement helpers**

Use only current and previously stored data. Pending state should live in the `run()` loop as an in-memory dict:

```python
q3_pending_by_symbol: dict[str, dict[str, Any]] = {}
```

Persisting across process restarts is out of scope for this task.

- [ ] **Step 3: Wire loop**

After `near_miss` is built and annotated:

1. If current near-miss confirms existing pending state, replace `near_miss` with confirmed copy before audit/scout processing.
2. Else if current near-miss qualifies as Q3 pending, store it.
3. Expired pending entries are removed when observed.

- [ ] **Step 4: Verify**

Run: `pytest tests/test_live_dry_run.py -q`

Expected: PASS.

---

### Task 4: Mirror A/B Samples

**Files:**
- Modify: `scripts/run_live_dry_run.py`
- Test: `tests/test_live_dry_run.py`

**Interfaces:**
- Produces:
  - `should_open_mirror_ab_sample(near_miss, config, ab_ledgers) -> bool`
  - `build_mirror_ab_payloads(symbol, near_miss, price, config, timestamp) -> tuple[dict[str, Any], dict[str, Any]]`
  - `update_mirror_ab_ledgers(ab_ledgers, symbol, near_miss, config, kline, timestamp) -> list[str]`

- [ ] **Step 1: Write failing tests**

Add tests asserting:

- A Q1/RR-gap near-miss opens one position in each A/B ledger with reason `MIRROR_AB_SAMPLE`.
- Main paper ledger remains empty when only mirror A/B is opened.
- Mirror sample does not open if symbol is already present in any A/B ledger.

- [ ] **Step 2: Implement eligibility**

Eligibility:

- `config.mirror_ab_enabled` true.
- `near_miss` is not None.
- `score >= config.mirror_ab_min_score`.
- `intended_side` is LONG or SHORT.
- `entry_price > 0`.
- Any near-miss reason contains one of `config.mirror_ab_allowed_reasons`.
- No A/B ledger currently has that symbol open.

- [ ] **Step 3: Implement payload builder**

Use `config.mirror_ab_notional` and leverage 1. Reasons must include:

```python
["MIRROR_AB_SAMPLE", f"MIRROR_AB_SOURCE_{primary_reason}", *reason_list]
```

Set `decision_payload["mirror_ab_sample"] = True` and `decision_payload["scout_mission"] = "MIRROR_AB_SAMPLE"`.

- [ ] **Step 4: Wire loop**

After normal main paper and normal A/B ledgers have processed the real decision, call `update_mirror_ab_ledgers(...)`. Do not call it for main `paper` or `scout_paper`.

- [ ] **Step 5: Verify**

Run: `pytest tests/test_live_dry_run.py -q`

Expected: PASS.

---

### Task 5: Observability and Runtime Summary

**Files:**
- Modify: `scripts/run_live_dry_run.py`
- Test: `tests/test_live_dry_run.py`

**Interfaces:**
- Extends `dry_run_assumptions(config)` with the new experiment config fields.
- Adds `quadrant` to decision and near-miss payloads.
- Adds runtime log lines for mirror A/B events.

- [ ] **Step 1: Write failing tests**

Add assertions to existing dry-run once test:

- `summary["dry_run_assumptions"]["mirror_ab_enabled"]` exists.
- decision rows include `quadrant`.
- near-miss rows include `quadrant` when written.

- [ ] **Step 2: Implement observability**

Annotate decision payload before audit:

```python
decision_payload = annotate_quadrant(decision_payload, config)
```

Annotate near-miss payload before audit and summary.

Add assumptions:

```python
"quadrant_thresholds": {...},
"scout_micro_q1_rr_gap_enabled": config.scout_micro_q1_rr_gap_enabled,
"scout_micro_q3_to_q1_enabled": config.scout_micro_q3_to_q1_enabled,
"mirror_ab_enabled": config.mirror_ab_enabled,
"mirror_ab_min_score": config.mirror_ab_min_score,
"mirror_ab_notional": config.mirror_ab_notional,
"dry_run_q1_green_channel_enabled": config.dry_run_q1_green_channel_enabled,
```

- [ ] **Step 3: Verify**

Run: `pytest tests/test_entry_chain_config.py tests/test_live_dry_run.py tests/test_paper_trading.py -q`

Expected: PASS.

---

## Deliberate Deferral

The requested main-account rule “Q1 + PA>=20 completely exempts RR” is intentionally deferred. It directly weakens the known RR defense and would change main paper ledger behavior before SCOUT/mirror data exists. This plan instead enables Q1 RR gap samples through SCOUT and mirror A/B first. If the user explicitly requires main ledger green-channel behavior after reviewing this deferral, implement it as a dry-run-only post-evaluation conversion in `scripts/run_live_dry_run.py`, not in `src/signals/entry_chain.py`.

## Self-Review

- Spec coverage: Q1 RR gap SCOUT, Q3-to-Q1 confirmation, watch-only promotion, LONG offset mission, mirror A/B samples, and experiment observability are covered. Main account RR exemption is documented as a risk-based deferral.
- Placeholder scan: no TBD/TODO placeholders.
- Type consistency: config field names are introduced once and reused in later tasks.
