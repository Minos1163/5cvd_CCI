# Configuration Schema Scripts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the scripts required by `docs/11_config_schema.md`.

**Architecture:** Add a pure configuration schema module under `src/config/config_schema.py` that defines required config files, required top-level sections, required field paths, config precedence, hot-update policy, version requirements, and validation helpers. Keep loading read-only and standard-library-only; do not introduce runtime dependencies or modify trading behavior.

**Tech Stack:** Python standard library, dataclasses, pytest.

---

## Scope Notes

`docs/11_config_schema.md` requires:

- Config files under `configs/`: `strategy.yaml`, `risk.yaml`, `execution.yaml`, `universe.yaml`, `logging.yaml`, `backtest.yaml`.
- Every config must include `version`.
- Modules read config but must not mutate it.
- Config precedence is default -> environment -> user override.
- Hot updates are allowed for logging and monitoring parameters, but forbidden for strategy core parameters.
- Hard-coded parameters, magic numbers, and duplicate definitions are forbidden.

This plan implements deterministic config contract helpers only. It does not wire every module to read from config, alter strategy logic, introduce a YAML dependency, or add live runtime hot reload.

## File Structure

- Create: `src/config/__init__.py` - package marker.
- Create: `src/config/config_schema.py` - config schema constants, lightweight YAML loader, read-only freeze helper, merge helper, validation, and hot-update policy helpers.
- Create: `scripts/describe_config_schema.py` - prints the 11 config contract as JSON.
- Create: `tests/test_config_schema.py` - tests schema constants, existing config validation, read-only behavior, precedence merge, hot-update policy, and missing version/field rejection.
- Create: `tests/test_describe_config_schema.py` - tests describe script JSON output.
- Modify: `scripts/scaffold_ai300_framework.py` - sync templates for new package, module, script, and tests.
- Preserve: `src/api/binance_client.py` - do not modify the stable Binance client.

---

### Task 1: Schema Constants and Existing Config Validation

**Files:**

- Create: `src/config/__init__.py`
- Create: `src/config/config_schema.py`
- Create: `tests/test_config_schema.py`

- [ ] **Step 1: Write failing tests for config schema constants and existing files**

Create `tests/test_config_schema.py`:

```python
from pathlib import Path

from src.config.config_schema import (
    CONFIG_FILES,
    CONFIG_PRECEDENCE,
    CONFIG_REQUIRED_FIELDS,
    CONFIG_ROOT,
    REQUIRED_TOP_LEVEL_KEYS,
    validate_config_directory,
)


def test_config_schema_lists_required_files_sections_and_precedence():
    assert CONFIG_ROOT == Path("configs")
    assert CONFIG_FILES == [
        "strategy.yaml",
        "risk.yaml",
        "execution.yaml",
        "universe.yaml",
        "logging.yaml",
        "backtest.yaml",
    ]
    assert REQUIRED_TOP_LEVEL_KEYS == {
        "strategy.yaml": ["version", "strategy", "indicators", "entry", "probe"],
        "risk.yaml": ["version", "risk", "stop", "take_profit"],
        "execution.yaml": ["version", "execution", "slippage"],
        "universe.yaml": ["version", "universe"],
        "logging.yaml": ["version", "logging"],
        "backtest.yaml": ["version", "backtest"],
    }
    assert CONFIG_PRECEDENCE == ["default", "environment", "user_override"]
    assert CONFIG_REQUIRED_FIELDS["strategy.yaml"][0] == "version"
    assert "strategy.timeframes.trigger" in CONFIG_REQUIRED_FIELDS["strategy.yaml"]
    assert "risk.risk_per_trade_pct" in CONFIG_REQUIRED_FIELDS["risk.yaml"]
    assert "execution.exchange" in CONFIG_REQUIRED_FIELDS["execution.yaml"]


def test_existing_configs_validate_against_schema():
    result = validate_config_directory(Path("configs"))
    assert result.passed is True
    assert result.errors == []
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_config_schema.py -q`

Expected: FAIL because `src.config.config_schema` does not exist.

- [ ] **Step 3: Implement schema constants, simple YAML loader, and directory validator**

Create `src/config/__init__.py`:

```python
"""Configuration schema and loading helpers."""
```

Create `src/config/config_schema.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any


CONFIG_ROOT = Path("configs")
CONFIG_FILES = [
    "strategy.yaml",
    "risk.yaml",
    "execution.yaml",
    "universe.yaml",
    "logging.yaml",
    "backtest.yaml",
]
CONFIG_PRECEDENCE = ["default", "environment", "user_override"]
REQUIRED_TOP_LEVEL_KEYS = {
    "strategy.yaml": ["version", "strategy", "indicators", "entry", "probe"],
    "risk.yaml": ["version", "risk", "stop", "take_profit"],
    "execution.yaml": ["version", "execution", "slippage"],
    "universe.yaml": ["version", "universe"],
    "logging.yaml": ["version", "logging"],
    "backtest.yaml": ["version", "backtest"],
}
CONFIG_REQUIRED_FIELDS = {
    "strategy.yaml": [
        "version",
        "strategy.name",
        "strategy.timeframes.trigger",
        "strategy.timeframes.confirm",
        "strategy.timeframes.trend",
        "strategy.timeframes.context",
        "indicators.macd.fast",
        "indicators.cci.period",
        "indicators.rsi.period",
        "indicators.boll.period",
        "entry.cci_long",
        "probe.enabled",
        "probe.size_ratio",
    ],
    "risk.yaml": [
        "version",
        "risk.risk_per_trade_pct",
        "risk.daily_loss_limit_pct",
        "risk.weekly_loss_limit_pct",
        "risk.max_drawdown_pct",
        "stop.atr_mult",
        "stop.min_stop_pct",
        "take_profit.tp1_r",
        "take_profit.tp2_r",
        "take_profit.tp3_r",
    ],
    "execution.yaml": [
        "version",
        "execution.exchange",
        "execution.leverage",
        "execution.use_market_order",
        "slippage.base_bps",
        "slippage.high_vol_bps",
    ],
    "universe.yaml": [
        "version",
        "universe.refresh_interval_hours",
        "universe.max_symbols",
    ],
    "logging.yaml": [
        "version",
        "logging.level",
    ],
    "backtest.yaml": [
        "version",
        "backtest.start",
        "backtest.end",
        "backtest.initial_capital",
    ],
}


@dataclass(frozen=True)
class ConfigValidationResult:
    passed: bool
    errors: list[str]


def load_simple_yaml(path: Path) -> dict[str, Any]:
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any] | list[Any]]] = [(-1, root)]
    pending_list_key: tuple[int, str, dict[str, Any]] | None = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()
        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if stripped.startswith("- "):
            if pending_list_key is None:
                raise ValueError(f"list item without key in {path}")
            list_indent, key, owner = pending_list_key
            if not isinstance(owner.get(key), list):
                owner[key] = []
            owner[key].append(_parse_scalar(stripped[2:].strip()))
            stack.append((list_indent, owner[key]))
            continue
        key, _, value = stripped.partition(":")
        key = key.strip()
        value = value.strip()
        if not isinstance(parent, dict):
            raise ValueError(f"nested mapping under list is not supported in {path}")
        if value == "":
            parent[key] = {}
            pending_list_key = (indent, key, parent)
            stack.append((indent, parent[key]))
        else:
            parent[key] = _parse_scalar(value)
            pending_list_key = None
    return root


def _parse_scalar(value: str) -> Any:
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value


def validate_config_directory(config_dir: Path = CONFIG_ROOT) -> ConfigValidationResult:
    errors: list[str] = []
    for filename in CONFIG_FILES:
        path = config_dir / filename
        if not path.exists():
            errors.append(f"missing config file: {filename}")
            continue
        payload = load_simple_yaml(path)
        for key in REQUIRED_TOP_LEVEL_KEYS[filename]:
            if key not in payload:
                errors.append(f"{filename} missing top-level key: {key}")
        for field in CONFIG_REQUIRED_FIELDS[filename]:
            if not has_field(payload, field):
                errors.append(f"{filename} missing required field: {field}")
    return ConfigValidationResult(not errors, errors)


def has_field(payload: dict[str, Any], dotted_path: str) -> bool:
    current: Any = payload
    for part in dotted_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return False
        current = current[part]
    return True
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_config_schema.py -q`

Expected: PASS for constants and existing config validation.

---

### Task 2: Read-Only Config and Precedence Merge

**Files:**

- Modify: `src/config/config_schema.py`
- Modify: `tests/test_config_schema.py`

- [ ] **Step 1: Add failing tests for read-only freeze and precedence merge**

Append to `tests/test_config_schema.py`:

```python
from src.config.config_schema import freeze_config, merge_config_layers


def test_freeze_config_returns_read_only_nested_mapping():
    frozen = freeze_config({"risk": {"risk_per_trade_pct": 0.01}})
    assert frozen["risk"]["risk_per_trade_pct"] == 0.01
    try:
        frozen["risk"] = {}
    except TypeError:
        pass
    else:
        raise AssertionError("top-level config must be read-only")
    try:
        frozen["risk"]["risk_per_trade_pct"] = 0.02
    except TypeError:
        pass
    else:
        raise AssertionError("nested config must be read-only")


def test_merge_config_layers_applies_default_environment_user_precedence_without_mutating_inputs():
    default = {"risk": {"risk_per_trade_pct": 0.01, "daily_loss_limit_pct": 0.05}}
    environment = {"risk": {"risk_per_trade_pct": 0.008}}
    user = {"risk": {"daily_loss_limit_pct": 0.03}}
    merged = merge_config_layers(default, environment, user)
    assert merged["risk"]["risk_per_trade_pct"] == 0.008
    assert merged["risk"]["daily_loss_limit_pct"] == 0.03
    assert default["risk"]["risk_per_trade_pct"] == 0.01
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_config_schema.py -q`

Expected: FAIL because freeze/merge helpers do not exist.

- [ ] **Step 3: Implement read-only freeze and merge helpers**

Append to `src/config/config_schema.py`:

```python
def freeze_config(payload: dict[str, Any]) -> MappingProxyType:
    return MappingProxyType({key: freeze_value(value) for key, value in payload.items()})


def freeze_value(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: freeze_value(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(freeze_value(item) for item in value)
    return value


def merge_config_layers(
    default: dict[str, Any],
    environment: dict[str, Any] | None = None,
    user_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    merged = _deep_copy(default)
    for layer in (environment or {}, user_override or {}):
        merged = _deep_merge(merged, layer)
    return merged


def _deep_copy(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {key: _deep_copy(value) for key, value in payload.items()}
    if isinstance(payload, list):
        return [_deep_copy(value) for value in payload]
    return payload


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = _deep_copy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = _deep_copy(value)
    return result
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_config_schema.py -q`

Expected: PASS.

---

### Task 3: Hot Update Policy and Config Mutation Rules

**Files:**

- Modify: `src/config/config_schema.py`
- Modify: `tests/test_config_schema.py`

- [ ] **Step 1: Add failing tests for hot-update policy and forbidden rules**

Append to `tests/test_config_schema.py`:

```python
from src.config.config_schema import (
    CONFIG_FORBIDDEN_RULES,
    HOT_UPDATE_ALLOWED_PATHS,
    HOT_UPDATE_FORBIDDEN_PREFIXES,
    is_hot_update_allowed,
)


def test_hot_update_policy_allows_logging_and_monitoring_only():
    assert HOT_UPDATE_ALLOWED_PATHS == ["logging.level", "logging.save_json", "logging.save_csv", "monitoring"]
    assert HOT_UPDATE_FORBIDDEN_PREFIXES == ["strategy", "indicators", "entry", "probe", "direct", "risk", "stop", "take_profit", "execution"]
    assert is_hot_update_allowed("logging.level") is True
    assert is_hot_update_allowed("logging.save_json") is True
    assert is_hot_update_allowed("monitoring.latency_alert_ms") is True
    assert is_hot_update_allowed("strategy.timeframes.trigger") is False
    assert is_hot_update_allowed("risk.risk_per_trade_pct") is False
    assert is_hot_update_allowed("execution.leverage") is False


def test_config_forbidden_rules_match_doc_boundary():
    assert CONFIG_FORBIDDEN_RULES == [
        "hardcoded_parameters",
        "magic_numbers",
        "duplicate_parameter_definitions",
        "module_mutates_config",
        "hot_update_strategy_core",
    ]
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_config_schema.py -q`

Expected: FAIL because hot-update helpers do not exist.

- [ ] **Step 3: Implement hot-update policy helpers**

Append to `src/config/config_schema.py`:

```python
HOT_UPDATE_ALLOWED_PATHS = ["logging.level", "logging.save_json", "logging.save_csv", "monitoring"]
HOT_UPDATE_FORBIDDEN_PREFIXES = [
    "strategy",
    "indicators",
    "entry",
    "probe",
    "direct",
    "risk",
    "stop",
    "take_profit",
    "execution",
]
CONFIG_FORBIDDEN_RULES = [
    "hardcoded_parameters",
    "magic_numbers",
    "duplicate_parameter_definitions",
    "module_mutates_config",
    "hot_update_strategy_core",
]


def is_hot_update_allowed(path: str) -> bool:
    normalized = path.strip()
    if any(normalized == prefix or normalized.startswith(f"{prefix}.") for prefix in HOT_UPDATE_FORBIDDEN_PREFIXES):
        return False
    return any(normalized == allowed or normalized.startswith(f"{allowed}.") for allowed in HOT_UPDATE_ALLOWED_PATHS)
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_config_schema.py -q`

Expected: PASS.

---

### Task 4: Describe Script

**Files:**

- Create: `scripts/describe_config_schema.py`
- Create: `tests/test_describe_config_schema.py`

- [ ] **Step 1: Add failing describe script test**

Create `tests/test_describe_config_schema.py`:

```python
import json
import subprocess
import sys


def test_describe_config_schema_outputs_completed_11_sections():
    completed = subprocess.run(
        [sys.executable, "scripts/describe_config_schema.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["config_root"] == "configs"
    assert payload["config_files"] == ["strategy.yaml", "risk.yaml", "execution.yaml", "universe.yaml", "logging.yaml", "backtest.yaml"]
    assert payload["precedence"] == ["default", "environment", "user_override"]
    assert payload["version_required"] is True
    assert payload["read_only_policy"] == "modules may read config but must not mutate it"
    assert payload["hot_update"]["allowed"][0] == "logging.level"
    assert "strategy" in payload["hot_update"]["forbidden_prefixes"]
    assert "magic_numbers" in payload["forbidden"]
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_describe_config_schema.py -q`

Expected: FAIL because the describe script does not exist.

- [ ] **Step 3: Implement describe script**

Create `scripts/describe_config_schema.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config.config_schema import (
    CONFIG_FILES,
    CONFIG_FORBIDDEN_RULES,
    CONFIG_PRECEDENCE,
    CONFIG_REQUIRED_FIELDS,
    CONFIG_ROOT,
    HOT_UPDATE_ALLOWED_PATHS,
    HOT_UPDATE_FORBIDDEN_PREFIXES,
    REQUIRED_TOP_LEVEL_KEYS,
)


def main() -> None:
    payload = {
        "config_root": str(CONFIG_ROOT),
        "config_files": CONFIG_FILES,
        "required_top_level_keys": REQUIRED_TOP_LEVEL_KEYS,
        "required_fields": CONFIG_REQUIRED_FIELDS,
        "precedence": CONFIG_PRECEDENCE,
        "version_required": True,
        "read_only_policy": "modules may read config but must not mutate it",
        "hot_update": {
            "allowed": HOT_UPDATE_ALLOWED_PATHS,
            "forbidden_prefixes": HOT_UPDATE_FORBIDDEN_PREFIXES,
        },
        "forbidden": CONFIG_FORBIDDEN_RULES,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_config_schema.py tests/test_describe_config_schema.py -q`

Expected: PASS.

---

### Task 5: Scaffold Sync and Verification

**Files:**

- Modify: `scripts/scaffold_ai300_framework.py`

- [ ] **Step 1: Sync scaffold templates**

Copy final contents of these files into `scripts/scaffold_ai300_framework.py`:

- `src/config/__init__.py`
- `src/config/config_schema.py`
- `scripts/describe_config_schema.py`
- `tests/test_config_schema.py`
- `tests/test_describe_config_schema.py`

- [ ] **Step 2: Run targeted tests**

Run: `pytest tests/test_config_schema.py tests/test_describe_config_schema.py tests/test_framework_scaffold.py -q`

Expected: PASS.

- [ ] **Step 3: Run full verification**

Run:

```bash
pytest -q
python -m compileall src scripts tests
python scripts/describe_config_schema.py
git diff -- src/api/binance_client.py
```

Expected: all tests pass, compile succeeds, describe JSON includes completed 11 sections, and Binance diff has no output.

- [ ] **Step 4: Clean generated caches**

Run:

```powershell
$root=(Resolve-Path '.').Path; $targets=Get-ChildItem -Path . -Recurse -Directory -Filter '__pycache__' | Where-Object { $_.FullName.StartsWith($root) }; foreach($target in $targets){ Remove-Item -LiteralPath $target.FullName -Recurse -Force }; Get-ChildItem -Path . -Recurse -Directory -Filter '__pycache__' | Select-Object -ExpandProperty FullName
```

Expected: no remaining `__pycache__` directories in the workspace.

---

## Self-Review

- Spec coverage: covers config file structure, strategy/risk/execution/universe/logging/backtest sections, indicator/entry/probe/direct examples where present, version requirement, read-only policy, precedence order, hot-update allowed/forbidden paths, and forbidden hard-coding/magic-number/duplicate-definition rules.
- Placeholder scan: no `TBD`, `TODO`, `implement later`, or unspecified test steps.
- Type consistency: `CONFIG_FILES`, `CONFIG_REQUIRED_FIELDS`, `validate_config_directory`, `freeze_config`, `merge_config_layers`, and `is_hot_update_allowed` are named consistently across tasks.
