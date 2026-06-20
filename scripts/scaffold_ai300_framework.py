from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROTECTED_PATH_LABELS = {"src/binance_client.py", "src/api/binance_client.py"}
PROTECTED = {ROOT / "src" / "binance_client.py", ROOT / "src" / "api" / "binance_client.py"}


def write_file(path: str, content: str) -> None:
    target = ROOT / path
    if target in PROTECTED:
        raise RuntimeError("scaffold must not modify src/binance_client.py")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        return
    target.write_text(content.strip() + "\n", encoding="utf-8")


FILES = {
    "pytest.ini": """
[pytest]
pythonpath = .
""",
    "configs/strategy.yaml": """
version: 1.0.0
strategy:
  name: macd_cci_cvd_v1
  mode: research
  timeframes:
    trigger: 15m
    confirm: 30m
    trend: 1h
    context: 4h
indicators:
  macd:
    fast: 12
    slow: 26
    signal: 9
  cci:
    period: 20
  rsi:
    period: 14
  boll:
    period: 20
    std: 2
  atr:
    period: 14
entry:
  cci_long: 100
  cci_short: -100
  rsi_reclaim: 50
  require_cvd_confirm: true
probe:
  enabled: true
  size_ratio: 0.25
  upgrade_r_multiple: 1.0
""",
    "configs/risk.yaml": """
version: 1.0.0
risk:
  risk_per_trade_pct: 0.01
  daily_loss_limit_pct: 0.05
  weekly_loss_limit_pct: 0.12
  max_drawdown_pct: 0.20
  max_total_exposure_pct: 0.75
  max_open_positions: 5
stop:
  atr_mult: 1.5
  min_stop_pct: 0.005
take_profit:
  tp1_r: 1.0
  tp2_r: 2.0
  tp3_r: 4.0
""",
    "configs/execution.yaml": """
version: 1.0.0
execution:
  mode: dry_run
  exchange: binance
  leverage: 3
  use_market_order: true
  require_risk_approval: true
slippage:
  base_bps: 3
  high_vol_bps: 8
""",
    "configs/universe.yaml": """
version: 1.0.0
universe:
  exchange: binance_futures
  contract_type: USDT_PERPETUAL
  quote_asset: USDT
  max_symbols: 20
  max_symbols_hard_cap: 30
  min_market_cap_rank: 20
  max_market_cap_rank: 30
  min_24h_volume_usd: 300000000
  min_listing_days: 365
  max_spread_pct: 0.05
  max_missing_bar_ratio: 0.005
  update_frequency: weekly
  universe_version: 2026W01
  symbols:
    - BTCUSDT
    - ETHUSDT
    - BNBUSDT
    - SOLUSDT
    - XRPUSDT
""",
    "configs/backtest.yaml": """
version: 1.0.0
backtest:
  start: "2024-01-01"
  end: "2025-01-01"
  initial_capital: 10000
  fee_bps: 5
  slippage_bps: 5
  fill_model: next_bar_open
""",
    "configs/logging.yaml": """
version: 1.0.0
logging:
  level: INFO
  json: true
  directory: logs
""",
    "src/config/__init__.py": '"""Configuration schema and loading helpers."""',
    "src/config/config_schema.py": """
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
        "universe.contract_type",
        "universe.quote_asset",
        "universe.max_symbols",
        "universe.max_symbols_hard_cap",
        "universe.min_market_cap_rank",
        "universe.max_market_cap_rank",
        "universe.min_24h_volume_usd",
        "universe.min_listing_days",
        "universe.max_spread_pct",
        "universe.max_missing_bar_ratio",
        "universe.update_frequency",
        "universe.universe_version",
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


@dataclass(frozen=True)
class ConfigValidationResult:
    passed: bool
    errors: list[str]


def load_simple_yaml(path: Path) -> dict[str, Any]:
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, root)]
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
            _, key, owner = pending_list_key
            if not isinstance(owner.get(key), list):
                owner[key] = []
            owner[key].append(_parse_scalar(stripped[2:].strip()))
            continue
        key, _, value = stripped.partition(":")
        key = key.strip()
        value = value.strip()
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


def is_hot_update_allowed(path: str) -> bool:
    normalized = path.strip()
    if any(normalized == prefix or normalized.startswith(f"{prefix}.") for prefix in HOT_UPDATE_FORBIDDEN_PREFIXES):
        return False
    return any(normalized == allowed or normalized.startswith(f"{allowed}.") for allowed in HOT_UPDATE_ALLOWED_PATHS)
""",
    "scripts/describe_config_schema.py": """
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
""",
    "tests/test_config_schema.py": """
from pathlib import Path

from src.config.config_schema import (
    CONFIG_FILES,
    CONFIG_FORBIDDEN_RULES,
    CONFIG_PRECEDENCE,
    CONFIG_REQUIRED_FIELDS,
    CONFIG_ROOT,
    HOT_UPDATE_ALLOWED_PATHS,
    HOT_UPDATE_FORBIDDEN_PREFIXES,
    REQUIRED_TOP_LEVEL_KEYS,
    freeze_config,
    is_hot_update_allowed,
    merge_config_layers,
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
    assert "universe.update_frequency" in CONFIG_REQUIRED_FIELDS["universe.yaml"]


def test_existing_configs_validate_against_schema():
    result = validate_config_directory(Path("configs"))
    assert result.passed is True
    assert result.errors == []


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


def test_hot_update_policy_allows_logging_and_monitoring_only():
    assert HOT_UPDATE_ALLOWED_PATHS == ["logging.level", "logging.save_json", "logging.save_csv", "monitoring"]
    assert HOT_UPDATE_FORBIDDEN_PREFIXES == [
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


def test_universe_config_requires_v1_market_universe_fields():
    required = CONFIG_REQUIRED_FIELDS["universe.yaml"]
    assert "universe.update_frequency" in required
    assert "universe.min_24h_volume_usd" in required
    assert "universe.min_listing_days" in required
    assert "universe.max_spread_pct" in required
    assert "universe.max_missing_bar_ratio" in required
    assert "universe.universe_version" in required
""",
    "tests/test_describe_config_schema.py": """
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
    assert payload["config_files"] == [
        "strategy.yaml",
        "risk.yaml",
        "execution.yaml",
        "universe.yaml",
        "logging.yaml",
        "backtest.yaml",
    ]
    assert payload["precedence"] == ["default", "environment", "user_override"]
    assert payload["version_required"] is True
    assert payload["read_only_policy"] == "modules may read config but must not mutate it"
    assert payload["hot_update"]["allowed"][0] == "logging.level"
    assert "strategy" in payload["hot_update"]["forbidden_prefixes"]
    assert "magic_numbers" in payload["forbidden"]
""",
    "src/__init__.py": '"""AI300 trading framework package."""',
    "src/core/__init__.py": '"""Core DTOs, events, and protocols."""',
    "src/core/constants.py": """
TIMEFRAME_TRIGGER = "15m"
TIMEFRAME_CONFIRM = "30m"
TIMEFRAME_TREND = "1h"
TIMEFRAME_CONTEXT = "4h"

SIDE_LONG = "LONG"
SIDE_SHORT = "SHORT"
SIDE_NONE = "NONE"

SIGNAL_DIRECT = "DIRECT"
SIGNAL_PROBE = "PROBE"
SIGNAL_WAIT = "WAIT"
SIGNAL_NO_TRADE = "NO_TRADE"
""",
    "src/core/events.py": """
from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Callable, Iterable, Mapping
from uuid import uuid4


class EventType(str, Enum):
    MARKET_DATA_UPDATED = "MARKET_DATA_UPDATED"
    INDICATOR_UPDATED = "INDICATOR_UPDATED"
    MULTI_TF_CONTEXT_READY = "MULTI_TF_CONTEXT_READY"
    WATCH_ENTERED = "WATCH_ENTERED"
    PROBE_ENTERED = "PROBE_ENTERED"
    DIRECT_ENTERED = "DIRECT_ENTERED"
    POSITION_OPENED = "POSITION_OPENED"
    POSITION_REDUCED = "POSITION_REDUCED"
    POSITION_CLOSED = "POSITION_CLOSED"
    STOP_HIT = "STOP_HIT"
    TP_HIT = "TP_HIT"
    RISK_BLOCKED = "RISK_BLOCKED"
    COOLDOWN_STARTED = "COOLDOWN_STARTED"
    COOLDOWN_ENDED = "COOLDOWN_ENDED"
    BACKTEST_STEP_COMPLETED = "BACKTEST_STEP_COMPLETED"
    REPORT_GENERATED = "REPORT_GENERATED"
    MARKET_CANDLE_CLOSED = "MARKET_CANDLE_CLOSED"
    INDICATORS_UPDATED = "INDICATORS_UPDATED"
    MULTI_TIMEFRAME_CONTEXT_UPDATED = "MULTI_TIMEFRAME_CONTEXT_UPDATED"
    SIGNAL_CREATED = "SIGNAL_CREATED"
    SIGNAL_REJECTED = "SIGNAL_REJECTED"
    STATE_TRANSITION = "STATE_TRANSITION"
    RISK_APPROVED = "RISK_APPROVED"
    RISK_REJECTED = "RISK_REJECTED"
    ORDER_INTENT_CREATED = "ORDER_INTENT_CREATED"
    ORDER_SUBMITTED = "ORDER_SUBMITTED"
    ORDER_ACKNOWLEDGED = "ORDER_ACKNOWLEDGED"
    ORDER_REJECTED = "ORDER_REJECTED"
    ORDER_FILLED = "ORDER_FILLED"
    HANDLER_FAILED = "HANDLER_FAILED"


class EventPriority(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    NORMAL = "NORMAL"
    LOW = "LOW"


class EventStatus(str, Enum):
    CREATED = "created"
    PUBLISHED = "published"
    DISPATCHED = "dispatched"
    HANDLED = "handled"
    PERSISTED = "persisted"
    ARCHIVED = "archived"
    FAILED = "failed"
    RETRIED = "retried"
    DEAD_LETTERED = "dead_lettered"
    DUPLICATE = "duplicate"


KEY_EVENT_TYPES = [
    "MARKET_DATA_UPDATED",
    "INDICATOR_UPDATED",
    "MULTI_TF_CONTEXT_READY",
    "SIGNAL_CREATED",
    "WATCH_ENTERED",
    "PROBE_ENTERED",
    "DIRECT_ENTERED",
    "ORDER_SUBMITTED",
    "ORDER_FILLED",
    "ORDER_REJECTED",
    "POSITION_OPENED",
    "POSITION_REDUCED",
    "POSITION_CLOSED",
    "STOP_HIT",
    "TP_HIT",
    "RISK_BLOCKED",
    "COOLDOWN_STARTED",
    "COOLDOWN_ENDED",
    "BACKTEST_STEP_COMPLETED",
    "REPORT_GENERATED",
]
EVENT_LIFECYCLE_STATES = [
    "created",
    "published",
    "dispatched",
    "handled",
    "persisted",
    "archived",
    "failed",
    "retried",
    "dead_lettered",
]
EVENT_REQUIRED_FIELDS = [
    "event_id",
    "event_type",
    "ts",
    "source",
    "symbol",
    "timeframe",
    "version",
    "payload",
    "priority",
    "correlation_id",
    "parent_event_id",
    "trace_id",
    "status",
]
EVENT_DEDUPE_KEY_FIELDS = ["symbol", "event_type", "strategy_event_id", "timeframe"]
EVENT_ERROR_TYPES = [
    "INVALID_PAYLOAD",
    "UNKNOWN_EVENT_TYPE",
    "HANDLER_ERROR",
    "TIMEOUT",
    "DUPLICATE_EVENT",
    "STATE_CONFLICT",
    "DEPENDENCY_UNAVAILABLE",
]
EVENT_CATEGORIES = {
    "Market Events": ["MARKET_DATA_UPDATED"],
    "Indicator Events": ["INDICATOR_UPDATED"],
    "Context Events": ["MULTI_TF_CONTEXT_READY"],
    "Signal Events": ["SIGNAL_CREATED", "WATCH_ENTERED", "PROBE_ENTERED", "DIRECT_ENTERED"],
    "Risk Events": ["STOP_HIT", "TP_HIT", "RISK_BLOCKED", "COOLDOWN_STARTED", "COOLDOWN_ENDED"],
    "Execution Events": ["ORDER_SUBMITTED", "ORDER_FILLED", "ORDER_REJECTED"],
    "Position Events": ["POSITION_OPENED", "POSITION_REDUCED", "POSITION_CLOSED"],
    "Backtest Events": ["BACKTEST_STEP_COMPLETED"],
    "Reporting Events": ["REPORT_GENERATED"],
}
EVENT_PRIORITY_RANK = {
    EventPriority.CRITICAL: 0,
    EventPriority.HIGH: 1,
    EventPriority.NORMAL: 2,
    EventPriority.LOW: 3,
}


@dataclass(frozen=True)
class Event:
    event_type: EventType
    ts: int
    source: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    symbol: str | None = None
    timeframe: str | None = None
    correlation_id: str | None = None
    event_id: str = field(default_factory=lambda: str(uuid4()))
    version: str = "1.0"
    priority: EventPriority = EventPriority.NORMAL
    parent_event_id: str | None = None
    trace_id: str | None = None
    status: EventStatus = EventStatus.CREATED

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "ts": self.ts,
            "source": self.source,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "version": self.version,
            "payload": dict(self.payload),
            "priority": self.priority.value,
            "correlation_id": self.correlation_id,
            "parent_event_id": self.parent_event_id,
            "trace_id": self.trace_id,
            "status": self.status.value,
        }

    def with_status(self, status: EventStatus) -> "Event":
        return replace(self, status=status)

    def dedupe_key(self) -> str:
        strategy_event_id = self.payload.get("strategy_event_id", self.event_id)
        return f"{self.symbol}:{self.event_type.value}:{strategy_event_id}:{self.timeframe}"


Handler = Callable[[Event], "HandlerResult"]


@dataclass(frozen=True)
class HandlerResult:
    success: bool
    next_events: list[Event] = field(default_factory=list)
    logs: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DeadLetterRecord:
    event: Event
    reason: str
    errors: list[str]
    retry_count: int
    handler_name: str


class EventBus:
    def __init__(self, *, max_retries: int = 0, max_queue_size: int = 1000) -> None:
        self.max_retries = max_retries
        self.max_queue_size = max_queue_size
        self._handlers: dict[EventType, list[Handler]] = {}
        self._processed_event_ids: set[str] = set()
        self._processed_dedupe_keys: set[str] = set()
        self.event_log: list[Event] = []
        self.dead_letters: list[DeadLetterRecord] = []

    def subscribe(self, event_type: EventType, handler: Handler) -> None:
        self._handlers.setdefault(event_type, []).append(handler)

    def publish(self, event: Event) -> HandlerResult:
        if event.event_id in self._processed_event_ids or event.dedupe_key() in self._processed_dedupe_keys:
            self.event_log.append(event.with_status(EventStatus.DUPLICATE))
            return HandlerResult(True, logs=["duplicate ignored"], metadata={"duplicate": True})
        self._processed_event_ids.add(event.event_id)
        self._processed_dedupe_keys.add(event.dedupe_key())
        return self._dispatch(event.with_status(EventStatus.PUBLISHED))

    def _dispatch(self, event: Event) -> HandlerResult:
        handlers = self._handlers.get(event.event_type, [])
        all_logs: list[str] = []
        all_errors: list[str] = []
        next_events: list[Event] = []
        for handler in handlers:
            result = self._call_handler(handler, event)
            all_logs.extend(result.logs)
            all_errors.extend(result.errors)
            next_events.extend(result.next_events)
            if not result.success:
                self.event_log.append(event.with_status(EventStatus.FAILED))
                return HandlerResult(False, next_events, all_logs, all_errors, {"failed_event_id": event.event_id})
        self.event_log.append(event.with_status(EventStatus.HANDLED))
        for next_event in sorted(next_events, key=lambda item: EVENT_PRIORITY_RANK[item.priority]):
            self.publish(next_event)
        return HandlerResult(True, next_events, all_logs, all_errors)

    def _call_handler(self, handler: Handler, event: Event) -> HandlerResult:
        attempts = 0
        while True:
            try:
                return handler(event)
            except Exception as exc:
                attempts += 1
                if attempts > self.max_retries:
                    self.dead_letters.append(
                        DeadLetterRecord(
                            event=event.with_status(EventStatus.DEAD_LETTERED),
                            reason="HANDLER_ERROR",
                            errors=[str(exc)],
                            retry_count=attempts - 1,
                            handler_name=getattr(handler, "__name__", handler.__class__.__name__),
                        )
                    )
                    return HandlerResult(False, errors=[str(exc)], metadata={"dead_lettered": True})

    def replay(
        self,
        events: Iterable[Event],
        *,
        start_ts: int | None = None,
        end_ts: int | None = None,
        symbol: str | None = None,
        event_type: EventType | None = None,
        ignore_low_priority: bool = False,
    ) -> list[HandlerResult]:
        selected = sorted(events, key=lambda item: item.ts)
        results: list[HandlerResult] = []
        for event in selected:
            if start_ts is not None and event.ts < start_ts:
                continue
            if end_ts is not None and event.ts > end_ts:
                continue
            if symbol is not None and event.symbol != symbol:
                continue
            if event_type is not None and event.event_type != event_type:
                continue
            if ignore_low_priority and event.priority == EventPriority.LOW:
                continue
            results.append(self.publish(event))
        return results
""",
    "src/core/models.py": """
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Candle:
    symbol: str
    timeframe: str
    open_time: int
    close_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    quote_volume: float = 0.0
    trade_count: int = 0
    taker_buy_volume: float = 0.0


@dataclass(frozen=True)
class IndicatorSnapshot:
    symbol: str
    timeframe: str
    close_time: int
    macd: float | None = None
    macd_signal: float | None = None
    macd_hist: float | None = None
    cci: float | None = None
    rsi: float | None = None
    boll_mid: float | None = None
    boll_upper: float | None = None
    boll_lower: float | None = None
    atr: float | None = None
    cvd: float | None = None
    cvd_delta: float | None = None


@dataclass(frozen=True)
class Signal:
    symbol: str
    side: str
    signal_type: str
    reason: str
    close_time: int


@dataclass(frozen=True)
class RiskDecision:
    approved: bool
    reason: str
    symbol: str
    side: str
    quantity: float = 0.0
    notional: float = 0.0
    stop_price: float | None = None


@dataclass(frozen=True)
class OrderIntent:
    symbol: str
    side: str
    position_side: str
    quantity: float
    order_type: str
    correlation_id: str
    price: float | None = None
    reduce_only: bool = False
""",
    "src/core/protocols.py": """
from __future__ import annotations

from typing import Protocol

from src.core.models import OrderIntent


class ExecutionAdapter(Protocol):
    def submit(self, intent: OrderIntent) -> dict:
        ...

    def cancel(self, symbol: str, order_id: int | str) -> dict:
        ...

    def sync(self, symbol: str | None = None) -> dict:
        ...
""",
    "src/core/project_spec.py": """
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
""",
    "src/core/strategy_philosophy.py": """
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PhilosophyCheck:
    name: str
    passed: bool
    reason: str


REGIME_ACTIONS = {
    "up": "long",
    "down": "short",
    "range": "wait",
}
STRATEGY_IDENTITY = {
    "venue": "binance_usdt_perpetual",
    "style": "multi_timeframe_trend_following",
    "core_sentence": "higher_tf_direction_mid_tf_quality_low_tf_timing_flow_confirmation_volatility_boundary",
}
STRATEGY_NON_GOALS = ["high_frequency_market_making", "arbitrage", "black_box_prediction", "complex_score_stacking", "manual_discretionary_override"]
FIRST_PRINCIPLES = ["risk_before_return", "trend_before_entry", "quality_before_quantity", "explainability_before_complexity", "live_backtest_isomorphism_before_optimization"]
MARKET_STATES = ["uptrend", "downtrend", "range", "trend_transition", "volatility_expansion", "volatility_contraction"]
DECISION_PRIORITY = ["data_quality", "risk_constraints", "higher_timeframe_direction", "mid_timeframe_quality", "lower_timeframe_timing", "fund_flow_confirmation", "position_executability", "execution_landing"]
ALLOWED_TRADE_TYPES = ["PROBE", "DIRECT"]
ANTI_NOISE_RULES = ["single_abnormal_candle", "short_timeframe_fake_breakout", "low_quality_divergence", "temporary_wick", "distorted_volume", "overheated_micro_continuation"]
ANTI_OVERFIT_RULES = ["add_rule_for_single_failed_sample", "add_exception_to_improve_win_rate_only", "optimize_for_one_history_segment", "hide_execution_costs", "change_live_rules_after_backtest"]
CAPITAL_MANAGEMENT_PRINCIPLES = ["define_trade_risk_first", "derive_position_size_from_risk", "choose_probe_or_direct_after_risk", "execution_layer_must_not_patch_size"]
EXIT_PHILOSOPHY = ["losses_should_be_fast", "admit_wrong_trade_early", "protect_capital_first", "let_valid_profit_run", "do_not_patch_distorted_position"]
UNCERTAINTY_ACTIONS = ["degrade", "wait", "observe", "reduce_size", "disable_new_entries"]
UNCERTAINTY_FORBIDDEN_ACTIONS = ["force_trade", "increase_tolerance", "add_exception", "patch_uncertainty"]
PHILOSOPHY_FORBIDDEN_PATTERNS = ["complex_watchlist_promotion_chain", "temporary_gate_patch_stack", "fixed_one_percent_stop_for_all_regimes", "weak_trend_large_position", "low_timeframe_noise_overrides_higher_timeframe", "signal_and_execution_reinterpret_position", "trade_first_explain_later", "countertrend_without_structure", "asymmetric_long_short_exception"]

TIMEFRAME_ROLES = {
    "4h": "background",
    "1h": "trend_confirmation",
    "30m": "trend_quality",
    "15m": "execution_trigger",
}

INDICATOR_RESPONSIBILITIES = {
    "MACD": "trend",
    "CCI": "trend_strength",
    "RSI": "pullback_quality",
    "BOLL": "volatility_structure",
    "CVD": "fund_flow",
    "ATR": "risk_control",
}


def validate_indicator_role(indicator: str, requested_role: str) -> tuple[bool, str]:
    key = indicator.upper()
    actual = INDICATOR_RESPONSIBILITIES.get(key)
    if actual is None:
        return False, f"unknown indicator: {indicator}"
    if actual != requested_role:
        return False, f"{key} is responsible for {actual}, not {requested_role}"
    return True, "allowed"


def validate_decision_chain_depth(chain: list[str], max_depth: int = 3) -> tuple[bool, str]:
    if len(chain) > max_depth:
        return False, "decision chain exceeds 3 layers"
    return True, "allowed"


def validate_decision_priority(priority: list[str]) -> PhilosophyCheck:
    if priority != DECISION_PRIORITY:
        return PhilosophyCheck("decision_priority", False, "decision priority must remain fixed")
    return PhilosophyCheck("decision_priority", True, "decision priority approved")


def validate_long_short_symmetry(rule_map: dict[str, list[str]]) -> PhilosophyCheck:
    if rule_map.get("LONG", []) != rule_map.get("SHORT", []):
        return PhilosophyCheck("long_short_symmetry", False, "long and short rules must be mirrored")
    return PhilosophyCheck("long_short_symmetry", True, "long and short rules are symmetric")


def validate_uncertainty_response(action: str) -> PhilosophyCheck:
    if action.strip().lower() in UNCERTAINTY_ACTIONS:
        return PhilosophyCheck("uncertainty_response", True, "uncertainty response approved")
    return PhilosophyCheck("uncertainty_response", False, "uncertainty must degrade, wait, observe, reduce size, or disable new entries")


def validate_strategy_pattern_allowed(pattern: str) -> PhilosophyCheck:
    normalized = pattern.casefold()
    for forbidden in PHILOSOPHY_FORBIDDEN_PATTERNS:
        if forbidden.casefold() in normalized or normalized in forbidden.casefold():
            return PhilosophyCheck("strategy_pattern", False, f"{forbidden} is forbidden by strategy philosophy")
    return PhilosophyCheck("strategy_pattern", True, "strategy pattern allowed")
""",
    "src/data/__init__.py": '"""Data loading and normalization."""',
    "src/data/candle_resampler.py": """
from __future__ import annotations

from collections.abc import Iterable

from src.core.models import Candle


def validate_candles(candles: Iterable[Candle]) -> list[Candle]:
    ordered = sorted(candles, key=lambda candle: candle.open_time)
    seen: set[int] = set()
    for candle in ordered:
        if candle.open_time in seen:
            raise ValueError(f"duplicate candle open_time: {candle.open_time}")
        if candle.high < max(candle.open, candle.close) or candle.low > min(candle.open, candle.close):
            raise ValueError("invalid OHLC relationship")
        seen.add(candle.open_time)
    return ordered
""",
    "src/data/cvd_builder.py": """
from __future__ import annotations

from collections.abc import Iterable

from src.core.models import Candle
from src.data.data_contract import CVDPoint, build_cvd_contract_points


def build_cvd(candles: Iterable[Candle]) -> list[float]:
    total = 0.0
    values: list[float] = []
    for candle in candles:
        sell_volume = max(candle.volume - candle.taker_buy_volume, 0.0)
        total += candle.taker_buy_volume - sell_volume
        values.append(total)
    return values


def build_cvd_points(candles: Iterable[Candle]) -> list[CVDPoint]:
    return build_cvd_contract_points(list(candles))
""",
    "src/data/data_contract.py": """
from __future__ import annotations

from dataclasses import dataclass

from src.core.models import Candle


REQUIRED_DATA_TYPES = ["kline", "volume", "active_buy_sell", "position_or_funding", "universe"]
DATA_LAYERS = [
    "raw_market_data",
    "normalized_market_data",
    "multi_timeframe_data",
    "indicator_result_data",
    "strategy_context_data",
]
DATA_SOURCES = [
    "kline",
    "volume",
    "active_buy_sell",
    "funding_rate",
    "open_interest",
    "universe",
    "execution",
    "account_position_snapshot",
]
REQUIRED_CANDLE_FIELDS = [
    "open_time",
    "close_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "quote_volume",
    "trade_count",
]
FULL_CANDLE_FIELDS = [
    "symbol",
    "timeframe",
    "open_time",
    "close_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "quote_volume",
    "trade_count",
    "taker_buy_base_volume",
    "taker_buy_quote_volume",
    "is_closed",
    "source",
    "quality_flag",
]
SUPPORTED_TIMEFRAMES = ["15m", "30m", "1h", "4h"]
TIMEFRAME_SECONDS = {"15m": 900, "30m": 1800, "1h": 3600, "4h": 14400}
TIMEFRAME_ROLES = {"15m": "execution", "30m": "confirmation", "1h": "direction", "4h": "background"}
AGGREGATION_RULES = {"30m": "15m", "1h": ("15m", "30m"), "4h": "1h"}
CVD_SOURCES = ["trades", "taker_buy_sell_estimate", "exchange_active_buy_sell"]
QUALITY_FLAGS = [True, False, "degraded", "stale"]

INDICATOR_CONTRACT_FIELDS = [
    "name",
    "symbol",
    "timeframe",
    "value",
    "signal",
    "trend",
    "strength",
    "timestamp",
    "metadata",
    "quality_flag",
]
INDICATOR_REQUIRED_OUTPUTS = {
    "MACD": ["macd_line", "signal_line", "histogram", "histogram_slope", "cross_state"],
    "RSI": ["rsi", "rsi_slope", "overbought_flag", "oversold_flag", "midline_state"],
    "CCI": ["cci", "cci_slope", "extreme_flag", "recovery_flag"],
    "BOLL": [
        "middle_band",
        "upper_band",
        "lower_band",
        "band_width",
        "band_expansion_flag",
        "band_contraction_flag",
        "price_position",
    ],
    "CVD": ["cvd", "cvd_delta", "cvd_slope", "cvd_divergence_flag", "buy_pressure", "sell_pressure"],
    "ATR": ["atr", "atr_pct", "volatility_state"],
}
STRATEGY_CONTEXT_FIELDS = [
    "symbol",
    "timestamp",
    "market_state_4h",
    "trend_state_1h",
    "confirm_state_30m",
    "trigger_state_15m",
    "indicators_15m",
    "indicators_30m",
    "indicators_1h",
    "indicators_4h",
    "risk_snapshot",
    "position_snapshot",
    "cooldown_state",
    "signal_candidate",
    "quality_flag",
]
STRATEGY_EVENT_FIELDS = [
    "event_id",
    "symbol",
    "timeframe",
    "event_type",
    "state_before",
    "state_after",
    "reason",
    "score",
    "timestamp",
    "metadata",
]
STRATEGY_EVENT_TYPES = [
    "SIGNAL_CREATED",
    "WATCH_ENTERED",
    "PROBE_ENTERED",
    "DIRECT_ENTERED",
    "POSITION_MANAGED",
    "EXIT_TRIGGERED",
    "RISK_BLOCKED",
    "DATA_INVALID",
]
EXECUTION_FIELDS = [
    "order_id",
    "client_order_id",
    "symbol",
    "side",
    "order_type",
    "quantity",
    "price",
    "reduce_only",
    "position_side",
    "status",
    "filled_qty",
    "avg_price",
    "commission",
    "latency_ms",
    "reject_reason",
    "raw_response",
]
ACCOUNT_SNAPSHOT_FIELDS = [
    "account_equity",
    "available_margin",
    "used_margin",
    "unrealized_pnl",
    "realized_pnl",
    "max_drawdown",
    "daily_pnl",
    "weekly_pnl",
]
POSITION_SNAPSHOT_FIELDS = [
    "symbol",
    "side",
    "position_qty",
    "entry_price",
    "mark_price",
    "unrealized_pnl",
    "leverage",
    "stop_price",
    "take_profit_price",
    "position_age",
]
UNIVERSE_ITEM_FIELDS = [
    "symbol",
    "base_asset",
    "quote_asset",
    "market_cap_rank",
    "volume_rank",
    "tier",
    "tradable",
    "listed_time",
    "delisting_flag",
    "correlation_group",
]
CACHE_CONTRACT_FIELDS = ["ttl", "update_frequency", "hit_condition", "no_future_cache"]
VERSION_FIELDS = [
    "raw_data_version",
    "aggregation_version",
    "indicator_version",
    "strategy_version",
    "risk_version",
    "execution_version",
]
STORAGE_CONTRACT = {
    "hot": ["recent_market", "current_position", "current_signal", "current_risk_state"],
    "warm": ["recent_trades", "recent_strategy_events", "recent_execution_logs"],
    "cold": ["historical_backtest_data", "long_term_trade_audit", "historical_performance_report"],
}
DATA_CONTRACT_FORBIDDEN = [
    "mix timezones",
    "reuse same field name with different meaning",
    "let indicators read raw exchange responses",
    "let strategy bypass normalized objects",
    "use presentation data as strategy data",
    "use patch fields in main decisions",
    "let backtest and live use different field sets",
]


@dataclass(frozen=True)
class ContractCheck:
    name: str
    passed: bool
    reason: str


@dataclass(frozen=True)
class MarketCandle:
    symbol: str
    timeframe: str
    open_time: int
    close_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    quote_volume: float
    trade_count: int
    taker_buy_base_volume: float
    taker_buy_quote_volume: float
    is_closed: bool
    source: str
    quality_flag: bool | str = True


@dataclass(frozen=True)
class IndicatorResult:
    name: str
    symbol: str
    timeframe: str
    value: dict
    signal: str
    trend: str
    strength: float
    timestamp: int
    metadata: dict
    quality_flag: bool | str = True


@dataclass(frozen=True)
class StrategyContext:
    symbol: str
    timestamp: int
    market_state_4h: str
    trend_state_1h: str
    confirm_state_30m: str
    trigger_state_15m: str
    indicators_15m: dict
    indicators_30m: dict
    indicators_1h: dict
    indicators_4h: dict
    risk_snapshot: dict
    position_snapshot: dict
    cooldown_state: dict
    signal_candidate: dict
    quality_flag: bool | str = True


@dataclass(frozen=True)
class CVDPoint:
    close_time: int
    cumulative: float
    delta: float
    slope: float
    divergence: str


def normalize_timeframe(timeframe: str) -> str:
    return timeframe.strip().lower()


def market_candle_to_candle(market_candle: MarketCandle) -> Candle:
    return Candle(
        symbol=market_candle.symbol,
        timeframe=market_candle.timeframe,
        open_time=market_candle.open_time,
        close_time=market_candle.close_time,
        open=market_candle.open,
        high=market_candle.high,
        low=market_candle.low,
        close=market_candle.close,
        volume=market_candle.volume,
        quote_volume=market_candle.quote_volume,
        trade_count=market_candle.trade_count,
        taker_buy_volume=market_candle.taker_buy_base_volume,
    )


def validate_ohlcv_contract(candle: Candle) -> ContractCheck:
    timeframe = normalize_timeframe(candle.timeframe)
    if timeframe not in SUPPORTED_TIMEFRAMES:
        return ContractCheck("ohlcv_contract", False, f"unsupported timeframe: {candle.timeframe}")
    if candle.close_time <= candle.open_time:
        return ContractCheck("ohlcv_contract", False, "close_time must be greater than open_time")
    if candle.high < max(candle.open, candle.close) or candle.low > min(candle.open, candle.close):
        return ContractCheck("ohlcv_contract", False, "invalid OHLC relationship")
    if min(candle.open, candle.high, candle.low, candle.close) <= 0:
        return ContractCheck("ohlcv_contract", False, "prices must be positive")
    if candle.volume <= 0:
        return ContractCheck("ohlcv_contract", False, "volume must be positive")
    if candle.quote_volume <= 0:
        return ContractCheck("ohlcv_contract", False, "quote_volume must be positive")
    if candle.trade_count <= 0:
        return ContractCheck("ohlcv_contract", False, "trade_count must be positive")
    return ContractCheck("ohlcv_contract", True, "candle contract approved")


def validate_market_candle(market_candle: MarketCandle) -> ContractCheck:
    if not market_candle.is_closed:
        return ContractCheck("market_candle", False, "market candle must be closed")
    if market_candle.quality_flag not in QUALITY_FLAGS:
        return ContractCheck("market_candle", False, "unsupported quality_flag")
    if not market_candle.source:
        return ContractCheck("market_candle", False, "source must be present")
    return validate_ohlcv_contract(market_candle_to_candle(market_candle))


def quality_allows_direct_entry(quality_flag: bool | str) -> bool:
    return quality_flag is True


def validate_indicator_result(result: IndicatorResult) -> ContractCheck:
    if result.quality_flag in {False, "stale"}:
        return ContractCheck("indicator_result", False, "indicator quality does not allow main-chain use")
    missing = sorted(set(INDICATOR_REQUIRED_OUTPUTS.get(result.name.upper(), [])) - set(result.value))
    if missing:
        return ContractCheck("indicator_result", False, f"missing indicator fields: {missing}")
    return ContractCheck("indicator_result", True, "indicator result approved")


def validate_strategy_context(context: StrategyContext) -> ContractCheck:
    if context.quality_flag in {False, "stale"}:
        return ContractCheck("strategy_context", False, "strategy context quality does not allow direct entry")
    if not context.symbol or context.timestamp <= 0:
        return ContractCheck("strategy_context", False, "symbol and positive timestamp are required")
    return ContractCheck("strategy_context", True, "strategy context approved")


def validate_required_fields(payload: dict, required_fields: list[str], name: str) -> ContractCheck:
    missing = sorted(field for field in required_fields if field not in payload)
    if missing:
        return ContractCheck(name, False, f"missing required fields: {missing}")
    return ContractCheck(name, True, f"{name} fields approved")


def validate_timeframe_utc_alignment(candle: Candle, base_close_time: int) -> ContractCheck:
    timeframe = normalize_timeframe(candle.timeframe)
    if timeframe not in TIMEFRAME_SECONDS:
        return ContractCheck("timeframe_alignment", False, f"unsupported timeframe: {candle.timeframe}")
    seconds = TIMEFRAME_SECONDS[timeframe]
    if candle.open_time % seconds != 0 or candle.close_time % seconds != 0:
        return ContractCheck("timeframe_alignment", False, "candle is not aligned to UTC timeframe grid")
    if candle.close_time > base_close_time:
        return ContractCheck("timeframe_alignment", False, "future data leakage is not allowed")
    return ContractCheck("timeframe_alignment", True, "candle is UTC aligned and closed")


def validate_indicator_input(candles: list[Candle]) -> ContractCheck:
    if not candles:
        return ContractCheck("indicator_input", False, "candles must not be empty")
    first_symbol = candles[0].symbol
    first_timeframe = normalize_timeframe(candles[0].timeframe)
    previous_open_time = -1
    for item in candles:
        if item.symbol != first_symbol:
            return ContractCheck("indicator_input", False, "candles must use one symbol")
        if normalize_timeframe(item.timeframe) != first_timeframe:
            return ContractCheck("indicator_input", False, "candles must use one timeframe")
        if item.open_time <= previous_open_time:
            return ContractCheck("indicator_input", False, "candles must be ordered by open_time")
        check = validate_ohlcv_contract(item)
        if not check.passed:
            return ContractCheck("indicator_input", False, check.reason)
        previous_open_time = item.open_time
    return ContractCheck("indicator_input", True, "candles: list[OHLCV] approved")


def judge_cvd_divergence(price_delta: float, cvd_delta: float) -> str:
    if price_delta > 0 and cvd_delta < 0:
        return "BEARISH"
    if price_delta < 0 and cvd_delta > 0:
        return "BULLISH"
    return "NONE"


def build_cvd_contract_points(candles: list[Candle]) -> list[CVDPoint]:
    total = 0.0
    previous_cumulative = 0.0
    previous_close = None
    points = []
    for item in candles:
        sell_volume = max(item.volume - item.taker_buy_volume, 0.0)
        delta = item.taker_buy_volume - sell_volume
        total += delta
        slope = total - previous_cumulative if points else 0.0
        price_delta = 0.0 if previous_close is None else item.close - previous_close
        points.append(
            CVDPoint(
                close_time=item.close_time,
                cumulative=total,
                delta=delta,
                slope=slope,
                divergence=judge_cvd_divergence(price_delta, delta),
            )
        )
        previous_cumulative = total
        previous_close = item.close
    return points
""",
    "src/data/market_data_loader.py": """
from __future__ import annotations

from src.core.models import Candle


class MarketDataLoader:
    def __init__(self, client=None):
        self.client = client

    def get_klines(self, symbol: str, timeframe: str, limit: int = 500) -> list[Candle]:
        if self.client is None:
            return []
        rows = self.client.get_klines(symbol, timeframe, limit=limit)
        candles: list[Candle] = []
        for row in rows:
            candles.append(
                Candle(
                    symbol=symbol,
                    timeframe=timeframe,
                    open_time=int(row[0]),
                    open=float(row[1]),
                    high=float(row[2]),
                    low=float(row[3]),
                    close=float(row[4]),
                    volume=float(row[5]),
                    close_time=int(row[6]),
                    quote_volume=float(row[7]) if len(row) > 7 else 0.0,
                    trade_count=int(row[8]) if len(row) > 8 else 0,
                    taker_buy_volume=float(row[9]) if len(row) > 9 else 0.0,
                )
            )
        return candles
""",
    "src/data/universe_filter.py": """
from __future__ import annotations

from dataclasses import dataclass, replace


UNIVERSE_SCOPE = "binance_usdt_perpetual"
MAX_SYMBOLS = 20
MAX_SYMBOLS_HARD_CAP = 30
RECOMMENDED_MIN_24H_VOLUME_USD = 300_000_000
MIN_LISTING_DAYS = 365
MAX_SPREAD_PCT = 0.05
MAX_MISSING_BAR_RATIO = 0.005
UPDATE_FREQUENCY = "weekly"
REQUIRED_TIMEFRAMES = ("15m", "30m", "1h", "4h")
UNIVERSE_STATUSES = ("ACTIVE", "SUSPENDED", "REMOVED")
MEME_POLICY = "exclude_by_default_even_if_large_cap"


TIER_A = {"BTCUSDT", "ETHUSDT"}
TIER_B = {"BNBUSDT", "SOLUSDT", "XRPUSDT"}
DEFAULT_EXCLUDED_MEME = {"DOGEUSDT", "SHIBUSDT", "PEPEUSDT", "FLOKIUSDT"}


@dataclass(frozen=True)
class UniverseCheck:
    passed: bool
    reason: str


@dataclass(frozen=True)
class UniverseCandidate:
    symbol: str
    market_cap_rank: int
    volume_24h: float
    price: float
    listed_days: int
    is_meme: bool = False
    delisting: bool = False
    contract_type: str = "USDT_PERPETUAL"
    quote_asset: str = "USDT"
    volume_rank: int = 0
    spread_pct: float = 0.0
    missing_bar_ratio: float = 0.0
    timeframes: tuple[str, ...] = REQUIRED_TIMEFRAMES
    monitoring_tag: bool = False
    abnormal_wick_count: int = 0

    def with_updates(self, **updates) -> "UniverseCandidate":
        return replace(self, **updates)


@dataclass(frozen=True)
class UniverseMember:
    symbol: str
    market_cap_rank: int
    volume_rank: int
    status: str
    added_time: int
    removed_time: int | None
    version: str
    reason: str


@dataclass(frozen=True)
class UniverseSnapshot:
    version: str
    members: list[UniverseMember]
    created_at: int
    effective_from: int
    effective_to: int | None
    update_reason: str

    def active_symbols(self) -> list[str]:
        return [member.symbol for member in self.members if member.status == "ACTIVE"]


def normalize_symbol(symbol: str) -> str:
    return symbol.strip().upper()


def filter_symbols(symbols: list[str], max_symbols: int = 20) -> list[str]:
    cleaned = []
    for symbol in symbols:
        value = normalize_symbol(symbol)
        if value.endswith("USDT") and value not in cleaned:
            cleaned.append(value)
    return cleaned[:max_symbols]


def filter_universe(
    candidates: list[UniverseCandidate],
    max_symbols: int = 20,
    min_volume_24h: float = 50_000_000,
    min_listed_days: int = 60,
) -> list[UniverseCandidate]:
    valid = []
    for candidate in candidates:
        symbol = normalize_symbol(candidate.symbol)
        adjusted = candidate.with_updates(symbol=symbol)
        check = validate_candidate(adjusted)
        if not check.passed:
            continue
        if adjusted.market_cap_rank > max_symbols:
            continue
        if adjusted.volume_24h < min_volume_24h:
            continue
        if adjusted.listed_days < min_listed_days:
            continue
        valid.append(adjusted)
    return sorted(valid, key=lambda item: item.market_cap_rank)[:max_symbols]


def validate_candidate(candidate: UniverseCandidate) -> UniverseCheck:
    symbol = normalize_symbol(candidate.symbol)
    if not symbol.endswith("USDT") or candidate.quote_asset != "USDT":
        return UniverseCheck(False, "only USDT symbols are allowed")
    if candidate.contract_type != "USDT_PERPETUAL":
        return UniverseCheck(False, "only USDT perpetual contracts are allowed")
    if candidate.market_cap_rank > MAX_SYMBOLS_HARD_CAP:
        return UniverseCheck(False, "market cap rank outside hard cap")
    if candidate.volume_24h < RECOMMENDED_MIN_24H_VOLUME_USD:
        return UniverseCheck(False, "24h volume below V1 threshold")
    if candidate.listed_days < MIN_LISTING_DAYS:
        return UniverseCheck(False, "listing age below V1 threshold")
    if candidate.spread_pct > MAX_SPREAD_PCT:
        return UniverseCheck(False, "spread too wide")
    if candidate.missing_bar_ratio > MAX_MISSING_BAR_RATIO:
        return UniverseCheck(False, "missing bar ratio too high")
    if set(REQUIRED_TIMEFRAMES) - set(candidate.timeframes):
        return UniverseCheck(False, "missing required timeframe history")
    if candidate.delisting or candidate.monitoring_tag:
        return UniverseCheck(False, "delisting or monitoring risk")
    if candidate.is_meme or symbol in DEFAULT_EXCLUDED_MEME:
        return UniverseCheck(False, MEME_POLICY)
    if candidate.abnormal_wick_count > 0:
        return UniverseCheck(False, "abnormal wick risk")
    return UniverseCheck(True, "candidate approved")


def build_universe_snapshot(version: str, members: list[UniverseMember], created_at: int) -> UniverseSnapshot:
    return UniverseSnapshot(
        version=version,
        members=members,
        created_at=created_at,
        effective_from=created_at,
        effective_to=None,
        update_reason="weekly_refresh",
    )


def validate_snapshot_for_backtest(snapshot: UniverseSnapshot, backtest_start: int) -> UniverseCheck:
    if snapshot.effective_from > backtest_start:
        return UniverseCheck(False, "snapshot starts after backtest period")
    if snapshot.effective_to is not None and snapshot.effective_to < backtest_start:
        return UniverseCheck(False, "snapshot ended before backtest period")
    return UniverseCheck(True, "historical universe snapshot approved")


def get_risk_tier(symbol: str) -> str:
    value = normalize_symbol(symbol)
    if value in TIER_A:
        return "A"
    if value in TIER_B:
        return "B"
    return "C"


def max_position_multiplier(symbol: str) -> float:
    tier = get_risk_tier(symbol)
    if tier == "A":
        return 2.0
    if tier == "B":
        return 1.0
    return 0.75


def choose_by_correlation_preference(symbols: list[str]) -> list[str]:
    normalized = filter_symbols(symbols, max_symbols=len(symbols))
    if "BTCUSDT" in normalized and "ETHUSDT" in normalized:
        normalized = [symbol for symbol in normalized if symbol != "ETHUSDT"]
    return normalized
""",
    "src/indicators/__init__.py": '"""Technical indicator functions."""',
    "src/indicators/atr.py": """
from __future__ import annotations

from src.core.models import Candle


def atr(candles: list[Candle], period: int = 14) -> float | None:
    if len(candles) < period + 1:
        return None
    ranges = []
    for prev, cur in zip(candles[-period - 1 : -1], candles[-period:]):
        ranges.append(max(cur.high - cur.low, abs(cur.high - prev.close), abs(cur.low - prev.close)))
    return sum(ranges) / period
""",
    "src/indicators/boll.py": """
from __future__ import annotations

import statistics


def bollinger(values: list[float], period: int = 20, std_mult: float = 2.0) -> tuple[float, float, float] | None:
    if len(values) < period:
        return None
    window = values[-period:]
    mid = sum(window) / period
    std = statistics.pstdev(window)
    return mid, mid + std_mult * std, mid - std_mult * std
""",
    "src/indicators/cci.py": """
from __future__ import annotations

from src.core.models import Candle


def cci(candles: list[Candle], period: int = 20) -> float | None:
    if len(candles) < period:
        return None
    typical = [(c.high + c.low + c.close) / 3 for c in candles[-period:]]
    avg = sum(typical) / period
    mean_dev = sum(abs(value - avg) for value in typical) / period
    if mean_dev == 0:
        return 0.0
    return (typical[-1] - avg) / (0.015 * mean_dev)
""",
    "src/indicators/cvd.py": """
from __future__ import annotations

from src.core.models import Candle


def cvd_delta(taker_buy_volume: float, total_volume: float) -> float:
    sell_volume = max(total_volume - taker_buy_volume, 0.0)
    return taker_buy_volume - sell_volume


def cumulative_cvd(candles: list[Candle]) -> list[float]:
    total = 0.0
    values: list[float] = []
    for candle in candles:
        total += cvd_delta(candle.taker_buy_volume, candle.volume)
        values.append(total)
    return values
""",
    "src/indicators/macd.py": """
from __future__ import annotations


def ema(values: list[float], period: int) -> list[float]:
    if not values:
        return []
    alpha = 2 / (period + 1)
    result = [values[0]]
    for value in values[1:]:
        result.append(alpha * value + (1 - alpha) * result[-1])
    return result


def macd(values: list[float], fast: int = 12, slow: int = 26, signal: int = 9) -> tuple[float, float, float] | None:
    if len(values) < slow:
        return None
    fast_ema = ema(values, fast)
    slow_ema = ema(values, slow)
    line = [f - s for f, s in zip(fast_ema, slow_ema)]
    signal_line = ema(line, signal)
    return line[-1], signal_line[-1], line[-1] - signal_line[-1]
""",
    "src/indicators/rsi.py": """
from __future__ import annotations


def rsi(values: list[float], period: int = 14) -> float | None:
    if len(values) < period + 1:
        return None
    gains = []
    losses = []
    for prev, cur in zip(values[-period - 1 : -1], values[-period:]):
        change = cur - prev
        gains.append(max(change, 0.0))
        losses.append(abs(min(change, 0.0)))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - 100 / (1 + rs)
""",
    "src/indicators/indicator_spec.py": """
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from src.data.data_contract import INDICATOR_REQUIRED_OUTPUTS, QUALITY_FLAGS


DEFAULT_INDICATOR_PARAMS = {
    "MACD": {"fast": 12, "slow": 26, "signal": 9},
    "CCI": {"period": 20},
    "BOLL": {"period": 20, "std": 2.0},
    "RSI": {"period": 14},
    "CVD": {},
    "ATR": {"period": 14},
}

INDICATOR_NAMES = ("MACD", "CCI", "BOLL", "RSI", "CVD", "ATR")
INDICATOR_RESPONSIBILITIES = {
    "MACD": "trend_momentum",
    "CCI": "strength_deviation_recovery",
    "BOLL": "volatility_structure",
    "RSI": "pullback_quality_overheat",
    "CVD": "active_buy_sell_pressure",
    "ATR": "volatility_stop_position_risk",
}
INDICATOR_INPUT_FIELDS = (
    "symbol",
    "timeframe",
    "open_time",
    "close_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "quote_volume",
    "trade_count",
    "taker_buy_base_volume",
    "taker_buy_quote_volume",
    "is_closed",
    "quality_flag",
)
INDICATOR_OUTPUT_FIELDS = (
    "name",
    "symbol",
    "timeframe",
    "timestamp",
    "value",
    "signal",
    "trend",
    "strength",
    "quality_flag",
    "metadata",
)
INDICATOR_CONFLICT_PRIORITY = (
    "data_quality",
    "cvd_divergence",
    "macd_trend_direction",
    "cci_strength",
    "boll_structure",
    "rsi_timing",
    "atr_risk",
)
INDICATOR_PRIORITY = INDICATOR_CONFLICT_PRIORITY
TIMEFRAME_INDICATOR_MAP = {
    "4h": ("MACD", "BOLL", "CCI"),
    "1h": ("MACD", "CCI", "CVD", "RSI"),
    "30m": ("MACD", "BOLL", "CCI", "CVD"),
    "15m": ("RSI", "MACD", "CVD", "BOLL"),
}
INDICATOR_CACHE_FIELDS = ("version", "timestamp", "timeframe", "indicator", "quality_flag")
INDICATOR_FORBIDDEN_USAGES = {
    "MACD": ("sole_entry", "position_size", "unfinished_bar_final", "execution_reinterpretation"),
    "CCI": ("sole_direction", "risk_control", "only_trend_proof"),
    "BOLL": ("sole_direction", "position_size", "replace_trend_logic"),
    "RSI": ("replace_trend", "replace_fund_flow", "guaranteed_reversal"),
    "CVD": ("sole_direction", "replace_price_structure", "force_signal_without_data", "execution_priority"),
    "ATR": ("direction", "long_short_signal", "replace_trend", "non_risk_module_mixing"),
}
GLOBAL_FORBIDDEN_INDICATOR_ACTIONS = (
    "create_order",
    "final_position_size",
    "bypass_state_machine",
    "must_trade",
)


@dataclass(frozen=True)
class IndicatorSpecCheck:
    passed: bool
    reason: str


def required_outputs_for(indicator: str) -> tuple[str, ...]:
    return tuple(INDICATOR_REQUIRED_OUTPUTS.get(indicator.upper(), ()))


def quality_allows_signal_use(quality_flag: bool | str) -> bool:
    return quality_flag in (True, "degraded")


def validate_indicator_input_contract(payload: Mapping[str, object]) -> IndicatorSpecCheck:
    missing = sorted(field for field in INDICATOR_INPUT_FIELDS if field not in payload)
    if missing:
        return IndicatorSpecCheck(False, f"missing indicator input fields: {missing}")
    if payload["is_closed"] is not True:
        return IndicatorSpecCheck(False, "indicator input candle must be closed")
    if payload["quality_flag"] not in QUALITY_FLAGS:
        return IndicatorSpecCheck(False, "unsupported quality_flag")
    if not quality_allows_signal_use(payload["quality_flag"]):
        return IndicatorSpecCheck(False, "quality_flag cannot drive indicator signal use")
    return IndicatorSpecCheck(True, "indicator input contract approved")


def validate_indicator_usage(indicator: str, usage: str) -> tuple[bool, str]:
    key = indicator.upper()
    if key not in INDICATOR_NAMES:
        return False, f"unknown indicator: {indicator}"
    normalized_usage = usage.strip().lower()
    if normalized_usage in GLOBAL_FORBIDDEN_INDICATOR_ACTIONS:
        return False, f"{normalized_usage} is globally forbidden for indicator layer"
    if normalized_usage in INDICATOR_FORBIDDEN_USAGES.get(key, ()):
        return False, f"{key} usage forbidden: {normalized_usage}"
    return True, f"{key} allowed for {normalized_usage}"


def classify_rsi(value: float) -> str:
    if value > 70:
        return "overheated"
    if value < 30:
        return "oversold"
    if 40 <= value <= 60:
        return "range"
    return "neutral"


def classify_cci(value: float) -> str:
    if value > 100:
        return "strong"
    if value < -100:
        return "weak"
    return "neutral"
""",
    "src/indicators/indicator_engine.py": """
from __future__ import annotations

from src.core.models import Candle, IndicatorSnapshot
from src.data.data_contract import IndicatorResult, MarketCandle, market_candle_to_candle
from src.indicators.atr import atr
from src.indicators.boll import bollinger
from src.indicators.cci import cci
from src.indicators.cvd import cumulative_cvd, cvd_delta
from src.indicators.indicator_spec import quality_allows_signal_use
from src.indicators.macd import macd
from src.indicators.rsi import rsi


def compute_indicator_snapshot(candles: list[Candle]) -> IndicatorSnapshot:
    if not candles:
        raise ValueError("candles must not be empty")

    last = candles[-1]
    closes = [candle.close for candle in candles]
    macd_values = macd(closes)
    boll_values = bollinger(closes)
    cvd_values = cumulative_cvd(candles)

    return IndicatorSnapshot(
        symbol=last.symbol,
        timeframe=last.timeframe,
        close_time=last.close_time,
        macd=macd_values[0] if macd_values else None,
        macd_signal=macd_values[1] if macd_values else None,
        macd_hist=macd_values[2] if macd_values else None,
        cci=cci(candles),
        rsi=rsi(closes),
        boll_mid=boll_values[0] if boll_values else None,
        boll_upper=boll_values[1] if boll_values else None,
        boll_lower=boll_values[2] if boll_values else None,
        atr=atr(candles),
        cvd=cvd_values[-1] if cvd_values else None,
        cvd_delta=cvd_delta(last.taker_buy_volume, last.volume),
    )


def compute_indicator_results(candles: list[MarketCandle]) -> list[IndicatorResult]:
    if not candles:
        raise ValueError("candles must not be empty")
    _validate_market_candles_for_indicator_results(candles)
    core_candles = [market_candle_to_candle(item) for item in candles]
    snapshot = compute_indicator_snapshot(core_candles)
    closes = [item.close for item in core_candles]
    quality_flag = _combined_quality_flag(candles)

    return [
        _build_macd_result(snapshot, closes, quality_flag),
        _build_cci_result(snapshot, core_candles, quality_flag),
        _build_boll_result(snapshot, closes, quality_flag),
        _build_rsi_result(snapshot, closes, quality_flag),
        _build_cvd_result(snapshot, core_candles, quality_flag),
        _build_atr_result(snapshot, core_candles, quality_flag),
    ]


def _validate_market_candles_for_indicator_results(candles: list[MarketCandle]) -> None:
    first_symbol = candles[0].symbol
    first_timeframe = candles[0].timeframe
    previous_open_time = -1
    for candle in candles:
        if candle.symbol != first_symbol:
            raise ValueError("indicator candles must use one symbol")
        if candle.timeframe != first_timeframe:
            raise ValueError("indicator candles must use one timeframe")
        if candle.open_time <= previous_open_time:
            raise ValueError("indicator candles must be ordered by open_time")
        if candle.is_closed is not True:
            raise ValueError("indicator candles must be closed")
        if not quality_allows_signal_use(candle.quality_flag):
            raise ValueError("indicator candle quality cannot drive indicator signal use")
        previous_open_time = candle.open_time


def _combined_quality_flag(candles: list[MarketCandle]) -> bool | str:
    if any(item.quality_flag == "degraded" for item in candles):
        return "degraded"
    return True


def _base_result(
    snapshot: IndicatorSnapshot,
    name: str,
    value: dict,
    signal: str,
    trend: str,
    strength: float,
    quality_flag: bool | str,
) -> IndicatorResult:
    return IndicatorResult(
        name=name,
        symbol=snapshot.symbol,
        timeframe=snapshot.timeframe,
        value=value,
        signal=signal,
        trend=trend,
        strength=max(0.0, min(float(strength), 1.0)),
        timestamp=snapshot.close_time,
        metadata=dict(value),
        quality_flag=quality_flag,
    )


def _build_macd_result(snapshot: IndicatorSnapshot, closes: list[float], quality_flag: bool | str) -> IndicatorResult:
    previous = macd(closes[:-1]) if len(closes) > 1 else None
    histogram = snapshot.macd_hist if snapshot.macd_hist is not None else 0.0
    previous_histogram = previous[2] if previous else histogram
    slope = histogram - previous_histogram
    if snapshot.macd is not None and snapshot.macd_signal is not None and snapshot.macd > snapshot.macd_signal:
        cross_state = "golden_cross"
    elif snapshot.macd is not None and snapshot.macd_signal is not None and snapshot.macd < snapshot.macd_signal:
        cross_state = "death_cross"
    else:
        cross_state = "neutral"
    trend = "UP" if histogram > 0 else "DOWN" if histogram < 0 else "NEUTRAL"
    signal = "BULLISH" if histogram > 0 and slope >= 0 else "BEARISH" if histogram < 0 and slope <= 0 else "NEUTRAL"
    value = {
        "macd_line": snapshot.macd,
        "signal_line": snapshot.macd_signal,
        "histogram": snapshot.macd_hist,
        "histogram_slope": slope,
        "cross_state": cross_state,
    }
    return _base_result(snapshot, "MACD", value, signal, trend, min(abs(histogram), 1.0), quality_flag)


def _build_cci_result(snapshot: IndicatorSnapshot, candles: list[Candle], quality_flag: bool | str) -> IndicatorResult:
    previous = cci(candles[:-1]) if len(candles) > 1 else None
    current = snapshot.cci if snapshot.cci is not None else 0.0
    slope = current - (previous if previous is not None else current)
    extreme = abs(current) > 150
    recovery = previous is not None and abs(previous) > 100 and abs(current) <= 100
    trend = "UP" if current > 100 else "DOWN" if current < -100 else "NEUTRAL"
    signal = "STRONG" if current > 100 else "WEAK" if current < -100 else "NEUTRAL"
    value = {"cci": snapshot.cci, "cci_slope": slope, "extreme_flag": extreme, "recovery_flag": recovery}
    return _base_result(snapshot, "CCI", value, signal, trend, min(abs(current) / 200, 1.0), quality_flag)


def _build_boll_result(snapshot: IndicatorSnapshot, closes: list[float], quality_flag: bool | str) -> IndicatorResult:
    previous = bollinger(closes[:-1]) if len(closes) > 1 else None
    width = 0.0
    previous_width = 0.0
    if snapshot.boll_upper is not None and snapshot.boll_lower is not None and snapshot.boll_mid:
        width = (snapshot.boll_upper - snapshot.boll_lower) / snapshot.boll_mid
    if previous and previous[0]:
        previous_width = (previous[1] - previous[2]) / previous[0]
    expansion = width > previous_width
    contraction = width < previous_width
    close = closes[-1]
    if snapshot.boll_upper is not None and close >= snapshot.boll_upper:
        position = "above_upper"
    elif snapshot.boll_lower is not None and close <= snapshot.boll_lower:
        position = "below_lower"
    elif snapshot.boll_mid is not None and close >= snapshot.boll_mid:
        position = "above_middle"
    else:
        position = "below_middle"
    trend = "UP" if position in {"above_upper", "above_middle"} else "DOWN"
    signal = "EXPANSION" if expansion else "CONTRACTION" if contraction else "NEUTRAL"
    value = {
        "middle_band": snapshot.boll_mid,
        "upper_band": snapshot.boll_upper,
        "lower_band": snapshot.boll_lower,
        "band_width": width,
        "band_expansion_flag": expansion,
        "band_contraction_flag": contraction,
        "price_position": position,
    }
    return _base_result(snapshot, "BOLL", value, signal, trend, min(width, 1.0), quality_flag)


def _build_rsi_result(snapshot: IndicatorSnapshot, closes: list[float], quality_flag: bool | str) -> IndicatorResult:
    previous = rsi(closes[:-1]) if len(closes) > 1 else None
    current = snapshot.rsi if snapshot.rsi is not None else 50.0
    slope = current - (previous if previous is not None else current)
    overbought = current > 70
    oversold = current < 30
    midline_state = "above_midline" if current > 55 else "below_midline" if current < 45 else "near_midline"
    trend = "UP" if current > 55 else "DOWN" if current < 45 else "NEUTRAL"
    signal = "OVERBOUGHT" if overbought else "OVERSOLD" if oversold else "NEUTRAL"
    value = {
        "rsi": snapshot.rsi,
        "rsi_slope": slope,
        "overbought_flag": overbought,
        "oversold_flag": oversold,
        "midline_state": midline_state,
    }
    return _base_result(snapshot, "RSI", value, signal, trend, abs(current - 50) / 50, quality_flag)


def _build_cvd_result(snapshot: IndicatorSnapshot, candles: list[Candle], quality_flag: bool | str) -> IndicatorResult:
    cvd_values = cumulative_cvd(candles)
    previous_cvd = cvd_values[-2] if len(cvd_values) > 1 else cvd_values[-1]
    current_cvd = cvd_values[-1]
    slope = current_cvd - previous_cvd
    price_delta = candles[-1].close - candles[-2].close if len(candles) > 1 else 0.0
    divergence = (price_delta > 0 and slope < 0) or (price_delta < 0 and slope > 0)
    buy_pressure = max(snapshot.cvd_delta or 0.0, 0.0)
    sell_pressure = abs(min(snapshot.cvd_delta or 0.0, 0.0))
    trend = "UP" if slope > 0 else "DOWN" if slope < 0 else "NEUTRAL"
    signal = "DIVERGENCE" if divergence else "BUY_PRESSURE" if slope > 0 else "SELL_PRESSURE" if slope < 0 else "NEUTRAL"
    value = {
        "cvd": snapshot.cvd,
        "cvd_delta": snapshot.cvd_delta,
        "cvd_slope": slope,
        "cvd_divergence_flag": divergence,
        "buy_pressure": buy_pressure,
        "sell_pressure": sell_pressure,
    }
    return _base_result(snapshot, "CVD", value, signal, trend, min(abs(slope) / 100, 1.0), quality_flag)


def _build_atr_result(snapshot: IndicatorSnapshot, candles: list[Candle], quality_flag: bool | str) -> IndicatorResult:
    current_atr = snapshot.atr if snapshot.atr is not None else 0.0
    close = candles[-1].close
    atr_pct = current_atr / close if close else 0.0
    if atr_pct >= 0.05:
        volatility_state = "high"
    elif atr_pct <= 0.01:
        volatility_state = "low"
    else:
        volatility_state = "normal"
    value = {"atr": snapshot.atr, "atr_pct": atr_pct, "volatility_state": volatility_state}
    return _base_result(snapshot, "ATR", value, "RISK_ONLY", "NEUTRAL", min(atr_pct * 10, 1.0), quality_flag)
""",
    "src/context/__init__.py": '"""Market context builders."""',
    "src/context/multi_tf_context.py": """
from __future__ import annotations

from src.context.multi_tf_rules import MultiTimeframeDecision, build_multi_tf_decision
from src.core.models import IndicatorSnapshot


def build_context(tf_1h: str, tf_30m: str, tf_15m: str, tf_4h: str = "NEUTRAL") -> dict:
    return {
        "context": tf_4h,
        "permission": tf_1h,
        "quality": tf_30m,
        "trigger": tf_15m,
    }


def build_context_from_snapshots(
    tf_4h: IndicatorSnapshot,
    tf_1h: IndicatorSnapshot,
    tf_30m: IndicatorSnapshot,
    tf_15m: IndicatorSnapshot,
    previous_15m_rsi: float | None = None,
) -> MultiTimeframeDecision:
    return build_multi_tf_decision(tf_4h, tf_1h, tf_30m, tf_15m, previous_15m_rsi)
""",
    "src/context/multi_tf_rules.py": """
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from src.core.models import IndicatorSnapshot


TIMEFRAME_ROLES = {
    "4h": "background_reference",
    "1h": "direction_confirmation",
    "30m": "trend_quality_confirmation",
    "15m": "execution_trigger",
}
TIMEFRAME_PRIORITY = (
    "data_quality",
    "risk_constraints",
    "4h_background",
    "1h_direction",
    "30m_quality",
    "15m_trigger",
    "position_executability",
    "execution_layer",
)
TIMEFRAME_OUTPUT_FIELDS = (
    "symbol",
    "timeframe",
    "timestamp",
    "state",
    "confidence",
    "reason",
    "sub_reasons",
    "quality_flag",
    "metadata",
)
TIMEFRAME_FORBIDDEN_ACTIONS = (
    "4h_hard_veto",
    "15m_direction_override",
    "independent_timeframe_commands",
    "unfinished_high_tf_final_signal",
    "nested_patch_conditions",
    "execution_reinterprets_context",
)
TIMEFRAME_STATE_SETS = {
    "4h": ("BULL", "BEAR", "NEUTRAL"),
    "1h": ("LONG_ALLOWED", "SHORT_ALLOWED", "NO_TRADE"),
    "30m": ("CONFIRMED", "WEAK", "INVALID", "TRANSITION"),
    "15m": ("DIRECT", "PROBE", "WAIT", "NO_TRADE"),
}


class TimeframeDecision(str, Enum):
    BULL = "BULL"
    BEAR = "BEAR"
    NEUTRAL = "NEUTRAL"
    LONG_ALLOWED = "LONG_ALLOWED"
    SHORT_ALLOWED = "SHORT_ALLOWED"
    NO_TRADE = "NO_TRADE"
    CONFIRMED = "CONFIRMED"
    INVALID = "INVALID"
    TRANSITION = "TRANSITION"
    LONG_CONFIRM = "LONG_CONFIRM"
    SHORT_CONFIRM = "SHORT_CONFIRM"
    WEAK = "WEAK"
    LONG_TRIGGER = "LONG_TRIGGER"
    SHORT_TRIGGER = "SHORT_TRIGGER"
    DIRECT = "DIRECT"
    PROBE = "PROBE"
    WAIT = "WAIT"


@dataclass(frozen=True)
class TimeframeRuleCheck:
    passed: bool
    reason: str


@dataclass(frozen=True)
class TimeframeResult:
    symbol: str
    timeframe: str
    timestamp: int
    state: str
    confidence: float
    reason: str
    sub_reasons: tuple[str, ...]
    quality_flag: bool | str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class MultiTimeframeDecision:
    symbol: str
    signal_type: str
    side: str
    context_4h: str
    permission_1h: str
    quality_30m: str
    trigger_15m: str
    reason: str
    quality_flag: bool | str = True
    timeframe_results: tuple[TimeframeResult, ...] = ()


def evaluate_4h_context(snapshot: IndicatorSnapshot) -> TimeframeDecision:
    if (snapshot.macd or 0) > 0 and (snapshot.cci or 0) > 100 and (snapshot.cvd_delta or 0) >= 0:
        return TimeframeDecision.BULL
    if (snapshot.macd or 0) < 0 and (snapshot.cci or 0) < -100 and (snapshot.cvd_delta or 0) <= 0:
        return TimeframeDecision.BEAR
    return TimeframeDecision.NEUTRAL


def evaluate_1h_permission(snapshot: IndicatorSnapshot) -> TimeframeDecision:
    if (snapshot.macd or 0) > 0 and (snapshot.cci or 0) > 100 and (snapshot.cvd_delta or 0) > 0:
        return TimeframeDecision.LONG_ALLOWED
    if (snapshot.macd or 0) < 0 and (snapshot.cci or 0) < -100 and (snapshot.cvd_delta or 0) < 0:
        return TimeframeDecision.SHORT_ALLOWED
    return TimeframeDecision.NO_TRADE


def evaluate_30m_quality(snapshot: IndicatorSnapshot) -> TimeframeDecision:
    if (snapshot.cci or 0) > 100:
        return TimeframeDecision.LONG_CONFIRM
    if (snapshot.cci or 0) < -100:
        return TimeframeDecision.SHORT_CONFIRM
    return TimeframeDecision.WEAK


def evaluate_30m_quality_state(snapshot: IndicatorSnapshot) -> TimeframeDecision:
    directional = evaluate_30m_quality(snapshot)
    if directional in {TimeframeDecision.LONG_CONFIRM, TimeframeDecision.SHORT_CONFIRM}:
        return TimeframeDecision.CONFIRMED
    if (snapshot.macd_hist is not None and abs(snapshot.macd_hist) < 0.000001) or snapshot.cci is None:
        return TimeframeDecision.TRANSITION
    return TimeframeDecision.WEAK


def evaluate_15m_trigger(snapshot: IndicatorSnapshot, previous_rsi: float | None = None) -> TimeframeDecision:
    rsi = snapshot.rsi
    cvd_delta = snapshot.cvd_delta or 0
    if rsi is None or previous_rsi is None:
        return TimeframeDecision.WAIT
    if previous_rsi <= 50 < rsi and cvd_delta > 0:
        return TimeframeDecision.LONG_TRIGGER
    if previous_rsi >= 50 > rsi and cvd_delta < 0:
        return TimeframeDecision.SHORT_TRIGGER
    return TimeframeDecision.WAIT


def build_timeframe_results(
    tf_4h: IndicatorSnapshot,
    tf_1h: IndicatorSnapshot,
    tf_30m: IndicatorSnapshot,
    tf_15m: IndicatorSnapshot,
    previous_15m_rsi: float | None = None,
    quality_flags: Mapping[str, bool | str] | None = None,
) -> tuple[TimeframeResult, ...]:
    flags = dict(quality_flags or {})
    context = evaluate_4h_context(tf_4h)
    permission = evaluate_1h_permission(tf_1h)
    quality = evaluate_30m_quality_state(tf_30m)
    trigger = evaluate_15m_trigger(tf_15m, previous_rsi=previous_15m_rsi)

    return (
        _timeframe_result(tf_4h, "4h", context.value, _confidence_from_snapshot(tf_4h), "4h_background", ("BACKGROUND",), flags.get("4h", True)),
        _timeframe_result(tf_1h, "1h", permission.value, _confidence_from_snapshot(tf_1h), "1h_direction", ("DIRECTION",), flags.get("1h", True)),
        _timeframe_result(
            tf_30m,
            "30m",
            quality.value,
            _confidence_from_snapshot(tf_30m),
            "30m_quality",
            (evaluate_30m_quality(tf_30m).value,),
            flags.get("30m", True),
            {"directional_quality": evaluate_30m_quality(tf_30m).value},
        ),
        _timeframe_result(tf_15m, "15m", _trigger_state_for_result(trigger), _confidence_from_snapshot(tf_15m), "15m_trigger", (trigger.value,), flags.get("15m", True)),
    )


def validate_timeframe_result(result: TimeframeResult) -> TimeframeRuleCheck:
    if result.timeframe not in TIMEFRAME_ROLES:
        return TimeframeRuleCheck(False, f"unsupported timeframe: {result.timeframe}")
    if result.quality_flag in {False, "stale"}:
        return TimeframeRuleCheck(False, "timeframe result quality cannot drive context")
    if result.state not in TIMEFRAME_STATE_SETS[result.timeframe]:
        return TimeframeRuleCheck(False, f"unsupported state for {result.timeframe}: {result.state}")
    if not 0 <= result.confidence <= 1:
        return TimeframeRuleCheck(False, "confidence must be between 0 and 1")
    return TimeframeRuleCheck(True, "timeframe result approved")


def build_multi_tf_decision(
    tf_4h: IndicatorSnapshot,
    tf_1h: IndicatorSnapshot,
    tf_30m: IndicatorSnapshot,
    tf_15m: IndicatorSnapshot,
    previous_15m_rsi: float | None = None,
    quality_flags: Mapping[str, bool | str] | None = None,
) -> MultiTimeframeDecision:
    results = build_timeframe_results(tf_4h, tf_1h, tf_30m, tf_15m, previous_15m_rsi, quality_flags)
    invalid = [item for item in results if not validate_timeframe_result(item).passed]
    context = evaluate_4h_context(tf_4h)
    permission = evaluate_1h_permission(tf_1h)
    quality = evaluate_30m_quality(tf_30m)
    trigger = evaluate_15m_trigger(tf_15m, previous_rsi=previous_15m_rsi)

    if invalid:
        return _decision(tf_15m.symbol, "NO_TRADE", "NONE", context, permission, quality, trigger, "data quality invalid", False, results)

    if permission == TimeframeDecision.LONG_ALLOWED:
        if quality == TimeframeDecision.SHORT_CONFIRM:
            return _decision(tf_15m.symbol, "NO_TRADE", "NONE", context, permission, quality, trigger, "direction conflict", True, results)
        if quality == TimeframeDecision.LONG_CONFIRM and trigger == TimeframeDecision.LONG_TRIGGER:
            if _background_conflicts(context, "LONG"):
                return _decision(tf_15m.symbol, "PROBE", "LONG", context, permission, quality, trigger, "4h conflict downgraded direct", True, results)
            return _decision(tf_15m.symbol, "DIRECT", "LONG", context, permission, quality, trigger, "long direct confirmed", True, results)
        if quality == TimeframeDecision.LONG_CONFIRM:
            return _decision(tf_15m.symbol, "PROBE", "LONG", context, permission, quality, trigger, "long higher timeframes confirmed", True, results)
        return _decision(tf_15m.symbol, "WAIT", "NONE", context, permission, quality, trigger, "waiting for 30m/15m confirmation", True, results)

    if permission == TimeframeDecision.SHORT_ALLOWED:
        if quality == TimeframeDecision.LONG_CONFIRM:
            return _decision(tf_15m.symbol, "NO_TRADE", "NONE", context, permission, quality, trigger, "direction conflict", True, results)
        if quality == TimeframeDecision.SHORT_CONFIRM and trigger == TimeframeDecision.SHORT_TRIGGER:
            if _background_conflicts(context, "SHORT"):
                return _decision(tf_15m.symbol, "PROBE", "SHORT", context, permission, quality, trigger, "4h conflict downgraded direct", True, results)
            return _decision(tf_15m.symbol, "DIRECT", "SHORT", context, permission, quality, trigger, "short direct confirmed", True, results)
        if quality == TimeframeDecision.SHORT_CONFIRM:
            return _decision(tf_15m.symbol, "PROBE", "SHORT", context, permission, quality, trigger, "short higher timeframes confirmed", True, results)
        return _decision(tf_15m.symbol, "WAIT", "NONE", context, permission, quality, trigger, "waiting for 30m/15m confirmation", True, results)

    return _decision(tf_15m.symbol, "NO_TRADE", "NONE", context, permission, quality, trigger, "1h direction not allowed", True, results)


def _timeframe_result(
    snapshot: IndicatorSnapshot,
    timeframe: str,
    state: str,
    confidence: float,
    reason: str,
    sub_reasons: tuple[str, ...],
    quality_flag: bool | str,
    metadata: dict[str, Any] | None = None,
) -> TimeframeResult:
    return TimeframeResult(
        symbol=snapshot.symbol,
        timeframe=timeframe,
        timestamp=snapshot.close_time,
        state=state,
        confidence=max(0.0, min(confidence, 1.0)),
        reason=reason,
        sub_reasons=sub_reasons,
        quality_flag=quality_flag,
        metadata=metadata or {},
    )


def _trigger_state_for_result(trigger: TimeframeDecision) -> str:
    if trigger in {TimeframeDecision.LONG_TRIGGER, TimeframeDecision.SHORT_TRIGGER}:
        return TimeframeDecision.DIRECT.value
    return TimeframeDecision.WAIT.value


def _confidence_from_snapshot(snapshot: IndicatorSnapshot) -> float:
    score = 0.0
    if snapshot.macd is not None:
        score += 0.25
    if snapshot.cci is not None:
        score += 0.25
    if snapshot.cvd_delta is not None:
        score += 0.25
    if snapshot.rsi is not None or snapshot.boll_mid is not None:
        score += 0.25
    return min(score, 1.0)


def _background_conflicts(context: TimeframeDecision, side: str) -> bool:
    return (side == "LONG" and context == TimeframeDecision.BEAR) or (
        side == "SHORT" and context == TimeframeDecision.BULL
    )


def _decision(
    symbol: str,
    signal_type: str,
    side: str,
    context: TimeframeDecision,
    permission: TimeframeDecision,
    quality: TimeframeDecision,
    trigger: TimeframeDecision,
    reason: str,
    quality_flag: bool | str,
    timeframe_results: tuple[TimeframeResult, ...],
) -> MultiTimeframeDecision:
    return MultiTimeframeDecision(
        symbol=symbol,
        signal_type=signal_type,
        side=side,
        context_4h=context.value,
        permission_1h=permission.value,
        quality_30m=quality.value,
        trigger_15m=trigger.value,
        reason=reason,
        quality_flag=quality_flag,
        timeframe_results=timeframe_results,
    )
""",
    "src/signals/__init__.py": '"""Signal generation boundary."""',
    "src/signals/signal_engine.py": """
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from src.core.constants import SIDE_LONG, SIDE_NONE, SIDE_SHORT


SIGNAL_TYPES = ["LONG", "SHORT", "WAIT", "NO_TRADE"]
SIGNAL_SIDES = [SIDE_LONG, SIDE_SHORT, SIDE_NONE]
ENTRY_MODES = ["PROBE", "DIRECT", "NONE"]
SIGNAL_LEVELS = ["NO_TRADE", "WAIT", "PROBE", "DIRECT"]

SIGNAL_DECISION_FLOW = [
    "read_multi_timeframe_context",
    "check_data_quality",
    "check_cooldown_state",
    "check_portfolio_risk",
    "judge_4h_background",
    "judge_1h_direction",
    "judge_30m_confirmation",
    "judge_15m_trigger",
    "judge_cvd_flow",
    "judge_macd_cci_rsi_boll_structure",
    "summarize_signal_result",
    "output_wait_probe_direct_or_no_trade",
    "record_evidence_fields",
]

TIMEFRAME_ROLES = {
    "4h": "market_background",
    "1h": "direction_permission",
    "30m": "trend_quality_confirmation",
    "15m": "entry_trigger_only",
}

INDICATOR_ROLES = {
    "MACD": ["trend_direction", "momentum_change", "cross", "weakening"],
    "CCI": ["trend_strength", "extreme_deviation", "mean_reversion", "recovery"],
    "BOLL": ["squeeze", "expansion", "midline_retest", "breakout_structure"],
    "RSI": ["overbought_oversold", "pullback_quality", "midline_recovery", "overheat"],
    "CVD": ["active_flow", "flow_direction", "divergence", "accumulation_distribution"],
    "ATR": ["volatility", "risk_context_only", "no_direction_decision"],
}

SCORE_COMPONENTS = ["trend_score", "confirm_score", "trigger_score", "flow_score", "volatility_score"]

SIGNAL_SUB_REASONS = [
    "TREND_ALIGNED",
    "TREND_CONFLICT",
    "MOMENTUM_STRONG",
    "MOMENTUM_WEAK",
    "FLOW_CONFIRMED",
    "FLOW_DIVERGENCE",
    "VOLATILITY_TOO_HIGH",
    "VOLATILITY_TOO_LOW",
    "TRIGGER_READY",
    "TRIGGER_NOT_READY",
    "RSI_OVERHEATED",
    "RSI_RECOVERY",
    "CCI_STRONG",
    "CCI_EXTREME",
    "BOLL_EXPANSION",
    "BOLL_CONTRACTION",
    "COOLDOWN_ACTIVE",
    "RISK_BLOCKED",
    "DATA_INVALID",
]

STATE_MACHINE_MAPPING = {
    "WAIT": "WATCH_*",
    "PROBE": "PROBE_*",
    "DIRECT": "DIRECT_*",
    "NO_TRADE": "FLAT_OR_KEEP_CURRENT",
}

SIGNAL_FORBIDDEN_ACTIONS = [
    "calculate_final_position_size",
    "set_stop_loss_or_take_profit",
    "submit_or_cancel_orders",
    "sync_positions_or_balances",
    "make_final_risk_verdict",
    "call_exchange_adapter",
    "rewrite_entry_mode_in_execution_layer",
]

SIGNAL_EVIDENCE_FIELDS = [
    "symbol",
    "timestamp",
    "signal_type",
    "signal_side",
    "entry_mode",
    "score",
    "confidence",
    "market_state_4h",
    "trend_state_1h",
    "confirm_state_30m",
    "trigger_state_15m",
    "macd_state",
    "cci_state",
    "boll_state",
    "rsi_state",
    "cvd_state",
    "atr_state",
    "reason",
    "sub_reasons",
]


@dataclass(frozen=True)
class SignalEngineContext:
    symbol: str
    timestamp: Any
    market_state_4h: str
    trend_state_1h: str
    confirm_state_30m: str
    trigger_state_15m: str
    indicators_15m: Mapping[str, Any]
    indicators_30m: Mapping[str, Any]
    indicators_1h: Mapping[str, Any]
    indicators_4h: Mapping[str, Any]
    risk_snapshot: Mapping[str, Any]
    position_snapshot: Mapping[str, Any]
    cooldown_state: Mapping[str, Any]
    quality_flag: bool


@dataclass(frozen=True)
class SignalScoreBreakdown:
    trend_score: float = 0.0
    confirm_score: float = 0.0
    trigger_score: float = 0.0
    flow_score: float = 0.0
    volatility_score: float = 0.0

    @property
    def total(self) -> float:
        return round(
            self.trend_score
            + self.confirm_score
            + self.trigger_score
            + self.flow_score
            + self.volatility_score,
            2,
        )


@dataclass(frozen=True)
class SignalResult:
    symbol: str
    timestamp: Any
    signal_type: str
    signal_side: str
    entry_mode: str
    score: float
    confidence: float
    reason: str
    sub_reasons: tuple[str, ...]
    required_state: str
    quality_flag: bool
    metadata: dict[str, Any]

    def __getitem__(self, key: str) -> Any:
        legacy = {
            "side": self.signal_side,
            "mode": self.entry_mode,
        }
        if key in legacy:
            return legacy[key]
        return self.to_dict()[key]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["sub_reasons"] = list(self.sub_reasons)
        payload["side"] = self.signal_side
        return payload


def generate_signal(context: Any) -> SignalResult:
    normalized = _normalize_context(context)
    side = _direction_side(normalized["trend_state_1h"])
    sub_reasons: list[str] = []
    score = SignalScoreBreakdown()

    if not normalized["quality_flag"]:
        return _build_result(normalized, "NO_TRADE", SIDE_NONE, "NONE", score, "DATA_INVALID", ["DATA_INVALID"])

    if _is_active(normalized["cooldown_state"]):
        return _build_result(normalized, "NO_TRADE", SIDE_NONE, "NONE", score, "COOLDOWN_ACTIVE", ["COOLDOWN_ACTIVE"])

    if _risk_blocked(normalized["risk_snapshot"]):
        return _build_result(normalized, "NO_TRADE", SIDE_NONE, "NONE", score, "RISK_BLOCKED", ["RISK_BLOCKED"])

    if side == SIDE_NONE:
        return _build_result(normalized, "NO_TRADE", SIDE_NONE, "NONE", score, "DIRECTION_NOT_ALLOWED", ["TREND_CONFLICT"])

    if _background_conflicts(normalized["market_state_4h"], side):
        return _build_result(normalized, "NO_TRADE", SIDE_NONE, "NONE", score, "HIGHER_TIMEFRAME_CONFLICT", ["TREND_CONFLICT"])

    trend_score = 0.2 if normalized["market_state_4h"] in {"BULL", "BEAR"} else 0.1
    trend_score += 0.2
    score = SignalScoreBreakdown(trend_score=trend_score)
    sub_reasons.append("TREND_ALIGNED")

    if not _confirm_matches(normalized["confirm_state_30m"], side):
        score = _replace_score(score, confirm_score=0.05)
        sub_reasons.extend(["MOMENTUM_WEAK", "TRIGGER_NOT_READY"])
        return _build_result(normalized, "WAIT", SIDE_NONE, "NONE", score, "CONFIRMATION_NOT_READY", sub_reasons)

    score = _replace_score(score, confirm_score=0.2)
    sub_reasons.extend(["MOMENTUM_STRONG", "CCI_STRONG"])

    trigger_ready = _trigger_matches(normalized["trigger_state_15m"], side)
    trigger_partial = _is_partial_trigger(normalized["trigger_state_15m"], side)
    if trigger_ready:
        score = _replace_score(score, trigger_score=0.2)
        sub_reasons.append("TRIGGER_READY")
    elif trigger_partial:
        score = _replace_score(score, trigger_score=0.1)
        sub_reasons.append("TRIGGER_NOT_READY")
    else:
        score = _replace_score(score, trigger_score=0.0)
        sub_reasons.append("TRIGGER_NOT_READY")
        return _build_result(normalized, "WAIT", SIDE_NONE, "NONE", score, "DIRECTION_CONFIRMED_TRIGGER_NOT_READY", sub_reasons)

    cvd_state = _indicator_state(normalized, "cvd")
    if _is_divergence(cvd_state) or _flow_conflicts(cvd_state, side):
        score = _replace_score(score, flow_score=-0.2)
        sub_reasons.append("FLOW_DIVERGENCE")
        entry_mode = "NONE" if _is_divergence(cvd_state) else "PROBE"
        signal_type = "WAIT" if entry_mode == "NONE" else side
        return _build_result(normalized, signal_type, SIDE_NONE if entry_mode == "NONE" else side, entry_mode, score, "FLOW_DIVERGENCE", sub_reasons)

    flow_confirmed = _flow_confirms(cvd_state, side)
    score = _replace_score(score, flow_score=0.2 if flow_confirmed else 0.05)
    if flow_confirmed:
        sub_reasons.append("FLOW_CONFIRMED")

    atr_state = _indicator_state(normalized, "atr")
    boll_state = _indicator_state(normalized, "boll")
    volatility_score = 0.1
    if _contains_any(atr_state, {"TOO_HIGH", "HIGH", "EXPANDED"}):
        volatility_score = -0.1
        sub_reasons.append("VOLATILITY_TOO_HIGH")
    elif _contains_any(atr_state, {"TOO_LOW", "LOW", "SQUEEZE"}):
        volatility_score = 0.0
        sub_reasons.append("VOLATILITY_TOO_LOW")
    if _contains_any(boll_state, {"EXPANSION", "BREAKOUT"}):
        sub_reasons.append("BOLL_EXPANSION")
    if _contains_any(boll_state, {"CONTRACTION", "SQUEEZE"}):
        sub_reasons.append("BOLL_CONTRACTION")
    score = _replace_score(score, volatility_score=volatility_score)

    rsi_state = _indicator_state(normalized, "rsi")
    overheated = side == SIDE_LONG and _contains_any(rsi_state, {"OVERHEATED", "OVERBOUGHT"})
    overcold = side == SIDE_SHORT and _contains_any(rsi_state, {"OVERCOLD", "OVERSOLD"})
    if overheated or overcold:
        sub_reasons.append("RSI_OVERHEATED")
    elif _contains_any(rsi_state, {"RECOVERY", "RECLAIM"}):
        sub_reasons.append("RSI_RECOVERY")

    cci_state = _indicator_state(normalized, "cci")
    if _contains_any(cci_state, {"EXTREME", "OVERHEATED", "OVERCOLD"}):
        sub_reasons.append("CCI_EXTREME")

    far_without_flow = _contains_any(boll_state, {"FAR_FROM_MID", "EXTENDED"}) and not flow_confirmed
    direct_allowed = trigger_ready and flow_confirmed and not overheated and not overcold and not far_without_flow

    if direct_allowed and score.total >= 0.7:
        return _build_result(normalized, side, side, "DIRECT", score, "ALL_LAYERS_ALIGNED", sub_reasons)

    return _build_result(normalized, side, side, "PROBE", score, "HIGHER_TF_CONFIRMED_LOWER_TF_PARTIAL", sub_reasons)


def _normalize_context(context: Any) -> dict[str, Any]:
    if isinstance(context, SignalEngineContext):
        return {
            "symbol": context.symbol,
            "timestamp": context.timestamp,
            "market_state_4h": context.market_state_4h,
            "trend_state_1h": context.trend_state_1h,
            "confirm_state_30m": context.confirm_state_30m,
            "trigger_state_15m": context.trigger_state_15m,
            "indicators_15m": dict(context.indicators_15m),
            "indicators_30m": dict(context.indicators_30m),
            "indicators_1h": dict(context.indicators_1h),
            "indicators_4h": dict(context.indicators_4h),
            "risk_snapshot": dict(context.risk_snapshot),
            "position_snapshot": dict(context.position_snapshot),
            "cooldown_state": dict(context.cooldown_state),
            "quality_flag": context.quality_flag,
        }

    if hasattr(context, "signal_type") and hasattr(context, "side"):
        entry_mode = getattr(context, "signal_type")
        side = getattr(context, "side")
        trend = "LONG_ALLOWED" if side == SIDE_LONG else "SHORT_ALLOWED" if side == SIDE_SHORT else "NO_TRADE"
        return {
            "symbol": getattr(context, "symbol", ""),
            "timestamp": getattr(context, "timestamp", None),
            "market_state_4h": getattr(context, "context_4h", "NEUTRAL"),
            "trend_state_1h": getattr(context, "permission_1h", trend),
            "confirm_state_30m": getattr(context, "quality_30m", f"{side}_CONFIRM" if side != SIDE_NONE else "WAIT"),
            "trigger_state_15m": getattr(context, "trigger_15m", side),
            "indicators_15m": {"cvd": side if entry_mode == "DIRECT" else "NEUTRAL"},
            "indicators_30m": {},
            "indicators_1h": {},
            "indicators_4h": {},
            "risk_snapshot": {"risk_blocked": False},
            "position_snapshot": {},
            "cooldown_state": {"active": False},
            "quality_flag": entry_mode != "NO_TRADE",
        }

    if not isinstance(context, Mapping):
        raise TypeError("context must be a mapping, SignalEngineContext, or multi-timeframe decision object")

    return {
        "symbol": context.get("symbol", ""),
        "timestamp": context.get("timestamp"),
        "market_state_4h": context.get("market_state_4h", context.get("context_4h", "NEUTRAL")),
        "trend_state_1h": context.get("trend_state_1h", context.get("permission", context.get("permission_1h", "NO_TRADE"))),
        "confirm_state_30m": context.get("confirm_state_30m", context.get("quality", context.get("quality_30m", "WAIT"))),
        "trigger_state_15m": context.get("trigger_state_15m", context.get("trigger", context.get("trigger_15m", "WAIT"))),
        "indicators_15m": dict(context.get("indicators_15m", {})),
        "indicators_30m": dict(context.get("indicators_30m", {})),
        "indicators_1h": dict(context.get("indicators_1h", {})),
        "indicators_4h": dict(context.get("indicators_4h", {})),
        "risk_snapshot": dict(context.get("risk_snapshot", {})),
        "position_snapshot": dict(context.get("position_snapshot", {})),
        "cooldown_state": dict(context.get("cooldown_state", {})),
        "quality_flag": bool(context.get("quality_flag", True)),
    }


def _build_result(
    context: Mapping[str, Any],
    signal_type: str,
    side: str,
    entry_mode: str,
    score: SignalScoreBreakdown,
    reason: str,
    sub_reasons: list[str],
) -> SignalResult:
    normalized_score = max(0.0, min(1.0, round(score.total, 2)))
    evidence = {
        "symbol": context["symbol"],
        "timestamp": context["timestamp"],
        "signal_type": signal_type,
        "signal_side": side,
        "entry_mode": entry_mode,
        "score": normalized_score,
        "confidence": normalized_score,
        "market_state_4h": context["market_state_4h"],
        "trend_state_1h": context["trend_state_1h"],
        "confirm_state_30m": context["confirm_state_30m"],
        "trigger_state_15m": context["trigger_state_15m"],
        "macd_state": _indicator_state(context, "macd"),
        "cci_state": _indicator_state(context, "cci"),
        "boll_state": _indicator_state(context, "boll"),
        "rsi_state": _indicator_state(context, "rsi"),
        "cvd_state": _indicator_state(context, "cvd"),
        "atr_state": _indicator_state(context, "atr"),
        "reason": reason,
        "sub_reasons": list(dict.fromkeys(sub_reasons)),
    }
    return SignalResult(
        symbol=context["symbol"],
        timestamp=context["timestamp"],
        signal_type=signal_type,
        signal_side=side,
        entry_mode=entry_mode,
        score=normalized_score,
        confidence=normalized_score,
        reason=reason,
        sub_reasons=tuple(evidence["sub_reasons"]),
        required_state=_required_state(signal_type, side, entry_mode),
        quality_flag=bool(context["quality_flag"]),
        metadata={
            "score_breakdown": asdict(score),
            "evidence": evidence,
            "state_machine_mapping": STATE_MACHINE_MAPPING.get(entry_mode, STATE_MACHINE_MAPPING.get(signal_type)),
        },
    )


def _replace_score(score: SignalScoreBreakdown, **changes: float) -> SignalScoreBreakdown:
    values = asdict(score)
    values.update(changes)
    return SignalScoreBreakdown(**values)


def _direction_side(value: str) -> str:
    normalized = str(value).upper()
    if normalized in {"LONG_ALLOWED", "LONG", "BULL"}:
        return SIDE_LONG
    if normalized in {"SHORT_ALLOWED", "SHORT", "BEAR"}:
        return SIDE_SHORT
    return SIDE_NONE


def _background_conflicts(market_state: str, side: str) -> bool:
    state = str(market_state).upper()
    return (side == SIDE_LONG and state == "BEAR") or (side == SIDE_SHORT and state == "BULL")


def _confirm_matches(value: str, side: str) -> bool:
    normalized = str(value).upper()
    allowed = {"LONG": {"LONG_CONFIRM", "LONG_CONFIRMED", "LONG", "BULL", "POSITIVE"}, "SHORT": {"SHORT_CONFIRM", "SHORT_CONFIRMED", "SHORT", "BEAR", "NEGATIVE"}}
    return normalized in allowed.get(side, set())


def _trigger_matches(value: str, side: str) -> bool:
    normalized = str(value).upper()
    return normalized in {side, f"{side}_TRIGGER", f"{side}_READY", "READY", "TRIGGER_READY"}


def _is_partial_trigger(value: str, side: str) -> bool:
    normalized = str(value).upper()
    return normalized in {f"{side}_PARTIAL", "PARTIAL", "EARLY", "WATCH"}


def _risk_blocked(snapshot: Mapping[str, Any]) -> bool:
    return bool(
        snapshot.get("risk_blocked")
        or snapshot.get("blocked")
        or snapshot.get("portfolio_risk_blocked")
        or str(snapshot.get("status", "")).upper() in {"BLOCKED", "RISK_BLOCKED"}
    )


def _is_active(snapshot: Mapping[str, Any]) -> bool:
    return bool(snapshot.get("active") or snapshot.get("cooldown_active") or str(snapshot.get("state", "")).upper() == "ACTIVE")


def _indicator_state(context: Mapping[str, Any], key: str) -> str:
    for bucket in ("indicators_15m", "indicators_30m", "indicators_1h", "indicators_4h"):
        value = context[bucket].get(key)
        if value is not None:
            return str(value).upper()
    return "UNKNOWN"


def _flow_confirms(cvd_state: str, side: str) -> bool:
    return str(cvd_state).upper() in {side, f"{side}_CONFIRMED", "CONFIRMED", "FLOW_CONFIRMED"}


def _flow_conflicts(cvd_state: str, side: str) -> bool:
    state = str(cvd_state).upper()
    return (side == SIDE_LONG and state in {"SHORT", "SELL", "BEAR"}) or (
        side == SIDE_SHORT and state in {"LONG", "BUY", "BULL"}
    )


def _is_divergence(cvd_state: str) -> bool:
    return "DIVERGENCE" in str(cvd_state).upper()


def _contains_any(value: str, needles: set[str]) -> bool:
    state = str(value).upper()
    return any(needle in state for needle in needles)


def _required_state(signal_type: str, side: str, entry_mode: str) -> str:
    if entry_mode in {"DIRECT", "PROBE"} and side in {SIDE_LONG, SIDE_SHORT}:
        return f"{entry_mode}_{side}"
    if signal_type == "WAIT":
        return "WATCH_*"
    return "FLAT"
""",
    "src/state_machine/__init__.py": '"""Entry and position state machines."""',
    "src/state_machine/entry_state_machine.py": """
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping


ENTRY_STATE_VERSION = "1.0"


class EntryState(str, Enum):
    FLAT = "FLAT"
    WATCH_LONG = "WATCH_LONG"
    WATCH_SHORT = "WATCH_SHORT"
    PROBE_LONG = "PROBE_LONG"
    PROBE_SHORT = "PROBE_SHORT"
    DIRECT_LONG = "DIRECT_LONG"
    DIRECT_SHORT = "DIRECT_SHORT"
    MANAGE_LONG = "MANAGE_LONG"
    MANAGE_SHORT = "MANAGE_SHORT"
    EXIT_LONG = "EXIT_LONG"
    EXIT_SHORT = "EXIT_SHORT"


ALLOWED_TRANSITIONS = {
    EntryState.FLAT: {
        EntryState.WATCH_LONG,
        EntryState.WATCH_SHORT,
        EntryState.PROBE_LONG,
        EntryState.PROBE_SHORT,
        EntryState.DIRECT_LONG,
        EntryState.DIRECT_SHORT,
    },
    EntryState.WATCH_LONG: {EntryState.PROBE_LONG, EntryState.DIRECT_LONG, EntryState.FLAT},
    EntryState.WATCH_SHORT: {EntryState.PROBE_SHORT, EntryState.DIRECT_SHORT, EntryState.FLAT},
    EntryState.PROBE_LONG: {EntryState.MANAGE_LONG, EntryState.EXIT_LONG, EntryState.FLAT, EntryState.DIRECT_LONG},
    EntryState.PROBE_SHORT: {EntryState.MANAGE_SHORT, EntryState.EXIT_SHORT, EntryState.FLAT, EntryState.DIRECT_SHORT},
    EntryState.DIRECT_LONG: {EntryState.MANAGE_LONG, EntryState.EXIT_LONG, EntryState.FLAT},
    EntryState.DIRECT_SHORT: {EntryState.MANAGE_SHORT, EntryState.EXIT_SHORT, EntryState.FLAT},
    EntryState.MANAGE_LONG: {EntryState.EXIT_LONG, EntryState.FLAT},
    EntryState.MANAGE_SHORT: {EntryState.EXIT_SHORT, EntryState.FLAT},
    EntryState.EXIT_LONG: {EntryState.FLAT},
    EntryState.EXIT_SHORT: {EntryState.FLAT},
}

ENTRY_STATE_CATEGORIES = {
    "watch": ("WATCH_LONG", "WATCH_SHORT"),
    "probe": ("PROBE_LONG", "PROBE_SHORT"),
    "direct": ("DIRECT_LONG", "DIRECT_SHORT"),
    "manage": ("MANAGE_LONG", "MANAGE_SHORT"),
    "exit": ("EXIT_LONG", "EXIT_SHORT"),
}
TRANSITION_LOG_FIELDS = (
    "symbol",
    "timestamp",
    "state_before",
    "state_after",
    "reason",
    "signal_type",
    "entry_mode",
    "risk_level",
    "quality_flag",
    "price",
    "version",
)
TRANSITION_SOURCES = (
    "signal_engine",
    "risk_engine",
    "execution_result",
    "position_sync",
    "cooldown",
    "data_quality",
)
TRANSITION_BLOCKERS = (
    "invalid_transition",
    "missing_reason",
    "risk_blocked",
    "data_quality_blocked",
    "cooldown_active",
    "position_not_executable",
)
ENTRY_STATE_FORBIDDEN_ACTIONS = (
    "calculate_indicators",
    "judge_trend_direction",
    "calculate_final_position_size",
    "generate_orders",
    "call_exchange_adapter",
    "rewrite_risk_decision",
    "unlogged_transition",
)


def transition(current: EntryState, target: EntryState) -> EntryState:
    if target not in ALLOWED_TRANSITIONS[current]:
        raise ValueError(f"invalid transition: {current.value} -> {target.value}")
    return target


@dataclass(frozen=True)
class TransitionDecision:
    allowed: bool
    state_before: EntryState
    state_after: EntryState
    reason: str
    blockers: tuple[str, ...] = ()


@dataclass(frozen=True)
class EntryTransition:
    symbol: str
    from_state: EntryState
    to_state: EntryState
    reason: str
    ts: Any
    price: float
    signal_type: str = "NO_TRADE"
    entry_mode: str = "NONE"
    risk_level: str = "NORMAL"
    quality_flag: bool = True
    version: str = ENTRY_STATE_VERSION
    source: str = "state_machine"
    position_size: float = 0.0
    risk_value: float = 0.0

    @property
    def timestamp(self) -> Any:
        return self.ts

    @property
    def state_before(self) -> EntryState:
        return self.from_state

    @property
    def state_after(self) -> EntryState:
        return self.to_state

    def to_log_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timestamp": self.ts,
            "state_before": self.from_state.value,
            "state_after": self.to_state.value,
            "reason": self.reason,
            "signal_type": self.signal_type,
            "entry_mode": self.entry_mode,
            "risk_level": self.risk_level,
            "quality_flag": self.quality_flag,
            "price": self.price,
            "version": self.version,
            "source": self.source,
            "from_state": self.from_state.value,
            "to_state": self.to_state.value,
            "ts": self.ts,
            "position_size": self.position_size,
            "risk_value": self.risk_value,
        }


def evaluate_transition(
    current: EntryState,
    target: EntryState,
    *,
    reason: str,
    risk_allowed: bool = True,
    quality_flag: bool = True,
    cooldown_active: bool = False,
    position_executable: bool = True,
) -> TransitionDecision:
    blockers: list[str] = []
    if target not in ALLOWED_TRANSITIONS[current]:
        blockers.append("invalid_transition")
    if not str(reason).strip():
        blockers.append("missing_reason")
    if not risk_allowed:
        blockers.append("risk_blocked")
    if not quality_flag:
        blockers.append("data_quality_blocked")
    if cooldown_active:
        blockers.append("cooldown_active")
    if not position_executable:
        blockers.append("position_not_executable")
    return TransitionDecision(
        allowed=not blockers,
        state_before=current,
        state_after=target,
        reason=reason,
        blockers=tuple(blockers),
    )


class EntryStateMachine:
    def __init__(self, symbol: str, initial_state: EntryState = EntryState.FLAT):
        self.symbol = symbol
        self.current_state = initial_state
        self.history: list[EntryTransition] = []

    def apply_transition(
        self,
        target: EntryState,
        reason: str,
        ts: Any,
        price: float,
        position_size: float = 0.0,
        risk_value: float = 0.0,
        *,
        signal_type: str = "NO_TRADE",
        entry_mode: str = "NONE",
        risk_level: str = "NORMAL",
        quality_flag: bool = True,
        risk_allowed: bool = True,
        cooldown_active: bool = False,
        position_executable: bool = True,
        source: str = "state_machine",
        version: str = ENTRY_STATE_VERSION,
    ) -> EntryTransition:
        source_state = self.current_state
        decision = evaluate_transition(
            source_state,
            target,
            reason=reason,
            risk_allowed=risk_allowed,
            quality_flag=quality_flag,
            cooldown_active=cooldown_active,
            position_executable=position_executable,
        )
        if not decision.allowed:
            raise ValueError(
                f"blocked transition: {source_state.value} -> {target.value}; blockers={','.join(decision.blockers)}"
            )
        record = EntryTransition(
            symbol=self.symbol,
            from_state=source_state,
            to_state=target,
            reason=reason,
            ts=ts,
            price=price,
            signal_type=signal_type,
            entry_mode=entry_mode,
            risk_level=risk_level,
            quality_flag=quality_flag,
            version=version,
            source=source,
            position_size=position_size,
            risk_value=risk_value,
        )
        self.current_state = target
        self.history.append(record)
        return record

    def apply_signal(
        self,
        signal: Mapping[str, Any],
        ts: Any,
        price: float,
        position_size: float = 0.0,
        risk_value: float = 0.0,
    ) -> list[EntryTransition]:
        signal_type = str(signal.get("signal_type", "")).upper()
        side = str(signal.get("side", signal.get("signal_side", ""))).upper()
        entry_mode = str(signal.get("entry_mode", signal.get("mode", signal_type))).upper()
        reason = str(signal.get("reason", signal_type or entry_mode))
        quality_flag = bool(signal.get("quality_flag", True))
        risk_level = str(signal.get("risk_level", "NORMAL")).upper()

        if signal_type in {"WAIT", "NO_TRADE"} or entry_mode == "NONE":
            return []
        if self.current_state != EntryState.FLAT:
            raise ValueError(f"signal entries require FLAT state, got {self.current_state.value}")

        target = _entry_target(signal_type, side, entry_mode)
        if target is None:
            raise ValueError(f"unsupported signal: {signal_type}/{side}/{entry_mode}")
        return [
            self.apply_transition(
                target,
                reason,
                ts,
                price,
                position_size,
                risk_value,
                signal_type=signal_type,
                entry_mode=_entry_mode_from_state(target),
                risk_level=risk_level,
                quality_flag=quality_flag,
                source="signal_engine",
            )
        ]

    def maybe_upgrade_probe(self, r_multiple: float, ts: Any, price: float) -> EntryTransition | None:
        if r_multiple < 1.0:
            return None
        if self.current_state == EntryState.PROBE_LONG:
            return self.apply_transition(
                EntryState.DIRECT_LONG,
                "probe reached 1R",
                ts,
                price,
                signal_type="LONG",
                entry_mode="DIRECT",
                source="signal_engine",
            )
        if self.current_state == EntryState.PROBE_SHORT:
            return self.apply_transition(
                EntryState.DIRECT_SHORT,
                "probe reached 1R",
                ts,
                price,
                signal_type="SHORT",
                entry_mode="DIRECT",
                source="signal_engine",
            )
        return None

    def mark_position_opened(self, reason: str, ts: Any, price: float) -> EntryTransition | None:
        if self.current_state == EntryState.PROBE_LONG:
            return self.apply_transition(EntryState.MANAGE_LONG, reason, ts, price, source="execution_result")
        if self.current_state == EntryState.PROBE_SHORT:
            return self.apply_transition(EntryState.MANAGE_SHORT, reason, ts, price, source="execution_result")
        if self.current_state == EntryState.DIRECT_LONG:
            return self.apply_transition(EntryState.MANAGE_LONG, reason, ts, price, source="execution_result")
        if self.current_state == EntryState.DIRECT_SHORT:
            return self.apply_transition(EntryState.MANAGE_SHORT, reason, ts, price, source="execution_result")
        return None

    def rollback_rejected_order(self, reason: str, ts: Any, price: float) -> EntryTransition | None:
        if self.current_state in {
            EntryState.PROBE_LONG,
            EntryState.PROBE_SHORT,
            EntryState.DIRECT_LONG,
            EntryState.DIRECT_SHORT,
        }:
            return self.apply_transition(EntryState.FLAT, reason, ts, price, source="execution_result")
        return None

    def exit_current(self, reason: str, ts: Any, price: float) -> list[EntryTransition]:
        if self.current_state in {EntryState.FLAT, EntryState.WATCH_LONG, EntryState.WATCH_SHORT}:
            return []
        if self.current_state in {EntryState.PROBE_LONG, EntryState.DIRECT_LONG, EntryState.MANAGE_LONG}:
            exit_state = EntryState.EXIT_LONG
        elif self.current_state in {EntryState.PROBE_SHORT, EntryState.DIRECT_SHORT, EntryState.MANAGE_SHORT}:
            exit_state = EntryState.EXIT_SHORT
        elif self.current_state in {EntryState.EXIT_LONG, EntryState.EXIT_SHORT}:
            exit_state = self.current_state
        else:
            raise ValueError(f"cannot exit from {self.current_state.value}")

        records: list[EntryTransition] = []
        if self.current_state != exit_state:
            records.append(self.apply_transition(exit_state, reason, ts, price, source="risk_engine"))
        records.append(self.apply_transition(EntryState.FLAT, reason, ts, price, source="position_sync"))
        return records


class EntryStateStore:
    def __init__(self) -> None:
        self._machines: dict[str, EntryStateMachine] = {}

    def get(self, symbol: str) -> EntryStateMachine:
        normalized = symbol.upper()
        if normalized not in self._machines:
            self._machines[normalized] = EntryStateMachine(normalized)
        return self._machines[normalized]

    def state_of(self, symbol: str) -> EntryState:
        return self.get(symbol).current_state


def _entry_target(signal_type: str, side: str, entry_mode: str) -> EntryState | None:
    mode = entry_mode if entry_mode in {"PROBE", "DIRECT"} else signal_type
    direction = side if side in {"LONG", "SHORT"} else signal_type
    if mode == "PROBE" and direction == "LONG":
        return EntryState.PROBE_LONG
    if mode == "PROBE" and direction == "SHORT":
        return EntryState.PROBE_SHORT
    if mode == "DIRECT" and direction == "LONG":
        return EntryState.DIRECT_LONG
    if mode == "DIRECT" and direction == "SHORT":
        return EntryState.DIRECT_SHORT
    return None


def _entry_mode_from_state(state: EntryState) -> str:
    if state in {EntryState.PROBE_LONG, EntryState.PROBE_SHORT}:
        return "PROBE"
    if state in {EntryState.DIRECT_LONG, EntryState.DIRECT_SHORT}:
        return "DIRECT"
    return "NONE"
""",
    "src/risk/__init__.py": '"""Risk controls and sizing."""',
    "src/risk/position_sizer.py": """
from __future__ import annotations

from dataclasses import dataclass


NO_TRADE = "NO_TRADE"
ENTRY_MODE_MULTIPLIERS = {"DIRECT": 1.0, "PROBE": 0.25}
SIGNAL_MULTIPLIERS = ENTRY_MODE_MULTIPLIERS
MARKET_TIER_MULTIPLIERS = {"A": 2.0, "B": 1.0, "C": 0.75}
VOLATILITY_FACTORS = {"NORMAL": 1.0, "HIGH": 0.5, "EXTREME": 0.0}
POSITION_REQUIRED_INPUTS = [
    "account_equity",
    "available_margin",
    "symbol_price",
    "leverage",
    "stop_pct",
    "risk_per_trade_pct",
    "symbol_tier",
    "open_exposure",
    "portfolio_exposure",
    "correlation_group",
    "position_side",
    "entry_mode",
    "volatility_state",
]
POSITION_DECISION_STEPS = [
    "read_account_equity_and_available_margin",
    "read_entry_mode",
    "read_stop_pct",
    "calculate_standard_notional",
    "apply_symbol_tier_factor",
    "apply_portfolio_exposure_limit",
    "apply_account_risk_factor",
    "check_min_notional",
    "check_min_margin",
    "output_final_executable_size",
]
POSITION_LOG_FIELDS = [
    "symbol",
    "entry_mode",
    "account_equity",
    "available_margin",
    "risk_amount",
    "stop_pct",
    "standard_notional",
    "probe_notional",
    "direct_notional",
    "tier_factor",
    "account_risk_factor",
    "portfolio_risk_factor",
    "final_notional",
    "final_qty",
    "min_notional_check",
    "leverage",
    "decision",
]
STATE_POSITION_POLICY = {
    "WATCH": "prepare_only",
    "PROBE": "probe_size",
    "DIRECT": "direct_size",
    "MANAGE": "manage_only",
    "EXIT": "close_only",
}


@dataclass(frozen=True)
class PositionSizingInput:
    symbol: str
    signal_type: str
    equity: float
    available_margin: float
    price: float
    leverage: float
    stop_pct: float
    atr: float
    risk_pct: float
    market_tier: str
    current_open_exposure: float
    portfolio_correlation: float
    min_notional: float
    max_total_exposure_pct: float
    entry_mode: str | None = None
    risk_per_trade_pct: float | None = None
    symbol_tier: str | None = None
    position_side: str = "BOTH"
    volatility_state: str = "NORMAL"
    account_risk_factor: float = 1.0
    portfolio_risk_factor: float = 1.0
    min_margin: float = 0.0
    max_leverage: float = 5.0
    symbol_exposure: float = 0.0
    max_symbol_exposure_pct: float = 0.20
    side_exposure: float = 0.0
    max_side_exposure_pct: float = 0.75
    correlation_group: str = ""
    correlation_group_exposure: float = 0.0
    max_correlation_group_exposure_pct: float = 0.50
    open_positions_count: int = 0
    max_open_positions: int = 5
    quantity_step: float = 0.0
    data_quality_ok: bool = True
    state_allows_entry: bool = True
    cooldown_active: bool = False
    leverage_set: bool = True


@dataclass(frozen=True)
class PositionSizingResult:
    approved: bool
    reason: str
    symbol: str
    signal_type: str
    standard_notional: float
    notional: float
    quantity: float
    required_margin: float
    risk_amount: float
    signal_multiplier: float
    market_tier: str
    market_tier_multiplier: float
    decision: str = NO_TRADE
    entry_mode: str = NO_TRADE
    final_notional: float = 0.0
    final_qty: float = 0.0
    tier_factor: float = 1.0
    account_risk_factor: float = 1.0
    portfolio_risk_factor: float = 1.0
    volatility_factor: float = 1.0
    min_notional_check: bool = False
    min_margin_check: bool = False
    leverage_value: float = 0.0
    position_side: str = "BOTH"
    correlation_group: str = ""
    audit: dict | None = None


def size_notional(equity: float, risk_pct: float, stop_pct: float, signal_type: str) -> float:
    if equity <= 0:
        raise ValueError("equity must be positive")
    if risk_pct <= 0:
        raise ValueError("risk_pct must be positive")
    if stop_pct <= 0:
        raise ValueError("stop_pct must be positive")
    base = equity * risk_pct / stop_pct
    if signal_type.upper() == "PROBE":
        return base * 0.25
    return base


def reject_if_below_min_notional(notional: float, min_notional: float) -> tuple[bool, str]:
    if notional < min_notional:
        return False, "notional below exchange minimum; skip instead of inflating size"
    return True, "approved"


def signal_multiplier(signal_type: str) -> float:
    value = signal_type.strip().upper()
    if value not in ENTRY_MODE_MULTIPLIERS:
        raise ValueError("signal_type must be DIRECT or PROBE")
    return ENTRY_MODE_MULTIPLIERS[value]


def market_tier_multiplier(market_tier: str) -> float:
    value = market_tier.strip().upper()
    if value not in MARKET_TIER_MULTIPLIERS:
        raise ValueError("market_tier must be A, B, or C")
    return MARKET_TIER_MULTIPLIERS[value]


def normalize_entry_mode(request: PositionSizingInput) -> str:
    value = request.entry_mode if request.entry_mode is not None else request.signal_type
    normalized = value.strip().upper()
    if normalized in {"NO_TRADE", "NONE", "WAIT"}:
        return NO_TRADE
    if normalized not in ENTRY_MODE_MULTIPLIERS:
        raise ValueError("entry_mode must be DIRECT, PROBE, or NO_TRADE")
    return normalized


def normalized_symbol_tier(request: PositionSizingInput) -> str:
    value = request.symbol_tier if request.symbol_tier is not None else request.market_tier
    return value.strip().upper()


def effective_risk_pct(request: PositionSizingInput) -> float:
    return request.risk_per_trade_pct if request.risk_per_trade_pct is not None else request.risk_pct


def volatility_factor(volatility_state: str) -> float:
    value = volatility_state.strip().upper()
    if value not in VOLATILITY_FACTORS:
        raise ValueError("volatility_state must be NORMAL, HIGH, or EXTREME")
    return VOLATILITY_FACTORS[value]


def floor_quantity(quantity: float, quantity_step: float) -> float:
    if quantity_step <= 0:
        return quantity
    steps = int(quantity / quantity_step)
    return steps * quantity_step


def calculate_position_size(request: PositionSizingInput) -> PositionSizingResult:
    _validate_request(request)
    entry_mode = normalize_entry_mode(request)
    normalized_tier = normalized_symbol_tier(request)
    sig_multiplier = ENTRY_MODE_MULTIPLIERS.get(entry_mode, 0.0)
    tier_multiplier = market_tier_multiplier(normalized_tier)
    vol_factor = volatility_factor(request.volatility_state)
    risk_pct = effective_risk_pct(request)
    risk_amount = request.equity * risk_pct
    standard_notional = risk_amount / request.stop_pct
    probe_notional = standard_notional * ENTRY_MODE_MULTIPLIERS["PROBE"]
    direct_notional = standard_notional * ENTRY_MODE_MULTIPLIERS["DIRECT"]
    raw_notional = (
        standard_notional
        * sig_multiplier
        * tier_multiplier
        * request.account_risk_factor
        * request.portfolio_risk_factor
        * vol_factor
    )
    raw_quantity = raw_notional / request.price
    quantity = floor_quantity(raw_quantity, request.quantity_step)
    notional = quantity * request.price
    required_margin = notional / request.leverage

    gate_reason = _gate_no_trade(request, entry_mode)
    if gate_reason is not None:
        return _result(
            request,
            False,
            gate_reason,
            standard_notional,
            0.0,
            0.0,
            0.0,
            risk_amount,
            sig_multiplier,
            tier_multiplier,
            entry_mode,
            NO_TRADE,
            vol_factor,
            probe_notional,
            direct_notional,
            False,
            False,
        )

    if vol_factor == 0:
        return _result(
            request,
            False,
            "volatility state blocks new position",
            standard_notional,
            0.0,
            0.0,
            0.0,
            risk_amount,
            sig_multiplier,
            tier_multiplier,
            entry_mode,
            NO_TRADE,
            vol_factor,
            probe_notional,
            direct_notional,
            False,
            False,
        )

    raw_ok, reason = reject_if_below_min_notional(raw_notional, request.min_notional)
    if not raw_ok:
        return _result(
            request,
            False,
            reason,
            standard_notional,
            notional,
            0.0,
            required_margin,
            risk_amount,
            sig_multiplier,
            tier_multiplier,
            entry_mode,
            NO_TRADE,
            vol_factor,
            probe_notional,
            direct_notional,
            False,
            required_margin >= request.min_margin,
        )

    ok, reason = reject_if_below_min_notional(notional, request.min_notional)
    if not ok:
        return _result(
            request,
            False,
            "notional below exchange minimum after precision floor; skip instead of inflating size",
            standard_notional,
            notional,
            quantity,
            required_margin,
            risk_amount,
            sig_multiplier,
            tier_multiplier,
            entry_mode,
            NO_TRADE,
            vol_factor,
            probe_notional,
            direct_notional,
            False,
            required_margin >= request.min_margin,
        )
    if required_margin > request.available_margin:
        return _result(
            request,
            False,
            "required margin exceeds available margin",
            standard_notional,
            notional,
            0.0,
            required_margin,
            risk_amount,
            sig_multiplier,
            tier_multiplier,
            entry_mode,
            NO_TRADE,
            vol_factor,
            probe_notional,
            direct_notional,
            True,
            required_margin >= request.min_margin,
        )
    if required_margin < request.min_margin:
        return _result(
            request,
            False,
            "required margin below exchange minimum",
            standard_notional,
            notional,
            0.0,
            required_margin,
            risk_amount,
            sig_multiplier,
            tier_multiplier,
            entry_mode,
            NO_TRADE,
            vol_factor,
            probe_notional,
            direct_notional,
            True,
            False,
        )
    if (request.current_open_exposure + notional) / request.equity > request.max_total_exposure_pct:
        return _result(
            request,
            False,
            "total exposure limit exceeded",
            standard_notional,
            notional,
            0.0,
            required_margin,
            risk_amount,
            sig_multiplier,
            tier_multiplier,
            entry_mode,
            NO_TRADE,
            vol_factor,
            probe_notional,
            direct_notional,
            True,
            True,
        )
    if (request.symbol_exposure + notional) / request.equity > request.max_symbol_exposure_pct:
        return _result(
            request,
            False,
            "symbol exposure limit exceeded",
            standard_notional,
            notional,
            0.0,
            required_margin,
            risk_amount,
            sig_multiplier,
            tier_multiplier,
            entry_mode,
            NO_TRADE,
            vol_factor,
            probe_notional,
            direct_notional,
            True,
            True,
        )
    if (request.side_exposure + notional) / request.equity > request.max_side_exposure_pct:
        return _result(
            request,
            False,
            "side exposure limit exceeded",
            standard_notional,
            notional,
            0.0,
            required_margin,
            risk_amount,
            sig_multiplier,
            tier_multiplier,
            entry_mode,
            NO_TRADE,
            vol_factor,
            probe_notional,
            direct_notional,
            True,
            True,
        )
    if (
        request.correlation_group_exposure + notional
    ) / request.equity > request.max_correlation_group_exposure_pct:
        return _result(
            request,
            False,
            "correlation group exposure limit exceeded",
            standard_notional,
            notional,
            0.0,
            required_margin,
            risk_amount,
            sig_multiplier,
            tier_multiplier,
            entry_mode,
            NO_TRADE,
            vol_factor,
            probe_notional,
            direct_notional,
            True,
            True,
        )

    return _result(
        request,
        True,
        "approved",
        standard_notional,
        notional,
        quantity,
        required_margin,
        risk_amount,
        sig_multiplier,
        tier_multiplier,
        entry_mode,
        entry_mode,
        vol_factor,
        probe_notional,
        direct_notional,
        True,
        True,
    )


def _validate_request(request: PositionSizingInput) -> None:
    positive_fields = {
        "equity": request.equity,
        "price": request.price,
        "leverage": request.leverage,
        "stop_pct": request.stop_pct,
        "atr": request.atr,
        "risk_pct": request.risk_pct,
        "min_notional": request.min_notional,
        "max_total_exposure_pct": request.max_total_exposure_pct,
        "account_risk_factor": request.account_risk_factor,
        "portfolio_risk_factor": request.portfolio_risk_factor,
        "max_leverage": request.max_leverage,
        "max_symbol_exposure_pct": request.max_symbol_exposure_pct,
        "max_side_exposure_pct": request.max_side_exposure_pct,
        "max_correlation_group_exposure_pct": request.max_correlation_group_exposure_pct,
        "max_open_positions": request.max_open_positions,
    }
    if request.risk_per_trade_pct is not None:
        positive_fields["risk_per_trade_pct"] = request.risk_per_trade_pct
    for name, value in positive_fields.items():
        if value <= 0:
            raise ValueError(f"{name} must be positive")
    if request.available_margin < 0:
        raise ValueError("available_margin must be non-negative")
    if request.current_open_exposure < 0:
        raise ValueError("current_open_exposure must be non-negative")
    if request.portfolio_correlation < 0:
        raise ValueError("portfolio_correlation must be non-negative")
    if request.min_margin < 0:
        raise ValueError("min_margin must be non-negative")
    if request.symbol_exposure < 0:
        raise ValueError("symbol_exposure must be non-negative")
    if request.side_exposure < 0:
        raise ValueError("side_exposure must be non-negative")
    if request.correlation_group_exposure < 0:
        raise ValueError("correlation_group_exposure must be non-negative")
    if request.open_positions_count < 0:
        raise ValueError("open_positions_count must be non-negative")
    if request.quantity_step < 0:
        raise ValueError("quantity_step must be non-negative")


def _gate_no_trade(request: PositionSizingInput, entry_mode: str) -> str | None:
    if entry_mode == NO_TRADE:
        return "entry mode is NO_TRADE"
    if not request.data_quality_ok:
        return "data quality is not tradable"
    if not request.state_allows_entry:
        return "state machine does not allow new position"
    if request.cooldown_active:
        return "cooldown is active"
    if not request.leverage_set:
        return "leverage must be set before sizing"
    if request.leverage > request.max_leverage:
        return "leverage exceeds system maximum"
    if request.open_positions_count >= request.max_open_positions:
        return "max simultaneous positions reached"
    return None


def _result(
    request: PositionSizingInput,
    approved: bool,
    reason: str,
    standard_notional: float,
    notional: float,
    quantity: float,
    required_margin: float,
    risk_amount: float,
    sig_multiplier: float,
    tier_multiplier: float,
    entry_mode: str,
    decision: str,
    vol_factor: float,
    probe_notional: float,
    direct_notional: float,
    min_notional_check: bool,
    min_margin_check: bool,
) -> PositionSizingResult:
    min_notional_check = min_notional_check and notional >= request.min_notional
    audit = {
        "symbol": request.symbol.strip().upper(),
        "entry_mode": entry_mode,
        "account_equity": request.equity,
        "available_margin": request.available_margin,
        "risk_amount": risk_amount,
        "stop_pct": request.stop_pct,
        "standard_notional": standard_notional,
        "probe_notional": probe_notional,
        "direct_notional": direct_notional,
        "tier_factor": tier_multiplier,
        "account_risk_factor": request.account_risk_factor,
        "portfolio_risk_factor": request.portfolio_risk_factor,
        "final_notional": notional,
        "final_qty": quantity,
        "min_notional_check": min_notional_check,
        "leverage": request.leverage,
        "decision": decision,
    }
    return PositionSizingResult(
        approved=approved,
        reason=reason,
        symbol=request.symbol.strip().upper(),
        signal_type=entry_mode,
        standard_notional=standard_notional,
        notional=notional,
        quantity=quantity,
        required_margin=required_margin,
        risk_amount=risk_amount,
        signal_multiplier=sig_multiplier,
        market_tier=normalized_symbol_tier(request),
        market_tier_multiplier=tier_multiplier,
        decision=decision,
        entry_mode=entry_mode,
        final_notional=notional,
        final_qty=quantity,
        tier_factor=tier_multiplier,
        account_risk_factor=request.account_risk_factor,
        portfolio_risk_factor=request.portfolio_risk_factor,
        volatility_factor=vol_factor,
        min_notional_check=min_notional_check,
        min_margin_check=min_margin_check,
        leverage_value=request.leverage,
        position_side=request.position_side.strip().upper(),
        correlation_group=request.correlation_group,
        audit=audit,
    )
""",
    "src/risk/stop_engine.py": """
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StopPlan:
    stop_price: float
    stop_distance: float
    stop_pct: float
    reason: str


def atr_stop(entry_price: float, atr: float, atr_mult: float, side: str) -> float:
    if entry_price <= 0 or atr <= 0 or atr_mult <= 0:
        raise ValueError("entry_price, atr, and atr_mult must be positive")
    distance = atr * atr_mult
    if side.upper() == "LONG":
        return entry_price - distance
    if side.upper() == "SHORT":
        return entry_price + distance
    raise ValueError("side must be LONG or SHORT")


def initial_atr_stop(entry_price: float, atr: float, atr_mult: float, side: str) -> StopPlan:
    stop_price = atr_stop(entry_price, atr, atr_mult, side)
    stop_distance = abs(entry_price - stop_price)
    return StopPlan(
        stop_price=stop_price,
        stop_distance=stop_distance,
        stop_pct=stop_distance / entry_price,
        reason="initial ATR stop",
    )
""",
    "src/risk/exit_engine.py": """
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ExitActionType(str, Enum):
    FORCED_STOP = "FORCED_STOP"
    PORTFOLIO_RISK = "PORTFOLIO_RISK"
    DIRECTION_REVERSAL = "DIRECTION_REVERSAL"
    VOLATILITY_ANOMALY = "VOLATILITY_ANOMALY"
    TRAILING_STOP = "TRAILING_STOP"
    PARTIAL_TAKE_PROFIT = "PARTIAL_TAKE_PROFIT"


EXIT_PRIORITY = [
    ExitActionType.FORCED_STOP,
    ExitActionType.PORTFOLIO_RISK,
    ExitActionType.DIRECTION_REVERSAL,
    ExitActionType.VOLATILITY_ANOMALY,
    ExitActionType.TRAILING_STOP,
    ExitActionType.PARTIAL_TAKE_PROFIT,
]


@dataclass(frozen=True)
class ExitAction:
    action_type: ExitActionType
    reason: str
    reduce_pct: float = 1.0
    target_price: float | None = None
    stop_price: float | None = None


def select_highest_priority_action(actions: list[ExitAction]) -> ExitAction | None:
    if not actions:
        return None
    rank = {action_type: index for index, action_type in enumerate(EXIT_PRIORITY)}
    return sorted(actions, key=lambda action: rank[action.action_type])[0]


def plan_take_profit_actions(
    entry_price: float,
    stop_price: float,
    side: str,
    r_levels: tuple[float, ...] = (1.0, 2.0, 3.0),
    reduce_pcts: tuple[float, ...] = (0.30, 0.40, 0.30),
) -> list[ExitAction]:
    if len(r_levels) != len(reduce_pcts):
        raise ValueError("r_levels and reduce_pcts must have the same length")
    risk = _risk_unit(entry_price, stop_price)
    normalized_side = side.strip().upper()
    actions = []
    for r_level, reduce_pct in zip(r_levels, reduce_pcts):
        if normalized_side == "LONG":
            target = entry_price + risk * r_level
        elif normalized_side == "SHORT":
            target = entry_price - risk * r_level
        else:
            raise ValueError("side must be LONG or SHORT")
        actions.append(
            ExitAction(
                ExitActionType.PARTIAL_TAKE_PROFIT,
                f"take profit {r_level:g}R",
                reduce_pct=reduce_pct,
                target_price=target,
            )
        )
    return actions


def breakeven_stop(entry_price: float, side: str, fee_bps: float, slippage_bps: float, safety_bps: float) -> float:
    if entry_price <= 0:
        raise ValueError("entry_price must be positive")
    total_bps = fee_bps + slippage_bps + safety_bps
    if total_bps < 0:
        raise ValueError("buffers must be non-negative")
    buffer = entry_price * total_bps / 10000
    normalized_side = side.strip().upper()
    if normalized_side == "LONG":
        return entry_price + buffer
    if normalized_side == "SHORT":
        return entry_price - buffer
    raise ValueError("side must be LONG or SHORT")


def trailing_stop_from_structure(
    side: str,
    current_stop: float,
    structure_price: float,
    buffer_pct: float,
) -> ExitAction | None:
    if current_stop <= 0 or structure_price <= 0 or buffer_pct < 0:
        raise ValueError("prices must be positive and buffer_pct must be non-negative")
    normalized_side = side.strip().upper()
    if normalized_side == "LONG":
        candidate = structure_price * (1 - buffer_pct)
        if candidate <= current_stop:
            return None
    elif normalized_side == "SHORT":
        candidate = structure_price * (1 + buffer_pct)
        if candidate >= current_stop:
            return None
    else:
        raise ValueError("side must be LONG or SHORT")
    return ExitAction(ExitActionType.TRAILING_STOP, "structure trailing stop", stop_price=candidate)


def forced_exit_actions(
    stop_hit: bool = False,
    portfolio_risk: bool = False,
    direction_reversal: bool = False,
    volatility_anomaly: bool = False,
) -> list[ExitAction]:
    actions = []
    if stop_hit:
        actions.append(ExitAction(ExitActionType.FORCED_STOP, "initial stop hit", reduce_pct=1.0))
    if portfolio_risk:
        actions.append(ExitAction(ExitActionType.PORTFOLIO_RISK, "portfolio risk limit exceeded", reduce_pct=1.0))
    if direction_reversal:
        actions.append(ExitAction(ExitActionType.DIRECTION_REVERSAL, "direction reversal confirmed", reduce_pct=1.0))
    if volatility_anomaly:
        actions.append(ExitAction(ExitActionType.VOLATILITY_ANOMALY, "volatility anomaly protection", reduce_pct=0.50))
    return actions


def cooldown_until(now_ts: int, bars: int, timeframe_seconds: int = 900) -> int:
    if bars < 0 or timeframe_seconds <= 0:
        raise ValueError("bars must be non-negative and timeframe_seconds must be positive")
    return now_ts + bars * timeframe_seconds


def _risk_unit(entry_price: float, stop_price: float) -> float:
    if entry_price <= 0 or stop_price <= 0:
        raise ValueError("entry_price and stop_price must be positive")
    distance = abs(entry_price - stop_price)
    if distance <= 0:
        raise ValueError("stop distance must be positive")
    return distance
""",
    "src/risk/portfolio_guard.py": """
from __future__ import annotations


def exposure_allowed(current_exposure: float, new_notional: float, equity: float, max_exposure_pct: float) -> bool:
    if equity <= 0:
        return False
    return (current_exposure + new_notional) / equity <= max_exposure_pct
""",
    "src/risk/cooldown_guard.py": """
from __future__ import annotations


def is_cooldown_active(now_ts: int, cooldown_until_ts: int | None) -> bool:
    return cooldown_until_ts is not None and now_ts < cooldown_until_ts
""",
    "src/execution/__init__.py": '"""Execution adapters and order routing."""',
    "src/execution/binance_adapter.py": """
from __future__ import annotations

from src.core.models import OrderIntent


class BinanceAdapter:
    def __init__(self, client):
        self.client = client

    def get_klines(self, *args, **kwargs):
        return self.client.get_klines(*args, **kwargs)

    def submit(self, intent: OrderIntent) -> dict:
        raise NotImplementedError("live order submission must be wired explicitly after dry-run validation")

    def cancel(self, symbol: str, order_id: int | str) -> dict:
        return self.client.cancel_order(symbol, int(order_id))

    def sync(self, symbol: str | None = None) -> dict:
        if symbol:
            return {"position": self.client.get_position(symbol)}
        return {"positions": self.client.get_all_positions()}
""",
    "src/execution/order_router.py": """
from __future__ import annotations

from src.core.models import OrderIntent, RiskDecision


def build_order_intent(decision: RiskDecision, correlation_id: str) -> OrderIntent:
    if not decision.approved:
        raise ValueError(f"risk rejected: {decision.reason}")
    return OrderIntent(
        symbol=decision.symbol,
        side=decision.side,
        position_side=decision.side,
        quantity=decision.quantity,
        order_type="MARKET",
        correlation_id=correlation_id,
    )
""",
    "src/backtest/__init__.py": '"""Backtest runner and models."""',
    "src/backtest/fill_model.py": """
from __future__ import annotations


def next_bar_market_fill(next_open: float, side: str, slippage_bps: float) -> float:
    adjustment = next_open * slippage_bps / 10000
    if side.upper() in {"BUY", "LONG"}:
        return next_open + adjustment
    if side.upper() in {"SELL", "SHORT"}:
        return next_open - adjustment
    raise ValueError("side must be BUY/LONG or SELL/SHORT")
""",
    "src/backtest/fee_model.py": """
from __future__ import annotations


def fee(notional: float, fee_bps: float) -> float:
    if notional < 0 or fee_bps < 0:
        raise ValueError("notional and fee_bps must be non-negative")
    return notional * fee_bps / 10000
""",
    "src/backtest/slippage_model.py": """
from __future__ import annotations


def slippage_amount(price: float, slippage_bps: float) -> float:
    if price < 0 or slippage_bps < 0:
        raise ValueError("price and slippage_bps must be non-negative")
    return price * slippage_bps / 10000
""",
    "src/backtest/metrics.py": """
from __future__ import annotations


def profit_factor(profits: list[float]) -> float | None:
    gross_profit = sum(value for value in profits if value > 0)
    gross_loss = abs(sum(value for value in profits if value < 0))
    if gross_loss == 0:
        return None
    return gross_profit / gross_loss


def win_rate(profits: list[float]) -> float | None:
    if not profits:
        return None
    return len([value for value in profits if value > 0]) / len(profits)
""",
    "src/backtest/protocol.py": """
from __future__ import annotations

from dataclasses import dataclass

from src.core.models import Candle


BACKTEST_PROCESSING_ORDER = [
    "update_history",
    "update_indicators",
    "update_multi_timeframe_context",
    "update_state",
    "check_exit",
    "check_reduce",
    "check_add",
    "check_entry",
    "record_events",
]

REQUIRED_TRADE_FIELDS = [
    "symbol",
    "side",
    "entry_time",
    "entry_price",
    "exit_time",
    "exit_price",
    "size",
    "leverage",
    "stop_price",
    "take_profit_price",
    "pnl",
    "pnl_pct",
    "reason_enter",
    "reason_exit",
    "state_before",
    "state_after",
]

REQUIRED_PERFORMANCE_FIELDS = [
    "total_return",
    "annualized_return",
    "max_drawdown",
    "win_rate",
    "profit_factor",
    "sharpe",
    "sortino",
    "average_rr",
    "average_holding_time",
    "symbol_performance",
    "portfolio_performance",
    "probe_vs_direct",
    "long_vs_short",
]

DATA_QUALITY_CHECKS = [
    "time_continuity",
    "missing_bar",
    "long_wick",
    "extreme_gap",
    "price_precision",
    "zero_volume",
    "duplicate_timestamp",
]

REQUIRED_STATE_TRANSITION_FIELDS = [
    "current_state",
    "target_state",
    "reason",
    "transition_time",
    "transition_price",
    "timeframe",
]

STRATIFIED_ANALYSIS_DIMENSIONS = [
    "symbol",
    "timeframe",
    "market_regime",
    "side",
    "signal_type",
    "single_vs_portfolio",
    "volatility_regime",
]

REQUIRED_OUTPUT_ARTIFACTS = [
    "equity_curve",
    "trade_detail",
    "performance_summary",
    "drawdown_summary",
    "state_machine_stats",
    "rejection_stats",
    "failure_samples",
    "strategy_version",
    "parameter_snapshot",
]


@dataclass(frozen=True)
class ProtocolCheck:
    name: str
    passed: bool
    reason: str


@dataclass(frozen=True)
class WalkForwardWindow:
    train_start: int
    train_end: int
    validation_start: int
    validation_end: int


def validate_processing_order(order: list[str]) -> ProtocolCheck:
    if order == BACKTEST_PROCESSING_ORDER:
        return ProtocolCheck("processing_order", True, "fixed processing order approved")
    return ProtocolCheck("processing_order", False, "must use fixed processing order with exits before entries")


def validate_candle_continuity(candles: list[Candle], timeframe_seconds: int) -> list[ProtocolCheck]:
    if timeframe_seconds <= 0:
        raise ValueError("timeframe_seconds must be positive")
    results = []
    seen = set()
    sorted_candles = sorted(candles, key=lambda item: item.open_time)
    for index, item in enumerate(sorted_candles):
        if item.open_time in seen:
            results.append(ProtocolCheck("duplicate_timestamp", False, f"duplicate timestamp {item.open_time}"))
        seen.add(item.open_time)
        if item.volume <= 0:
            results.append(ProtocolCheck("zero_volume", False, f"zero volume at {item.open_time}"))
        if item.high < max(item.open, item.close) or item.low > min(item.open, item.close):
            results.append(ProtocolCheck("ohlc_integrity", False, f"invalid OHLC at {item.open_time}"))
        if index > 0:
            expected = sorted_candles[index - 1].open_time + timeframe_seconds
            if item.open_time != expected:
                results.append(ProtocolCheck("time_gap", False, f"gap before {item.open_time}"))
    if not results:
        results.append(ProtocolCheck("candle_continuity", True, "candles are continuous"))
    return results


def validate_data_quality(
    candles: list[Candle],
    timeframe_seconds: int,
    max_wick_ratio: float = 0.80,
    max_gap_pct: float = 0.20,
    max_price_decimals: int = 8,
) -> list[ProtocolCheck]:
    results = validate_candle_continuity(candles, timeframe_seconds)
    sorted_candles = sorted(candles, key=lambda item: item.open_time)
    previous_close = None
    for item in sorted_candles:
        body = abs(item.close - item.open)
        candle_range = item.high - item.low
        if candle_range <= 0:
            results.append(ProtocolCheck("ohlc_integrity", False, f"invalid range at {item.open_time}"))
        elif body > 0:
            upper_wick = item.high - max(item.open, item.close)
            lower_wick = min(item.open, item.close) - item.low
            if max(upper_wick, lower_wick) / candle_range > max_wick_ratio:
                results.append(ProtocolCheck("long_wick", False, f"long wick at {item.open_time}"))
        if previous_close is not None and previous_close > 0:
            gap_pct = abs(item.open - previous_close) / previous_close
            if gap_pct > max_gap_pct:
                results.append(ProtocolCheck("extreme_gap", False, f"extreme gap at {item.open_time}"))
        for field_name in ("open", "high", "low", "close"):
            if _decimal_places(getattr(item, field_name)) > max_price_decimals:
                results.append(ProtocolCheck("price_precision", False, f"price precision too high at {item.open_time}"))
                break
        previous_close = item.close
    if all(result.passed for result in results):
        return [ProtocolCheck("data_quality", True, "data quality approved")]
    return results


def validate_timeframe_alignment(
    base_close_time: int,
    higher_close_time: int,
    higher_timeframe_seconds: int,
) -> ProtocolCheck:
    if higher_timeframe_seconds <= 0:
        raise ValueError("higher_timeframe_seconds must be positive")
    if higher_close_time > base_close_time:
        return ProtocolCheck("timeframe_alignment", False, "future higher timeframe bar is not allowed")
    if higher_close_time % higher_timeframe_seconds != 0:
        return ProtocolCheck("timeframe_alignment", False, "higher timeframe close is misaligned")
    return ProtocolCheck("timeframe_alignment", True, "higher timeframe uses completed UTC-aligned bar")


def validate_state_transition_fields(fields: set[str]) -> ProtocolCheck:
    missing = sorted(set(REQUIRED_STATE_TRANSITION_FIELDS) - fields)
    if missing:
        return ProtocolCheck("state_transition_fields", False, f"missing state transition fields: {missing}")
    return ProtocolCheck("state_transition_fields", True, "state transition fields complete")


def validate_stratified_analysis_dimensions(dimensions: set[str]) -> ProtocolCheck:
    missing = sorted(set(STRATIFIED_ANALYSIS_DIMENSIONS) - dimensions)
    if missing:
        return ProtocolCheck("stratified_analysis", False, f"missing analysis dimensions: {missing}")
    return ProtocolCheck("stratified_analysis", True, "stratified analysis dimensions complete")


def validate_output_artifacts(artifacts: set[str]) -> ProtocolCheck:
    missing = sorted(set(REQUIRED_OUTPUT_ARTIFACTS) - artifacts)
    if missing:
        return ProtocolCheck("output_artifacts", False, f"missing output artifacts: {missing}")
    return ProtocolCheck("output_artifacts", True, "output artifacts complete")


def generate_walk_forward_windows(
    start_ts: int,
    end_ts: int,
    train_seconds: int,
    validation_seconds: int,
    step_seconds: int,
) -> list[WalkForwardWindow]:
    if end_ts <= start_ts:
        raise ValueError("end_ts must be greater than start_ts")
    if min(train_seconds, validation_seconds, step_seconds) <= 0:
        raise ValueError("window sizes must be positive")
    windows = []
    cursor = start_ts
    while cursor + train_seconds + validation_seconds <= end_ts:
        train_start = cursor
        train_end = cursor + train_seconds
        validation_start = train_end
        validation_end = validation_start + validation_seconds
        windows.append(WalkForwardWindow(train_start, train_end, validation_start, validation_end))
        cursor += step_seconds
    return windows


def validate_backtest_protocol(
    fee_bps: float,
    slippage_bps: float,
    fill_model: str,
    uses_position_sizer: bool,
    trade_fields: set[str],
    performance_fields: set[str],
) -> list[ProtocolCheck]:
    checks = [
        ProtocolCheck("fee", fee_bps > 0, "fee bps must be included"),
        ProtocolCheck("slippage", slippage_bps > 0, "slippage bps must be included"),
        ProtocolCheck(
            "fill_model",
            fill_model in {"next_bar_open", "trigger_price", "conservative_limit"},
            "approved fill model required",
        ),
        ProtocolCheck("position_model", uses_position_sizer, "backtest must use live position sizing model"),
    ]
    missing_trade = sorted(set(REQUIRED_TRADE_FIELDS) - trade_fields)
    checks.append(
        ProtocolCheck(
            "trade_fields",
            not missing_trade,
            f"missing trade fields: {missing_trade}" if missing_trade else "trade fields complete",
        )
    )
    missing_perf = sorted(set(REQUIRED_PERFORMANCE_FIELDS) - performance_fields)
    checks.append(
        ProtocolCheck(
            "performance_fields",
            not missing_perf,
            f"missing performance fields: {missing_perf}" if missing_perf else "performance fields complete",
        )
    )
    checks.append(validate_processing_order(BACKTEST_PROCESSING_ORDER))
    return checks


def _decimal_places(value: float) -> int:
    text = f"{value:.12f}".rstrip("0").rstrip(".")
    if "." not in text:
        return 0
    return len(text.split(".", 1)[1])
""",
    "src/backtest/engine.py": """
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

BACKTEST_REQUIRED_INPUTS = [
    "run_id", "strategy_name", "strategy_version", "config_version", "data_version",
    "symbols", "timeframes", "start_time", "end_time", "initial_capital",
    "fee_model", "slippage_model", "funding_model", "fill_model",
    "capital_constraints", "risk_constraints", "entry_modes", "source",
]
BACKTEST_RESULT_FIELDS = [
    "run_id", "status", "final_equity", "total_return", "annual_return",
    "max_drawdown", "profit_factor", "sharpe", "sortino", "win_rate",
    "avg_win", "avg_loss", "expectancy", "trade_count", "symbol_breakdown",
    "side_breakdown", "entry_mode_breakdown", "summary_json", "report_path",
]
BACKTEST_STEP_ORDER = [
    "update_current_time_step_data",
    "update_indicators",
    "update_multi_timeframe_context",
    "update_current_position_state",
    "check_exits",
    "check_reductions",
    "check_additions",
    "check_entries",
    "simulate_order_submit_and_fill",
    "write_events_logs_snapshots",
    "advance",
]
BACKTEST_FILL_MODELS = ["NEXT_BAR_OPEN", "TRIGGER_PRICE", "CONSERVATIVE_LIMIT_FILL"]
BACKTEST_REQUIRED_EVENTS = ["BACKTEST_STEP_COMPLETED", "SIGNAL_CREATED", "RISK_BLOCKED", "ORDER_SUBMITTED", "ORDER_FILLED", "ORDER_REJECTED", "POSITION_OPENED", "POSITION_REDUCED", "POSITION_CLOSED", "STOP_HIT", "TP_HIT", "COOLDOWN_STARTED", "COOLDOWN_ENDED"]
BACKTEST_ARTIFACTS = ["backtest_result.json", "trade_log.csv", "equity_curve.csv", "drawdown_curve.csv", "state_transitions.csv", "risk_events.csv", "signal_events.csv", "performance_summary.md", "performance_summary.html"]
BACKTEST_FORBIDDEN_ACTIONS = ["use_future_bar", "use_unfinished_higher_timeframe_bar", "change_strategy_rules", "skip_fee_slippage_or_funding", "auto_fill_uncrossed_limit_order", "promote_probe_to_direct", "ignore_risk_block", "call_exchange_or_live_adapter"]
BACKTEST_ANALYSIS_DIMENSIONS = ["symbol", "timeframe", "side", "entry_mode", "market_state", "volatility_state", "risk_level", "holding_time", "trading_session"]
BACKTEST_FAILURE_SAMPLE_TYPES = ["signal_rejected", "risk_blocked", "position_rejected", "execution_rejected", "stop_hit", "cooldown_triggered"]


@dataclass(frozen=True)
class BacktestRequest:
    run_id: str
    strategy_name: str
    strategy_version: str
    config_version: str
    data_version: str
    symbols: list[str]
    timeframes: list[str]
    start_time: int
    end_time: int
    initial_capital: float
    fee_model: Mapping[str, Any] = field(default_factory=dict)
    slippage_model: Mapping[str, Any] = field(default_factory=dict)
    funding_model: Mapping[str, Any] = field(default_factory=dict)
    fill_model: str = "NEXT_BAR_OPEN"
    capital_constraints: Mapping[str, Any] = field(default_factory=dict)
    risk_constraints: Mapping[str, Any] = field(default_factory=dict)
    entry_modes: list[str] = field(default_factory=lambda: ["PROBE", "DIRECT"])
    source: str = "historical"


@dataclass(frozen=True)
class BacktestBar:
    symbol: str
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float


def build_artifact_manifest(request: BacktestRequest) -> dict[str, str]:
    return {name: f"reports/backtests/{request.run_id}/{name}" for name in BACKTEST_ARTIFACTS}
""",
    "src/reporting/__init__.py": '"""Reporting helpers."""',
    "src/reporting/trade_journal.py": """
from __future__ import annotations


def journal_row(**kwargs) -> dict:
    return dict(kwargs)
""",
    "src/reporting/performance_summary.py": """
from __future__ import annotations

from src.backtest.metrics import profit_factor, win_rate


def summarize_trade_pnls(pnls: list[float]) -> dict:
    return {
        "trade_count": len(pnls),
        "win_rate": win_rate(pnls),
        "profit_factor": profit_factor(pnls),
        "net_pnl": sum(pnls),
    }
""",
    "src/utils/__init__.py": '"""Shared utilities."""',
    "src/utils/timeframe.py": """
from __future__ import annotations


TIMEFRAME_SECONDS = {
    "15m": 15 * 60,
    "30m": 30 * 60,
    "1h": 60 * 60,
    "4h": 4 * 60 * 60,
}


def timeframe_seconds(timeframe: str) -> int:
    return TIMEFRAME_SECONDS[timeframe]
""",
    "src/utils/validation.py": """
from __future__ import annotations


def require_positive(value: float, name: str) -> None:
    if value <= 0:
        raise ValueError(f"{name} must be positive")
""",
    "src/utils/logger.py": """
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
""",
    "src/observability/__init__.py": '"""Observability contracts for logs and metrics."""',
    "src/observability/logging_metrics.py": """
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
METRIC_GROUPS = {
    "indicator_monitoring": ["signal_count", "trigger_count", "filled_count"],
    "state_machine": ["flat_time", "watch_time", "probe_time", "direct_time"],
    "risk": ["stop_loss_count", "take_profit_count", "forced_liquidation_count", "cooldown_count"],
}
DAILY_KPI_FIELDS = ["trade_count", "win_rate", "net_profit", "loss_count"]
CORE_METRICS = ["profit_factor", "sharpe", "max_drawdown", "expectancy"]
SYSTEM_METRICS = ["cpu", "ram", "api_latency", "order_latency"]
REPORT_FILENAMES = {
    "daily": "daily_report.html",
    "weekly": "weekly_report.html",
    "monthly": "monthly_report.html",
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


def report_filename(period: str) -> str:
    value = period.strip().lower()
    if value not in REPORT_FILENAMES:
        raise ValueError("period must be daily, weekly, or monthly")
    return REPORT_FILENAMES[value]
""",
    "scripts/describe_logging_metrics.py": """
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
""",
    "tests/test_logging_metrics.py": """
import json
import logging

import pytest

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
    LogEvent,
    build_daily_kpi_summary,
    build_json_log,
    render_prometheus_metrics,
    report_filename,
    validate_log_event,
)
from src.utils.logger import log_json


class CaptureLogger:
    def __init__(self):
        self.records = []

    def log(self, level, message):
        self.records.append((level, message))


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
        "profit_factor": pytest.approx(125 / 75),
        "expectancy": 12.5,
    }


def test_render_prometheus_metrics_uses_text_exposition_format():
    rendered = render_prometheus_metrics({"order_latency": 12.5, "signal_count": 3})
    assert "ai300_order_latency 12.5" in rendered
    assert "ai300_signal_count 3" in rendered
    assert rendered.endswith("\\n")


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
""",
    "tests/test_describe_logging_metrics.py": """
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
""",
    "scripts/describe_entry_state_machine.py": """
from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.state_machine.entry_state_machine import (
    ALLOWED_TRANSITIONS,
    ENTRY_STATE_CATEGORIES,
    ENTRY_STATE_FORBIDDEN_ACTIONS,
    ENTRY_STATE_VERSION,
    TRANSITION_BLOCKERS,
    TRANSITION_LOG_FIELDS,
    TRANSITION_SOURCES,
    EntryState,
)


def main() -> None:
    payload = {
        "version": ENTRY_STATE_VERSION,
        "initial_state": EntryState.FLAT.value,
        "states": [state.value for state in EntryState],
        "state_categories": ENTRY_STATE_CATEGORIES,
        "probe_upgrade_r": 1.0,
        "required_log_fields": list(TRANSITION_LOG_FIELDS),
        "transition_sources": list(TRANSITION_SOURCES),
        "transition_blockers": list(TRANSITION_BLOCKERS),
        "forbidden_actions": list(ENTRY_STATE_FORBIDDEN_ACTIONS),
        "allowed_transitions": {
            state.value: sorted(target.value for target in targets)
            for state, targets in ALLOWED_TRANSITIONS.items()
        },
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
""",
    "scripts/describe_risk_exit_rules.py": """
from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.risk.exit_engine import EXIT_PRIORITY


def main() -> None:
    payload = {
        "initial_stop_source": "ATR only",
        "exit_priority": [item.value for item in EXIT_PRIORITY],
        "take_profit": {"r_levels": [1.0, 2.0, 3.0], "reduce_pcts": [0.30, 0.40, 0.30]},
        "breakeven_buffer": ["fee", "slippage", "safety"],
        "cooldown": {"default_timeframe": "15m", "normal_stop_bars": [3, 6]},
        "forbidden": [
            "multiple active stop systems",
            "execution layer rewriting risk model",
            "lower-priority exit overriding higher-priority exit",
            "loss averaging",
        ],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
""",
    "scripts/describe_backtest_protocol.py": """
from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.backtest.protocol import (
    BACKTEST_PROCESSING_ORDER,
    DATA_QUALITY_CHECKS,
    REQUIRED_OUTPUT_ARTIFACTS,
    REQUIRED_PERFORMANCE_FIELDS,
    REQUIRED_STATE_TRANSITION_FIELDS,
    REQUIRED_TRADE_FIELDS,
    STRATIFIED_ANALYSIS_DIMENSIONS,
)


def main() -> None:
    payload = {
        "base_timeframe": "15m",
        "higher_timeframes": ["30m", "1h", "4h"],
        "processing_order": BACKTEST_PROCESSING_ORDER,
        "approved_fill_models": ["next_bar_open", "trigger_price", "conservative_limit"],
        "costs_required": ["fee", "slippage"],
        "data_quality_checks": DATA_QUALITY_CHECKS,
        "required_trade_fields": REQUIRED_TRADE_FIELDS,
        "required_performance_fields": REQUIRED_PERFORMANCE_FIELDS,
        "required_state_transition_fields": REQUIRED_STATE_TRANSITION_FIELDS,
        "stratified_analysis_dimensions": STRATIFIED_ANALYSIS_DIMENSIONS,
        "required_output_artifacts": REQUIRED_OUTPUT_ARTIFACTS,
        "validation_features": [
            "data_quality",
            "timeframe_alignment",
            "state_transition_logs",
            "walk_forward",
            "output_artifacts",
        ],
        "forbidden": [
            "future data",
            "unfinished candle final values",
            "ignoring fees or slippage",
            "inflating probe into direct",
        ],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
""",
    "scripts/describe_position_sizing.py": """
from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.risk.position_sizer import (
    ENTRY_MODE_MULTIPLIERS,
    MARKET_TIER_MULTIPLIERS,
    POSITION_DECISION_STEPS,
    POSITION_LOG_FIELDS,
    POSITION_REQUIRED_INPUTS,
    STATE_POSITION_POLICY,
    VOLATILITY_FACTORS,
    PositionSizingInput,
    calculate_position_size,
)


def _sample(signal_type: str) -> dict:
    result = calculate_position_size(
        PositionSizingInput(
            symbol="BTCUSDT",
            signal_type=signal_type,
            entry_mode=signal_type,
            equity=10_000,
            available_margin=5_000,
            price=50_000,
            leverage=5,
            stop_pct=0.02,
            atr=800,
            risk_pct=0.01,
            market_tier="B",
            current_open_exposure=0,
            portfolio_correlation=0.2,
            min_notional=5,
            max_total_exposure_pct=0.75,
            max_symbol_exposure_pct=0.75,
            max_correlation_group_exposure_pct=0.75,
        )
    )
    return {
        "decision": result.decision,
        "notional": result.notional,
        "quantity": result.quantity,
        "required_margin": result.required_margin,

}


def main() -> None:
    payload = {
        "formula": "position_notional = risk_amount / stop_pct",
        "signal_multipliers": ENTRY_MODE_MULTIPLIERS,
        "entry_mode_multipliers": ENTRY_MODE_MULTIPLIERS,
        "market_tier_multipliers": MARKET_TIER_MULTIPLIERS,
        "volatility_factors": VOLATILITY_FACTORS,
        "minimum_notional_policy": "reject; never inflate",
        "no_trade_policy": "return NO_TRADE; never inflate or promote",
        "required_inputs": POSITION_REQUIRED_INPUTS,
        "decision_steps": POSITION_DECISION_STEPS,
        "log_fields": POSITION_LOG_FIELDS,
        "state_policy": STATE_POSITION_POLICY,
        "sample": {"direct": _sample("DIRECT"), "probe": _sample("PROBE")},
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
""",
    "scripts/describe_multi_tf_rules.py": """
from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.context.multi_tf_rules import (
    TIMEFRAME_FORBIDDEN_ACTIONS,
    TIMEFRAME_OUTPUT_FIELDS,
    TIMEFRAME_PRIORITY,
    TIMEFRAME_ROLES,
    TIMEFRAME_STATE_SETS,
)


def main() -> None:
    payload = {
        "roles": TIMEFRAME_ROLES,
        "priority": TIMEFRAME_PRIORITY,
        "output_fields": TIMEFRAME_OUTPUT_FIELDS,
        "state_sets": TIMEFRAME_STATE_SETS,
        "outputs": ["DIRECT", "PROBE", "WAIT", "NO_TRADE"],
        "rule": "4h is reference only; 1h permission controls direction; 15m controls timing only",
        "conflict_policy": {
            "4h_vs_1h": "downgrade_direct_to_probe_or_wait",
            "1h_vs_30m": "weak_quality_cannot_direct",
            "30m_vs_15m": "wait_when_trigger_missing",
            "15m_vs_cvd": "divergence_downgrades_to_wait_or_no_trade",
        },
        "signal_mapping_examples": [
            {"4h": "NEUTRAL", "1h": "LONG_ALLOWED", "30m": "CONFIRMED", "15m": "DIRECT", "signal": "DIRECT_LONG"},
            {"4h": "BULL", "1h": "LONG_ALLOWED", "30m": "WEAK", "15m": "DIRECT", "signal": "PROBE_LONG"},
            {"4h": "BEAR", "1h": "NO_TRADE", "30m": "CONFIRMED", "15m": "DIRECT", "signal": "NO_TRADE"},
            {"4h": "NEUTRAL", "1h": "SHORT_ALLOWED", "30m": "TRANSITION", "15m": "WAIT", "signal": "WAIT_SHORT"},
        ],
        "forbidden_actions": TIMEFRAME_FORBIDDEN_ACTIONS,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
""",
    "scripts/describe_indicator_rules.py": """
from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.data_contract import INDICATOR_REQUIRED_OUTPUTS, QUALITY_FLAGS
from src.indicators.indicator_spec import (
    DEFAULT_INDICATOR_PARAMS,
    GLOBAL_FORBIDDEN_INDICATOR_ACTIONS,
    INDICATOR_CACHE_FIELDS,
    INDICATOR_CONFLICT_PRIORITY,
    INDICATOR_FORBIDDEN_USAGES,
    INDICATOR_INPUT_FIELDS,
    INDICATOR_NAMES,
    INDICATOR_OUTPUT_FIELDS,
    INDICATOR_RESPONSIBILITIES,
    TIMEFRAME_INDICATOR_MAP,
)


def main() -> None:
    payload = {
        "indicator_names": INDICATOR_NAMES,
        "params": DEFAULT_INDICATOR_PARAMS,
        "responsibilities": INDICATOR_RESPONSIBILITIES,
        "input_fields": INDICATOR_INPUT_FIELDS,
        "output_fields": INDICATOR_OUTPUT_FIELDS,
        "quality_flags": QUALITY_FLAGS,
        "required_outputs": INDICATOR_REQUIRED_OUTPUTS,
        "timeframe_indicator_map": TIMEFRAME_INDICATOR_MAP,
        "conflict_priority": INDICATOR_CONFLICT_PRIORITY,
        "forbidden_usages": INDICATOR_FORBIDDEN_USAGES,
        "global_forbidden_actions": GLOBAL_FORBIDDEN_INDICATOR_ACTIONS,
        "cache_fields": INDICATOR_CACHE_FIELDS,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
""",
    "scripts/describe_data_contract.py": """
from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.data_contract import (
    ACCOUNT_SNAPSHOT_FIELDS,
    AGGREGATION_RULES,
    CACHE_CONTRACT_FIELDS,
    CVD_SOURCES,
    DATA_CONTRACT_FORBIDDEN,
    DATA_LAYERS,
    DATA_SOURCES,
    EXECUTION_FIELDS,
    FULL_CANDLE_FIELDS,
    INDICATOR_CONTRACT_FIELDS,
    INDICATOR_REQUIRED_OUTPUTS,
    POSITION_SNAPSHOT_FIELDS,
    QUALITY_FLAGS,
    REQUIRED_CANDLE_FIELDS,
    REQUIRED_DATA_TYPES,
    STORAGE_CONTRACT,
    STRATEGY_CONTEXT_FIELDS,
    STRATEGY_EVENT_FIELDS,
    STRATEGY_EVENT_TYPES,
    SUPPORTED_TIMEFRAMES,
    TIMEFRAME_ROLES,
    UNIVERSE_ITEM_FIELDS,
    VERSION_FIELDS,
)


def main() -> None:
    payload = {
        "required_data_types": REQUIRED_DATA_TYPES,
        "data_layers": DATA_LAYERS,
        "data_sources": DATA_SOURCES,
        "required_candle_fields": REQUIRED_CANDLE_FIELDS,
        "full_candle_fields": FULL_CANDLE_FIELDS,
        "supported_timeframes": SUPPORTED_TIMEFRAMES,
        "timeframe_roles": TIMEFRAME_ROLES,
        "aggregation_rules": AGGREGATION_RULES,
        "cvd_sources": CVD_SOURCES,
        "cvd_features": ["cumulative", "delta", "slope", "divergence"],
        "indicator_input": "candles: list[OHLCV]",
        "indicator_contract_fields": INDICATOR_CONTRACT_FIELDS,
        "indicator_required_outputs": INDICATOR_REQUIRED_OUTPUTS,
        "strategy_context_fields": STRATEGY_CONTEXT_FIELDS,
        "strategy_event_fields": STRATEGY_EVENT_FIELDS,
        "strategy_event_types": STRATEGY_EVENT_TYPES,
        "execution_fields": EXECUTION_FIELDS,
        "account_snapshot_fields": ACCOUNT_SNAPSHOT_FIELDS,
        "position_snapshot_fields": POSITION_SNAPSHOT_FIELDS,
        "universe_item_fields": UNIVERSE_ITEM_FIELDS,
        "quality_flags": QUALITY_FLAGS,
        "cache_contract_fields": CACHE_CONTRACT_FIELDS,
        "version_fields": VERSION_FIELDS,
        "storage_contract": STORAGE_CONTRACT,
        "forbidden": DATA_CONTRACT_FORBIDDEN,
        "time_axis": "UTC",
        "future_leakage": "forbidden",
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
""",
    "scripts/describe_project_rules.py": """
from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

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
from src.core.strategy_philosophy import (
    ALLOWED_TRADE_TYPES,
    ANTI_NOISE_RULES,
    ANTI_OVERFIT_RULES,
    CAPITAL_MANAGEMENT_PRINCIPLES,
    DECISION_PRIORITY,
    EXIT_PHILOSOPHY,
    FIRST_PRINCIPLES,
    INDICATOR_RESPONSIBILITIES,
    MARKET_STATES,
    PHILOSOPHY_FORBIDDEN_PATTERNS,
    STRATEGY_IDENTITY,
    STRATEGY_NON_GOALS,
    TIMEFRAME_ROLES,
    UNCERTAINTY_ACTIONS,
    UNCERTAINTY_FORBIDDEN_ACTIONS,
)
from src.data.universe_filter import (
    MAX_MISSING_BAR_RATIO,
    MAX_SPREAD_PCT,
    MAX_SYMBOLS,
    MAX_SYMBOLS_HARD_CAP,
    MEME_POLICY,
    MIN_LISTING_DAYS,
    RECOMMENDED_MIN_24H_VOLUME_USD,
    REQUIRED_TIMEFRAMES,
    UNIVERSE_SCOPE,
    UNIVERSE_STATUSES,
    UPDATE_FREQUENCY,
)


def main() -> None:
    payload = {
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
        "philosophy": {
            "strategy_identity": STRATEGY_IDENTITY,
            "strategy_non_goals": STRATEGY_NON_GOALS,
            "first_principles": FIRST_PRINCIPLES,
            "market_states": MARKET_STATES,
            "timeframe_roles": TIMEFRAME_ROLES,
            "indicator_responsibilities": INDICATOR_RESPONSIBILITIES,
            "decision_priority": DECISION_PRIORITY,
            "allowed_trade_types": ALLOWED_TRADE_TYPES,
            "anti_noise_rules": ANTI_NOISE_RULES,
            "anti_overfit_rules": ANTI_OVERFIT_RULES,
            "capital_management_principles": CAPITAL_MANAGEMENT_PRINCIPLES,
            "exit_philosophy": EXIT_PHILOSOPHY,
            "uncertainty_actions": UNCERTAINTY_ACTIONS,
            "uncertainty_forbidden_actions": UNCERTAINTY_FORBIDDEN_ACTIONS,
            "forbidden_patterns": PHILOSOPHY_FORBIDDEN_PATTERNS,
        },
        "universe": {
            "scope": UNIVERSE_SCOPE,
            "max_symbols": MAX_SYMBOLS,
            "max_symbols_hard_cap": MAX_SYMBOLS_HARD_CAP,
            "min_24h_volume_usd": RECOMMENDED_MIN_24H_VOLUME_USD,
            "min_listing_days": MIN_LISTING_DAYS,
            "max_spread_pct": MAX_SPREAD_PCT,
            "max_missing_bar_ratio": MAX_MISSING_BAR_RATIO,
            "update_frequency": UPDATE_FREQUENCY,
            "required_timeframes": REQUIRED_TIMEFRAMES,
            "statuses": UNIVERSE_STATUSES,
            "meme_policy": MEME_POLICY,
            "max_simultaneous_positions": 5,
            "recommended_positions": 3,
            "single_symbol_exposure": 0.20,
            "refresh_time_utc": "00:00",
        },
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
""",
    "tests/test_project_spec.py": """
from src.core.project_spec import (
    BACKTEST_GOALS,
    BANNED_FEATURES,
    CORE_DESIGN_GOALS,
    CORE_TIMEFRAMES,
    ENTRY_FORMS,
    FINAL_SYSTEM_TRAITS,
    IMPLEMENTATION_PRINCIPLES,
    INDICATOR_RESPONSIBILITIES,
    LAYER_ORDER,
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
    TIMEFRAME_ROLES,
    TRADING_DECISION_PRINCIPLES,
    UNIFIED_CONTRACTS,
    validate_entry_form,
    validate_feature_allowed,
    validate_timeframe_role,
)


def test_project_priority_matches_docs():
    assert PROJECT_PRIORITY == ("stability", "explainability", "profitability")


def test_timeframes_match_docs():
    assert CORE_TIMEFRAMES == ("15m", "30m", "1h")
    assert REFERENCE_TIMEFRAMES == ("4h",)


def test_banned_watchlist_promotion_is_rejected():
    ok, reason = validate_feature_allowed("watchlist promotion")
    assert ok is False
    assert "Watchlist Promotion" in reason


def test_layer_order_has_risk_before_execution():
    assert LAYER_ORDER.index("risk") < LAYER_ORDER.index("execution")


def test_success_criteria_contains_core_metrics():
    assert SUCCESS_CRITERIA["max_drawdown_lt"] == 0.20
    assert SUCCESS_CRITERIA["profit_factor_gt"] == 1.5
    assert "Watchlist Promotion" in BANNED_FEATURES


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
""",
    "tests/test_describe_project_rules.py": """
import json
import subprocess
import sys


def test_describe_project_rules_outputs_json():
    result = subprocess.run(
        [sys.executable, "scripts/describe_project_rules.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    assert payload["project"]["priority"][0] == "stability"
    assert payload["philosophy"]["timeframe_roles"]["4h"] == "background"
    assert payload["universe"]["max_simultaneous_positions"] == 5


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


def test_describe_project_rules_outputs_expanded_market_universe_contract():
    result = subprocess.run(
        [sys.executable, "scripts/describe_project_rules.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    universe = payload["universe"]
    assert universe["scope"] == "binance_usdt_perpetual"
    assert universe["max_symbols"] == 20
    assert universe["max_symbols_hard_cap"] == 30
    assert universe["min_24h_volume_usd"] == 300000000
    assert universe["min_listing_days"] == 365
    assert universe["max_spread_pct"] == 0.05
    assert universe["required_timeframes"] == ["15m", "30m", "1h", "4h"]
    assert universe["statuses"] == ["ACTIVE", "SUSPENDED", "REMOVED"]
""",
    "tests/test_framework_scaffold.py": """
from pathlib import Path

from src.backtest.fill_model import next_bar_market_fill
from src.risk.position_sizer import reject_if_below_min_notional, size_notional
from src.state_machine.entry_state_machine import EntryState, transition
from scripts.scaffold_ai300_framework import FILES


def test_probe_is_quarter_direct():
    direct = size_notional(10000, 0.01, 0.02, "DIRECT")
    probe = size_notional(10000, 0.01, 0.02, "PROBE")
    assert probe == direct * 0.25


def test_probe_below_min_notional_rejects_instead_of_inflating():
    ok, reason = reject_if_below_min_notional(4.0, 5.0)
    assert ok is False
    assert "skip" in reason


def test_buy_slippage_increases_price():
    assert next_bar_market_fill(100.0, "BUY", 10) == 100.1


def test_valid_state_transition():
    assert transition(EntryState.FLAT, EntryState.WATCH_LONG) == EntryState.WATCH_LONG


def test_scaffold_includes_signal_engine_16_templates():
    assert "src/signals/signal_engine.py" in FILES
    assert "scripts/describe_signal_engine.py" in FILES
    assert "tests/test_signal_engine.py" in FILES
    assert "tests/test_describe_signal_engine.py" in FILES
    assert "SignalResult" in FILES["src/signals/signal_engine.py"]


def test_scaffold_includes_risk_engine_17_templates():
    assert "src/risk/risk_engine.py" in FILES
    assert "scripts/describe_risk_engine.py" in FILES
    assert "tests/test_risk_engine.py" in FILES
    assert "tests/test_describe_risk_engine.py" in FILES
    assert "RiskResult" in FILES["src/risk/risk_engine.py"]


def test_scaffold_includes_execution_engine_18_templates():
    assert "src/execution/execution_engine.py" in FILES
    assert "scripts/describe_execution_engine.py" in FILES
    assert "tests/test_execution_engine.py" in FILES
    assert "tests/test_describe_execution_engine.py" in FILES
    assert "ExecutionEngine" in FILES["src/execution/execution_engine.py"]


def test_scaffold_includes_backtest_engine_19_templates():
    assert "src/backtest/engine.py" in FILES
    assert "scripts/describe_backtest_engine.py" in FILES
    assert "tests/test_backtest_engine.py" in FILES
    assert "tests/test_describe_backtest_engine.py" in FILES
    assert "BacktestRequest" in FILES["src/backtest/engine.py"]
    assert "BACKTEST_STEP_ORDER" in FILES["src/backtest/engine.py"]


def test_scaffold_includes_deployment_architecture_20_templates():
    assert "src/deployment/deployment_architecture.py" in FILES
    assert "scripts/describe_deployment_architecture.py" in FILES
    assert "tests/test_deployment_architecture.py" in FILES
    assert "tests/test_describe_deployment_architecture.py" in FILES
    assert "DeploymentPlan" in FILES["src/deployment/deployment_architecture.py"]
    assert "PROTECTION_MODE_TRIGGERS" in FILES["src/deployment/deployment_architecture.py"]


def test_scaffold_includes_expanded_strategy_philosophy_templates():
    template = FILES["src/core/strategy_philosophy.py"]
    assert "STRATEGY_IDENTITY" in template
    assert "DECISION_PRIORITY" in template
    assert "PHILOSOPHY_FORBIDDEN_PATTERNS" in template
    assert "validate_uncertainty_response" in template
    assert "validate_long_short_symmetry" in template


def test_scaffold_templates_include_expanded_project_contract():
    content = Path("scripts/scaffold_ai300_framework.py").read_text(encoding="utf-8")
    assert 'PROJECT_NAME = "多周期主流虚拟币趋势交易系统"' in content
    assert '"background_reference_only"' in content
    assert '"position_sizing"' in content
    assert '"monitoring"' in content
    assert "stable_position_and_order_recovery" in content


def test_scaffold_still_protects_binance_client():
    content = Path("scripts/scaffold_ai300_framework.py").read_text(encoding="utf-8")
    assert "src/api/binance_client.py" in content
    assert "scaffold must not modify src/binance_client.py" in content


def test_scaffold_includes_expanded_market_universe_templates():
    template = FILES["src/data/universe_filter.py"]
    assert "UNIVERSE_SCOPE" in template
    assert "UniverseSnapshot" in template
    assert "validate_snapshot_for_backtest" in template
    assert "MAX_MISSING_BAR_RATIO" in template
""",
    "tests/test_market_universe.py": """
from src.data.universe_filter import (
    MAX_MISSING_BAR_RATIO,
    MAX_SPREAD_PCT,
    MAX_SYMBOLS,
    MAX_SYMBOLS_HARD_CAP,
    MIN_LISTING_DAYS,
    RECOMMENDED_MIN_24H_VOLUME_USD,
    REQUIRED_TIMEFRAMES,
    UNIVERSE_SCOPE,
    UNIVERSE_STATUSES,
    UniverseCandidate,
    UniverseMember,
    UniverseSnapshot,
    build_universe_snapshot,
    choose_by_correlation_preference,
    filter_universe,
    get_risk_tier,
    max_position_multiplier,
    validate_candidate,
    validate_snapshot_for_backtest,
)


def test_filter_universe_keeps_valid_usdt_perps_only():
    candidates = [
        UniverseCandidate("BTCUSDT", 1, 2_000_000_000, 500, 365, False, False),
        UniverseCandidate("DOGEUSDT", 9, 500_000_000, 0.25, 365, True, False),
        UniverseCandidate("NEWUSDT", 18, 100_000_000, 10, 10, False, False),
        UniverseCandidate("ETHBTC", 2, 1_000_000_000, 1, 365, False, False),
    ]
    selected = filter_universe(candidates, max_symbols=20, min_volume_24h=50_000_000)
    assert [item.symbol for item in selected] == ["BTCUSDT"]


def test_risk_tiers_and_multipliers():
    assert get_risk_tier("BTCUSDT") == "A"
    assert max_position_multiplier("ETHUSDT") == 2.0
    assert max_position_multiplier("SOLUSDT") == 1.0
    assert max_position_multiplier("LINKUSDT") == 0.75


def test_correlation_preference_prefers_btc_over_eth():
    selected = choose_by_correlation_preference(["ETHUSDT", "BTCUSDT"])
    assert selected == ["BTCUSDT"]


def test_universe_v1_thresholds_match_doc():
    assert UNIVERSE_SCOPE == "binance_usdt_perpetual"
    assert MAX_SYMBOLS == 20
    assert MAX_SYMBOLS_HARD_CAP == 30
    assert RECOMMENDED_MIN_24H_VOLUME_USD == 300_000_000
    assert MIN_LISTING_DAYS == 365
    assert MAX_SPREAD_PCT == 0.05
    assert MAX_MISSING_BAR_RATIO == 0.005
    assert REQUIRED_TIMEFRAMES == ("15m", "30m", "1h", "4h")
    assert UNIVERSE_STATUSES == ("ACTIVE", "SUSPENDED", "REMOVED")


def test_validate_candidate_rejects_spread_missing_history_and_monitoring_tag():
    good = UniverseCandidate(
        "BTCUSDT",
        market_cap_rank=1,
        volume_24h=1_000_000_000,
        price=50_000,
        listed_days=1000,
        contract_type="USDT_PERPETUAL",
        quote_asset="USDT",
        volume_rank=1,
        spread_pct=0.03,
        missing_bar_ratio=0.0,
        timeframes=("15m", "30m", "1h", "4h"),
    )
    assert validate_candidate(good).passed is True

    wide = good.with_updates(symbol="WIDEUSDT", spread_pct=0.20)
    assert validate_candidate(wide).passed is False

    missing = good.with_updates(symbol="MISSUSDT", missing_bar_ratio=0.01)
    assert validate_candidate(missing).passed is False

    monitored = good.with_updates(symbol="TAGUSDT", monitoring_tag=True)
    assert validate_candidate(monitored).passed is False


def test_universe_snapshot_tracks_version_status_and_reasons():
    member = UniverseMember(
        symbol="BTCUSDT",
        market_cap_rank=1,
        volume_rank=1,
        status="ACTIVE",
        added_time=1_700_000_000,
        removed_time=None,
        version="2026W01",
        reason="passes_v1_filters",
    )
    snapshot = build_universe_snapshot("2026W01", [member], created_at=1_700_000_000)

    assert snapshot.version == "2026W01"
    assert snapshot.active_symbols() == ["BTCUSDT"]
    assert snapshot.members[0].reason == "passes_v1_filters"


def test_backtest_must_use_historical_universe_version():
    snapshot = UniverseSnapshot(
        version="2026W01",
        members=[],
        created_at=1_700_000_000,
        effective_from=1_700_000_000,
        effective_to=1_700_604_800,
        update_reason="weekly_refresh",
    )
    assert validate_snapshot_for_backtest(snapshot, backtest_start=1_700_100_000).passed is True
    assert validate_snapshot_for_backtest(snapshot, backtest_start=1_600_000_000).passed is False
""",
    "tests/test_position_sizing.py": """
import pytest

from src.risk.position_sizer import (
    ENTRY_MODE_MULTIPLIERS,
    NO_TRADE,
    POSITION_DECISION_STEPS,
    POSITION_LOG_FIELDS,
    POSITION_REQUIRED_INPUTS,
    STATE_POSITION_POLICY,
    PositionSizingInput,
    calculate_position_size,
    market_tier_multiplier,
    normalize_entry_mode,
    size_notional,
)


def base_request(**overrides):
    values = {
        "symbol": "BTCUSDT",
        "signal_type": "DIRECT",
        "equity": 10_000,
        "available_margin": 5_000,
        "price": 50_000,
        "leverage": 5,
        "stop_pct": 0.02,
        "atr": 800,
        "risk_pct": 0.01,
        "market_tier": "B",
        "current_open_exposure": 0,
        "portfolio_correlation": 0.2,
        "min_notional": 5,
        "max_total_exposure_pct": 0.75,
        "max_symbol_exposure_pct": 0.75,
        "max_correlation_group_exposure_pct": 0.75,
    }
    values.update(overrides)
    return PositionSizingInput(**values)


def test_size_notional_preserves_direct_probe_ratio():
    direct = size_notional(10_000, 0.01, 0.02, "DIRECT")
    probe = size_notional(10_000, 0.01, 0.02, "PROBE")
    assert direct == 5_000
    assert probe == 1_250


def test_calculate_direct_standard_notional_from_risk():
    result = calculate_position_size(base_request())
    assert result.approved is True
    assert result.standard_notional == 5_000
    assert result.notional == 5_000
    assert result.quantity == pytest.approx(0.1)
    assert result.required_margin == 1_000
    assert result.reason == "approved"


def test_calculate_probe_is_quarter_standard_notional():
    result = calculate_position_size(base_request(signal_type="PROBE"))
    assert result.approved is True
    assert result.standard_notional == 5_000
    assert result.signal_multiplier == 0.25
    assert result.notional == 1_250
    assert result.quantity == pytest.approx(0.025)


def test_probe_below_min_notional_rejects_instead_of_inflating():
    result = calculate_position_size(
        base_request(
            signal_type="PROBE",
            equity=100,
            price=100,
            risk_pct=0.01,
            stop_pct=0.10,
            min_notional=5,
        )
    )
    assert result.approved is False
    assert result.notional == 2.5
    assert result.quantity == 0
    assert "skip instead of inflating" in result.reason


def test_margin_shortfall_rejects_without_resizing():
    result = calculate_position_size(base_request(available_margin=100))
    assert result.approved is False
    assert result.notional == 5_000
    assert result.required_margin == 1_000
    assert "available margin" in result.reason


def test_total_exposure_limit_rejects_without_resizing():
    result = calculate_position_size(
        base_request(current_open_exposure=7_000, max_total_exposure_pct=0.75)
    )
    assert result.approved is False
    assert result.notional == 5_000
    assert "total exposure" in result.reason


def test_invalid_stop_pct_raises():
    with pytest.raises(ValueError, match="stop_pct must be positive"):
        calculate_position_size(base_request(stop_pct=0))


def test_market_tier_multiplier_is_metadata_not_probe_inflation():
    assert market_tier_multiplier("A") == 2.0
    assert market_tier_multiplier("B") == 1.0
    assert market_tier_multiplier("C") == 0.75
    result = calculate_position_size(base_request(signal_type="PROBE", market_tier="C"))
    assert result.signal_multiplier == 0.25
    assert result.market_tier_multiplier == 0.75
    assert result.notional == 937.5


def test_completed_position_sizing_contract_lists_doc_inputs_steps_and_logs():
    assert POSITION_REQUIRED_INPUTS == [
        "account_equity",
        "available_margin",
        "symbol_price",
        "leverage",
        "stop_pct",
        "risk_per_trade_pct",
        "symbol_tier",
        "open_exposure",
        "portfolio_exposure",
        "correlation_group",
        "position_side",
        "entry_mode",
        "volatility_state",
    ]
    assert POSITION_DECISION_STEPS == [
        "read_account_equity_and_available_margin",
        "read_entry_mode",
        "read_stop_pct",
        "calculate_standard_notional",
        "apply_symbol_tier_factor",
        "apply_portfolio_exposure_limit",
        "apply_account_risk_factor",
        "check_min_notional",
        "check_min_margin",
        "output_final_executable_size",
    ]
    assert POSITION_LOG_FIELDS == [
        "symbol",
        "entry_mode",
        "account_equity",
        "available_margin",
        "risk_amount",
        "stop_pct",
        "standard_notional",
        "probe_notional",
        "direct_notional",
        "tier_factor",
        "account_risk_factor",
        "portfolio_risk_factor",
        "final_notional",
        "final_qty",
        "min_notional_check",
        "leverage",
        "decision",
    ]


def test_entry_mode_alias_preserves_existing_signal_type_interface():
    legacy = base_request(signal_type="PROBE")
    explicit = base_request(signal_type="DIRECT", entry_mode="probe")
    assert normalize_entry_mode(legacy) == "PROBE"
    assert normalize_entry_mode(explicit) == "PROBE"
    assert ENTRY_MODE_MULTIPLIERS["DIRECT"] == 1.0
    assert ENTRY_MODE_MULTIPLIERS["PROBE"] == 0.25
    assert NO_TRADE == "NO_TRADE"
    assert STATE_POSITION_POLICY["WATCH"] == "prepare_only"
    assert STATE_POSITION_POLICY["EXIT"] == "close_only"


def test_direct_size_applies_tier_account_portfolio_and_volatility_factors():
    result = calculate_position_size(
        base_request(
            market_tier="B",
            symbol_tier="B",
            account_risk_factor=0.8,
            portfolio_risk_factor=0.5,
            volatility_state="HIGH",
        )
    )
    assert result.approved is True
    assert result.standard_notional == 5_000
    assert result.notional == 1_000
    assert result.final_notional == 1_000
    assert result.quantity == pytest.approx(0.02)
    assert result.decision == "DIRECT"
    assert result.audit["account_risk_factor"] == 0.8
    assert result.audit["portfolio_risk_factor"] == 0.5
    assert result.audit["decision"] == "DIRECT"


def test_no_trade_mode_returns_clean_no_trade_without_sizing():
    result = calculate_position_size(base_request(entry_mode="NO_TRADE"))
    assert result.approved is False
    assert result.decision == "NO_TRADE"
    assert result.notional == 0
    assert result.quantity == 0
    assert "entry mode is NO_TRADE" in result.reason


def test_state_cooldown_quality_and_leverage_gates_return_no_trade():
    assert calculate_position_size(base_request(data_quality_ok=False)).decision == "NO_TRADE"
    assert calculate_position_size(base_request(state_allows_entry=False)).decision == "NO_TRADE"
    assert calculate_position_size(base_request(cooldown_active=True)).decision == "NO_TRADE"
    assert calculate_position_size(base_request(leverage_set=False)).decision == "NO_TRADE"
    assert calculate_position_size(base_request(leverage=10, max_leverage=5)).decision == "NO_TRADE"


def test_symbol_side_correlation_and_position_count_limits_return_no_trade():
    assert calculate_position_size(
        base_request(symbol_exposure=2_000, max_symbol_exposure_pct=0.20)
    ).decision == "NO_TRADE"
    assert calculate_position_size(
        base_request(side_exposure=7_000, max_side_exposure_pct=0.75)
    ).decision == "NO_TRADE"
    assert calculate_position_size(
        base_request(correlation_group_exposure=4_500, max_correlation_group_exposure_pct=0.50)
    ).decision == "NO_TRADE"
    assert calculate_position_size(
        base_request(open_positions_count=5, max_open_positions=5)
    ).decision == "NO_TRADE"


def test_quantity_step_floors_without_inflating_notional():
    result = calculate_position_size(
        base_request(
            market_tier="B",
            quantity_step=0.03,
            price=10_000,
        )
    )
    assert result.approved is True
    assert result.quantity == pytest.approx(0.48)
    assert result.notional == pytest.approx(4_800)
    assert result.notional < result.standard_notional


def test_precision_floor_rechecks_min_notional_and_skips():
    result = calculate_position_size(
        base_request(
            signal_type="PROBE",
            market_tier="B",
            equity=100,
            price=100,
            risk_pct=0.01,
            stop_pct=0.10,
            min_notional=2.4,
            quantity_step=0.02,
        )
    )
    assert result.approved is False
    assert result.decision == "NO_TRADE"
    assert result.notional == pytest.approx(2.0)
    assert result.quantity == pytest.approx(0.02)
    assert "precision floor" in result.reason
""",
    "tests/test_describe_position_sizing.py": """
import json
import subprocess
import sys


def test_describe_position_sizing_outputs_policy_json():
    completed = subprocess.run(
        [sys.executable, "scripts/describe_position_sizing.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["formula"] == "position_notional = risk_amount / stop_pct"
    assert payload["signal_multipliers"]["DIRECT"] == 1.0
    assert payload["signal_multipliers"]["PROBE"] == 0.25
    assert payload["minimum_notional_policy"] == "reject; never inflate"
    assert payload["sample"]["probe"]["notional"] == payload["sample"]["direct"]["notional"] * 0.25


def test_describe_position_sizing_outputs_completed_06_sections():
    completed = subprocess.run(
        [sys.executable, "scripts/describe_position_sizing.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["required_inputs"][0] == "account_equity"
    assert payload["decision_steps"][0] == "read_account_equity_and_available_margin"
    assert payload["log_fields"][-1] == "decision"
    assert payload["state_policy"]["PROBE"] == "probe_size"
    assert payload["volatility_factors"]["HIGH"] == 0.5
    assert payload["no_trade_policy"] == "return NO_TRADE; never inflate or promote"
    assert payload["sample"]["probe"]["decision"] == "PROBE"
""",
    "tests/test_risk_exit_engine.py": """
import pytest

from src.risk.exit_engine import (
    EXIT_PRIORITY,
    ExitAction,
    ExitActionType,
    breakeven_stop,
    cooldown_until,
    forced_exit_actions,
    plan_take_profit_actions,
    select_highest_priority_action,
    trailing_stop_from_structure,
)
from src.risk.stop_engine import initial_atr_stop


def test_initial_atr_stop_uses_atr_distance_for_long():
    stop = initial_atr_stop(entry_price=100, atr=2, atr_mult=1.5, side="LONG")
    assert stop.stop_price == 97
    assert stop.stop_distance == 3
    assert stop.stop_pct == pytest.approx(0.03)
    assert stop.reason == "initial ATR stop"


def test_initial_atr_stop_uses_atr_distance_for_short():
    stop = initial_atr_stop(entry_price=100, atr=2, atr_mult=1.5, side="SHORT")
    assert stop.stop_price == 103
    assert stop.stop_distance == 3
    assert stop.stop_pct == pytest.approx(0.03)


def test_exit_priority_matches_spec_order():
    assert EXIT_PRIORITY == [
        ExitActionType.FORCED_STOP,
        ExitActionType.PORTFOLIO_RISK,
        ExitActionType.DIRECTION_REVERSAL,
        ExitActionType.VOLATILITY_ANOMALY,
        ExitActionType.TRAILING_STOP,
        ExitActionType.PARTIAL_TAKE_PROFIT,
    ]


def test_select_highest_priority_action_prevents_lower_priority_override():
    actions = [
        ExitAction(ExitActionType.PARTIAL_TAKE_PROFIT, "take tp1", reduce_pct=0.30),
        ExitAction(ExitActionType.FORCED_STOP, "stop hit", reduce_pct=1.0),
    ]
    selected = select_highest_priority_action(actions)
    assert selected is not None
    assert selected.action_type == ExitActionType.FORCED_STOP
    assert selected.reason == "stop hit"


def test_plan_take_profit_actions_are_r_based_partials_for_long():
    actions = plan_take_profit_actions(entry_price=100, stop_price=95, side="LONG")
    assert [action.target_price for action in actions] == [105, 110, 115]
    assert [action.reduce_pct for action in actions] == [0.30, 0.40, 0.30]
    assert all(action.action_type == ExitActionType.PARTIAL_TAKE_PROFIT for action in actions)


def test_plan_take_profit_actions_are_r_based_partials_for_short():
    actions = plan_take_profit_actions(entry_price=100, stop_price=105, side="SHORT", r_levels=(1, 2, 4))
    assert [action.target_price for action in actions] == [95, 90, 80]


def test_breakeven_stop_covers_fee_slippage_and_safety_buffer():
    stop = breakeven_stop(entry_price=100, side="LONG", fee_bps=5, slippage_bps=5, safety_bps=10)
    assert stop == pytest.approx(100.2)


def test_trailing_stop_uses_structure_without_widening_long_stop():
    action = trailing_stop_from_structure(
        side="LONG",
        current_stop=100,
        structure_price=103,
        buffer_pct=0.01,
    )
    assert action is not None
    assert action.stop_price == pytest.approx(101.97)
    assert action.action_type == ExitActionType.TRAILING_STOP


def test_trailing_stop_returns_none_when_it_would_widen_stop():
    action = trailing_stop_from_structure(
        side="LONG",
        current_stop=100,
        structure_price=99,
        buffer_pct=0.01,
    )
    assert action is None


def test_forced_exit_actions_use_highest_priority_flags():
    actions = forced_exit_actions(
        stop_hit=True,
        portfolio_risk=True,
        direction_reversal=True,
        volatility_anomaly=True,
    )
    selected = select_highest_priority_action(actions)
    assert selected is not None
    assert selected.action_type == ExitActionType.FORCED_STOP


def test_cooldown_until_counts_completed_bars():
    assert cooldown_until(now_ts=1_000, bars=4, timeframe_seconds=900) == 4_600
""",
    "tests/test_backtest_protocol.py": """
from src.backtest.protocol import (
    BACKTEST_PROCESSING_ORDER,
    DATA_QUALITY_CHECKS,
    REQUIRED_OUTPUT_ARTIFACTS,
    REQUIRED_PERFORMANCE_FIELDS,
    REQUIRED_STATE_TRANSITION_FIELDS,
    REQUIRED_TRADE_FIELDS,
    STRATIFIED_ANALYSIS_DIMENSIONS,
    WalkForwardWindow,
    generate_walk_forward_windows,
    validate_backtest_protocol,
    validate_candle_continuity,
    validate_data_quality,
    validate_output_artifacts,
    validate_processing_order,
    validate_state_transition_fields,
    validate_stratified_analysis_dimensions,
    validate_timeframe_alignment,
)
from src.core.models import Candle


def candle(open_time: int, close_time: int, volume: float = 10) -> Candle:
    return Candle(
        symbol="BTCUSDT",
        timeframe="15m",
        open_time=open_time,
        close_time=close_time,
        open=100,
        high=105,
        low=95,
        close=101,
        volume=volume,
    )


def test_processing_order_is_exit_before_entry():
    assert BACKTEST_PROCESSING_ORDER == [
        "update_history",
        "update_indicators",
        "update_multi_timeframe_context",
        "update_state",
        "check_exit",
        "check_reduce",
        "check_add",
        "check_entry",
        "record_events",
    ]
    assert validate_processing_order(BACKTEST_PROCESSING_ORDER).passed is True


def test_processing_order_rejects_entry_before_exit():
    wrong = list(BACKTEST_PROCESSING_ORDER)
    wrong[4], wrong[7] = wrong[7], wrong[4]
    result = validate_processing_order(wrong)
    assert result.passed is False
    assert "fixed processing order" in result.reason


def test_validate_candle_continuity_detects_duplicates_and_gaps():
    candles = [candle(0, 900), candle(900, 1800), candle(900, 1800), candle(2700, 3600)]
    results = validate_candle_continuity(candles, timeframe_seconds=900)
    failed = [result.reason for result in results if not result.passed]
    assert any("duplicate" in reason for reason in failed)
    assert any("gap" in reason for reason in failed)


def test_validate_backtest_protocol_requires_costs_outputs_and_position_model():
    results = validate_backtest_protocol(
        fee_bps=5,
        slippage_bps=5,
        fill_model="next_bar_open",
        uses_position_sizer=True,
        trade_fields=set(REQUIRED_TRADE_FIELDS),
        performance_fields=set(REQUIRED_PERFORMANCE_FIELDS),
    )
    assert all(result.passed for result in results)


def test_validate_backtest_protocol_rejects_missing_costs():
    results = validate_backtest_protocol(
        fee_bps=0,
        slippage_bps=0,
        fill_model="next_bar_open",
        uses_position_sizer=True,
        trade_fields=set(REQUIRED_TRADE_FIELDS),
        performance_fields=set(REQUIRED_PERFORMANCE_FIELDS),
    )
    assert any((not result.passed and "fee" in result.reason) for result in results)
    assert any((not result.passed and "slippage" in result.reason) for result in results)


def test_data_quality_check_names_cover_doc_requirements():
    assert DATA_QUALITY_CHECKS == [
        "time_continuity",
        "missing_bar",
        "long_wick",
        "extreme_gap",
        "price_precision",
        "zero_volume",
        "duplicate_timestamp",
    ]


def test_validate_data_quality_detects_long_wick_gap_precision_and_zero_volume():
    candles = [
        candle(0, 900, volume=10),
        Candle(
            symbol="BTCUSDT",
            timeframe="15m",
            open_time=900,
            close_time=1800,
            open=130.123456789,
            high=180,
            low=100,
            close=132,
            volume=0,
        ),
    ]
    results = validate_data_quality(
        candles,
        timeframe_seconds=900,
        max_wick_ratio=0.50,
        max_gap_pct=0.20,
        max_price_decimals=4,
    )
    failed = [result.reason for result in results if not result.passed]
    assert any("long wick" in reason for reason in failed)
    assert any("extreme gap" in reason for reason in failed)
    assert any("price precision" in reason for reason in failed)
    assert any("zero volume" in reason for reason in failed)


def test_validate_timeframe_alignment_requires_completed_higher_timeframe_bar():
    result = validate_timeframe_alignment(
        base_close_time=3_600,
        higher_close_time=3_600,
        higher_timeframe_seconds=3_600,
    )
    assert result.passed is True
    leaking = validate_timeframe_alignment(
        base_close_time=3_600,
        higher_close_time=7_200,
        higher_timeframe_seconds=3_600,
    )
    assert leaking.passed is False
    assert "future" in leaking.reason


def test_required_state_transition_fields_match_doc():
    assert REQUIRED_STATE_TRANSITION_FIELDS == [
        "current_state",
        "target_state",
        "reason",
        "transition_time",
        "transition_price",
        "timeframe",
    ]
    ok = validate_state_transition_fields(set(REQUIRED_STATE_TRANSITION_FIELDS))
    assert ok.passed is True
    missing = validate_state_transition_fields({"current_state"})
    assert missing.passed is False
    assert "target_state" in missing.reason


def test_stratified_analysis_dimensions_cover_doc_requirements():
    assert STRATIFIED_ANALYSIS_DIMENSIONS == [
        "symbol",
        "timeframe",
        "market_regime",
        "side",
        "signal_type",
        "single_vs_portfolio",
        "volatility_regime",
    ]
    assert validate_stratified_analysis_dimensions(set(STRATIFIED_ANALYSIS_DIMENSIONS)).passed is True


def test_required_output_artifacts_cover_doc_requirements():
    assert REQUIRED_OUTPUT_ARTIFACTS == [
        "equity_curve",
        "trade_detail",
        "performance_summary",
        "drawdown_summary",
        "state_machine_stats",
        "rejection_stats",
        "failure_samples",
        "strategy_version",
        "parameter_snapshot",
    ]
    assert validate_output_artifacts(set(REQUIRED_OUTPUT_ARTIFACTS)).passed is True


def test_generate_walk_forward_windows_rolls_train_and_validation_ranges():
    windows = generate_walk_forward_windows(
        start_ts=0,
        end_ts=10_000,
        train_seconds=4_000,
        validation_seconds=2_000,
        step_seconds=2_000,
    )
    assert windows == [
        WalkForwardWindow(train_start=0, train_end=4_000, validation_start=4_000, validation_end=6_000),
        WalkForwardWindow(train_start=2_000, train_end=6_000, validation_start=6_000, validation_end=8_000),
        WalkForwardWindow(train_start=4_000, train_end=8_000, validation_start=8_000, validation_end=10_000),
    ]
""",
    "tests/test_describe_risk_exit_rules.py": """
import json
import subprocess
import sys


def test_describe_risk_exit_rules_outputs_policy_json():
    completed = subprocess.run(
        [sys.executable, "scripts/describe_risk_exit_rules.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["initial_stop_source"] == "ATR only"
    assert payload["exit_priority"][0] == "FORCED_STOP"
    assert payload["take_profit"]["r_levels"] == [1.0, 2.0, 3.0]
    assert payload["forbidden"][0] == "multiple active stop systems"
""",
    "tests/test_describe_backtest_protocol.py": """
import json
import subprocess
import sys


def test_describe_backtest_protocol_outputs_policy_json():
    completed = subprocess.run(
        [sys.executable, "scripts/describe_backtest_protocol.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["base_timeframe"] == "15m"
    assert payload["processing_order"][4] == "check_exit"
    assert payload["processing_order"][7] == "check_entry"
    assert "sharpe" in payload["required_performance_fields"]
    assert payload["costs_required"] == ["fee", "slippage"]


def test_describe_backtest_protocol_exposes_standalone_08_requirements():
    completed = subprocess.run(
        [sys.executable, "scripts/describe_backtest_protocol.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["data_quality_checks"][0] == "time_continuity"
    assert payload["required_state_transition_fields"][0] == "current_state"
    assert "walk_forward" in payload["validation_features"]
    assert "equity_curve" in payload["required_output_artifacts"]
    assert "volatility_regime" in payload["stratified_analysis_dimensions"]
""",
    "tests/test_data_contract.py": """
import pytest

from src.core.models import Candle
from src.data.cvd_builder import build_cvd_points
from src.data.data_contract import (
    ACCOUNT_SNAPSHOT_FIELDS,
    AGGREGATION_RULES,
    CACHE_CONTRACT_FIELDS,
    CVD_SOURCES,
    CVDPoint,
    DATA_CONTRACT_FORBIDDEN,
    DATA_LAYERS,
    DATA_SOURCES,
    EXECUTION_FIELDS,
    FULL_CANDLE_FIELDS,
    INDICATOR_CONTRACT_FIELDS,
    INDICATOR_REQUIRED_OUTPUTS,
    MarketCandle,
    POSITION_SNAPSHOT_FIELDS,
    QUALITY_FLAGS,
    REQUIRED_CANDLE_FIELDS,
    REQUIRED_DATA_TYPES,
    STORAGE_CONTRACT,
    STRATEGY_CONTEXT_FIELDS,
    STRATEGY_EVENT_FIELDS,
    STRATEGY_EVENT_TYPES,
    SUPPORTED_TIMEFRAMES,
    TIMEFRAME_ROLES,
    UNIVERSE_ITEM_FIELDS,
    VERSION_FIELDS,
    IndicatorResult,
    StrategyContext,
    build_cvd_contract_points,
    judge_cvd_divergence,
    quality_allows_direct_entry,
    validate_indicator_result,
    validate_indicator_input,
    validate_market_candle,
    validate_ohlcv_contract,
    validate_required_fields,
    validate_strategy_context,
    validate_timeframe_utc_alignment,
)


def candle(**overrides) -> Candle:
    values = {
        "symbol": "BTCUSDT",
        "timeframe": "15m",
        "open_time": 0,
        "close_time": 900,
        "open": 100.0,
        "high": 105.0,
        "low": 95.0,
        "close": 101.0,
        "volume": 10.0,
        "quote_volume": 1_000.0,
        "trade_count": 20,
        "taker_buy_volume": 6.0,
    }
    values.update(overrides)
    return Candle(**values)


def test_data_contract_constants_match_doc():
    assert REQUIRED_DATA_TYPES == [
        "kline",
        "volume",
        "active_buy_sell",
        "position_or_funding",
        "universe",
    ]
    assert REQUIRED_CANDLE_FIELDS == [
        "open_time",
        "close_time",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "quote_volume",
        "trade_count",
    ]
    assert SUPPORTED_TIMEFRAMES == ["15m", "30m", "1h", "4h"]
    assert TIMEFRAME_ROLES["15m"] == "execution"
    assert TIMEFRAME_ROLES["4h"] == "background"


def test_validate_ohlcv_contract_accepts_valid_candle():
    result = validate_ohlcv_contract(candle())
    assert result.passed is True
    assert result.reason == "candle contract approved"


def test_validate_ohlcv_contract_rejects_bad_timeframe_and_ohlc():
    result = validate_ohlcv_contract(candle(timeframe="5m", high=99))
    assert result.passed is False
    assert "timeframe" in result.reason


def test_validate_ohlcv_contract_rejects_missing_volume_fields():
    result = validate_ohlcv_contract(candle(quote_volume=0, trade_count=0))
    assert result.passed is False
    assert "quote_volume" in result.reason


def test_aggregation_rules_match_doc():
    assert AGGREGATION_RULES == {
        "30m": "15m",
        "1h": ("15m", "30m"),
        "4h": "1h",
    }


def test_validate_timeframe_utc_alignment_accepts_closed_15m_grid():
    result = validate_timeframe_utc_alignment(candle(open_time=900, close_time=1800), base_close_time=1800)
    assert result.passed is True


def test_validate_timeframe_utc_alignment_rejects_future_leakage():
    result = validate_timeframe_utc_alignment(candle(open_time=1800, close_time=2700), base_close_time=1800)
    assert result.passed is False
    assert "future" in result.reason


def test_validate_indicator_input_requires_uniform_symbol_timeframe_and_order():
    candles = [candle(open_time=900, close_time=1800), candle(open_time=0, close_time=900)]
    result = validate_indicator_input(candles)
    assert result.passed is False
    assert "ordered" in result.reason

    ok = validate_indicator_input([candle(open_time=0, close_time=900), candle(open_time=900, close_time=1800)])
    assert ok.passed is True


def test_cvd_sources_match_doc():
    assert CVD_SOURCES == ["trades", "taker_buy_sell_estimate", "exchange_active_buy_sell"]


def test_build_cvd_contract_points_outputs_value_delta_slope():
    candles = [
        candle(open_time=0, close_time=900, close=100, volume=10, taker_buy_volume=6),
        candle(open_time=900, close_time=1800, close=101, volume=10, taker_buy_volume=7),
    ]
    points = build_cvd_contract_points(candles)
    assert points == [
        CVDPoint(close_time=900, cumulative=2.0, delta=2.0, slope=0.0, divergence="NONE"),
        CVDPoint(close_time=1800, cumulative=6.0, delta=4.0, slope=4.0, divergence="NONE"),
    ]
    assert build_cvd_points(candles) == points


def test_judge_cvd_divergence_detects_price_up_cvd_down():
    assert judge_cvd_divergence(price_delta=1.0, cvd_delta=-2.0) == "BEARISH"
    assert judge_cvd_divergence(price_delta=-1.0, cvd_delta=2.0) == "BULLISH"
    assert judge_cvd_divergence(price_delta=1.0, cvd_delta=2.0) == "NONE"


def market_candle(**overrides) -> MarketCandle:
    values = {
        "symbol": "BTCUSDT",
        "timeframe": "15m",
        "open_time": 0,
        "close_time": 900,
        "open": 100.0,
        "high": 105.0,
        "low": 95.0,
        "close": 101.0,
        "volume": 10.0,
        "quote_volume": 1_000.0,
        "trade_count": 20,
        "taker_buy_base_volume": 6.0,
        "taker_buy_quote_volume": 600.0,
        "is_closed": True,
        "source": "binance",
        "quality_flag": True,
    }
    values.update(overrides)
    return MarketCandle(**values)


def test_completed_doc_data_layers_and_sources():
    assert DATA_LAYERS == [
        "raw_market_data",
        "normalized_market_data",
        "multi_timeframe_data",
        "indicator_result_data",
        "strategy_context_data",
    ]
    assert DATA_SOURCES == [
        "kline",
        "volume",
        "active_buy_sell",
        "funding_rate",
        "open_interest",
        "universe",
        "execution",
        "account_position_snapshot",
    ]


def test_full_market_candle_fields_match_completed_doc():
    assert FULL_CANDLE_FIELDS == [
        "symbol",
        "timeframe",
        "open_time",
        "close_time",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "quote_volume",
        "trade_count",
        "taker_buy_base_volume",
        "taker_buy_quote_volume",
        "is_closed",
        "source",
        "quality_flag",
    ]
    assert QUALITY_FLAGS == [True, False, "degraded", "stale"]


def test_validate_market_candle_requires_closed_quality_true_data():
    check = validate_market_candle(market_candle())
    assert check.passed is True
    assert quality_allows_direct_entry(True) is True
    assert quality_allows_direct_entry("degraded") is False
    assert quality_allows_direct_entry("stale") is False


def test_validate_market_candle_rejects_unclosed_or_bad_quality_data():
    result = validate_market_candle(market_candle(is_closed=False))
    assert result.passed is False
    assert "closed" in result.reason


def test_indicator_contract_fields_and_required_outputs_match_doc():
    assert INDICATOR_CONTRACT_FIELDS == [
        "name",
        "symbol",
        "timeframe",
        "value",
        "signal",
        "trend",
        "strength",
        "timestamp",
        "metadata",
        "quality_flag",
    ]
    assert INDICATOR_REQUIRED_OUTPUTS["MACD"] == ["macd_line", "signal_line", "histogram", "histogram_slope", "cross_state"]
    assert INDICATOR_REQUIRED_OUTPUTS["ATR"] == ["atr", "atr_pct", "volatility_state"]


def test_validate_indicator_result_blocks_false_or_stale_quality():
    result = IndicatorResult(
        name="MACD",
        symbol="BTCUSDT",
        timeframe="15m",
        value={"macd_line": 1, "signal_line": 0, "histogram": 1, "histogram_slope": 0.1, "cross_state": "GOLDEN"},
        signal="LONG",
        trend="UP",
        strength=0.8,
        timestamp=900,
        metadata={},
        quality_flag=True,
    )
    assert validate_indicator_result(result).passed is True
    stale = IndicatorResult(**{**result.__dict__, "quality_flag": "stale"})
    assert validate_indicator_result(stale).passed is False


def test_strategy_context_fields_and_validation_match_doc():
    assert STRATEGY_CONTEXT_FIELDS[0] == "symbol"
    context = StrategyContext(
        symbol="BTCUSDT",
        timestamp=900,
        market_state_4h="BULL",
        trend_state_1h="LONG_ALLOWED",
        confirm_state_30m="CONFIRMED",
        trigger_state_15m="DIRECT",
        indicators_15m={},
        indicators_30m={},
        indicators_1h={},
        indicators_4h={},
        risk_snapshot={},
        position_snapshot={},
        cooldown_state={},
        signal_candidate={},
        quality_flag=True,
    )
    assert validate_strategy_context(context).passed is True
    bad = StrategyContext(**{**context.__dict__, "quality_flag": False})
    assert validate_strategy_context(bad).passed is False


def test_event_execution_account_position_and_universe_fields_match_doc():
    assert STRATEGY_EVENT_FIELDS == ["event_id", "symbol", "timeframe", "event_type", "state_before", "state_after", "reason", "score", "timestamp", "metadata"]
    assert "DATA_INVALID" in STRATEGY_EVENT_TYPES
    assert EXECUTION_FIELDS[:4] == ["order_id", "client_order_id", "symbol", "side"]
    assert ACCOUNT_SNAPSHOT_FIELDS[:3] == ["account_equity", "available_margin", "used_margin"]
    assert POSITION_SNAPSHOT_FIELDS[:4] == ["symbol", "side", "position_qty", "entry_price"]
    assert UNIVERSE_ITEM_FIELDS[-1] == "correlation_group"


def test_validate_required_fields_reports_missing_fields():
    check = validate_required_fields({"symbol": "BTCUSDT"}, ["symbol", "side"], "execution")
    assert check.passed is False
    assert "side" in check.reason
    ok = validate_required_fields({"symbol": "BTCUSDT", "side": "LONG"}, ["symbol", "side"], "execution")
    assert ok.passed is True


def test_cache_version_storage_and_forbidden_contracts_match_doc():
    assert CACHE_CONTRACT_FIELDS == ["ttl", "update_frequency", "hit_condition", "no_future_cache"]
    assert VERSION_FIELDS == ["raw_data_version", "aggregation_version", "indicator_version", "strategy_version", "risk_version", "execution_version"]
    assert STORAGE_CONTRACT["hot"] == ["recent_market", "current_position", "current_signal", "current_risk_state"]
    assert "let backtest and live use different field sets" in DATA_CONTRACT_FORBIDDEN
""",
    "src/execution/live_execution_contract.py": """
from __future__ import annotations

from dataclasses import asdict, dataclass


EXECUTION_RESPONSIBILITIES = [
    "create_order",
    "cancel_order",
    "query_order_status",
    "query_position_status",
    "sync_account_info",
    "sync_leverage_and_margin",
    "maintain_order_lifecycle_log",
    "return_raw_exchange_response",
    "standardize_execution_error",
]
EXECUTION_INPUT_FIELDS = [
    "symbol",
    "side",
    "order_type",
    "quantity",
    "price",
    "reduce_only",
    "position_side",
    "time_in_force",
    "stop_price",
    "take_profit_price",
    "client_order_id",
    "strategy_event_id",
    "strategy_state",
    "expected_position_side",
    "expected_risk_tag",
]
EXECUTION_OUTPUT_FIELDS = [
    "order_id",
    "client_order_id",
    "status",
    "filled_qty",
    "avg_price",
    "commission",
    "executed_notional",
    "reject_reason",
    "raw_response",
    "latency_ms",
    "ts",
]
SUPPORTED_ORDER_TYPES = ["MARKET", "LIMIT", "IOC", "STOP_MARKET", "TAKE_PROFIT_MARKET"]
ORDER_LIFECYCLE_STATES = [
    "created",
    "validated",
    "submitted",
    "acknowledged",
    "partially_filled",
    "filled",
    "canceled",
    "rejected",
    "expired",
    "reconciled",
]
EXECUTION_LOG_FIELDS = [
    "ts",
    "module",
    "symbol",
    "action",
    "order_type",
    "side",
    "quantity",
    "price",
    "reduce_only",
    "position_side",
    "client_order_id",
    "strategy_event_id",
    "status",
    "reject_reason",
    "order_id",
    "filled_qty",
    "avg_price",
    "commission",
    "latency_ms",
    "raw_response",
]
OBSERVABILITY_METRICS = [
    "order_success_rate",
    "reject_rate",
    "average_latency_ms",
    "protection_order_success_rate",
    "partial_fill_ratio",
    "order_retry_count",
    "sync_failure_count",
    "recovery_time_ms",
]
PROTECTION_MODE_TRIGGERS = [
    "consecutive_rejects",
    "consecutive_sync_failures",
    "consecutive_protection_order_failures",
    "abnormal_position_state",
    "unknown_order_state",
    "exchange_unavailable",
]
EXECUTION_FORBIDDEN_ACTIONS = [
    "execution layer changes strategy intent",
    "execution layer changes order quantity",
    "execution layer recalculates position size",
    "execution layer changes strategy state",
    "execution layer swallows exchange errors",
    "execution layer retries as a new strategy",
]


@dataclass(frozen=True)
class ExecutionInstruction:
    symbol: str
    side: str
    order_type: str
    quantity: float
    price: float | None
    reduce_only: bool
    position_side: str
    time_in_force: str | None
    stop_price: float | None
    take_profit_price: float | None
    client_order_id: str
    strategy_event_id: str
    strategy_state: str
    expected_position_side: str
    expected_risk_tag: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ExecutionResponse:
    order_id: str
    client_order_id: str
    status: str
    filled_qty: float
    avg_price: float
    commission: float
    executed_notional: float
    reject_reason: str
    raw_response: dict
    latency_ms: int
    ts: int

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class LifecycleEvent:
    client_order_id: str
    state: str
    ts: int
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ExecutionValidation:
    passed: bool
    reason: str


def build_idempotency_key(instruction: ExecutionInstruction) -> str:
    return ":".join(
        [
            instruction.symbol.strip().upper(),
            instruction.strategy_event_id,
            instruction.strategy_state,
            instruction.side.strip().upper(),
        ]
    )


def normalize_reject_reason(raw_message: str) -> str:
    text = raw_message.lower()
    if "timeout" in text:
        return "NETWORK_TIMEOUT"
    if "margin" in text or "-2019" in text:
        return "INSUFFICIENT_MARGIN"
    if "precision" in text:
        return "PRECISION_ERROR"
    if "leverage" in text:
        return "LEVERAGE_ERROR"
    if "reduce" in text:
        return "REDUCE_ONLY_ERROR"
    return "EXCHANGE_ERROR"


def validate_execution_instruction(
    instruction: ExecutionInstruction,
    *,
    tradable: bool = True,
    in_trade_window: bool = True,
    leverage_ready: bool = True,
    min_notional: float = 5.0,
    quantity_step: float = 0.0,
    current_position_side: str | None = None,
    account_risk_allows: bool = True,
    symbol_cooldown_active: bool = False,
) -> ExecutionValidation:
    side = instruction.side.strip().upper()
    order_type = instruction.order_type.strip().upper()
    if side not in {"BUY", "SELL"}:
        return ExecutionValidation(False, "side must be BUY or SELL")
    if order_type not in SUPPORTED_ORDER_TYPES:
        return ExecutionValidation(False, "unsupported order_type")
    if instruction.quantity <= 0:
        return ExecutionValidation(False, "quantity must be positive")
    if quantity_step > 0 and int(instruction.quantity / quantity_step) * quantity_step != instruction.quantity:
        return ExecutionValidation(False, "quantity precision is invalid")
    reference_price = instruction.price or instruction.stop_price or instruction.take_profit_price
    if reference_price is not None and instruction.quantity * reference_price < min_notional:
        return ExecutionValidation(False, "minimum notional not satisfied")
    if instruction.reduce_only and instruction.expected_risk_tag.lower() == "entry":
        return ExecutionValidation(False, "entry orders must not be reduce_only")
    if current_position_side is not None and current_position_side.upper() != instruction.expected_position_side.upper():
        return ExecutionValidation(False, "current position side mismatch")
    if not tradable:
        return ExecutionValidation(False, "symbol is not tradable")
    if not in_trade_window:
        return ExecutionValidation(False, "outside tradable execution window")
    if not leverage_ready:
        return ExecutionValidation(False, "leverage is not ready")
    if not account_risk_allows:
        return ExecutionValidation(False, "account risk blocks execution")
    if symbol_cooldown_active:
        return ExecutionValidation(False, "symbol execution cooldown is active")
    return ExecutionValidation(True, "validated")


def lifecycle_transition(
    client_order_id: str,
    previous_state: str,
    next_state: str,
    ts: int,
    reason: str,
) -> LifecycleEvent:
    if previous_state not in ORDER_LIFECYCLE_STATES or next_state not in ORDER_LIFECYCLE_STATES:
        raise ValueError("unknown lifecycle state")
    if ORDER_LIFECYCLE_STATES.index(next_state) < ORDER_LIFECYCLE_STATES.index(previous_state):
        raise ValueError("order lifecycle must not regress")
    return LifecycleEvent(client_order_id, next_state, ts, reason)


def build_execution_log(
    instruction: ExecutionInstruction,
    response: ExecutionResponse,
    *,
    action: str,
    module: str = "execution",
) -> dict:
    return {
        "ts": response.ts,
        "module": module,
        "symbol": instruction.symbol,
        "action": action,
        "order_type": instruction.order_type,
        "side": instruction.side,
        "quantity": instruction.quantity,
        "price": instruction.price,
        "reduce_only": instruction.reduce_only,
        "position_side": instruction.position_side,
        "client_order_id": instruction.client_order_id,
        "strategy_event_id": instruction.strategy_event_id,
        "status": response.status,
        "reject_reason": response.reject_reason,
        "order_id": response.order_id,
        "filled_qty": response.filled_qty,
        "avg_price": response.avg_price,
        "commission": response.commission,
        "latency_ms": response.latency_ms,
        "raw_response": response.raw_response,
    }


def build_partial_fill_snapshot(
    *,
    order_qty: float,
    filled_qty: float,
    avg_price: float,
    client_order_id: str,
) -> dict:
    return {
        "client_order_id": client_order_id,
        "order_qty": order_qty,
        "filled_qty": filled_qty,
        "remaining_qty": order_qty - filled_qty,
        "avg_price": avg_price,
        "status": "partially_filled",
    }


def should_enter_protection_mode(
    *,
    consecutive_rejects: int = 0,
    consecutive_sync_failures: int = 0,
    consecutive_protection_order_failures: int = 0,
    abnormal_position_state: bool = False,
    unknown_order_state: bool = False,
    exchange_unavailable: bool = False,
    threshold: int = 3,
) -> ExecutionValidation:
    if consecutive_rejects >= threshold:
        return ExecutionValidation(True, "consecutive rejects")
    if consecutive_sync_failures >= threshold:
        return ExecutionValidation(True, "consecutive sync failures")
    if consecutive_protection_order_failures >= threshold:
        return ExecutionValidation(True, "consecutive protection order failures")
    if abnormal_position_state:
        return ExecutionValidation(True, "abnormal position state")
    if unknown_order_state:
        return ExecutionValidation(True, "unknown order state")
    if exchange_unavailable:
        return ExecutionValidation(True, "exchange unavailable")
    return ExecutionValidation(False, "normal")
""",
    "scripts/describe_live_execution_contract.py": """
from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.execution.live_execution_contract import (
    EXECUTION_FORBIDDEN_ACTIONS,
    EXECUTION_INPUT_FIELDS,
    EXECUTION_LOG_FIELDS,
    EXECUTION_OUTPUT_FIELDS,
    EXECUTION_RESPONSIBILITIES,
    OBSERVABILITY_METRICS,
    ORDER_LIFECYCLE_STATES,
    PROTECTION_MODE_TRIGGERS,
    SUPPORTED_ORDER_TYPES,
)


def main() -> None:
    payload = {
        "responsibilities": EXECUTION_RESPONSIBILITIES,
        "input_fields": EXECUTION_INPUT_FIELDS,
        "output_fields": EXECUTION_OUTPUT_FIELDS,
        "supported_order_types": SUPPORTED_ORDER_TYPES,
        "lifecycle_states": ORDER_LIFECYCLE_STATES,
        "idempotency_key": "symbol + strategy_event_id + strategy_state + side",
        "pre_execution_checks": [
            "tradable",
            "trade_window",
            "leverage_ready",
            "quantity_precision",
            "minimum_notional",
            "reduce_only",
            "position_side",
            "current_position_side",
            "account_risk",
            "symbol_cooldown",
        ],
        "log_fields": EXECUTION_LOG_FIELDS,
        "observability_metrics": OBSERVABILITY_METRICS,
        "protection_mode_triggers": PROTECTION_MODE_TRIGGERS,
        "forbidden": EXECUTION_FORBIDDEN_ACTIONS,
        "binance_client_policy": "thin adapter only; do not modify strategy, risk, state, or sizing logic",
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
""",
    "tests/test_live_execution_contract.py": """
from src.execution.live_execution_contract import (
    EXECUTION_FORBIDDEN_ACTIONS,
    EXECUTION_INPUT_FIELDS,
    EXECUTION_LOG_FIELDS,
    EXECUTION_OUTPUT_FIELDS,
    EXECUTION_RESPONSIBILITIES,
    OBSERVABILITY_METRICS,
    ORDER_LIFECYCLE_STATES,
    PROTECTION_MODE_TRIGGERS,
    SUPPORTED_ORDER_TYPES,
    ExecutionInstruction,
    ExecutionResponse,
    ExecutionValidation,
    LifecycleEvent,
    build_execution_log,
    build_idempotency_key,
    build_partial_fill_snapshot,
    lifecycle_transition,
    normalize_reject_reason,
    should_enter_protection_mode,
    validate_execution_instruction,
)


def valid_instruction(**overrides):
    values = {
        "symbol": "BTCUSDT",
        "side": "BUY",
        "order_type": "MARKET",
        "quantity": 0.1,
        "price": None,
        "reduce_only": False,
        "position_side": "LONG",
        "time_in_force": None,
        "stop_price": 95_000,
        "take_profit_price": 110_000,
        "client_order_id": "cli-1",
        "strategy_event_id": "evt-1",
        "strategy_state": "DIRECT_LONG",
        "expected_position_side": "LONG",
        "expected_risk_tag": "entry",
    }
    values.update(overrides)
    return ExecutionInstruction(**values)


def test_live_execution_contract_lists_doc_fields_and_boundaries():
    assert EXECUTION_RESPONSIBILITIES == [
        "create_order",
        "cancel_order",
        "query_order_status",
        "query_position_status",
        "sync_account_info",
        "sync_leverage_and_margin",
        "maintain_order_lifecycle_log",
        "return_raw_exchange_response",
        "standardize_execution_error",
    ]
    assert EXECUTION_INPUT_FIELDS == [
        "symbol",
        "side",
        "order_type",
        "quantity",
        "price",
        "reduce_only",
        "position_side",
        "time_in_force",
        "stop_price",
        "take_profit_price",
        "client_order_id",
        "strategy_event_id",
        "strategy_state",
        "expected_position_side",
        "expected_risk_tag",
    ]
    assert EXECUTION_OUTPUT_FIELDS == [
        "order_id",
        "client_order_id",
        "status",
        "filled_qty",
        "avg_price",
        "commission",
        "executed_notional",
        "reject_reason",
        "raw_response",
        "latency_ms",
        "ts",
    ]
    assert SUPPORTED_ORDER_TYPES == ["MARKET", "LIMIT", "IOC", "STOP_MARKET", "TAKE_PROFIT_MARKET"]
    assert ORDER_LIFECYCLE_STATES == [
        "created",
        "validated",
        "submitted",
        "acknowledged",
        "partially_filled",
        "filled",
        "canceled",
        "rejected",
        "expired",
        "reconciled",
    ]
    assert "execution layer changes order quantity" in EXECUTION_FORBIDDEN_ACTIONS
    assert "order_success_rate" in OBSERVABILITY_METRICS


def test_execution_records_round_trip_to_dict():
    instruction = valid_instruction()
    response = ExecutionResponse(
        order_id="1",
        client_order_id="cli-1",
        status="created",
        filled_qty=0,
        avg_price=0,
        commission=0,
        executed_notional=0,
        reject_reason="",
        raw_response={"ok": True},
        latency_ms=12,
        ts=1_700_000_000,
    )
    event = LifecycleEvent("cli-1", "created", 1_700_000_000, "instruction accepted")
    assert instruction.to_dict()["strategy_event_id"] == "evt-1"
    assert response.to_dict()["status"] == "created"
    assert event.to_dict()["state"] == "created"


def test_validate_execution_instruction_approves_clean_market_order():
    validation = validate_execution_instruction(
        valid_instruction(),
        tradable=True,
        in_trade_window=True,
        leverage_ready=True,
        min_notional=5,
        quantity_step=0.001,
        current_position_side="LONG",
        account_risk_allows=True,
        symbol_cooldown_active=False,
    )
    assert validation == ExecutionValidation(True, "validated")


def test_validate_execution_instruction_rejects_bad_side_type_qty_and_reduce_only():
    assert validate_execution_instruction(valid_instruction(side="HOLD")).passed is False
    assert validate_execution_instruction(valid_instruction(order_type="POST_ONLY")).passed is False
    assert validate_execution_instruction(valid_instruction(quantity=0)).passed is False
    assert validate_execution_instruction(
        valid_instruction(reduce_only=True, expected_risk_tag="entry")
    ).passed is False


def test_validate_execution_instruction_rejects_precision_min_notional_and_context_gates():
    assert validate_execution_instruction(
        valid_instruction(quantity=0.1005), quantity_step=0.001
    ).passed is False
    assert validate_execution_instruction(
        valid_instruction(quantity=0.001, price=100, order_type="LIMIT"), min_notional=5
    ).passed is False
    assert validate_execution_instruction(valid_instruction(), tradable=False).passed is False
    assert validate_execution_instruction(valid_instruction(), in_trade_window=False).passed is False
    assert validate_execution_instruction(valid_instruction(), leverage_ready=False).passed is False
    assert validate_execution_instruction(valid_instruction(), account_risk_allows=False).passed is False
    assert validate_execution_instruction(valid_instruction(), symbol_cooldown_active=True).passed is False


def test_idempotency_key_and_reject_normalization_are_stable():
    instruction = valid_instruction()
    assert build_idempotency_key(instruction) == "BTCUSDT:evt-1:DIRECT_LONG:BUY"
    assert normalize_reject_reason("-2019 margin insufficient") == "INSUFFICIENT_MARGIN"
    assert normalize_reject_reason("precision over maximum") == "PRECISION_ERROR"
    assert normalize_reject_reason("timeout waiting exchange") == "NETWORK_TIMEOUT"
    assert normalize_reject_reason("anything else") == "EXCHANGE_ERROR"


def test_lifecycle_transition_and_execution_log_fields_are_replayable():
    instruction = valid_instruction()
    response = ExecutionResponse(
        order_id="1",
        client_order_id="cli-1",
        status="acknowledged",
        filled_qty=0,
        avg_price=0,
        commission=0,
        executed_notional=0,
        reject_reason="",
        raw_response={"orderId": 1},
        latency_ms=20,
        ts=1_700_000_001,
    )
    event = lifecycle_transition("cli-1", "submitted", "acknowledged", 1_700_000_001, "exchange ack")
    assert event.state == "acknowledged"
    log = build_execution_log(instruction, response, action="create_order", module="execution")
    assert list(log) == EXECUTION_LOG_FIELDS
    assert log["raw_response"] == {"orderId": 1}


def test_lifecycle_transition_rejects_unknown_or_regressive_state():
    assert lifecycle_transition("cli-1", "created", "validated", 1, "ok").state == "validated"
    try:
        lifecycle_transition("cli-1", "submitted", "created", 1, "bad")
    except ValueError as exc:
        assert "regress" in str(exc)
    else:
        raise AssertionError("expected regression rejection")
    try:
        lifecycle_transition("cli-1", "created", "unknown", 1, "bad")
    except ValueError as exc:
        assert "unknown lifecycle state" in str(exc)
    else:
        raise AssertionError("expected unknown state rejection")


def test_partial_fill_snapshot_keeps_remaining_quantity_for_upper_layer():
    snapshot = build_partial_fill_snapshot(
        order_qty=1.0,
        filled_qty=0.4,
        avg_price=100,
        client_order_id="cli-1",
    )
    assert snapshot == {
        "client_order_id": "cli-1",
        "order_qty": 1.0,
        "filled_qty": 0.4,
        "remaining_qty": 0.6,
        "avg_price": 100,
        "status": "partially_filled",
    }


def test_protection_mode_triggers_on_consecutive_failures_and_unknown_state():
    assert PROTECTION_MODE_TRIGGERS == [
        "consecutive_rejects",
        "consecutive_sync_failures",
        "consecutive_protection_order_failures",
        "abnormal_position_state",
        "unknown_order_state",
        "exchange_unavailable",
    ]
    assert should_enter_protection_mode(consecutive_rejects=3).passed is True
    assert should_enter_protection_mode(consecutive_sync_failures=3).passed is True
    assert should_enter_protection_mode(consecutive_protection_order_failures=3).passed is True
    assert should_enter_protection_mode(abnormal_position_state=True).passed is True
    assert should_enter_protection_mode(unknown_order_state=True).passed is True
    assert should_enter_protection_mode(exchange_unavailable=True).passed is True
    assert should_enter_protection_mode().passed is False
""",
    "tests/test_describe_live_execution_contract.py": """
import json
import subprocess
import sys


def test_describe_live_execution_contract_outputs_completed_10_sections():
    completed = subprocess.run(
        [sys.executable, "scripts/describe_live_execution_contract.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["input_fields"][0] == "symbol"
    assert payload["output_fields"][0] == "order_id"
    assert payload["supported_order_types"] == ["MARKET", "LIMIT", "IOC", "STOP_MARKET", "TAKE_PROFIT_MARKET"]
    assert payload["lifecycle_states"][0] == "created"
    assert payload["idempotency_key"] == "symbol + strategy_event_id + strategy_state + side"
    assert payload["protection_mode_triggers"][-1] == "exchange_unavailable"
    assert "execution layer changes order quantity" in payload["forbidden"]
""",
    "tests/test_describe_data_contract.py": """
import json
import subprocess
import sys


def test_describe_data_contract_outputs_policy_json():
    completed = subprocess.run(
        [sys.executable, "scripts/describe_data_contract.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["required_candle_fields"][0] == "open_time"
    assert payload["timeframe_roles"]["15m"] == "execution"
    assert payload["aggregation_rules"]["30m"] == "15m"
    assert payload["cvd_features"] == ["cumulative", "delta", "slope", "divergence"]
    assert payload["indicator_input"] == "candles: list[OHLCV]"


def test_describe_data_contract_outputs_completed_09_sections():
    completed = subprocess.run(
        [sys.executable, "scripts/describe_data_contract.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["data_layers"][0] == "raw_market_data"
    assert payload["full_candle_fields"][0] == "symbol"
    assert payload["indicator_required_outputs"]["ATR"] == ["atr", "atr_pct", "volatility_state"]
    assert "DATA_INVALID" in payload["strategy_event_types"]
    assert payload["storage_contract"]["cold"] == ["historical_backtest_data", "long_term_trade_audit", "historical_performance_report"]
""",
    "src/core/module_spec.py": """
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


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
FORBIDDEN_MODULE_PATTERNS = ["cross_layer_overreach", "circular_dependency", "god_utility_class"]
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
DEPENDENCY_ALIASES = {
    "observability": "monitoring",
    "portfolio": "position_sizing",
}

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

RECOMMENDED_FILES = {
    "signals": ["macd_signal.py", "cci_signal.py", "entry_signal.py"],
    "risk": ["position_sizer.py", "stop_engine.py", "tp_engine.py", "cooldown_guard.py"],
    "execution": ["order_manager.py", "position_manager.py", "exchange_adapter.py"],
    "backtest": ["runner.py", "broker.py", "analyzer.py"],
    "reporting": ["html_report.py", "csv_exporter.py", "excel_exporter.py"],
}
TEST_DIRECTORIES = ["tests/unit", "tests/integration", "tests/backtest"]
FINAL_PRINCIPLE = "strategy judges, risk constrains, execution executes"


@dataclass(frozen=True)
class ModuleSpecCheck:
    passed: bool
    reason: str


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


def validate_dependency(source_layer: str, target_layer: str) -> ModuleSpecCheck:
    source = _normalize_dependency_layer(source_layer)
    target = _normalize_dependency_layer(target_layer)
    if source == "execution" and target in {"signals", "signal"}:
        return ModuleSpecCheck(False, "execution must not call signal layer")
    if source == "risk" and target == "backtest":
        return ModuleSpecCheck(False, "risk must not call backtest")
    if source in ALLOWED_DEPENDENCY_CHAIN and target in ALLOWED_DEPENDENCY_CHAIN:
        if ALLOWED_DEPENDENCY_CHAIN.index(source) <= ALLOWED_DEPENDENCY_CHAIN.index(target):
            return ModuleSpecCheck(True, "dependency approved")
        return ModuleSpecCheck(False, "reverse dependency is forbidden")
    return ModuleSpecCheck(True, "dependency outside strict chain")


def _normalize_dependency_layer(layer: str) -> str:
    return DEPENDENCY_ALIASES.get(layer, layer)


def validate_module_structure(src_root: str | Path) -> ModuleSpecCheck:
    root = Path(src_root)
    missing = [name for name in FINAL_MODULE_STRUCTURE if not (root / name).exists()]
    if missing:
        return ModuleSpecCheck(False, f"missing module directories: {missing}")
    return ModuleSpecCheck(True, "module structure approved")
""",
    "src/portfolio/__init__.py": '"""Portfolio account, exposure, and position synchronization boundary."""',
    "scripts/describe_python_module_spec.py": """
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
""",
    "tests/test_python_module_spec.py": """
from src.core.module_spec import (
    ALLOWED_DEPENDENCY_CHAIN,
    BASE_INTERFACE_METHODS,
    CONCEPTUAL_LAYER_IMPLEMENTATIONS,
    CONTEXT_STATES,
    ENGINE_NAMES,
    EVENT_TYPES,
    FINAL_MODULE_STRUCTURE,
    FORBIDDEN_MODULE_PATTERNS,
    LAYER_RESPONSIBILITIES,
    RECOMMENDED_FILES,
    SIGNAL_OUTPUTS,
    STATE_MACHINE_STATES,
    TEST_DIRECTORIES,
    BaseExecution,
    BaseIndicator,
    BaseRiskModel,
    BaseSignal,
    DTO,
    ModuleSpecCheck,
    StrategyContext,
    validate_dependency,
    validate_module_structure,
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
        "observability",
        "deployment",
        "utils",
    ]
    assert LAYER_RESPONSIBILITIES["config"] == ["load_config", "validate_config", "freeze_config"]
    assert LAYER_RESPONSIBILITIES["data"] == ["fetch_data", "cache_data", "normalize_data"]
    assert LAYER_RESPONSIBILITIES["indicators"] == ["calculate_indicators", "output_results"]
    assert LAYER_RESPONSIBILITIES["context"] == ["multi_timeframe_market_state"]
    assert LAYER_RESPONSIBILITIES["execution"] == ["execute_approved_intent", "order_lifecycle", "position_sync"]
    assert LAYER_RESPONSIBILITIES["portfolio"] == ["account_management", "portfolio_risk", "position_sync"]
    assert LAYER_RESPONSIBILITIES["observability"] == ["logging", "metrics", "monitoring"]
    assert LAYER_RESPONSIBILITIES["deployment"] == ["startup", "shutdown", "recovery", "release_gates"]
    assert FORBIDDEN_MODULE_PATTERNS == ["cross_layer_overreach", "circular_dependency", "god_utility_class"]


def test_dependency_chain_allows_forward_flow_and_rejects_reverse_flow():
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
    assert validate_dependency("data", "indicators") == ModuleSpecCheck(True, "dependency approved")
    assert validate_dependency("signals", "risk") == ModuleSpecCheck(True, "dependency approved")
    assert validate_dependency("risk", "position_sizing") == ModuleSpecCheck(True, "dependency approved")
    assert validate_dependency("position_sizing", "execution") == ModuleSpecCheck(True, "dependency approved")
    assert validate_dependency("execution", "signals").passed is False
    assert validate_dependency("risk", "backtest").passed is False
    assert validate_dependency("monitoring", "execution").passed is False


def test_validate_module_structure_accepts_current_src_directories():
    assert validate_module_structure("src").passed is True


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


def test_recommended_files_and_test_directories_match_doc():
    assert RECOMMENDED_FILES["signals"] == ["macd_signal.py", "cci_signal.py", "entry_signal.py"]
    assert RECOMMENDED_FILES["risk"] == ["position_sizer.py", "stop_engine.py", "tp_engine.py", "cooldown_guard.py"]
    assert RECOMMENDED_FILES["execution"] == ["order_manager.py", "position_manager.py", "exchange_adapter.py"]
    assert RECOMMENDED_FILES["backtest"] == ["runner.py", "broker.py", "analyzer.py"]
    assert RECOMMENDED_FILES["reporting"] == ["html_report.py", "csv_exporter.py", "excel_exporter.py"]
    assert TEST_DIRECTORIES == ["tests/unit", "tests/integration", "tests/backtest"]


def test_conceptual_layer_implementations_bridge_current_file_layout():
    assert CONCEPTUAL_LAYER_IMPLEMENTATIONS == {
        "position_sizing": "src/risk/position_sizer.py",
        "monitoring": "src/observability/logging_metrics.py",
        "deployment": "src/deployment/deployment_architecture.py",
    }
""",
    "tests/test_describe_python_module_spec.py": """
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
""",
    "scripts/describe_event_bus_spec.py": """
from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.events import (
    EVENT_CATEGORIES,
    EVENT_DEDUPE_KEY_FIELDS,
    EVENT_ERROR_TYPES,
    EVENT_LIFECYCLE_STATES,
    EVENT_REQUIRED_FIELDS,
    KEY_EVENT_TYPES,
    EventPriority,
    HandlerResult,
)


def main() -> None:
    payload = {
        "event_model_fields": EVENT_REQUIRED_FIELDS,
        "key_event_types": KEY_EVENT_TYPES,
        "categories": EVENT_CATEGORIES,
        "priorities": [item.value for item in EventPriority],
        "lifecycle_states": EVENT_LIFECYCLE_STATES,
        "dedupe_key": EVENT_DEDUPE_KEY_FIELDS,
        "handler_result_fields": list(HandlerResult.__dataclass_fields__),
        "error_types": EVENT_ERROR_TYPES,
        "modes": ["sync", "async_contract_only"],
        "replay_filters": ["start_ts", "end_ts", "symbol", "event_type", "ignore_low_priority"],
        "bus_boundary": "message transport only; no strategy, risk, sizing, or execution decisions",
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
""",
    "tests/test_event_bus_spec.py": """
from src.core.events import (
    DeadLetterRecord,
    EVENT_CATEGORIES,
    EVENT_DEDUPE_KEY_FIELDS,
    EVENT_ERROR_TYPES,
    EVENT_LIFECYCLE_STATES,
    EVENT_REQUIRED_FIELDS,
    KEY_EVENT_TYPES,
    Event,
    EventBus,
    EventPriority,
    EventStatus,
    EventType,
    HandlerResult,
)


def test_event_contract_constants_match_doc():
    assert KEY_EVENT_TYPES == [
        "MARKET_DATA_UPDATED",
        "INDICATOR_UPDATED",
        "MULTI_TF_CONTEXT_READY",
        "SIGNAL_CREATED",
        "WATCH_ENTERED",
        "PROBE_ENTERED",
        "DIRECT_ENTERED",
        "ORDER_SUBMITTED",
        "ORDER_FILLED",
        "ORDER_REJECTED",
        "POSITION_OPENED",
        "POSITION_REDUCED",
        "POSITION_CLOSED",
        "STOP_HIT",
        "TP_HIT",
        "RISK_BLOCKED",
        "COOLDOWN_STARTED",
        "COOLDOWN_ENDED",
        "BACKTEST_STEP_COMPLETED",
        "REPORT_GENERATED",
    ]
    assert EVENT_LIFECYCLE_STATES == [
        "created",
        "published",
        "dispatched",
        "handled",
        "persisted",
        "archived",
        "failed",
        "retried",
        "dead_lettered",
    ]
    assert EVENT_REQUIRED_FIELDS == [
        "event_id",
        "event_type",
        "ts",
        "source",
        "symbol",
        "timeframe",
        "version",
        "payload",
        "priority",
        "correlation_id",
        "parent_event_id",
        "trace_id",
        "status",
    ]
    assert EVENT_DEDUPE_KEY_FIELDS == ["symbol", "event_type", "strategy_event_id", "timeframe"]
    assert EVENT_ERROR_TYPES == [
        "INVALID_PAYLOAD",
        "UNKNOWN_EVENT_TYPE",
        "HANDLER_ERROR",
        "TIMEOUT",
        "DUPLICATE_EVENT",
        "STATE_CONFLICT",
        "DEPENDENCY_UNAVAILABLE",
    ]
    assert EVENT_CATEGORIES["Market Events"] == ["MARKET_DATA_UPDATED"]
    assert EVENT_CATEGORIES["Execution Events"] == ["ORDER_SUBMITTED", "ORDER_FILLED", "ORDER_REJECTED"]


def test_event_serializes_with_standard_fields_and_dedupe_key():
    event = Event(
        event_type=EventType.SIGNAL_CREATED,
        ts=1_700_000_000,
        source="signal_engine",
        symbol="BTCUSDT",
        timeframe="15m",
        payload={"strategy_event_id": "sig-1", "signal": "DIRECT_LONG"},
        priority=EventPriority.HIGH,
        correlation_id="corr-1",
        parent_event_id="evt-parent",
        trace_id="trace-1",
    )
    payload = event.to_dict()
    assert list(payload) == EVENT_REQUIRED_FIELDS
    assert payload["event_type"] == "SIGNAL_CREATED"
    assert payload["priority"] == "HIGH"
    assert payload["status"] == "created"
    assert event.dedupe_key() == "BTCUSDT:SIGNAL_CREATED:sig-1:15m"
    assert event.with_status(EventStatus.PUBLISHED).status == EventStatus.PUBLISHED


def test_event_bus_publish_subscribe_logs_and_idempotency():
    bus = EventBus()
    handled = []

    def handler(event):
        handled.append(event.event_id)
        return HandlerResult(success=True, logs=["handled"])

    bus.subscribe(EventType.SIGNAL_CREATED, handler)
    event = Event(
        EventType.SIGNAL_CREATED,
        1,
        "signal_engine",
        {"strategy_event_id": "sig-1"},
        symbol="BTCUSDT",
        timeframe="15m",
    )
    first = bus.publish(event)
    duplicate = bus.publish(event)
    assert first.success is True
    assert duplicate.success is True
    assert duplicate.metadata["duplicate"] is True
    assert handled == [event.event_id]
    assert [stored.status for stored in bus.event_log] == [EventStatus.HANDLED, EventStatus.DUPLICATE]


def test_event_bus_dispatches_next_events_and_priority_order():
    bus = EventBus()
    seen = []

    def signal_handler(event):
        seen.append(event.event_type.value)
        return HandlerResult(
            success=True,
            next_events=[
                Event(EventType.REPORT_GENERATED, 3, "report_engine", priority=EventPriority.LOW),
                Event(EventType.RISK_BLOCKED, 2, "risk_engine", priority=EventPriority.CRITICAL),
            ],
        )

    def record(event):
        seen.append(event.event_type.value)
        return HandlerResult(success=True)

    bus.subscribe(EventType.SIGNAL_CREATED, signal_handler)
    bus.subscribe(EventType.RISK_BLOCKED, record)
    bus.subscribe(EventType.REPORT_GENERATED, record)
    bus.publish(Event(EventType.SIGNAL_CREATED, 1, "signal_engine", {"strategy_event_id": "sig-2"}))
    assert seen == ["SIGNAL_CREATED", "RISK_BLOCKED", "REPORT_GENERATED"]


def test_event_bus_dead_letters_handler_failures():
    bus = EventBus(max_retries=1)

    def failing_handler(event):
        raise RuntimeError("boom")

    event = Event(EventType.ORDER_FILLED, 1, "execution_engine", {"strategy_event_id": "ord-1"})
    bus.subscribe(EventType.ORDER_FILLED, failing_handler)
    result = bus.publish(event)
    assert result.success is False
    assert len(bus.dead_letters) == 1
    assert isinstance(bus.dead_letters[0], DeadLetterRecord)
    assert bus.dead_letters[0].reason == "HANDLER_ERROR"
    assert bus.dead_letters[0].retry_count == 1


def test_event_bus_replay_filters_by_time_symbol_type_and_priority():
    bus = EventBus()
    seen = []

    def record(event):
        seen.append((event.event_type.value, event.symbol))
        return HandlerResult(success=True)

    bus.subscribe(EventType.MARKET_DATA_UPDATED, record)
    bus.subscribe(EventType.REPORT_GENERATED, record)
    events = [
        Event(EventType.MARKET_DATA_UPDATED, 1, "data_loader", symbol="BTCUSDT", priority=EventPriority.NORMAL),
        Event(EventType.MARKET_DATA_UPDATED, 2, "data_loader", symbol="ETHUSDT", priority=EventPriority.NORMAL),
        Event(EventType.REPORT_GENERATED, 3, "report_engine", symbol="BTCUSDT", priority=EventPriority.LOW),
    ]
    bus.replay(
        events,
        start_ts=1,
        end_ts=3,
        symbol="BTCUSDT",
        event_type=EventType.MARKET_DATA_UPDATED,
        ignore_low_priority=True,
    )
    assert seen == [("MARKET_DATA_UPDATED", "BTCUSDT")]
""",
    "tests/test_describe_event_bus_spec.py": """
import json
import subprocess
import sys


def test_describe_event_bus_spec_outputs_completed_14_sections():
    completed = subprocess.run(
        [sys.executable, "scripts/describe_event_bus_spec.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["event_model_fields"][0] == "event_id"
    assert payload["key_event_types"][0] == "MARKET_DATA_UPDATED"
    assert payload["priorities"] == ["CRITICAL", "HIGH", "NORMAL", "LOW"]
    assert payload["lifecycle_states"][-1] == "dead_lettered"
    assert payload["dedupe_key"] == ["symbol", "event_type", "strategy_event_id", "timeframe"]
    assert payload["handler_result_fields"] == ["success", "next_events", "logs", "errors", "metadata"]
    assert "HANDLER_ERROR" in payload["error_types"]
""",
    'src/data/database_schema.py': 'from __future__ import annotations\n\nfrom dataclasses import dataclass\n\n\nDATABASE_ENGINE = "PostgreSQL"\nDATA_LAYERS = ["hot", "warm", "cold", "archive"]\nCOMMON_CORE_FIELDS = ["id", "symbol", "timeframe", "ts", "version", "source", "created_at", "updated_at"]\nCORE_TABLES = [\n    "symbols",\n    "market_candles",\n    "indicator_results",\n    "multi_tf_contexts",\n    "strategy_events",\n    "signals",\n    "orders",\n    "order_fills",\n    "positions",\n    "risk_snapshots",\n    "account_snapshots",\n    "cooldowns",\n    "backtest_runs",\n    "backtest_steps",\n    "backtest_trades",\n    "performance_metrics",\n    "audit_logs",\n    "reports",\n    "config_versions",\n    "event_bus_messages",\n    "system_health",\n]\n\n\n@dataclass(frozen=True)\nclass Column:\n    name: str\n    data_type: str\n    nullable: bool = True\n    default: str | None = None\n\n    def ddl(self) -> str:\n        parts = [self.name, self.data_type]\n        if not self.nullable:\n            parts.append("NOT NULL")\n        if self.default is not None:\n            parts.extend(["DEFAULT", self.default])\n        return " ".join(parts)\n\n\n@dataclass(frozen=True)\nclass IndexSpec:\n    name: str\n    columns: list[str]\n\n\n@dataclass(frozen=True)\nclass TableSchema:\n    name: str\n    columns: list[Column]\n    primary_key: str\n    unique_keys: list[list[str]]\n    indexes: list[IndexSpec]\n    partition_hint: str | None = None\n\n    def column_names(self) -> list[str]:\n        return [column.name for column in self.columns]\n\n\n@dataclass(frozen=True)\nclass SchemaValidationResult:\n    passed: bool\n    errors: list[str]\n\n\ndef c(name: str, data_type: str, nullable: bool = True, default: str | None = None) -> Column:\n    return Column(name, data_type, nullable, default)\n\n\ndef idx(table: str, *columns: str) -> IndexSpec:\n    return IndexSpec(f"idx_{table}_{\'_\'.join(columns)}", list(columns))\n\n\ndef base_columns(include_symbol: bool = True, include_timeframe: bool = True, include_ts: bool = True) -> list[Column]:\n    columns = [c("id", "BIGSERIAL", False)]\n    if include_symbol:\n        columns.append(c("symbol", "VARCHAR(32)"))\n    if include_timeframe:\n        columns.append(c("timeframe", "VARCHAR(8)"))\n    if include_ts:\n        columns.append(c("ts", "TIMESTAMP WITH TIME ZONE"))\n    columns.extend(\n        [\n            c("version", "VARCHAR(32)"),\n            c("source", "VARCHAR(64)"),\n            c("created_at", "TIMESTAMP WITH TIME ZONE", False, "NOW()"),\n            c("updated_at", "TIMESTAMP WITH TIME ZONE"),\n        ]\n    )\n    return columns\n\n\nTABLE_SCHEMAS = {\n    "symbols": TableSchema(\n        "symbols",\n        [\n            c("id", "BIGSERIAL", False),\n            c("symbol", "VARCHAR(32)", False),\n            c("base_asset", "VARCHAR(16)", False),\n            c("quote_asset", "VARCHAR(16)", False),\n            c("market_cap_rank", "INT"),\n            c("volume_rank", "INT"),\n            c("tier", "VARCHAR(8)", False),\n            c("tradable", "BOOLEAN", False, "TRUE"),\n            c("listed_time", "TIMESTAMP WITH TIME ZONE"),\n            c("delisting_flag", "BOOLEAN", False, "FALSE"),\n            c("correlation_group", "VARCHAR(32)"),\n            c("source", "VARCHAR(64)"),\n            c("version", "VARCHAR(32)"),\n            c("created_at", "TIMESTAMP WITH TIME ZONE", False, "NOW()"),\n            c("updated_at", "TIMESTAMP WITH TIME ZONE", False, "NOW()"),\n        ],\n        "id",\n        [["symbol"]],\n        [idx("symbols", "symbol"), idx("symbols", "tradable"), idx("symbols", "tier"), idx("symbols", "correlation_group")],\n    ),\n    "market_candles": TableSchema(\n        "market_candles",\n        [\n            c("id", "BIGSERIAL", False),\n            c("symbol", "VARCHAR(32)", False),\n            c("timeframe", "VARCHAR(8)", False),\n            c("open_time", "TIMESTAMP WITH TIME ZONE", False),\n            c("close_time", "TIMESTAMP WITH TIME ZONE", False),\n            c("open", "NUMERIC(24, 12)", False),\n            c("high", "NUMERIC(24, 12)", False),\n            c("low", "NUMERIC(24, 12)", False),\n            c("close", "NUMERIC(24, 12)", False),\n            c("volume", "NUMERIC(30, 12)", False),\n            c("quote_volume", "NUMERIC(30, 12)"),\n            c("trade_count", "BIGINT"),\n            c("taker_buy_base_volume", "NUMERIC(30, 12)"),\n            c("taker_buy_quote_volume", "NUMERIC(30, 12)"),\n            c("is_closed", "BOOLEAN", False, "TRUE"),\n            c("quality_flag", "VARCHAR(16)", False, "\'true\'"),\n            c("source", "VARCHAR(64)", False),\n            c("version", "VARCHAR(32)"),\n            c("created_at", "TIMESTAMP WITH TIME ZONE", False, "NOW()"),\n            c("updated_at", "TIMESTAMP WITH TIME ZONE", False, "NOW()"),\n        ],\n        "id",\n        [["symbol", "timeframe", "open_time"]],\n        [idx("market_candles", "symbol", "timeframe", "open_time"), idx("market_candles", "timeframe", "open_time"), idx("market_candles", "symbol", "open_time")],\n        "partition by timeframe, then month or day",\n    ),\n    "indicator_results": TableSchema(\n        "indicator_results",\n        base_columns() + [c("indicator_name", "VARCHAR(32)", False), c("value_json", "JSONB", False), c("signal", "VARCHAR(32)"), c("trend", "VARCHAR(16)"), c("strength", "NUMERIC(18, 8)"), c("quality_flag", "VARCHAR(16)", False, "\'true\'")],\n        "id",\n        [["symbol", "timeframe", "ts", "indicator_name", "version"]],\n        [idx("indicator_results", "symbol", "timeframe", "ts"), idx("indicator_results", "indicator_name", "ts"), idx("indicator_results", "quality_flag")],\n    ),\n    "multi_tf_contexts": TableSchema(\n        "multi_tf_contexts",\n        base_columns(include_timeframe=False) + [c("market_state_4h", "VARCHAR(16)"), c("trend_state_1h", "VARCHAR(32)"), c("confirm_state_30m", "VARCHAR(32)"), c("trigger_state_15m", "VARCHAR(32)"), c("direction_bias", "VARCHAR(16)"), c("entry_mode", "VARCHAR(16)"), c("confidence_score", "NUMERIC(18, 8)"), c("quality_flag", "VARCHAR(16)", False, "\'true\'"), c("context_json", "JSONB", False)],\n        "id",\n        [["symbol", "ts", "version"]],\n        [idx("multi_tf_contexts", "symbol", "ts"), idx("multi_tf_contexts", "trend_state_1h", "ts"), idx("multi_tf_contexts", "direction_bias", "ts")],\n    ),\n    "strategy_events": TableSchema(\n        "strategy_events",\n        [c("id", "BIGSERIAL", False), c("event_id", "VARCHAR(64)", False), c("correlation_id", "VARCHAR(64)"), c("parent_event_id", "VARCHAR(64)"), c("trace_id", "VARCHAR(64)"), c("symbol", "VARCHAR(32)"), c("timeframe", "VARCHAR(8)"), c("event_type", "VARCHAR(64)", False), c("state_before", "VARCHAR(32)"), c("state_after", "VARCHAR(32)"), c("reason", "VARCHAR(256)"), c("priority", "VARCHAR(16)", False, "\'NORMAL\'"), c("payload", "JSONB", False), c("status", "VARCHAR(32)", False, "\'created\'"), c("source", "VARCHAR(64)", False), c("version", "VARCHAR(32)"), c("ts", "TIMESTAMP WITH TIME ZONE", False), c("created_at", "TIMESTAMP WITH TIME ZONE", False, "NOW()"), c("updated_at", "TIMESTAMP WITH TIME ZONE", False, "NOW()")],\n        "id",\n        [["event_id"]],\n        [idx("strategy_events", "symbol", "ts"), idx("strategy_events", "event_type", "ts"), idx("strategy_events", "trace_id"), idx("strategy_events", "correlation_id"), idx("strategy_events", "status", "ts")],\n        "partition by month",\n    ),\n    "signals": TableSchema("signals", [c("id", "BIGSERIAL", False), c("signal_id", "VARCHAR(64)", False), c("event_id", "VARCHAR(64)"), c("symbol", "VARCHAR(32)", False), c("ts", "TIMESTAMP WITH TIME ZONE", False), c("signal_side", "VARCHAR(16)", False), c("signal_type", "VARCHAR(32)", False), c("entry_mode", "VARCHAR(16)", False), c("score", "NUMERIC(18, 8)"), c("confidence_score", "NUMERIC(18, 8)"), c("reason", "VARCHAR(256)"), c("quality_flag", "VARCHAR(16)", False, "\'true\'"), c("signal_json", "JSONB", False), c("source", "VARCHAR(64)"), c("version", "VARCHAR(32)"), c("created_at", "TIMESTAMP WITH TIME ZONE", False, "NOW()"), c("updated_at", "TIMESTAMP WITH TIME ZONE", False, "NOW()")], "id", [["signal_id"]], [idx("signals", "symbol", "ts"), idx("signals", "signal_side", "ts"), idx("signals", "signal_type", "ts")]),\n    "orders": TableSchema("orders", [c("id", "BIGSERIAL", False), c("order_id", "VARCHAR(64)"), c("client_order_id", "VARCHAR(64)"), c("event_id", "VARCHAR(64)"), c("symbol", "VARCHAR(32)", False), c("side", "VARCHAR(16)", False), c("order_type", "VARCHAR(32)", False), c("position_side", "VARCHAR(16)"), c("reduce_only", "BOOLEAN", False, "FALSE"), c("time_in_force", "VARCHAR(16)"), c("quantity", "NUMERIC(30, 12)", False), c("price", "NUMERIC(24, 12)"), c("stop_price", "NUMERIC(24, 12)"), c("take_profit_price", "NUMERIC(24, 12)"), c("status", "VARCHAR(32)", False), c("requested_notional", "NUMERIC(30, 12)"), c("executed_notional", "NUMERIC(30, 12)"), c("strategy_state", "VARCHAR(32)"), c("strategy_version", "VARCHAR(32)"), c("risk_tag", "VARCHAR(32)"), c("exchange_payload", "JSONB"), c("exchange_response", "JSONB"), c("source", "VARCHAR(64)", False), c("version", "VARCHAR(32)"), c("ts", "TIMESTAMP WITH TIME ZONE", False), c("created_at", "TIMESTAMP WITH TIME ZONE", False, "NOW()"), c("updated_at", "TIMESTAMP WITH TIME ZONE", False, "NOW()")], "id", [["order_id"], ["client_order_id"]], [idx("orders", "symbol", "ts"), idx("orders", "status", "ts"), idx("orders", "client_order_id"), idx("orders", "event_id")], "partition by month"),\n    "order_fills": TableSchema("order_fills", [c("id", "BIGSERIAL", False), c("order_id", "VARCHAR(64)", False), c("client_order_id", "VARCHAR(64)"), c("symbol", "VARCHAR(32)", False), c("fill_id", "VARCHAR(64)"), c("side", "VARCHAR(16)", False), c("price", "NUMERIC(24, 12)", False), c("qty", "NUMERIC(30, 12)", False), c("quote_qty", "NUMERIC(30, 12)"), c("commission", "NUMERIC(30, 12)"), c("commission_asset", "VARCHAR(16)"), c("trade_time", "TIMESTAMP WITH TIME ZONE", False), c("is_maker", "BOOLEAN"), c("source", "VARCHAR(64)"), c("version", "VARCHAR(32)"), c("created_at", "TIMESTAMP WITH TIME ZONE", False, "NOW()")], "id", [["order_id", "fill_id"]], [idx("order_fills", "order_id"), idx("order_fills", "symbol", "trade_time"), idx("order_fills", "client_order_id")], "partition by month"),\n    "positions": TableSchema("positions", [c("id", "BIGSERIAL", False), c("position_id", "VARCHAR(64)"), c("symbol", "VARCHAR(32)", False), c("side", "VARCHAR(16)", False), c("qty", "NUMERIC(30, 12)", False), c("entry_price", "NUMERIC(24, 12)", False), c("mark_price", "NUMERIC(24, 12)"), c("leverage", "NUMERIC(18, 8)"), c("unrealized_pnl", "NUMERIC(30, 12)"), c("realized_pnl", "NUMERIC(30, 12)"), c("stop_price", "NUMERIC(24, 12)"), c("take_profit_price", "NUMERIC(24, 12)"), c("position_age_bars", "INT"), c("state", "VARCHAR(32)", False, "\'OPEN\'"), c("strategy_state", "VARCHAR(32)"), c("entry_event_id", "VARCHAR(64)"), c("exit_event_id", "VARCHAR(64)"), c("source", "VARCHAR(64)"), c("version", "VARCHAR(32)"), c("open_ts", "TIMESTAMP WITH TIME ZONE"), c("close_ts", "TIMESTAMP WITH TIME ZONE"), c("created_at", "TIMESTAMP WITH TIME ZONE", False, "NOW()"), c("updated_at", "TIMESTAMP WITH TIME ZONE", False, "NOW()")], "id", [["position_id"]], [idx("positions", "symbol", "state"), idx("positions", "symbol", "open_ts"), idx("positions", "entry_event_id"), idx("positions", "exit_event_id")]),\n    "risk_snapshots": TableSchema("risk_snapshots", base_columns(include_timeframe=False) + [c("snapshot_id", "VARCHAR(64)"), c("account_equity", "NUMERIC(30, 12)"), c("available_margin", "NUMERIC(30, 12)"), c("used_margin", "NUMERIC(30, 12)"), c("daily_pnl", "NUMERIC(30, 12)"), c("weekly_pnl", "NUMERIC(30, 12)"), c("max_drawdown", "NUMERIC(18, 8)"), c("exposure_pct", "NUMERIC(18, 8)"), c("portfolio_exposure_pct", "NUMERIC(18, 8)"), c("risk_state", "VARCHAR(32)"), c("cooldown_state", "VARCHAR(32)"), c("risk_json", "JSONB", False)], "id", [["snapshot_id"]], [idx("risk_snapshots", "symbol", "ts"), idx("risk_snapshots", "risk_state", "ts"), idx("risk_snapshots", "cooldown_state", "ts")]),\n    "account_snapshots": TableSchema("account_snapshots", [c("id", "BIGSERIAL", False), c("snapshot_id", "VARCHAR(64)"), c("ts", "TIMESTAMP WITH TIME ZONE", False), c("account_equity", "NUMERIC(30, 12)", False), c("available_margin", "NUMERIC(30, 12)"), c("used_margin", "NUMERIC(30, 12)"), c("unrealized_pnl", "NUMERIC(30, 12)"), c("realized_pnl", "NUMERIC(30, 12)"), c("daily_pnl", "NUMERIC(30, 12)"), c("weekly_pnl", "NUMERIC(30, 12)"), c("total_exposure_pct", "NUMERIC(18, 8)"), c("max_drawdown_pct", "NUMERIC(18, 8)"), c("account_state", "VARCHAR(32)"), c("account_json", "JSONB", False), c("source", "VARCHAR(64)"), c("version", "VARCHAR(32)"), c("created_at", "TIMESTAMP WITH TIME ZONE", False, "NOW()")], "id", [["snapshot_id"]], [idx("account_snapshots", "ts"), idx("account_snapshots", "account_state", "ts")]),\n    "cooldowns": TableSchema("cooldowns", [c("id", "BIGSERIAL", False), c("cooldown_id", "VARCHAR(64)"), c("symbol", "VARCHAR(32)", False), c("side", "VARCHAR(16)"), c("started_at", "TIMESTAMP WITH TIME ZONE", False), c("ended_at", "TIMESTAMP WITH TIME ZONE"), c("duration_bars", "INT"), c("reason", "VARCHAR(256)"), c("status", "VARCHAR(32)", False, "\'ACTIVE\'"), c("source", "VARCHAR(64)"), c("version", "VARCHAR(32)"), c("created_at", "TIMESTAMP WITH TIME ZONE", False, "NOW()"), c("updated_at", "TIMESTAMP WITH TIME ZONE", False, "NOW()")], "id", [["cooldown_id"]], [idx("cooldowns", "symbol", "status"), idx("cooldowns", "started_at"), idx("cooldowns", "ended_at")]),\n}\n\nTABLE_SCHEMAS.update(\n    {\n        "backtest_runs": TableSchema("backtest_runs", [c("id", "BIGSERIAL", False), c("run_id", "VARCHAR(64)", False), c("strategy_name", "VARCHAR(64)", False), c("strategy_version", "VARCHAR(32)", False), c("config_version", "VARCHAR(32)"), c("data_version", "VARCHAR(32)"), c("start_time", "TIMESTAMP WITH TIME ZONE", False), c("end_time", "TIMESTAMP WITH TIME ZONE", False), c("symbols_json", "JSONB", False), c("timeframe_json", "JSONB", False), c("initial_capital", "NUMERIC(30, 12)", False), c("status", "VARCHAR(32)", False), c("summary_json", "JSONB"), c("created_at", "TIMESTAMP WITH TIME ZONE", False, "NOW()"), c("updated_at", "TIMESTAMP WITH TIME ZONE", False, "NOW()")], "id", [["run_id"]], [idx("backtest_runs", "strategy_name", "strategy_version"), idx("backtest_runs", "status", "created_at"), idx("backtest_runs", "start_time", "end_time")]),\n        "backtest_steps": TableSchema("backtest_steps", [c("id", "BIGSERIAL", False), c("run_id", "VARCHAR(64)", False), c("step_index", "BIGINT", False), c("symbol", "VARCHAR(32)", False), c("timeframe", "VARCHAR(8)", False), c("ts", "TIMESTAMP WITH TIME ZONE", False), c("state_before", "VARCHAR(32)"), c("state_after", "VARCHAR(32)"), c("event_type", "VARCHAR(64)"), c("payload", "JSONB"), c("created_at", "TIMESTAMP WITH TIME ZONE", False, "NOW()")], "id", [["run_id", "step_index"]], [idx("backtest_steps", "run_id", "step_index"), idx("backtest_steps", "run_id", "symbol", "ts")]),\n        "backtest_trades": TableSchema("backtest_trades", [c("id", "BIGSERIAL", False), c("run_id", "VARCHAR(64)", False), c("trade_id", "VARCHAR(64)"), c("symbol", "VARCHAR(32)", False), c("side", "VARCHAR(16)", False), c("entry_time", "TIMESTAMP WITH TIME ZONE", False), c("entry_price", "NUMERIC(24, 12)", False), c("exit_time", "TIMESTAMP WITH TIME ZONE"), c("exit_price", "NUMERIC(24, 12)"), c("qty", "NUMERIC(30, 12)", False), c("leverage", "NUMERIC(18, 8)"), c("pnl", "NUMERIC(30, 12)"), c("pnl_pct", "NUMERIC(18, 8)"), c("fees", "NUMERIC(30, 12)"), c("slippage", "NUMERIC(30, 12)"), c("reason_enter", "VARCHAR(256)"), c("reason_exit", "VARCHAR(256)"), c("entry_mode", "VARCHAR(16)"), c("exit_mode", "VARCHAR(16)"), c("state_before", "VARCHAR(32)"), c("state_after", "VARCHAR(32)"), c("trade_json", "JSONB"), c("created_at", "TIMESTAMP WITH TIME ZONE", False, "NOW()")], "id", [["trade_id"]], [idx("backtest_trades", "run_id", "symbol"), idx("backtest_trades", "entry_time"), idx("backtest_trades", "exit_time")]),\n        "performance_metrics": TableSchema("performance_metrics", [c("id", "BIGSERIAL", False), c("run_id", "VARCHAR(64)"), c("metric_scope", "VARCHAR(32)", False), c("metric_name", "VARCHAR(64)", False), c("metric_value", "NUMERIC(30, 12)"), c("metric_json", "JSONB"), c("ts", "TIMESTAMP WITH TIME ZONE", False), c("source", "VARCHAR(64)"), c("version", "VARCHAR(32)"), c("created_at", "TIMESTAMP WITH TIME ZONE", False, "NOW()")], "id", [["run_id", "metric_scope", "metric_name"]], [idx("performance_metrics", "run_id"), idx("performance_metrics", "metric_scope", "metric_name")]),\n        "audit_logs": TableSchema("audit_logs", [c("id", "BIGSERIAL", False), c("audit_id", "VARCHAR(64)"), c("ts", "TIMESTAMP WITH TIME ZONE", False), c("module", "VARCHAR(64)", False), c("action", "VARCHAR(64)", False), c("symbol", "VARCHAR(32)"), c("event_id", "VARCHAR(64)"), c("trace_id", "VARCHAR(64)"), c("severity", "VARCHAR(16)", False), c("message", "TEXT", False), c("payload", "JSONB"), c("source", "VARCHAR(64)"), c("version", "VARCHAR(32)"), c("created_at", "TIMESTAMP WITH TIME ZONE", False, "NOW()")], "id", [["audit_id"]], [idx("audit_logs", "ts"), idx("audit_logs", "module", "ts"), idx("audit_logs", "severity", "ts"), idx("audit_logs", "trace_id")], "partition by month"),\n        "reports": TableSchema("reports", [c("id", "BIGSERIAL", False), c("report_id", "VARCHAR(64)"), c("report_type", "VARCHAR(32)", False), c("run_id", "VARCHAR(64)"), c("title", "VARCHAR(256)"), c("file_path", "TEXT", False), c("file_format", "VARCHAR(16)", False), c("summary_json", "JSONB"), c("ts", "TIMESTAMP WITH TIME ZONE", False), c("created_at", "TIMESTAMP WITH TIME ZONE", False, "NOW()")], "id", [["report_id"]], [idx("reports", "report_type", "ts"), idx("reports", "run_id")]),\n        "config_versions": TableSchema("config_versions", [c("id", "BIGSERIAL", False), c("config_version", "VARCHAR(32)", False), c("config_name", "VARCHAR(64)", False), c("config_json", "JSONB", False), c("checksum", "VARCHAR(128)"), c("source", "VARCHAR(64)"), c("ts", "TIMESTAMP WITH TIME ZONE", False), c("created_at", "TIMESTAMP WITH TIME ZONE", False, "NOW()")], "id", [["config_version", "config_name"]], [idx("config_versions", "config_version", "config_name")]),\n        "event_bus_messages": TableSchema("event_bus_messages", [c("id", "BIGSERIAL", False), c("message_id", "VARCHAR(64)", False), c("event_id", "VARCHAR(64)", False), c("event_type", "VARCHAR(64)", False), c("trace_id", "VARCHAR(64)"), c("correlation_id", "VARCHAR(64)"), c("source", "VARCHAR(64)", False), c("target", "VARCHAR(64)"), c("priority", "VARCHAR(16)", False), c("payload", "JSONB", False), c("status", "VARCHAR(32)", False), c("ts", "TIMESTAMP WITH TIME ZONE", False), c("created_at", "TIMESTAMP WITH TIME ZONE", False, "NOW()")], "id", [["message_id"]], [idx("event_bus_messages", "event_type", "ts"), idx("event_bus_messages", "trace_id"), idx("event_bus_messages", "correlation_id"), idx("event_bus_messages", "status", "ts")], "partition by month"),\n        "system_health": TableSchema("system_health", [c("id", "BIGSERIAL", False), c("ts", "TIMESTAMP WITH TIME ZONE", False), c("component", "VARCHAR(64)", False), c("status", "VARCHAR(32)", False), c("latency_ms", "NUMERIC(18, 8)"), c("error_count", "INT"), c("warning_count", "INT"), c("health_json", "JSONB"), c("created_at", "TIMESTAMP WITH TIME ZONE", False, "NOW()")], "id", [], [idx("system_health", "component", "ts"), idx("system_health", "status", "ts")]),\n    }\n)\n\nWRITE_BOUNDARIES = {\n    "data layer": ["market_candles", "symbols"],\n    "indicator layer": ["indicator_results"],\n    "context layer": ["multi_tf_contexts"],\n    "signal layer": ["signals"],\n    "state machine": ["strategy_events"],\n    "risk layer": ["risk_snapshots", "cooldowns", "positions"],\n    "execution layer": ["orders", "order_fills", "positions"],\n    "backtest layer": ["backtest_runs", "backtest_steps", "backtest_trades", "performance_metrics"],\n    "audit layer": ["audit_logs", "event_bus_messages", "system_health"],\n    "config layer": ["config_versions"],\n    "reporting layer": ["reports"],\n}\nIDEMPOTENCY_KEYS = {\n    "strategy_events": "event_id",\n    "orders": "client_order_id",\n    "backtest_runs": "run_id",\n    "risk_snapshots": "snapshot_id",\n    "account_snapshots": "snapshot_id",\n}\nPARTITIONED_TABLES = ["market_candles", "strategy_events", "orders", "order_fills", "audit_logs", "event_bus_messages"]\nRETENTION_POLICY = {\n    "market_candles": "long_term",\n    "indicator_results": "6_to_12_months",\n    "strategy_events": "12_months_plus",\n    "orders": "long_term",\n    "order_fills": "long_term",\n    "backtest_runs": "long_term",\n    "backtest_trades": "long_term",\n    "audit_logs": "long_term",\n    "system_health": "3_to_6_months",\n}\nJSON_FIELD_POLICY = {\n    "allowed": [\n        "indicator composite results",\n        "strategy context details",\n        "raw execution responses",\n        "backtest summaries",\n        "audit extensions",\n    ],\n    "forbidden": ["core filter logic", "core fields", "unstructured business records"],\n}\nMIGRATION_REQUIREMENTS = ["migration_script", "rollback_script", "version", "compatibility_notes", "test_verification"]\nSTARTUP_CHECKS = ["tables_exist", "indexes_exist", "version_matches", "required_fields_present", "database_writable", "connection_healthy"]\nHIGH_FREQUENCY_QUERIES = [\n    "recent_candles",\n    "recent_indicator_results",\n    "current_positions",\n    "recent_strategy_events",\n    "recent_orders_and_fills",\n    "current_risk_snapshot",\n    "current_cooldown_state",\n    "current_backtest_result",\n]\nFORBIDDEN_DATABASE_PATTERNS = [\n    "single_super_table",\n    "execution_temp_state_in_long_term_table",\n    "mixed_live_backtest_without_source",\n    "database_field_patch_business_logic",\n    "strategy_mutates_raw_history",\n    "json_as_universal_storage",\n    "business_record_without_unique_key",\n]\nEXTENSION_TABLES = [\n    "market_regime_history",\n    "signal_scores",\n    "trade_decisions",\n    "slippage_records",\n    "funding_rates",\n    "open_interest_snapshots",\n    "correlation_matrix_snapshots",\n]\n\n\ndef render_create_table(table_name: str) -> str:\n    schema = TABLE_SCHEMAS[table_name]\n    lines = [f"  {column.ddl()}" for column in schema.columns]\n    lines.append(f"  PRIMARY KEY ({schema.primary_key})")\n    for unique_key in schema.unique_keys:\n        lines.append(f"  UNIQUE({\', \'.join(unique_key)})")\n    return f"CREATE TABLE {schema.name} (\\n" + ",\\n".join(lines) + "\\n);"\n\n\ndef validate_schema_contract() -> SchemaValidationResult:\n    errors: list[str] = []\n    version_exempt_tables = {"backtest_runs", "backtest_steps", "backtest_trades", "reports", "config_versions", "event_bus_messages", "system_health"}\n    for table in CORE_TABLES:\n        schema = TABLE_SCHEMAS.get(table)\n        if schema is None:\n            errors.append(f"missing table schema: {table}")\n            continue\n        names = schema.column_names()\n        if schema.primary_key not in names:\n            errors.append(f"{table} missing primary key column: {schema.primary_key}")\n        if not any(column.name in {"ts", "open_time", "trade_time", "started_at", "entry_time", "created_at"} for column in schema.columns):\n            errors.append(f"{table} missing time field")\n        if not any(column.name == "version" for column in schema.columns) and table not in version_exempt_tables:\n            errors.append(f"{table} missing version field")\n        for unique_key in schema.unique_keys:\n            missing = [column for column in unique_key if column not in names]\n            if missing:\n                errors.append(f"{table} unique key references missing columns: {missing}")\n        for index in schema.indexes:\n            missing = [column for column in index.columns if column not in names]\n            if missing:\n                errors.append(f"{table} index {index.name} references missing columns: {missing}")\n    return SchemaValidationResult(not errors, errors)\n',
    'scripts/describe_database_schema.py': 'from __future__ import annotations\n\nimport json\nfrom pathlib import Path\nimport sys\n\n\nROOT = Path(__file__).resolve().parents[1]\nif str(ROOT) not in sys.path:\n    sys.path.insert(0, str(ROOT))\n\nfrom src.data.database_schema import (\n    COMMON_CORE_FIELDS,\n    CORE_TABLES,\n    DATABASE_ENGINE,\n    DATA_LAYERS,\n    EXTENSION_TABLES,\n    FORBIDDEN_DATABASE_PATTERNS,\n    HIGH_FREQUENCY_QUERIES,\n    IDEMPOTENCY_KEYS,\n    JSON_FIELD_POLICY,\n    MIGRATION_REQUIREMENTS,\n    PARTITIONED_TABLES,\n    RETENTION_POLICY,\n    STARTUP_CHECKS,\n    TABLE_SCHEMAS,\n    WRITE_BOUNDARIES,\n)\n\n\ndef main() -> None:\n    payload = {\n        "database_engine": DATABASE_ENGINE,\n        "data_layers": DATA_LAYERS,\n        "common_core_fields": COMMON_CORE_FIELDS,\n        "core_tables": CORE_TABLES,\n        "tables": {\n            name: {\n                "columns": schema.column_names(),\n                "primary_key": schema.primary_key,\n                "unique_keys": schema.unique_keys,\n                "indexes": [index.columns for index in schema.indexes],\n                "partition_hint": schema.partition_hint,\n            }\n            for name, schema in TABLE_SCHEMAS.items()\n        },\n        "write_boundaries": WRITE_BOUNDARIES,\n        "idempotency_keys": IDEMPOTENCY_KEYS,\n        "partitioned_tables": PARTITIONED_TABLES,\n        "retention_policy": RETENTION_POLICY,\n        "json_field_policy": JSON_FIELD_POLICY,\n        "migration_requirements": MIGRATION_REQUIREMENTS,\n        "startup_checks": STARTUP_CHECKS,\n        "high_frequency_queries": HIGH_FREQUENCY_QUERIES,\n        "forbidden_patterns": FORBIDDEN_DATABASE_PATTERNS,\n        "extension_tables": EXTENSION_TABLES,\n        "side_effect_policy": "schema contract only; no database connection or live writes",\n    }\n    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))\n\n\nif __name__ == "__main__":\n    main()\n',
    'tests/test_database_schema.py': 'from src.data.database_schema import (\n    COMMON_CORE_FIELDS,\n    CORE_TABLES,\n    DATABASE_ENGINE,\n    DATA_LAYERS,\n    EXTENSION_TABLES,\n    FORBIDDEN_DATABASE_PATTERNS,\n    IDEMPOTENCY_KEYS,\n    JSON_FIELD_POLICY,\n    MIGRATION_REQUIREMENTS,\n    PARTITIONED_TABLES,\n    RETENTION_POLICY,\n    TABLE_SCHEMAS,\n    WRITE_BOUNDARIES,\n    render_create_table,\n    validate_schema_contract,\n)\n\n\ndef test_database_engine_layers_and_core_tables_match_doc():\n    assert DATABASE_ENGINE == "PostgreSQL"\n    assert DATA_LAYERS == ["hot", "warm", "cold", "archive"]\n    assert CORE_TABLES == [\n        "symbols",\n        "market_candles",\n        "indicator_results",\n        "multi_tf_contexts",\n        "strategy_events",\n        "signals",\n        "orders",\n        "order_fills",\n        "positions",\n        "risk_snapshots",\n        "account_snapshots",\n        "cooldowns",\n        "backtest_runs",\n        "backtest_steps",\n        "backtest_trades",\n        "performance_metrics",\n        "audit_logs",\n        "reports",\n        "config_versions",\n        "event_bus_messages",\n        "system_health",\n    ]\n    assert COMMON_CORE_FIELDS == ["id", "symbol", "timeframe", "ts", "version", "source", "created_at", "updated_at"]\n\n\ndef test_core_table_metadata_includes_required_columns_indexes_and_unique_keys():\n    symbols = TABLE_SCHEMAS["symbols"]\n    assert symbols.primary_key == "id"\n    assert "symbol" in symbols.column_names()\n    assert symbols.unique_keys == [["symbol"]]\n    assert ["symbol"] in [index.columns for index in symbols.indexes]\n    candles = TABLE_SCHEMAS["market_candles"]\n    assert "open_time" in candles.column_names()\n    assert "close_time" in candles.column_names()\n    assert candles.unique_keys == [["symbol", "timeframe", "open_time"]]\n    assert ["symbol", "timeframe", "open_time"] in [index.columns for index in candles.indexes]\n    strategy_events = TABLE_SCHEMAS["strategy_events"]\n    assert "event_id" in strategy_events.column_names()\n    assert "trace_id" in strategy_events.column_names()\n    assert ["event_id"] in strategy_events.unique_keys\n    orders = TABLE_SCHEMAS["orders"]\n    assert "client_order_id" in orders.column_names()\n    assert "exchange_response" in orders.column_names()\n    assert ["client_order_id"] in orders.unique_keys\n\n\ndef test_validate_schema_contract_accepts_all_doc_tables():\n    result = validate_schema_contract()\n    assert result.passed is True\n    assert result.errors == []\n\n\ndef test_render_create_table_includes_primary_key_unique_keys_and_jsonb_fields():\n    ddl = render_create_table("strategy_events")\n    assert ddl.startswith("CREATE TABLE strategy_events")\n    assert "id BIGSERIAL NOT NULL" in ddl\n    assert "PRIMARY KEY (id)" in ddl\n    assert "UNIQUE(event_id)" in ddl\n    assert "payload JSONB NOT NULL" in ddl\n    candle_ddl = render_create_table("market_candles")\n    assert "UNIQUE(symbol, timeframe, open_time)" in candle_ddl\n    assert "quality_flag VARCHAR(16) NOT NULL DEFAULT \'true\'" in candle_ddl\n\n\ndef test_write_boundaries_idempotency_partition_and_retention_policies_match_doc():\n    assert WRITE_BOUNDARIES["data layer"] == ["market_candles", "symbols"]\n    assert WRITE_BOUNDARIES["execution layer"] == ["orders", "order_fills", "positions"]\n    assert WRITE_BOUNDARIES["audit layer"] == ["audit_logs", "event_bus_messages", "system_health"]\n    assert IDEMPOTENCY_KEYS == {\n        "strategy_events": "event_id",\n        "orders": "client_order_id",\n        "backtest_runs": "run_id",\n        "risk_snapshots": "snapshot_id",\n        "account_snapshots": "snapshot_id",\n    }\n    assert PARTITIONED_TABLES == ["market_candles", "strategy_events", "orders", "order_fills", "audit_logs", "event_bus_messages"]\n    assert RETENTION_POLICY["market_candles"] == "long_term"\n    assert RETENTION_POLICY["system_health"] == "3_to_6_months"\n\n\ndef test_json_migration_forbidden_and_extension_policies_match_doc():\n    assert JSON_FIELD_POLICY["allowed"] == [\n        "indicator composite results",\n        "strategy context details",\n        "raw execution responses",\n        "backtest summaries",\n        "audit extensions",\n    ]\n    assert JSON_FIELD_POLICY["forbidden"] == ["core filter logic", "core fields", "unstructured business records"]\n    assert MIGRATION_REQUIREMENTS == ["migration_script", "rollback_script", "version", "compatibility_notes", "test_verification"]\n    assert "single_super_table" in FORBIDDEN_DATABASE_PATTERNS\n    assert "database_field_patch_business_logic" in FORBIDDEN_DATABASE_PATTERNS\n    assert EXTENSION_TABLES == [\n        "market_regime_history",\n        "signal_scores",\n        "trade_decisions",\n        "slippage_records",\n        "funding_rates",\n        "open_interest_snapshots",\n        "correlation_matrix_snapshots",\n    ]\n',
    'tests/test_describe_database_schema.py': 'import json\nimport subprocess\nimport sys\n\n\ndef test_describe_database_schema_outputs_completed_15_sections():\n    completed = subprocess.run(\n        [sys.executable, "scripts/describe_database_schema.py"],\n        check=True,\n        capture_output=True,\n        text=True,\n    )\n    payload = json.loads(completed.stdout)\n    assert payload["database_engine"] == "PostgreSQL"\n    assert payload["data_layers"] == ["hot", "warm", "cold", "archive"]\n    assert payload["core_tables"][0] == "symbols"\n    assert payload["core_tables"][-1] == "system_health"\n    assert payload["tables"]["market_candles"]["unique_keys"] == [["symbol", "timeframe", "open_time"]]\n    assert payload["write_boundaries"]["execution layer"] == ["orders", "order_fills", "positions"]\n    assert payload["idempotency_keys"]["orders"] == "client_order_id"\n    assert "market_candles" in payload["partitioned_tables"]\n    assert payload["retention_policy"]["system_health"] == "3_to_6_months"\n    assert "database_field_patch_business_logic" in payload["forbidden_patterns"]\n',
    "scripts/describe_signal_engine.py": """
from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.signals.signal_engine import (
    ENTRY_MODES,
    INDICATOR_ROLES,
    SCORE_COMPONENTS,
    SIGNAL_DECISION_FLOW,
    SIGNAL_EVIDENCE_FIELDS,
    SIGNAL_FORBIDDEN_ACTIONS,
    SIGNAL_SIDES,
    SIGNAL_SUB_REASONS,
    SIGNAL_TYPES,
    STATE_MACHINE_MAPPING,
    TIMEFRAME_ROLES,
    generate_signal,
)


def main() -> None:
    sample = generate_signal(
        {
            "symbol": "BTCUSDT",
            "timestamp": 1,
            "market_state_4h": "BULL",
            "trend_state_1h": "LONG_ALLOWED",
            "confirm_state_30m": "LONG_CONFIRM",
            "trigger_state_15m": "LONG",
            "indicators_15m": {"cvd": "LONG", "rsi": "RECOVERY", "boll": "EXPANSION", "atr": "NORMAL"},
            "indicators_30m": {"macd": "LONG", "cci": "STRONG"},
            "indicators_1h": {},
            "indicators_4h": {},
            "risk_snapshot": {"risk_blocked": False},
            "position_snapshot": {},
            "cooldown_state": {"active": False},
            "quality_flag": True,
        }
    ).to_dict()
    payload = {
        "engine": "signal_engine",
        "responsibility": "generate_trade_intent_only",
        "allowed_outputs": {
            "signal_type": SIGNAL_TYPES,
            "signal_side": SIGNAL_SIDES,
            "entry_mode": ENTRY_MODES,
        },
        "decision_flow": SIGNAL_DECISION_FLOW,
        "timeframe_roles": TIMEFRAME_ROLES,
        "indicator_roles": INDICATOR_ROLES,
        "score_components": SCORE_COMPONENTS,
        "standard_sub_reasons": SIGNAL_SUB_REASONS,
        "state_machine_mapping": STATE_MACHINE_MAPPING,
        "evidence_fields": SIGNAL_EVIDENCE_FIELDS,
        "forbidden_actions": {
            "signal layer": SIGNAL_FORBIDDEN_ACTIONS,
            "execution layer": [
                "must_not_modify_signal_type",
                "must_not_rewrite_entry_mode",
                "must_not_promote_probe_to_direct",
                "must_not_change_side",
                "must_not_add_new_trade_reason",
            ],
        },
        "downgrade_policy": {
            "data_quality_failure": "NO_TRADE, WAIT, or no DIRECT",
            "cooldown_active": "NO_TRADE",
            "risk_blocked": "NO_TRADE",
            "flow_divergence": "downgrade from DIRECT to WAIT or NO_TRADE",
            "anti_chase": "RSI overheat or BOLL extension prevents DIRECT",
        },
        "sample_direct_long": sample,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
""",
    "tests/test_signal_engine.py": """
from src.signals.signal_engine import (
    ENTRY_MODES,
    SIGNAL_EVIDENCE_FIELDS,
    SIGNAL_FORBIDDEN_ACTIONS,
    SIGNAL_TYPES,
    STATE_MACHINE_MAPPING,
    SignalEngineContext,
    generate_signal,
)


def base_context(**overrides):
    context = {
        "symbol": "BTCUSDT",
        "timestamp": 1,
        "market_state_4h": "BULL",
        "trend_state_1h": "LONG_ALLOWED",
        "confirm_state_30m": "LONG_CONFIRM",
        "trigger_state_15m": "LONG",
        "indicators_15m": {
            "cvd": "LONG",
            "rsi": "RECOVERY",
            "boll": "EXPANSION",
            "atr": "NORMAL",
        },
        "indicators_30m": {"macd": "LONG", "cci": "STRONG"},
        "indicators_1h": {},
        "indicators_4h": {},
        "risk_snapshot": {"risk_blocked": False},
        "position_snapshot": {},
        "cooldown_state": {"active": False},
        "quality_flag": True,
    }
    context.update(overrides)
    return context


def test_direct_long_records_evidence_and_required_state():
    result = generate_signal(base_context())

    assert result.signal_type == "LONG"
    assert result.signal_side == "LONG"
    assert result.entry_mode == "DIRECT"
    assert result.required_state == "DIRECT_LONG"
    assert result["side"] == "LONG"
    assert result.score >= 0.7
    assert "TREND_ALIGNED" in result.sub_reasons
    assert "FLOW_CONFIRMED" in result.sub_reasons
    assert result.metadata["evidence"]["trigger_state_15m"] == "LONG"


def test_direct_short_is_symmetric():
    result = generate_signal(
        base_context(
            market_state_4h="BEAR",
            trend_state_1h="SHORT_ALLOWED",
            confirm_state_30m="SHORT_CONFIRM",
            trigger_state_15m="SHORT",
            indicators_15m={"cvd": "SHORT", "rsi": "RECOVERY", "boll": "EXPANSION", "atr": "NORMAL"},
            indicators_30m={"macd": "SHORT", "cci": "STRONG"},
        )
    )

    assert result.signal_type == "SHORT"
    assert result.signal_side == "SHORT"
    assert result.entry_mode == "DIRECT"
    assert result.required_state == "DIRECT_SHORT"


def test_probe_when_trigger_is_partial():
    result = generate_signal(base_context(trigger_state_15m="LONG_PARTIAL"))

    assert result.signal_type == "LONG"
    assert result.signal_side == "LONG"
    assert result.entry_mode == "PROBE"
    assert result.required_state == "PROBE_LONG"


def test_wait_when_trigger_is_not_ready():
    result = generate_signal(base_context(trigger_state_15m="WAIT"))

    assert result.signal_type == "WAIT"
    assert result.signal_side == "NONE"
    assert result.entry_mode == "NONE"
    assert result.required_state == "WATCH_*"
    assert "TRIGGER_NOT_READY" in result.sub_reasons


def test_no_trade_for_data_quality_cooldown_risk_and_trend_conflict():
    assert generate_signal(base_context(quality_flag=False)).reason == "DATA_INVALID"
    assert generate_signal(base_context(cooldown_state={"active": True})).reason == "COOLDOWN_ACTIVE"
    assert generate_signal(base_context(risk_snapshot={"risk_blocked": True})).reason == "RISK_BLOCKED"
    assert generate_signal(base_context(market_state_4h="BEAR")).reason == "HIGHER_TIMEFRAME_CONFLICT"


def test_flow_divergence_downgrades_to_wait():
    result = generate_signal(base_context(indicators_15m={"cvd": "DIVERGENCE", "rsi": "RECOVERY"}))

    assert result.signal_type == "WAIT"
    assert result.entry_mode == "NONE"
    assert "FLOW_DIVERGENCE" in result.sub_reasons


def test_rsi_overheated_prevents_direct_long():
    result = generate_signal(base_context(indicators_15m={"cvd": "LONG", "rsi": "OVERHEATED", "boll": "EXPANSION"}))

    assert result.signal_type == "LONG"
    assert result.entry_mode == "PROBE"
    assert "RSI_OVERHEATED" in result.sub_reasons


def test_dataclass_context_is_supported():
    ctx = SignalEngineContext(**base_context())
    result = generate_signal(ctx)

    assert result.signal_type == "LONG"
    assert result.entry_mode == "DIRECT"


def test_signal_engine_public_contract_constants():
    assert SIGNAL_TYPES == ["LONG", "SHORT", "WAIT", "NO_TRADE"]
    assert ENTRY_MODES == ["PROBE", "DIRECT", "NONE"]
    assert STATE_MACHINE_MAPPING["PROBE"] == "PROBE_*"
    assert "call_exchange_adapter" in SIGNAL_FORBIDDEN_ACTIONS
    assert "cvd_state" in SIGNAL_EVIDENCE_FIELDS
""",
    "tests/test_describe_signal_engine.py": """
import json
import subprocess
import sys


def test_describe_signal_engine_outputs_completed_16_sections():
    result = subprocess.run(
        [sys.executable, "scripts/describe_signal_engine.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["engine"] == "signal_engine"
    assert payload["responsibility"] == "generate_trade_intent_only"
    assert payload["allowed_outputs"]["signal_type"] == ["LONG", "SHORT", "WAIT", "NO_TRADE"]
    assert payload["allowed_outputs"]["entry_mode"] == ["PROBE", "DIRECT", "NONE"]
    assert payload["decision_flow"][0] == "read_multi_timeframe_context"
    assert payload["decision_flow"][-1] == "record_evidence_fields"
    assert payload["timeframe_roles"]["15m"] == "entry_trigger_only"
    assert payload["indicator_roles"]["ATR"][-1] == "no_direction_decision"
    assert payload["score_components"] == [
        "trend_score",
        "confirm_score",
        "trigger_score",
        "flow_score",
        "volatility_score",
    ]
    assert "FLOW_DIVERGENCE" in payload["standard_sub_reasons"]
    assert payload["state_machine_mapping"]["DIRECT"] == "DIRECT_*"
    assert "execution layer" in payload["forbidden_actions"]
    assert "call_exchange_adapter" in payload["forbidden_actions"]["signal layer"]
    assert payload["downgrade_policy"]["risk_blocked"] == "NO_TRADE"
    assert payload["sample_direct_long"]["entry_mode"] == "DIRECT"
""",
    "src/risk/risk_engine.py": """
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from src.risk.exit_engine import EXIT_PRIORITY, forced_exit_actions, plan_take_profit_actions, select_highest_priority_action
from src.risk.stop_engine import initial_atr_stop


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
RISK_SCORE_COMPONENTS = [
    "account_risk_score",
    "portfolio_risk_score",
    "symbol_risk_score",
    "volatility_risk_score",
    "cooldown_risk_score",
    "data_quality_risk_score",
]
RISK_REQUIRED_INPUTS = [
    "symbol",
    "timestamp",
    "signal_type",
    "signal_side",
    "entry_mode",
    "account_equity",
    "available_margin",
    "used_margin",
    "open_positions",
    "portfolio_exposure",
    "symbol_exposure",
    "daily_pnl",
    "weekly_pnl",
    "max_drawdown",
    "atr",
    "stop_pct",
    "quality_flag",
    "cooldown_state",
    "market_state_4h",
    "trend_state_1h",
    "confirm_state_30m",
    "trigger_state_15m",
]
RISK_OUTPUT_FIELDS = [
    "allow_trade",
    "allow_add",
    "allow_reduce",
    "allow_exit",
    "risk_level",
    "risk_reason",
    "risk_score",
    "position_size_factor",
    "stop_distance",
    "stop_pct",
    "take_profit_plan",
    "cooldown_required",
    "cooldown_bars",
    "portfolio_blocked",
    "metrics_snapshot",
    "metadata",
]
RISK_SNAPSHOT_FIELDS = [
    "symbol",
    "timestamp",
    "account_equity",
    "available_margin",
    "daily_pnl",
    "weekly_pnl",
    "max_drawdown",
    "portfolio_exposure",
    "symbol_exposure",
    "atr",
    "stop_pct",
    "risk_score",
    "risk_level",
    "allow_trade",
    "allow_add",
    "allow_reduce",
    "allow_exit",
    "risk_reason",
]
RISK_FORBIDDEN_ACTIONS = [
    "generate_trade_signal",
    "submit_or_cancel_orders",
    "change_signal_side",
    "promote_probe_to_direct",
    "calculate_exchange_precision_quantity",
    "maintain_exchange_connection",
    "use_different_live_and_backtest_rules",
]
DEFAULT_RISK_LIMITS = {
    "daily_loss_limit_pct": 0.05,
    "weekly_loss_limit_pct": 0.12,
    "max_drawdown_pct": 0.20,
    "max_symbol_exposure_pct": 0.20,
    "max_portfolio_exposure_pct": 0.75,
    "max_open_positions": 5,
    "risk_per_trade_pct": 0.01,
    "min_stop_pct": 0.005,
    "max_stop_pct": 0.08,
    "stop_atr_mult": 1.5,
    "normal_cooldown_bars": 4,
}
PROBE_POSITION_FACTOR = 0.25
DIRECT_POSITION_FACTOR = 1.0


@dataclass(frozen=True)
class RiskContext:
    symbol: str
    timestamp: Any
    signal_type: str
    signal_side: str
    entry_mode: str
    account_equity: float
    available_margin: float
    used_margin: float
    open_positions: int
    portfolio_exposure: float
    symbol_exposure: float
    daily_pnl: float
    weekly_pnl: float
    max_drawdown: float
    atr: float
    stop_pct: float
    quality_flag: bool
    cooldown_state: Mapping[str, Any]
    market_state_4h: str
    trend_state_1h: str
    confirm_state_30m: str
    trigger_state_15m: str
    entry_price: float = 100.0
    volatility_state: str = "NORMAL"
    stop_hit: bool = False
    direction_reversal: bool = False
    exchange_error: bool = False
    risk_limits: Mapping[str, float] | None = None


@dataclass(frozen=True)
class RiskScoreBreakdown:
    account_risk_score: int = 0
    portfolio_risk_score: int = 0
    symbol_risk_score: int = 0
    volatility_risk_score: int = 0
    cooldown_risk_score: int = 0
    data_quality_risk_score: int = 0

    @property
    def total(self) -> int:
        return sum(asdict(self).values())


@dataclass(frozen=True)
class RiskResult:
    allow_trade: bool
    allow_add: bool
    allow_reduce: bool
    allow_exit: bool
    risk_level: str
    risk_reason: str
    risk_score: int
    position_size_factor: float
    stop_distance: float
    stop_pct: float
    take_profit_plan: list[dict[str, Any]]
    cooldown_required: bool
    cooldown_bars: int
    portfolio_blocked: bool
    metrics_snapshot: dict[str, Any]
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_risk(context: RiskContext | Mapping[str, Any]) -> RiskResult:
    ctx = _normalize_context(context)
    limits = _risk_limits(ctx)
    score = RiskScoreBreakdown()
    stop_distance, effective_stop_pct = _stop_values(ctx, limits)

    if not ctx["quality_flag"]:
        score = _replace_score(score, data_quality_risk_score=8)
        return _blocked(ctx, score, "DATA_QUALITY_BLOCKED", stop_distance, effective_stop_pct, cooldown_required=True)

    if _cooldown_active(ctx["cooldown_state"]):
        score = _replace_score(score, cooldown_risk_score=8)
        return _blocked(ctx, score, "COOLDOWN_ACTIVE", stop_distance, effective_stop_pct, cooldown_required=False)

    account_reason = _account_block_reason(ctx, limits)
    if account_reason is not None:
        score = _replace_score(score, account_risk_score=8)
        return _blocked(ctx, score, account_reason, stop_distance, effective_stop_pct, cooldown_required=True)

    portfolio_reason = _portfolio_block_reason(ctx, limits)
    if portfolio_reason is not None:
        score = _replace_score(score, portfolio_risk_score=8)
        return _blocked(ctx, score, portfolio_reason, stop_distance, effective_stop_pct, cooldown_required=True, portfolio_blocked=True)

    symbol_reason = _symbol_block_reason(ctx, limits)
    if symbol_reason is not None:
        score = _replace_score(score, symbol_risk_score=8)
        return _blocked(ctx, score, symbol_reason, stop_distance, effective_stop_pct, cooldown_required=True)

    stop_reason = _stop_block_reason(ctx, limits, effective_stop_pct)
    if stop_reason is not None:
        score = _replace_score(score, volatility_risk_score=8)
        return _blocked(ctx, score, stop_reason, stop_distance, effective_stop_pct, cooldown_required=False)

    if ctx["available_margin"] <= 0:
        score = _replace_score(score, account_risk_score=8)
        return _blocked(ctx, score, "AVAILABLE_MARGIN_INSUFFICIENT", stop_distance, effective_stop_pct, cooldown_required=False)

    score = _score_soft_risk(ctx, limits, score)
    forced = select_highest_priority_action(
        forced_exit_actions(
            stop_hit=ctx["stop_hit"],
            portfolio_risk=ctx["portfolio_exposure"] >= limits["max_portfolio_exposure_pct"] * 0.95,
            direction_reversal=ctx["direction_reversal"],
            volatility_anomaly=_volatility_state(ctx) == "EXTREME",
        )
    )
    if forced is not None and forced.action_type.value in {"FORCED_STOP", "PORTFOLIO_RISK"}:
        score = _replace_score(score, portfolio_risk_score=max(score.portfolio_risk_score, 6))
        return _result(
            ctx,
            score,
            "EXTREME",
            "FORCED_EXIT_REQUIRED",
            False,
            False,
            True,
            True,
            0.0,
            stop_distance,
            effective_stop_pct,
            cooldown_required=True,
            portfolio_blocked=forced.action_type.value == "PORTFOLIO_RISK",
            exit_action=forced,
        )

    risk_level = _risk_level(score.total)
    position_factor = _position_factor(ctx, risk_level)
    allow_trade = risk_level not in {"EXTREME", "BLOCKED"} and position_factor > 0
    allow_reduce = risk_level in {"HIGH", "EXTREME"} or ctx["portfolio_exposure"] >= limits["max_portfolio_exposure_pct"] * 0.85
    allow_exit = bool(forced or risk_level in {"HIGH", "EXTREME"})

    if risk_level == "HIGH":
        reason = "TREND_OK_BUT_VOLATILITY_HIGH" if _volatility_state(ctx) == "HIGH" else "RISK_HIGH_POSITION_REDUCED"
    elif risk_level == "LOW":
        reason = "RISK_LOW"
    else:
        reason = "FULL_CONFIRMATION_AND_RISK_OK"

    return _result(
        ctx,
        score,
        risk_level,
        reason,
        allow_trade,
        _allow_add(ctx, risk_level),
        allow_reduce,
        allow_exit,
        position_factor,
        stop_distance,
        effective_stop_pct,
        cooldown_required=False,
        portfolio_blocked=False,
        exit_action=forced,
    )


def _normalize_context(context: RiskContext | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(context, RiskContext):
        data = asdict(context)
    else:
        data = dict(context)
    normalized = {field: data.get(field) for field in RISK_REQUIRED_INPUTS}
    normalized.update(
        {
            "entry_price": data.get("entry_price", 100.0),
            "volatility_state": data.get("volatility_state", "NORMAL"),
            "stop_hit": bool(data.get("stop_hit", False)),
            "direction_reversal": bool(data.get("direction_reversal", False)),
            "exchange_error": bool(data.get("exchange_error", False)),
            "risk_limits": dict(data.get("risk_limits") or {}),
        }
    )
    normalized["symbol"] = str(normalized.get("symbol") or "").upper()
    normalized["signal_type"] = str(normalized.get("signal_type") or "NO_TRADE").upper()
    normalized["signal_side"] = str(normalized.get("signal_side") or "NONE").upper()
    normalized["entry_mode"] = str(normalized.get("entry_mode") or "NONE").upper()
    normalized["cooldown_state"] = dict(normalized.get("cooldown_state") or {})
    normalized["quality_flag"] = bool(normalized.get("quality_flag"))
    for key in (
        "account_equity",
        "available_margin",
        "used_margin",
        "portfolio_exposure",
        "symbol_exposure",
        "daily_pnl",
        "weekly_pnl",
        "max_drawdown",
        "atr",
        "stop_pct",
        "entry_price",
    ):
        normalized[key] = float(normalized.get(key) or 0.0)
    normalized["open_positions"] = int(normalized.get("open_positions") or 0)
    return normalized


def _risk_limits(ctx: Mapping[str, Any]) -> dict[str, float]:
    limits = dict(DEFAULT_RISK_LIMITS)
    limits.update(ctx.get("risk_limits") or {})
    return limits


def _blocked(
    ctx: Mapping[str, Any],
    score: RiskScoreBreakdown,
    reason: str,
    stop_distance: float,
    stop_pct: float,
    cooldown_required: bool,
    portfolio_blocked: bool = False,
) -> RiskResult:
    return _result(
        ctx,
        score,
        "BLOCKED",
        reason,
        False,
        False,
        portfolio_blocked or reason in {"WEEKLY_LOSS_LIMIT_REACHED", "MAX_DRAWDOWN_LIMIT_REACHED"},
        True,
        0.0,
        stop_distance,
        stop_pct,
        cooldown_required=cooldown_required,
        portfolio_blocked=portfolio_blocked,
        exit_action=None,
    )


def _result(
    ctx: Mapping[str, Any],
    score: RiskScoreBreakdown,
    risk_level: str,
    risk_reason: str,
    allow_trade: bool,
    allow_add: bool,
    allow_reduce: bool,
    allow_exit: bool,
    position_size_factor: float,
    stop_distance: float,
    stop_pct: float,
    cooldown_required: bool,
    portfolio_blocked: bool,
    exit_action: Any,
) -> RiskResult:
    take_profit_plan = []
    if ctx["signal_side"] in {"LONG", "SHORT"} and stop_distance > 0 and ctx["entry_price"] > 0:
        stop_price = ctx["entry_price"] - stop_distance if ctx["signal_side"] == "LONG" else ctx["entry_price"] + stop_distance
        take_profit_plan = [
            {
                "action_type": action.action_type.value,
                "reason": action.reason,
                "reduce_pct": action.reduce_pct,
                "target_price": action.target_price,
            }
            for action in plan_take_profit_actions(ctx["entry_price"], stop_price, ctx["signal_side"])
        ]
    snapshot = {
        "symbol": ctx["symbol"],
        "timestamp": ctx["timestamp"],
        "account_equity": ctx["account_equity"],
        "available_margin": ctx["available_margin"],
        "daily_pnl": ctx["daily_pnl"],
        "weekly_pnl": ctx["weekly_pnl"],
        "max_drawdown": ctx["max_drawdown"],
        "portfolio_exposure": ctx["portfolio_exposure"],
        "symbol_exposure": ctx["symbol_exposure"],
        "atr": ctx["atr"],
        "stop_pct": stop_pct,
        "risk_score": score.total,
        "risk_level": risk_level,
        "allow_trade": allow_trade,
        "allow_add": allow_add,
        "allow_reduce": allow_reduce,
        "allow_exit": allow_exit,
        "risk_reason": risk_reason,
    }
    return RiskResult(
        allow_trade=allow_trade,
        allow_add=allow_add,
        allow_reduce=allow_reduce,
        allow_exit=allow_exit,
        risk_level=risk_level,
        risk_reason=risk_reason,
        risk_score=score.total,
        position_size_factor=position_size_factor,
        stop_distance=stop_distance,
        stop_pct=stop_pct,
        take_profit_plan=take_profit_plan,
        cooldown_required=cooldown_required,
        cooldown_bars=int(_risk_limits(ctx)["normal_cooldown_bars"]) if cooldown_required else 0,
        portfolio_blocked=portfolio_blocked,
        metrics_snapshot=snapshot,
        metadata={
            "decision_flow": RISK_DECISION_FLOW,
            "score_breakdown": asdict(score),
            "exit_action": None if exit_action is None else asdict(exit_action),
            "exit_priority": [item.value for item in EXIT_PRIORITY],
            "forbidden_actions": RISK_FORBIDDEN_ACTIONS,
        },
    )


def _stop_values(ctx: Mapping[str, Any], limits: Mapping[str, float]) -> tuple[float, float]:
    if ctx["entry_price"] <= 0 or ctx["atr"] <= 0 or ctx["signal_side"] not in {"LONG", "SHORT"}:
        return 0.0, ctx["stop_pct"]
    plan = initial_atr_stop(ctx["entry_price"], ctx["atr"], limits["stop_atr_mult"], ctx["signal_side"])
    effective_stop_pct = ctx["stop_pct"] if ctx["stop_pct"] > 0 else plan.stop_pct
    return ctx["entry_price"] * effective_stop_pct, effective_stop_pct


def _account_block_reason(ctx: Mapping[str, Any], limits: Mapping[str, float]) -> str | None:
    if ctx["account_equity"] <= 0:
        return "ACCOUNT_EQUITY_INVALID"
    if ctx["daily_pnl"] <= -ctx["account_equity"] * limits["daily_loss_limit_pct"]:
        return "DAILY_LOSS_LIMIT_REACHED"
    if ctx["weekly_pnl"] <= -ctx["account_equity"] * limits["weekly_loss_limit_pct"]:
        return "WEEKLY_LOSS_LIMIT_REACHED"
    if ctx["max_drawdown"] >= limits["max_drawdown_pct"]:
        return "MAX_DRAWDOWN_LIMIT_REACHED"
    return None


def _portfolio_block_reason(ctx: Mapping[str, Any], limits: Mapping[str, float]) -> str | None:
    if ctx["portfolio_exposure"] >= limits["max_portfolio_exposure_pct"]:
        return "PORTFOLIO_EXPOSURE_LIMIT_REACHED"
    if ctx["open_positions"] >= int(limits["max_open_positions"]):
        return "MAX_OPEN_POSITIONS_REACHED"
    return None


def _symbol_block_reason(ctx: Mapping[str, Any], limits: Mapping[str, float]) -> str | None:
    if ctx["symbol_exposure"] >= limits["max_symbol_exposure_pct"]:
        return "SYMBOL_EXPOSURE_LIMIT_REACHED"
    return None


def _stop_block_reason(ctx: Mapping[str, Any], limits: Mapping[str, float], stop_pct: float) -> str | None:
    if ctx["atr"] <= 0:
        return "ATR_UNAVAILABLE"
    if stop_pct <= 0:
        return "STOP_DISTANCE_INVALID"
    if stop_pct < limits["min_stop_pct"]:
        return "STOP_DISTANCE_TOO_SMALL"
    if stop_pct > limits["max_stop_pct"]:
        return "STOP_DISTANCE_TOO_LARGE"
    return None


def _score_soft_risk(ctx: Mapping[str, Any], limits: Mapping[str, float], score: RiskScoreBreakdown) -> RiskScoreBreakdown:
    account_score = 2
    portfolio_score = 0
    symbol_score = 0
    volatility_score = 0
    if ctx["daily_pnl"] < 0:
        account_score += 1
    if ctx["weekly_pnl"] < 0:
        account_score += 1
    if ctx["max_drawdown"] >= limits["max_drawdown_pct"] * 0.5:
        account_score += 1
    if ctx["portfolio_exposure"] >= limits["max_portfolio_exposure_pct"] * 0.85:
        portfolio_score += 2
    if ctx["symbol_exposure"] >= limits["max_symbol_exposure_pct"] * 0.75:
        symbol_score += 2
    volatility = _volatility_state(ctx)
    if volatility == "HIGH":
        volatility_score += 3
    elif volatility == "EXTREME":
        volatility_score += 5
    elif volatility == "LOW":
        volatility_score += 1
    return _replace_score(
        score,
        account_risk_score=account_score,
        portfolio_risk_score=portfolio_score,
        symbol_risk_score=symbol_score,
        volatility_risk_score=volatility_score,
    )


def _risk_level(score: int) -> str:
    if score <= 1:
        return "LOW"
    if score <= 3:
        return "NORMAL"
    if score <= 5:
        return "HIGH"
    if score <= 7:
        return "EXTREME"
    return "BLOCKED"


def _position_factor(ctx: Mapping[str, Any], risk_level: str) -> float:
    if risk_level in {"EXTREME", "BLOCKED"}:
        return 0.0
    base = PROBE_POSITION_FACTOR if ctx["entry_mode"] == "PROBE" else DIRECT_POSITION_FACTOR
    if risk_level == "HIGH":
        return min(base, PROBE_POSITION_FACTOR)
    if risk_level == "LOW" and ctx["entry_mode"] == "DIRECT":
        return DIRECT_POSITION_FACTOR
    return base


def _allow_add(ctx: Mapping[str, Any], risk_level: str) -> bool:
    if risk_level not in {"LOW", "NORMAL"}:
        return False
    if ctx["entry_mode"] != "DIRECT":
        return False
    if ctx["portfolio_exposure"] > DEFAULT_RISK_LIMITS["max_portfolio_exposure_pct"] * 0.5:
        return False
    return True


def _cooldown_active(cooldown_state: Mapping[str, Any]) -> bool:
    return bool(
        cooldown_state.get("active")
        or cooldown_state.get("cooldown_active")
        or str(cooldown_state.get("state", "")).upper() == "ACTIVE"
    )


def _volatility_state(ctx: Mapping[str, Any]) -> str:
    return str(ctx.get("volatility_state") or "NORMAL").upper()


def _replace_score(score: RiskScoreBreakdown, **changes: int) -> RiskScoreBreakdown:
    values = asdict(score)
    values.update(changes)
    return RiskScoreBreakdown(**values)
""",
    "scripts/describe_risk_engine.py": """
from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.risk.risk_engine import (
    DEFAULT_RISK_LIMITS,
    RISK_DECISION_FLOW,
    RISK_FORBIDDEN_ACTIONS,
    RISK_LEVELS,
    RISK_OUTPUT_FIELDS,
    RISK_REQUIRED_INPUTS,
    RISK_SCORE_COMPONENTS,
    RISK_SNAPSHOT_FIELDS,
    evaluate_risk,
)


def _sample(**overrides):
    context = {
        "symbol": "BTCUSDT",
        "timestamp": 1,
        "signal_type": "LONG",
        "signal_side": "LONG",
        "entry_mode": "DIRECT",
        "account_equity": 10_000,
        "available_margin": 5_000,
        "used_margin": 1_000,
        "open_positions": 1,
        "portfolio_exposure": 0.20,
        "symbol_exposure": 0.05,
        "daily_pnl": 0,
        "weekly_pnl": 0,
        "max_drawdown": 0.05,
        "atr": 100,
        "stop_pct": 0.02,
        "quality_flag": True,
        "cooldown_state": {"active": False},
        "market_state_4h": "BULL",
        "trend_state_1h": "LONG_ALLOWED",
        "confirm_state_30m": "LONG_CONFIRM",
        "trigger_state_15m": "LONG",
        "entry_price": 50_000,
        "volatility_state": "NORMAL",
    }
    context.update(overrides)
    return evaluate_risk(context).to_dict()


def main() -> None:
    payload = {
        "engine": "risk_engine",
        "responsibility": "pre_trade_risk_gate_and_risk_constraints",
        "risk_levels": RISK_LEVELS,
        "decision_flow": RISK_DECISION_FLOW,
        "required_inputs": RISK_REQUIRED_INPUTS,
        "output_fields": RISK_OUTPUT_FIELDS,
        "default_limits": DEFAULT_RISK_LIMITS,
        "score_components": RISK_SCORE_COMPONENTS,
        "snapshot_fields": RISK_SNAPSHOT_FIELDS,
        "relationships": {
            "signal engine": "provides direction, entry mode, evidence, and candidate intent",
            "position module": "calculates final_notional and final_qty",
            "execution layer": "turns confirmed risk and position decisions into orders and logs",
        },
        "forbidden_actions": {
            "risk layer": RISK_FORBIDDEN_ACTIONS,
            "execution layer": [
                "must_not_modify_stop",
                "must_not_modify_position_size",
                "must_not_recalculate_risk",
                "must_not_infer_trade_continuation",
            ],
        },
        "sample": {
            "direct": _sample(),
            "probe": _sample(entry_mode="PROBE"),
            "blocked": _sample(daily_pnl=-600),
            "high_volatility": _sample(volatility_state="HIGH"),
        },
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
""",
    "tests/test_risk_engine.py": """
from src.risk.risk_engine import (
    DEFAULT_RISK_LIMITS,
    RISK_DECISION_FLOW,
    RISK_FORBIDDEN_ACTIONS,
    RISK_LEVELS,
    RISK_OUTPUT_FIELDS,
    RISK_REQUIRED_INPUTS,
    RISK_SNAPSHOT_FIELDS,
    RiskContext,
    evaluate_risk,
)


def base_context(**overrides):
    context = {
        "symbol": "BTCUSDT",
        "timestamp": 1,
        "signal_type": "LONG",
        "signal_side": "LONG",
        "entry_mode": "DIRECT",
        "account_equity": 10_000,
        "available_margin": 5_000,
        "used_margin": 1_000,
        "open_positions": 1,
        "portfolio_exposure": 0.20,
        "symbol_exposure": 0.05,
        "daily_pnl": 0,
        "weekly_pnl": 0,
        "max_drawdown": 0.05,
        "atr": 100,
        "stop_pct": 0.02,
        "quality_flag": True,
        "cooldown_state": {"active": False},
        "market_state_4h": "BULL",
        "trend_state_1h": "LONG_ALLOWED",
        "confirm_state_30m": "LONG_CONFIRM",
        "trigger_state_15m": "LONG",
        "entry_price": 50_000,
        "volatility_state": "NORMAL",
    }
    context.update(overrides)
    return context


def test_direct_risk_ok_outputs_normal_risk_snapshot():
    result = evaluate_risk(base_context())

    assert result.allow_trade is True
    assert result.risk_level == "NORMAL"
    assert result.position_size_factor == 1.0
    assert result.risk_reason == "FULL_CONFIRMATION_AND_RISK_OK"
    assert result.stop_distance == 1_000
    assert result.stop_pct == 0.02
    assert result.metrics_snapshot["symbol"] == "BTCUSDT"
    assert result.metrics_snapshot["risk_level"] == "NORMAL"
    assert result.take_profit_plan[0]["target_price"] == 51_000


def test_probe_uses_quarter_position_factor_without_promotion():
    result = evaluate_risk(base_context(entry_mode="PROBE"))

    assert result.allow_trade is True
    assert result.position_size_factor == 0.25
    assert result.metadata["forbidden_actions"] == RISK_FORBIDDEN_ACTIONS


def test_daily_weekly_drawdown_quality_cooldown_and_exposure_block():
    assert evaluate_risk(base_context(daily_pnl=-600)).risk_reason == "DAILY_LOSS_LIMIT_REACHED"
    assert evaluate_risk(base_context(weekly_pnl=-1300)).risk_reason == "WEEKLY_LOSS_LIMIT_REACHED"
    assert evaluate_risk(base_context(max_drawdown=0.25)).risk_reason == "MAX_DRAWDOWN_LIMIT_REACHED"
    assert evaluate_risk(base_context(quality_flag=False)).risk_reason == "DATA_QUALITY_BLOCKED"
    assert evaluate_risk(base_context(cooldown_state={"active": True})).risk_reason == "COOLDOWN_ACTIVE"
    assert evaluate_risk(base_context(portfolio_exposure=0.80)).risk_reason == "PORTFOLIO_EXPOSURE_LIMIT_REACHED"
    assert evaluate_risk(base_context(symbol_exposure=0.25)).risk_reason == "SYMBOL_EXPOSURE_LIMIT_REACHED"


def test_blocked_result_allows_exit_and_can_require_cooldown():
    result = evaluate_risk(base_context(daily_pnl=-600))

    assert result.allow_trade is False
    assert result.allow_exit is True
    assert result.risk_level == "BLOCKED"
    assert result.cooldown_required is True
    assert result.cooldown_bars == DEFAULT_RISK_LIMITS["normal_cooldown_bars"]


def test_high_volatility_downgrades_to_probe_factor():
    result = evaluate_risk(base_context(volatility_state="HIGH"))

    assert result.allow_trade is True
    assert result.risk_level == "HIGH"
    assert result.position_size_factor == 0.25
    assert result.allow_reduce is True
    assert result.risk_reason == "TREND_OK_BUT_VOLATILITY_HIGH"


def test_extreme_volatility_requires_exit_not_new_trade():
    result = evaluate_risk(base_context(volatility_state="EXTREME"))

    assert result.allow_trade is False
    assert result.allow_exit is True
    assert result.allow_reduce is True
    assert result.risk_level == "EXTREME"


def test_stop_distance_and_atr_gates_block_invalid_risk():
    assert evaluate_risk(base_context(atr=0)).risk_reason == "ATR_UNAVAILABLE"
    assert evaluate_risk(base_context(stop_pct=0.001)).risk_reason == "STOP_DISTANCE_TOO_SMALL"
    assert evaluate_risk(base_context(stop_pct=0.10)).risk_reason == "STOP_DISTANCE_TOO_LARGE"


def test_forced_exit_trigger_has_highest_priority_and_cooldown():
    result = evaluate_risk(base_context(stop_hit=True))

    assert result.allow_trade is False
    assert result.allow_exit is True
    assert result.cooldown_required is True
    assert result.risk_reason == "FORCED_EXIT_REQUIRED"
    assert result.metadata["exit_action"]["action_type"] == "FORCED_STOP"


def test_dataclass_context_is_supported():
    result = evaluate_risk(RiskContext(**base_context()))

    assert result.allow_trade is True
    assert result.risk_level == "NORMAL"


def test_risk_engine_public_contract_constants():
    assert RISK_LEVELS == ["LOW", "NORMAL", "HIGH", "EXTREME", "BLOCKED"]
    assert RISK_DECISION_FLOW == [
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
    assert "quality_flag" in RISK_REQUIRED_INPUTS
    assert "metadata" in RISK_OUTPUT_FIELDS
    assert "risk_reason" in RISK_SNAPSHOT_FIELDS
    assert "submit_or_cancel_orders" in RISK_FORBIDDEN_ACTIONS
""",
    "tests/test_describe_risk_engine.py": """
import json
import subprocess
import sys


def test_describe_risk_engine_outputs_completed_17_sections():
    result = subprocess.run(
        [sys.executable, "scripts/describe_risk_engine.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["engine"] == "risk_engine"
    assert payload["responsibility"] == "pre_trade_risk_gate_and_risk_constraints"
    assert payload["risk_levels"] == ["LOW", "NORMAL", "HIGH", "EXTREME", "BLOCKED"]
    assert payload["decision_flow"][0] == "check_data_quality"
    assert payload["decision_flow"][-1] == "output_risk_result"
    assert "quality_flag" in payload["required_inputs"]
    assert "metrics_snapshot" in payload["output_fields"]
    assert payload["default_limits"]["daily_loss_limit_pct"] == 0.05
    assert payload["score_components"] == [
        "account_risk_score",
        "portfolio_risk_score",
        "symbol_risk_score",
        "volatility_risk_score",
        "cooldown_risk_score",
        "data_quality_risk_score",
    ]
    assert "risk_reason" in payload["snapshot_fields"]
    assert payload["relationships"]["position module"] == "calculates final_notional and final_qty"
    assert payload["forbidden_actions"]["risk layer"][0] == "generate_trade_signal"
    assert "must_not_recalculate_risk" in payload["forbidden_actions"]["execution layer"]
    assert payload["sample"]["direct"]["risk_level"] == "NORMAL"
    assert payload["sample"]["probe"]["position_size_factor"] == 0.25
    assert payload["sample"]["blocked"]["risk_reason"] == "DAILY_LOSS_LIMIT_REACHED"
""",
    "src/execution/execution_engine.py": """
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

from src.execution.live_execution_contract import (
    EXECUTION_FORBIDDEN_ACTIONS,
    EXECUTION_LOG_FIELDS,
    OBSERVABILITY_METRICS,
    ORDER_LIFECYCLE_STATES,
    PROTECTION_MODE_TRIGGERS,
    SUPPORTED_ORDER_TYPES,
    ExecutionInstruction,
    ExecutionResponse,
    build_execution_log,
    build_partial_fill_snapshot,
    normalize_reject_reason,
    should_enter_protection_mode,
    validate_execution_instruction,
)


EXECUTION_ENGINE_RESPONSIBILITIES = [
    "validate_request",
    "build_order_instruction",
    "submit_order",
    "cancel_order",
    "query_order_status",
    "handle_partial_fill",
    "sync_position",
    "record_audit_log",
    "emit_execution_events",
    "surface_errors_upward",
]
EXECUTION_REQUEST_FIELDS = [
    "request_id",
    "event_id",
    "trace_id",
    "correlation_id",
    "symbol",
    "side",
    "order_type",
    "quantity",
    "price",
    "reduce_only",
    "position_side",
    "time_in_force",
    "stop_price",
    "take_profit_price",
    "entry_mode",
    "strategy_state",
    "strategy_version",
    "risk_tag",
    "expected_position_qty",
    "expected_position_side",
    "timestamp",
]
EXECUTION_RESULT_FIELDS = [
    "request_id",
    "event_id",
    "order_id",
    "client_order_id",
    "status",
    "filled_qty",
    "avg_price",
    "executed_notional",
    "commission",
    "latency_ms",
    "reject_reason",
    "raw_response",
    "position_snapshot",
    "risk_snapshot",
    "timestamp",
]
EXECUTION_EVENT_TYPES = [
    "ORDER_SUBMITTED",
    "ORDER_ACKNOWLEDGED",
    "ORDER_FILLED",
    "ORDER_REJECTED",
    "ORDER_CANCELED",
    "POSITION_OPENED",
    "POSITION_REDUCED",
    "POSITION_CLOSED",
    "RISK_BLOCKED",
]
EXECUTION_RETRY_POLICY = {
    "max_retries": 2,
    "retryable_reasons": ["NETWORK_TIMEOUT", "TEMPORARY_UNAVAILABLE", "ORDER_QUERY_DELAY"],
    "non_retryable_reasons": ["PRECISION_ERROR", "MIN_NOTIONAL", "LEVERAGE_ERROR", "REDUCE_ONLY_ERROR", "RISK_BLOCKED"],
}
EXECUTION_PRE_CHECKS = [
    "tradable",
    "trade_window",
    "leverage_ready",
    "quantity_precision",
    "minimum_notional",
    "reduce_only",
    "position_side",
    "current_position_side",
    "account_risk",
    "symbol_cooldown",
]
EXECUTION_FORBIDDEN_ENGINE_ACTIONS = [
    "rewrite_strategy_intent",
    "rewrite_risk_decision",
    "recalculate_position_size",
    "recalculate_stop_or_take_profit",
    "treat_partial_fill_as_new_signal",
    "retry_with_new_strategy_action",
    "swallow_exchange_error",
]
BINANCE_CLIENT_POLICY = "thin injected adapter only; do not modify stable client"


@dataclass(frozen=True)
class ExecutionRequest:
    request_id: str
    event_id: str
    trace_id: str
    correlation_id: str
    symbol: str
    side: str
    order_type: str
    quantity: float
    price: float | None
    reduce_only: bool
    position_side: str
    time_in_force: str | None
    stop_price: float | None
    take_profit_price: float | None
    entry_mode: str
    strategy_state: str
    strategy_version: str
    risk_tag: str
    expected_position_qty: float
    expected_position_side: str
    timestamp: int
    risk_snapshot: Mapping[str, Any] = field(default_factory=dict)
    position_snapshot: Mapping[str, Any] = field(default_factory=dict)

    def to_instruction(self, client_order_id: str) -> ExecutionInstruction:
        return ExecutionInstruction(
            symbol=self.symbol,
            side=self.side,
            order_type=self.order_type,
            quantity=self.quantity,
            price=self.price,
            reduce_only=self.reduce_only,
            position_side=self.position_side,
            time_in_force=self.time_in_force,
            stop_price=self.stop_price,
            take_profit_price=self.take_profit_price,
            client_order_id=client_order_id,
            strategy_event_id=self.event_id,
            strategy_state=self.strategy_state,
            expected_position_side=self.expected_position_side,
            expected_risk_tag=self.risk_tag,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExecutionResult:
    request_id: str
    event_id: str
    order_id: str
    client_order_id: str
    status: str
    filled_qty: float
    avg_price: float
    executed_notional: float
    commission: float
    latency_ms: int
    reject_reason: str
    raw_response: dict[str, Any]
    position_snapshot: dict[str, Any]
    risk_snapshot: dict[str, Any]
    timestamp: int
    lifecycle: list[dict[str, Any]]
    events: list[str]
    audit_log: dict[str, Any]
    protection_mode: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ExecutionEngine:
    def __init__(
        self,
        adapter: Any,
        *,
        tradable_symbols: set[str] | None = None,
        min_notional: float = 5.0,
        quantity_step: float = 0.0,
        max_retries: int = 2,
    ) -> None:
        self.adapter = adapter
        self.tradable_symbols = tradable_symbols
        self.min_notional = min_notional
        self.quantity_step = quantity_step
        self.max_retries = max_retries
        self._results_by_idempotency_key: dict[str, ExecutionResult] = {}
        self.lifecycle_log: list[dict[str, Any]] = []
        self.audit_logs: list[dict[str, Any]] = []
        self.consecutive_rejects = 0
        self.consecutive_sync_failures = 0
        self.consecutive_protection_order_failures = 0

    def submit_order(self, request: ExecutionRequest) -> ExecutionResult:
        idempotency_key = build_execution_idempotency_key(request)
        if idempotency_key in self._results_by_idempotency_key:
            return self._results_by_idempotency_key[idempotency_key]

        client_order_id = idempotency_key
        instruction = request.to_instruction(client_order_id)
        lifecycle = [self._lifecycle(client_order_id, "created", request.timestamp, "request accepted")]
        validation = validate_execution_instruction(
            instruction,
            tradable=_is_tradable(request.symbol, self.tradable_symbols),
            min_notional=self.min_notional,
            quantity_step=self.quantity_step,
            current_position_side=request.position_snapshot.get("position_side"),
            account_risk_allows=bool(request.risk_snapshot.get("allow_trade", True)),
            symbol_cooldown_active=bool(request.risk_snapshot.get("symbol_cooldown_active", False)),
        )
        if not validation.passed:
            lifecycle.append(self._lifecycle(client_order_id, "rejected", request.timestamp, validation.reason))
            result = self._result_from_response(
                request,
                instruction,
                ExecutionResponse(
                    order_id="",
                    client_order_id=client_order_id,
                    status="rejected",
                    filled_qty=0.0,
                    avg_price=0.0,
                    commission=0.0,
                    executed_notional=0.0,
                    reject_reason=validation.reason,
                    raw_response={"validation": validation.reason},
                    latency_ms=0,
                    ts=request.timestamp,
                ),
                lifecycle,
                ["ORDER_REJECTED"],
                retry_count=0,
            )
            self.consecutive_rejects += 1
            self._results_by_idempotency_key[idempotency_key] = result
            return result

        lifecycle.append(self._lifecycle(client_order_id, "validated", request.timestamp, "validated"))
        lifecycle.append(self._lifecycle(client_order_id, "submitted", request.timestamp, "submitted to adapter"))
        response, retry_count = self._submit_with_retry(instruction, request.timestamp)
        status = normalize_order_status(response.status)
        lifecycle.append(self._lifecycle(client_order_id, "acknowledged", response.ts, "adapter response received"))
        if status in {"partially_filled", "filled", "rejected"}:
            lifecycle.append(self._lifecycle(client_order_id, status, response.ts, status))

        events = ["ORDER_SUBMITTED"]
        if status == "filled":
            events.extend(["ORDER_FILLED", _position_event(request)])
            self.consecutive_rejects = 0
        elif status == "partially_filled":
            events.append("ORDER_ACKNOWLEDGED")
        elif status == "rejected":
            events.append("ORDER_REJECTED")
            self.consecutive_rejects += 1
        else:
            events.append("ORDER_ACKNOWLEDGED")

        result = self._result_from_response(request, instruction, response, lifecycle, events, retry_count=retry_count)
        self._results_by_idempotency_key[idempotency_key] = result
        return result

    def cancel_order(self, request_id: str, symbol: str, order_id: str | int, timestamp: int = 0) -> ExecutionResult:
        try:
            raw = self.adapter.cancel(symbol, order_id)
            status = normalize_order_status(str(raw.get("status", "canceled")))
            reject_reason = ""
        except Exception as exc:
            raw = {"error": str(exc)}
            status = "rejected"
            reject_reason = normalize_reject_reason(str(exc))
            self.consecutive_rejects += 1
        client_order_id = str(raw.get("client_order_id") or raw.get("clientOrderId") or f"cancel:{symbol}:{order_id}")
        lifecycle = [
            self._lifecycle(client_order_id, "created", timestamp, "cancel requested"),
            self._lifecycle(client_order_id, status if status == "canceled" else "rejected", timestamp, "cancel result"),
        ]
        instruction = ExecutionInstruction(
            symbol=symbol,
            side=str(raw.get("side", "SELL")),
            order_type=str(raw.get("order_type", "MARKET")),
            quantity=float(raw.get("quantity", 0.0)),
            price=None,
            reduce_only=True,
            position_side=str(raw.get("position_side", "BOTH")),
            time_in_force=None,
            stop_price=None,
            take_profit_price=None,
            client_order_id=client_order_id,
            strategy_event_id=request_id,
            strategy_state="CANCEL",
            expected_position_side=str(raw.get("position_side", "BOTH")),
            expected_risk_tag="cancel",
        )
        response = ExecutionResponse(
            order_id=str(order_id),
            client_order_id=client_order_id,
            status=status,
            filled_qty=float(raw.get("filled_qty", 0.0)),
            avg_price=float(raw.get("avg_price", 0.0)),
            commission=float(raw.get("commission", 0.0)),
            executed_notional=float(raw.get("executed_notional", 0.0)),
            reject_reason=reject_reason,
            raw_response=raw,
            latency_ms=int(raw.get("latency_ms", 0)),
            ts=timestamp,
        )
        return self._result_from_response(
            ExecutionRequest(
                request_id=request_id,
                event_id=request_id,
                trace_id=request_id,
                correlation_id=request_id,
                symbol=symbol,
                side=instruction.side,
                order_type=instruction.order_type,
                quantity=instruction.quantity,
                price=None,
                reduce_only=True,
                position_side=instruction.position_side,
                time_in_force=None,
                stop_price=None,
                take_profit_price=None,
                entry_mode="NONE",
                strategy_state="CANCEL",
                strategy_version="",
                risk_tag="cancel",
                expected_position_qty=0.0,
                expected_position_side=instruction.expected_position_side,
                timestamp=timestamp,
            ),
            instruction,
            response,
            lifecycle,
            ["ORDER_CANCELED"] if status == "canceled" else ["ORDER_REJECTED"],
            retry_count=0,
        )

    def sync_position(self, symbol: str | None = None) -> dict[str, Any]:
        try:
            snapshot = self.adapter.sync(symbol)
            self.consecutive_sync_failures = 0
            return {"passed": True, "snapshot": snapshot, "protection_mode": False, "reason": "synced"}
        except Exception as exc:
            self.consecutive_sync_failures += 1
            protection = should_enter_protection_mode(consecutive_sync_failures=self.consecutive_sync_failures)
            return {"passed": False, "snapshot": {}, "protection_mode": protection.passed, "reason": str(exc)}

    def _submit_with_retry(self, instruction: ExecutionInstruction, timestamp: int) -> tuple[ExecutionResponse, int]:
        retry_count = 0
        while True:
            try:
                raw = self.adapter.submit(instruction)
                return _response_from_raw(instruction, raw, timestamp), retry_count
            except Exception as exc:
                reason = normalize_reject_reason(str(exc))
                if reason not in EXECUTION_RETRY_POLICY["retryable_reasons"] or retry_count >= self.max_retries:
                    return (
                        ExecutionResponse(
                            order_id="",
                            client_order_id=instruction.client_order_id,
                            status="rejected",
                            filled_qty=0.0,
                            avg_price=0.0,
                            commission=0.0,
                            executed_notional=0.0,
                            reject_reason=reason,
                            raw_response={"error": str(exc)},
                            latency_ms=0,
                            ts=timestamp,
                        ),
                        retry_count,
                    )
                retry_count += 1

    def _result_from_response(
        self,
        request: ExecutionRequest,
        instruction: ExecutionInstruction,
        response: ExecutionResponse,
        lifecycle: list[dict[str, Any]],
        events: list[str],
        *,
        retry_count: int,
    ) -> ExecutionResult:
        audit_log = build_execution_log(instruction, response, action="submit_order", module="execution_engine")
        self.audit_logs.append(audit_log)
        protection = should_enter_protection_mode(consecutive_rejects=self.consecutive_rejects)
        status = normalize_order_status(response.status)
        metadata: dict[str, Any] = {
            "retry_count": retry_count,
            "idempotency_key": instruction.client_order_id,
            "forbidden_actions": EXECUTION_FORBIDDEN_ENGINE_ACTIONS,
            "partial_fill": None,
        }
        if status == "partially_filled":
            metadata["partial_fill"] = build_partial_fill_snapshot(
                order_qty=request.quantity,
                filled_qty=response.filled_qty,
                avg_price=response.avg_price,
                client_order_id=instruction.client_order_id,
            )
        return ExecutionResult(
            request_id=request.request_id,
            event_id=request.event_id,
            order_id=response.order_id,
            client_order_id=instruction.client_order_id,
            status=status,
            filled_qty=response.filled_qty,
            avg_price=response.avg_price,
            executed_notional=response.executed_notional,
            commission=response.commission,
            latency_ms=response.latency_ms,
            reject_reason=response.reject_reason,
            raw_response=response.raw_response,
            position_snapshot=dict(request.position_snapshot),
            risk_snapshot=dict(request.risk_snapshot),
            timestamp=response.ts,
            lifecycle=lifecycle,
            events=events,
            audit_log=audit_log,
            protection_mode=protection.passed,
            metadata=metadata,
        )

    def _lifecycle(self, client_order_id: str, state: str, ts: int, reason: str) -> dict[str, Any]:
        if state not in ORDER_LIFECYCLE_STATES:
            raise ValueError("unknown lifecycle state")
        row = {"client_order_id": client_order_id, "state": state, "ts": ts, "reason": reason}
        self.lifecycle_log.append(row)
        return row


def build_execution_idempotency_key(request: ExecutionRequest) -> str:
    return ":".join(
        [
            request.symbol.strip().upper(),
            request.event_id,
            request.strategy_state,
            request.side.strip().upper(),
            request.entry_mode.strip().upper(),
        ]
    )


def normalize_order_status(status: str) -> str:
    value = str(status).strip().lower()
    aliases = {
        "new": "acknowledged",
        "acknowledged": "acknowledged",
        "submitted": "submitted",
        "partially_filled": "partially_filled",
        "partial": "partially_filled",
        "filled": "filled",
        "canceled": "canceled",
        "cancelled": "canceled",
        "rejected": "rejected",
        "expired": "expired",
    }
    return aliases.get(value, "rejected")


def _response_from_raw(instruction: ExecutionInstruction, raw: Mapping[str, Any], timestamp: int) -> ExecutionResponse:
    status = normalize_order_status(str(raw.get("status", "acknowledged")))
    filled_qty = float(raw.get("filled_qty", raw.get("executedQty", 0.0)))
    avg_price = float(raw.get("avg_price", raw.get("avgPrice", raw.get("price", 0.0)) or 0.0))
    executed_notional = float(raw.get("executed_notional", filled_qty * avg_price))
    reject_reason = str(raw.get("reject_reason", ""))
    if status == "rejected" and not reject_reason:
        reject_reason = normalize_reject_reason(str(raw.get("message", raw.get("error", "exchange rejected"))))
    return ExecutionResponse(
        order_id=str(raw.get("order_id", raw.get("orderId", ""))),
        client_order_id=instruction.client_order_id,
        status=status,
        filled_qty=filled_qty,
        avg_price=avg_price,
        commission=float(raw.get("commission", 0.0)),
        executed_notional=executed_notional,
        reject_reason=reject_reason,
        raw_response=dict(raw),
        latency_ms=int(raw.get("latency_ms", 0)),
        ts=int(raw.get("timestamp", timestamp)),
    )


def _is_tradable(symbol: str, tradable_symbols: set[str] | None) -> bool:
    if tradable_symbols is None:
        return True
    return symbol.strip().upper() in tradable_symbols


def _position_event(request: ExecutionRequest) -> str:
    if request.reduce_only:
        return "POSITION_REDUCED"
    return "POSITION_OPENED"
""",
    "scripts/describe_execution_engine.py": """
from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.execution.execution_engine import (
    BINANCE_CLIENT_POLICY,
    EXECUTION_ENGINE_RESPONSIBILITIES,
    EXECUTION_EVENT_TYPES,
    EXECUTION_FORBIDDEN_ENGINE_ACTIONS,
    EXECUTION_PRE_CHECKS,
    EXECUTION_REQUEST_FIELDS,
    EXECUTION_RESULT_FIELDS,
    EXECUTION_RETRY_POLICY,
    ExecutionEngine,
    ExecutionRequest,
)
from src.execution.live_execution_contract import (
    EXECUTION_LOG_FIELDS,
    OBSERVABILITY_METRICS,
    ORDER_LIFECYCLE_STATES,
    PROTECTION_MODE_TRIGGERS,
    SUPPORTED_ORDER_TYPES,
)


class _DescribeAdapter:
    def submit(self, instruction):
        return {"order_id": "ord-1", "status": "filled", "filled_qty": 0.1, "avg_price": 50_000}

    def cancel(self, symbol, order_id):
        return {"status": "canceled", "client_order_id": f"cancel:{symbol}:{order_id}"}

    def sync(self, symbol=None):
        return {"position": {"symbol": symbol, "qty": 0.1}}


def _sample_result():
    request = ExecutionRequest(
        request_id="req-1",
        event_id="evt-1",
        trace_id="trace-1",
        correlation_id="corr-1",
        symbol="BTCUSDT",
        side="BUY",
        order_type="MARKET",
        quantity=0.1,
        price=50_000,
        reduce_only=False,
        position_side="LONG",
        time_in_force=None,
        stop_price=49_000,
        take_profit_price=52_000,
        entry_mode="DIRECT",
        strategy_state="DIRECT_LONG",
        strategy_version="v1",
        risk_tag="entry",
        expected_position_qty=0.1,
        expected_position_side="LONG",
        timestamp=1,
        risk_snapshot={"allow_trade": True},
        position_snapshot={"position_side": "LONG"},
    )
    return ExecutionEngine(_DescribeAdapter()).submit_order(request).to_dict()


def main() -> None:
    payload = {
        "engine": "execution_engine",
        "responsibility": "execute_already_confirmed_trade_actions",
        "responsibilities": EXECUTION_ENGINE_RESPONSIBILITIES,
        "request_fields": EXECUTION_REQUEST_FIELDS,
        "result_fields": EXECUTION_RESULT_FIELDS,
        "order_lifecycle_states": ORDER_LIFECYCLE_STATES,
        "supported_order_types": SUPPORTED_ORDER_TYPES,
        "pre_execution_checks": EXECUTION_PRE_CHECKS,
        "idempotency_key": "symbol + event_id + strategy_state + side + entry_mode",
        "retry_policy": EXECUTION_RETRY_POLICY,
        "protection_mode_triggers": PROTECTION_MODE_TRIGGERS,
        "event_types": EXECUTION_EVENT_TYPES,
        "log_fields": EXECUTION_LOG_FIELDS,
        "observability_metrics": OBSERVABILITY_METRICS,
        "forbidden_actions": EXECUTION_FORBIDDEN_ENGINE_ACTIONS,
        "binance_client_policy": BINANCE_CLIENT_POLICY,
        "sample_result": _sample_result(),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
""",
    "tests/test_execution_engine.py": """
import pytest

from src.execution.execution_engine import (
    BINANCE_CLIENT_POLICY,
    EXECUTION_ENGINE_RESPONSIBILITIES,
    EXECUTION_EVENT_TYPES,
    EXECUTION_FORBIDDEN_ENGINE_ACTIONS,
    EXECUTION_PRE_CHECKS,
    EXECUTION_REQUEST_FIELDS,
    EXECUTION_RESULT_FIELDS,
    EXECUTION_RETRY_POLICY,
    ExecutionEngine,
    ExecutionRequest,
    build_execution_idempotency_key,
    normalize_order_status,
)


class FakeAdapter:
    def __init__(self, submit_response=None, submit_errors=None, cancel_response=None, sync_response=None, sync_error=None):
        self.submit_response = submit_response or {
            "order_id": "ord-1",
            "status": "filled",
            "filled_qty": 0.1,
            "avg_price": 50_000,
            "commission": 1,
            "latency_ms": 12,
        }
        self.submit_errors = list(submit_errors or [])
        self.cancel_response = cancel_response or {"status": "canceled", "client_order_id": "cli-cancel"}
        self.sync_response = sync_response or {"position": {"symbol": "BTCUSDT", "qty": 0.1}}
        self.sync_error = sync_error
        self.submit_calls = 0
        self.cancel_calls = 0
        self.sync_calls = 0

    def submit(self, instruction):
        self.submit_calls += 1
        if self.submit_errors:
            raise RuntimeError(self.submit_errors.pop(0))
        return self.submit_response

    def cancel(self, symbol, order_id):
        self.cancel_calls += 1
        if isinstance(self.cancel_response, Exception):
            raise self.cancel_response
        return self.cancel_response

    def sync(self, symbol=None):
        self.sync_calls += 1
        if self.sync_error is not None:
            raise RuntimeError(self.sync_error)
        return self.sync_response


def valid_request(**overrides):
    values = {
        "request_id": "req-1",
        "event_id": "evt-1",
        "trace_id": "trace-1",
        "correlation_id": "corr-1",
        "symbol": "BTCUSDT",
        "side": "BUY",
        "order_type": "MARKET",
        "quantity": 0.1,
        "price": 50_000,
        "reduce_only": False,
        "position_side": "LONG",
        "time_in_force": None,
        "stop_price": 49_000,
        "take_profit_price": 52_000,
        "entry_mode": "DIRECT",
        "strategy_state": "DIRECT_LONG",
        "strategy_version": "v1",
        "risk_tag": "entry",
        "expected_position_qty": 0.1,
        "expected_position_side": "LONG",
        "timestamp": 1_700_000_000,
        "risk_snapshot": {"allow_trade": True},
        "position_snapshot": {"position_side": "LONG"},
    }
    values.update(overrides)
    return ExecutionRequest(**values)


def test_submit_market_order_records_result_lifecycle_and_events():
    engine = ExecutionEngine(FakeAdapter())
    result = engine.submit_order(valid_request())

    assert result.status == "filled"
    assert result.client_order_id == "BTCUSDT:evt-1:DIRECT_LONG:BUY:DIRECT"
    assert [item["state"] for item in result.lifecycle] == [
        "created",
        "validated",
        "submitted",
        "acknowledged",
        "filled",
    ]
    assert result.events == ["ORDER_SUBMITTED", "ORDER_FILLED", "POSITION_OPENED"]
    assert result.audit_log["module"] == "execution_engine"
    assert result.audit_log["raw_response"]["order_id"] == "ord-1"


def test_idempotent_duplicate_request_returns_cached_result():
    adapter = FakeAdapter()
    engine = ExecutionEngine(adapter)
    first = engine.submit_order(valid_request())
    second = engine.submit_order(valid_request())

    assert first is second
    assert adapter.submit_calls == 1


def test_validation_rejects_without_adapter_submit():
    adapter = FakeAdapter()
    engine = ExecutionEngine(adapter)
    result = engine.submit_order(valid_request(quantity=0))

    assert result.status == "rejected"
    assert result.reject_reason == "quantity must be positive"
    assert result.events == ["ORDER_REJECTED"]
    assert adapter.submit_calls == 0


def test_partial_fill_is_reported_without_new_signal_or_auto_fill():
    adapter = FakeAdapter(
        submit_response={"order_id": "ord-2", "status": "partially_filled", "filled_qty": 0.04, "avg_price": 50_000}
    )
    engine = ExecutionEngine(adapter)
    result = engine.submit_order(valid_request())

    assert result.status == "partially_filled"
    assert result.metadata["partial_fill"] == {
        "client_order_id": "BTCUSDT:evt-1:DIRECT_LONG:BUY:DIRECT",
        "order_qty": 0.1,
        "filled_qty": 0.04,
        "remaining_qty": 0.060000000000000005,
        "avg_price": 50_000.0,
        "status": "partially_filled",
    }
    assert result.events == ["ORDER_SUBMITTED", "ORDER_ACKNOWLEDGED"]


def test_rejected_exchange_response_is_normalized_and_counted():
    adapter = FakeAdapter(submit_response={"status": "rejected", "message": "-2019 margin insufficient"})
    engine = ExecutionEngine(adapter)
    result = engine.submit_order(valid_request())

    assert result.status == "rejected"
    assert result.reject_reason == "INSUFFICIENT_MARGIN"
    assert result.events == ["ORDER_SUBMITTED", "ORDER_REJECTED"]


def test_cancel_order_success_and_failure_paths_are_explicit():
    success_engine = ExecutionEngine(FakeAdapter(cancel_response={"status": "canceled", "client_order_id": "cli-1"}))
    success = success_engine.cancel_order("req-cancel", "BTCUSDT", "ord-1", timestamp=2)
    assert success.status == "canceled"
    assert success.events == ["ORDER_CANCELED"]

    failure_engine = ExecutionEngine(FakeAdapter(cancel_response=RuntimeError("precision error")))
    failure = failure_engine.cancel_order("req-cancel", "BTCUSDT", "ord-1", timestamp=2)
    assert failure.status == "rejected"
    assert failure.reject_reason == "PRECISION_ERROR"
    assert failure.events == ["ORDER_REJECTED"]


def test_sync_failure_enters_protection_mode_after_threshold():
    engine = ExecutionEngine(FakeAdapter(sync_error="exchange unavailable"))

    assert engine.sync_position("BTCUSDT")["protection_mode"] is False
    assert engine.sync_position("BTCUSDT")["protection_mode"] is False
    third = engine.sync_position("BTCUSDT")
    assert third["passed"] is False
    assert third["protection_mode"] is True


def test_retry_reuses_same_instruction_for_retryable_error():
    adapter = FakeAdapter(submit_errors=["timeout waiting exchange"])
    engine = ExecutionEngine(adapter)
    result = engine.submit_order(valid_request())

    assert result.status == "filled"
    assert result.metadata["retry_count"] == 1
    assert adapter.submit_calls == 2
    assert result.client_order_id == "BTCUSDT:evt-1:DIRECT_LONG:BUY:DIRECT"


def test_non_retryable_error_rejects_without_changing_intent():
    adapter = FakeAdapter(submit_errors=["precision over maximum"])
    engine = ExecutionEngine(adapter)
    result = engine.submit_order(valid_request())

    assert result.status == "rejected"
    assert result.reject_reason == "PRECISION_ERROR"
    assert result.metadata["retry_count"] == 0
    assert adapter.submit_calls == 1


def test_execution_engine_public_contract_constants():
    assert EXECUTION_ENGINE_RESPONSIBILITIES[0] == "validate_request"
    assert "request_id" in EXECUTION_REQUEST_FIELDS
    assert "raw_response" in EXECUTION_RESULT_FIELDS
    assert EXECUTION_EVENT_TYPES[:3] == ["ORDER_SUBMITTED", "ORDER_ACKNOWLEDGED", "ORDER_FILLED"]
    assert EXECUTION_PRE_CHECKS[-1] == "symbol_cooldown"
    assert EXECUTION_RETRY_POLICY["max_retries"] == 2
    assert "rewrite_strategy_intent" in EXECUTION_FORBIDDEN_ENGINE_ACTIONS
    assert BINANCE_CLIENT_POLICY == "thin injected adapter only; do not modify stable client"
    assert build_execution_idempotency_key(valid_request()) == "BTCUSDT:evt-1:DIRECT_LONG:BUY:DIRECT"
    assert normalize_order_status("cancelled") == "canceled"


def test_unknown_lifecycle_status_is_not_accepted():
    engine = ExecutionEngine(FakeAdapter(submit_response={"status": "mystery"}))
    result = engine.submit_order(valid_request())

    assert result.status == "rejected"
    assert result.events == ["ORDER_SUBMITTED", "ORDER_REJECTED"]


def test_no_src_api_binance_import_in_execution_engine():
    import src.execution.execution_engine as execution_engine

    assert "src.api.binance_client" not in str(execution_engine.__dict__)
""",
    "tests/test_describe_execution_engine.py": """
import json
import subprocess
import sys


def test_describe_execution_engine_outputs_completed_18_sections():
    result = subprocess.run(
        [sys.executable, "scripts/describe_execution_engine.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["engine"] == "execution_engine"
    assert payload["responsibility"] == "execute_already_confirmed_trade_actions"
    assert payload["responsibilities"][0] == "validate_request"
    assert "request_id" in payload["request_fields"]
    assert "raw_response" in payload["result_fields"]
    assert payload["order_lifecycle_states"][0] == "created"
    assert payload["supported_order_types"] == ["MARKET", "LIMIT", "IOC", "STOP_MARKET", "TAKE_PROFIT_MARKET"]
    assert payload["pre_execution_checks"][-1] == "symbol_cooldown"
    assert payload["idempotency_key"] == "symbol + event_id + strategy_state + side + entry_mode"
    assert payload["retry_policy"]["max_retries"] == 2
    assert payload["protection_mode_triggers"][-1] == "exchange_unavailable"
    assert "ORDER_FILLED" in payload["event_types"]
    assert "latency_ms" in payload["log_fields"]
    assert "order_success_rate" in payload["observability_metrics"]
    assert "rewrite_strategy_intent" in payload["forbidden_actions"]
    assert payload["binance_client_policy"] == "thin injected adapter only; do not modify stable client"
    assert payload["sample_result"]["status"] == "filled"
""",
    "scripts/describe_backtest_engine.py": """
from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.backtest.engine import (
    BACKTEST_ANALYSIS_DIMENSIONS,
    BACKTEST_ARTIFACTS,
    BACKTEST_FAILURE_SAMPLE_TYPES,
    BACKTEST_FILL_MODELS,
    BACKTEST_FORBIDDEN_ACTIONS,
    BACKTEST_REQUIRED_EVENTS,
    BACKTEST_REQUIRED_INPUTS,
    BACKTEST_RESULT_FIELDS,
    BACKTEST_STEP_ORDER,
)


def main() -> None:
    payload = {
        "engine": "backtest_engine",
        "request_fields": BACKTEST_REQUIRED_INPUTS,
        "result_fields": BACKTEST_RESULT_FIELDS,
        "step_order": BACKTEST_STEP_ORDER,
        "fill_models": BACKTEST_FILL_MODELS,
        "required_events": BACKTEST_REQUIRED_EVENTS,
        "artifacts": BACKTEST_ARTIFACTS,
        "analysis_dimensions": BACKTEST_ANALYSIS_DIMENSIONS,
        "failure_sample_types": BACKTEST_FAILURE_SAMPLE_TYPES,
        "required_costs": ["fee", "slippage", "funding"],
        "forbidden_actions": BACKTEST_FORBIDDEN_ACTIONS,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
""",
    "tests/test_backtest_engine.py": """
from src.backtest.engine import (
    BACKTEST_ARTIFACTS,
    BACKTEST_FILL_MODELS,
    BACKTEST_FORBIDDEN_ACTIONS,
    BACKTEST_REQUIRED_INPUTS,
    BACKTEST_STEP_ORDER,
    BacktestRequest,
    build_artifact_manifest,
)


def test_backtest_engine_19_contract_template():
    assert BACKTEST_REQUIRED_INPUTS[0] == "run_id"
    assert BACKTEST_STEP_ORDER[4] == "check_exits"
    assert BACKTEST_FILL_MODELS == ["NEXT_BAR_OPEN", "TRIGGER_PRICE", "CONSERVATIVE_LIMIT_FILL"]
    assert "use_future_bar" in BACKTEST_FORBIDDEN_ACTIONS


def test_backtest_artifact_manifest_template():
    request = BacktestRequest(
        run_id="run-1",
        strategy_name="ai300",
        strategy_version="v1",
        config_version="cfg-1",
        data_version="data-1",
        symbols=["BTCUSDT"],
        timeframes=["15m"],
        start_time=0,
        end_time=900,
        initial_capital=10_000,
    )
    manifest = build_artifact_manifest(request)
    assert set(manifest) == set(BACKTEST_ARTIFACTS)
""",
    "tests/test_describe_backtest_engine.py": """
import json
import subprocess
import sys


def test_describe_backtest_engine_template():
    result = subprocess.run(
        [sys.executable, "scripts/describe_backtest_engine.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    assert payload["engine"] == "backtest_engine"
    assert payload["request_fields"][0] == "run_id"
    assert payload["step_order"][4] == "check_exits"
    assert "funding" in payload["required_costs"]
""",
    "src/deployment/__init__.py": '"""Deployment architecture contracts and safety checks."""',
    "src/deployment/deployment_architecture.py": """
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


DEPLOYMENT_ENVIRONMENTS = ["development", "staging", "production"]
DEPLOYMENT_LAYERS = ["data layer", "indicator layer", "context layer", "signal layer", "risk layer", "execution layer", "portfolio layer", "backtest layer", "reporting layer", "monitoring layer"]
DEPLOYMENT_PROCESS_UNITS = ["market data daemon", "strategy engine", "execution engine", "risk supervisor", "portfolio sync daemon", "backtest runner", "report generator", "health monitor"]
DEPLOYMENT_TARGETS = ["full_strategy", "single_symbol_strategy", "backtest_job", "daily_report_job", "health_check", "market_data_sync", "position_sync", "execution_listener", "event_replay", "failure_recovery"]
CONFIG_FILES = ["strategy.yaml", "risk.yaml", "execution.yaml", "universe.yaml", "logging.yaml", "backtest.yaml", "database.yaml", "monitoring.yaml"]
SECRET_POLICY = {"allowed": ["environment_variables", "secret_file", "secret_manager", "container_secret_mount"], "forbidden": ["code_repository", "plain_config_file", "logs", "reports"]}
LOG_DIRECTORIES = ["logs/strategy", "logs/risk", "logs/execution", "logs/backtest", "logs/audit", "logs/system"]
STARTUP_SEQUENCE = ["load_config", "validate_config_version", "connect_database", "load_universe", "fetch_latest_market_data", "sync_account_and_positions", "check_protection_orders", "start_event_bus", "start_monitoring", "start_strategy_main_loop", "enter_trading_runtime"]
SHUTDOWN_SEQUENCE = ["stop_accepting_new_signals", "stop_new_entries", "keep_risk_and_exit_capability", "stop_market_data_consumption", "persist_current_state", "clean_temporary_resources", "close_connections", "write_shutdown_log"]
RECOVERY_STATE_FIELDS = ["current_state_machine_state", "current_positions", "open_orders", "cooldown_state", "risk_snapshot", "strategy_version", "config_version"]
FAILURE_MODES = ["data_source_unavailable", "market_data_delayed", "missing_data", "exchange_rejected", "order_submit_failed", "protection_order_failed", "position_sync_failed", "database_write_failed", "config_load_failed", "event_bus_blocked", "risk_threshold_invalid", "state_machine_inconsistent"]
PROTECTION_MODE_ALLOWED_ACTIONS = ["block_new_entries", "allow_reductions", "allow_stop_loss_exit", "allow_position_sync", "allow_logs_and_audit", "allow_manual_inspection"]
PROTECTION_MODE_TRIGGERS = ["consecutive_rejects", "abnormal_position_state", "risk_abnormal", "exchange_unavailable", "data_abnormal", "unknown_order_state", "database_not_writable", "event_bus_unavailable", "consecutive_sync_failures", "consecutive_protection_failures"]
MONITORING_METRICS = ["market_data_latency", "strategy_loop_latency", "order_submit_latency", "fill_report_latency", "position_sync_failures", "protection_order_failures", "reject_count", "risk_block_count", "missing_data_count", "system_exception_count"]
OBSERVABILITY_QUESTIONS = ["is_system_trading", "current_positions", "why_not_trading", "is_risk_safe", "current_order_status", "is_in_cooldown", "is_in_protection_mode", "latest_exception"]
CONTAINER_SERVICES = ["strategy-app", "backtest-runner", "database", "monitoring", "report-worker"]
HEALTH_CHECKS = ["database_connection", "exchange_connection", "market_data_update", "event_bus", "position_sync", "risk_state", "config_state", "critical_processes"]
HEALTH_CHECK_TYPES = ["liveness", "readiness", "startup"]
VERSION_SNAPSHOT_FIELDS = ["code_version", "strategy_version", "risk_version", "config_version", "data_version", "backtest_version", "report_version"]
RELEASE_GATES = ["local_unit_tests", "backtest_passed", "staging_validation_passed", "config_validation_passed", "monitoring_connected", "production_canary", "small_scale_live_validation", "full_rollout_approval"]
ROLLBACK_REQUIREMENTS = ["code_version", "config_version", "migration_version", "strategy_version", "risk_version"]
CANARY_STAGES = ["single_symbol", "small_symbol_set", "expanded_universe", "expanded_position_size"]
CANARY_OBSERVATION_METRICS = ["fill_rate", "reject_rate", "protection_order_success_rate", "risk_block_rate", "state_consistency", "latency", "drawdown"]
DEPLOYMENT_TEST_REQUIREMENTS = ["config_load_test", "startup_test", "shutdown_test", "restart_recovery_test", "database_recovery_test", "protection_mode_test", "alert_test", "container_restart_test", "canary_release_test", "rollback_test"]
DEPLOYMENT_FORBIDDEN_PATTERNS = ["shared_development_production_config", "direct_online_trial_after_code_change", "deployment_without_recovery", "live_without_protection_mode", "persistent_runtime_without_monitoring", "memory_as_only_source_of_truth", "execution_layer_depends_on_temp_script", "backtest_pollutes_live_database", "direct_development_to_production"]
IMPLEMENTATION_ORDER = ["data layer", "indicator layer", "context layer", "signal layer", "risk layer", "execution layer", "backtest layer", "reporting layer", "monitoring layer", "live rollout"]
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
""",
    "scripts/describe_deployment_architecture.py": """
from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.deployment.deployment_architecture import (
    BINANCE_CLIENT_POLICY,
    DEPLOYMENT_ENVIRONMENTS,
    DEPLOYMENT_FORBIDDEN_PATTERNS,
    HEALTH_CHECK_TYPES,
    PROTECTION_MODE_TRIGGERS,
    RELEASE_GATES,
    ROLLBACK_REQUIREMENTS,
    SHUTDOWN_SEQUENCE,
    STARTUP_SEQUENCE,
)


def main() -> None:
    payload = {
        "architecture": "deployment_architecture",
        "environments": DEPLOYMENT_ENVIRONMENTS,
        "startup_sequence": STARTUP_SEQUENCE,
        "shutdown_sequence": SHUTDOWN_SEQUENCE,
        "protection_mode_triggers": PROTECTION_MODE_TRIGGERS,
        "health_check_types": HEALTH_CHECK_TYPES,
        "release_gates": RELEASE_GATES,
        "rollback_requirements": ROLLBACK_REQUIREMENTS,
        "forbidden_patterns": DEPLOYMENT_FORBIDDEN_PATTERNS,
        "binance_client_policy": BINANCE_CLIENT_POLICY,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
""",
    "tests/test_deployment_architecture.py": """
from src.deployment.deployment_architecture import (
    DEPLOYMENT_ENVIRONMENTS,
    PROTECTION_MODE_TRIGGERS,
    STARTUP_SEQUENCE,
    DeploymentPlan,
)


def test_deployment_architecture_template_contract():
    assert DEPLOYMENT_ENVIRONMENTS == ["development", "staging", "production"]
    assert STARTUP_SEQUENCE[0] == "load_config"
    assert "database_not_writable" in PROTECTION_MODE_TRIGGERS
    assert DeploymentPlan.__name__ == "DeploymentPlan"
""",
    "tests/test_describe_deployment_architecture.py": """
import json
import subprocess
import sys


def test_describe_deployment_architecture_template():
    result = subprocess.run(
        [sys.executable, "scripts/describe_deployment_architecture.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    assert payload["architecture"] == "deployment_architecture"
    assert payload["environments"] == ["development", "staging", "production"]
    assert "database_not_writable" in payload["protection_mode_triggers"]
""",

}


def main() -> None:
    for path, content in FILES.items():
        write_file(path, content)
    print(f"Scaffold complete: {len(FILES)} file templates checked.")


if __name__ == "__main__":
    main()




