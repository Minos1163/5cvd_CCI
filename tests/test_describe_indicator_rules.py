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

    # 03 期契约里的 RSI 已在 canonical 规格中被 EMA 顶替（src/indicators/indicator_spec.py:18）。
    # 本断言锁的是**描述器的实际输出**，而描述器从 canonical 模块 import，故此处必须与 spec 一致。
    assert payload["indicator_names"] == ["MACD", "CCI", "BOLL", "EMA", "CVD", "ATR"]
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
    # 15m 启用集：RSI 位被 EMA 顶替，且 EMA 占据原来的第一位。
    assert payload["timeframe_indicator_map"]["15m"] == ["EMA", "MACD", "CVD", "BOLL"]
    assert payload["conflict_priority"][0] == "data_quality"
    assert "direction" in payload["forbidden_usages"]["ATR"]
    assert payload["cache_fields"] == ["version", "timestamp", "timeframe", "indicator", "quality_flag"]
