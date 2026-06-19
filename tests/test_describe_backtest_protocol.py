import json
import subprocess
import sys


def test_describe_backtest_protocol_outputs_policy_json():
    completed = subprocess.run(
        [sys.executable, "scripts/describe_backtest_protocol.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["base_timeframe"] == "15m"
    assert payload["processing_order"][4] == "check_exit"
    assert payload["processing_order"][7] == "check_entry"
    assert "sharpe" in payload["required_performance_fields"]
    assert payload["costs_required"] == ["fee", "slippage"]


def test_describe_backtest_protocol_exposes_standalone_08_requirements():
    completed = subprocess.run(
        [sys.executable, "scripts/describe_backtest_protocol.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["data_quality_checks"][0] == "time_continuity"
    assert payload["required_state_transition_fields"][0] == "current_state"
    assert "walk_forward" in payload["validation_features"]
    assert "equity_curve" in payload["required_output_artifacts"]
    assert "volatility_regime" in payload["stratified_analysis_dimensions"]
