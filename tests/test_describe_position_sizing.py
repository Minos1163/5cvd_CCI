import json
import subprocess
import sys


def test_describe_position_sizing_outputs_policy_json():
    completed = subprocess.run(
        [sys.executable, "scripts/describe_position_sizing.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["formula"] == "position_notional = risk_amount / stop_pct"
    assert payload["signal_multipliers"]["DIRECT"] == 1.0
    assert payload["signal_multipliers"]["PROBE"] == 0.25
    assert payload["minimum_notional_policy"] == "reject; never inflate"
    assert payload["sample"]["probe"]["notional"] == payload["sample"]["direct"]["notional"] * 0.25


def test_describe_position_sizing_outputs_completed_06_sections():
    completed = subprocess.run(
        [sys.executable, "scripts/describe_position_sizing.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["required_inputs"][0] == "account_equity"
    assert payload["decision_steps"][0] == "read_account_equity_and_available_margin"
    assert payload["log_fields"][-1] == "decision"
    assert payload["state_policy"]["PROBE"] == "probe_size"
    assert payload["volatility_factors"]["HIGH"] == 0.5
    assert payload["no_trade_policy"] == "return NO_TRADE; never inflate or promote"
    assert payload["sample"]["probe"]["decision"] == "PROBE"
