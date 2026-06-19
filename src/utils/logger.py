from __future__ import annotations

from datetime import datetime, timezone
import json
import logging


def log_json(logger: logging.Logger, level: int, event: str, **fields) -> None:
    module = fields.pop("module", "system")
    ts = fields.pop("ts", datetime.now(timezone.utc).isoformat())
    payload = {
        "ts": ts,
        "level": logging.getLevelName(level),
        "module": module,
        "event": event,
        **fields,
    }
    logger.log(level, json.dumps(payload, ensure_ascii=False, sort_keys=True))
