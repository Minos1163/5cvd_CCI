from src.risk.stress_simulator import estimate_stress_loss_pct, stress_decision


def test_estimate_stress_loss_pct_scales_with_exposure_and_leverage():
    loss = estimate_stress_loss_pct(exposure_pct=0.30, leverage=5, adverse_move_pct=0.10)

    assert round(loss, 4) == 0.15


def test_stress_decision_blocks_when_loss_exceeds_threshold():
    decision = stress_decision(exposure_pct=0.30, leverage=5, adverse_move_pct=0.20, max_loss_pct=0.25)

    assert decision["action"] == "BLOCK"
    assert decision["estimated_loss_pct"] == 0.30


def test_stress_decision_allows_when_loss_is_within_threshold():
    decision = stress_decision(exposure_pct=0.10, leverage=3, adverse_move_pct=0.10, max_loss_pct=0.25)

    assert decision["action"] == "ALLOW"
    assert decision["estimated_loss_pct"] == 0.03

