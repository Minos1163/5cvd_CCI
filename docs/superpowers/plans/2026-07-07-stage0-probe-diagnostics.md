# Stage 0 Probe Diagnostics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add dry-run observability needed to diagnose `PROBE=0` before changing strategy thresholds, leverage, or position sizing.

**Architecture:** Keep trading behavior unchanged. Extend `summary.json` with diagnostic counters derived from existing decision reasons, plus explicit risk/cost assumptions and latest portfolio exposure snapshots. The runtime already writes `summary.json` every cycle, so this is the lowest-risk place to add Stage 0 data.

**Tech Stack:** Python, dataclasses, JSON, pytest.

## Global Constraints

- This is DRY-RUN strategy research; do not modify live execution or production config paths.
- Do not loosen PROBE/DIRECT thresholds, leverage, position sizing, or symbol pools in this task.
- Do not add a portfolio exposure hard gate yet; only report current exposure/cap diagnostics.
- Avoid lookahead bias, future candle data, repaint signals, and same-bar fill assumptions.
- Strategy hypothesis: `PROBE=0` must be diagnosed by independent PROBE rejection statistics before any parameter relaxation.
- Expected market regime: mixed crypto regime where high score supply may exist but is blocked by RR/Fib/side/symbol policy gates.
- Failure mode: diagnostics may reveal low true eligible supply; that is useful information, not a reason to loosen gates in this change.
- Verification command: `pytest tests/test_dry_run_summary.py tests/test_live_dry_run.py -q`.
- Keep changes surgical: no new dependencies, no broad refactors.

---

## File Structure

- Modify `src/observability/dry_run_summary.py`: add layer-level rejection counters, assumptions payload, and latest portfolio exposure diagnostics.
- Modify `scripts/run_live_dry_run.py`: pass dry-run assumptions and portfolio snapshots into `DryRunSummary`.
- Modify `tests/test_dry_run_summary.py`: cover new summary fields.
- Modify `tests/test_live_dry_run.py`: cover that generated `summary.json` includes Stage 0 diagnostics.

---

### Task 1: Summary Rejection Layer Counters

**Files:**
- Modify: `src/observability/dry_run_summary.py`
- Modify: `tests/test_dry_run_summary.py`

**Interfaces:**
- `DryRunSummary.record_decision(decision: Mapping[str, object]) -> None` continues to accept the existing decision payload.
- `DryRunSummary.to_dict(...)` gains:
  - `gate_rejections_by_layer: dict[str, int]`
  - `gate_rejections_by_layer_reason: dict[str, dict[str, int]]`

- [x] **Step 1: Write failing test**

Add a test that records decisions with reasons:

```python
def test_summary_splits_rejection_reasons_by_layer():
    summary = DryRunSummary(target_tier="aggressive")
    summary.record_decision({"action": "WATCH", "symbol": "LINKUSDT", "score": 87.3, "reasons": ["FIB_PA_ARCHITECTURE_WEIGHTS", "DIRECT_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_2.0", "PROBE_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_2.0"]})
    summary.record_decision({"action": "NO_TRADE", "symbol": "TRXUSDT", "score": 77.7, "reasons": ["FIB_PA_ARCHITECTURE_WEIGHTS", "DAILY_TRADE_BUDGET_USED"]})
    payload = summary.to_dict(orders_submitted=0, data_health="OK")
    assert payload["gate_rejections_by_layer"]["direct"] == 1
    assert payload["gate_rejections_by_layer"]["probe"] == 1
    assert payload["gate_rejections_by_layer"]["budget"] == 1
    assert payload["gate_rejections_by_layer_reason"]["probe"] == {"PROBE_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_2.0": 1}
```

- [x] **Step 2: Run failing test**

Run: `pytest tests/test_dry_run_summary.py -q`  
Expected: FAIL because new keys do not exist.

- [x] **Step 3: Implement minimal classification**

Classify reasons as:

```text
direct: reason starts with DIRECT_
probe: reason starts with PROBE_ or HIGH_BETA_PROBE_
budget: reason in DAILY_TRADE_BUDGET_USED / SYMBOL_DAILY_TRADE_BUDGET_USED
symbol_policy: reason starts SYMBOL_ or reason in SYMBOL_BLACKLISTED / SYMBOL_WATCH_ONLY
side_policy: reason starts SIDE_THRESHOLD_OFFSET_
fib_policy: reason starts FIB_
portfolio: reason contains EXPOSURE or MARGIN or CIRCUIT
other: everything else except FIB_PA_ARCHITECTURE_WEIGHTS
```

- [x] **Step 4: Verify**

Run: `pytest tests/test_dry_run_summary.py -q`  
Expected: PASS.

---

### Task 2: Risk, Cost, And Exposure Diagnostics

**Files:**
- Modify: `src/observability/dry_run_summary.py`
- Modify: `scripts/run_live_dry_run.py`
- Modify: `tests/test_dry_run_summary.py`

**Interfaces:**
- `DryRunSummary` accepts optional `assumptions: Mapping[str, object]`.
- `DryRunSummary.record_portfolio_snapshot(row: Mapping[str, object]) -> None`.
- `summary.json` gains:
  - `dry_run_assumptions`
  - `latest_portfolio_exposure`

- [x] **Step 1: Add failing tests**

Add:

```python
def test_summary_includes_assumptions_and_latest_portfolio_exposure():
    summary = DryRunSummary(target_tier="aggressive", assumptions={"fee_bps": 5.0, "slippage_bps": 5.0})
    summary.record_portfolio_snapshot({"total_exposure_pct": 0.6, "net_side_exposure_pct": -0.2, "open_position_count": 2})
    payload = summary.to_dict(orders_submitted=0, data_health="OK")
    assert payload["dry_run_assumptions"] == {"fee_bps": 5.0, "slippage_bps": 5.0}
    assert payload["latest_portfolio_exposure"] == {"total_exposure_pct": 0.6, "net_side_exposure_pct": -0.2, "open_position_count": 2}
```

- [x] **Step 2: Implement summary fields**

Add dataclass fields:

```python
assumptions: Mapping[str, object] = field(default_factory=dict)
latest_portfolio_exposure: dict[str, object] = field(default_factory=dict)
```

Add `record_portfolio_snapshot`.

- [x] **Step 3: Wire runtime assumptions**

In `scripts/run_live_dry_run.py`, initialize:

```python
summary = DryRunSummary(target_tier=args.target_tier, assumptions=dry_run_assumptions(config))
```

Add `dry_run_assumptions(config)` returning current config risk caps and paper constants:

```python
{
  "direct_risk_pct": config.direct_risk_pct,
  "probe_risk_pct": config.probe_risk_pct,
  "max_active_symbols": config.max_active_symbols,
  "max_total_exposure_pct": config.max_total_exposure_pct,
  "max_same_direction_exposure_pct": config.max_same_direction_exposure_pct,
  "max_symbol_trades_per_day": config.max_symbol_trades_per_day,
  "daily_max_trades_base": config.daily_max_trades_base,
  "min_daily_trades": config.min_daily_trades,
  "paper_fee_bps": FEE_BPS,
  "paper_slippage_bps": SLIPPAGE_BPS,
  "paper_tp_levels": list(TP_LEVELS),
  "paper_tp_fractions": list(TP_FRACTIONS),
}
```

At the start of each cycle, after applying paper state or before writing summary, record latest exposure from `paper.get_portfolio_state_snapshot(now)`:

```python
summary.record_portfolio_snapshot(portfolio_exposure_snapshot(paper.get_portfolio_state_snapshot(now), config))
```

- [x] **Step 4: Verify**

Run: `pytest tests/test_dry_run_summary.py -q`  
Expected: PASS.

---

### Task 3: Runtime Summary Smoke

**Files:**
- Modify: `tests/test_live_dry_run.py`

**Interfaces:**
- Existing `summary.json` written by one-shot dry-run contains new keys.

- [x] **Step 1: Add assertions to existing one-shot summary test**

In a test that already runs `scripts/run_live_dry_run.py --once`, assert:

```python
assert "gate_rejections_by_layer" in summary
assert "probe" in summary["gate_rejections_by_layer"]
assert "dry_run_assumptions" in summary
assert summary["dry_run_assumptions"]["paper_fee_bps"] == 5.0
assert "latest_portfolio_exposure" in summary
```

- [x] **Step 2: Run focused suite**

Run:

```powershell
pytest tests/test_dry_run_summary.py tests/test_live_dry_run.py -q
```

Expected: PASS.

---

### Task 4: Final Verification

**Files:**
- No additional changes expected.

- [x] **Step 1: Run verification**

Run:

```powershell
pytest tests/test_dry_run_summary.py tests/test_live_dry_run.py -q
```

Expected: PASS.

- [x] **Step 2: Behavior check**

Run a one-shot dry-run and inspect `summary.json`:

```powershell
python scripts/run_live_dry_run.py --config configs/entry_chain.dry_run_fib_pa_v1.json --target-tier aggressive --market-data-source synthetic --once --output-dir tmp_stage0_probe_diag
```

Expected:

```text
summary.json includes gate_rejections_by_layer, gate_rejections_by_layer_reason, dry_run_assumptions, latest_portfolio_exposure
```
