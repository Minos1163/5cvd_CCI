from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProjectSpecCheck:
    passed: bool
    reason: str


PROJECT_NAME = "多周期主流虚拟币趋势交易系统"
PROJECT_ENGLISH_NAME = "crypto-mtf-trend-strategy"
PROJECT_OBJECTIVE = (
    "构建一套可回测、可实盘、可审计、可维护的 Binance USDT 永续合约交易系统，"
    "用于交易市值前 20 的主流虚拟币。"
)
PROJECT_PRIORITY = ("stability", "explainability", "profitability")
TRADING_VENUE = "binance_usdt_perpetual"

CORE_DESIGN_GOALS = (
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

CORE_TIMEFRAMES = ("15m", "30m", "1h")
REFERENCE_TIMEFRAMES = ("4h",)
TIMEFRAME_ROLES = {
    "15m": "execution",
    "30m": "confirmation",
    "1h": "direction",
    "4h": "background_reference_only",
}

INDICATOR_RESPONSIBILITIES = {
    "MACD": "trend_and_momentum",
    "CCI": "strength_and_deviation",
    "BOLL": "volatility_structure_and_expansion",
    "RSI": "pullback_quality_and_overheat",
    "CVD": "fund_flow_and_aggressive_buy_sell_power",
    "ATR": "stop_take_profit_position_and_volatility_risk",
}

TRADING_DECISION_PRINCIPLES = (
    "multi_timeframe_alignment_first",
    "complete_structure_first",
    "same_direction_fund_flow_first",
    "reasonable_volatility_first",
    "qualified_data_quality_first",
    "risk_approval_first",
    "executable_position_first",
)

ENTRY_FORMS = {
    "PROBE": {"size_ratio": 0.25, "role": "test_direction_continuation"},
    "DIRECT": {"size_ratio": 1.0, "role": "full_confirmed_entry"},
}

PROJECT_NON_GOALS = (
    "no_high_frequency_trading",
    "no_arbitrage",
    "no_market_making",
    "no_black_box_machine_learning_prediction",
    "no_complex_watchlist_promotion_chain",
    "no_cross_layer_patchwork",
    "no_trade_for_the_sake_of_trading",
)

RISK_GOALS = (
    "control_single_trade_loss",
    "control_single_symbol_risk",
    "control_portfolio_total_exposure",
    "control_daily_loss",
    "control_weekly_loss",
    "control_drawdown",
    "control_abnormal_volatility_exposure",
    "control_revenge_retry_after_consecutive_losses",
)

POSITION_GOALS = (
    "stable_probe_direct_semantics",
    "position_links_to_stop_distance",
    "position_links_to_volatility",
    "position_links_to_equity",
    "position_links_to_portfolio_exposure",
    "position_links_to_min_notional",
)

BACKTEST_GOALS = (
    "backtest_live_isomorphic",
    "no_future_data",
    "record_each_trade",
    "record_state_machine",
    "record_failure_samples",
    "record_risk_blocks",
    "record_position_calculation",
    "repeatable_runs",
    "version_comparable",
)

LIVE_TRADING_GOALS = (
    "recoverable_strategy_state",
    "traceable_order_state",
    "syncable_position_state",
    "repairable_protection_orders",
    "risk_can_block",
    "alert_on_exception",
    "auditable_behavior",
)

SYSTEM_LAYERS = (
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
MODULE_DEPENDENCY_FLOW = SYSTEM_LAYERS

UNIFIED_CONTRACTS = (
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

OPERATIONAL_SUCCESS_STANDARDS = (
    "stable_signal_generation",
    "stable_open_close_execution",
    "stable_state_and_log_recording",
    "stable_backtest_live_reproduction",
    "stable_probe_direct_position_management",
    "stable_drawdown_control",
    "stable_multi_timeframe_consistency",
    "stable_position_and_order_recovery",
)

IMPLEMENTATION_PRINCIPLES = (
    "contract_first",
    "data_structure_first",
    "backtest_before_live",
    "unit_tests_before_integration",
    "isomorphism_before_optimization",
    "explainability_before_performance",
    "reproducibility_before_extension",
    "stability_before_flashiness",
)

RECOMMENDED_DEVELOPMENT_ORDER = (
    "config_and_data_contract",
    "indicator_layer",
    "multi_timeframe_context",
    "signal_engine",
    "state_machine",
    "risk_engine",
    "position_module",
    "backtest_engine",
    "execution_engine",
    "logging_and_reporting",
    "monitoring_and_recovery",
    "live_integration",
)

FINAL_SYSTEM_TRAITS = (
    "simple_structure",
    "clear_modules",
    "explainable_logic",
    "reproducible_results",
    "backtest_verifiable",
    "live_auditable",
    "low_maintenance_cost",
    "hard_to_lose_control_when_extended",
)

BANNED_FEATURES = (
    "black box model",
    "AI direct decision",
    "complex scorer",
    "multi-layer gate nesting",
    "Watchlist Promotion",
    "weak signal heavy size",
    "complex promotion",
    "execution reinterpret position",
    "low timeframe overrides high timeframe",
    "temporary patch as main strategy",
)

LAYER_ORDER = SYSTEM_LAYERS

SUCCESS_CRITERIA = {
    "annual_return_gt": 0.30,
    "max_drawdown_lt": 0.20,
    "profit_factor_gt": 1.5,
    "sharpe_gt": 1.5,
    "win_rate_min": 0.40,
    "win_rate_max": 0.60,
    "reward_risk_gt": 2.0,
}


def validate_feature_allowed(feature_name: str) -> tuple[bool, str]:
    normalized = feature_name.casefold()
    for banned in BANNED_FEATURES:
        if banned.casefold() in normalized or normalized in banned.casefold():
            return False, f"{banned} is banned by project overview"
    return True, "allowed"


def validate_timeframe_role(timeframe: str, role: str) -> ProjectSpecCheck:
    expected = TIMEFRAME_ROLES.get(timeframe)
    if expected is None:
        return ProjectSpecCheck(False, f"unknown timeframe: {timeframe}")
    if expected != role:
        return ProjectSpecCheck(False, f"{timeframe} role must be {expected}, got {role}")
    return ProjectSpecCheck(True, "timeframe role approved")


def validate_entry_form(entry_form: str) -> ProjectSpecCheck:
    normalized = entry_form.upper()
    if normalized not in ENTRY_FORMS:
        return ProjectSpecCheck(False, f"{entry_form} is not an allowed entry form")
    return ProjectSpecCheck(True, "entry form approved")
