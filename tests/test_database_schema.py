from src.data.database_schema import (
    COMMON_CORE_FIELDS,
    CORE_TABLES,
    DATABASE_ENGINE,
    DATA_LAYERS,
    EXTENSION_TABLES,
    FORBIDDEN_DATABASE_PATTERNS,
    IDEMPOTENCY_KEYS,
    JSON_FIELD_POLICY,
    MIGRATION_REQUIREMENTS,
    PARTITIONED_TABLES,
    RETENTION_POLICY,
    TABLE_SCHEMAS,
    WRITE_BOUNDARIES,
    render_create_table,
    validate_schema_contract,
)


def test_database_engine_layers_and_core_tables_match_doc():
    assert DATABASE_ENGINE == "PostgreSQL"
    assert DATA_LAYERS == ["hot", "warm", "cold", "archive"]
    assert CORE_TABLES == [
        "symbols",
        "market_candles",
        "indicator_results",
        "multi_tf_contexts",
        "strategy_events",
        "signals",
        "orders",
        "order_fills",
        "positions",
        "risk_snapshots",
        "account_snapshots",
        "cooldowns",
        "backtest_runs",
        "backtest_steps",
        "backtest_trades",
        "performance_metrics",
        "audit_logs",
        "reports",
        "config_versions",
        "event_bus_messages",
        "system_health",
    ]
    assert COMMON_CORE_FIELDS == ["id", "symbol", "timeframe", "ts", "version", "source", "created_at", "updated_at"]


def test_core_table_metadata_includes_required_columns_indexes_and_unique_keys():
    symbols = TABLE_SCHEMAS["symbols"]
    assert symbols.primary_key == "id"
    assert "symbol" in symbols.column_names()
    assert symbols.unique_keys == [["symbol"]]
    assert ["symbol"] in [index.columns for index in symbols.indexes]
    candles = TABLE_SCHEMAS["market_candles"]
    assert "open_time" in candles.column_names()
    assert "close_time" in candles.column_names()
    assert candles.unique_keys == [["symbol", "timeframe", "open_time"]]
    assert ["symbol", "timeframe", "open_time"] in [index.columns for index in candles.indexes]
    strategy_events = TABLE_SCHEMAS["strategy_events"]
    assert "event_id" in strategy_events.column_names()
    assert "trace_id" in strategy_events.column_names()
    assert ["event_id"] in strategy_events.unique_keys
    orders = TABLE_SCHEMAS["orders"]
    assert "client_order_id" in orders.column_names()
    assert "exchange_response" in orders.column_names()
    assert ["client_order_id"] in orders.unique_keys


def test_validate_schema_contract_accepts_all_doc_tables():
    result = validate_schema_contract()
    assert result.passed is True
    assert result.errors == []


def test_render_create_table_includes_primary_key_unique_keys_and_jsonb_fields():
    ddl = render_create_table("strategy_events")
    assert ddl.startswith("CREATE TABLE strategy_events")
    assert "id BIGSERIAL NOT NULL" in ddl
    assert "PRIMARY KEY (id)" in ddl
    assert "UNIQUE(event_id)" in ddl
    assert "payload JSONB NOT NULL" in ddl
    candle_ddl = render_create_table("market_candles")
    assert "UNIQUE(symbol, timeframe, open_time)" in candle_ddl
    assert "quality_flag VARCHAR(16) NOT NULL DEFAULT 'true'" in candle_ddl


def test_write_boundaries_idempotency_partition_and_retention_policies_match_doc():
    assert WRITE_BOUNDARIES["data layer"] == ["market_candles", "symbols"]
    assert WRITE_BOUNDARIES["execution layer"] == ["orders", "order_fills", "positions"]
    assert WRITE_BOUNDARIES["audit layer"] == ["audit_logs", "event_bus_messages", "system_health"]
    assert IDEMPOTENCY_KEYS == {
        "strategy_events": "event_id",
        "orders": "client_order_id",
        "backtest_runs": "run_id",
        "risk_snapshots": "snapshot_id",
        "account_snapshots": "snapshot_id",
    }
    assert PARTITIONED_TABLES == ["market_candles", "strategy_events", "orders", "order_fills", "audit_logs", "event_bus_messages"]
    assert RETENTION_POLICY["market_candles"] == "long_term"
    assert RETENTION_POLICY["system_health"] == "3_to_6_months"


def test_json_migration_forbidden_and_extension_policies_match_doc():
    assert JSON_FIELD_POLICY["allowed"] == [
        "indicator composite results",
        "strategy context details",
        "raw execution responses",
        "backtest summaries",
        "audit extensions",
    ]
    assert JSON_FIELD_POLICY["forbidden"] == ["core filter logic", "core fields", "unstructured business records"]
    assert MIGRATION_REQUIREMENTS == ["migration_script", "rollback_script", "version", "compatibility_notes", "test_verification"]
    assert "single_super_table" in FORBIDDEN_DATABASE_PATTERNS
    assert "database_field_patch_business_logic" in FORBIDDEN_DATABASE_PATTERNS
    assert EXTENSION_TABLES == [
        "market_regime_history",
        "signal_scores",
        "trade_decisions",
        "slippage_records",
        "funding_rates",
        "open_interest_snapshots",
        "correlation_matrix_snapshots",
    ]
