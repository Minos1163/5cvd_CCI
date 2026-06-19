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
    return "\n".join(lines) + "\n"


def report_filename(period: str) -> str:
    value = period.strip().lower()
    if value not in REPORT_FILENAMES:
        raise ValueError("period must be daily, weekly, or monthly")
    return REPORT_FILENAMES[value]
