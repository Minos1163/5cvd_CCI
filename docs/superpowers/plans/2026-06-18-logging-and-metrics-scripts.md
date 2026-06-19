# Logging And Metrics Scripts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the scripts required by `docs/12_logging_and_metrics.md`.

**Architecture:** Add a pure `src/observability/logging_metrics.py` contract module for JSON log shape, required event fields, metric catalog, KPI summaries, report filenames, and Prometheus text rendering. Keep the existing `src/utils/logger.py` compatible while making it emit the standardized payload fields; do not start an HTTP metrics server or write reports to disk.

**Tech Stack:** Python standard library, dataclasses, pytest.

---

## Scope Notes

`docs/12_logging_and_metrics.md` requires:

- Logs must answer what happened, why it happened, and when it happened.
- Logs must be unified JSON; `print` debugging is forbidden.
- Levels: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`.
- Required log directories: `logs/strategy`, `logs/execution`, `logs/risk`, `logs/system`.
- Specific required fields for state-machine, entry, exit, risk, execution, and indicator logs.
- Metrics/KPI catalog: signal/trigger/fill counts, daily trade stats, win rate, net profit, loss count, Profit Factor, Sharpe, Max Drawdown, Expectancy, state duration, risk actions, CPU/RAM/API/order latency.
- Prometheus `/metrics` is recommended, but this pass only renders Prometheus exposition text.
- Daily/weekly/monthly report filenames must be stable.

This plan implements deterministic contract utilities only. It does not add a web server, persist logs, build full HTML reports, collect OS CPU/RAM telemetry, or replace application logging configuration.

## File Structure

- Create: `src/observability/__init__.py` - package marker.
- Create: `src/observability/logging_metrics.py` - log/metric constants, dataclasses, validators, JSON payload builder, KPI summary, Prometheus text renderer, and report filename helper.
- Modify: `src/utils/logger.py` - keep `log_json` but include standard `ts`, `level`, `module`, and `event` keys.
- Create: `scripts/describe_logging_metrics.py` - prints the 12 logging/metrics contract as JSON.
- Create: `tests/test_logging_metrics.py` - tests log contracts, payload builder, KPI summary, Prometheus rendering, report filenames, and `log_json` compatibility.
- Create: `tests/test_describe_logging_metrics.py` - tests describe script JSON output.
- Modify: `scripts/scaffold_ai300_framework.py` - sync templates for new module, script, tests, and modified logger.
- Preserve: `src/api/binance_client.py` - do not modify the stable Binance client.

---

### Task 1: Logging Contract Constants and JSON Payload Builder

**Files:**

- Create: `src/observability/__init__.py`
- Create: `src/observability/logging_metrics.py`
- Create: `tests/test_logging_metrics.py`

- [ ] **Step 1: Write failing tests for logging constants and payloads**

Create `tests/test_logging_metrics.py`:

```python
import json
import logging

from src.observability.logging_metrics import (
    FORBIDDEN_LOGGING_PRACTICES,
    LOG_DIRECTORIES,
    LOG_LEVELS,
    LOG_PURPOSES,
    REQUIRED_LOG_FIELDS,
    LogEvent,
    build_json_log,
    validate_log_event,
)


def test_logging_contract_lists_levels_purposes_directories_and_forbidden_print_debug():
    assert LOG_PURPOSES == ["debugging", "review", "audit", "monitoring"]
    assert FORBIDDEN_LOGGING_PRACTICES == ["print_debugging"]
    assert LOG_LEVELS == ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    assert LOG_DIRECTORIES == ["logs/strategy", "logs/execution", "logs/risk", "logs/system"]
    assert REQUIRED_LOG_FIELDS["state_machine"] == ["from_state", "to_state", "reason", "symbol", "price"]
    assert REQUIRED_LOG_FIELDS["execution"] == ["request", "response", "latency", "order_id"]


def test_log_event_builds_stable_json_payload_and_validates_required_fields():
    event = LogEvent(
        ts="2026-01-01T00:00:00Z",
        level="INFO",
        module="entry_engine",
        event="LONG_OPEN",
        fields={"symbol": "BTCUSDT", "side": "LONG", "entry_price": 100, "size": 1, "risk": 0.01},
    )
    payload = build_json_log(event)
    assert list(payload) == ["ts", "level", "module", "event", "symbol", "side", "entry_price", "size", "risk"]
    assert json.dumps(payload, ensure_ascii=False, sort_keys=True)
    assert validate_log_event("entry", payload).passed is True
    assert validate_log_event("entry", {"symbol": "BTCUSDT"}).passed is False
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_logging_metrics.py -q`

Expected: FAIL because `src.observability.logging_metrics` does not exist.

- [ ] **Step 3: Implement logging constants, dataclasses, and validation**

Create `src/observability/__init__.py`:

```python
"""Observability contracts for logs and metrics."""
```

Create `src/observability/logging_metrics.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


LOG_PURPOSES = ["debugging", "review", "audit", "monitoring"]
FORBIDDEN_LOGGING_PRACTICES = ["print_debugging"]
LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
LOG_DIRECTORIES = ["logs/strategy", "logs/execution", "logs/risk", "logs/system"]
REQUIRED_LOG_FIELDS = {
    "state_machine": ["from_state", "to_state", "reason", "symbol", "price"],
    "entry": ["symbol", "side", "entry_price", "size", "risk"],
    "exit": ["exit_reason", "pnl", "holding_time"],
    "risk": ["action", "symbol", "reason"],
    "execution": ["request", "response", "latency", "order_id"],
    "indicator_debug": ["symbol", "timeframe", "MACD", "CCI", "RSI", "CVD", "BOLL"],
}


@dataclass(frozen=True)
class ContractCheck:
    passed: bool
    reason: str


@dataclass(frozen=True)
class LogEvent:
    ts: str
    level: str
    module: str
    event: str
    fields: dict[str, Any]


def build_json_log(event: LogEvent) -> dict[str, Any]:
    level = event.level.upper()
    if level not in LOG_LEVELS:
        raise ValueError("unsupported log level")
    return {
        "ts": event.ts,
        "level": level,
        "module": event.module,
        "event": event.event,
        **event.fields,
    }


def validate_log_event(event_type: str, payload: dict[str, Any]) -> ContractCheck:
    missing = [field for field in REQUIRED_LOG_FIELDS[event_type] if field not in payload]
    if missing:
        return ContractCheck(False, f"missing log fields: {missing}")
    return ContractCheck(True, "log event approved")
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_logging_metrics.py -q`

Expected: PASS for logging contract tests.

---

### Task 2: Metrics Catalog, KPI Summary, and Prometheus Rendering

**Files:**

- Modify: `src/observability/logging_metrics.py`
- Modify: `tests/test_logging_metrics.py`

- [ ] **Step 1: Add failing tests for metrics and KPI utilities**

Append to `tests/test_logging_metrics.py`:

```python
from src.observability.logging_metrics import (
    CORE_METRICS,
    DAILY_KPI_FIELDS,
    METRIC_GROUPS,
    SYSTEM_METRICS,
    build_daily_kpi_summary,
    render_prometheus_metrics,
)


def test_metrics_catalog_matches_doc_groups_and_core_metrics():
    assert METRIC_GROUPS["indicator_monitoring"] == ["signal_count", "trigger_count", "filled_count"]
    assert DAILY_KPI_FIELDS == ["trade_count", "win_rate", "net_profit", "loss_count"]
    assert CORE_METRICS == ["profit_factor", "sharpe", "max_drawdown", "expectancy"]
    assert METRIC_GROUPS["state_machine"] == ["flat_time", "watch_time", "probe_time", "direct_time"]
    assert METRIC_GROUPS["risk"] == ["stop_loss_count", "take_profit_count", "forced_liquidation_count", "cooldown_count"]
    assert SYSTEM_METRICS == ["cpu", "ram", "api_latency", "order_latency"]


def test_build_daily_kpi_summary_calculates_trade_count_win_rate_profit_factor_and_expectancy():
    summary = build_daily_kpi_summary([100, -50, 25, -25])
    assert summary == {
        "trade_count": 4,
        "win_rate": 0.5,
        "net_profit": 50,
        "loss_count": 2,
        "profit_factor": 2.5,
        "expectancy": 12.5,
    }


def test_render_prometheus_metrics_uses_text_exposition_format():
    rendered = render_prometheus_metrics({"order_latency": 12.5, "signal_count": 3})
    assert "ai300_order_latency 12.5" in rendered
    assert "ai300_signal_count 3" in rendered
    assert rendered.endswith("\\n")
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_logging_metrics.py -q`

Expected: FAIL because metrics helpers do not exist.

- [ ] **Step 3: Implement metric constants and helpers**

Append to `src/observability/logging_metrics.py`:

```python
METRIC_GROUPS = {
    "indicator_monitoring": ["signal_count", "trigger_count", "filled_count"],
    "state_machine": ["flat_time", "watch_time", "probe_time", "direct_time"],
    "risk": ["stop_loss_count", "take_profit_count", "forced_liquidation_count", "cooldown_count"],
}
DAILY_KPI_FIELDS = ["trade_count", "win_rate", "net_profit", "loss_count"]
CORE_METRICS = ["profit_factor", "sharpe", "max_drawdown", "expectancy"]
SYSTEM_METRICS = ["cpu", "ram", "api_latency", "order_latency"]


def build_daily_kpi_summary(pnls: list[float]) -> dict[str, float | int | None]:
    wins = [value for value in pnls if value > 0]
    losses = [value for value in pnls if value < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    return {
        "trade_count": len(pnls),
        "win_rate": len(wins) / len(pnls) if pnls else None,
        "net_profit": sum(pnls),
        "loss_count": len(losses),
        "profit_factor": gross_profit / gross_loss if gross_loss else None,
        "expectancy": sum(pnls) / len(pnls) if pnls else None,
    }


def render_prometheus_metrics(metrics: dict[str, float | int], namespace: str = "ai300") -> str:
    lines = [f"{namespace}_{name} {value}" for name, value in sorted(metrics.items())]
    return "\\n".join(lines) + "\\n"
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_logging_metrics.py -q`

Expected: PASS.

---

### Task 3: Report Filenames and Logger Compatibility

**Files:**

- Modify: `src/observability/logging_metrics.py`
- Modify: `src/utils/logger.py`
- Modify: `tests/test_logging_metrics.py`

- [ ] **Step 1: Add failing tests for report filenames and `log_json` compatibility**

Append to `tests/test_logging_metrics.py`:

```python
from src.observability.logging_metrics import REPORT_FILENAMES, report_filename
from src.utils.logger import log_json


class CaptureLogger:
    def __init__(self):
        self.records = []

    def log(self, level, message):
        self.records.append((level, message))


def test_report_filenames_are_stable():
    assert REPORT_FILENAMES == {
        "daily": "daily_report.html",
        "weekly": "weekly_report.html",
        "monthly": "monthly_report.html",
    }
    assert report_filename("daily") == "daily_report.html"


def test_log_json_emits_standard_json_payload_with_ts_level_module_and_event():
    logger = CaptureLogger()
    log_json(logger, logging.INFO, "LONG_OPEN", module="entry_engine", ts="2026-01-01", symbol="BTCUSDT")
    level, message = logger.records[0]
    payload = json.loads(message)
    assert level == logging.INFO
    assert payload["ts"] == "2026-01-01"
    assert payload["level"] == "INFO"
    assert payload["module"] == "entry_engine"
    assert payload["event"] == "LONG_OPEN"
    assert payload["symbol"] == "BTCUSDT"
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_logging_metrics.py -q`

Expected: FAIL because report helpers and standardized `log_json` payload are missing.

- [ ] **Step 3: Implement report helpers**

Append to `src/observability/logging_metrics.py`:

```python
REPORT_FILENAMES = {
    "daily": "daily_report.html",
    "weekly": "weekly_report.html",
    "monthly": "monthly_report.html",
}


def report_filename(period: str) -> str:
    value = period.strip().lower()
    if value not in REPORT_FILENAMES:
        raise ValueError("period must be daily, weekly, or monthly")
    return REPORT_FILENAMES[value]
```

Modify `src/utils/logger.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone
import json
import logging


def log_json(logger: logging.Logger, level: int, event: str, **fields) -> None:
    module = fields.pop("module", "system")
    ts = fields.pop("ts", datetime.now(timezone.utc).isoformat())
    payload = {
        "ts": ts,
        "level": logging.getLevelName(level),
        "module": module,
        "event": event,
        **fields,
    }
    logger.log(level, json.dumps(payload, ensure_ascii=False, sort_keys=True))
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_logging_metrics.py -q`

Expected: PASS.

---

### Task 4: Describe Script

**Files:**

- Create: `scripts/describe_logging_metrics.py`
- Create: `tests/test_describe_logging_metrics.py`

- [ ] **Step 1: Add failing describe script test**

Create `tests/test_describe_logging_metrics.py`:

```python
import json
import subprocess
import sys


def test_describe_logging_metrics_outputs_completed_12_sections():
    completed = subprocess.run(
        [sys.executable, "scripts/describe_logging_metrics.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["log_format"] == "json"
    assert payload["log_levels"] == ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    assert payload["log_directories"] == ["logs/strategy", "logs/execution", "logs/risk", "logs/system"]
    assert payload["required_log_fields"]["entry"] == ["symbol", "side", "entry_price", "size", "risk"]
    assert payload["core_metrics"] == ["profit_factor", "sharpe", "max_drawdown", "expectancy"]
    assert payload["prometheus"]["recommended_endpoint"] == "/metrics"
    assert payload["reports"]["daily"] == "daily_report.html"
    assert "print_debugging" in payload["forbidden"]
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_describe_logging_metrics.py -q`

Expected: FAIL because the describe script does not exist.

- [ ] **Step 3: Implement describe script**

Create `scripts/describe_logging_metrics.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.observability.logging_metrics import (
    CORE_METRICS,
    DAILY_KPI_FIELDS,
    FORBIDDEN_LOGGING_PRACTICES,
    LOG_DIRECTORIES,
    LOG_LEVELS,
    LOG_PURPOSES,
    METRIC_GROUPS,
    REPORT_FILENAMES,
    REQUIRED_LOG_FIELDS,
    SYSTEM_METRICS,
)


def main() -> None:
    payload = {
        "log_format": "json",
        "log_purposes": LOG_PURPOSES,
        "log_levels": LOG_LEVELS,
        "log_directories": LOG_DIRECTORIES,
        "required_log_fields": REQUIRED_LOG_FIELDS,
        "metric_groups": METRIC_GROUPS,
        "daily_kpi_fields": DAILY_KPI_FIELDS,
        "core_metrics": CORE_METRICS,
        "system_metrics": SYSTEM_METRICS,
        "prometheus": {"recommended_endpoint": "/metrics", "format": "text_exposition"},
        "reports": REPORT_FILENAMES,
        "forbidden": FORBIDDEN_LOGGING_PRACTICES,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_logging_metrics.py tests/test_describe_logging_metrics.py -q`

Expected: PASS.

---

### Task 5: Scaffold Sync and Verification

**Files:**

- Modify: `scripts/scaffold_ai300_framework.py`

- [ ] **Step 1: Sync scaffold templates**

Copy final contents of these files into `scripts/scaffold_ai300_framework.py`:

- `src/observability/__init__.py`
- `src/observability/logging_metrics.py`
- `src/utils/logger.py`
- `scripts/describe_logging_metrics.py`
- `tests/test_logging_metrics.py`
- `tests/test_describe_logging_metrics.py`

- [ ] **Step 2: Run targeted tests**

Run: `pytest tests/test_logging_metrics.py tests/test_describe_logging_metrics.py tests/test_framework_scaffold.py -q`

Expected: PASS.

- [ ] **Step 3: Run full verification**

Run:

```bash
pytest -q
python -m compileall src scripts tests
python scripts/describe_logging_metrics.py
git diff -- src/api/binance_client.py
```

Expected: all tests pass, compile succeeds, describe JSON includes completed 12 sections, and Binance diff has no output.

- [ ] **Step 4: Clean generated caches**

Run:

```powershell
$root=(Resolve-Path '.').Path; $targets=Get-ChildItem -Path . -Recurse -Directory -Filter '__pycache__' | Where-Object { $_.FullName.StartsWith($root) }; foreach($target in $targets){ Remove-Item -LiteralPath $target.FullName -Recurse -Force }; Get-ChildItem -Path . -Recurse -Directory -Filter '__pycache__' | Select-Object -ExpandProperty FullName
```

Expected: no remaining `__pycache__` directories in the workspace.

---

## Self-Review

- Spec coverage: covers log purposes, forbidden print debugging, log levels, JSON format, log directories, state/entry/exit/risk/execution/indicator log fields, indicator monitoring, daily KPI, core metrics, state-machine metrics, risk metrics, system metrics, Prometheus recommendation, and daily/weekly/monthly report filenames.
- Placeholder scan: no `TBD`, `TODO`, `implement later`, or unspecified test steps.
- Type consistency: `LogEvent`, `ContractCheck`, `build_json_log`, `validate_log_event`, `build_daily_kpi_summary`, `render_prometheus_metrics`, `REPORT_FILENAMES`, and `report_filename` are named consistently across tasks.
