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
