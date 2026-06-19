import json
import subprocess
import sys


def test_describe_risk_exit_rules_outputs_policy_json():
    completed = subprocess.run(
        [sys.executable, "scripts/describe_risk_exit_rules.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["initial_stop_source"] == "ATR only"
    assert payload["exit_priority"][0] == "FORCED_STOP"
    assert payload["take_profit"]["r_levels"] == [1.0, 2.0, 3.0]
    assert payload["forbidden"][0] == "multiple active stop systems"
