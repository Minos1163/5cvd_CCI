from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PhilosophyCheck:
    name: str
    passed: bool
    reason: str


REGIME_ACTIONS = {
    "up": "long",
    "down": "short",
    "range": "wait",
}

STRATEGY_IDENTITY = {
    "venue": "binance_usdt_perpetual",
    "style": "multi_timeframe_trend_following",
    "core_sentence": "higher_tf_direction_mid_tf_quality_low_tf_timing_flow_confirmation_volatility_boundary",
}
STRATEGY_NON_GOALS = [
    "high_frequency_market_making",
    "arbitrage",
    "black_box_prediction",
    "complex_score_stacking",
    "manual_discretionary_override",
]
FIRST_PRINCIPLES = [
    "risk_before_return",
    "trend_before_entry",
    "quality_before_quantity",
    "explainability_before_complexity",
    "live_backtest_isomorphism_before_optimization",
]
MARKET_STATES = [
    "uptrend",
    "downtrend",
    "range",
    "trend_transition",
    "volatility_expansion",
    "volatility_contraction",
]
DECISION_PRIORITY = [
    "data_quality",
    "risk_constraints",
    "higher_timeframe_direction",
    "mid_timeframe_quality",
    "lower_timeframe_timing",
    "fund_flow_confirmation",
    "position_executability",
    "execution_landing",
]
ALLOWED_TRADE_TYPES = ["PROBE", "DIRECT"]
ANTI_NOISE_RULES = [
    "single_abnormal_candle",
    "short_timeframe_fake_breakout",
    "low_quality_divergence",
    "temporary_wick",
    "distorted_volume",
    "overheated_micro_continuation",
]
ANTI_OVERFIT_RULES = [
    "add_rule_for_single_failed_sample",
    "add_exception_to_improve_win_rate_only",
    "optimize_for_one_history_segment",
    "hide_execution_costs",
    "change_live_rules_after_backtest",
]
CAPITAL_MANAGEMENT_PRINCIPLES = [
    "define_trade_risk_first",
    "derive_position_size_from_risk",
    "choose_probe_or_direct_after_risk",
    "execution_layer_must_not_patch_size",
]
EXIT_PHILOSOPHY = [
    "losses_should_be_fast",
    "admit_wrong_trade_early",
    "protect_capital_first",
    "let_valid_profit_run",
    "do_not_patch_distorted_position",
]
UNCERTAINTY_ACTIONS = ["degrade", "wait", "observe", "reduce_size", "disable_new_entries"]
UNCERTAINTY_FORBIDDEN_ACTIONS = ["force_trade", "increase_tolerance", "add_exception", "patch_uncertainty"]
PHILOSOPHY_FORBIDDEN_PATTERNS = [
    "complex_watchlist_promotion_chain",
    "temporary_gate_patch_stack",
    "fixed_one_percent_stop_for_all_regimes",
    "weak_trend_large_position",
    "low_timeframe_noise_overrides_higher_timeframe",
    "signal_and_execution_reinterpret_position",
    "trade_first_explain_later",
    "countertrend_without_structure",
    "asymmetric_long_short_exception",
]

TIMEFRAME_ROLES = {
    "4h": "background",
    "1h": "trend_confirmation",
    "30m": "trend_quality",
    "15m": "execution_trigger",
}

INDICATOR_RESPONSIBILITIES = {
    "MACD": "trend",
    "CCI": "trend_strength",
    "RSI": "pullback_quality",
    "BOLL": "volatility_structure",
    "CVD": "fund_flow",
    "ATR": "risk_control",
}


def validate_indicator_role(indicator: str, requested_role: str) -> tuple[bool, str]:
    key = indicator.upper()
    actual = INDICATOR_RESPONSIBILITIES.get(key)
    if actual is None:
        return False, f"unknown indicator: {indicator}"
    if actual != requested_role:
        return False, f"{key} is responsible for {actual}, not {requested_role}"
    return True, "allowed"


def validate_decision_chain_depth(chain: list[str], max_depth: int = 3) -> tuple[bool, str]:
    if len(chain) > max_depth:
        return False, "decision chain exceeds 3 layers"
    return True, "allowed"


def validate_decision_priority(priority: list[str]) -> PhilosophyCheck:
    if priority != DECISION_PRIORITY:
        return PhilosophyCheck("decision_priority", False, "decision priority must remain fixed")
    return PhilosophyCheck("decision_priority", True, "decision priority approved")


def validate_long_short_symmetry(rule_map: dict[str, list[str]]) -> PhilosophyCheck:
    long_rules = rule_map.get("LONG", [])
    short_rules = rule_map.get("SHORT", [])
    if long_rules != short_rules:
        return PhilosophyCheck("long_short_symmetry", False, "long and short rules must be mirrored")
    return PhilosophyCheck("long_short_symmetry", True, "long and short rules are symmetric")


def validate_uncertainty_response(action: str) -> PhilosophyCheck:
    normalized = action.strip().lower()
    if normalized in UNCERTAINTY_ACTIONS:
        return PhilosophyCheck("uncertainty_response", True, "uncertainty response approved")
    return PhilosophyCheck(
        "uncertainty_response",
        False,
        "uncertainty must degrade, wait, observe, reduce size, or disable new entries",
    )


def validate_strategy_pattern_allowed(pattern: str) -> PhilosophyCheck:
    normalized = pattern.casefold()
    for forbidden in PHILOSOPHY_FORBIDDEN_PATTERNS:
        if forbidden.casefold() in normalized or normalized in forbidden.casefold():
            return PhilosophyCheck("strategy_pattern", False, f"{forbidden} is forbidden by strategy philosophy")
    return PhilosophyCheck("strategy_pattern", True, "strategy pattern allowed")
