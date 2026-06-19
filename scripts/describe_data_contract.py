from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.data_contract import (
    ACCOUNT_SNAPSHOT_FIELDS,
    AGGREGATION_RULES,
    CACHE_CONTRACT_FIELDS,
    CVD_SOURCES,
    DATA_CONTRACT_FORBIDDEN,
    DATA_LAYERS,
    DATA_SOURCES,
    EXECUTION_FIELDS,
    FULL_CANDLE_FIELDS,
    INDICATOR_CONTRACT_FIELDS,
    INDICATOR_REQUIRED_OUTPUTS,
    POSITION_SNAPSHOT_FIELDS,
    QUALITY_FLAGS,
    REQUIRED_CANDLE_FIELDS,
    REQUIRED_DATA_TYPES,
    STORAGE_CONTRACT,
    STRATEGY_CONTEXT_FIELDS,
    STRATEGY_EVENT_FIELDS,
    STRATEGY_EVENT_TYPES,
    SUPPORTED_TIMEFRAMES,
    TIMEFRAME_ROLES,
    UNIVERSE_ITEM_FIELDS,
    VERSION_FIELDS,
)


def main() -> None:
    payload = {
        "required_data_types": REQUIRED_DATA_TYPES,
        "data_layers": DATA_LAYERS,
        "data_sources": DATA_SOURCES,
        "required_candle_fields": REQUIRED_CANDLE_FIELDS,
        "full_candle_fields": FULL_CANDLE_FIELDS,
        "supported_timeframes": SUPPORTED_TIMEFRAMES,
        "timeframe_roles": TIMEFRAME_ROLES,
        "aggregation_rules": AGGREGATION_RULES,
        "cvd_sources": CVD_SOURCES,
        "cvd_features": ["cumulative", "delta", "slope", "divergence"],
        "indicator_input": "candles: list[OHLCV]",
        "indicator_contract_fields": INDICATOR_CONTRACT_FIELDS,
        "indicator_required_outputs": INDICATOR_REQUIRED_OUTPUTS,
        "strategy_context_fields": STRATEGY_CONTEXT_FIELDS,
        "strategy_event_fields": STRATEGY_EVENT_FIELDS,
        "strategy_event_types": STRATEGY_EVENT_TYPES,
        "execution_fields": EXECUTION_FIELDS,
        "account_snapshot_fields": ACCOUNT_SNAPSHOT_FIELDS,
        "position_snapshot_fields": POSITION_SNAPSHOT_FIELDS,
        "universe_item_fields": UNIVERSE_ITEM_FIELDS,
        "quality_flags": QUALITY_FLAGS,
        "cache_contract_fields": CACHE_CONTRACT_FIELDS,
        "version_fields": VERSION_FIELDS,
        "storage_contract": STORAGE_CONTRACT,
        "forbidden": DATA_CONTRACT_FORBIDDEN,
        "time_axis": "UTC",
        "future_leakage": "forbidden",
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
