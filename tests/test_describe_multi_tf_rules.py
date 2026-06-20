import json
import subprocess
import sys

from src.context.multi_tf_rules import build_multi_tf_decision
from src.signals.signal_engine import generate_signal
from tests.test_multi_tf_rules import snap


def test_signal_engine_accepts_multi_tf_decision():
    decision = build_multi_tf_decision(
        tf_4h=snap("4h", macd=0, cci=0, cvd_delta=0),
        tf_1h=snap("1h", macd=1, cci=120, cvd_delta=5),
        tf_30m=snap("30m", cci=130),
        tf_15m=snap("15m", rsi=55, cvd_delta=5),
        previous_15m_rsi=45,
    )
    signal = generate_signal(decision)
    assert signal["signal_type"] == "LONG"
    assert signal["entry_mode"] == "DIRECT"
    assert signal["side"] == "LONG"


def test_describe_multi_tf_rules_outputs_completed_04_contract():
    result = subprocess.run(
        [sys.executable, "scripts/describe_multi_tf_rules.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    assert payload["roles"]["4h"] == "background_reference"
    assert payload["roles"]["1h"] == "direction_confirmation"
    assert payload["priority"][0] == "data_quality"
    assert payload["priority"][3] == "1h_direction"
    assert payload["output_fields"] == [
        "symbol",
        "timeframe",
        "timestamp",
        "state",
        "confidence",
        "reason",
        "sub_reasons",
        "quality_flag",
        "metadata",
    ]
    assert payload["state_sets"]["30m"] == ["CONFIRMED", "WEAK", "INVALID", "TRANSITION"]
    assert payload["conflict_policy"]["4h_vs_1h"] == "downgrade_direct_to_probe_or_wait"
    assert "15m_direction_override" in payload["forbidden_actions"]
