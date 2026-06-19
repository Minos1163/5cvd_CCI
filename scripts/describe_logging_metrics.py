from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.observability.logging_metrics import (
    CORE_METRICS,
    DAILY_KPI_FIELDS,
    FORBIDDEN_LOGGING_PRACTICES,
    LOG_DIRECTORIES,
    LOG_LEVELS,
    LOG_PURPOSES,
    METRIC_GROUPS,
    REPORT_FILENAMES,
    REQUIRED_LOG_FIELDS,
    SYSTEM_METRICS,
)


def main() -> None:
    payload = {
        "log_format": "json",
        "log_purposes": LOG_PURPOSES,
        "log_levels": LOG_LEVELS,
        "log_directories": LOG_DIRECTORIES,
        "required_log_fields": REQUIRED_LOG_FIELDS,
        "metric_groups": METRIC_GROUPS,
        "daily_kpi_fields": DAILY_KPI_FIELDS,
        "core_metrics": CORE_METRICS,
        "system_metrics": SYSTEM_METRICS,
        "prometheus": {"recommended_endpoint": "/metrics", "format": "text_exposition"},
        "reports": REPORT_FILENAMES,
        "forbidden": FORBIDDEN_LOGGING_PRACTICES,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
