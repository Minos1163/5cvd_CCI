# Elite Probe And Dynamic Scout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make dry-run main trades more selective by blocking lowest-tier PROBE entries from the main ledger, while expanding SCOUT_MICRO coverage to the symbols where near-miss pressure actually appears.

**Architecture:** Keep the existing action model (`NO_TRADE`, `WATCH`, `PROBE`, `DIRECT`) and avoid introducing a new `SCOUT` action. Main-entry PROBE filtering stays inside `check_probe_conditions`; SCOUT_MICRO continues to consume near-miss `WATCH/NO_TRADE` payloads, with mission eligibility driven by tags/reasons plus configured authorization pools.

**Tech Stack:** Python, dataclasses, JSON config, pytest.

## Global Constraints

- This is DRY-RUN strategy research; do not modify live execution or production config paths.
- Avoid lookahead bias, future candle data, repaint signals, and same-bar fill assumptions.
- Strategy hypothesis: low-score PROBE entries that only barely pass component minimums create poor first-shot risk and can consume later better symbol opportunities.
- Expected market regime: choppy-to-trending crypto markets where strong structure confirmation improves short-term trade quality.
- Failure mode: filters may become too strict and reduce main trade count; SCOUT mission pools may still sample noisy LONG offset candidates.
- Verification command: `pytest tests/test_entry_chain_probe_conditions.py tests/test_live_dry_run.py tests/test_entry_chain_config.py tests/test_dry_run_configs.py -q`.
- Keep changes surgical: no new dependencies, no live config edits, no broad refactors.

---

## File Structure

- Modify `src/signals/entry_chain.py`: add optional elite PROBE main-trade checks inside `check_probe_conditions`.
- Modify `scripts/run_live_dry_run.py`: make `TARGETED_LONG_OFFSET` mission eligibility honor the existing scout tag as well as the reason string.
- Modify `configs/entry_chain.dry_run_fib_pa_v1.json`: enable elite PROBE checks, expand targeted-long scout symbols, add ADA to SCOUT_ONLY, and pause ZEC micro-trading by removing it from SCOUT pools.
- Modify `tests/test_entry_chain_probe_conditions.py`: cover low-score veto and elite structure pass/fail cases.
- Modify `tests/test_live_dry_run.py`: cover targeted-long mission eligibility for expanded dynamic mission tags.
- Modify `tests/test_dry_run_configs.py`: update dry-run config expectations.

---

### Task 1: Elite PROBE Main-Trade Gate

**Files:**
- Modify: `src/signals/entry_chain.py`
- Modify: `tests/test_entry_chain_probe_conditions.py`

**Interfaces:**
- Consumes: `check_probe_conditions(score, side, component_points, rr_detail, config) -> tuple[bool, str]`
- Produces: optional config keys inside `probe_conditions`:
  - `elite_probe_enabled: bool`
  - `elite_probe_min_score: float`
  - `elite_probe_min_pa_score: float`
  - `elite_probe_min_fib_score: float`
  - `elite_probe_trend_min_ema_score: float`
  - `elite_probe_trend_min_structure_sum: float`

- [ ] **Step 1: Add failing tests**

Add tests:

```python
def test_probe_rejected_when_below_elite_min_score_even_if_components_pass():
    allowed, reason = check_probe_conditions(
        score=72.75,
        side="SHORT",
        component_points={
            "fibonacci_location": 13.0,
            "price_action_structure": 12.0,
            "risk_reward_geometry": 6.5,
            "trend_ema_context": 13.25,
            "cci_momentum_quality": 10.0,
        },
        rr_detail=None,
        config={
            "enabled": True,
            "min_score": 72.0,
            "min_fib_score": 12.0,
            "min_pa_score": 10.0,
            "min_rr_score": 4.0,
            "elite_probe_enabled": True,
            "elite_probe_min_score": 75.0,
        },
    )

    assert allowed is False
    assert reason == "PROBE_LOW_SCORE_ELITE_VETO"
```

```python
def test_probe_rejected_when_elite_structure_is_not_strong_enough():
    allowed, reason = check_probe_conditions(
        score=80.0,
        side="SHORT",
        component_points={
            "fibonacci_location": 13.0,
            "price_action_structure": 12.0,
            "risk_reward_geometry": 6.5,
            "trend_ema_context": 13.25,
            "cci_momentum_quality": 10.0,
        },
        rr_detail=None,
        config={
            "enabled": True,
            "min_score": 72.0,
            "min_fib_score": 12.0,
            "min_pa_score": 10.0,
            "min_rr_score": 4.0,
            "elite_probe_enabled": True,
            "elite_probe_min_score": 75.0,
            "elite_probe_min_pa_score": 18.0,
            "elite_probe_min_fib_score": 15.0,
            "elite_probe_trend_min_ema_score": 15.0,
            "elite_probe_trend_min_structure_sum": 30.0,
        },
    )

    assert allowed is False
    assert reason == "PROBE_BELOW_ELITE_STRUCTURE_GATE"
```

```python
def test_probe_allowed_when_elite_structure_or_trend_compensation_passes():
    structure_allowed, structure_reason = check_probe_conditions(
        score=80.0,
        side="SHORT",
        component_points={
            "fibonacci_location": 15.0,
            "price_action_structure": 18.0,
            "risk_reward_geometry": 5.0,
            "trend_ema_context": 12.0,
            "cci_momentum_quality": 10.0,
        },
        rr_detail=None,
        config={
            "enabled": True,
            "min_score": 72.0,
            "min_fib_score": 12.0,
            "min_pa_score": 10.0,
            "min_rr_score": 4.0,
            "elite_probe_enabled": True,
            "elite_probe_min_score": 75.0,
            "elite_probe_min_pa_score": 18.0,
            "elite_probe_min_fib_score": 15.0,
            "elite_probe_trend_min_ema_score": 15.0,
            "elite_probe_trend_min_structure_sum": 30.0,
        },
    )
    trend_allowed, trend_reason = check_probe_conditions(
        score=80.0,
        side="SHORT",
        component_points={
            "fibonacci_location": 13.0,
            "price_action_structure": 17.0,
            "risk_reward_geometry": 5.0,
            "trend_ema_context": 15.0,
            "cci_momentum_quality": 10.0,
        },
        rr_detail=None,
        config={
            "enabled": True,
            "min_score": 72.0,
            "min_fib_score": 12.0,
            "min_pa_score": 10.0,
            "min_rr_score": 4.0,
            "elite_probe_enabled": True,
            "elite_probe_min_score": 75.0,
            "elite_probe_min_pa_score": 18.0,
            "elite_probe_min_fib_score": 15.0,
            "elite_probe_trend_min_ema_score": 15.0,
            "elite_probe_trend_min_structure_sum": 30.0,
        },
    )

    assert structure_allowed is True
    assert structure_reason == ""
    assert trend_allowed is True
    assert trend_reason == ""
```

- [ ] **Step 2: Run focused failing tests**

Run: `pytest tests/test_entry_chain_probe_conditions.py -q`  
Expected: FAIL because elite config keys are not implemented.

- [ ] **Step 3: Implement minimal elite gate**

Inside `check_probe_conditions`, after the existing low-score quality and trend/CCI gates but before RR checks return success, add:

```python
    if bool(config.get("elite_probe_enabled", False)):
        elite_min_score = float(config.get("elite_probe_min_score", 75.0))
        if float(score) < elite_min_score:
            return False, "PROBE_LOW_SCORE_ELITE_VETO"
        fib_score = float(component_points.get("fibonacci_location", 0.0))
        pa_score = float(component_points.get("price_action_structure", 0.0))
        elite_pa = float(config.get("elite_probe_min_pa_score", 18.0))
        elite_fib = float(config.get("elite_probe_min_fib_score", 15.0))
        elite_ema = float(config.get("elite_probe_trend_min_ema_score", 15.0))
        elite_sum = float(config.get("elite_probe_trend_min_structure_sum", 30.0))
        strong_structure = pa_score >= elite_pa and fib_score >= elite_fib
        trend_structure = trend_score >= elite_ema and (pa_score + fib_score) >= elite_sum
        if not (strong_structure or trend_structure):
            return False, "PROBE_BELOW_ELITE_STRUCTURE_GATE"
```

- [ ] **Step 4: Verify**

Run: `pytest tests/test_entry_chain_probe_conditions.py -q`  
Expected: PASS.

---

### Task 2: Dynamic SCOUT Mission Coverage

**Files:**
- Modify: `scripts/run_live_dry_run.py`
- Modify: `tests/test_live_dry_run.py`

**Interfaces:**
- Consumes: near-miss payload with `scout_tags: ["TARGETED_LONG_OFFSET"]`
- Produces: `scout_micro_mission(...) == "TARGETED_LONG_OFFSET"` when symbol is authorized and score/PA/RR meet mission thresholds.

- [ ] **Step 1: Add failing test for authorized non-CC targeted LONG**

Add:

```python
def test_scout_micro_allows_targeted_long_offset_for_authorized_mission_pool_symbol(tmp_path):
    ledger = PaperTradingLedger(tmp_path / "scout_micro")
    near_miss = {
        "symbol": "LINKUSDT",
        "intended_side": "LONG",
        "entry_price": 18.0,
        "score": 86.0,
        "reasons": ["FIB_PA_ARCHITECTURE_WEIGHTS", "SIDE_THRESHOLD_OFFSET_LONG_10.00"],
        "component_points": {
            "price_action_structure": 21.0,
            "risk_reward_geometry": 3.0,
        },
        "scout_tags": ["TARGETED_LONG_OFFSET"],
    }
    config = EntryChainConfig(
        scout_micro_symbols=("LINKUSDT",),
        scout_micro_targeted_long_symbols=("LINKUSDT",),
    )

    assert (
        should_open_scout_micro(
            symbol="LINKUSDT",
            near_miss=near_miss,
            config=config,
            data_health="OK",
            scout_paper=ledger,
        )
        is True
    )
```

Add:

```python
def test_scout_micro_uses_targeted_long_tag_even_when_reason_list_is_compacted(tmp_path):
    ledger = PaperTradingLedger(tmp_path / "scout_micro")
    near_miss = {
        "symbol": "LABUSDT",
        "intended_side": "LONG",
        "entry_price": 1.0,
        "score": 86.0,
        "reasons": ["FIB_PA_ARCHITECTURE_WEIGHTS"],
        "component_points": {
            "price_action_structure": 21.0,
            "risk_reward_geometry": 3.0,
        },
        "scout_tags": ["TARGETED_LONG_OFFSET"],
    }
    config = EntryChainConfig(
        scout_micro_symbols=("LABUSDT",),
        scout_micro_targeted_long_symbols=("LABUSDT",),
    )

    assert (
        should_open_scout_micro(
            symbol="LABUSDT",
            near_miss=near_miss,
            config=config,
            data_health="OK",
            scout_paper=ledger,
        )
        is True
    )
```

- [ ] **Step 2: Run focused failing tests**

Run: `pytest tests/test_live_dry_run.py -q`  
Expected: second new test FAIL because `_targeted_long_offset_scout_eligible` only checks reason text.

- [ ] **Step 3: Implement tag-aware mission check**

In `_targeted_long_offset_scout_eligible`, compute tags and accept either the reason or the tag:

```python
    tags = near_miss.get("scout_tags", [])
    tag_list = [str(item) for item in tags] if isinstance(tags, list) else [str(tags)]
    if "SIDE_THRESHOLD_OFFSET_LONG_10.00" not in reasons and "TARGETED_LONG_OFFSET" not in tag_list:
        return False
```

- [ ] **Step 4: Verify**

Run: `pytest tests/test_live_dry_run.py -q`  
Expected: PASS.

---

### Task 3: Dry-Run Configuration For Elite Main Trades And Wider SCOUT Pool

**Files:**
- Modify: `configs/entry_chain.dry_run_fib_pa_v1.json`
- Modify: `tests/test_dry_run_configs.py`

**Interfaces:**
- Produces dry-run config values:
  - `probe_conditions.elite_probe_enabled = true`
  - `probe_conditions.elite_probe_min_score = 75.0`
  - `probe_conditions.elite_probe_min_pa_score = 18.0`
  - `probe_conditions.elite_probe_min_fib_score = 15.0`
  - `probe_conditions.elite_probe_trend_min_ema_score = 15.0`
  - `probe_conditions.elite_probe_trend_min_structure_sum = 30.0`
  - `scout_micro_symbols` includes `XLMUSDT`, `CCUSDT`, `XMRUSDT`, `ADAUSDT`, `LINKUSDT`, `LABUSDT`, `HYPEUSDT`, `DOGEUSDT`
  - `scout_micro_targeted_long_symbols` includes `LINKUSDT`, `LABUSDT`, `HYPEUSDT`, `DOGEUSDT`, `CCUSDT`, `XLMUSDT`
  - `scout_micro_scout_only_symbols` includes `XMRUSDT`, `ADAUSDT`
  - `ZECUSDT` remains blacklisted but is removed from SCOUT micro pools.

- [ ] **Step 1: Update config test expectations**

Update `tests/test_dry_run_configs.py` assertions to the exact values above and assert the elite probe keys are present inside `config.probe_conditions`.

- [ ] **Step 2: Run focused failing config tests**

Run: `pytest tests/test_dry_run_configs.py -q`  
Expected: FAIL until JSON config is updated.

- [ ] **Step 3: Update JSON config**

Edit `configs/entry_chain.dry_run_fib_pa_v1.json` with the exact values from the interface section.

- [ ] **Step 4: Verify**

Run: `pytest tests/test_dry_run_configs.py -q`  
Expected: PASS.

---

### Task 4: Final Verification

**Files:**
- No additional source changes expected.

- [ ] **Step 1: Run combined focused suite**

Run:

```powershell
pytest tests/test_entry_chain_probe_conditions.py tests/test_live_dry_run.py tests/test_entry_chain_config.py tests/test_dry_run_configs.py -q
```

Expected: PASS.

- [ ] **Step 2: Inspect changed files**

Run:

```powershell
git diff -- src/signals/entry_chain.py scripts/run_live_dry_run.py configs/entry_chain.dry_run_fib_pa_v1.json tests/test_entry_chain_probe_conditions.py tests/test_live_dry_run.py tests/test_dry_run_configs.py docs/superpowers/plans/2026-07-06-elite-probe-dynamic-scout.md
```

Expected: Diff only contains this plan's scoped changes.
