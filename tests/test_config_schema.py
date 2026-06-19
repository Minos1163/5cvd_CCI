from pathlib import Path

from src.config.config_schema import (
    CONFIG_FILES,
    CONFIG_FORBIDDEN_RULES,
    CONFIG_PRECEDENCE,
    CONFIG_REQUIRED_FIELDS,
    CONFIG_ROOT,
    HOT_UPDATE_ALLOWED_PATHS,
    HOT_UPDATE_FORBIDDEN_PREFIXES,
    REQUIRED_TOP_LEVEL_KEYS,
    freeze_config,
    is_hot_update_allowed,
    merge_config_layers,
    validate_config_directory,
)


def test_config_schema_lists_required_files_sections_and_precedence():
    assert CONFIG_ROOT == Path("configs")
    assert CONFIG_FILES == [
        "strategy.yaml",
        "risk.yaml",
        "execution.yaml",
        "universe.yaml",
        "logging.yaml",
        "backtest.yaml",
    ]
    assert REQUIRED_TOP_LEVEL_KEYS == {
        "strategy.yaml": ["version", "strategy", "indicators", "entry", "probe"],
        "risk.yaml": ["version", "risk", "stop", "take_profit"],
        "execution.yaml": ["version", "execution", "slippage"],
        "universe.yaml": ["version", "universe"],
        "logging.yaml": ["version", "logging"],
        "backtest.yaml": ["version", "backtest"],
    }
    assert CONFIG_PRECEDENCE == ["default", "environment", "user_override"]
    assert CONFIG_REQUIRED_FIELDS["strategy.yaml"][0] == "version"
    assert "strategy.timeframes.trigger" in CONFIG_REQUIRED_FIELDS["strategy.yaml"]
    assert "risk.risk_per_trade_pct" in CONFIG_REQUIRED_FIELDS["risk.yaml"]
    assert "execution.exchange" in CONFIG_REQUIRED_FIELDS["execution.yaml"]


def test_existing_configs_validate_against_schema():
    result = validate_config_directory(Path("configs"))
    assert result.passed is True
    assert result.errors == []


def test_freeze_config_returns_read_only_nested_mapping():
    frozen = freeze_config({"risk": {"risk_per_trade_pct": 0.01}})
    assert frozen["risk"]["risk_per_trade_pct"] == 0.01
    try:
        frozen["risk"] = {}
    except TypeError:
        pass
    else:
        raise AssertionError("top-level config must be read-only")
    try:
        frozen["risk"]["risk_per_trade_pct"] = 0.02
    except TypeError:
        pass
    else:
        raise AssertionError("nested config must be read-only")


def test_merge_config_layers_applies_default_environment_user_precedence_without_mutating_inputs():
    default = {"risk": {"risk_per_trade_pct": 0.01, "daily_loss_limit_pct": 0.05}}
    environment = {"risk": {"risk_per_trade_pct": 0.008}}
    user = {"risk": {"daily_loss_limit_pct": 0.03}}
    merged = merge_config_layers(default, environment, user)
    assert merged["risk"]["risk_per_trade_pct"] == 0.008
    assert merged["risk"]["daily_loss_limit_pct"] == 0.03
    assert default["risk"]["risk_per_trade_pct"] == 0.01


def test_hot_update_policy_allows_logging_and_monitoring_only():
    assert HOT_UPDATE_ALLOWED_PATHS == ["logging.level", "logging.save_json", "logging.save_csv", "monitoring"]
    assert HOT_UPDATE_FORBIDDEN_PREFIXES == [
        "strategy",
        "indicators",
        "entry",
        "probe",
        "direct",
        "risk",
        "stop",
        "take_profit",
        "execution",
    ]
    assert is_hot_update_allowed("logging.level") is True
    assert is_hot_update_allowed("logging.save_json") is True
    assert is_hot_update_allowed("monitoring.latency_alert_ms") is True
    assert is_hot_update_allowed("strategy.timeframes.trigger") is False
    assert is_hot_update_allowed("risk.risk_per_trade_pct") is False
    assert is_hot_update_allowed("execution.leverage") is False


def test_config_forbidden_rules_match_doc_boundary():
    assert CONFIG_FORBIDDEN_RULES == [
        "hardcoded_parameters",
        "magic_numbers",
        "duplicate_parameter_definitions",
        "module_mutates_config",
        "hot_update_strategy_core",
    ]
