from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config.config_schema import (
    CONFIG_FILES,
    CONFIG_FORBIDDEN_RULES,
    CONFIG_PRECEDENCE,
    CONFIG_REQUIRED_FIELDS,
    CONFIG_ROOT,
    HOT_UPDATE_ALLOWED_PATHS,
    HOT_UPDATE_FORBIDDEN_PREFIXES,
    REQUIRED_TOP_LEVEL_KEYS,
)


def main() -> None:
    payload = {
        "config_root": str(CONFIG_ROOT),
        "config_files": CONFIG_FILES,
        "required_top_level_keys": REQUIRED_TOP_LEVEL_KEYS,
        "required_fields": CONFIG_REQUIRED_FIELDS,
        "precedence": CONFIG_PRECEDENCE,
        "version_required": True,
        "read_only_policy": "modules may read config but must not mutate it",
        "hot_update": {
            "allowed": HOT_UPDATE_ALLOWED_PATHS,
            "forbidden_prefixes": HOT_UPDATE_FORBIDDEN_PREFIXES,
        },
        "forbidden": CONFIG_FORBIDDEN_RULES,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
