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
