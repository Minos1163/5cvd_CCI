# Strategy Philosophy Gap Fill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Update the section 01 strategy philosophy scripts so the expanded philosophy document is represented as testable contracts without changing live execution or signal parameters.

**Architecture:** Extend `src/core/strategy_philosophy.py` from a small role map into the strategy's policy contract module: decision priority, allowed trade types, symmetry, uncertainty responses, anti-noise/anti-overfit guards, capital/exit principles, and forbidden strategy patterns. Keep the implementation pure and side-effect free; actual signal/risk behavior remains in their own modules and can later be checked against these contracts.

**Tech Stack:** Python constants and small validation helpers, pytest, JSON describe script, existing scaffold template dictionary.

**Trading Hypothesis:** The system remains a multi-timeframe trend-following strategy for mainstream Binance USDT perpetuals. High timeframe direction and mid-timeframe quality must gate low-timeframe timing; risk and data quality come before opportunity.

**Expected Market Regime:** Directional continuation with identifiable 1H trend and 30m quality. In noisy ranges, uncertain states, low-quality data, cooldown, or risk pressure, the correct strategy action is wait/degrade/reduce exposure instead of adding exceptions.

**Failure Mode:** Overfitting through extra gates, asymmetric long/short exceptions, low-timeframe noise overriding higher-timeframe structure, ATR being used for direction, or execution/risk layers reinterpreting signal intent.

**Verification Command:** `pytest tests/test_strategy_philosophy.py tests/test_describe_project_rules.py tests/test_framework_scaffold.py -q`

---

### Task 1: Expanded Philosophy Contract

**Files:**
- Modify: `src/core/strategy_philosophy.py`
- Modify: `tests/test_strategy_philosophy.py`

- [ ] **Step 1: Write failing tests for expanded strategy philosophy**

Append tests to `tests/test_strategy_philosophy.py`:

```python
from src.core.strategy_philosophy import (
    ALLOWED_TRADE_TYPES,
    ANTI_NOISE_RULES,
    ANTI_OVERFIT_RULES,
    CAPITAL_MANAGEMENT_PRINCIPLES,
    DECISION_PRIORITY,
    EXIT_PHILOSOPHY,
    FIRST_PRINCIPLES,
    MARKET_STATES,
    PHILOSOPHY_FORBIDDEN_PATTERNS,
    STRATEGY_IDENTITY,
    STRATEGY_NON_GOALS,
    UNCERTAINTY_ACTIONS,
    validate_decision_priority,
    validate_long_short_symmetry,
    validate_strategy_pattern_allowed,
    validate_uncertainty_response,
)


def test_expanded_strategy_identity_and_non_goals_match_doc():
    assert STRATEGY_IDENTITY["venue"] == "binance_usdt_perpetual"
    assert STRATEGY_IDENTITY["style"] == "multi_timeframe_trend_following"
    assert STRATEGY_IDENTITY["core_sentence"] == "higher_tf_direction_mid_tf_quality_low_tf_timing_flow_confirmation_volatility_boundary"
    assert STRATEGY_NON_GOALS == [
        "high_frequency_market_making",
        "arbitrage",
        "black_box_prediction",
        "complex_score_stacking",
        "manual_discretionary_override",
    ]


def test_first_principles_and_decision_priority_are_fixed():
    assert FIRST_PRINCIPLES == [
        "risk_before_return",
        "trend_before_entry",
        "quality_before_quantity",
        "explainability_before_complexity",
        "live_backtest_isomorphism_before_optimization",
    ]
    assert DECISION_PRIORITY == [
        "data_quality",
        "risk_constraints",
        "higher_timeframe_direction",
        "mid_timeframe_quality",
        "lower_timeframe_timing",
        "fund_flow_confirmation",
        "position_executability",
        "execution_landing",
    ]
    assert validate_decision_priority(DECISION_PRIORITY).passed is True
    bad = list(DECISION_PRIORITY)
    bad[0], bad[1] = bad[1], bad[0]
    assert validate_decision_priority(bad).passed is False


def test_trade_types_market_states_and_uncertainty_policy():
    assert ALLOWED_TRADE_TYPES == ["PROBE", "DIRECT"]
    assert MARKET_STATES == [
        "uptrend",
        "downtrend",
        "range",
        "trend_transition",
        "volatility_expansion",
        "volatility_contraction",
    ]
    assert UNCERTAINTY_ACTIONS == ["degrade", "wait", "observe", "reduce_size", "disable_new_entries"]
    assert validate_uncertainty_response("wait").passed is True
    assert validate_uncertainty_response("increase_tolerance").passed is False


def test_symmetry_noise_overfit_capital_and_exit_principles_are_scripted():
    assert validate_long_short_symmetry({"LONG": ["trend", "quality"], "SHORT": ["trend", "quality"]}).passed is True
    assert validate_long_short_symmetry({"LONG": ["trend"], "SHORT": ["trend", "extra_exception"]}).passed is False
    assert "single_abnormal_candle" in ANTI_NOISE_RULES
    assert "add_rule_for_single_failed_sample" in ANTI_OVERFIT_RULES
    assert CAPITAL_MANAGEMENT_PRINCIPLES[0] == "define_trade_risk_first"
    assert EXIT_PHILOSOPHY[0] == "losses_should_be_fast"


def test_forbidden_strategy_patterns_reject_patchy_or_asymmetric_logic():
    assert "complex_watchlist_promotion_chain" in PHILOSOPHY_FORBIDDEN_PATTERNS
    assert "low_timeframe_noise_overrides_higher_timeframe" in PHILOSOPHY_FORBIDDEN_PATTERNS
    rejected = validate_strategy_pattern_allowed("add low_timeframe_noise_overrides_higher_timeframe exception")
    assert rejected.passed is False
    assert "low_timeframe_noise_overrides_higher_timeframe" in rejected.reason
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_strategy_philosophy.py -q`

Expected: FAIL because the expanded constants and helpers do not exist.

- [ ] **Step 3: Implement expanded philosophy contracts**

Update `src/core/strategy_philosophy.py`:

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PhilosophyCheck:
    name: str
    passed: bool
    reason: str


STRATEGY_IDENTITY = {
    "venue": "binance_usdt_perpetual",
    "style": "multi_timeframe_trend_following",
    "core_sentence": "higher_tf_direction_mid_tf_quality_low_tf_timing_flow_confirmation_volatility_boundary",
}
STRATEGY_NON_GOALS = [...]
FIRST_PRINCIPLES = [...]
MARKET_STATES = [...]
DECISION_PRIORITY = [...]
ALLOWED_TRADE_TYPES = ["PROBE", "DIRECT"]
ANTI_NOISE_RULES = [...]
ANTI_OVERFIT_RULES = [...]
CAPITAL_MANAGEMENT_PRINCIPLES = [...]
EXIT_PHILOSOPHY = [...]
UNCERTAINTY_ACTIONS = [...]
UNCERTAINTY_FORBIDDEN_ACTIONS = [...]
PHILOSOPHY_FORBIDDEN_PATTERNS = [...]
```

Keep existing names `REGIME_ACTIONS`, `TIMEFRAME_ROLES`, `INDICATOR_RESPONSIBILITIES`, `validate_indicator_role`, and `validate_decision_chain_depth`.

Add helpers:

```python
def validate_decision_priority(priority: list[str]) -> PhilosophyCheck:
    if priority != DECISION_PRIORITY:
        return PhilosophyCheck("decision_priority", False, "decision priority must remain fixed")
    return PhilosophyCheck("decision_priority", True, "decision priority approved")


def validate_long_short_symmetry(rule_map: dict[str, list[str]]) -> PhilosophyCheck:
    long_rules = rule_map.get("LONG", [])
    short_rules = rule_map.get("SHORT", [])
    if long_rules != short_rules:
        return PhilosophyCheck("long_short_symmetry", False, "long and short rules must be mirrored")
    return PhilosophyCheck("long_short_symmetry", True, "long and short rules are symmetric")


def validate_uncertainty_response(action: str) -> PhilosophyCheck:
    normalized = action.strip().lower()
    if normalized in UNCERTAINTY_ACTIONS:
        return PhilosophyCheck("uncertainty_response", True, "uncertainty response approved")
    return PhilosophyCheck("uncertainty_response", False, "uncertainty must degrade, wait, observe, reduce size, or disable new entries")


def validate_strategy_pattern_allowed(pattern: str) -> PhilosophyCheck:
    normalized = pattern.casefold()
    for forbidden in PHILOSOPHY_FORBIDDEN_PATTERNS:
        if forbidden.casefold() in normalized or normalized in forbidden.casefold():
            return PhilosophyCheck("strategy_pattern", False, f"{forbidden} is forbidden by strategy philosophy")
    return PhilosophyCheck("strategy_pattern", True, "strategy pattern allowed")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_strategy_philosophy.py -q`

Expected: PASS.

### Task 2: Describe Script Coverage

**Files:**
- Modify: `scripts/describe_project_rules.py`
- Modify: `tests/test_describe_project_rules.py`

- [ ] **Step 1: Write failing describe test expectations**

Update `tests/test_describe_project_rules.py`:

```python
def test_describe_project_rules_outputs_expanded_strategy_philosophy():
    result = subprocess.run(
        [sys.executable, "scripts/describe_project_rules.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    philosophy = payload["philosophy"]
    assert philosophy["strategy_identity"]["style"] == "multi_timeframe_trend_following"
    assert philosophy["first_principles"][0] == "risk_before_return"
    assert philosophy["decision_priority"][0] == "data_quality"
    assert philosophy["allowed_trade_types"] == ["PROBE", "DIRECT"]
    assert "single_abnormal_candle" in philosophy["anti_noise_rules"]
    assert "add_rule_for_single_failed_sample" in philosophy["anti_overfit_rules"]
    assert "increase_tolerance" in philosophy["uncertainty_forbidden_actions"]
    assert "complex_watchlist_promotion_chain" in philosophy["forbidden_patterns"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_describe_project_rules.py -q`

Expected: FAIL because the describe script does not expose expanded philosophy fields.

- [ ] **Step 3: Update describe script**

Modify `scripts/describe_project_rules.py` imports and payload to include:

- `STRATEGY_IDENTITY`
- `STRATEGY_NON_GOALS`
- `FIRST_PRINCIPLES`
- `MARKET_STATES`
- `DECISION_PRIORITY`
- `ALLOWED_TRADE_TYPES`
- `ANTI_NOISE_RULES`
- `ANTI_OVERFIT_RULES`
- `CAPITAL_MANAGEMENT_PRINCIPLES`
- `EXIT_PHILOSOPHY`
- `UNCERTAINTY_ACTIONS`
- `UNCERTAINTY_FORBIDDEN_ACTIONS`
- `PHILOSOPHY_FORBIDDEN_PATTERNS`

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_describe_project_rules.py -q`

Expected: PASS.

### Task 3: Scaffold Sync

**Files:**
- Modify: `scripts/scaffold_ai300_framework.py`
- Modify: `tests/test_framework_scaffold.py`

- [ ] **Step 1: Write failing scaffold test**

Append to `tests/test_framework_scaffold.py`:

```python
def test_scaffold_includes_expanded_strategy_philosophy_templates():
    template = FILES["src/core/strategy_philosophy.py"]
    assert "STRATEGY_IDENTITY" in template
    assert "DECISION_PRIORITY" in template
    assert "PHILOSOPHY_FORBIDDEN_PATTERNS" in template
    assert "validate_uncertainty_response" in template
    assert "validate_long_short_symmetry" in template
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_framework_scaffold.py -q`

Expected: FAIL because scaffold template still contains only the old philosophy contract.

- [ ] **Step 3: Update scaffold template**

Modify the `FILES["src/core/strategy_philosophy.py"]` string in `scripts/scaffold_ai300_framework.py` so it includes the expanded constants and helper names. Keep the template compact but complete enough for the scaffold test and describe script.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_framework_scaffold.py -q`

Expected: PASS.

### Task 4: Final Verification and Cache Cleanup

**Files:**
- No edits expected unless verification exposes a defect.

- [ ] **Step 1: Run targeted verification**

Run:

```powershell
pytest tests\test_strategy_philosophy.py tests\test_describe_project_rules.py tests\test_framework_scaffold.py -q
```

Expected: PASS.

- [ ] **Step 2: Run full verification**

Run:

```powershell
pytest -q
python -m compileall src scripts tests
python scripts\describe_project_rules.py
```

Expected: all commands exit 0.

- [ ] **Step 3: Confirm Binance client untouched**

Run:

```powershell
git diff -- src\api\binance_client.py
```

Expected: no output.

- [ ] **Step 4: Remove generated Python cache directories**

Run:

```powershell
$root=(Resolve-Path '.').Path
$targets=Get-ChildItem -Path . -Recurse -Directory -Filter '__pycache__' | Where-Object { $_.FullName.StartsWith($root) }
foreach($target in $targets){ Remove-Item -LiteralPath $target.FullName -Recurse -Force }
Get-ChildItem -Path . -Recurse -Directory -Filter '__pycache__' | Select-Object -First 5 -ExpandProperty FullName
```

Expected: no output from the final command.

---

## Self-Review

Spec coverage:
- Strategy identity, non-goals, core sentence, first principles, market states, timeframe roles, indicator roles, forbidden behavior, trade types, decision layers, fixed priority, long/short symmetry, trend/noise/overfit discipline, capital management, exit philosophy, uncertainty handling, and final values are covered.
- This plan intentionally does not alter `src/signals/signal_engine.py` or live behavior. It only makes section 01's philosophy testable.

Placeholder scan:
- No TBD/TODO/fill-later placeholders remain.

Type consistency:
- `PhilosophyCheck`, validation helper names, and constants are used consistently across module, tests, describe script, and scaffold.
