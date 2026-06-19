import json
import subprocess
import sys


def test_describe_project_rules_outputs_json():
    result = subprocess.run(
        [sys.executable, "scripts/describe_project_rules.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    assert payload["project"]["priority"][0] == "stability"
    assert payload["philosophy"]["timeframe_roles"]["4h"] == "background"
    assert payload["universe"]["max_simultaneous_positions"] == 5


def test_describe_project_rules_outputs_expanded_strategy_philosophy():
    result = subprocess.run(
        [sys.executable, "scripts/describe_project_rules.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    philosophy = payload["philosophy"]
    assert philosophy["strategy_identity"]["style"] == "multi_timeframe_trend_following"
    assert philosophy["first_principles"][0] == "risk_before_return"
    assert philosophy["decision_priority"][0] == "data_quality"
    assert philosophy["allowed_trade_types"] == ["PROBE", "DIRECT"]
    assert "single_abnormal_candle" in philosophy["anti_noise_rules"]
    assert "add_rule_for_single_failed_sample" in philosophy["anti_overfit_rules"]
    assert "increase_tolerance" in philosophy["uncertainty_forbidden_actions"]
    assert "complex_watchlist_promotion_chain" in philosophy["forbidden_patterns"]


def test_describe_project_rules_outputs_expanded_project_overview_contract():
    result = subprocess.run(
        [sys.executable, "scripts/describe_project_rules.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    project = payload["project"]

    assert project["name"] == "多周期主流虚拟币趋势交易系统"
    assert project["english_name"] == "crypto-mtf-trend-strategy"
    assert project["timeframe_roles"]["4h"] == "background_reference_only"
    assert project["entry_forms"]["PROBE"]["size_ratio"] == 0.25
    assert project["system_layers"][-1] == "monitoring"
    assert project["module_dependency_flow"] == project["system_layers"]
    assert project["unified_contracts"] == [
        "data",
        "indicator",
        "event",
        "state_machine",
        "risk",
        "position",
        "execution",
        "backtest",
        "config",
        "logging",
    ]
    assert project["implementation_principles"][0] == "contract_first"
    assert "stable_position_and_order_recovery" in project["operational_success_standards"]
