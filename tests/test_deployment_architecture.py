from src.deployment.deployment_architecture import (
    CANARY_STAGES,
    CONFIG_FILES,
    DEPLOYMENT_ENVIRONMENTS,
    DEPLOYMENT_FORBIDDEN_PATTERNS,
    DEPLOYMENT_LAYERS,
    DEPLOYMENT_PROCESS_UNITS,
    DEPLOYMENT_TARGETS,
    DEPLOYMENT_TEST_REQUIREMENTS,
    FAILURE_MODES,
    HEALTH_CHECKS,
    HEALTH_CHECK_TYPES,
    LOG_DIRECTORIES,
    MONITORING_METRICS,
    PROTECTION_MODE_ALLOWED_ACTIONS,
    PROTECTION_MODE_TRIGGERS,
    RECOVERY_STATE_FIELDS,
    RELEASE_GATES,
    ROLLBACK_REQUIREMENTS,
    SECRET_POLICY,
    SHUTDOWN_SEQUENCE,
    STARTUP_SEQUENCE,
    VERSION_SNAPSHOT_FIELDS,
    DeploymentPlan,
    HealthSnapshot,
    build_version_snapshot,
    evaluate_deployment_readiness,
    evaluate_health_snapshot,
    should_enter_protection_mode,
    validate_environment_isolation,
    validate_release_gates,
    validate_rollback_plan,
)


def valid_plan(**overrides) -> DeploymentPlan:
    values = {
        "environment": "production",
        "config_profile": "production",
        "uses_live_exchange": True,
        "uses_testnet": False,
        "config_files": list(CONFIG_FILES),
        "secret_sources": ["environment_variables"],
        "enabled_processes": list(DEPLOYMENT_PROCESS_UNITS),
        "startup_checks": list(STARTUP_SEQUENCE),
        "release_gates": list(RELEASE_GATES),
        "rollback_items": list(ROLLBACK_REQUIREMENTS),
    }
    values.update(overrides)
    return DeploymentPlan(**values)


def healthy_snapshot(**overrides) -> HealthSnapshot:
    values = {
        "database_writable": True,
        "exchange_connected": True,
        "market_data_fresh": True,
        "event_bus_available": True,
        "position_sync_ok": True,
        "risk_state_ok": True,
        "config_valid": True,
        "critical_processes_alive": True,
        "consecutive_rejects": 0,
        "consecutive_sync_failures": 0,
        "consecutive_protection_failures": 0,
        "abnormal_position_state": False,
        "unknown_order_state": False,
        "latency_ms": {"market_data": 100, "strategy_loop": 100},
    }
    values.update(overrides)
    return HealthSnapshot(**values)


def test_deployment_contract_lists_doc_sections():
    assert DEPLOYMENT_ENVIRONMENTS == ["development", "staging", "production"]
    assert DEPLOYMENT_LAYERS == [
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
    assert DEPLOYMENT_PROCESS_UNITS == [
        "market data daemon",
        "strategy engine",
        "execution engine",
        "risk supervisor",
        "portfolio sync daemon",
        "backtest runner",
        "report generator",
        "health monitor",
    ]
    assert DEPLOYMENT_TARGETS[:3] == ["full_strategy", "single_symbol_strategy", "backtest_job"]
    assert CONFIG_FILES == [
        "strategy.yaml",
        "risk.yaml",
        "execution.yaml",
        "universe.yaml",
        "logging.yaml",
        "backtest.yaml",
        "database.yaml",
        "monitoring.yaml",
    ]
    assert SECRET_POLICY["forbidden"][0] == "code_repository"
    assert LOG_DIRECTORIES[-1] == "logs/system"
    assert STARTUP_SEQUENCE[0] == "load_config"
    assert STARTUP_SEQUENCE[-1] == "enter_trading_runtime"
    assert SHUTDOWN_SEQUENCE[0] == "stop_accepting_new_signals"
    assert "current_positions" in RECOVERY_STATE_FIELDS
    assert "event_bus_blocked" in FAILURE_MODES
    assert PROTECTION_MODE_ALLOWED_ACTIONS == [
        "block_new_entries",
        "allow_reductions",
        "allow_stop_loss_exit",
        "allow_position_sync",
        "allow_logs_and_audit",
        "allow_manual_inspection",
    ]
    assert "database_not_writable" in PROTECTION_MODE_TRIGGERS
    assert "market_data_latency" in MONITORING_METRICS
    assert "database_connection" in HEALTH_CHECKS
    assert HEALTH_CHECK_TYPES == ["liveness", "readiness", "startup"]
    assert CANARY_STAGES[0] == "single_symbol"
    assert "rollback_test" in DEPLOYMENT_TEST_REQUIREMENTS
    assert "direct_development_to_production" in DEPLOYMENT_FORBIDDEN_PATTERNS


def test_environment_isolation_rejects_shared_live_config_or_secret_files():
    plan = DeploymentPlan(
        environment="production",
        config_profile="dev",
        uses_live_exchange=False,
        uses_testnet=False,
        config_files=["strategy.yaml", "risk.yaml"],
        secret_sources=["plain_config_file"],
        enabled_processes=["strategy engine"],
        startup_checks=["load_config"],
        release_gates=["local_unit_tests"],
        rollback_items=["code_version"],
    )
    result = validate_environment_isolation(plan)
    assert result.passed is False
    assert "production must use production config profile" in result.errors
    assert "production cannot use plain config file secrets" in result.errors
    assert "production must use live exchange" in result.errors


def test_development_must_not_use_live_exchange_and_staging_uses_safe_exchange():
    development = valid_plan(environment="development", config_profile="development", uses_live_exchange=True)
    assert validate_environment_isolation(development).passed is False

    staging = valid_plan(
        environment="staging",
        config_profile="staging",
        uses_live_exchange=False,
        uses_testnet=True,
    )
    assert validate_environment_isolation(staging).passed is True


def test_readiness_requires_all_startup_checks_release_gates_and_rollback_items():
    result = evaluate_deployment_readiness(valid_plan())
    assert result.passed is True
    assert result.protection_mode is False

    missing = valid_plan(startup_checks=["load_config"])
    failed = evaluate_deployment_readiness(missing)
    assert failed.passed is False
    assert "missing startup checks" in failed.errors[0]

    no_gate = valid_plan(release_gates=["local_unit_tests"])
    assert validate_release_gates(no_gate.release_gates).passed is False

    no_rollback = valid_plan(rollback_items=["code_version"])
    assert validate_rollback_plan(no_rollback.rollback_items).passed is False


def test_health_snapshot_enters_protection_mode_on_runtime_failures():
    snapshot = healthy_snapshot(database_writable=False)
    result = evaluate_health_snapshot(snapshot)
    assert result.passed is False
    assert result.protection_mode is True
    assert "database_not_writable" in result.errors
    assert should_enter_protection_mode(snapshot).passed is True


def test_consecutive_failures_and_unknown_state_trigger_protection_mode():
    assert should_enter_protection_mode(healthy_snapshot(consecutive_rejects=3)).passed is True
    assert should_enter_protection_mode(healthy_snapshot(consecutive_sync_failures=3)).passed is True
    assert should_enter_protection_mode(healthy_snapshot(consecutive_protection_failures=3)).passed is True
    assert should_enter_protection_mode(healthy_snapshot(abnormal_position_state=True)).passed is True
    assert should_enter_protection_mode(healthy_snapshot(unknown_order_state=True)).passed is True
    assert should_enter_protection_mode(healthy_snapshot()).passed is False


def test_version_release_and_rollback_contracts_are_explicit():
    snapshot = build_version_snapshot(
        code_version="abc",
        strategy_version="s1",
        risk_version="r1",
        config_version="c1",
        data_version="d1",
        backtest_version="b1",
        report_version="rp1",
    )
    assert list(snapshot) == VERSION_SNAPSHOT_FIELDS
    assert validate_release_gates(RELEASE_GATES).passed is True
    assert validate_rollback_plan(ROLLBACK_REQUIREMENTS).passed is True
