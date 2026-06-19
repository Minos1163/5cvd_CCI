# Deployment Architecture Scripts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the section 20 deployment architecture contract scripts so deployment environments, startup/shutdown checks, protection mode, release gates, rollback requirements, and observability rules are testable without touching live trading.

**Architecture:** Add a new local contract module under `src/deployment/deployment_architecture.py` with constants, dataclasses, and pure validation helpers. The module will not start processes, connect to exchanges, mutate production config, or import `src.api.binance_client`; it only evaluates deployment readiness and safety policy from supplied snapshots.

**Tech Stack:** Python dataclasses, standard library mappings/lists, pytest, JSON describe script, existing scaffold dictionary pattern.

---

### Task 1: Deployment Architecture Contract and Safety Helpers

**Files:**
- Create: `src/deployment/__init__.py`
- Create: `src/deployment/deployment_architecture.py`
- Create: `tests/test_deployment_architecture.py`

- [ ] **Step 1: Write failing contract tests**

Create `tests/test_deployment_architecture.py` with:

```python
from src.deployment.deployment_architecture import (
    DEPLOYMENT_ENVIRONMENTS,
    DEPLOYMENT_LAYERS,
    DEPLOYMENT_PROCESS_UNITS,
    DEPLOYMENT_TARGETS,
    CONFIG_FILES,
    SECRET_POLICY,
    LOG_DIRECTORIES,
    STARTUP_SEQUENCE,
    SHUTDOWN_SEQUENCE,
    RECOVERY_STATE_FIELDS,
    FAILURE_MODES,
    PROTECTION_MODE_ALLOWED_ACTIONS,
    PROTECTION_MODE_TRIGGERS,
    MONITORING_METRICS,
    HEALTH_CHECKS,
    HEALTH_CHECK_TYPES,
    VERSION_SNAPSHOT_FIELDS,
    RELEASE_GATES,
    ROLLBACK_REQUIREMENTS,
    CANARY_STAGES,
    DEPLOYMENT_TEST_REQUIREMENTS,
    DEPLOYMENT_FORBIDDEN_PATTERNS,
    DeploymentPlan,
    HealthSnapshot,
    build_version_snapshot,
    evaluate_deployment_readiness,
    evaluate_health_snapshot,
    should_enter_protection_mode,
    validate_environment_isolation,
    validate_release_gates,
    validate_rollback_plan,
)


def test_deployment_contract_lists_doc_sections():
    assert DEPLOYMENT_ENVIRONMENTS == ["development", "staging", "production"]
    assert DEPLOYMENT_LAYERS == [
        "data layer",
        "indicator layer",
        "context layer",
        "signal layer",
        "risk layer",
        "execution layer",
        "portfolio layer",
        "backtest layer",
        "reporting layer",
        "monitoring layer",
    ]
    assert DEPLOYMENT_PROCESS_UNITS == [
        "market data daemon",
        "strategy engine",
        "execution engine",
        "risk supervisor",
        "portfolio sync daemon",
        "backtest runner",
        "report generator",
        "health monitor",
    ]
    assert STARTUP_SEQUENCE[0] == "load_config"
    assert STARTUP_SEQUENCE[-1] == "enter_trading_runtime"
    assert SHUTDOWN_SEQUENCE[0] == "stop_accepting_new_signals"
    assert "database_not_writable" in PROTECTION_MODE_TRIGGERS
    assert "database_connection" in HEALTH_CHECKS
    assert "direct_development_to_production" in DEPLOYMENT_FORBIDDEN_PATTERNS


def test_environment_isolation_rejects_shared_live_config_or_secret_files():
    plan = DeploymentPlan(
        environment="production",
        config_profile="dev",
        uses_live_exchange=False,
        uses_testnet=False,
        config_files=["strategy.yaml", "risk.yaml"],
        secret_sources=["plain_config_file"],
        enabled_processes=["strategy engine"],
        startup_checks=["load_config"],
        release_gates=["local_unit_tests"],
        rollback_items=["code_version"],
    )
    result = validate_environment_isolation(plan)
    assert result.passed is False
    assert "production must use production config profile" in result.errors
    assert "production cannot use plain config file secrets" in result.errors
    assert "production must use live exchange" in result.errors


def test_readiness_requires_all_startup_checks_release_gates_and_rollback_items():
    plan = valid_plan()
    result = evaluate_deployment_readiness(plan)
    assert result.passed is True
    assert result.protection_mode is False

    missing = valid_plan(startup_checks=["load_config"])
    failed = evaluate_deployment_readiness(missing)
    assert failed.passed is False
    assert "missing startup checks" in failed.errors[0]


def test_health_snapshot_enters_protection_mode_on_runtime_failures():
    snapshot = HealthSnapshot(
        database_writable=False,
        exchange_connected=True,
        market_data_fresh=True,
        event_bus_available=True,
        position_sync_ok=True,
        risk_state_ok=True,
        config_valid=True,
        critical_processes_alive=True,
        consecutive_rejects=0,
        consecutive_sync_failures=0,
        consecutive_protection_failures=0,
        abnormal_position_state=False,
        unknown_order_state=False,
        latency_ms={"market_data": 100},
    )
    result = evaluate_health_snapshot(snapshot)
    assert result.passed is False
    assert result.protection_mode is True
    assert "database_not_writable" in result.errors
    assert should_enter_protection_mode(snapshot).passed is True


def test_version_release_and_rollback_contracts_are_explicit():
    snapshot = build_version_snapshot(
        code_version="abc",
        strategy_version="s1",
        risk_version="r1",
        config_version="c1",
        data_version="d1",
        backtest_version="b1",
        report_version="rp1",
    )
    assert list(snapshot) == VERSION_SNAPSHOT_FIELDS
    assert validate_release_gates(RELEASE_GATES).passed is True
    assert validate_rollback_plan(ROLLBACK_REQUIREMENTS).passed is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_deployment_architecture.py -q`

Expected: FAIL because the new deployment module does not exist.

- [ ] **Step 3: Implement deployment contract module**

Create `src/deployment/__init__.py`:

```python
"""Deployment architecture contracts and safety checks."""
```

Create `src/deployment/deployment_architecture.py` with:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


DEPLOYMENT_ENVIRONMENTS = ["development", "staging", "production"]
DEPLOYMENT_LAYERS = [...]
DEPLOYMENT_PROCESS_UNITS = [...]
DEPLOYMENT_TARGETS = [...]
CONFIG_FILES = [...]
SECRET_POLICY = {...}
LOG_DIRECTORIES = [...]
STARTUP_SEQUENCE = [...]
SHUTDOWN_SEQUENCE = [...]
RECOVERY_STATE_FIELDS = [...]
FAILURE_MODES = [...]
PROTECTION_MODE_ALLOWED_ACTIONS = [...]
PROTECTION_MODE_TRIGGERS = [...]
MONITORING_METRICS = [...]
OBSERVABILITY_QUESTIONS = [...]
CONTAINER_SERVICES = [...]
HEALTH_CHECKS = [...]
HEALTH_CHECK_TYPES = ["liveness", "readiness", "startup"]
VERSION_SNAPSHOT_FIELDS = [...]
RELEASE_GATES = [...]
ROLLBACK_REQUIREMENTS = [...]
CANARY_STAGES = [...]
CANARY_OBSERVATION_METRICS = [...]
DEPLOYMENT_TEST_REQUIREMENTS = [...]
DEPLOYMENT_FORBIDDEN_PATTERNS = [...]
IMPLEMENTATION_ORDER = [...]
BINANCE_CLIENT_POLICY = "deployment contract only; do not import or modify stable Binance client"


@dataclass(frozen=True)
class DeploymentCheckResult:
    passed: bool
    errors: list[str]
    warnings: list[str]
    protection_mode: bool = False


@dataclass(frozen=True)
class DeploymentPlan:
    environment: str
    config_profile: str
    uses_live_exchange: bool
    uses_testnet: bool
    config_files: list[str]
    secret_sources: list[str]
    enabled_processes: list[str]
    startup_checks: list[str]
    release_gates: list[str]
    rollback_items: list[str]


@dataclass(frozen=True)
class HealthSnapshot:
    database_writable: bool
    exchange_connected: bool
    market_data_fresh: bool
    event_bus_available: bool
    position_sync_ok: bool
    risk_state_ok: bool
    config_valid: bool
    critical_processes_alive: bool
    consecutive_rejects: int = 0
    consecutive_sync_failures: int = 0
    consecutive_protection_failures: int = 0
    abnormal_position_state: bool = False
    unknown_order_state: bool = False
    latency_ms: Mapping[str, int] | None = None
```

Implement:

- `validate_environment_isolation(plan)`
- `validate_release_gates(gates)`
- `validate_rollback_plan(items)`
- `evaluate_health_snapshot(snapshot)`
- `should_enter_protection_mode(snapshot, threshold=3)`
- `evaluate_deployment_readiness(plan)`
- `build_version_snapshot(...)`

Rules:

- Production requires `config_profile == "production"`, `uses_live_exchange is True`, `uses_testnet is False`, no `plain_config_file` secret source, all `CONFIG_FILES`, all `DEPLOYMENT_PROCESS_UNITS`, all `STARTUP_SEQUENCE`, all `RELEASE_GATES`, and all `ROLLBACK_REQUIREMENTS`.
- Staging requires `config_profile == "staging"` and either testnet or non-live exchange.
- Development must not use live exchange.
- Health failure on database, exchange, market data, event bus, position sync, risk state, config, process liveness, consecutive failures, abnormal position, or unknown order state triggers protection mode.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_deployment_architecture.py -q`

Expected: PASS.

### Task 2: Describe Script and Scaffold Sync

**Files:**
- Create: `scripts/describe_deployment_architecture.py`
- Create: `tests/test_describe_deployment_architecture.py`
- Modify: `scripts/scaffold_ai300_framework.py`
- Modify: `tests/test_framework_scaffold.py`

- [ ] **Step 1: Write failing describe and scaffold tests**

Create `tests/test_describe_deployment_architecture.py`:

```python
import json
import subprocess
import sys


def test_describe_deployment_architecture_outputs_completed_20_sections():
    result = subprocess.run(
        [sys.executable, "scripts/describe_deployment_architecture.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    assert payload["architecture"] == "deployment_architecture"
    assert payload["environments"] == ["development", "staging", "production"]
    assert payload["startup_sequence"][0] == "load_config"
    assert payload["shutdown_sequence"][0] == "stop_accepting_new_signals"
    assert "database_not_writable" in payload["protection_mode_triggers"]
    assert payload["health_check_types"] == ["liveness", "readiness", "startup"]
    assert "local_unit_tests" in payload["release_gates"]
    assert "code_version" in payload["rollback_requirements"]
    assert "direct_development_to_production" in payload["forbidden_patterns"]
    assert payload["binance_client_policy"] == "deployment contract only; do not import or modify stable Binance client"
    assert payload["sample_readiness"]["passed"] is True
```

Append to `tests/test_framework_scaffold.py`:

```python
def test_scaffold_includes_deployment_architecture_20_templates():
    assert "src/deployment/deployment_architecture.py" in FILES
    assert "scripts/describe_deployment_architecture.py" in FILES
    assert "tests/test_deployment_architecture.py" in FILES
    assert "tests/test_describe_deployment_architecture.py" in FILES
    assert "DeploymentPlan" in FILES["src/deployment/deployment_architecture.py"]
    assert "PROTECTION_MODE_TRIGGERS" in FILES["src/deployment/deployment_architecture.py"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_describe_deployment_architecture.py tests/test_framework_scaffold.py -q`

Expected: FAIL because the describe script and scaffold templates do not exist.

- [ ] **Step 3: Implement describe script**

Create `scripts/describe_deployment_architecture.py` that imports the deployment constants and prints JSON including:

- `architecture`
- `environments`
- `layers`
- `process_units`
- `deployment_targets`
- `config_files`
- `secret_policy`
- `log_directories`
- `startup_sequence`
- `shutdown_sequence`
- `recovery_state_fields`
- `failure_modes`
- `protection_mode_allowed_actions`
- `protection_mode_triggers`
- `monitoring_metrics`
- `observability_questions`
- `container_services`
- `health_checks`
- `health_check_types`
- `version_snapshot_fields`
- `release_gates`
- `rollback_requirements`
- `canary_stages`
- `canary_observation_metrics`
- `deployment_test_requirements`
- `forbidden_patterns`
- `implementation_order`
- `binance_client_policy`
- `sample_readiness`

- [ ] **Step 4: Sync scaffold templates**

Update `scripts/scaffold_ai300_framework.py` `FILES` with:

- `src/deployment/__init__.py`
- `src/deployment/deployment_architecture.py`
- `scripts/describe_deployment_architecture.py`
- `tests/test_deployment_architecture.py`
- `tests/test_describe_deployment_architecture.py`

Use compact templates with the same public names. Do not add or modify any Binance client template.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_describe_deployment_architecture.py tests/test_framework_scaffold.py -q`

Expected: PASS.

### Task 3: Final Verification and Cache Cleanup

**Files:**
- No edits expected unless verification exposes a defect.

- [ ] **Step 1: Run targeted verification**

Run:

```powershell
pytest tests\test_deployment_architecture.py tests\test_describe_deployment_architecture.py tests\test_framework_scaffold.py -q
```

Expected: PASS.

- [ ] **Step 2: Run full verification**

Run:

```powershell
pytest -q
python -m compileall src scripts tests
python scripts\describe_deployment_architecture.py
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
- Environments, layers, process units, data/state flow proxies, config/secret/log policy, database/recovery constraints, backtest/live deployment separation, startup/shutdown, failure modes, protection mode, monitoring, health checks, versioning, release, rollback, canary, tests, forbidden patterns, and implementation order are covered.
- This plan intentionally does not create real process managers, containers, database connections, or exchange connectivity. It creates local contract and readiness checks only.

Placeholder scan:
- No TBD/TODO/fill-later placeholders remain.

Type consistency:
- `DeploymentPlan`, `HealthSnapshot`, `DeploymentCheckResult`, and helper names are used consistently across tests, implementation, and describe script.
