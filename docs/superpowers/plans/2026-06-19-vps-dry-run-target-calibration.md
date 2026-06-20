# VPS Dry Run Target Calibration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add target calibration, tiered dry-run configs, stress-risk checks, summary monitoring, and review workflow so VPS dry-run can safely evolve from conservative observation toward balanced/aggressive research.

**Architecture:** Keep the existing dry-run runner safe with `orders_submitted = 0`, then add configuration tiers and observability around it. Risk calibration lives outside exchange execution: every dry-run cycle writes decision logs, order drafts, gate rejections, health, summary, and stress-risk estimates.

**Tech Stack:** Python stdlib, dataclasses, JSON/JSONL/CSV files, pytest, existing entry-chain and dry-run modules.

---

## Scope

Implement now:

- Conservative / balanced / aggressive dry-run config files.
- Target profile documentation embedded in configs and summary output.
- Tail-risk stress simulator for per-decision theoretical loss.
- `summary.json` refreshed every dry-run cycle.
- Extra audit fields: `model_version`, `market_snapshot`, `latency_ms`.
- Error logging to `logs/errors.log`.
- Strategy review template.
- Runbook update for staged config promotion.

Defer:

- Real position tracking from exchange account.
- True PnL and 1R exit lifecycle.
- Telegram/email notification.
- Live order submission.
- 12-month OOS automation and parameter grid scan.

## Files

- Create: `configs/entry_chain.dry_run_conservative.json`
- Create: `configs/entry_chain.dry_run_balanced.json`
- Create: `configs/entry_chain.dry_run_aggressive.json`
- Modify: `configs/entry_chain.dry_run.json`
- Create: `src/risk/stress_simulator.py`
- Create: `src/observability/dry_run_summary.py`
- Modify: `src/observability/decision_audit.py`
- Modify: `scripts/run_live_dry_run.py`
- Modify: `scripts/vps_dry_run_healthcheck.py`
- Modify: `docs/runbooks/vps_dry_run.md`
- Create: `docs/review_template.md`
- Tests:
  - `tests/test_dry_run_configs.py`
  - `tests/test_stress_simulator.py`
  - `tests/test_dry_run_summary.py`
  - update `tests/test_decision_audit.py`
  - update `tests/test_live_dry_run.py`

## Acceptance Criteria

- `pytest tests/test_dry_run_configs.py tests/test_stress_simulator.py tests/test_dry_run_summary.py tests/test_decision_audit.py tests/test_live_dry_run.py -q` passes.
- `python scripts/run_live_dry_run.py --config configs/entry_chain.dry_run_conservative.json --once --output-dir reports/dry_run/local_calibration --symbols BNBUSDT,SOLUSDT` writes:
  - `decisions.jsonl`
  - `order_drafts.jsonl`
  - `gate_rejections.csv`
  - `health.json`
  - `summary.json`
  - `logs/errors.log` only if an error occurs.
- `summary.json` contains target tier, decision counts, recent decisions, stress risk, data health, and `orders_submitted = 0`.
- `python scripts/vps_dry_run_healthcheck.py --config configs/entry_chain.dry_run_conservative.json` returns `dry_run_safe = true`.
- `git diff -- src/api/binance_client.py` is empty.

## Task 1: Tiered Dry-Run Configs

**Files:**
- Create: `tests/test_dry_run_configs.py`
- Create: `configs/entry_chain.dry_run_conservative.json`
- Create: `configs/entry_chain.dry_run_balanced.json`
- Create: `configs/entry_chain.dry_run_aggressive.json`
- Modify: `configs/entry_chain.dry_run.json`

- [ ] **Step 1: Write tests**

```python
from pathlib import Path
from src.signals.entry_chain_config import load_entry_chain_config


def test_dry_run_config_tiers_are_parseable_and_ordered():
    conservative = load_entry_chain_config("configs/entry_chain.dry_run_conservative.json")
    balanced = load_entry_chain_config("configs/entry_chain.dry_run_balanced.json")
    aggressive = load_entry_chain_config("configs/entry_chain.dry_run_aggressive.json")

    assert conservative.direct_threshold > balanced.direct_threshold > aggressive.direct_threshold
    assert conservative.daily_max_trades_base < balanced.daily_max_trades_base < aggressive.daily_max_trades_base
    assert conservative.max_total_exposure_pct <= balanced.max_total_exposure_pct <= aggressive.max_total_exposure_pct


def test_default_dry_run_config_matches_conservative_tier():
    default = Path("configs/entry_chain.dry_run.json").read_text(encoding="utf-8")
    conservative = Path("configs/entry_chain.dry_run_conservative.json").read_text(encoding="utf-8")

    assert default == conservative
```

- [ ] **Step 2: Add config files**

Use conservative as current default. Balanced and aggressive increase frequency but still remain dry-run only.

- [ ] **Step 3: Verify**

Run: `pytest tests/test_dry_run_configs.py -q`

Expected: PASS.

## Task 2: Stress Simulator

**Files:**
- Create: `src/risk/stress_simulator.py`
- Create: `tests/test_stress_simulator.py`

- [ ] **Step 1: Write tests**

```python
from src.risk.stress_simulator import estimate_stress_loss_pct, stress_decision


def test_estimate_stress_loss_pct_scales_with_exposure_and_leverage():
    loss = estimate_stress_loss_pct(exposure_pct=0.30, leverage=5, adverse_move_pct=0.10)

    assert round(loss, 4) == 0.15


def test_stress_decision_blocks_when_loss_exceeds_threshold():
    decision = stress_decision(exposure_pct=0.30, leverage=5, adverse_move_pct=0.20, max_loss_pct=0.25)

    assert decision["action"] == "BLOCK"
    assert decision["estimated_loss_pct"] == 0.30
```

- [ ] **Step 2: Implement**

Functions:

- `estimate_stress_loss_pct(exposure_pct, leverage, adverse_move_pct) -> float`
- `stress_decision(..., max_loss_pct=0.25) -> dict`

- [ ] **Step 3: Verify**

Run: `pytest tests/test_stress_simulator.py -q`

Expected: PASS.

## Task 3: Summary JSON

**Files:**
- Create: `src/observability/dry_run_summary.py`
- Create: `tests/test_dry_run_summary.py`

- [ ] **Step 1: Write tests**

```python
import json
from src.observability.dry_run_summary import DryRunSummary, write_summary


def test_write_summary_contains_targets_and_decision_counts(tmp_path):
    summary = DryRunSummary(target_tier="conservative")
    summary.record_decision({"action": "NO_TRADE", "symbol": "BNBUSDT", "score": 50, "reasons": ["LOW_SCORE"]})
    summary.record_decision({"action": "PROBE", "symbol": "SOLUSDT", "score": 75, "reasons": []})

    write_summary(tmp_path / "summary.json", summary, orders_submitted=0, data_health="OK")

    payload = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert payload["target_tier"] == "conservative"
    assert payload["decision_counts"]["NO_TRADE"] == 1
    assert payload["decision_counts"]["PROBE"] == 1
    assert payload["orders_submitted"] == 0
```

- [ ] **Step 2: Implement**

Track:

- target tier
- decision counts
- active symbols
- cooldown symbols placeholder
- recent 5 decisions
- stress risk snapshots
- data health
- orders submitted

- [ ] **Step 3: Verify**

Run: `pytest tests/test_dry_run_summary.py -q`

Expected: PASS.

## Task 4: Audit Field Expansion

**Files:**
- Modify: `src/observability/decision_audit.py`
- Modify: `tests/test_decision_audit.py`

- [ ] **Step 1: Extend test**

Assert decisions may include:

- `model_version`
- `market_snapshot`
- `latency_ms`

and are preserved in `decisions.jsonl`.

- [ ] **Step 2: Implement if needed**

Current JSONL writer preserves arbitrary fields; only test is needed unless gate CSV needs model version.

- [ ] **Step 3: Verify**

Run: `pytest tests/test_decision_audit.py -q`

Expected: PASS.

## Task 5: Dry-Run Runner Integration

**Files:**
- Modify: `scripts/run_live_dry_run.py`
- Modify: `tests/test_live_dry_run.py`

- [ ] **Step 1: Extend dry-run test**

Check:

- `summary.json` exists
- `summary.json["orders_submitted"] == 0`
- `summary.json["data_health"] == "OK"`
- source still has no `submit_order(` / `cancel_order(`

- [ ] **Step 2: Implement integration**

Add:

- `--target-tier conservative|balanced|aggressive`
- latency measurement around decision evaluation
- synthetic `market_snapshot`
- stress decision per draft
- summary writer update
- top-level try/except that writes `logs/errors.log` then re-raises

- [ ] **Step 3: Verify**

Run: `pytest tests/test_live_dry_run.py -q`

Expected: PASS.

## Task 6: Healthcheck And Docs

**Files:**
- Modify: `scripts/vps_dry_run_healthcheck.py`
- Modify: `docs/runbooks/vps_dry_run.md`
- Create: `docs/review_template.md`
- Modify: `tests/test_live_dry_run.py`

- [ ] **Step 1: Healthcheck supports tiered config**

Run healthcheck against conservative, balanced, aggressive.

- [ ] **Step 2: Runbook**

Document:

- conservative first
- promote to balanced only after 30 days meeting conservative target
- aggressive only after manual review and 60 more days
- minimum real-trade transition standard

- [ ] **Step 3: Review template**

Create a 30-day review template with KPI, top gate rejects, abnormal cases, parameter changes, and next risk budget.

- [ ] **Step 4: Verify**

Run:

```powershell
pytest tests/test_live_dry_run.py -q
python scripts/vps_dry_run_healthcheck.py --config configs/entry_chain.dry_run_conservative.json
python scripts/vps_dry_run_healthcheck.py --config configs/entry_chain.dry_run_balanced.json
python scripts/vps_dry_run_healthcheck.py --config configs/entry_chain.dry_run_aggressive.json
```

Expected: PASS.

## Self-Review

- Spec coverage: This plan covers target realism, staged configs, stress risk, summary monitoring, data health, error logging, transition standards, and review workflow.
- Placeholder scan: All tasks include file paths, test intent, and concrete commands.
- Risk review: No real orders, no Binance client edits, no credential storage, and `orders_submitted = 0` remains required.
