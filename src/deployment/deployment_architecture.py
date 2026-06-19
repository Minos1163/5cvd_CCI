from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


DEPLOYMENT_ENVIRONMENTS = ["development", "staging", "production"]
DEPLOYMENT_LAYERS = [
    "data layer",
    "indicator layer",
    "context layer",
    "signal layer",
    "risk layer",
    "execution layer",
    "portfolio layer",
    "backtest layer",
    "reporting layer",
    "monitoring layer",
]
DEPLOYMENT_PROCESS_UNITS = [
    "market data daemon",
    "strategy engine",
    "execution engine",
    "risk supervisor",
    "portfolio sync daemon",
    "backtest runner",
    "report generator",
    "health monitor",
]
DEPLOYMENT_TARGETS = [
    "full_strategy",
    "single_symbol_strategy",
    "backtest_job",
    "daily_report_job",
    "health_check",
    "market_data_sync",
    "position_sync",
    "execution_listener",
    "event_replay",
    "failure_recovery",
]
CONFIG_FILES = [
    "strategy.yaml",
    "risk.yaml",
    "execution.yaml",
    "universe.yaml",
    "logging.yaml",
    "backtest.yaml",
    "database.yaml",
    "monitoring.yaml",
]
SECRET_POLICY = {
    "allowed": ["environment_variables", "secret_file", "secret_manager", "container_secret_mount"],
    "forbidden": ["code_repository", "plain_config_file", "logs", "reports"],
}
LOG_DIRECTORIES = [
    "logs/strategy",
    "logs/risk",
    "logs/execution",
    "logs/backtest",
    "logs/audit",
    "logs/system",
]
STARTUP_SEQUENCE = [
    "load_config",
    "validate_config_version",
    "connect_database",
    "load_universe",
    "fetch_latest_market_data",
    "sync_account_and_positions",
    "check_protection_orders",
    "start_event_bus",
    "start_monitoring",
    "start_strategy_main_loop",
    "enter_trading_runtime",
]
SHUTDOWN_SEQUENCE = [
    "stop_accepting_new_signals",
    "stop_new_entries",
    "keep_risk_and_exit_capability",
    "stop_market_data_consumption",
    "persist_current_state",
    "clean_temporary_resources",
    "close_connections",
    "write_shutdown_log",
]
RECOVERY_STATE_FIELDS = [
    "current_state_machine_state",
    "current_positions",
    "open_orders",
    "cooldown_state",
    "risk_snapshot",
    "strategy_version",
    "config_version",
]
FAILURE_MODES = [
    "data_source_unavailable",
    "market_data_delayed",
    "missing_data",
    "exchange_rejected",
    "order_submit_failed",
    "protection_order_failed",
    "position_sync_failed",
    "database_write_failed",
    "config_load_failed",
    "event_bus_blocked",
    "risk_threshold_invalid",
    "state_machine_inconsistent",
]
PROTECTION_MODE_ALLOWED_ACTIONS = [
    "block_new_entries",
    "allow_reductions",
    "allow_stop_loss_exit",
    "allow_position_sync",
    "allow_logs_and_audit",
    "allow_manual_inspection",
]
PROTECTION_MODE_TRIGGERS = [
    "consecutive_rejects",
    "abnormal_position_state",
    "risk_abnormal",
    "exchange_unavailable",
    "data_abnormal",
    "unknown_order_state",
    "database_not_writable",
    "event_bus_unavailable",
    "consecutive_sync_failures",
    "consecutive_protection_failures",
]
MONITORING_METRICS = [
    "market_data_latency",
    "strategy_loop_latency",
    "order_submit_latency",
    "fill_report_latency",
    "position_sync_failures",
    "protection_order_failures",
    "reject_count",
    "risk_block_count",
    "missing_data_count",
    "system_exception_count",
]
OBSERVABILITY_QUESTIONS = [
    "is_system_trading",
    "current_positions",
    "why_not_trading",
    "is_risk_safe",
    "current_order_status",
    "is_in_cooldown",
    "is_in_protection_mode",
    "latest_exception",
]
CONTAINER_SERVICES = ["strategy-app", "backtest-runner", "database", "monitoring", "report-worker"]
HEALTH_CHECKS = [
    "database_connection",
    "exchange_connection",
    "market_data_update",
    "event_bus",
    "position_sync",
    "risk_state",
    "config_state",
    "critical_processes",
]
HEALTH_CHECK_TYPES = ["liveness", "readiness", "startup"]
VERSION_SNAPSHOT_FIELDS = [
    "code_version",
    "strategy_version",
    "risk_version",
    "config_version",
    "data_version",
    "backtest_version",
    "report_version",
]
RELEASE_GATES = [
    "local_unit_tests",
    "backtest_passed",
    "staging_validation_passed",
    "config_validation_passed",
    "monitoring_connected",
    "production_canary",
    "small_scale_live_validation",
    "full_rollout_approval",
]
ROLLBACK_REQUIREMENTS = [
    "code_version",
    "config_version",
    "migration_version",
    "strategy_version",
    "risk_version",
]
CANARY_STAGES = ["single_symbol", "small_symbol_set", "expanded_universe", "expanded_position_size"]
CANARY_OBSERVATION_METRICS = [
    "fill_rate",
    "reject_rate",
    "protection_order_success_rate",
    "risk_block_rate",
    "state_consistency",
    "latency",
    "drawdown",
]
DEPLOYMENT_TEST_REQUIREMENTS = [
    "config_load_test",
    "startup_test",
    "shutdown_test",
    "restart_recovery_test",
    "database_recovery_test",
    "protection_mode_test",
    "alert_test",
    "container_restart_test",
    "canary_release_test",
    "rollback_test",
]
DEPLOYMENT_FORBIDDEN_PATTERNS = [
    "shared_development_production_config",
    "direct_online_trial_after_code_change",
    "deployment_without_recovery",
    "live_without_protection_mode",
    "persistent_runtime_without_monitoring",
    "memory_as_only_source_of_truth",
    "execution_layer_depends_on_temp_script",
    "backtest_pollutes_live_database",
    "direct_development_to_production",
]
IMPLEMENTATION_ORDER = [
    "data layer",
    "indicator layer",
    "context layer",
    "signal layer",
    "risk layer",
    "execution layer",
    "backtest layer",
    "reporting layer",
    "monitoring layer",
    "live rollout",
]
BINANCE_CLIENT_POLICY = "deployment contract only; do not import or modify stable Binance client"


@dataclass(frozen=True)
class DeploymentCheckResult:
    passed: bool
    errors: list[str]
    warnings: list[str]
    protection_mode: bool = False


@dataclass(frozen=True)
class DeploymentPlan:
    environment: str
    config_profile: str
    uses_live_exchange: bool
    uses_testnet: bool
    config_files: list[str]
    secret_sources: list[str]
    enabled_processes: list[str]
    startup_checks: list[str]
    release_gates: list[str]
    rollback_items: list[str]


@dataclass(frozen=True)
class HealthSnapshot:
    database_writable: bool
    exchange_connected: bool
    market_data_fresh: bool
    event_bus_available: bool
    position_sync_ok: bool
    risk_state_ok: bool
    config_valid: bool
    critical_processes_alive: bool
    consecutive_rejects: int = 0
    consecutive_sync_failures: int = 0
    consecutive_protection_failures: int = 0
    abnormal_position_state: bool = False
    unknown_order_state: bool = False
    latency_ms: Mapping[str, int] | None = None


def validate_environment_isolation(plan: DeploymentPlan) -> DeploymentCheckResult:
    errors: list[str] = []
    warnings: list[str] = []
    environment = plan.environment.strip().lower()
    if environment not in DEPLOYMENT_ENVIRONMENTS:
        errors.append("unknown deployment environment")
    if environment == "production":
        if plan.config_profile != "production":
            errors.append("production must use production config profile")
        if not plan.uses_live_exchange:
            errors.append("production must use live exchange")
        if plan.uses_testnet:
            errors.append("production must not use testnet")
        if "plain_config_file" in plan.secret_sources:
            errors.append("production cannot use plain config file secrets")
    elif environment == "staging":
        if plan.config_profile != "staging":
            errors.append("staging must use staging config profile")
        if plan.uses_live_exchange and not plan.uses_testnet:
            errors.append("staging must use testnet or non-live exchange")
    elif environment == "development":
        if plan.uses_live_exchange:
            errors.append("development must not use live exchange")
        if plan.config_profile not in {"development", "dev"}:
            warnings.append("development should use development config profile")
    return DeploymentCheckResult(not errors, errors, warnings)


def validate_release_gates(gates: list[str]) -> DeploymentCheckResult:
    missing = _missing(RELEASE_GATES, gates)
    errors = [f"missing release gates: {missing}"] if missing else []
    return DeploymentCheckResult(not errors, errors, [])


def validate_rollback_plan(items: list[str]) -> DeploymentCheckResult:
    missing = _missing(ROLLBACK_REQUIREMENTS, items)
    errors = [f"missing rollback requirements: {missing}"] if missing else []
    return DeploymentCheckResult(not errors, errors, [])


def evaluate_deployment_readiness(plan: DeploymentPlan) -> DeploymentCheckResult:
    errors: list[str] = []
    warnings: list[str] = []
    isolation = validate_environment_isolation(plan)
    errors.extend(isolation.errors)
    warnings.extend(isolation.warnings)
    missing_configs = _missing(CONFIG_FILES, plan.config_files)
    if missing_configs:
        errors.append(f"missing config files: {missing_configs}")
    forbidden_secrets = sorted(set(plan.secret_sources) & set(SECRET_POLICY["forbidden"]))
    if forbidden_secrets:
        errors.append(f"forbidden secret sources: {forbidden_secrets}")
    missing_processes = _missing(DEPLOYMENT_PROCESS_UNITS, plan.enabled_processes)
    if missing_processes:
        errors.append(f"missing process units: {missing_processes}")
    missing_startup = _missing(STARTUP_SEQUENCE, plan.startup_checks)
    if missing_startup:
        errors.append(f"missing startup checks: {missing_startup}")
    release = validate_release_gates(plan.release_gates)
    rollback = validate_rollback_plan(plan.rollback_items)
    errors.extend(release.errors)
    errors.extend(rollback.errors)
    return DeploymentCheckResult(not errors, errors, warnings, protection_mode=bool(errors))


def evaluate_health_snapshot(snapshot: HealthSnapshot) -> DeploymentCheckResult:
    errors = _health_errors(snapshot)
    protection = should_enter_protection_mode(snapshot)
    return DeploymentCheckResult(not errors, errors, [], protection_mode=protection.passed)


def should_enter_protection_mode(snapshot: HealthSnapshot, threshold: int = 3) -> DeploymentCheckResult:
    errors = _health_errors(snapshot)
    if snapshot.consecutive_rejects >= threshold:
        errors.append("consecutive_rejects")
    if snapshot.consecutive_sync_failures >= threshold:
        errors.append("consecutive_sync_failures")
    if snapshot.consecutive_protection_failures >= threshold:
        errors.append("consecutive_protection_failures")
    if snapshot.abnormal_position_state:
        errors.append("abnormal_position_state")
    if snapshot.unknown_order_state:
        errors.append("unknown_order_state")
    return DeploymentCheckResult(bool(errors), errors, [], protection_mode=bool(errors))


def build_version_snapshot(
    *,
    code_version: str,
    strategy_version: str,
    risk_version: str,
    config_version: str,
    data_version: str,
    backtest_version: str,
    report_version: str,
) -> dict[str, str]:
    return {
        "code_version": code_version,
        "strategy_version": strategy_version,
        "risk_version": risk_version,
        "config_version": config_version,
        "data_version": data_version,
        "backtest_version": backtest_version,
        "report_version": report_version,
    }


def _health_errors(snapshot: HealthSnapshot) -> list[str]:
    errors: list[str] = []
    if not snapshot.database_writable:
        errors.append("database_not_writable")
    if not snapshot.exchange_connected:
        errors.append("exchange_unavailable")
    if not snapshot.market_data_fresh:
        errors.append("data_abnormal")
    if not snapshot.event_bus_available:
        errors.append("event_bus_unavailable")
    if not snapshot.position_sync_ok:
        errors.append("position_sync_failed")
    if not snapshot.risk_state_ok:
        errors.append("risk_abnormal")
    if not snapshot.config_valid:
        errors.append("config_invalid")
    if not snapshot.critical_processes_alive:
        errors.append("critical_process_down")
    return errors


def _missing(required: list[str], actual: list[str]) -> list[str]:
    actual_set = set(actual)
    return [item for item in required if item not in actual_set]
