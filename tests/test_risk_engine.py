from src.risk.risk_engine import (
    DEFAULT_RISK_LIMITS,
    RISK_DECISION_FLOW,
    RISK_FORBIDDEN_ACTIONS,
    RISK_LEVELS,
    RISK_OUTPUT_FIELDS,
    RISK_REQUIRED_INPUTS,
    RISK_SNAPSHOT_FIELDS,
    RiskContext,
    evaluate_risk,
)


def base_context(**overrides):
    context = {
        "symbol": "BTCUSDT",
        "timestamp": 1,
        "signal_type": "LONG",
        "signal_side": "LONG",
        "entry_mode": "DIRECT",
        "account_equity": 10_000,
        "available_margin": 5_000,
        "used_margin": 1_000,
        "open_positions": 1,
        "portfolio_exposure": 0.20,
        "symbol_exposure": 0.05,
        "daily_pnl": 0,
        "weekly_pnl": 0,
        "max_drawdown": 0.05,
        "atr": 100,
        "stop_pct": 0.02,
        "quality_flag": True,
        "cooldown_state": {"active": False},
        "market_state_4h": "BULL",
        "trend_state_1h": "LONG_ALLOWED",
        "confirm_state_30m": "LONG_CONFIRM",
        "trigger_state_15m": "LONG",
        "entry_price": 50_000,
        "volatility_state": "NORMAL",
    }
    context.update(overrides)
    return context


def test_direct_risk_ok_outputs_normal_risk_snapshot():
    result = evaluate_risk(base_context())

    assert result.allow_trade is True
    assert result.risk_level == "NORMAL"
    assert result.position_size_factor == 1.0
    assert result.risk_reason == "FULL_CONFIRMATION_AND_RISK_OK"
    assert result.stop_distance == 1_000
    assert result.stop_pct == 0.02
    assert result.metrics_snapshot["symbol"] == "BTCUSDT"
    assert result.metrics_snapshot["risk_level"] == "NORMAL"
    assert result.take_profit_plan[0]["target_price"] == 51_000


def test_probe_uses_quarter_position_factor_without_promotion():
    result = evaluate_risk(base_context(entry_mode="PROBE"))

    assert result.allow_trade is True
    assert result.position_size_factor == 0.25
    assert result.metadata["forbidden_actions"] == RISK_FORBIDDEN_ACTIONS


def test_daily_weekly_drawdown_quality_cooldown_and_exposure_block():
    assert evaluate_risk(base_context(daily_pnl=-600)).risk_reason == "DAILY_LOSS_LIMIT_REACHED"
    assert evaluate_risk(base_context(weekly_pnl=-1300)).risk_reason == "WEEKLY_LOSS_LIMIT_REACHED"
    assert evaluate_risk(base_context(max_drawdown=0.25)).risk_reason == "MAX_DRAWDOWN_LIMIT_REACHED"
    assert evaluate_risk(base_context(quality_flag=False)).risk_reason == "DATA_QUALITY_BLOCKED"
    assert evaluate_risk(base_context(cooldown_state={"active": True})).risk_reason == "COOLDOWN_ACTIVE"
    assert evaluate_risk(base_context(portfolio_exposure=0.80)).risk_reason == "PORTFOLIO_EXPOSURE_LIMIT_REACHED"
    assert evaluate_risk(base_context(symbol_exposure=0.25)).risk_reason == "SYMBOL_EXPOSURE_LIMIT_REACHED"


def test_blocked_result_allows_exit_and_can_require_cooldown():
    result = evaluate_risk(base_context(daily_pnl=-600))

    assert result.allow_trade is False
    assert result.allow_exit is True
    assert result.risk_level == "BLOCKED"
    assert result.cooldown_required is True
    assert result.cooldown_bars == DEFAULT_RISK_LIMITS["normal_cooldown_bars"]


def test_high_volatility_downgrades_to_probe_factor():
    result = evaluate_risk(base_context(volatility_state="HIGH"))

    assert result.allow_trade is True
    assert result.risk_level == "HIGH"
    assert result.position_size_factor == 0.25
    assert result.allow_reduce is True
    assert result.risk_reason == "TREND_OK_BUT_VOLATILITY_HIGH"


def test_extreme_volatility_requires_exit_not_new_trade():
    result = evaluate_risk(base_context(volatility_state="EXTREME"))

    assert result.allow_trade is False
    assert result.allow_exit is True
    assert result.allow_reduce is True
    assert result.risk_level == "EXTREME"


def test_stop_distance_and_atr_gates_block_invalid_risk():
    assert evaluate_risk(base_context(atr=0)).risk_reason == "ATR_UNAVAILABLE"
    assert evaluate_risk(base_context(stop_pct=0.001)).risk_reason == "STOP_DISTANCE_TOO_SMALL"
    assert evaluate_risk(base_context(stop_pct=0.10)).risk_reason == "STOP_DISTANCE_TOO_LARGE"


def test_forced_exit_trigger_has_highest_priority_and_cooldown():
    result = evaluate_risk(base_context(stop_hit=True))

    assert result.allow_trade is False
    assert result.allow_exit is True
    assert result.cooldown_required is True
    assert result.risk_reason == "FORCED_EXIT_REQUIRED"
    assert result.metadata["exit_action"]["action_type"] == "FORCED_STOP"


def test_dataclass_context_is_supported():
    result = evaluate_risk(RiskContext(**base_context()))

    assert result.allow_trade is True
    assert result.risk_level == "NORMAL"


def test_risk_engine_public_contract_constants():
    assert RISK_LEVELS == ["LOW", "NORMAL", "HIGH", "EXTREME", "BLOCKED"]
    assert RISK_DECISION_FLOW == [
        "check_data_quality",
        "check_cooldown",
        "check_account_risk",
        "check_portfolio_risk",
        "check_symbol_risk",
        "check_volatility_risk",
        "check_stop_distance",
        "check_position_executability",
        "check_add_reduce_exit",
        "output_risk_result",
    ]
    assert "quality_flag" in RISK_REQUIRED_INPUTS
    assert "metadata" in RISK_OUTPUT_FIELDS
    assert "risk_reason" in RISK_SNAPSHOT_FIELDS
    assert "submit_or_cancel_orders" in RISK_FORBIDDEN_ACTIONS
