from src.backtest.engine import BacktestBar
from src.signals.entry_chain_features import risk_reward_geometry_detail, risk_reward_geometry_score


def swing(kind, price):
    return type("Swing", (), {"kind": kind, "price": price})()


def test_risk_reward_detail_exposes_core_rr_fields():
    detail = risk_reward_geometry_detail(
        close=100.0,
        side="LONG",
        atr_value=1.0,
        atr_pct_value=0.01,
        swings=[swing("HIGH", 100.5)],
    )

    assert "score" in detail
    assert "net_tp1_r" in detail
    assert "stop_pct" in detail
    assert "tp1_pct" in detail
    assert "opposition_dist_r" in detail
    assert "rr_zero_reason" in detail


def test_risk_reward_detail_uses_one_point_two_r_tp1():
    detail = risk_reward_geometry_detail(
        close=100.0,
        side="LONG",
        atr_value=1.0,
        atr_pct_value=0.01,
        swings=[],
    )

    assert detail["stop_pct"] == 0.015
    assert detail["tp1_pct"] == 0.018
    assert detail["net_tp1_r"] == 1.133


def test_risk_reward_score_matches_detail_score():
    swings = [swing("LOW", 99.5)]

    score = risk_reward_geometry_score(100.0, "SHORT", 1.0, 0.01, swings)
    detail = risk_reward_geometry_detail(100.0, "SHORT", 1.0, 0.01, swings)

    assert score == detail["score"]


def test_risk_reward_low_atr_min_stop_no_longer_flags_low_net_r_at_one_point_two_r():
    detail = risk_reward_geometry_detail(
        close=100.0,
        side="LONG",
        atr_value=0.01,
        atr_pct_value=0.0001,
        swings=[],
    )

    assert detail["net_tp1_r"] == 1.0
    assert detail["rr_zero_reason"] != "NET_TP1_R_TOO_LOW"
