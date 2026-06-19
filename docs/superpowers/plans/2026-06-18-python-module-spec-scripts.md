# Python Module Specification Scripts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the scripts required by `docs/13_python_module_spec.md`.

**Architecture:** Add a pure module-boundary contract under `src/core/module_spec.py` that defines final layer order, responsibilities, forbidden cross-layer behavior, base protocol interfaces, DTO/context records, event names, engine names, and dependency validation. Preserve existing modules and add only missing boundary packages/stubs where needed; do not refactor strategy, risk, execution, or Binance code.

**Tech Stack:** Python standard library, dataclasses, typing.Protocol, pytest.

---

## Scope Notes

`docs/13_python_module_spec.md` requires:

- Final module structure: config, data, indicators, context, signals, state_machine, risk, execution, portfolio, backtest, reporting, utils.
- No cross-layer overreach, circular dependency, or universal utility classes.
- Layer responsibilities and allowed outputs for context/signals/state machine.
- Allowed dependency direction: data -> indicators -> context -> signals -> state_machine -> risk -> execution.
- Explicit forbidden reverse dependencies: execution must not call signal; risk must not call backtest.
- Unified base interfaces: `BaseSignal.generate`, `BaseIndicator.calculate`, `BaseRiskModel.evaluate`, `BaseExecution.submit/cancel/sync`.
- Engine names: market/signal/risk/execution/report.
- `StrategyContext`, EventBus events, and DTO objects.
- Recommended file names for signals, risk, execution, backtest, and reporting.

This plan implements deterministic contracts and validators. It does not migrate all existing modules to subclass protocols, scan Python import ASTs, create a real event bus dispatcher, or add live portfolio behavior.

## File Structure

- Create: `src/core/module_spec.py` - module layer constants, responsibilities, protocols, DTO/context/event contracts, dependency validators, and recommended file lists.
- Create: `src/portfolio/__init__.py` - package boundary required by final structure.
- Create: `scripts/describe_python_module_spec.py` - prints the completed 13 module contract as JSON.
- Create: `tests/test_python_module_spec.py` - tests layer structure, dependency rules, base protocols, DTO/context, event names, and recommended files.
- Create: `tests/test_describe_python_module_spec.py` - tests describe script JSON output.
- Modify: `scripts/scaffold_ai300_framework.py` - sync templates for the new module, package, script, and tests.
- Preserve: `src/api/binance_client.py` - do not modify the stable Binance client.

---

### Task 1: Module Layers, Responsibilities, and Dependency Rules

**Files:**

- Create: `src/core/module_spec.py`
- Create: `src/portfolio/__init__.py`
- Create: `tests/test_python_module_spec.py`

- [ ] **Step 1: Write failing tests for layers and dependency validation**

Create `tests/test_python_module_spec.py`:

```python
from src.core.module_spec import (
    ALLOWED_DEPENDENCY_CHAIN,
    FINAL_MODULE_STRUCTURE,
    FORBIDDEN_MODULE_PATTERNS,
    LAYER_RESPONSIBILITIES,
    ModuleSpecCheck,
    validate_dependency,
    validate_module_structure,
)


def test_final_module_structure_and_responsibilities_match_doc():
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
        "utils",
    ]
    assert LAYER_RESPONSIBILITIES["data"] == ["fetch_data", "cache_data", "normalize_data"]
    assert LAYER_RESPONSIBILITIES["indicators"] == ["calculate_indicators", "output_results"]
    assert LAYER_RESPONSIBILITIES["context"] == ["multi_timeframe_market_state"]
    assert LAYER_RESPONSIBILITIES["execution"] == ["call_binance_client"]
    assert LAYER_RESPONSIBILITIES["portfolio"] == ["account_management", "portfolio_risk", "position_sync"]
    assert FORBIDDEN_MODULE_PATTERNS == ["cross_layer_overreach", "circular_dependency", "god_utility_class"]


def test_dependency_chain_allows_forward_flow_and_rejects_reverse_flow():
    assert ALLOWED_DEPENDENCY_CHAIN == ["data", "indicators", "context", "signals", "state_machine", "risk", "execution"]
    assert validate_dependency("data", "indicators") == ModuleSpecCheck(True, "dependency approved")
    assert validate_dependency("signals", "risk") == ModuleSpecCheck(True, "dependency approved")
    assert validate_dependency("execution", "signals").passed is False
    assert validate_dependency("risk", "backtest").passed is False


def test_validate_module_structure_accepts_current_src_directories():
    assert validate_module_structure("src").passed is True
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_python_module_spec.py -q`

Expected: FAIL because `src.core.module_spec` does not exist.

- [ ] **Step 3: Implement module constants and validators**

Create `src/portfolio/__init__.py`:

```python
"""Portfolio account, exposure, and position synchronization boundary."""
```

Create `src/core/module_spec.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


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
    "utils",
]
FORBIDDEN_MODULE_PATTERNS = ["cross_layer_overreach", "circular_dependency", "god_utility_class"]
LAYER_RESPONSIBILITIES = {
    "data": ["fetch_data", "cache_data", "normalize_data"],
    "indicators": ["calculate_indicators", "output_results"],
    "context": ["multi_timeframe_market_state"],
    "signals": ["generate_entry_signal"],
    "state_machine": ["state_management"],
    "risk": ["risk_control", "position_sizing", "stop_loss", "take_profit"],
    "execution": ["call_binance_client"],
    "portfolio": ["account_management", "portfolio_risk", "position_sync"],
    "backtest": ["backtest", "statistics", "performance_analysis"],
    "reporting": ["html_report", "csv_export", "excel_export"],
    "utils": ["time_helpers", "file_helpers", "config_helpers"],
}
ALLOWED_DEPENDENCY_CHAIN = ["data", "indicators", "context", "signals", "state_machine", "risk", "execution"]


@dataclass(frozen=True)
class ModuleSpecCheck:
    passed: bool
    reason: str


def validate_dependency(source_layer: str, target_layer: str) -> ModuleSpecCheck:
    if source_layer == "execution" and target_layer in {"signals", "signal"}:
        return ModuleSpecCheck(False, "execution must not call signal layer")
    if source_layer == "risk" and target_layer == "backtest":
        return ModuleSpecCheck(False, "risk must not call backtest")
    if source_layer in ALLOWED_DEPENDENCY_CHAIN and target_layer in ALLOWED_DEPENDENCY_CHAIN:
        if ALLOWED_DEPENDENCY_CHAIN.index(source_layer) <= ALLOWED_DEPENDENCY_CHAIN.index(target_layer):
            return ModuleSpecCheck(True, "dependency approved")
        return ModuleSpecCheck(False, "reverse dependency is forbidden")
    return ModuleSpecCheck(True, "dependency outside strict chain")


def validate_module_structure(src_root: str | Path) -> ModuleSpecCheck:
    root = Path(src_root)
    missing = [name for name in FINAL_MODULE_STRUCTURE if not (root / name).exists()]
    if missing:
        return ModuleSpecCheck(False, f"missing module directories: {missing}")
    return ModuleSpecCheck(True, "module structure approved")
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_python_module_spec.py -q`

Expected: PASS for layer and dependency tests.

---

### Task 2: Base Protocols, DTOs, StrategyContext, and Events

**Files:**

- Modify: `src/core/module_spec.py`
- Modify: `tests/test_python_module_spec.py`

- [ ] **Step 1: Add failing tests for protocols, DTOs, context, and events**

Append to `tests/test_python_module_spec.py`:

```python
from src.core.module_spec import (
    BASE_INTERFACE_METHODS,
    CONTEXT_STATES,
    ENGINE_NAMES,
    EVENT_TYPES,
    SIGNAL_OUTPUTS,
    STATE_MACHINE_STATES,
    BaseExecution,
    BaseIndicator,
    BaseRiskModel,
    BaseSignal,
    DTO,
    StrategyContext,
)


class ExampleSignal:
    def generate(self, context):
        return "WAIT"


class ExampleIndicator:
    def calculate(self, candles):
        return {"value": 1}


class ExampleRisk:
    def evaluate(self, signal, context):
        return {"approved": True}


class ExampleExecution:
    def submit(self, instruction):
        return {"status": "submitted"}

    def cancel(self, order_id):
        return {"status": "canceled"}

    def sync(self):
        return {"status": "synced"}


def test_base_protocols_are_runtime_checkable_by_required_methods():
    assert isinstance(ExampleSignal(), BaseSignal)
    assert isinstance(ExampleIndicator(), BaseIndicator)
    assert isinstance(ExampleRisk(), BaseRiskModel)
    assert isinstance(ExampleExecution(), BaseExecution)
    assert BASE_INTERFACE_METHODS == {
        "BaseSignal": ["generate"],
        "BaseIndicator": ["calculate"],
        "BaseRiskModel": ["evaluate"],
        "BaseExecution": ["submit", "cancel", "sync"],
    }


def test_context_signal_state_engine_event_and_dto_contracts():
    assert CONTEXT_STATES == ["BULL", "BEAR", "NEUTRAL"]
    assert SIGNAL_OUTPUTS == ["LONG", "SHORT", "WAIT"]
    assert STATE_MACHINE_STATES == ["FLAT", "WATCH", "PROBE", "DIRECT", "MANAGE", "EXIT"]
    assert ENGINE_NAMES == ["market_engine", "signal_engine", "risk_engine", "execution_engine", "report_engine"]
    assert EVENT_TYPES == ["SIGNAL_CREATED", "ORDER_FILLED", "STOP_HIT", "TP_HIT"]
    context = StrategyContext(
        symbol="BTCUSDT",
        timeframe="15m",
        indicators={"macd": 1},
        state="WATCH",
        risk={"risk_per_trade_pct": 0.01},
    )
    dto = DTO(name="SignalDTO", payload={"side": "LONG"})
    assert context.symbol == "BTCUSDT"
    assert dto.payload["side"] == "LONG"
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_python_module_spec.py -q`

Expected: FAIL because protocols and DTO/context constants do not exist.

- [ ] **Step 3: Implement protocols, DTOs, and constants**

Append to `src/core/module_spec.py`:

```python
from typing import runtime_checkable


@runtime_checkable
class BaseSignal(Protocol):
    def generate(self, context: Any) -> Any:
        ...


@runtime_checkable
class BaseIndicator(Protocol):
    def calculate(self, candles: Any) -> Any:
        ...


@runtime_checkable
class BaseRiskModel(Protocol):
    def evaluate(self, signal: Any, context: Any) -> Any:
        ...


@runtime_checkable
class BaseExecution(Protocol):
    def submit(self, instruction: Any) -> Any:
        ...

    def cancel(self, order_id: Any) -> Any:
        ...

    def sync(self) -> Any:
        ...


BASE_INTERFACE_METHODS = {
    "BaseSignal": ["generate"],
    "BaseIndicator": ["calculate"],
    "BaseRiskModel": ["evaluate"],
    "BaseExecution": ["submit", "cancel", "sync"],
}
CONTEXT_STATES = ["BULL", "BEAR", "NEUTRAL"]
SIGNAL_OUTPUTS = ["LONG", "SHORT", "WAIT"]
STATE_MACHINE_STATES = ["FLAT", "WATCH", "PROBE", "DIRECT", "MANAGE", "EXIT"]
ENGINE_NAMES = ["market_engine", "signal_engine", "risk_engine", "execution_engine", "report_engine"]
EVENT_TYPES = ["SIGNAL_CREATED", "ORDER_FILLED", "STOP_HIT", "TP_HIT"]


@dataclass(frozen=True)
class StrategyContext:
    symbol: str
    timeframe: str
    indicators: dict[str, Any]
    state: str
    risk: dict[str, Any]


@dataclass(frozen=True)
class DTO:
    name: str
    payload: dict[str, Any]
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_python_module_spec.py -q`

Expected: PASS.

---

### Task 3: Recommended Files and Describe Script

**Files:**

- Modify: `src/core/module_spec.py`
- Create: `scripts/describe_python_module_spec.py`
- Create: `tests/test_describe_python_module_spec.py`
- Modify: `tests/test_python_module_spec.py`

- [ ] **Step 1: Add failing tests for recommended files and describe script**

Append to `tests/test_python_module_spec.py`:

```python
from src.core.module_spec import RECOMMENDED_FILES, TEST_DIRECTORIES


def test_recommended_files_and_test_directories_match_doc():
    assert RECOMMENDED_FILES["signals"] == ["macd_signal.py", "cci_signal.py", "entry_signal.py"]
    assert RECOMMENDED_FILES["risk"] == ["position_sizer.py", "stop_engine.py", "tp_engine.py", "cooldown_guard.py"]
    assert RECOMMENDED_FILES["execution"] == ["order_manager.py", "position_manager.py", "exchange_adapter.py"]
    assert RECOMMENDED_FILES["backtest"] == ["runner.py", "broker.py", "analyzer.py"]
    assert RECOMMENDED_FILES["reporting"] == ["html_report.py", "csv_exporter.py", "excel_exporter.py"]
    assert TEST_DIRECTORIES == ["tests/unit", "tests/integration", "tests/backtest"]
```

Create `tests/test_describe_python_module_spec.py`:

```python
import json
import subprocess
import sys


def test_describe_python_module_spec_outputs_completed_13_sections():
    completed = subprocess.run(
        [sys.executable, "scripts/describe_python_module_spec.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["final_module_structure"][0] == "config"
    assert payload["allowed_dependency_chain"] == ["data", "indicators", "context", "signals", "state_machine", "risk", "execution"]
    assert payload["base_interfaces"]["BaseExecution"] == ["submit", "cancel", "sync"]
    assert payload["context_states"] == ["BULL", "BEAR", "NEUTRAL"]
    assert payload["event_types"] == ["SIGNAL_CREATED", "ORDER_FILLED", "STOP_HIT", "TP_HIT"]
    assert payload["recommended_files"]["execution"] == ["order_manager.py", "position_manager.py", "exchange_adapter.py"]
    assert payload["final_principle"] == "strategy judges, risk constrains, execution executes"
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_python_module_spec.py tests/test_describe_python_module_spec.py -q`

Expected: FAIL because recommended constants and describe script are missing.

- [ ] **Step 3: Implement recommended constants and describe script**

Append to `src/core/module_spec.py`:

```python
RECOMMENDED_FILES = {
    "signals": ["macd_signal.py", "cci_signal.py", "entry_signal.py"],
    "risk": ["position_sizer.py", "stop_engine.py", "tp_engine.py", "cooldown_guard.py"],
    "execution": ["order_manager.py", "position_manager.py", "exchange_adapter.py"],
    "backtest": ["runner.py", "broker.py", "analyzer.py"],
    "reporting": ["html_report.py", "csv_exporter.py", "excel_exporter.py"],
}
TEST_DIRECTORIES = ["tests/unit", "tests/integration", "tests/backtest"]
FINAL_PRINCIPLE = "strategy judges, risk constrains, execution executes"
```

Create `scripts/describe_python_module_spec.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.module_spec import (
    ALLOWED_DEPENDENCY_CHAIN,
    BASE_INTERFACE_METHODS,
    CONTEXT_STATES,
    ENGINE_NAMES,
    EVENT_TYPES,
    FINAL_MODULE_STRUCTURE,
    FINAL_PRINCIPLE,
    FORBIDDEN_MODULE_PATTERNS,
    LAYER_RESPONSIBILITIES,
    RECOMMENDED_FILES,
    SIGNAL_OUTPUTS,
    STATE_MACHINE_STATES,
    TEST_DIRECTORIES,
)


def main() -> None:
    payload = {
        "final_module_structure": FINAL_MODULE_STRUCTURE,
        "layer_responsibilities": LAYER_RESPONSIBILITIES,
        "forbidden_patterns": FORBIDDEN_MODULE_PATTERNS,
        "allowed_dependency_chain": ALLOWED_DEPENDENCY_CHAIN,
        "base_interfaces": BASE_INTERFACE_METHODS,
        "context_states": CONTEXT_STATES,
        "signal_outputs": SIGNAL_OUTPUTS,
        "state_machine_states": STATE_MACHINE_STATES,
        "engine_names": ENGINE_NAMES,
        "event_types": EVENT_TYPES,
        "recommended_files": RECOMMENDED_FILES,
        "test_directories": TEST_DIRECTORIES,
        "final_principle": FINAL_PRINCIPLE,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_python_module_spec.py tests/test_describe_python_module_spec.py -q`

Expected: PASS.

---

### Task 4: Scaffold Sync and Verification

**Files:**

- Modify: `scripts/scaffold_ai300_framework.py`

- [ ] **Step 1: Sync scaffold templates**

Copy final contents of these files into `scripts/scaffold_ai300_framework.py`:

- `src/core/module_spec.py`
- `src/portfolio/__init__.py`
- `scripts/describe_python_module_spec.py`
- `tests/test_python_module_spec.py`
- `tests/test_describe_python_module_spec.py`

- [ ] **Step 2: Run targeted tests**

Run: `pytest tests/test_python_module_spec.py tests/test_describe_python_module_spec.py tests/test_framework_scaffold.py -q`

Expected: PASS.

- [ ] **Step 3: Run full verification**

Run:

```bash
pytest -q
python -m compileall src scripts tests
python scripts/describe_python_module_spec.py
git diff -- src/api/binance_client.py
```

Expected: all tests pass, compile succeeds, describe JSON includes completed 13 sections, and Binance diff has no output.

- [ ] **Step 4: Clean generated caches**

Run:

```powershell
$root=(Resolve-Path '.').Path; $targets=Get-ChildItem -Path . -Recurse -Directory -Filter '__pycache__' | Where-Object { $_.FullName.StartsWith($root) }; foreach($target in $targets){ Remove-Item -LiteralPath $target.FullName -Recurse -Force }; Get-ChildItem -Path . -Recurse -Directory -Filter '__pycache__' | Select-Object -ExpandProperty FullName
```

Expected: no remaining `__pycache__` directories in the workspace.

---

## Self-Review

- Spec coverage: covers final module structure, data/indicator/context/signal/state/risk/execution/portfolio/backtest/reporting/utils responsibilities, allowed and forbidden dependencies, base interfaces, engine names, StrategyContext, EventBus event names, DTO contract, recommended files, test directories, and final responsibility principle.
- Placeholder scan: no `TBD`, `TODO`, `implement later`, or unspecified test steps.
- Type consistency: `ModuleSpecCheck`, `BaseSignal`, `BaseIndicator`, `BaseRiskModel`, `BaseExecution`, `StrategyContext`, `DTO`, `validate_dependency`, and `validate_module_structure` are named consistently across tasks.
