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
