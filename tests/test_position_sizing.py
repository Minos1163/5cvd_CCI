import pytest

from src.risk.position_sizer import (
    ENTRY_MODE_MULTIPLIERS,
    NO_TRADE,
    POSITION_DECISION_STEPS,
    POSITION_LOG_FIELDS,
    POSITION_REQUIRED_INPUTS,
    STATE_POSITION_POLICY,
    PositionSizingInput,
    calculate_position_size,
    market_tier_multiplier,
    normalize_entry_mode,
    size_notional,
)


def base_request(**overrides):
    values = {
        "symbol": "BTCUSDT",
        "signal_type": "DIRECT",
        "equity": 10_000,
        "available_margin": 5_000,
        "price": 50_000,
        "leverage": 5,
        "stop_pct": 0.02,
        "atr": 800,
        "risk_pct": 0.01,
        "market_tier": "B",
        "current_open_exposure": 0,
        "portfolio_correlation": 0.2,
        "min_notional": 5,
        "max_total_exposure_pct": 0.75,
        "max_symbol_exposure_pct": 0.75,
        "max_correlation_group_exposure_pct": 0.75,
    }
    values.update(overrides)
    return PositionSizingInput(**values)


def test_size_notional_preserves_direct_probe_ratio():
    direct = size_notional(10_000, 0.01, 0.02, "DIRECT")
    probe = size_notional(10_000, 0.01, 0.02, "PROBE")
    assert direct == 5_000
    assert probe == 1_250


def test_calculate_direct_standard_notional_from_risk():
    result = calculate_position_size(base_request())
    assert result.approved is True
    assert result.standard_notional == 5_000
    assert result.notional == 5_000
    assert result.quantity == pytest.approx(0.1)
    assert result.required_margin == 1_000
    assert result.reason == "approved"


def test_calculate_probe_is_quarter_standard_notional():
    result = calculate_position_size(base_request(signal_type="PROBE"))
    assert result.approved is True
    assert result.standard_notional == 5_000
    assert result.signal_multiplier == 0.25
    assert result.notional == 1_250
    assert result.quantity == pytest.approx(0.025)


def test_probe_below_min_notional_rejects_instead_of_inflating():
    result = calculate_position_size(
        base_request(
            signal_type="PROBE",
            equity=100,
            price=100,
            risk_pct=0.01,
            stop_pct=0.10,
            min_notional=5,
        )
    )
    assert result.approved is False
    assert result.notional == 2.5
    assert result.quantity == 0
    assert "skip instead of inflating" in result.reason


def test_margin_shortfall_rejects_without_resizing():
    result = calculate_position_size(base_request(available_margin=100))
    assert result.approved is False
    assert result.notional == 5_000
    assert result.required_margin == 1_000
    assert "available margin" in result.reason


def test_total_exposure_limit_rejects_without_resizing():
    result = calculate_position_size(
        base_request(current_open_exposure=7_000, max_total_exposure_pct=0.75)
    )
    assert result.approved is False
    assert result.notional == 5_000
    assert "total exposure" in result.reason


def test_invalid_stop_pct_raises():
    with pytest.raises(ValueError, match="stop_pct must be positive"):
        calculate_position_size(base_request(stop_pct=0))


def test_market_tier_multiplier_is_metadata_not_probe_inflation():
    assert market_tier_multiplier("A") == 2.0
    assert market_tier_multiplier("B") == 1.0
    assert market_tier_multiplier("C") == 0.75
    result = calculate_position_size(base_request(signal_type="PROBE", market_tier="C"))
    assert result.signal_multiplier == 0.25
    assert result.market_tier_multiplier == 0.75
    assert result.notional == 937.5


def test_completed_position_sizing_contract_lists_doc_inputs_steps_and_logs():
    assert POSITION_REQUIRED_INPUTS == [
        "account_equity",
        "available_margin",
        "symbol_price",
        "leverage",
        "stop_pct",
        "risk_per_trade_pct",
        "symbol_tier",
        "open_exposure",
        "portfolio_exposure",
        "correlation_group",
        "position_side",
        "entry_mode",
        "volatility_state",
    ]
    assert POSITION_DECISION_STEPS == [
        "read_account_equity_and_available_margin",
        "read_entry_mode",
        "read_stop_pct",
        "calculate_standard_notional",
        "apply_symbol_tier_factor",
        "apply_portfolio_exposure_limit",
        "apply_account_risk_factor",
        "check_min_notional",
        "check_min_margin",
        "output_final_executable_size",
    ]
    assert POSITION_LOG_FIELDS == [
        "symbol",
        "entry_mode",
        "account_equity",
        "available_margin",
        "risk_amount",
        "stop_pct",
        "standard_notional",
        "probe_notional",
        "direct_notional",
        "tier_factor",
        "account_risk_factor",
        "portfolio_risk_factor",
        "final_notional",
        "final_qty",
        "min_notional_check",
        "leverage",
        "decision",
    ]


def test_entry_mode_alias_preserves_existing_signal_type_interface():
    legacy = base_request(signal_type="PROBE")
    explicit = base_request(signal_type="DIRECT", entry_mode="probe")
    assert normalize_entry_mode(legacy) == "PROBE"
    assert normalize_entry_mode(explicit) == "PROBE"
    assert ENTRY_MODE_MULTIPLIERS["DIRECT"] == 1.0
    assert ENTRY_MODE_MULTIPLIERS["PROBE"] == 0.25
    assert NO_TRADE == "NO_TRADE"
    assert STATE_POSITION_POLICY["WATCH"] == "prepare_only"
    assert STATE_POSITION_POLICY["EXIT"] == "close_only"


def test_direct_size_applies_tier_account_portfolio_and_volatility_factors():
    result = calculate_position_size(
        base_request(
            market_tier="B",
            symbol_tier="B",
            account_risk_factor=0.8,
            portfolio_risk_factor=0.5,
            volatility_state="HIGH",
        )
    )
    assert result.approved is True
    assert result.standard_notional == 5_000
    assert result.notional == 1_000
    assert result.final_notional == 1_000
    assert result.quantity == pytest.approx(0.02)
    assert result.decision == "DIRECT"
    assert result.audit["account_risk_factor"] == 0.8
    assert result.audit["portfolio_risk_factor"] == 0.5
    assert result.audit["decision"] == "DIRECT"


def test_no_trade_mode_returns_clean_no_trade_without_sizing():
    result = calculate_position_size(base_request(entry_mode="NO_TRADE"))
    assert result.approved is False
    assert result.decision == "NO_TRADE"
    assert result.notional == 0
    assert result.quantity == 0
    assert "entry mode is NO_TRADE" in result.reason


def test_state_cooldown_quality_and_leverage_gates_return_no_trade():
    assert calculate_position_size(base_request(data_quality_ok=False)).decision == "NO_TRADE"
    assert calculate_position_size(base_request(state_allows_entry=False)).decision == "NO_TRADE"
    assert calculate_position_size(base_request(cooldown_active=True)).decision == "NO_TRADE"
    assert calculate_position_size(base_request(leverage_set=False)).decision == "NO_TRADE"
    assert calculate_position_size(base_request(leverage=10, max_leverage=5)).decision == "NO_TRADE"


def test_symbol_side_correlation_and_position_count_limits_return_no_trade():
    assert calculate_position_size(
        base_request(symbol_exposure=2_000, max_symbol_exposure_pct=0.20)
    ).decision == "NO_TRADE"
    assert calculate_position_size(
        base_request(side_exposure=7_000, max_side_exposure_pct=0.75)
    ).decision == "NO_TRADE"
    assert calculate_position_size(
        base_request(correlation_group_exposure=4_500, max_correlation_group_exposure_pct=0.50)
    ).decision == "NO_TRADE"
    assert calculate_position_size(
        base_request(open_positions_count=5, max_open_positions=5)
    ).decision == "NO_TRADE"


def test_quantity_step_floors_without_inflating_notional():
    result = calculate_position_size(
        base_request(
            market_tier="B",
            quantity_step=0.03,
            price=10_000,
        )
    )
    assert result.approved is True
    assert result.quantity == pytest.approx(0.48)
    assert result.notional == pytest.approx(4_800)
    assert result.notional < result.standard_notional


def test_precision_floor_rechecks_min_notional_and_skips():
    result = calculate_position_size(
        base_request(
            signal_type="PROBE",
            market_tier="B",
            equity=100,
            price=100,
            risk_pct=0.01,
            stop_pct=0.10,
            min_notional=2.4,
            quantity_step=0.02,
        )
    )
    assert result.approved is False
    assert result.decision == "NO_TRADE"
    assert result.notional == pytest.approx(2.0)
    assert result.quantity == pytest.approx(0.02)
    assert "precision floor" in result.reason
