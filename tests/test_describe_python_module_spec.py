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
    assert "observability" in payload["final_module_structure"]
    assert "deployment" in payload["final_module_structure"]
    assert payload["allowed_dependency_chain"] == [
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
    assert payload["base_interfaces"]["BaseExecution"] == ["submit", "cancel", "sync"]
    assert payload["context_states"] == ["BULL", "BEAR", "NEUTRAL"]
    assert payload["event_types"] == ["SIGNAL_CREATED", "ORDER_FILLED", "STOP_HIT", "TP_HIT"]
    assert payload["recommended_files"]["execution"] == ["order_manager.py", "position_manager.py", "exchange_adapter.py"]
    assert payload["final_principle"] == "strategy judges, risk constrains, execution executes"
