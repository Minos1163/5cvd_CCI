from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.deployment.deployment_architecture import (
    BINANCE_CLIENT_POLICY,
    CANARY_OBSERVATION_METRICS,
    CANARY_STAGES,
    CONFIG_FILES,
    CONTAINER_SERVICES,
    DEPLOYMENT_ENVIRONMENTS,
    DEPLOYMENT_FORBIDDEN_PATTERNS,
    DEPLOYMENT_LAYERS,
    DEPLOYMENT_PROCESS_UNITS,
    DEPLOYMENT_TARGETS,
    DEPLOYMENT_TEST_REQUIREMENTS,
    FAILURE_MODES,
    HEALTH_CHECKS,
    HEALTH_CHECK_TYPES,
    IMPLEMENTATION_ORDER,
    LOG_DIRECTORIES,
    MONITORING_METRICS,
    OBSERVABILITY_QUESTIONS,
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
    evaluate_deployment_readiness,
)


def _sample_readiness() -> dict:
    plan = DeploymentPlan(
        environment="production",
        config_profile="production",
        uses_live_exchange=True,
        uses_testnet=False,
        config_files=list(CONFIG_FILES),
        secret_sources=["environment_variables"],
        enabled_processes=list(DEPLOYMENT_PROCESS_UNITS),
        startup_checks=list(STARTUP_SEQUENCE),
        release_gates=list(RELEASE_GATES),
        rollback_items=list(ROLLBACK_REQUIREMENTS),
    )
    return asdict(evaluate_deployment_readiness(plan))


def main() -> None:
    payload = {
        "architecture": "deployment_architecture",
        "environments": DEPLOYMENT_ENVIRONMENTS,
        "layers": DEPLOYMENT_LAYERS,
        "process_units": DEPLOYMENT_PROCESS_UNITS,
        "deployment_targets": DEPLOYMENT_TARGETS,
        "config_files": CONFIG_FILES,
        "secret_policy": SECRET_POLICY,
        "log_directories": LOG_DIRECTORIES,
        "startup_sequence": STARTUP_SEQUENCE,
        "shutdown_sequence": SHUTDOWN_SEQUENCE,
        "recovery_state_fields": RECOVERY_STATE_FIELDS,
        "failure_modes": FAILURE_MODES,
        "protection_mode_allowed_actions": PROTECTION_MODE_ALLOWED_ACTIONS,
        "protection_mode_triggers": PROTECTION_MODE_TRIGGERS,
        "monitoring_metrics": MONITORING_METRICS,
        "observability_questions": OBSERVABILITY_QUESTIONS,
        "container_services": CONTAINER_SERVICES,
        "health_checks": HEALTH_CHECKS,
        "health_check_types": HEALTH_CHECK_TYPES,
        "version_snapshot_fields": VERSION_SNAPSHOT_FIELDS,
        "release_gates": RELEASE_GATES,
        "rollback_requirements": ROLLBACK_REQUIREMENTS,
        "canary_stages": CANARY_STAGES,
        "canary_observation_metrics": CANARY_OBSERVATION_METRICS,
        "deployment_test_requirements": DEPLOYMENT_TEST_REQUIREMENTS,
        "forbidden_patterns": DEPLOYMENT_FORBIDDEN_PATTERNS,
        "implementation_order": IMPLEMENTATION_ORDER,
        "binance_client_policy": BINANCE_CLIENT_POLICY,
        "sample_readiness": _sample_readiness(),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
