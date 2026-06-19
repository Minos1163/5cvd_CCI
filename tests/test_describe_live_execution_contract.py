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
