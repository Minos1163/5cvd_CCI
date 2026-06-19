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
    assert rendered.endswith("\n")


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
