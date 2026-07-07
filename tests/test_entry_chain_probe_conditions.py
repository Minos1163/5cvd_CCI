from src.signals.entry_chain import check_probe_conditions


def test_probe_allowed_when_score_and_components_pass():
    component_points = {
        "fibonacci_location": 13.0,
        "price_action_structure": 9.0,
        "risk_reward_geometry": 4.0,
        "trend_ema_context": 11.0,
        "cci_momentum_quality": 9.0,
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
            "trend_ema_context": 11.0,
            "cci_momentum_quality": 9.0,
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
            "trend_ema_context": 11.0,
            "cci_momentum_quality": 9.0,
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


def test_probe_rejected_when_trend_and_momentum_quality_are_both_weak():
    allowed, reason = check_probe_conditions(
        score=80.0,
        side="SHORT",
        component_points={
            "fibonacci_location": 18.0,
            "price_action_structure": 21.0,
            "risk_reward_geometry": 5.0,
            "trend_ema_context": 8.0,
            "cci_momentum_quality": 8.5,
        },
        rr_detail=None,
        config={
            "enabled": True,
            "min_score": 72.0,
            "min_fib_score": 12.0,
            "min_pa_score": 10.0,
            "min_rr_score": 4.0,
            "trend_or_cci_min_ema_score": 10.0,
            "trend_or_cci_min_cci_score": 9.0,
        },
    )

    assert allowed is False
    assert reason == "PROBE_BELOW_TREND_OR_CCI_QUALITY_GATE"


def test_probe_rejected_when_low_score_has_weak_quality_compensation():
    allowed, reason = check_probe_conditions(
        score=72.0,
        side="LONG",
        component_points={
            "fibonacci_location": 13.0,
            "price_action_structure": 21.0,
            "risk_reward_geometry": 5.0,
            "trend_ema_context": 8.0,
            "cci_momentum_quality": 7.0,
        },
        rr_detail=None,
        config={
            "enabled": True,
            "min_score": 72.0,
            "min_fib_score": 12.0,
            "min_pa_score": 10.0,
            "min_rr_score": 4.0,
            "trend_or_cci_min_ema_score": 10.0,
            "trend_or_cci_min_cci_score": 9.0,
            "low_score_quality_veto_score": 75.0,
            "low_score_quality_min_ema_score": 10.0,
            "low_score_quality_min_cci_score": 7.0,
        },
    )

    assert allowed is False
    assert reason == "PROBE_LOW_SCORE_QUALITY_VETO"


def test_probe_allowed_when_low_score_quality_is_compensated():
    allowed, reason = check_probe_conditions(
        score=74.5,
        side="LONG",
        component_points={
            "fibonacci_location": 13.0,
            "price_action_structure": 21.0,
            "risk_reward_geometry": 5.0,
            "trend_ema_context": 11.0,
            "cci_momentum_quality": 9.0,
        },
        rr_detail=None,
        config={
            "enabled": True,
            "min_score": 72.0,
            "min_fib_score": 12.0,
            "min_pa_score": 10.0,
            "min_rr_score": 4.0,
            "trend_or_cci_min_ema_score": 10.0,
            "trend_or_cci_min_cci_score": 9.0,
            "low_score_quality_veto_score": 75.0,
            "low_score_quality_min_ema_score": 10.0,
            "low_score_quality_min_cci_score": 7.0,
        },
    )

    assert allowed is True
    assert reason == ""


def test_probe_rejected_when_below_elite_min_score_even_if_components_pass():
    allowed, reason = check_probe_conditions(
        score=72.75,
        side="SHORT",
        component_points={
            "fibonacci_location": 13.0,
            "price_action_structure": 12.0,
            "risk_reward_geometry": 6.5,
            "trend_ema_context": 13.25,
            "cci_momentum_quality": 10.0,
        },
        rr_detail=None,
        config={
            "enabled": True,
            "min_score": 72.0,
            "min_fib_score": 12.0,
            "min_pa_score": 10.0,
            "min_rr_score": 4.0,
            "elite_probe_enabled": True,
            "elite_probe_min_score": 75.0,
        },
    )

    assert allowed is False
    assert reason == "PROBE_LOW_SCORE_ELITE_VETO"


def test_probe_rejected_when_elite_structure_is_not_strong_enough():
    allowed, reason = check_probe_conditions(
        score=80.0,
        side="SHORT",
        component_points={
            "fibonacci_location": 13.0,
            "price_action_structure": 12.0,
            "risk_reward_geometry": 6.5,
            "trend_ema_context": 13.25,
            "cci_momentum_quality": 10.0,
        },
        rr_detail=None,
        config={
            "enabled": True,
            "min_score": 72.0,
            "min_fib_score": 12.0,
            "min_pa_score": 10.0,
            "min_rr_score": 4.0,
            "elite_probe_enabled": True,
            "elite_probe_min_score": 75.0,
            "elite_probe_min_pa_score": 18.0,
            "elite_probe_min_fib_score": 15.0,
            "elite_probe_trend_min_ema_score": 15.0,
            "elite_probe_trend_min_structure_sum": 30.0,
        },
    )

    assert allowed is False
    assert reason == "PROBE_BELOW_ELITE_STRUCTURE_GATE"


def test_probe_allowed_when_elite_structure_or_trend_compensation_passes():
    config = {
        "enabled": True,
        "min_score": 72.0,
        "min_fib_score": 12.0,
        "min_pa_score": 10.0,
        "min_rr_score": 4.0,
        "elite_probe_enabled": True,
        "elite_probe_min_score": 75.0,
        "elite_probe_min_pa_score": 18.0,
        "elite_probe_min_fib_score": 15.0,
        "elite_probe_trend_min_ema_score": 15.0,
        "elite_probe_trend_min_structure_sum": 30.0,
    }
    structure_allowed, structure_reason = check_probe_conditions(
        score=80.0,
        side="SHORT",
        component_points={
            "fibonacci_location": 15.0,
            "price_action_structure": 18.0,
            "risk_reward_geometry": 5.0,
            "trend_ema_context": 12.0,
            "cci_momentum_quality": 10.0,
        },
        rr_detail=None,
        config=config,
    )
    trend_allowed, trend_reason = check_probe_conditions(
        score=80.0,
        side="SHORT",
        component_points={
            "fibonacci_location": 13.0,
            "price_action_structure": 17.0,
            "risk_reward_geometry": 5.0,
            "trend_ema_context": 15.0,
            "cci_momentum_quality": 10.0,
        },
        rr_detail=None,
        config=config,
    )

    assert structure_allowed is True
    assert structure_reason == ""
    assert trend_allowed is True
    assert trend_reason == ""


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
