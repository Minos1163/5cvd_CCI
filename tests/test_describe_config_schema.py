import json
import subprocess
import sys


def test_describe_config_schema_outputs_completed_11_sections():
    completed = subprocess.run(
        [sys.executable, "scripts/describe_config_schema.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["config_root"] == "configs"
    assert payload["config_files"] == [
        "strategy.yaml",
        "risk.yaml",
        "execution.yaml",
        "universe.yaml",
        "logging.yaml",
        "backtest.yaml",
    ]
    assert payload["precedence"] == ["default", "environment", "user_override"]
    assert payload["version_required"] is True
    assert payload["read_only_policy"] == "modules may read config but must not mutate it"
    assert payload["hot_update"]["allowed"][0] == "logging.level"
    assert "strategy" in payload["hot_update"]["forbidden_prefixes"]
    assert "magic_numbers" in payload["forbidden"]
