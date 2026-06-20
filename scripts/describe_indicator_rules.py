from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.data_contract import INDICATOR_REQUIRED_OUTPUTS, QUALITY_FLAGS
from src.indicators.indicator_spec import (
    DEFAULT_INDICATOR_PARAMS,
    GLOBAL_FORBIDDEN_INDICATOR_ACTIONS,
    INDICATOR_CACHE_FIELDS,
    INDICATOR_CONFLICT_PRIORITY,
    INDICATOR_FORBIDDEN_USAGES,
    INDICATOR_INPUT_FIELDS,
    INDICATOR_NAMES,
    INDICATOR_OUTPUT_FIELDS,
    INDICATOR_RESPONSIBILITIES,
    TIMEFRAME_INDICATOR_MAP,
)


def main() -> None:
    payload = {
        "indicator_names": INDICATOR_NAMES,
        "params": DEFAULT_INDICATOR_PARAMS,
        "responsibilities": INDICATOR_RESPONSIBILITIES,
        "input_fields": INDICATOR_INPUT_FIELDS,
        "output_fields": INDICATOR_OUTPUT_FIELDS,
        "quality_flags": QUALITY_FLAGS,
        "required_outputs": INDICATOR_REQUIRED_OUTPUTS,
        "timeframe_indicator_map": TIMEFRAME_INDICATOR_MAP,
        "conflict_priority": INDICATOR_CONFLICT_PRIORITY,
        "forbidden_usages": INDICATOR_FORBIDDEN_USAGES,
        "global_forbidden_actions": GLOBAL_FORBIDDEN_INDICATOR_ACTIONS,
        "cache_fields": INDICATOR_CACHE_FIELDS,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
