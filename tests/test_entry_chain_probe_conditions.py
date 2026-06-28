from src.signals.entry_chain import check_probe_conditions


def test_probe_allowed_when_score_and_components_pass():
    component_points = {
        "fibonacci_location": 13.0,
        "price_action_structure": 9.0,
        "risk_reward_geometry": 4.0,
    }
    rr_detail = {"net_tp1_r": 1.0}

    allowed, reason = check_probe_conditions(
        score=74.0,
        side="SHORT",
        component_points=component_points,
        rr_detail=rr_detail,
        config={
            "enabled": True,
            "min_score": 72.0,
            "min_fib_score": 12.0,
            "min_pa_score": 6.0,
            "min_rr_net_r": 0.9,
        },
    )

    assert allowed is True
    assert reason == ""


def test_probe_rejected_when_fib_is_too_low():
    component_points = {
        "fibonacci_location": 9.0,
        "price_action_structure": 21.0,
        "risk_reward_geometry": 5.0,
    }
    rr_detail = {"net_tp1_r": 1.1}

    allowed, reason = check_probe_conditions(
        score=82.0,
        side="LONG",
        component_points=component_points,
        rr_detail=rr_detail,
        config={
            "enabled": True,
            "min_score": 72.0,
            "min_fib_score": 12.0,
            "min_pa_score": 6.0,
            "min_rr_net_r": 0.9,
        },
    )

    assert allowed is False
    assert reason == "PROBE_BELOW_FIBONACCI_LOCATION_MINIMUM_GAP_3.0"


def test_probe_rejected_when_net_r_is_too_low():
    allowed, reason = check_probe_conditions(
        score=80.0,
        side="LONG",
        component_points={
            "fibonacci_location": 18.0,
            "price_action_structure": 21.0,
            "risk_reward_geometry": 3.5,
        },
        rr_detail={"net_tp1_r": 0.72},
        config={
            "enabled": True,
            "min_score": 72.0,
            "min_fib_score": 12.0,
            "min_pa_score": 6.0,
            "min_rr_net_r": 0.9,
        },
    )

    assert allowed is False
    assert reason == "PROBE_BELOW_RR_NET_R_MINIMUM_GAP_0.2"
