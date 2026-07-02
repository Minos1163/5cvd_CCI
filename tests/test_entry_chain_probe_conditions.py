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


def test_probe_rejected_when_price_action_below_configured_minimum():
    allowed, reason = check_probe_conditions(
        score=80.0,
        side="LONG",
        component_points={
            "fibonacci_location": 18.0,
            "price_action_structure": 8.0,
            "risk_reward_geometry": 6.5,
        },
        rr_detail={"net_tp1_r": 1.1},
        config={
            "enabled": True,
            "min_score": 72.0,
            "min_fib_score": 12.0,
            "min_pa_score": 10.0,
            "min_rr_net_r": 0.9,
        },
    )

    assert allowed is False
    assert reason == "PROBE_BELOW_PRICE_ACTION_STRUCTURE_MINIMUM_GAP_2.0"


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


def test_probe_rejected_when_rr_score_is_below_configured_minimum_without_detail():
    allowed, reason = check_probe_conditions(
        score=88.0,
        side="SHORT",
        component_points={
            "fibonacci_location": 18.0,
            "price_action_structure": 21.0,
            "risk_reward_geometry": 3.5,
        },
        rr_detail=None,
        config={
            "enabled": True,
            "min_score": 72.0,
            "min_fib_score": 12.0,
            "min_pa_score": 10.0,
            "min_rr_score": 4.0,
        },
    )

    assert allowed is False
    assert reason == "PROBE_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_0.5"


def test_high_beta_probe_rejected_when_cci_is_too_low():
    allowed, reason = check_probe_conditions(
        score=86.0,
        side="LONG",
        component_points={
            "fibonacci_location": 18.0,
            "price_action_structure": 16.0,
            "risk_reward_geometry": 6.0,
            "cci_momentum_quality": 8.5,
            "trend_ema_context": 14.0,
        },
        rr_detail=None,
        config={
            "enabled": True,
            "symbol": "LABUSDT",
            "min_score": 72.0,
            "min_fib_score": 12.0,
            "min_pa_score": 10.0,
            "min_rr_score": 4.0,
            "high_beta_min_rr_score": 5.0,
            "high_beta_min_pa_score": 12.0,
            "high_beta_min_cci_score": 9.0,
            "high_beta_min_ema_score": 12.0,
        },
    )

    assert allowed is False
    assert reason == "HIGH_BETA_PROBE_BELOW_CCI_MOMENTUM_QUALITY_MINIMUM_GAP_0.5"


def test_high_beta_probe_rejected_when_ema_context_is_too_low():
    allowed, reason = check_probe_conditions(
        score=86.0,
        side="LONG",
        component_points={
            "fibonacci_location": 18.0,
            "price_action_structure": 16.0,
            "risk_reward_geometry": 6.0,
            "cci_momentum_quality": 10.0,
            "trend_ema_context": 11.0,
        },
        rr_detail=None,
        config={
            "enabled": True,
            "symbol": "HYPEUSDT",
            "min_score": 72.0,
            "min_fib_score": 12.0,
            "min_pa_score": 10.0,
            "min_rr_score": 4.0,
            "high_beta_min_rr_score": 5.0,
            "high_beta_min_pa_score": 12.0,
            "high_beta_min_cci_score": 9.0,
            "high_beta_min_ema_score": 12.0,
        },
    )

    assert allowed is False
    assert reason == "HIGH_BETA_PROBE_BELOW_TREND_EMA_CONTEXT_MINIMUM_GAP_1.0"
