from src.signals.ema_scorer import (
    EmaContext,
    ema_direction_gate,
    ema_trend_state,
    score_ema50_quality,
    score_ema_momentum,
)


def test_ema200_hard_gate_rejects_countertrend_long():
    context = EmaContext(
        close=99,
        ema_9=101,
        ema_21=100,
        ema_50=100,
        ema_200=100,
        ema50_slope=0.001,
        ema9_21_gap=0.01,
        bars_since_ema50_cross=4,
        bars_since_ema200_cross=4,
    )

    assert ema_direction_gate("LONG", context, mode="hard").allowed is False
    assert ema_direction_gate("LONG", context, mode="hard").reason == "EMA200_COUNTER_DIRECTION"


def test_ema200_soft_gate_returns_penalty_not_rejection():
    context = EmaContext(99, 101, 100, 100, 100, 0.001, 0.01, 4, 4)

    decision = ema_direction_gate("LONG", context, mode="soft")

    assert decision.allowed is True
    assert decision.penalty == -0.20


def test_score_ema50_quality_rewards_aligned_slope_and_stability():
    context = EmaContext(105, 104, 103, 100, 90, 0.004, 0.01, 5, 20)

    assert score_ema50_quality("LONG", context) == 0.95


def test_score_ema50_quality_penalizes_fresh_cross():
    context = EmaContext(105, 104, 103, 100, 90, 0.004, 0.01, 1, 20)

    assert score_ema50_quality("LONG", context) == 0.75


def test_score_ema_momentum_uses_fast_slow_alignment_and_gap():
    context = EmaContext(105, 104, 103, 100, 90, 0.002, 0.01, 5, 20)

    assert score_ema_momentum("LONG", context) == 0.8
    assert score_ema_momentum("SHORT", context) == 0.0


def test_ema_trend_state_maps_to_leverage_tiers():
    strong = EmaContext(105, 104, 103, 100, 90, 0.004, 0.01, 5, 20)
    mild = EmaContext(105, 104, 103, 100, 90, 0.0015, 0.01, 5, 20)
    flat = EmaContext(105, 104, 103, 100, 90, 0.0001, 0.01, 5, 20)

    assert ema_trend_state("LONG", strong) == "STRONG_TREND"
    assert ema_trend_state("LONG", mild) == "MILD_TREND"
    assert ema_trend_state("LONG", flat) == "FLAT_OR_TRANSITION"
