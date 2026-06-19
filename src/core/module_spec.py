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
