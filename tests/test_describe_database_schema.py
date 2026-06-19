import json
import subprocess
import sys


def test_describe_database_schema_outputs_completed_15_sections():
    completed = subprocess.run(
        [sys.executable, "scripts/describe_database_schema.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["database_engine"] == "PostgreSQL"
    assert payload["data_layers"] == ["hot", "warm", "cold", "archive"]
    assert payload["core_tables"][0] == "symbols"
    assert payload["core_tables"][-1] == "system_health"
    assert payload["tables"]["market_candles"]["unique_keys"] == [["symbol", "timeframe", "open_time"]]
    assert payload["write_boundaries"]["execution layer"] == ["orders", "order_fills", "positions"]
    assert payload["idempotency_keys"]["orders"] == "client_order_id"
    assert "market_candles" in payload["partitioned_tables"]
    assert payload["retention_policy"]["system_health"] == "3_to_6_months"
    assert "database_field_patch_business_logic" in payload["forbidden_patterns"]
