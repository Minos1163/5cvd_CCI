from src.backtest.protocol import (
    BACKTEST_PROCESSING_ORDER,
    DATA_QUALITY_CHECKS,
    REQUIRED_OUTPUT_ARTIFACTS,
    REQUIRED_PERFORMANCE_FIELDS,
    REQUIRED_STATE_TRANSITION_FIELDS,
    REQUIRED_TRADE_FIELDS,
    STRATIFIED_ANALYSIS_DIMENSIONS,
    WalkForwardWindow,
    generate_walk_forward_windows,
    validate_backtest_protocol,
    validate_candle_continuity,
    validate_data_quality,
    validate_output_artifacts,
    validate_processing_order,
    validate_state_transition_fields,
    validate_stratified_analysis_dimensions,
    validate_timeframe_alignment,
)
from src.core.models import Candle


def candle(open_time: int, close_time: int, volume: float = 10) -> Candle:
    return Candle(
        symbol="BTCUSDT",
        timeframe="15m",
        open_time=open_time,
        close_time=close_time,
        open=100,
        high=105,
        low=95,
        close=101,
        volume=volume,
    )


def test_processing_order_is_exit_before_entry():
    assert BACKTEST_PROCESSING_ORDER == [
        "update_history",
        "update_indicators",
        "update_multi_timeframe_context",
        "update_state",
        "check_exit",
        "check_reduce",
        "check_add",
        "check_entry",
        "record_events",
    ]
    assert validate_processing_order(BACKTEST_PROCESSING_ORDER).passed is True


def test_processing_order_rejects_entry_before_exit():
    wrong = list(BACKTEST_PROCESSING_ORDER)
    wrong[4], wrong[7] = wrong[7], wrong[4]
    result = validate_processing_order(wrong)
    assert result.passed is False
    assert "fixed processing order" in result.reason


def test_validate_candle_continuity_detects_duplicates_and_gaps():
    candles = [candle(0, 900), candle(900, 1800), candle(900, 1800), candle(2700, 3600)]
    results = validate_candle_continuity(candles, timeframe_seconds=900)
    failed = [result.reason for result in results if not result.passed]
    assert any("duplicate" in reason for reason in failed)
    assert any("gap" in reason for reason in failed)


def test_validate_backtest_protocol_requires_costs_outputs_and_position_model():
    results = validate_backtest_protocol(
        fee_bps=5,
        slippage_bps=5,
        fill_model="next_bar_open",
        uses_position_sizer=True,
        trade_fields=set(REQUIRED_TRADE_FIELDS),
        performance_fields=set(REQUIRED_PERFORMANCE_FIELDS),
    )
    assert all(result.passed for result in results)


def test_validate_backtest_protocol_rejects_missing_costs():
    results = validate_backtest_protocol(
        fee_bps=0,
        slippage_bps=0,
        fill_model="next_bar_open",
        uses_position_sizer=True,
        trade_fields=set(REQUIRED_TRADE_FIELDS),
        performance_fields=set(REQUIRED_PERFORMANCE_FIELDS),
    )
    assert any((not result.passed and "fee" in result.reason) for result in results)
    assert any((not result.passed and "slippage" in result.reason) for result in results)


def test_data_quality_check_names_cover_doc_requirements():
    assert DATA_QUALITY_CHECKS == [
        "time_continuity",
        "missing_bar",
        "long_wick",
        "extreme_gap",
        "price_precision",
        "zero_volume",
        "duplicate_timestamp",
    ]


def test_validate_data_quality_detects_long_wick_gap_precision_and_zero_volume():
    candles = [
        candle(0, 900, volume=10),
        Candle(
            symbol="BTCUSDT",
            timeframe="15m",
            open_time=900,
            close_time=1800,
            open=130.123456789,
            high=180,
            low=100,
            close=132,
            volume=0,
        ),
    ]
    results = validate_data_quality(
        candles,
        timeframe_seconds=900,
        max_wick_ratio=0.50,
        max_gap_pct=0.20,
        max_price_decimals=4,
    )
    failed = [result.reason for result in results if not result.passed]
    assert any("long wick" in reason for reason in failed)
    assert any("extreme gap" in reason for reason in failed)
    assert any("price precision" in reason for reason in failed)
    assert any("zero volume" in reason for reason in failed)


def test_validate_timeframe_alignment_requires_completed_higher_timeframe_bar():
    result = validate_timeframe_alignment(
        base_close_time=3_600,
        higher_close_time=3_600,
        higher_timeframe_seconds=3_600,
    )
    assert result.passed is True
    leaking = validate_timeframe_alignment(
        base_close_time=3_600,
        higher_close_time=7_200,
        higher_timeframe_seconds=3_600,
    )
    assert leaking.passed is False
    assert "future" in leaking.reason


def test_required_state_transition_fields_match_doc():
    assert REQUIRED_STATE_TRANSITION_FIELDS == [
        "current_state",
        "target_state",
        "reason",
        "transition_time",
        "transition_price",
        "timeframe",
    ]
    ok = validate_state_transition_fields(set(REQUIRED_STATE_TRANSITION_FIELDS))
    assert ok.passed is True
    missing = validate_state_transition_fields({"current_state"})
    assert missing.passed is False
    assert "target_state" in missing.reason


def test_stratified_analysis_dimensions_cover_doc_requirements():
    assert STRATIFIED_ANALYSIS_DIMENSIONS == [
        "symbol",
        "timeframe",
        "market_regime",
        "side",
        "signal_type",
        "single_vs_portfolio",
        "volatility_regime",
    ]
    assert validate_stratified_analysis_dimensions(set(STRATIFIED_ANALYSIS_DIMENSIONS)).passed is True


def test_required_output_artifacts_cover_doc_requirements():
    assert REQUIRED_OUTPUT_ARTIFACTS == [
        "equity_curve",
        "trade_detail",
        "performance_summary",
        "drawdown_summary",
        "state_machine_stats",
        "rejection_stats",
        "failure_samples",
        "strategy_version",
        "parameter_snapshot",
    ]
    assert validate_output_artifacts(set(REQUIRED_OUTPUT_ARTIFACTS)).passed is True


def test_generate_walk_forward_windows_rolls_train_and_validation_ranges():
    windows = generate_walk_forward_windows(
        start_ts=0,
        end_ts=10_000,
        train_seconds=4_000,
        validation_seconds=2_000,
        step_seconds=2_000,
    )
    assert windows == [
        WalkForwardWindow(train_start=0, train_end=4_000, validation_start=4_000, validation_end=6_000),
        WalkForwardWindow(train_start=2_000, train_end=6_000, validation_start=6_000, validation_end=8_000),
        WalkForwardWindow(train_start=4_000, train_end=8_000, validation_start=8_000, validation_end=10_000),
    ]
