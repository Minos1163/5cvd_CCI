import json
import subprocess
import sys


def test_describe_indicator_rules_outputs_json():
    result = subprocess.run(
        [sys.executable, "scripts/describe_indicator_rules.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    assert payload["params"]["MACD"]["fast"] == 12
    assert payload["responsibilities"]["ATR"] == "risk"
    assert payload["priority"][0] == "MACD"
