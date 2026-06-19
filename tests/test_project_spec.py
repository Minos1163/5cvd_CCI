from src.core.project_spec import (
    BACKTEST_GOALS,
    BANNED_FEATURES,
    CORE_DESIGN_GOALS,
    CORE_TIMEFRAMES,
    ENTRY_FORMS,
    FINAL_SYSTEM_TRAITS,
    IMPLEMENTATION_PRINCIPLES,
    INDICATOR_RESPONSIBILITIES,
    LAYER_ORDER,
    LIVE_TRADING_GOALS,
    MODULE_DEPENDENCY_FLOW,
    OPERATIONAL_SUCCESS_STANDARDS,
    POSITION_GOALS,
    PROJECT_ENGLISH_NAME,
    PROJECT_NAME,
    PROJECT_NON_GOALS,
    PROJECT_OBJECTIVE,
    PROJECT_PRIORITY,
    RECOMMENDED_DEVELOPMENT_ORDER,
    REFERENCE_TIMEFRAMES,
    RISK_GOALS,
    SUCCESS_CRITERIA,
    SYSTEM_LAYERS,
    TIMEFRAME_ROLES,
    TRADING_DECISION_PRINCIPLES,
    UNIFIED_CONTRACTS,
    validate_entry_form,
    validate_feature_allowed,
    validate_timeframe_role,
)


def test_project_priority_matches_docs():
    assert PROJECT_PRIORITY == ("stability", "explainability", "profitability")


def test_timeframes_match_docs():
    assert CORE_TIMEFRAMES == ("15m", "30m", "1h")
    assert REFERENCE_TIMEFRAMES == ("4h",)


def test_banned_watchlist_promotion_is_rejected():
    ok, reason = validate_feature_allowed("watchlist promotion")
    assert ok is False
    assert "Watchlist Promotion" in reason


def test_layer_order_has_risk_before_execution():
    assert LAYER_ORDER.index("risk") < LAYER_ORDER.index("execution")


def test_success_criteria_contains_core_metrics():
    assert SUCCESS_CRITERIA["max_drawdown_lt"] == 0.20
    assert SUCCESS_CRITERIA["profit_factor_gt"] == 1.5
    assert "Watchlist Promotion" in BANNED_FEATURES


def test_project_identity_objective_and_design_goals_match_overview():
    assert PROJECT_NAME == "多周期主流虚拟币趋势交易系统"
    assert PROJECT_ENGLISH_NAME == "crypto-mtf-trend-strategy"
    assert "Binance USDT 永续合约" in PROJECT_OBJECTIVE
    assert CORE_DESIGN_GOALS == (
        "logic_clear",
        "timeframe_responsibilities_clear",
        "single_responsibility_indicators",
        "traceable_state_machine",
        "stable_position_contract",
        "unified_risk_rules",
        "backtest_live_isomorphic",
        "thin_stable_execution_layer",
        "fixed_data_contract",
        "replayable_auditable_behavior",
    )


def test_timeframe_roles_are_explicit_and_4h_is_reference_only():
    assert TIMEFRAME_ROLES == {
        "15m": "execution",
        "30m": "confirmation",
        "1h": "direction",
        "4h": "background_reference_only",
    }
    assert validate_timeframe_role("15m", "execution").passed is True
    assert validate_timeframe_role("4h", "hard_filter").passed is False


def test_indicator_responsibilities_are_single_purpose():
    assert INDICATOR_RESPONSIBILITIES == {
        "MACD": "trend_and_momentum",
        "CCI": "strength_and_deviation",
        "BOLL": "volatility_structure_and_expansion",
        "RSI": "pullback_quality_and_overheat",
        "CVD": "fund_flow_and_aggressive_buy_sell_power",
        "ATR": "stop_take_profit_position_and_volatility_risk",
    }


def test_entry_forms_are_probe_and_direct_only():
    assert ENTRY_FORMS == {
        "PROBE": {"size_ratio": 0.25, "role": "test_direction_continuation"},
        "DIRECT": {"size_ratio": 1.0, "role": "full_confirmed_entry"},
    }
    assert validate_entry_form("PROBE").passed is True
    assert validate_entry_form("DIRECT").passed is True
    assert validate_entry_form("PROMOTION").passed is False


def test_project_layers_contracts_principles_and_success_standards_are_scripted():
    assert SYSTEM_LAYERS == MODULE_DEPENDENCY_FLOW
    assert MODULE_DEPENDENCY_FLOW == (
        "data",
        "indicators",
        "context",
        "signals",
        "state_machine",
        "risk",
        "position_sizing",
        "execution",
        "backtest",
        "reporting",
        "monitoring",
    )
    assert UNIFIED_CONTRACTS == (
        "data",
        "indicator",
        "event",
        "state_machine",
        "risk",
        "position",
        "execution",
        "backtest",
        "config",
        "logging",
    )
    assert OPERATIONAL_SUCCESS_STANDARDS[0] == "stable_signal_generation"
    assert IMPLEMENTATION_PRINCIPLES[0] == "contract_first"
    assert RECOMMENDED_DEVELOPMENT_ORDER[0] == "config_and_data_contract"
    assert FINAL_SYSTEM_TRAITS[-1] == "hard_to_lose_control_when_extended"


def test_project_goal_groups_and_non_goals_are_exposed():
    assert PROJECT_PRIORITY == ("stability", "explainability", "profitability")
    assert "no_high_frequency_trading" in PROJECT_NON_GOALS
    assert "control_single_trade_loss" in RISK_GOALS
    assert "position_links_to_stop_distance" in POSITION_GOALS
    assert "no_future_data" in BACKTEST_GOALS
    assert "recoverable_strategy_state" in LIVE_TRADING_GOALS
    assert TRADING_DECISION_PRINCIPLES[0] == "multi_timeframe_alignment_first"
