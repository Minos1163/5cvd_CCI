import json
import subprocess
import sys


def test_describe_entry_state_machine_outputs_json():
    result = subprocess.run(
        [sys.executable, "scripts/describe_entry_state_machine.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    assert payload["version"] == "1.0"
    assert payload["initial_state"] == "FLAT"
    assert "PROBE_LONG" in payload["states"]
    assert payload["probe_upgrade_r"] == 1.0
    assert "DIRECT_LONG" in payload["allowed_transitions"]["FLAT"]
    assert "MANAGE_LONG" in payload["allowed_transitions"]["PROBE_LONG"]
    assert payload["required_log_fields"] == [
        "symbol",
        "timestamp",
        "state_before",
        "state_after",
        "reason",
        "signal_type",
        "entry_mode",
        "risk_level",
        "quality_flag",
        "price",
        "version",
    ]
    assert "risk_blocked" in payload["transition_blockers"]
    assert "execution_result" in payload["transition_sources"]
    assert "calculate_final_position_size" in payload["forbidden_actions"]
