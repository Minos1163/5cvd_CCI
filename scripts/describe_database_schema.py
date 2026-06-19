from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.database_schema import (
    COMMON_CORE_FIELDS,
    CORE_TABLES,
    DATABASE_ENGINE,
    DATA_LAYERS,
    EXTENSION_TABLES,
    FORBIDDEN_DATABASE_PATTERNS,
    HIGH_FREQUENCY_QUERIES,
    IDEMPOTENCY_KEYS,
    JSON_FIELD_POLICY,
    MIGRATION_REQUIREMENTS,
    PARTITIONED_TABLES,
    RETENTION_POLICY,
    STARTUP_CHECKS,
    TABLE_SCHEMAS,
    WRITE_BOUNDARIES,
)


def main() -> None:
    payload = {
        "database_engine": DATABASE_ENGINE,
        "data_layers": DATA_LAYERS,
        "common_core_fields": COMMON_CORE_FIELDS,
        "core_tables": CORE_TABLES,
        "tables": {
            name: {
                "columns": schema.column_names(),
                "primary_key": schema.primary_key,
                "unique_keys": schema.unique_keys,
                "indexes": [index.columns for index in schema.indexes],
                "partition_hint": schema.partition_hint,
            }
            for name, schema in TABLE_SCHEMAS.items()
        },
        "write_boundaries": WRITE_BOUNDARIES,
        "idempotency_keys": IDEMPOTENCY_KEYS,
        "partitioned_tables": PARTITIONED_TABLES,
        "retention_policy": RETENTION_POLICY,
        "json_field_policy": JSON_FIELD_POLICY,
        "migration_requirements": MIGRATION_REQUIREMENTS,
        "startup_checks": STARTUP_CHECKS,
        "high_frequency_queries": HIGH_FREQUENCY_QUERIES,
        "forbidden_patterns": FORBIDDEN_DATABASE_PATTERNS,
        "extension_tables": EXTENSION_TABLES,
        "side_effect_policy": "schema contract only; no database connection or live writes",
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
