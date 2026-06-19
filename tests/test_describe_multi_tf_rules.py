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


def test_describe_multi_tf_rules_outputs_json():
    result = subprocess.run(
        [sys.executable, "scripts/describe_multi_tf_rules.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    assert payload["roles"]["4h"] == "background"
    assert "DIRECT" in payload["outputs"]
