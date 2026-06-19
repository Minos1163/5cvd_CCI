from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.backtest.protocol import (
    BACKTEST_PROCESSING_ORDER,
    DATA_QUALITY_CHECKS,
    REQUIRED_OUTPUT_ARTIFACTS,
    REQUIRED_PERFORMANCE_FIELDS,
    REQUIRED_STATE_TRANSITION_FIELDS,
    REQUIRED_TRADE_FIELDS,
    STRATIFIED_ANALYSIS_DIMENSIONS,
)


def main() -> None:
    payload = {
        "base_timeframe": "15m",
        "higher_timeframes": ["30m", "1h", "4h"],
        "processing_order": BACKTEST_PROCESSING_ORDER,
        "approved_fill_models": ["next_bar_open", "trigger_price", "conservative_limit"],
        "costs_required": ["fee", "slippage"],
        "data_quality_checks": DATA_QUALITY_CHECKS,
        "required_trade_fields": REQUIRED_TRADE_FIELDS,
        "required_performance_fields": REQUIRED_PERFORMANCE_FIELDS,
        "required_state_transition_fields": REQUIRED_STATE_TRANSITION_FIELDS,
        "stratified_analysis_dimensions": STRATIFIED_ANALYSIS_DIMENSIONS,
        "required_output_artifacts": REQUIRED_OUTPUT_ARTIFACTS,
        "validation_features": [
            "data_quality",
            "timeframe_alignment",
            "state_transition_logs",
            "walk_forward",
            "output_artifacts",
        ],
        "forbidden": [
            "future data",
            "unfinished candle final values",
            "ignoring fees or slippage",
            "inflating probe into direct",
        ],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
