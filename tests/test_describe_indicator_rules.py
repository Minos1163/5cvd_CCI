import json
import subprocess
import sys


def test_describe_indicator_rules_outputs_completed_03_contract():
    result = subprocess.run(
        [sys.executable, "scripts/describe_indicator_rules.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["indicator_names"] == ["MACD", "CCI", "BOLL", "RSI", "CVD", "ATR"]
    assert payload["params"]["MACD"]["fast"] == 12
    assert payload["responsibilities"]["ATR"] == "volatility_stop_position_risk"
    assert payload["input_fields"][-2:] == ["is_closed", "quality_flag"]
    assert payload["output_fields"] == [
        "name",
        "symbol",
        "timeframe",
        "timestamp",
        "value",
        "signal",
        "trend",
        "strength",
        "quality_flag",
        "metadata",
    ]
    assert payload["required_outputs"]["MACD"] == [
        "macd_line",
        "signal_line",
        "histogram",
        "histogram_slope",
        "cross_state",
    ]
    assert payload["timeframe_indicator_map"]["15m"] == ["RSI", "MACD", "CVD", "BOLL"]
    assert payload["conflict_priority"][0] == "data_quality"
    assert "direction" in payload["forbidden_usages"]["ATR"]
    assert payload["cache_fields"] == ["version", "timestamp", "timeframe", "indicator", "quality_flag"]
