import json
import subprocess
import sys


def test_describe_data_contract_outputs_policy_json():
    completed = subprocess.run(
        [sys.executable, "scripts/describe_data_contract.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["required_candle_fields"][0] == "open_time"
    assert payload["timeframe_roles"]["15m"] == "execution"
    assert payload["aggregation_rules"]["30m"] == "15m"
    assert payload["cvd_features"] == ["cumulative", "delta", "slope", "divergence"]
    assert payload["indicator_input"] == "candles: list[OHLCV]"


def test_describe_data_contract_outputs_completed_09_sections():
    completed = subprocess.run(
        [sys.executable, "scripts/describe_data_contract.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["data_layers"][0] == "raw_market_data"
    assert payload["full_candle_fields"][0] == "symbol"
    assert payload["indicator_required_outputs"]["ATR"] == ["atr", "atr_pct", "volatility_state"]
    assert "DATA_INVALID" in payload["strategy_event_types"]
    assert payload["storage_contract"]["cold"] == ["historical_backtest_data", "long_term_trade_audit", "historical_performance_report"]
