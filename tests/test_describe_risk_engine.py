import json
import subprocess
import sys


def test_describe_risk_engine_outputs_completed_17_sections():
    result = subprocess.run(
        [sys.executable, "scripts/describe_risk_engine.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["engine"] == "risk_engine"
    assert payload["responsibility"] == "pre_trade_risk_gate_and_risk_constraints"
    assert payload["risk_levels"] == ["LOW", "NORMAL", "HIGH", "EXTREME", "BLOCKED"]
    assert payload["decision_flow"][0] == "check_data_quality"
    assert payload["decision_flow"][-1] == "output_risk_result"
    assert "quality_flag" in payload["required_inputs"]
    assert "metrics_snapshot" in payload["output_fields"]
    assert payload["default_limits"]["daily_loss_limit_pct"] == 0.05
    assert payload["score_components"] == [
        "account_risk_score",
        "portfolio_risk_score",
        "symbol_risk_score",
        "volatility_risk_score",
        "cooldown_risk_score",
        "data_quality_risk_score",
    ]
    assert "risk_reason" in payload["snapshot_fields"]
    assert payload["relationships"]["position module"] == "calculates final_notional and final_qty"
    assert payload["forbidden_actions"]["risk layer"][0] == "generate_trade_signal"
    assert "must_not_recalculate_risk" in payload["forbidden_actions"]["execution layer"]
    assert payload["sample"]["direct"]["risk_level"] == "NORMAL"
    assert payload["sample"]["probe"]["position_size_factor"] == 0.25
    assert payload["sample"]["blocked"]["risk_reason"] == "DAILY_LOSS_LIMIT_REACHED"
