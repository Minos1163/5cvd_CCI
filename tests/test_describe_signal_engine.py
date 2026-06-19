import json
import subprocess
import sys


def test_describe_signal_engine_outputs_completed_16_sections():
    result = subprocess.run(
        [sys.executable, "scripts/describe_signal_engine.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["engine"] == "signal_engine"
    assert payload["responsibility"] == "generate_trade_intent_only"
    assert payload["allowed_outputs"]["signal_type"] == ["LONG", "SHORT", "WAIT", "NO_TRADE"]
    assert payload["allowed_outputs"]["entry_mode"] == ["PROBE", "DIRECT", "NONE"]
    assert payload["decision_flow"][0] == "read_multi_timeframe_context"
    assert payload["decision_flow"][-1] == "record_evidence_fields"
    assert payload["timeframe_roles"]["15m"] == "entry_trigger_only"
    assert payload["indicator_roles"]["ATR"][-1] == "no_direction_decision"
    assert payload["score_components"] == [
        "trend_score",
        "confirm_score",
        "trigger_score",
        "flow_score",
        "volatility_score",
    ]
    assert "FLOW_DIVERGENCE" in payload["standard_sub_reasons"]
    assert payload["state_machine_mapping"]["DIRECT"] == "DIRECT_*"
    assert "execution layer" in payload["forbidden_actions"]
    assert "call_exchange_adapter" in payload["forbidden_actions"]["signal layer"]
    assert payload["downgrade_policy"]["risk_blocked"] == "NO_TRADE"
    assert payload["sample_direct_long"]["entry_mode"] == "DIRECT"
