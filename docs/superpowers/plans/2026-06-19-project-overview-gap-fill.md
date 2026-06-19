# Project Overview Gap Fill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the refreshed `docs/00_project_overview.md` into a clean, testable, machine-readable project-level contract without changing live trading behavior.

**Architecture:** Keep this as a contract synchronization pass. The implementation should update the top-level markdown, core project/module contract constants, describe script output, scaffold templates, and tests. It must not modify `src/api/binance_client.py`, live exchange behavior, strategy signal logic, risk calculations, or backtest fill assumptions.

**Tech Stack:** Python standard library, dataclasses/tuples/dicts, pytest, JSON describe scripts, markdown documentation.

---

## File Structure

Modify:

- `docs/00_project_overview.md`  
  Clean the markdown so it starts directly at `# Project Overview` and remove the outer ChatGPT wrapper/code fence.

- `src/core/project_spec.py`  
  Expand the project overview constants and validation helpers.

- `tests/test_project_spec.py`  
  Add tests that lock the expanded `00` overview contract.

- `src/core/module_spec.py`  
  Align module structure and dependency flow with the full system boundary.

- `tests/test_python_module_spec.py`  
  Add tests for the expanded module/dependency contract.

- `scripts/describe_project_rules.py`  
  Export the expanded project overview as JSON.

- `tests/test_describe_project_rules.py`  
  Assert the describe script exposes the new overview fields.

- `scripts/scaffold_ai300_framework.py`  
  Sync scaffold templates so a future scaffold does not recreate the old project contract.

- `tests/test_framework_scaffold.py`  
  Verify the scaffold continues to protect `src/api/binance_client.py` and emits the expanded project contract in fresh workspaces.

Do not modify:

- `src/api/binance_client.py`
- `src/execution/binance_adapter.py`
- Any live credentials, config secrets, or production execution paths

---

## Shared Contract Decisions

Use these names consistently across all tasks:

```python
PROJECT_NAME = "多周期主流虚拟币趋势交易系统"
PROJECT_ENGLISH_NAME = "crypto-mtf-trend-strategy"
TRADING_VENUE = "binance_usdt_perpetual"

CORE_TIMEFRAMES = ("15m", "30m", "1h")
REFERENCE_TIMEFRAMES = ("4h",)
TIMEFRAME_ROLES = {
    "15m": "execution",
    "30m": "confirmation",
    "1h": "direction",
    "4h": "background_reference_only",
}

ENTRY_FORMS = {
    "PROBE": {"size_ratio": 0.25, "role": "test_direction_continuation"},
    "DIRECT": {"size_ratio": 1.0, "role": "full_confirmed_entry"},
}
```

Use this conceptual dependency flow:

```python
MODULE_DEPENDENCY_FLOW = (
    "data",
    "indicators",
    "context",
    "signals",
    "state_machine",
    "risk",
    "position_sizing",
    "execution",
    "backtest",
    "reporting",
    "monitoring",
)
```

Bridge the conceptual `position_sizing` layer to the existing code location by documenting it in constants, not by moving files:

```python
CONCEPTUAL_LAYER_IMPLEMENTATIONS = {
    "position_sizing": "src/risk/position_sizer.py",
    "monitoring": "src/observability/logging_metrics.py",
    "deployment": "src/deployment/deployment_architecture.py",
}
```

---

### Task 1: Clean The Project Overview Markdown

**Files:**

- Modify: `docs/00_project_overview.md`

- [ ] **Step 1: Inspect the current wrapper lines**

Run:

```powershell
$i=0; Get-Content docs\00_project_overview.md | ForEach-Object { $i++; if ($i -le 8 -or $_ -match '````') { "${i}: $_" } }
```

Expected: output shows wrapper text before `# Project Overview` and an outer ````md code fence.

- [ ] **Step 2: Rewrite the markdown without changing section meaning**

Edit `docs/00_project_overview.md` so:

- Line 1 is exactly `# Project Overview`.
- The file keeps all numbered sections from the refreshed overview.
- The dependency-flow block uses a normal fenced code block:

```markdown
```text
Data Layer
  -> Indicator Layer
  -> Context Layer
  -> Signal Engine
  -> State Machine
  -> Risk Engine
  -> Position Sizing
  -> Execution Engine
  -> Backtest Engine
  -> Reporting / Monitoring
```
```

- There is no outer ````md wrapper around the whole file.
- There is no sentence saying "下面是重新生成的".

- [ ] **Step 3: Verify the cleaned document**

Run:

```powershell
$first = Get-Content docs\00_project_overview.md -TotalCount 1
if ($first -ne "# Project Overview") { throw "unexpected first line: $first" }
Select-String -Path docs\00_project_overview.md -Pattern "下面是重新生成|````md" -Quiet
```

Expected: the first command succeeds. The final `Select-String` prints `False`.

- [ ] **Step 4: Commit**

```powershell
git add docs\00_project_overview.md
git commit -m "docs: clean project overview contract"
```

Expected: commit succeeds and only `docs/00_project_overview.md` is staged for this task.

---

### Task 2: Expand The Project Overview Contract

**Files:**

- Modify: `src/core/project_spec.py`
- Modify: `tests/test_project_spec.py`

- [ ] **Step 1: Write failing tests for the expanded project contract**

Add these imports and tests to `tests/test_project_spec.py`:

```python
from src.core.project_spec import (
    BACKTEST_GOALS,
    CORE_DESIGN_GOALS,
    ENTRY_FORMS,
    FINAL_SYSTEM_TRAITS,
    IMPLEMENTATION_PRINCIPLES,
    INDICATOR_RESPONSIBILITIES,
    LIVE_TRADING_GOALS,
    MODULE_DEPENDENCY_FLOW,
    OPERATIONAL_SUCCESS_STANDARDS,
    POSITION_GOALS,
    PROJECT_ENGLISH_NAME,
    PROJECT_NAME,
    PROJECT_NON_GOALS,
    PROJECT_OBJECTIVE,
    PROJECT_PRIORITY,
    RECOMMENDED_DEVELOPMENT_ORDER,
    RISK_GOALS,
    SYSTEM_LAYERS,
    TIMEFRAME_ROLES,
    TRADING_DECISION_PRINCIPLES,
    UNIFIED_CONTRACTS,
    validate_entry_form,
    validate_timeframe_role,
)


def test_project_identity_objective_and_design_goals_match_overview():
    assert PROJECT_NAME == "多周期主流虚拟币趋势交易系统"
    assert PROJECT_ENGLISH_NAME == "crypto-mtf-trend-strategy"
    assert "Binance USDT 永续合约" in PROJECT_OBJECTIVE
    assert CORE_DESIGN_GOALS == (
        "logic_clear",
        "timeframe_responsibilities_clear",
        "single_responsibility_indicators",
        "traceable_state_machine",
        "stable_position_contract",
        "unified_risk_rules",
        "backtest_live_isomorphic",
        "thin_stable_execution_layer",
        "fixed_data_contract",
        "replayable_auditable_behavior",
    )


def test_timeframe_roles_are_explicit_and_4h_is_reference_only():
    assert TIMEFRAME_ROLES == {
        "15m": "execution",
        "30m": "confirmation",
        "1h": "direction",
        "4h": "background_reference_only",
    }
    assert validate_timeframe_role("15m", "execution").passed is True
    assert validate_timeframe_role("4h", "hard_filter").passed is False


def test_indicator_responsibilities_are_single_purpose():
    assert INDICATOR_RESPONSIBILITIES == {
        "MACD": "trend_and_momentum",
        "CCI": "strength_and_deviation",
        "BOLL": "volatility_structure_and_expansion",
        "RSI": "pullback_quality_and_overheat",
        "CVD": "fund_flow_and_aggressive_buy_sell_power",
        "ATR": "stop_take_profit_position_and_volatility_risk",
    }


def test_entry_forms_are_probe_and_direct_only():
    assert ENTRY_FORMS == {
        "PROBE": {"size_ratio": 0.25, "role": "test_direction_continuation"},
        "DIRECT": {"size_ratio": 1.0, "role": "full_confirmed_entry"},
    }
    assert validate_entry_form("PROBE").passed is True
    assert validate_entry_form("DIRECT").passed is True
    assert validate_entry_form("PROMOTION").passed is False


def test_project_layers_contracts_principles_and_success_standards_are_scripted():
    assert SYSTEM_LAYERS == MODULE_DEPENDENCY_FLOW
    assert MODULE_DEPENDENCY_FLOW == (
        "data",
        "indicators",
        "context",
        "signals",
        "state_machine",
        "risk",
        "position_sizing",
        "execution",
        "backtest",
        "reporting",
        "monitoring",
    )
    assert UNIFIED_CONTRACTS == (
        "data",
        "indicator",
        "event",
        "state_machine",
        "risk",
        "position",
        "execution",
        "backtest",
        "config",
        "logging",
    )
    assert OPERATIONAL_SUCCESS_STANDARDS[0] == "stable_signal_generation"
    assert IMPLEMENTATION_PRINCIPLES[0] == "contract_first"
    assert RECOMMENDED_DEVELOPMENT_ORDER[0] == "config_and_data_contract"
    assert FINAL_SYSTEM_TRAITS[-1] == "hard_to_lose_control_when_extended"


def test_project_goal_groups_and_non_goals_are_exposed():
    assert PROJECT_PRIORITY == ("stability", "explainability", "profitability")
    assert "no_high_frequency_trading" in PROJECT_NON_GOALS
    assert "control_single_trade_loss" in RISK_GOALS
    assert "position_links_to_stop_distance" in POSITION_GOALS
    assert "no_future_data" in BACKTEST_GOALS
    assert "recoverable_strategy_state" in LIVE_TRADING_GOALS
    assert TRADING_DECISION_PRINCIPLES[0] == "multi_timeframe_alignment_first"
```

- [ ] **Step 2: Run the project-spec tests and confirm they fail**

Run:

```powershell
pytest tests\test_project_spec.py -q
```

Expected: FAIL because the new constants and validators are not implemented yet.

- [ ] **Step 3: Implement the minimal project contract**

Update `src/core/project_spec.py` by adding the missing constants and validation result type. Keep the existing `PROJECT_PRIORITY`, `CORE_TIMEFRAMES`, `REFERENCE_TIMEFRAMES`, `TRADING_VENUE`, `SUCCESS_CRITERIA`, and `validate_feature_allowed()` names for compatibility.

Use this implementation shape:

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProjectSpecCheck:
    passed: bool
    reason: str


PROJECT_NAME = "多周期主流虚拟币趋势交易系统"
PROJECT_ENGLISH_NAME = "crypto-mtf-trend-strategy"
PROJECT_OBJECTIVE = (
    "构建一套可回测、可实盘、可审计、可维护的 Binance USDT 永续合约交易系统，"
    "用于交易市值前 20 的主流虚拟币。"
)
PROJECT_PRIORITY = ("stability", "explainability", "profitability")
TRADING_VENUE = "binance_usdt_perpetual"

CORE_DESIGN_GOALS = (
    "logic_clear",
    "timeframe_responsibilities_clear",
    "single_responsibility_indicators",
    "traceable_state_machine",
    "stable_position_contract",
    "unified_risk_rules",
    "backtest_live_isomorphic",
    "thin_stable_execution_layer",
    "fixed_data_contract",
    "replayable_auditable_behavior",
)

CORE_TIMEFRAMES = ("15m", "30m", "1h")
REFERENCE_TIMEFRAMES = ("4h",)
TIMEFRAME_ROLES = {
    "15m": "execution",
    "30m": "confirmation",
    "1h": "direction",
    "4h": "background_reference_only",
}

INDICATOR_RESPONSIBILITIES = {
    "MACD": "trend_and_momentum",
    "CCI": "strength_and_deviation",
    "BOLL": "volatility_structure_and_expansion",
    "RSI": "pullback_quality_and_overheat",
    "CVD": "fund_flow_and_aggressive_buy_sell_power",
    "ATR": "stop_take_profit_position_and_volatility_risk",
}

TRADING_DECISION_PRINCIPLES = (
    "multi_timeframe_alignment_first",
    "complete_structure_first",
    "same_direction_fund_flow_first",
    "reasonable_volatility_first",
    "qualified_data_quality_first",
    "risk_approval_first",
    "executable_position_first",
)

ENTRY_FORMS = {
    "PROBE": {"size_ratio": 0.25, "role": "test_direction_continuation"},
    "DIRECT": {"size_ratio": 1.0, "role": "full_confirmed_entry"},
}

PROJECT_NON_GOALS = (
    "no_high_frequency_trading",
    "no_arbitrage",
    "no_market_making",
    "no_black_box_machine_learning_prediction",
    "no_complex_watchlist_promotion_chain",
    "no_cross_layer_patchwork",
    "no_trade_for_the_sake_of_trading",
)

RISK_GOALS = (
    "control_single_trade_loss",
    "control_single_symbol_risk",
    "control_portfolio_total_exposure",
    "control_daily_loss",
    "control_weekly_loss",
    "control_drawdown",
    "control_abnormal_volatility_exposure",
    "control_revenge_retry_after_consecutive_losses",
)

POSITION_GOALS = (
    "stable_probe_direct_semantics",
    "position_links_to_stop_distance",
    "position_links_to_volatility",
    "position_links_to_equity",
    "position_links_to_portfolio_exposure",
    "position_links_to_min_notional",
)

BACKTEST_GOALS = (
    "backtest_live_isomorphic",
    "no_future_data",
    "record_each_trade",
    "record_state_machine",
    "record_failure_samples",
    "record_risk_blocks",
    "record_position_calculation",
    "repeatable_runs",
    "version_comparable",
)

LIVE_TRADING_GOALS = (
    "recoverable_strategy_state",
    "traceable_order_state",
    "syncable_position_state",
    "repairable_protection_orders",
    "risk_can_block",
    "alert_on_exception",
    "auditable_behavior",
)

SYSTEM_LAYERS = (
    "data",
    "indicators",
    "context",
    "signals",
    "state_machine",
    "risk",
    "position_sizing",
    "execution",
    "backtest",
    "reporting",
    "monitoring",
)
MODULE_DEPENDENCY_FLOW = SYSTEM_LAYERS

UNIFIED_CONTRACTS = (
    "data",
    "indicator",
    "event",
    "state_machine",
    "risk",
    "position",
    "execution",
    "backtest",
    "config",
    "logging",
)

OPERATIONAL_SUCCESS_STANDARDS = (
    "stable_signal_generation",
    "stable_open_close_execution",
    "stable_state_and_log_recording",
    "stable_backtest_live_reproduction",
    "stable_probe_direct_position_management",
    "stable_drawdown_control",
    "stable_multi_timeframe_consistency",
    "stable_position_and_order_recovery",
)

IMPLEMENTATION_PRINCIPLES = (
    "contract_first",
    "data_structure_first",
    "backtest_before_live",
    "unit_tests_before_integration",
    "isomorphism_before_optimization",
    "explainability_before_performance",
    "reproducibility_before_extension",
    "stability_before_flashiness",
)

RECOMMENDED_DEVELOPMENT_ORDER = (
    "config_and_data_contract",
    "indicator_layer",
    "multi_timeframe_context",
    "signal_engine",
    "state_machine",
    "risk_engine",
    "position_module",
    "backtest_engine",
    "execution_engine",
    "logging_and_reporting",
    "monitoring_and_recovery",
    "live_integration",
)

FINAL_SYSTEM_TRAITS = (
    "simple_structure",
    "clear_modules",
    "explainable_logic",
    "reproducible_results",
    "backtest_verifiable",
    "live_auditable",
    "low_maintenance_cost",
    "hard_to_lose_control_when_extended",
)

BANNED_FEATURES = (
    "black box model",
    "AI direct decision",
    "complex scorer",
    "multi-layer gate nesting",
    "Watchlist Promotion",
    "weak signal heavy size",
    "complex promotion",
    "execution reinterpret position",
    "low timeframe overrides high timeframe",
    "temporary patch as main strategy",
)

LAYER_ORDER = SYSTEM_LAYERS

SUCCESS_CRITERIA = {
    "annual_return_gt": 0.30,
    "max_drawdown_lt": 0.20,
    "profit_factor_gt": 1.5,
    "sharpe_gt": 1.5,
    "win_rate_min": 0.40,
    "win_rate_max": 0.60,
    "reward_risk_gt": 2.0,
}


def validate_feature_allowed(feature_name: str) -> tuple[bool, str]:
    normalized = feature_name.casefold()
    for banned in BANNED_FEATURES:
        if banned.casefold() in normalized or normalized in banned.casefold():
            return False, f"{banned} is banned by project overview"
    return True, "allowed"


def validate_timeframe_role(timeframe: str, role: str) -> ProjectSpecCheck:
    expected = TIMEFRAME_ROLES.get(timeframe)
    if expected is None:
        return ProjectSpecCheck(False, f"unknown timeframe: {timeframe}")
    if expected != role:
        return ProjectSpecCheck(False, f"{timeframe} role must be {expected}, got {role}")
    return ProjectSpecCheck(True, "timeframe role approved")


def validate_entry_form(entry_form: str) -> ProjectSpecCheck:
    normalized = entry_form.upper()
    if normalized not in ENTRY_FORMS:
        return ProjectSpecCheck(False, f"{entry_form} is not an allowed entry form")
    return ProjectSpecCheck(True, "entry form approved")
```

- [ ] **Step 4: Run project-spec tests**

Run:

```powershell
pytest tests\test_project_spec.py -q
```

Expected: all tests in `tests/test_project_spec.py` pass.

- [ ] **Step 5: Commit**

```powershell
git add src\core\project_spec.py tests\test_project_spec.py
git commit -m "feat: expand project overview contract"
```

Expected: commit succeeds and no Binance client file is staged.

---

### Task 3: Align Module Structure And Dependency Flow

**Files:**

- Modify: `src/core/module_spec.py`
- Modify: `tests/test_python_module_spec.py`

- [ ] **Step 1: Write failing module-spec tests**

Update `tests/test_python_module_spec.py` to expect the expanded structure:

```python
def test_final_module_structure_includes_observability_and_deployment():
    assert FINAL_MODULE_STRUCTURE == [
        "config",
        "data",
        "indicators",
        "context",
        "signals",
        "state_machine",
        "risk",
        "execution",
        "portfolio",
        "backtest",
        "reporting",
        "observability",
        "deployment",
        "utils",
    ]
    assert LAYER_RESPONSIBILITIES["observability"] == ["logging", "metrics", "monitoring"]
    assert LAYER_RESPONSIBILITIES["deployment"] == ["startup", "shutdown", "recovery", "release_gates"]


def test_dependency_chain_matches_project_overview_flow_with_position_bridge():
    assert ALLOWED_DEPENDENCY_CHAIN == [
        "data",
        "indicators",
        "context",
        "signals",
        "state_machine",
        "risk",
        "position_sizing",
        "execution",
        "backtest",
        "reporting",
        "monitoring",
    ]
    assert validate_dependency("risk", "position_sizing") == ModuleSpecCheck(True, "dependency approved")
    assert validate_dependency("position_sizing", "execution") == ModuleSpecCheck(True, "dependency approved")
    assert validate_dependency("execution", "signals").passed is False
    assert validate_dependency("monitoring", "execution").passed is False
```

- [ ] **Step 2: Run module-spec tests and confirm they fail**

Run:

```powershell
pytest tests\test_python_module_spec.py -q
```

Expected: FAIL because the structure and dependency chain are still old.

- [ ] **Step 3: Update module structure and responsibilities**

In `src/core/module_spec.py`, update these constants:

```python
FINAL_MODULE_STRUCTURE = [
    "config",
    "data",
    "indicators",
    "context",
    "signals",
    "state_machine",
    "risk",
    "execution",
    "portfolio",
    "backtest",
    "reporting",
    "observability",
    "deployment",
    "utils",
]

LAYER_RESPONSIBILITIES = {
    "config": ["load_config", "validate_config", "freeze_config"],
    "data": ["fetch_data", "cache_data", "normalize_data"],
    "indicators": ["calculate_indicators", "output_results"],
    "context": ["multi_timeframe_market_state"],
    "signals": ["generate_entry_signal"],
    "state_machine": ["state_management"],
    "risk": ["risk_control", "stop_loss", "take_profit", "cooldown"],
    "execution": ["execute_approved_intent", "order_lifecycle", "position_sync"],
    "portfolio": ["account_management", "portfolio_risk", "position_sync"],
    "backtest": ["backtest", "statistics", "performance_analysis"],
    "reporting": ["html_report", "csv_export", "excel_export"],
    "observability": ["logging", "metrics", "monitoring"],
    "deployment": ["startup", "shutdown", "recovery", "release_gates"],
    "utils": ["time_helpers", "file_helpers", "config_helpers"],
}

ALLOWED_DEPENDENCY_CHAIN = [
    "data",
    "indicators",
    "context",
    "signals",
    "state_machine",
    "risk",
    "position_sizing",
    "execution",
    "backtest",
    "reporting",
    "monitoring",
]

CONCEPTUAL_LAYER_IMPLEMENTATIONS = {
    "position_sizing": "src/risk/position_sizer.py",
    "monitoring": "src/observability/logging_metrics.py",
    "deployment": "src/deployment/deployment_architecture.py",
}
```

Keep `validate_module_structure("src")` checking real directories through `FINAL_MODULE_STRUCTURE`. Do not add a `position_sizing` directory because the current implementation lives in `src/risk/position_sizer.py`.

- [ ] **Step 4: Update dependency validation for monitoring aliases**

In `validate_dependency()`, normalize conceptual aliases before index checks:

```python
DEPENDENCY_ALIASES = {
    "observability": "monitoring",
    "portfolio": "position_sizing",
}


def _normalize_dependency_layer(layer: str) -> str:
    return DEPENDENCY_ALIASES.get(layer, layer)
```

Then compare normalized layers in `ALLOWED_DEPENDENCY_CHAIN`.

- [ ] **Step 5: Run module-spec tests**

Run:

```powershell
pytest tests\test_python_module_spec.py -q
```

Expected: all module-spec tests pass.

- [ ] **Step 6: Commit**

```powershell
git add src\core\module_spec.py tests\test_python_module_spec.py
git commit -m "feat: align module dependency contract"
```

Expected: commit succeeds.

---

### Task 4: Expand The Project Describe Script

**Files:**

- Modify: `scripts/describe_project_rules.py`
- Modify: `tests/test_describe_project_rules.py`

- [ ] **Step 1: Write failing describe-script tests**

Add this test to `tests/test_describe_project_rules.py`:

```python
def test_describe_project_rules_outputs_expanded_project_overview_contract():
    result = subprocess.run(
        [sys.executable, "scripts/describe_project_rules.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    project = payload["project"]

    assert project["name"] == "多周期主流虚拟币趋势交易系统"
    assert project["english_name"] == "crypto-mtf-trend-strategy"
    assert project["timeframe_roles"]["4h"] == "background_reference_only"
    assert project["entry_forms"]["PROBE"]["size_ratio"] == 0.25
    assert project["system_layers"][-1] == "monitoring"
    assert project["module_dependency_flow"] == project["system_layers"]
    assert project["unified_contracts"] == [
        "data",
        "indicator",
        "event",
        "state_machine",
        "risk",
        "position",
        "execution",
        "backtest",
        "config",
        "logging",
    ]
    assert project["implementation_principles"][0] == "contract_first"
    assert "stable_position_and_order_recovery" in project["operational_success_standards"]
```

- [ ] **Step 2: Run describe-script tests and confirm they fail**

Run:

```powershell
pytest tests\test_describe_project_rules.py -q
```

Expected: FAIL because `describe_project_rules.py` does not export the expanded project contract.

- [ ] **Step 3: Import the expanded project constants**

Update `scripts/describe_project_rules.py` imports from `src.core.project_spec`:

```python
from src.core.project_spec import (
    BACKTEST_GOALS,
    CORE_DESIGN_GOALS,
    CORE_TIMEFRAMES,
    ENTRY_FORMS,
    FINAL_SYSTEM_TRAITS,
    IMPLEMENTATION_PRINCIPLES,
    INDICATOR_RESPONSIBILITIES as PROJECT_INDICATOR_RESPONSIBILITIES,
    LIVE_TRADING_GOALS,
    MODULE_DEPENDENCY_FLOW,
    OPERATIONAL_SUCCESS_STANDARDS,
    POSITION_GOALS,
    PROJECT_ENGLISH_NAME,
    PROJECT_NAME,
    PROJECT_NON_GOALS,
    PROJECT_OBJECTIVE,
    PROJECT_PRIORITY,
    RECOMMENDED_DEVELOPMENT_ORDER,
    REFERENCE_TIMEFRAMES,
    RISK_GOALS,
    SUCCESS_CRITERIA,
    SYSTEM_LAYERS,
    TIMEFRAME_ROLES as PROJECT_TIMEFRAME_ROLES,
    TRADING_DECISION_PRINCIPLES,
    TRADING_VENUE,
    UNIFIED_CONTRACTS,
)
```

- [ ] **Step 4: Expand the `project` JSON payload**

Replace the current `"project"` dictionary with:

```python
"project": {
    "name": PROJECT_NAME,
    "english_name": PROJECT_ENGLISH_NAME,
    "objective": PROJECT_OBJECTIVE,
    "priority": PROJECT_PRIORITY,
    "trading_venue": TRADING_VENUE,
    "core_design_goals": CORE_DESIGN_GOALS,
    "core_timeframes": CORE_TIMEFRAMES,
    "reference_timeframes": REFERENCE_TIMEFRAMES,
    "timeframe_roles": PROJECT_TIMEFRAME_ROLES,
    "indicator_responsibilities": PROJECT_INDICATOR_RESPONSIBILITIES,
    "trading_decision_principles": TRADING_DECISION_PRINCIPLES,
    "entry_forms": ENTRY_FORMS,
    "non_goals": PROJECT_NON_GOALS,
    "risk_goals": RISK_GOALS,
    "position_goals": POSITION_GOALS,
    "backtest_goals": BACKTEST_GOALS,
    "live_trading_goals": LIVE_TRADING_GOALS,
    "system_layers": SYSTEM_LAYERS,
    "module_dependency_flow": MODULE_DEPENDENCY_FLOW,
    "unified_contracts": UNIFIED_CONTRACTS,
    "operational_success_standards": OPERATIONAL_SUCCESS_STANDARDS,
    "implementation_principles": IMPLEMENTATION_PRINCIPLES,
    "recommended_development_order": RECOMMENDED_DEVELOPMENT_ORDER,
    "final_system_traits": FINAL_SYSTEM_TRAITS,
    "success_criteria": SUCCESS_CRITERIA,
},
```

- [ ] **Step 5: Run describe-script tests**

Run:

```powershell
pytest tests\test_describe_project_rules.py -q
```

Expected: all describe-script tests pass.

- [ ] **Step 6: Manually inspect describe output**

Run:

```powershell
python scripts\describe_project_rules.py
```

Expected: valid JSON that includes `project.name`, `project.timeframe_roles`, `project.entry_forms`, and `project.unified_contracts`.

- [ ] **Step 7: Commit**

```powershell
git add scripts\describe_project_rules.py tests\test_describe_project_rules.py
git commit -m "feat: describe expanded project overview"
```

Expected: commit succeeds.

---

### Task 5: Sync Scaffold Templates

**Files:**

- Modify: `scripts/scaffold_ai300_framework.py`
- Modify: `tests/test_framework_scaffold.py`

- [ ] **Step 1: Write failing scaffold tests**

Add assertions to `tests/test_framework_scaffold.py` that run the scaffold in a temporary copy or inspect template content, matching the existing test style in that file. The test must verify:

```python
def test_scaffold_templates_include_expanded_project_contract():
    content = Path("scripts/scaffold_ai300_framework.py").read_text(encoding="utf-8")
    assert "PROJECT_NAME = \"多周期主流虚拟币趋势交易系统\"" in content
    assert "\"background_reference_only\"" in content
    assert "\"position_sizing\"" in content
    assert "\"monitoring\"" in content
    assert "stable_position_and_order_recovery" in content


def test_scaffold_still_protects_binance_client():
    content = Path("scripts/scaffold_ai300_framework.py").read_text(encoding="utf-8")
    assert "src/api/binance_client.py" in content
    assert "scaffold must not modify src/binance_client.py" in content
```

- [ ] **Step 2: Run scaffold tests and confirm they fail**

Run:

```powershell
pytest tests\test_framework_scaffold.py -q
```

Expected: FAIL because scaffold templates still include the older project contract.

- [ ] **Step 3: Update scaffold templates**

In `scripts/scaffold_ai300_framework.py`, update the string templates for:

- `src/core/project_spec.py`
- `src/core/module_spec.py`
- `scripts/describe_project_rules.py`
- `tests/test_project_spec.py`
- `tests/test_python_module_spec.py`
- `tests/test_describe_project_rules.py`

The template content must match the implemented files from Tasks 2 through 4. Preserve:

```python
PROTECTED = {ROOT / "src" / "binance_client.py", ROOT / "src" / "api" / "binance_client.py"}
```

and:

```python
if target in PROTECTED:
    raise RuntimeError("scaffold must not modify src/binance_client.py")
```

- [ ] **Step 4: Run scaffold tests**

Run:

```powershell
pytest tests\test_framework_scaffold.py -q
```

Expected: scaffold tests pass.

- [ ] **Step 5: Commit**

```powershell
git add scripts\scaffold_ai300_framework.py tests\test_framework_scaffold.py
git commit -m "chore: sync scaffold project overview templates"
```

Expected: commit succeeds.

---

### Task 6: Final Verification

**Files:**

- No planned source edits.

- [ ] **Step 1: Run targeted contract tests**

Run:

```powershell
pytest tests\test_project_spec.py tests\test_python_module_spec.py tests\test_describe_project_rules.py tests\test_framework_scaffold.py -q
```

Expected: all targeted tests pass.

- [ ] **Step 2: Run the full test suite**

Run:

```powershell
pytest -q
```

Expected: full suite passes.

- [ ] **Step 3: Compile Python files**

Run:

```powershell
python -m compileall src scripts tests
```

Expected: compile succeeds without syntax errors.

- [ ] **Step 4: Verify the describe script emits valid JSON**

Run:

```powershell
python scripts\describe_project_rules.py | python -m json.tool > $env:TEMP\ai300_project_rules.json
Get-Content $env:TEMP\ai300_project_rules.json -TotalCount 20
```

Expected: formatted JSON begins with a top-level object containing `philosophy`, `project`, and `universe`.

- [ ] **Step 5: Verify the stable Binance client was not modified**

Run:

```powershell
git diff -- src\api\binance_client.py
```

Expected: no output.

- [ ] **Step 6: Check changed files**

Run:

```powershell
git status --short
```

Expected: changed files are limited to:

- `docs/00_project_overview.md`
- `src/core/project_spec.py`
- `tests/test_project_spec.py`
- `src/core/module_spec.py`
- `tests/test_python_module_spec.py`
- `scripts/describe_project_rules.py`
- `tests/test_describe_project_rules.py`
- `scripts/scaffold_ai300_framework.py`
- `tests/test_framework_scaffold.py`

If unrelated files appear, do not revert them automatically. Report them as pre-existing or user-created changes unless the task itself modified them.

---

## Non-Goals

- Do not run a backtest as part of this plan.
- Do not tune strategy parameters.
- Do not modify signal generation logic.
- Do not modify risk calculation behavior.
- Do not modify live order submission behavior.
- Do not modify `src/api/binance_client.py`.
- Do not introduce new dependencies.

---

## Completion Criteria

The task is complete when:

- `docs/00_project_overview.md` is clean markdown.
- Project overview constants cover all major sections of `00`.
- Module spec matches the full system boundary and one-way dependency flow.
- `scripts/describe_project_rules.py` exports the expanded overview contract.
- Scaffold templates cannot reintroduce the old contract.
- Targeted tests pass.
- Full tests pass.
- `git diff -- src\api\binance_client.py` has no output.

