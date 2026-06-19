from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.events import (
    EVENT_CATEGORIES,
    EVENT_DEDUPE_KEY_FIELDS,
    EVENT_ERROR_TYPES,
    EVENT_LIFECYCLE_STATES,
    EVENT_REQUIRED_FIELDS,
    KEY_EVENT_TYPES,
    EventPriority,
    HandlerResult,
)


def main() -> None:
    payload = {
        "event_model_fields": EVENT_REQUIRED_FIELDS,
        "key_event_types": KEY_EVENT_TYPES,
        "categories": EVENT_CATEGORIES,
        "priorities": [item.value for item in EventPriority],
        "lifecycle_states": EVENT_LIFECYCLE_STATES,
        "dedupe_key": EVENT_DEDUPE_KEY_FIELDS,
        "handler_result_fields": list(HandlerResult.__dataclass_fields__),
        "error_types": EVENT_ERROR_TYPES,
        "modes": ["sync", "async_contract_only"],
        "replay_filters": ["start_ts", "end_ts", "symbol", "event_type", "ignore_low_priority"],
        "bus_boundary": "message transport only; no strategy, risk, sizing, or execution decisions",
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
