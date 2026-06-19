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
