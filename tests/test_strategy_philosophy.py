from src.core.strategy_philosophy import (
    ALLOWED_TRADE_TYPES,
    ANTI_NOISE_RULES,
    ANTI_OVERFIT_RULES,
    CAPITAL_MANAGEMENT_PRINCIPLES,
    DECISION_PRIORITY,
    EXIT_PHILOSOPHY,
    FIRST_PRINCIPLES,
    INDICATOR_RESPONSIBILITIES,
    MARKET_STATES,
    PHILOSOPHY_FORBIDDEN_PATTERNS,
    REGIME_ACTIONS,
    STRATEGY_IDENTITY,
    STRATEGY_NON_GOALS,
    TIMEFRAME_ROLES,
    UNCERTAINTY_ACTIONS,
    validate_decision_chain_depth,
    validate_decision_priority,
    validate_indicator_role,
    validate_long_short_symmetry,
    validate_strategy_pattern_allowed,
    validate_uncertainty_response,
)


def test_regime_actions_are_simple():
    assert REGIME_ACTIONS["up"] == "long"
    assert REGIME_ACTIONS["down"] == "short"
    assert REGIME_ACTIONS["range"] == "wait"


def test_timeframe_roles_match_docs():
    assert TIMEFRAME_ROLES["4h"] == "background"
    assert TIMEFRAME_ROLES["1h"] == "trend_confirmation"
    assert TIMEFRAME_ROLES["30m"] == "trend_quality"
    assert TIMEFRAME_ROLES["15m"] == "execution_trigger"


def test_indicator_has_single_responsibility():
    ok, reason = validate_indicator_role("ATR", "direction")
    assert ok is False
    assert "risk_control" in reason


def test_decision_chain_depth_limit():
    assert validate_decision_chain_depth(["trend", "quality", "trigger"])[0] is True
    assert validate_decision_chain_depth(["a", "b", "c", "d"])[0] is False


def test_indicator_responsibility_map():
    assert INDICATOR_RESPONSIBILITIES["MACD"] == "trend"
    assert INDICATOR_RESPONSIBILITIES["ATR"] == "risk_control"


def test_expanded_strategy_identity_and_non_goals_match_doc():
    assert STRATEGY_IDENTITY["venue"] == "binance_usdt_perpetual"
    assert STRATEGY_IDENTITY["style"] == "multi_timeframe_trend_following"
    assert (
        STRATEGY_IDENTITY["core_sentence"]
        == "higher_tf_direction_mid_tf_quality_low_tf_timing_flow_confirmation_volatility_boundary"
    )
    assert STRATEGY_NON_GOALS == [
        "high_frequency_market_making",
        "arbitrage",
        "black_box_prediction",
        "complex_score_stacking",
        "manual_discretionary_override",
    ]


def test_first_principles_and_decision_priority_are_fixed():
    assert FIRST_PRINCIPLES == [
        "risk_before_return",
        "trend_before_entry",
        "quality_before_quantity",
        "explainability_before_complexity",
        "live_backtest_isomorphism_before_optimization",
    ]
    assert DECISION_PRIORITY == [
        "data_quality",
        "risk_constraints",
        "higher_timeframe_direction",
        "mid_timeframe_quality",
        "lower_timeframe_timing",
        "fund_flow_confirmation",
        "position_executability",
        "execution_landing",
    ]
    assert validate_decision_priority(DECISION_PRIORITY).passed is True
    bad = list(DECISION_PRIORITY)
    bad[0], bad[1] = bad[1], bad[0]
    assert validate_decision_priority(bad).passed is False


def test_trade_types_market_states_and_uncertainty_policy():
    assert ALLOWED_TRADE_TYPES == ["PROBE", "DIRECT"]
    assert MARKET_STATES == [
        "uptrend",
        "downtrend",
        "range",
        "trend_transition",
        "volatility_expansion",
        "volatility_contraction",
    ]
    assert UNCERTAINTY_ACTIONS == ["degrade", "wait", "observe", "reduce_size", "disable_new_entries"]
    assert validate_uncertainty_response("wait").passed is True
    assert validate_uncertainty_response("increase_tolerance").passed is False


def test_symmetry_noise_overfit_capital_and_exit_principles_are_scripted():
    assert validate_long_short_symmetry({"LONG": ["trend", "quality"], "SHORT": ["trend", "quality"]}).passed is True
    assert validate_long_short_symmetry({"LONG": ["trend"], "SHORT": ["trend", "extra_exception"]}).passed is False
    assert "single_abnormal_candle" in ANTI_NOISE_RULES
    assert "add_rule_for_single_failed_sample" in ANTI_OVERFIT_RULES
    assert CAPITAL_MANAGEMENT_PRINCIPLES[0] == "define_trade_risk_first"
    assert EXIT_PHILOSOPHY[0] == "losses_should_be_fast"


def test_forbidden_strategy_patterns_reject_patchy_or_asymmetric_logic():
    assert "complex_watchlist_promotion_chain" in PHILOSOPHY_FORBIDDEN_PATTERNS
    assert "low_timeframe_noise_overrides_higher_timeframe" in PHILOSOPHY_FORBIDDEN_PATTERNS
    rejected = validate_strategy_pattern_allowed("add low_timeframe_noise_overrides_higher_timeframe exception")
    assert rejected.passed is False
    assert "low_timeframe_noise_overrides_higher_timeframe" in rejected.reason
