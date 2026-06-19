import json
import subprocess
import sys


def test_describe_deployment_architecture_outputs_completed_20_sections():
    result = subprocess.run(
        [sys.executable, "scripts/describe_deployment_architecture.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    assert payload["architecture"] == "deployment_architecture"
    assert payload["environments"] == ["development", "staging", "production"]
    assert payload["startup_sequence"][0] == "load_config"
    assert payload["shutdown_sequence"][0] == "stop_accepting_new_signals"
    assert "database_not_writable" in payload["protection_mode_triggers"]
    assert payload["health_check_types"] == ["liveness", "readiness", "startup"]
    assert "local_unit_tests" in payload["release_gates"]
    assert "code_version" in payload["rollback_requirements"]
    assert "direct_development_to_production" in payload["forbidden_patterns"]
    assert payload["binance_client_policy"] == "deployment contract only; do not import or modify stable Binance client"
    assert payload["sample_readiness"]["passed"] is True
