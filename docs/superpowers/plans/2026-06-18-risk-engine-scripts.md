# Risk Engine Scripts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `docs/17_risk_engine.md` contract as executable Python scripts: a pure risk engine, a describe script, tests, and scaffold templates.

**Architecture:** Add `src/risk/risk_engine.py` as the risk gate that consumes signal intent plus account, portfolio, volatility, stop, and cooldown context, then emits a structured `RiskResult`. Existing 06 `position_sizer.py`, 07 `stop_engine.py`, and `exit_engine.py` remain responsible for final quantity math and exit primitives; the risk engine only outputs constraints, scaling factors, reasons, snapshots, and metadata.

**Tech Stack:** Python dataclasses, standard-library JSON scripts, pytest.

---

### Task 1: Risk Engine Contract And Decision Order

**Files:**
- Create: `src/risk/risk_engine.py`
- Test: `tests/test_risk_engine.py`

- [ ] **Step 1: Write failing tests for direct approval and snapshot fields**

Create tests that assert a clean direct context allows trade and records a replayable snapshot:

```python
def test_direct_risk_ok_outputs_normal_risk_snapshot():
    result = evaluate_risk(base_context())
    assert result.allow_trade is True
    assert result.risk_level == "NORMAL"
    assert result.position_size_factor == 1.0
    assert result.risk_reason == "FULL_CONFIRMATION_AND_RISK_OK"
    assert result.metrics_snapshot["symbol"] == "BTCUSDT"
    assert result.metrics_snapshot["risk_level"] == "NORMAL"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_risk_engine.py -q`

Expected: FAIL because `src.risk.risk_engine` does not exist.

- [ ] **Step 3: Implement the pure risk engine**

Create constants and dataclasses:

```python
RISK_LEVELS = ["LOW", "NORMAL", "HIGH", "EXTREME", "BLOCKED"]
RISK_DECISION_FLOW = [
    "check_data_quality",
    "check_cooldown",
    "check_account_risk",
    "check_portfolio_risk",
    "check_symbol_risk",
    "check_volatility_risk",
    "check_stop_distance",
    "check_position_executability",
    "check_add_reduce_exit",
    "output_risk_result",
]

@dataclass(frozen=True)
class RiskContext: ...

@dataclass(frozen=True)
class RiskResult: ...
```

Implement `evaluate_risk(context)` as a side-effect-free function. It must not import or call Binance, submit orders, generate signals, or calculate final exchange precision.

- [ ] **Step 4: Run risk tests**

Run: `pytest tests/test_risk_engine.py -q`

Expected: PASS.

### Task 2: Risk Gates, Scaling, Exit, And Cooldown Tests

**Files:**
- Modify: `tests/test_risk_engine.py`
- Modify: `src/risk/risk_engine.py`

- [ ] **Step 1: Add failing tests for all required 17 gates**

Cover:

```python
def test_daily_weekly_drawdown_quality_cooldown_and_exposure_block():
    assert evaluate_risk(base_context(daily_pnl=-600)).risk_reason == "DAILY_LOSS_LIMIT_REACHED"
    assert evaluate_risk(base_context(weekly_pnl=-1300)).risk_reason == "WEEKLY_LOSS_LIMIT_REACHED"
    assert evaluate_risk(base_context(max_drawdown=0.25)).risk_reason == "MAX_DRAWDOWN_LIMIT_REACHED"
    assert evaluate_risk(base_context(quality_flag=False)).risk_reason == "DATA_QUALITY_BLOCKED"
    assert evaluate_risk(base_context(cooldown_state={"active": True})).risk_reason == "COOLDOWN_ACTIVE"
    assert evaluate_risk(base_context(portfolio_exposure=0.80)).risk_reason == "PORTFOLIO_EXPOSURE_LIMIT_REACHED"
```

Also cover high volatility probe scaling, direct approval, reduce trigger, forced exit trigger, and stop distance blocking.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_risk_engine.py -q`

Expected: FAIL until the gates and scoring logic are implemented.

- [ ] **Step 3: Implement gates and scoring**

Implement risk scoring components:

```python
RISK_SCORE_COMPONENTS = [
    "account_risk_score",
    "portfolio_risk_score",
    "symbol_risk_score",
    "volatility_risk_score",
    "cooldown_risk_score",
    "data_quality_risk_score",
]
```

Map total scores to `LOW`, `NORMAL`, `HIGH`, `EXTREME`, and `BLOCKED`. Hard blocks include data quality failure, active cooldown, daily loss, weekly loss, max drawdown, portfolio exposure limit, symbol exposure limit, unavailable ATR, invalid stop distance, and insufficient margin.

- [ ] **Step 4: Run risk tests**

Run: `pytest tests/test_risk_engine.py -q`

Expected: PASS.

### Task 3: Risk Engine Describe Script

**Files:**
- Create: `scripts/describe_risk_engine.py`
- Test: `tests/test_describe_risk_engine.py`

- [ ] **Step 1: Write failing describe-script tests**

Add a subprocess test that asserts:

```python
assert payload["engine"] == "risk_engine"
assert payload["risk_levels"] == ["LOW", "NORMAL", "HIGH", "EXTREME", "BLOCKED"]
assert payload["decision_flow"][0] == "check_data_quality"
assert payload["forbidden_actions"]["risk layer"][0] == "generate_trade_signal"
assert payload["relationships"]["position module"] == "calculates final_notional and final_qty"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_describe_risk_engine.py -q`

Expected: FAIL because the script does not exist.

- [ ] **Step 3: Implement `scripts/describe_risk_engine.py`**

The script imports public constants from `src.risk.risk_engine` and prints sorted JSON containing risk levels, decision flow, inputs, outputs, default limits, score components, snapshot fields, action priority, relationship boundaries, forbidden actions, and sample decisions.

- [ ] **Step 4: Run describe tests**

Run: `pytest tests/test_describe_risk_engine.py -q`

Expected: PASS.

### Task 4: Scaffold Template Sync

**Files:**
- Modify: `scripts/scaffold_ai300_framework.py`
- Test: `tests/test_framework_scaffold.py`

- [ ] **Step 1: Add scaffold assertions**

Extend scaffold checks:

```python
def test_scaffold_includes_risk_engine_17_templates():
    assert "src/risk/risk_engine.py" in FILES
    assert "scripts/describe_risk_engine.py" in FILES
    assert "tests/test_risk_engine.py" in FILES
    assert "tests/test_describe_risk_engine.py" in FILES
    assert "RiskResult" in FILES["src/risk/risk_engine.py"]
```

- [ ] **Step 2: Sync templates**

Update the `FILES` mapping in `scripts/scaffold_ai300_framework.py` with the final risk engine module, describe script, and tests. Keep the protected Binance client guard unchanged.

- [ ] **Step 3: Run scaffold tests**

Run: `pytest tests/test_framework_scaffold.py tests/test_risk_engine.py tests/test_describe_risk_engine.py -q`

Expected: PASS.

### Task 5: Verification

**Files:**
- Read-only verification of `src/api/binance_client.py`

- [ ] **Step 1: Run targeted tests**

Run: `pytest tests/test_risk_engine.py tests/test_describe_risk_engine.py tests/test_framework_scaffold.py -q`

Expected: PASS.

- [ ] **Step 2: Run full tests**

Run: `pytest -q`

Expected: PASS.

- [ ] **Step 3: Compile Python files**

Run: `python -m compileall src scripts tests`

Expected: all files compile.

- [ ] **Step 4: Confirm Binance client untouched**

Run: `git diff -- src/api/binance_client.py`

Expected: no output.

- [ ] **Step 5: Remove generated cache directories**

Run:

```powershell
$root=(Resolve-Path '.').Path
$targets=Get-ChildItem -Path . -Recurse -Directory -Filter '__pycache__' | Where-Object { $_.FullName.StartsWith($root) }
foreach($target in $targets){ Remove-Item -LiteralPath $target.FullName -Recurse -Force }
```

Expected: no remaining `__pycache__` directories under the workspace.

---

## Scope Review

- Covered: standardized `RiskContext`, `RiskResult`, fixed decision order, data quality, cooldown, account risk, portfolio risk, symbol risk, volatility risk, stop distance, position executability, add/reduce/exit flags, probe/direct scaling, risk score, risk snapshot, describe script, scaffold sync.
- Explicitly out of scope: trend signal generation, final exchange quantity precision, order creation, Binance adapter calls, live balance mutation, and execution-layer risk recalculation.
