import json

from src.observability.dry_run_summary import DryRunSummary, write_summary


def test_write_summary_contains_targets_and_decision_counts(tmp_path):
    summary = DryRunSummary(target_tier="conservative")
    summary.record_decision({"action": "NO_TRADE", "symbol": "BNBUSDT", "score": 50, "reasons": ["LOW_SCORE"]})
    summary.record_decision({"action": "PROBE", "symbol": "SOLUSDT", "score": 75, "reasons": []})
    summary.record_stress({"symbol": "SOLUSDT", "action": "ALLOW", "estimated_loss_pct": 0.03})

    write_summary(tmp_path / "summary.json", summary, orders_submitted=0, data_health="OK")

    payload = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert payload["target_tier"] == "conservative"
    assert payload["decision_counts"]["NO_TRADE"] == 1
    assert payload["decision_counts"]["PROBE"] == 1
    assert payload["orders_submitted"] == 0
    assert payload["data_health"] == "OK"
    assert payload["stress_risk"][-1]["estimated_loss_pct"] == 0.03


def test_summary_tracks_near_misses():
    summary = DryRunSummary(target_tier="aggressive")
    summary.record_near_miss(
        {
            "timestamp": 1,
            "symbol": "CCUSDT",
            "action": "WATCH",
            "score": 90.59,
            "primary_reason": "HIGH_BETA_PROBE_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_3.0",
        }
    )

    payload = summary.to_dict(orders_submitted=0, data_health="OK")

    assert payload["near_miss_count"] == 1
    assert payload["near_miss_by_reason"] == {"HIGH_BETA_PROBE_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_3.0": 1}
    assert payload["recent_near_misses"] == [
        {
            "timestamp": 1,
            "symbol": "CCUSDT",
            "action": "WATCH",
            "score": 90.59,
            "primary_reason": "HIGH_BETA_PROBE_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_3.0",
        }
    ]


def test_summary_splits_rejection_reasons_by_layer():
    summary = DryRunSummary(target_tier="aggressive")
    summary.record_decision(
        {
            "action": "WATCH",
            "symbol": "LINKUSDT",
            "score": 87.3,
            "reasons": [
                "FIB_PA_ARCHITECTURE_WEIGHTS",
                "DIRECT_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_2.0",
                "PROBE_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_2.0",
            ],
        }
    )
    summary.record_decision(
        {
            "action": "NO_TRADE",
            "symbol": "TRXUSDT",
            "score": 77.7,
            "reasons": ["FIB_PA_ARCHITECTURE_WEIGHTS", "DAILY_TRADE_BUDGET_USED"],
        }
    )

    payload = summary.to_dict(orders_submitted=0, data_health="OK")

    assert payload["gate_rejections_by_layer"]["direct"] == 1
    assert payload["gate_rejections_by_layer"]["probe"] == 1
    assert payload["gate_rejections_by_layer"]["budget"] == 1
    assert payload["gate_rejections_by_layer_reason"]["probe"] == {
        "PROBE_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_2.0": 1
    }


def test_summary_includes_assumptions_and_latest_portfolio_exposure():
    summary = DryRunSummary(target_tier="aggressive", assumptions={"fee_bps": 5.0, "slippage_bps": 5.0})
    summary.record_portfolio_snapshot({"total_exposure_pct": 0.6, "net_side_exposure_pct": -0.2, "open_position_count": 2})

    payload = summary.to_dict(orders_submitted=0, data_health="OK")

    assert payload["dry_run_assumptions"] == {"fee_bps": 5.0, "slippage_bps": 5.0}
    assert payload["latest_portfolio_exposure"] == {
        "total_exposure_pct": 0.6,
        "net_side_exposure_pct": -0.2,
        "open_position_count": 2,
    }
