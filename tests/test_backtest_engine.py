import pytest

from src.backtest.engine import (
    BACKTEST_ANALYSIS_DIMENSIONS,
    BACKTEST_ARTIFACTS,
    BACKTEST_FILL_MODELS,
    BACKTEST_FORBIDDEN_ACTIONS,
    BACKTEST_REQUIRED_EVENTS,
    BACKTEST_REQUIRED_INPUTS,
    BACKTEST_RESULT_FIELDS,
    BACKTEST_STEP_ORDER,
    BacktestBar,
    BacktestRequest,
    assert_no_lookahead,
    build_artifact_manifest,
    run_backtest,
    validate_backtest_request,
)


def bar(
    timestamp: int,
    *,
    symbol: str = "BTCUSDT",
    open: float = 100.0,
    high: float | None = None,
    low: float | None = None,
    close: float = 101.0,
    volume: float = 10.0,
) -> BacktestBar:
    candle_high = max(open, close) + 5 if high is None else high
    candle_low = min(open, close) - 5 if low is None else low
    return BacktestBar(
        symbol=symbol,
        timestamp=timestamp,
        open=open,
        high=candle_high,
        low=candle_low,
        close=close,
        volume=volume,
    )


def valid_request(**overrides) -> BacktestRequest:
    values = {
        "run_id": "run-19",
        "strategy_name": "ai300",
        "strategy_version": "v1",
        "config_version": "cfg-1",
        "data_version": "data-1",
        "symbols": ["BTCUSDT"],
        "timeframes": ["15m", "30m", "1h", "4h"],
        "start_time": 0,
        "end_time": 2700,
        "initial_capital": 10_000.0,
        "fee_model": {"fee_bps": 5},
        "slippage_model": {"slippage_bps": 10},
        "funding_model": {},
        "fill_model": "NEXT_BAR_OPEN",
        "capital_constraints": {"notional_per_trade": 1_000},
        "risk_constraints": {},
        "entry_modes": ["PROBE", "DIRECT"],
        "source": "unit-test",
    }
    values.update(overrides)
    return BacktestRequest(**values)


def always_long_direct(request, symbol, current_bar, context):
    return {
        "signal_type": "LONG",
        "signal_side": "LONG",
        "entry_mode": "DIRECT",
        "risk_allowed": True,
        "notional": 1_000,
    }


def alternating_strategy(request, symbol, current_bar, context):
    side = "SHORT" if symbol == "ETHUSDT" else "LONG"
    return {
        "signal_type": side,
        "signal_side": side,
        "entry_mode": "DIRECT",
        "risk_allowed": True,
        "notional": 500,
    }


def blocked_strategy(request, symbol, current_bar, context):
    if current_bar.timestamp == 0:
        return {"signal_type": "NO_TRADE", "signal_side": "NONE", "entry_mode": "NONE"}
    return {
        "signal_type": "LONG",
        "signal_side": "LONG",
        "entry_mode": "DIRECT",
        "risk_allowed": False,
        "risk_reason": "DAILY_LOSS_LIMIT_REACHED",
    }


def test_backtest_engine_contract_matches_19_doc():
    assert BACKTEST_REQUIRED_INPUTS == [
        "run_id",
        "strategy_name",
        "strategy_version",
        "config_version",
        "data_version",
        "symbols",
        "timeframes",
        "start_time",
        "end_time",
        "initial_capital",
        "fee_model",
        "slippage_model",
        "funding_model",
        "fill_model",
        "capital_constraints",
        "risk_constraints",
        "entry_modes",
        "source",
    ]
    assert BACKTEST_RESULT_FIELDS == [
        "run_id",
        "status",
        "final_equity",
        "total_return",
        "annual_return",
        "max_drawdown",
        "profit_factor",
        "sharpe",
        "sortino",
        "win_rate",
        "avg_win",
        "avg_loss",
        "expectancy",
        "trade_count",
        "symbol_breakdown",
        "side_breakdown",
        "entry_mode_breakdown",
        "summary_json",
        "report_path",
    ]
    assert BACKTEST_STEP_ORDER == [
        "update_current_time_step_data",
        "update_indicators",
        "update_multi_timeframe_context",
        "update_current_position_state",
        "check_exits",
        "check_reductions",
        "check_additions",
        "check_entries",
        "simulate_order_submit_and_fill",
        "write_events_logs_snapshots",
        "advance",
    ]
    assert BACKTEST_FILL_MODELS == ["NEXT_BAR_OPEN", "TRIGGER_PRICE", "CONSERVATIVE_LIMIT_FILL"]
    assert "ORDER_FILLED" in BACKTEST_REQUIRED_EVENTS
    assert "performance_summary.html" in BACKTEST_ARTIFACTS
    assert "use_future_bar" in BACKTEST_FORBIDDEN_ACTIONS
    assert "entry_mode" in BACKTEST_ANALYSIS_DIMENSIONS


def test_validate_backtest_request_rejects_missing_duplicate_and_gap_data():
    request = valid_request()
    missing = validate_backtest_request(request, {})
    assert missing.status == "rejected"
    assert any("missing bars" in item for item in missing.issues)

    duplicate_bars = [
        bar(0, close=100),
        bar(900, close=101),
        bar(900, close=102),
    ]
    duplicate = validate_backtest_request(request, {"BTCUSDT": duplicate_bars})
    assert duplicate.status == "rejected"
    assert any("duplicate timestamp" in item for item in duplicate.issues)

    gap_bars = [bar(0, close=100), bar(1800, close=101)]
    gap = validate_backtest_request(request, {"BTCUSDT": gap_bars})
    assert gap.status == "rejected"
    assert any("gap before" in item for item in gap.issues)


def test_assert_no_lookahead_blocks_future_data():
    assert_no_lookahead(900, 900)
    with pytest.raises(ValueError, match="future"):
        assert_no_lookahead(900, 1800)


def test_next_bar_open_fill_uses_next_bar_and_not_same_bar():
    request = valid_request(fill_model="NEXT_BAR_OPEN")
    bars = {"BTCUSDT": [bar(0, open=100, close=101), bar(900, open=110, close=111), bar(1800, open=120, close=121)]}
    result = run_backtest(request, bars, strategy_callback=always_long_direct)
    assert result.status == "completed"
    assert result.trades[0].entry_time == 900
    assert result.trades[0].entry_price > 110
    assert result.trades[0].reason_exit == "one_bar_exit"
    assert result.trades[0].partial_exits == ()
    assert result.summary_json["fill_model"] == "NEXT_BAR_OPEN"


def test_atr_tp_exit_model_routes_through_lifecycle():
    request = valid_request(
        risk_constraints={
            "exit_model": "atr_tp",
            "atr_stop_mult": 1.0,
            "min_stop_pct": 0.01,
            "max_stop_pct": 0.01,
            "tp_levels": (1.0, 2.0, 3.0),
            "tp_fractions": (0.4, 0.35, 0.25),
            "max_hold_bars": 3,
        },
        slippage_model={"slippage_bps": 0},
    )
    bars = {
        "BTCUSDT": [
            bar(0, open=100, close=100),
            bar(900, open=100, high=101.1, low=100.0, close=101),
            bar(1800, open=101, high=102.2, low=101.0, close=102),
            bar(2700, open=102, high=103.3, low=102.0, close=103),
        ]
    }

    result = run_backtest(request, bars, strategy_callback=always_long_direct)

    assert result.trades[0].reason_exit == "atr_tp_tp_ladder_complete"
    assert result.trades[0].exit_time == 2700
    assert result.trades[0].exit_price == 101.85
    assert len(result.trades[0].partial_exits) == 3
    assert result.trades[0].partial_exits[0]["reason"] == "TP1_HIT"
    assert result.trades[0].tp1_reached is True
    assert result.trades[0].hold_bars == 3


def test_atr_tp_fee_accounting_uses_partial_exit_notional():
    request = valid_request(
        risk_constraints={
            "exit_model": "atr_tp",
            "atr_stop_mult": 1.0,
            "min_stop_pct": 0.01,
            "max_stop_pct": 0.01,
            "tp_levels": (1.0, 2.0, 3.0),
            "tp_fractions": (0.4, 0.35, 0.25),
            "max_hold_bars": 3,
        },
        fee_model={"fee_bps": 5},
        slippage_model={"slippage_bps": 0},
    )
    bars = {
        "BTCUSDT": [
            bar(0, open=100, close=100),
            bar(900, open=100, high=101.1, low=100.0, close=101),
            bar(1800, open=101, high=102.2, low=101.0, close=102),
            bar(2700, open=102, high=103.3, low=102.0, close=103),
        ]
    }

    result = run_backtest(request, bars, strategy_callback=always_long_direct)
    trade = result.trades[0]
    expected_exit_fee_notional = 0.4 * 101 + 0.35 * 102 + 0.25 * 103
    expected_fees = 1000 * 0.0005 + (1000 / 100) * expected_exit_fee_notional * 0.0005

    assert round(trade.fees, 6) == round(expected_fees, 6)
    assert round(trade.total_fees_pct, 6) == round(expected_fees / 1000, 6)


def test_atr_tp_slippage_accounts_for_entry_and_partial_exits():
    request = valid_request(
        risk_constraints={
            "exit_model": "atr_tp",
            "atr_stop_mult": 1.0,
            "min_stop_pct": 0.01,
            "max_stop_pct": 0.01,
            "tp_levels": (1.0, 2.0, 3.0),
            "tp_fractions": (0.4, 0.35, 0.25),
            "max_hold_bars": 3,
        },
        fee_model={"fee_bps": 0},
        slippage_model={"slippage_bps": 10},
    )
    bars = {
        "BTCUSDT": [
            bar(0, open=100, close=100),
            bar(900, open=100, high=101.2, low=100.0, close=101),
            bar(1800, open=101, high=102.3, low=101.0, close=102),
            bar(2700, open=102, high=103.4, low=102.0, close=103),
        ]
    }

    result = run_backtest(request, bars, strategy_callback=always_long_direct)
    trade = result.trades[0]

    assert trade.entry_slippage > 0
    assert trade.exit_slippage > 0
    assert trade.slippage == trade.entry_slippage + trade.exit_slippage
    assert trade.net_pnl == trade.gross_pnl - trade.slippage


def test_atr_tp_records_mfe_mae_and_stop_offset_for_long():
    request = valid_request(
        risk_constraints={
            "exit_model": "atr_tp",
            "atr_stop_mult": 1.0,
            "min_stop_pct": 0.01,
            "max_stop_pct": 0.01,
            "max_hold_bars": 3,
        },
        fee_model={"fee_bps": 0},
        slippage_model={"slippage_bps": 0},
    )
    bars = {
        "BTCUSDT": [
            bar(0, open=100, close=100),
            bar(900, open=100, high=100.5, low=99.5, close=100),
            bar(1800, open=100, high=100.2, low=98.9, close=99),
            bar(2700, open=99, high=99.2, low=98.5, close=98.8),
        ]
    }

    result = run_backtest(request, bars, strategy_callback=always_long_direct)
    trade = result.trades[0]

    assert trade.reason_exit == "atr_tp_stop_hit"
    assert trade.stop_hit_bar_offset == 2
    assert trade.mfe_pct == 0.005
    assert trade.mae_pct == -0.011


def test_leverage_simulation_uses_effective_notional_for_economics():
    request = valid_request(
        risk_constraints={"enable_leverage_simulation": True, "fixed_leverage": 3},
        fee_model={"fee_bps": 5},
        slippage_model={"slippage_bps": 0},
    )
    bars = {"BTCUSDT": [bar(0, open=100, close=100), bar(900, open=100, close=101), bar(1800, open=110, close=110)]}

    result = run_backtest(request, bars, strategy_callback=always_long_direct)
    trade = result.trades[0]

    assert trade.leverage == 3
    assert trade.margin_notional == 1000
    assert trade.effective_notional == 3000
    assert round(trade.quantity, 6) == 30.0
    assert trade.gross_pnl > 290
    assert trade.fees > 3
    assert trade.net_pnl == trade.gross_pnl - trade.fees - trade.slippage - trade.funding


def test_leverage_simulation_is_disabled_by_default():
    result = run_backtest(
        valid_request(),
        {"BTCUSDT": [bar(0, open=100, close=100), bar(900, open=100, close=101), bar(1800, open=110, close=110)]},
        strategy_callback=always_long_direct,
    )
    trade = result.trades[0]

    assert trade.leverage == 1
    assert trade.margin_notional == 1000
    assert trade.effective_notional == 1000


def test_runner_records_required_events_breakdowns_and_costs():
    request = valid_request(symbols=["BTCUSDT", "ETHUSDT"])
    bars = {
        "BTCUSDT": [
            bar(0, symbol="BTCUSDT"),
            bar(900, symbol="BTCUSDT", open=102, close=103),
            bar(1800, symbol="BTCUSDT", open=105, close=106),
        ],
        "ETHUSDT": [
            bar(0, symbol="ETHUSDT", open=50, close=49),
            bar(900, symbol="ETHUSDT", open=50, close=48),
            bar(1800, symbol="ETHUSDT", open=49, close=47),
        ],
    }
    result = run_backtest(request, bars, strategy_callback=alternating_strategy)
    event_names = [item["event_type"] for item in result.events]
    assert "SIGNAL_CREATED" in event_names
    assert "ORDER_SUBMITTED" in event_names
    assert "ORDER_FILLED" in event_names
    assert "BACKTEST_STEP_COMPLETED" in event_names
    assert result.symbol_breakdown["BTCUSDT"]["trade_count"] >= 1
    assert "LONG" in result.side_breakdown
    assert "DIRECT" in result.entry_mode_breakdown
    assert result.trades[0].fees > 0
    assert result.trades[0].slippage > 0
    assert "funding_missing_approximate" in result.degraded_assumptions


def test_risk_block_and_signal_rejection_are_failed_samples():
    result = run_backtest(valid_request(), {"BTCUSDT": [bar(0), bar(900), bar(1800)]}, strategy_callback=blocked_strategy)
    assert any(item["type"] == "risk_blocked" for item in result.failed_samples)
    assert any(item["event_type"] == "RISK_BLOCKED" for item in result.risk_events)
    assert any(item["type"] == "signal_rejected" for item in result.failed_samples)


def test_daily_loss_breaker_blocks_new_entries_after_threshold():
    request = valid_request(
        risk_constraints={"daily_hard_loss_pct": 0.01},
        fee_model={"fee_bps": 0},
        slippage_model={"slippage_bps": 0},
    )
    bars = {
        "BTCUSDT": [
            bar(0, open=100, close=100),
            bar(900, open=100, close=90),
            bar(1800, open=90, close=90),
            bar(2700, open=90, close=95),
        ]
    }

    result = run_backtest(request, bars, strategy_callback=always_long_direct)

    assert result.trade_count == 1
    assert any(item["payload"].get("reason") == "DAILY_HARD_LOSS_CIRCUIT" for item in result.risk_events)


def test_conservative_limit_fill_rejects_uncrossed_limit_order():
    request = valid_request(fill_model="CONSERVATIVE_LIMIT_FILL")
    bars = {"BTCUSDT": [bar(0), bar(900, low=99, high=105), bar(1800)]}

    def limit_not_crossed(request, symbol, current_bar, context):
        return {
            "signal_type": "LONG",
            "signal_side": "LONG",
            "entry_mode": "DIRECT",
            "risk_allowed": True,
            "order_type": "LIMIT",
            "limit_price": 90,
        }

    result = run_backtest(request, bars, strategy_callback=limit_not_crossed)
    assert any(item["event_type"] == "ORDER_REJECTED" for item in result.events)
    assert any(item["type"] == "execution_rejected" for item in result.failed_samples)
    assert result.trade_count == 0


def test_build_artifact_manifest_lists_required_files():
    manifest = build_artifact_manifest(valid_request("run-1") if False else valid_request())
    assert manifest["backtest_result.json"].endswith("backtest_result.json")
    assert set(BACKTEST_ARTIFACTS) == set(manifest)
