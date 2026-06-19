import json
import subprocess
import sys


def test_describe_backtest_engine_outputs_completed_19_sections():
    completed = subprocess.run(
        [sys.executable, "scripts/describe_backtest_engine.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["engine"] == "backtest_engine"
    assert payload["request_fields"][0] == "run_id"
    assert payload["result_fields"][0] == "run_id"
    assert payload["step_order"][4] == "check_exits"
    assert payload["fill_models"] == ["NEXT_BAR_OPEN", "TRIGGER_PRICE", "CONSERVATIVE_LIMIT_FILL"]
    assert "funding" in payload["required_costs"]
    assert "use_future_bar" in payload["forbidden_actions"]
    assert "backtest_result.json" in payload["artifacts"]
    assert payload["sample_result"]["status"] == "completed"
    assert payload["sample_result"]["trade_count"] >= 1
