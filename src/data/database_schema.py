from __future__ import annotations

from dataclasses import dataclass


DATABASE_ENGINE = "PostgreSQL"
DATA_LAYERS = ["hot", "warm", "cold", "archive"]
COMMON_CORE_FIELDS = ["id", "symbol", "timeframe", "ts", "version", "source", "created_at", "updated_at"]
CORE_TABLES = [
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


@dataclass(frozen=True)
class Column:
    name: str
    data_type: str
    nullable: bool = True
    default: str | None = None

    def ddl(self) -> str:
        parts = [self.name, self.data_type]
        if not self.nullable:
            parts.append("NOT NULL")
        if self.default is not None:
            parts.extend(["DEFAULT", self.default])
        return " ".join(parts)


@dataclass(frozen=True)
class IndexSpec:
    name: str
    columns: list[str]


@dataclass(frozen=True)
class TableSchema:
    name: str
    columns: list[Column]
    primary_key: str
    unique_keys: list[list[str]]
    indexes: list[IndexSpec]
    partition_hint: str | None = None

    def column_names(self) -> list[str]:
        return [column.name for column in self.columns]


@dataclass(frozen=True)
class SchemaValidationResult:
    passed: bool
    errors: list[str]


def c(name: str, data_type: str, nullable: bool = True, default: str | None = None) -> Column:
    return Column(name, data_type, nullable, default)


def idx(table: str, *columns: str) -> IndexSpec:
    return IndexSpec(f"idx_{table}_{'_'.join(columns)}", list(columns))


def base_columns(include_symbol: bool = True, include_timeframe: bool = True, include_ts: bool = True) -> list[Column]:
    columns = [c("id", "BIGSERIAL", False)]
    if include_symbol:
        columns.append(c("symbol", "VARCHAR(32)"))
    if include_timeframe:
        columns.append(c("timeframe", "VARCHAR(8)"))
    if include_ts:
        columns.append(c("ts", "TIMESTAMP WITH TIME ZONE"))
    columns.extend(
        [
            c("version", "VARCHAR(32)"),
            c("source", "VARCHAR(64)"),
            c("created_at", "TIMESTAMP WITH TIME ZONE", False, "NOW()"),
            c("updated_at", "TIMESTAMP WITH TIME ZONE"),
        ]
    )
    return columns


TABLE_SCHEMAS = {
    "symbols": TableSchema(
        "symbols",
        [
            c("id", "BIGSERIAL", False),
            c("symbol", "VARCHAR(32)", False),
            c("base_asset", "VARCHAR(16)", False),
            c("quote_asset", "VARCHAR(16)", False),
            c("market_cap_rank", "INT"),
            c("volume_rank", "INT"),
            c("tier", "VARCHAR(8)", False),
            c("tradable", "BOOLEAN", False, "TRUE"),
            c("listed_time", "TIMESTAMP WITH TIME ZONE"),
            c("delisting_flag", "BOOLEAN", False, "FALSE"),
            c("correlation_group", "VARCHAR(32)"),
            c("source", "VARCHAR(64)"),
            c("version", "VARCHAR(32)"),
            c("created_at", "TIMESTAMP WITH TIME ZONE", False, "NOW()"),
            c("updated_at", "TIMESTAMP WITH TIME ZONE", False, "NOW()"),
        ],
        "id",
        [["symbol"]],
        [idx("symbols", "symbol"), idx("symbols", "tradable"), idx("symbols", "tier"), idx("symbols", "correlation_group")],
    ),
    "market_candles": TableSchema(
        "market_candles",
        [
            c("id", "BIGSERIAL", False),
            c("symbol", "VARCHAR(32)", False),
            c("timeframe", "VARCHAR(8)", False),
            c("open_time", "TIMESTAMP WITH TIME ZONE", False),
            c("close_time", "TIMESTAMP WITH TIME ZONE", False),
            c("open", "NUMERIC(24, 12)", False),
            c("high", "NUMERIC(24, 12)", False),
            c("low", "NUMERIC(24, 12)", False),
            c("close", "NUMERIC(24, 12)", False),
            c("volume", "NUMERIC(30, 12)", False),
            c("quote_volume", "NUMERIC(30, 12)"),
            c("trade_count", "BIGINT"),
            c("taker_buy_base_volume", "NUMERIC(30, 12)"),
            c("taker_buy_quote_volume", "NUMERIC(30, 12)"),
            c("is_closed", "BOOLEAN", False, "TRUE"),
            c("quality_flag", "VARCHAR(16)", False, "'true'"),
            c("source", "VARCHAR(64)", False),
            c("version", "VARCHAR(32)"),
            c("created_at", "TIMESTAMP WITH TIME ZONE", False, "NOW()"),
            c("updated_at", "TIMESTAMP WITH TIME ZONE", False, "NOW()"),
        ],
        "id",
        [["symbol", "timeframe", "open_time"]],
        [idx("market_candles", "symbol", "timeframe", "open_time"), idx("market_candles", "timeframe", "open_time"), idx("market_candles", "symbol", "open_time")],
        "partition by timeframe, then month or day",
    ),
    "indicator_results": TableSchema(
        "indicator_results",
        base_columns() + [c("indicator_name", "VARCHAR(32)", False), c("value_json", "JSONB", False), c("signal", "VARCHAR(32)"), c("trend", "VARCHAR(16)"), c("strength", "NUMERIC(18, 8)"), c("quality_flag", "VARCHAR(16)", False, "'true'")],
        "id",
        [["symbol", "timeframe", "ts", "indicator_name", "version"]],
        [idx("indicator_results", "symbol", "timeframe", "ts"), idx("indicator_results", "indicator_name", "ts"), idx("indicator_results", "quality_flag")],
    ),
    "multi_tf_contexts": TableSchema(
        "multi_tf_contexts",
        base_columns(include_timeframe=False) + [c("market_state_4h", "VARCHAR(16)"), c("trend_state_1h", "VARCHAR(32)"), c("confirm_state_30m", "VARCHAR(32)"), c("trigger_state_15m", "VARCHAR(32)"), c("direction_bias", "VARCHAR(16)"), c("entry_mode", "VARCHAR(16)"), c("confidence_score", "NUMERIC(18, 8)"), c("quality_flag", "VARCHAR(16)", False, "'true'"), c("context_json", "JSONB", False)],
        "id",
        [["symbol", "ts", "version"]],
        [idx("multi_tf_contexts", "symbol", "ts"), idx("multi_tf_contexts", "trend_state_1h", "ts"), idx("multi_tf_contexts", "direction_bias", "ts")],
    ),
    "strategy_events": TableSchema(
        "strategy_events",
        [c("id", "BIGSERIAL", False), c("event_id", "VARCHAR(64)", False), c("correlation_id", "VARCHAR(64)"), c("parent_event_id", "VARCHAR(64)"), c("trace_id", "VARCHAR(64)"), c("symbol", "VARCHAR(32)"), c("timeframe", "VARCHAR(8)"), c("event_type", "VARCHAR(64)", False), c("state_before", "VARCHAR(32)"), c("state_after", "VARCHAR(32)"), c("reason", "VARCHAR(256)"), c("priority", "VARCHAR(16)", False, "'NORMAL'"), c("payload", "JSONB", False), c("status", "VARCHAR(32)", False, "'created'"), c("source", "VARCHAR(64)", False), c("version", "VARCHAR(32)"), c("ts", "TIMESTAMP WITH TIME ZONE", False), c("created_at", "TIMESTAMP WITH TIME ZONE", False, "NOW()"), c("updated_at", "TIMESTAMP WITH TIME ZONE", False, "NOW()")],
        "id",
        [["event_id"]],
        [idx("strategy_events", "symbol", "ts"), idx("strategy_events", "event_type", "ts"), idx("strategy_events", "trace_id"), idx("strategy_events", "correlation_id"), idx("strategy_events", "status", "ts")],
        "partition by month",
    ),
    "signals": TableSchema("signals", [c("id", "BIGSERIAL", False), c("signal_id", "VARCHAR(64)", False), c("event_id", "VARCHAR(64)"), c("symbol", "VARCHAR(32)", False), c("ts", "TIMESTAMP WITH TIME ZONE", False), c("signal_side", "VARCHAR(16)", False), c("signal_type", "VARCHAR(32)", False), c("entry_mode", "VARCHAR(16)", False), c("score", "NUMERIC(18, 8)"), c("confidence_score", "NUMERIC(18, 8)"), c("reason", "VARCHAR(256)"), c("quality_flag", "VARCHAR(16)", False, "'true'"), c("signal_json", "JSONB", False), c("source", "VARCHAR(64)"), c("version", "VARCHAR(32)"), c("created_at", "TIMESTAMP WITH TIME ZONE", False, "NOW()"), c("updated_at", "TIMESTAMP WITH TIME ZONE", False, "NOW()")], "id", [["signal_id"]], [idx("signals", "symbol", "ts"), idx("signals", "signal_side", "ts"), idx("signals", "signal_type", "ts")]),
    "orders": TableSchema("orders", [c("id", "BIGSERIAL", False), c("order_id", "VARCHAR(64)"), c("client_order_id", "VARCHAR(64)"), c("event_id", "VARCHAR(64)"), c("symbol", "VARCHAR(32)", False), c("side", "VARCHAR(16)", False), c("order_type", "VARCHAR(32)", False), c("position_side", "VARCHAR(16)"), c("reduce_only", "BOOLEAN", False, "FALSE"), c("time_in_force", "VARCHAR(16)"), c("quantity", "NUMERIC(30, 12)", False), c("price", "NUMERIC(24, 12)"), c("stop_price", "NUMERIC(24, 12)"), c("take_profit_price", "NUMERIC(24, 12)"), c("status", "VARCHAR(32)", False), c("requested_notional", "NUMERIC(30, 12)"), c("executed_notional", "NUMERIC(30, 12)"), c("strategy_state", "VARCHAR(32)"), c("strategy_version", "VARCHAR(32)"), c("risk_tag", "VARCHAR(32)"), c("exchange_payload", "JSONB"), c("exchange_response", "JSONB"), c("source", "VARCHAR(64)", False), c("version", "VARCHAR(32)"), c("ts", "TIMESTAMP WITH TIME ZONE", False), c("created_at", "TIMESTAMP WITH TIME ZONE", False, "NOW()"), c("updated_at", "TIMESTAMP WITH TIME ZONE", False, "NOW()")], "id", [["order_id"], ["client_order_id"]], [idx("orders", "symbol", "ts"), idx("orders", "status", "ts"), idx("orders", "client_order_id"), idx("orders", "event_id")], "partition by month"),
    "order_fills": TableSchema("order_fills", [c("id", "BIGSERIAL", False), c("order_id", "VARCHAR(64)", False), c("client_order_id", "VARCHAR(64)"), c("symbol", "VARCHAR(32)", False), c("fill_id", "VARCHAR(64)"), c("side", "VARCHAR(16)", False), c("price", "NUMERIC(24, 12)", False), c("qty", "NUMERIC(30, 12)", False), c("quote_qty", "NUMERIC(30, 12)"), c("commission", "NUMERIC(30, 12)"), c("commission_asset", "VARCHAR(16)"), c("trade_time", "TIMESTAMP WITH TIME ZONE", False), c("is_maker", "BOOLEAN"), c("source", "VARCHAR(64)"), c("version", "VARCHAR(32)"), c("created_at", "TIMESTAMP WITH TIME ZONE", False, "NOW()")], "id", [["order_id", "fill_id"]], [idx("order_fills", "order_id"), idx("order_fills", "symbol", "trade_time"), idx("order_fills", "client_order_id")], "partition by month"),
    "positions": TableSchema("positions", [c("id", "BIGSERIAL", False), c("position_id", "VARCHAR(64)"), c("symbol", "VARCHAR(32)", False), c("side", "VARCHAR(16)", False), c("qty", "NUMERIC(30, 12)", False), c("entry_price", "NUMERIC(24, 12)", False), c("mark_price", "NUMERIC(24, 12)"), c("leverage", "NUMERIC(18, 8)"), c("unrealized_pnl", "NUMERIC(30, 12)"), c("realized_pnl", "NUMERIC(30, 12)"), c("stop_price", "NUMERIC(24, 12)"), c("take_profit_price", "NUMERIC(24, 12)"), c("position_age_bars", "INT"), c("state", "VARCHAR(32)", False, "'OPEN'"), c("strategy_state", "VARCHAR(32)"), c("entry_event_id", "VARCHAR(64)"), c("exit_event_id", "VARCHAR(64)"), c("source", "VARCHAR(64)"), c("version", "VARCHAR(32)"), c("open_ts", "TIMESTAMP WITH TIME ZONE"), c("close_ts", "TIMESTAMP WITH TIME ZONE"), c("created_at", "TIMESTAMP WITH TIME ZONE", False, "NOW()"), c("updated_at", "TIMESTAMP WITH TIME ZONE", False, "NOW()")], "id", [["position_id"]], [idx("positions", "symbol", "state"), idx("positions", "symbol", "open_ts"), idx("positions", "entry_event_id"), idx("positions", "exit_event_id")]),
    "risk_snapshots": TableSchema("risk_snapshots", base_columns(include_timeframe=False) + [c("snapshot_id", "VARCHAR(64)"), c("account_equity", "NUMERIC(30, 12)"), c("available_margin", "NUMERIC(30, 12)"), c("used_margin", "NUMERIC(30, 12)"), c("daily_pnl", "NUMERIC(30, 12)"), c("weekly_pnl", "NUMERIC(30, 12)"), c("max_drawdown", "NUMERIC(18, 8)"), c("exposure_pct", "NUMERIC(18, 8)"), c("portfolio_exposure_pct", "NUMERIC(18, 8)"), c("risk_state", "VARCHAR(32)"), c("cooldown_state", "VARCHAR(32)"), c("risk_json", "JSONB", False)], "id", [["snapshot_id"]], [idx("risk_snapshots", "symbol", "ts"), idx("risk_snapshots", "risk_state", "ts"), idx("risk_snapshots", "cooldown_state", "ts")]),
    "account_snapshots": TableSchema("account_snapshots", [c("id", "BIGSERIAL", False), c("snapshot_id", "VARCHAR(64)"), c("ts", "TIMESTAMP WITH TIME ZONE", False), c("account_equity", "NUMERIC(30, 12)", False), c("available_margin", "NUMERIC(30, 12)"), c("used_margin", "NUMERIC(30, 12)"), c("unrealized_pnl", "NUMERIC(30, 12)"), c("realized_pnl", "NUMERIC(30, 12)"), c("daily_pnl", "NUMERIC(30, 12)"), c("weekly_pnl", "NUMERIC(30, 12)"), c("total_exposure_pct", "NUMERIC(18, 8)"), c("max_drawdown_pct", "NUMERIC(18, 8)"), c("account_state", "VARCHAR(32)"), c("account_json", "JSONB", False), c("source", "VARCHAR(64)"), c("version", "VARCHAR(32)"), c("created_at", "TIMESTAMP WITH TIME ZONE", False, "NOW()")], "id", [["snapshot_id"]], [idx("account_snapshots", "ts"), idx("account_snapshots", "account_state", "ts")]),
    "cooldowns": TableSchema("cooldowns", [c("id", "BIGSERIAL", False), c("cooldown_id", "VARCHAR(64)"), c("symbol", "VARCHAR(32)", False), c("side", "VARCHAR(16)"), c("started_at", "TIMESTAMP WITH TIME ZONE", False), c("ended_at", "TIMESTAMP WITH TIME ZONE"), c("duration_bars", "INT"), c("reason", "VARCHAR(256)"), c("status", "VARCHAR(32)", False, "'ACTIVE'"), c("source", "VARCHAR(64)"), c("version", "VARCHAR(32)"), c("created_at", "TIMESTAMP WITH TIME ZONE", False, "NOW()"), c("updated_at", "TIMESTAMP WITH TIME ZONE", False, "NOW()")], "id", [["cooldown_id"]], [idx("cooldowns", "symbol", "status"), idx("cooldowns", "started_at"), idx("cooldowns", "ended_at")]),
}

TABLE_SCHEMAS.update(
    {
        "backtest_runs": TableSchema("backtest_runs", [c("id", "BIGSERIAL", False), c("run_id", "VARCHAR(64)", False), c("strategy_name", "VARCHAR(64)", False), c("strategy_version", "VARCHAR(32)", False), c("config_version", "VARCHAR(32)"), c("data_version", "VARCHAR(32)"), c("start_time", "TIMESTAMP WITH TIME ZONE", False), c("end_time", "TIMESTAMP WITH TIME ZONE", False), c("symbols_json", "JSONB", False), c("timeframe_json", "JSONB", False), c("initial_capital", "NUMERIC(30, 12)", False), c("status", "VARCHAR(32)", False), c("summary_json", "JSONB"), c("created_at", "TIMESTAMP WITH TIME ZONE", False, "NOW()"), c("updated_at", "TIMESTAMP WITH TIME ZONE", False, "NOW()")], "id", [["run_id"]], [idx("backtest_runs", "strategy_name", "strategy_version"), idx("backtest_runs", "status", "created_at"), idx("backtest_runs", "start_time", "end_time")]),
        "backtest_steps": TableSchema("backtest_steps", [c("id", "BIGSERIAL", False), c("run_id", "VARCHAR(64)", False), c("step_index", "BIGINT", False), c("symbol", "VARCHAR(32)", False), c("timeframe", "VARCHAR(8)", False), c("ts", "TIMESTAMP WITH TIME ZONE", False), c("state_before", "VARCHAR(32)"), c("state_after", "VARCHAR(32)"), c("event_type", "VARCHAR(64)"), c("payload", "JSONB"), c("created_at", "TIMESTAMP WITH TIME ZONE", False, "NOW()")], "id", [["run_id", "step_index"]], [idx("backtest_steps", "run_id", "step_index"), idx("backtest_steps", "run_id", "symbol", "ts")]),
        "backtest_trades": TableSchema("backtest_trades", [c("id", "BIGSERIAL", False), c("run_id", "VARCHAR(64)", False), c("trade_id", "VARCHAR(64)"), c("symbol", "VARCHAR(32)", False), c("side", "VARCHAR(16)", False), c("entry_time", "TIMESTAMP WITH TIME ZONE", False), c("entry_price", "NUMERIC(24, 12)", False), c("exit_time", "TIMESTAMP WITH TIME ZONE"), c("exit_price", "NUMERIC(24, 12)"), c("qty", "NUMERIC(30, 12)", False), c("leverage", "NUMERIC(18, 8)"), c("pnl", "NUMERIC(30, 12)"), c("pnl_pct", "NUMERIC(18, 8)"), c("fees", "NUMERIC(30, 12)"), c("slippage", "NUMERIC(30, 12)"), c("reason_enter", "VARCHAR(256)"), c("reason_exit", "VARCHAR(256)"), c("entry_mode", "VARCHAR(16)"), c("exit_mode", "VARCHAR(16)"), c("state_before", "VARCHAR(32)"), c("state_after", "VARCHAR(32)"), c("trade_json", "JSONB"), c("created_at", "TIMESTAMP WITH TIME ZONE", False, "NOW()")], "id", [["trade_id"]], [idx("backtest_trades", "run_id", "symbol"), idx("backtest_trades", "entry_time"), idx("backtest_trades", "exit_time")]),
        "performance_metrics": TableSchema("performance_metrics", [c("id", "BIGSERIAL", False), c("run_id", "VARCHAR(64)"), c("metric_scope", "VARCHAR(32)", False), c("metric_name", "VARCHAR(64)", False), c("metric_value", "NUMERIC(30, 12)"), c("metric_json", "JSONB"), c("ts", "TIMESTAMP WITH TIME ZONE", False), c("source", "VARCHAR(64)"), c("version", "VARCHAR(32)"), c("created_at", "TIMESTAMP WITH TIME ZONE", False, "NOW()")], "id", [["run_id", "metric_scope", "metric_name"]], [idx("performance_metrics", "run_id"), idx("performance_metrics", "metric_scope", "metric_name")]),
        "audit_logs": TableSchema("audit_logs", [c("id", "BIGSERIAL", False), c("audit_id", "VARCHAR(64)"), c("ts", "TIMESTAMP WITH TIME ZONE", False), c("module", "VARCHAR(64)", False), c("action", "VARCHAR(64)", False), c("symbol", "VARCHAR(32)"), c("event_id", "VARCHAR(64)"), c("trace_id", "VARCHAR(64)"), c("severity", "VARCHAR(16)", False), c("message", "TEXT", False), c("payload", "JSONB"), c("source", "VARCHAR(64)"), c("version", "VARCHAR(32)"), c("created_at", "TIMESTAMP WITH TIME ZONE", False, "NOW()")], "id", [["audit_id"]], [idx("audit_logs", "ts"), idx("audit_logs", "module", "ts"), idx("audit_logs", "severity", "ts"), idx("audit_logs", "trace_id")], "partition by month"),
        "reports": TableSchema("reports", [c("id", "BIGSERIAL", False), c("report_id", "VARCHAR(64)"), c("report_type", "VARCHAR(32)", False), c("run_id", "VARCHAR(64)"), c("title", "VARCHAR(256)"), c("file_path", "TEXT", False), c("file_format", "VARCHAR(16)", False), c("summary_json", "JSONB"), c("ts", "TIMESTAMP WITH TIME ZONE", False), c("created_at", "TIMESTAMP WITH TIME ZONE", False, "NOW()")], "id", [["report_id"]], [idx("reports", "report_type", "ts"), idx("reports", "run_id")]),
        "config_versions": TableSchema("config_versions", [c("id", "BIGSERIAL", False), c("config_version", "VARCHAR(32)", False), c("config_name", "VARCHAR(64)", False), c("config_json", "JSONB", False), c("checksum", "VARCHAR(128)"), c("source", "VARCHAR(64)"), c("ts", "TIMESTAMP WITH TIME ZONE", False), c("created_at", "TIMESTAMP WITH TIME ZONE", False, "NOW()")], "id", [["config_version", "config_name"]], [idx("config_versions", "config_version", "config_name")]),
        "event_bus_messages": TableSchema("event_bus_messages", [c("id", "BIGSERIAL", False), c("message_id", "VARCHAR(64)", False), c("event_id", "VARCHAR(64)", False), c("event_type", "VARCHAR(64)", False), c("trace_id", "VARCHAR(64)"), c("correlation_id", "VARCHAR(64)"), c("source", "VARCHAR(64)", False), c("target", "VARCHAR(64)"), c("priority", "VARCHAR(16)", False), c("payload", "JSONB", False), c("status", "VARCHAR(32)", False), c("ts", "TIMESTAMP WITH TIME ZONE", False), c("created_at", "TIMESTAMP WITH TIME ZONE", False, "NOW()")], "id", [["message_id"]], [idx("event_bus_messages", "event_type", "ts"), idx("event_bus_messages", "trace_id"), idx("event_bus_messages", "correlation_id"), idx("event_bus_messages", "status", "ts")], "partition by month"),
        "system_health": TableSchema("system_health", [c("id", "BIGSERIAL", False), c("ts", "TIMESTAMP WITH TIME ZONE", False), c("component", "VARCHAR(64)", False), c("status", "VARCHAR(32)", False), c("latency_ms", "NUMERIC(18, 8)"), c("error_count", "INT"), c("warning_count", "INT"), c("health_json", "JSONB"), c("created_at", "TIMESTAMP WITH TIME ZONE", False, "NOW()")], "id", [], [idx("system_health", "component", "ts"), idx("system_health", "status", "ts")]),
    }
)

WRITE_BOUNDARIES = {
    "data layer": ["market_candles", "symbols"],
    "indicator layer": ["indicator_results"],
    "context layer": ["multi_tf_contexts"],
    "signal layer": ["signals"],
    "state machine": ["strategy_events"],
    "risk layer": ["risk_snapshots", "cooldowns", "positions"],
    "execution layer": ["orders", "order_fills", "positions"],
    "backtest layer": ["backtest_runs", "backtest_steps", "backtest_trades", "performance_metrics"],
    "audit layer": ["audit_logs", "event_bus_messages", "system_health"],
    "config layer": ["config_versions"],
    "reporting layer": ["reports"],
}
IDEMPOTENCY_KEYS = {
    "strategy_events": "event_id",
    "orders": "client_order_id",
    "backtest_runs": "run_id",
    "risk_snapshots": "snapshot_id",
    "account_snapshots": "snapshot_id",
}
PARTITIONED_TABLES = ["market_candles", "strategy_events", "orders", "order_fills", "audit_logs", "event_bus_messages"]
RETENTION_POLICY = {
    "market_candles": "long_term",
    "indicator_results": "6_to_12_months",
    "strategy_events": "12_months_plus",
    "orders": "long_term",
    "order_fills": "long_term",
    "backtest_runs": "long_term",
    "backtest_trades": "long_term",
    "audit_logs": "long_term",
    "system_health": "3_to_6_months",
}
JSON_FIELD_POLICY = {
    "allowed": [
        "indicator composite results",
        "strategy context details",
        "raw execution responses",
        "backtest summaries",
        "audit extensions",
    ],
    "forbidden": ["core filter logic", "core fields", "unstructured business records"],
}
MIGRATION_REQUIREMENTS = ["migration_script", "rollback_script", "version", "compatibility_notes", "test_verification"]
STARTUP_CHECKS = ["tables_exist", "indexes_exist", "version_matches", "required_fields_present", "database_writable", "connection_healthy"]
HIGH_FREQUENCY_QUERIES = [
    "recent_candles",
    "recent_indicator_results",
    "current_positions",
    "recent_strategy_events",
    "recent_orders_and_fills",
    "current_risk_snapshot",
    "current_cooldown_state",
    "current_backtest_result",
]
FORBIDDEN_DATABASE_PATTERNS = [
    "single_super_table",
    "execution_temp_state_in_long_term_table",
    "mixed_live_backtest_without_source",
    "database_field_patch_business_logic",
    "strategy_mutates_raw_history",
    "json_as_universal_storage",
    "business_record_without_unique_key",
]
EXTENSION_TABLES = [
    "market_regime_history",
    "signal_scores",
    "trade_decisions",
    "slippage_records",
    "funding_rates",
    "open_interest_snapshots",
    "correlation_matrix_snapshots",
]


def render_create_table(table_name: str) -> str:
    schema = TABLE_SCHEMAS[table_name]
    lines = [f"  {column.ddl()}" for column in schema.columns]
    lines.append(f"  PRIMARY KEY ({schema.primary_key})")
    for unique_key in schema.unique_keys:
        lines.append(f"  UNIQUE({', '.join(unique_key)})")
    return f"CREATE TABLE {schema.name} (\n" + ",\n".join(lines) + "\n);"


def validate_schema_contract() -> SchemaValidationResult:
    errors: list[str] = []
    version_exempt_tables = {"backtest_runs", "backtest_steps", "backtest_trades", "reports", "config_versions", "event_bus_messages", "system_health"}
    for table in CORE_TABLES:
        schema = TABLE_SCHEMAS.get(table)
        if schema is None:
            errors.append(f"missing table schema: {table}")
            continue
        names = schema.column_names()
        if schema.primary_key not in names:
            errors.append(f"{table} missing primary key column: {schema.primary_key}")
        if not any(column.name in {"ts", "open_time", "trade_time", "started_at", "entry_time", "created_at"} for column in schema.columns):
            errors.append(f"{table} missing time field")
        if not any(column.name == "version" for column in schema.columns) and table not in version_exempt_tables:
            errors.append(f"{table} missing version field")
        for unique_key in schema.unique_keys:
            missing = [column for column in unique_key if column not in names]
            if missing:
                errors.append(f"{table} unique key references missing columns: {missing}")
        for index in schema.indexes:
            missing = [column for column in index.columns if column not in names]
            if missing:
                errors.append(f"{table} index {index.name} references missing columns: {missing}")
    return SchemaValidationResult(not errors, errors)
