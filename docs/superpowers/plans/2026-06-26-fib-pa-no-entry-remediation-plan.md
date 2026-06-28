# Fib/PA No-Entry Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve Fib/PA dry-run observability and cautiously restore low-risk sampling after the 2026-06-26 13:15-23:00 CST zero-entry window.

**Architecture:** Keep the new CCI+CVD+EMA+Price Action+Fibonacci architecture intact. Add clearer rejection diagnostics first, then enable conditional PROBE sampling behind stricter component minimums, and only after observation evaluate RR geometry and Fib extension gate changes.

**Tech Stack:** Python strategy code, JSON config, pytest, local dry-run logs under `logs/`.

## Global Constraints

- Do not modify live execution, live risk, or production config paths unless explicitly asked.
- Do not introduce lookahead bias, future candle data, repaint signals, or same-bar fill assumptions.
- Entry and exit logic must remain live-executable with explicit fee, slippage, latency, and candle-close assumptions.
- Every strategy change must state hypothesis, expected market regime, failure mode, and verification command.
- Use single-variable rollout: do not simultaneously relax PROBE, LONG threshold, RR geometry, and Fib hard gate.
- Preserve ZEC blacklist through the existing temporary blacklist period; add observation/shadow diagnostics instead of directly allowing ZEC entries.
- Keep current branch `626-PA+Fib`; do not commit or push unless the user asks.

---

## Market Hypothesis

The zero-entry window is not a runtime failure. It is the expected consequence of the new position-first Fib/PA scoring stack:

```text
EMA and CVD are often supportive:
  trend_ema_context avg = 15.14 / 20
  flow_cvd_confirmation avg = 14.04 / 18

But entry quality components suppress trades:
  cci_momentum_quality avg = 4.26 / 14
  price_action_structure avg = 6.51 / 22
  risk_reward_geometry avg = 1.68 / 8
```

Expected market regime:

```text
Choppy or early reversal market where trend context exists,
but clean pullback/retest structure and net TP1 path are scarce.
```

Primary failure mode to avoid:

```text
Overreacting to zero entries by lowering all thresholds at once,
thereby recreating the old failure mode: high trend-agreement score at poor location.
```

Verification command baseline:

```powershell
pytest -q
python -m py_compile src\signals\entry_chain.py
```

If exact files differ in the repository, locate them first with:

```powershell
rg -n "COMPONENT_MINIMUM|PROBE_DISABLED|FIB_EXTENSION_EXHAUSTION|risk_reward_geometry|disable_probe" src configs tests
```

---

## File Structure

Expected files to inspect or modify:

- Modify: `src/signals/entry_chain.py`
  - Add explicit component-minimum rejection tags.
  - Ensure PROBE-specific component minimums are logged separately from DIRECT minimums.

- Modify: `src/signals/entry_chain_config.py`
  - Add or expose conditional PROBE config fields if they do not already exist.
  - Add optional Fib extension gate split fields only after Task 4.

- Modify: `configs/entry_chain.dry_run_fib_pa_v1.json`
  - Turn on conditional PROBE only after diagnostics are in place.
  - Do not change LONG DIRECT offset in this plan.

- Test: `tests/test_entry_chain_component_minimums.py`
  - Cover explicit rejection reason labels and gap formatting.

- Test: `tests/test_entry_chain_probe_conditions.py`
  - Cover conditional PROBE allowed/blocked behavior.

- Optional later modify: `src/signals/fib_location.py`
  - Split Fib extension hard block into hard block / soft demote / penalty.

- Optional later test: `tests/test_fib_location.py`
  - Cover hard and soft Fib extension zones.

---

## Task 1: Add Explicit Component-Minimum Diagnostics

**Files:**
- Modify: `src/signals/entry_chain.py`
- Test: `tests/test_entry_chain_component_minimums.py`

**Interfaces:**
- Consumes: existing component point dict from `score_detail.points` or equivalent local variable.
- Produces: rejection reason strings in this format:
  - `DIRECT_BELOW_PRICE_ACTION_STRUCTURE_MINIMUM_GAP_2.5`
  - `DIRECT_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_1.0`
  - `PROBE_BELOW_FIBONACCI_LOCATION_MINIMUM_GAP_3.0`

**Hypothesis:** Zero-entry diagnosis improves if the runtime tells us which component failed and by how much, rather than only logging a generic component-minimum failure.

**Failure Mode:** Overly long or unstable reason labels make aggregation difficult. Keep reason labels deterministic and one decimal place only.

- [ ] **Step 1: Locate current component minimum logic**

Run:

```powershell
rg -n "COMPONENT_MINIMUM|component_minimum|minimum|BELOW_.*MINIMUM|PROBE_COMPONENT" src tests
```

Expected: find the function or block that downgrades/rejects candidates based on component minimums.

- [ ] **Step 2: Write failing tests for reason labels**

Create or update `tests/test_entry_chain_component_minimums.py` with tests equivalent to:

```python
def test_component_minimum_reason_names_component_and_gap():
    scores = {
        "price_action_structure": 3.5,
        "fibonacci_location": 18.0,
        "risk_reward_geometry": 4.0,
    }

    ok, reason = check_component_minimums(
        scores,
        "DIRECT",
        {"price_action_structure": 6.0},
    )

    assert ok is False
    assert reason == "DIRECT_BELOW_PRICE_ACTION_STRUCTURE_MINIMUM_GAP_2.5"


def test_component_minimum_passes_when_all_components_meet_threshold():
    scores = {
        "price_action_structure": 6.0,
        "fibonacci_location": 13.0,
        "risk_reward_geometry": 4.0,
    }

    ok, reason = check_component_minimums(
        scores,
        "DIRECT",
        {
            "price_action_structure": 6.0,
            "fibonacci_location": 6.0,
            "risk_reward_geometry": 2.0,
        },
    )

    assert ok is True
    assert reason == ""
```

If the real helper signature differs, adapt the test to the local function, but preserve expected labels.

- [ ] **Step 3: Run the focused test and confirm failure**

Run:

```powershell
pytest tests\test_entry_chain_component_minimums.py -q
```

Expected: FAIL because explicit gap labels are not implemented yet.

- [ ] **Step 4: Implement deterministic reason helper**

In `src/signals/entry_chain.py`, implement or adapt:

```python
def _component_minimum_reason(action: str, component: str, min_score: float, actual_score: float) -> str:
    gap = max(0.0, min_score - actual_score)
    component_label = component.upper()
    return f"{action}_BELOW_{component_label}_MINIMUM_GAP_{gap:.1f}"


def check_component_minimums(
    component_points: dict[str, float],
    action: str,
    minimums: dict[str, float],
) -> tuple[bool, str]:
    for component, min_score in minimums.items():
        actual_score = float(component_points.get(component, 0.0))
        if actual_score < min_score:
            return False, _component_minimum_reason(action, component, min_score, actual_score)
    return True, ""
```

If an existing public function already exists, keep its name and add the helper internally.

- [ ] **Step 5: Verify focused tests**

Run:

```powershell
pytest tests\test_entry_chain_component_minimums.py -q
```

Expected: PASS.

- [ ] **Step 6: Verify no syntax break**

Run:

```powershell
python -m py_compile src\signals\entry_chain.py
```

Expected: no output and exit code 0.

---

## Task 2: Enable Conditional PROBE Diagnostics Without Lowering DIRECT

**Files:**
- Modify: `src/signals/entry_chain.py`
- Modify: `src/signals/entry_chain_config.py`
- Modify: `configs/entry_chain.dry_run_fib_pa_v1.json`
- Test: `tests/test_entry_chain_probe_conditions.py`

**Interfaces:**
- Consumes: total score, intended side, component points, and risk/reward details.
- Produces: PROBE only when all conditions pass:
  - total score >= 72
  - Fib points >= 12
  - PA points >= 6
  - net TP1 R >= 0.9 if available
  - max active PROBE positions <= 2 if active-position context exists

**Hypothesis:** Conditional PROBE restores low-risk sampling without lowering DIRECT quality gates.

**Failure Mode:** If PROBE is enabled without component guards, the old low-quality PROBE failure mode returns.

- [ ] **Step 1: Inspect current config schema and PROBE behavior**

Run:

```powershell
rg -n "disable_probe|probe|PROBE_DISABLED|direct_short|direct_long|threshold" src configs tests
```

Expected: identify where `disable_probe` is read and where PROBE is converted to `NO_TRADE`.

- [ ] **Step 2: Add failing tests for conditional PROBE**

Create or update `tests/test_entry_chain_probe_conditions.py`:

```python
def test_probe_allowed_when_score_and_components_pass():
    component_points = {
        "fibonacci_location": 13.0,
        "price_action_structure": 9.0,
        "risk_reward_geometry": 4.0,
    }
    rr_detail = {"net_tp1_r": 1.0}

    allowed, reason = check_probe_conditions(
        score=74.0,
        side="SHORT",
        component_points=component_points,
        rr_detail=rr_detail,
        config={
            "enabled": True,
            "min_score": 72.0,
            "min_fib_score": 12.0,
            "min_pa_score": 6.0,
            "min_rr_net_r": 0.9,
        },
    )

    assert allowed is True
    assert reason == ""


def test_probe_rejected_when_fib_is_too_low():
    component_points = {
        "fibonacci_location": 9.0,
        "price_action_structure": 21.0,
        "risk_reward_geometry": 5.0,
    }
    rr_detail = {"net_tp1_r": 1.1}

    allowed, reason = check_probe_conditions(
        score=82.0,
        side="LONG",
        component_points=component_points,
        rr_detail=rr_detail,
        config={
            "enabled": True,
            "min_score": 72.0,
            "min_fib_score": 12.0,
            "min_pa_score": 6.0,
            "min_rr_net_r": 0.9,
        },
    )

    assert allowed is False
    assert reason == "PROBE_BELOW_FIBONACCI_LOCATION_MINIMUM_GAP_3.0"
```

If the repository already has a probe helper, adapt the tests to its real signature.

- [ ] **Step 3: Run focused test and confirm failure**

Run:

```powershell
pytest tests\test_entry_chain_probe_conditions.py -q
```

Expected: FAIL because conditional PROBE helper or config fields are missing.

- [ ] **Step 4: Implement `check_probe_conditions`**

Add a helper near existing entry-chain gate helpers:

```python
def check_probe_conditions(
    score: float,
    side: str,
    component_points: dict[str, float],
    rr_detail: dict[str, float] | None,
    config: dict,
) -> tuple[bool, str]:
    if not config.get("enabled", False):
        return False, "PROBE_DISABLED"

    min_score = float(config.get("min_score", 72.0))
    if score < min_score:
        gap = min_score - score
        return False, f"PROBE_BELOW_SCORE_MINIMUM_GAP_{gap:.1f}"

    minimums = {
        "fibonacci_location": float(config.get("min_fib_score", 12.0)),
        "price_action_structure": float(config.get("min_pa_score", 6.0)),
    }
    ok, reason = check_component_minimums(component_points, "PROBE", minimums)
    if not ok:
        return False, reason

    rr_detail = rr_detail or {}
    min_rr_net_r = float(config.get("min_rr_net_r", 0.9))
    net_tp1_r = rr_detail.get("net_tp1_r")
    if net_tp1_r is not None and float(net_tp1_r) < min_rr_net_r:
        gap = min_rr_net_r - float(net_tp1_r)
        return False, f"PROBE_BELOW_RR_NET_R_MINIMUM_GAP_{gap:.1f}"

    return True, ""
```

If Python version or project style does not support `dict[str, float]`, use `Mapping[str, float]` or existing typing style.

- [ ] **Step 5: Wire config to dry-run only**

Update `configs/entry_chain.dry_run_fib_pa_v1.json`:

```json
{
  "disable_probe": false,
  "probe_conditions": {
    "enabled": true,
    "min_score": 72.0,
    "min_fib_score": 12.0,
    "min_pa_score": 6.0,
    "min_rr_net_r": 0.9,
    "long_threshold_offset": 7.0,
    "short_threshold_offset": 0.0,
    "max_active_probes": 2
  }
}
```

Preserve all existing unrelated config keys.

- [ ] **Step 6: Verify focused tests**

Run:

```powershell
pytest tests\test_entry_chain_probe_conditions.py tests\test_entry_chain_component_minimums.py -q
```

Expected: PASS.

- [ ] **Step 7: Verify broader signal tests**

Run:

```powershell
pytest tests -q
```

Expected: PASS. If unrelated legacy tests fail, record exact failing tests and do not hide them.

---

## Task 3: Add RR Geometry Diagnosis Before Changing TP

**Files:**
- Modify: `src/signals/entry_chain.py` or the existing RR scorer file.
- Test: existing RR test file, or create `tests/test_risk_reward_geometry_detail.py`.

**Interfaces:**
- Consumes: current RR scorer inputs.
- Produces: diagnostic fields in `score_detail` or equivalent metadata:
  - `net_tp1_r`
  - `stop_pct`
  - `tp1_pct`
  - `opposition_dist_r`
  - `rr_zero_reason`

**Hypothesis:** RR average 1.68/8 may be caused by either true lack of path or overly strict opposition/fee logic. Do not alter TP levels until reason distribution is visible.

**Failure Mode:** Changing TP1 to 1.2R immediately may reduce TP1 hit rate without proving RR was the real issue.

- [ ] **Step 1: Locate RR scorer**

Run:

```powershell
rg -n "risk_reward_geometry|net_tp1_r|opposition|nearby_opposition|tp1|stop_pct" src tests
```

Expected: identify scorer function returning RR score and details.

- [ ] **Step 2: Add tests for RR detail fields**

Add a test matching existing scorer signature. Required assertions:

```python
assert "net_tp1_r" in detail
assert "stop_pct" in detail
assert "tp1_pct" in detail
assert "rr_zero_reason" in detail
```

For a zero-score fixture, assert one of:

```python
assert detail["rr_zero_reason"] in {
    "NET_TP1_R_TOO_LOW",
    "OPPOSITION_STRUCTURE_TOO_CLOSE",
    "ATR_OUT_OF_RANGE",
    "UNKNOWN",
}
```

- [ ] **Step 3: Run focused RR tests and confirm failure**

Run:

```powershell
pytest tests\test_risk_reward_geometry_detail.py -q
```

Expected: FAIL if fields do not exist.

- [ ] **Step 4: Add detail fields without changing RR scoring**

Modify the RR scorer so scoring is unchanged, but detail output includes:

```python
detail = {
    **detail,
    "net_tp1_r": round(net_tp1_r, 3),
    "stop_pct": round(stop_dist / close, 4),
    "tp1_pct": round(tp1_dist / close, 4),
    "opposition_dist_r": round(opposition_dist / stop_dist, 3) if opposition_dist is not None else None,
    "rr_zero_reason": rr_zero_reason,
}
```

Set `rr_zero_reason` deterministically:

```python
rr_zero_reason = ""
if score <= 0.0:
    if net_tp1_r < min_net_tp1_r:
        rr_zero_reason = "NET_TP1_R_TOO_LOW"
    elif opposition_structure_too_close:
        rr_zero_reason = "OPPOSITION_STRUCTURE_TOO_CLOSE"
    elif atr_out_of_range:
        rr_zero_reason = "ATR_OUT_OF_RANGE"
    else:
        rr_zero_reason = "UNKNOWN"
```

- [ ] **Step 5: Verify tests**

Run:

```powershell
pytest tests\test_risk_reward_geometry_detail.py -q
pytest tests -q
```

Expected: PASS or report unrelated failures exactly.

---

## Task 4: Plan-Only Fib Extension Gate Split

**Files:**
- Do not modify code in this task unless Tasks 1-3 have passed and the user explicitly asks to continue.
- Future modify: `src/signals/fib_location.py`
- Future test: `tests/test_fib_location.py`

**Interfaces:**
- Produces future gate levels:
  - distance <= 0.3 ATR: `FIB_EXTENSION_EXHAUSTION_BLOCK`
  - 0.3 ATR < distance <= 0.7 ATR: `FIB_EXTENSION_EXHAUSTION_DEMOTE_WATCH`
  - 0.7 ATR < distance <= 1.5 ATR: Fib score penalty only

**Hypothesis:** Current 0.5 ATR hard-block tolerance may be too wide; splitting hard and soft zones preserves protection while improving diagnostics.

**Failure Mode:** Softening Fib too early may re-enable extension-zone chase entries before shadow data proves they are safe.

- [ ] **Step 1: Do not implement during the first rollout**

Expected: no code changes for Fib gate split in the same commit as PROBE restoration.

- [ ] **Step 2: Add observation query for current Fib blocks**

Run after 12-24 hours of new logs:

```powershell
rg "FIB_EXTENSION_EXHAUSTION_BLOCK" logs\2026-06 -n
```

Expected: enough cases to compare hard-block candidates against subsequent price movement.

- [ ] **Step 3: Implement only if Claude approves**

If approved, write tests first:

```python
def test_fib_extension_within_point_three_atr_blocks():
    assert tag == "FIB_EXTENSION_EXHAUSTION_BLOCK"


def test_fib_extension_between_point_three_and_point_seven_atr_demotes():
    assert tag == "FIB_EXTENSION_EXHAUSTION_DEMOTE_WATCH"
```

---

## Task 5: Post-Change Verification and Reporting

**Files:**
- Create: `docs/superpowers/reports/YYYY-MM-DD-fib-pa-probe-rollout-verification.md`

**Interfaces:**
- Consumes: new dry-run logs after deployment.
- Produces: review report for Claude containing:
  - PROBE candidates count
  - PROBE opened count
  - component-minimum reason distribution
  - RR zero reason distribution
  - Fib block count

- [ ] **Step 1: Run test suite**

Run:

```powershell
pytest tests -q
```

Expected: PASS or exact failure list.

- [ ] **Step 2: Run compile check**

Run:

```powershell
python -m py_compile src\signals\entry_chain.py
```

Expected: no output and exit code 0.

- [ ] **Step 3: Inspect config diff**

Run:

```powershell
git diff -- configs\entry_chain.dry_run_fib_pa_v1.json
```

Expected: only `disable_probe=false` and `probe_conditions` changes, no unrelated live config changes.

- [ ] **Step 4: Inspect code diff for scope**

Run:

```powershell
git diff -- src tests
```

Expected: only diagnostics and conditional PROBE logic; no TP/SL or live execution mutation.

- [ ] **Step 5: Write rollout report after VPS logs are available**

The report must include:

```text
Window start/end
Decisions count
PROBE candidates
PROBE openings
DIRECT openings
Reason distribution
RR zero reason distribution
Component minimum gap distribution
Paper PnL if any
```

---

## Prohibited Changes In This Plan

Do not implement these in the same rollout:

```text
Do not lower LONG DIRECT offset from +10 to +7.
Do not remove or bypass ZEC blacklist.
Do not change TP levels from [1.0, 2.0, 3.0] to [1.2, 2.2, 3.5] yet.
Do not relax RR minimums until RR zero reasons are logged.
Do not completely remove Fib extension hard block.
Do not alter live execution or exchange mutation behavior.
```

---

## Success Criteria

The first rollout is successful if, after 12-24 hours of dry-run:

```text
Script health remains OK.
No live exchange mutation is enabled.
Component-minimum rejection reasons identify the exact failed component.
PROBE_DISABLED no longer dominates candidate loss.
Any PROBE entries satisfy Fib >= 12, PA >= 6, and net_tp1_r >= 0.9 when available.
RR=0 cases have an explainable rr_zero_reason.
No unrelated production config files changed.
```

If no PROBE opens after this rollout, the next review should focus on whether `min_score=72`, `min_fib_score=12`, `min_pa_score=6`, or `min_rr_net_r=0.9` is the actual bottleneck, not on lowering DIRECT thresholds.

