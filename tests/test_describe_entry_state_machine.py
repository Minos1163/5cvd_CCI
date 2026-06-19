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
    assert payload["initial_state"] == "FLAT"
    assert "PROBE_LONG" in payload["states"]
    assert payload["probe_upgrade_r"] == 1.0
