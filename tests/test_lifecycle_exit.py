from src.backtest.engine import BacktestBar
from src.backtest.lifecycle_exit import AtrTpExitConfig, simulate_atr_tp_exit


def bar(timestamp, *, high, low, close=None, volume=10.0):
    price = close if close is not None else (high + low) / 2
    return BacktestBar("BTCUSDT", timestamp, price, high, low, price, volume)


def test_long_hits_tp_ladder_weighted_exit():
    result = simulate_atr_tp_exit(
        side="LONG",
        entry_time=0,
        entry_price=100.0,
        bars_after_entry=[
            bar(900, high=101.1, low=100.1),
            bar(1800, high=102.1, low=101.4),
            bar(2700, high=103.2, low=102.4),
        ],
        atr_pct=0.01,
        config=AtrTpExitConfig(atr_stop_mult=1.0, min_stop_pct=0.01, max_stop_pct=0.01),
    )

    assert result is not None
    assert result.exit_time == 2700
    assert result.average_exit_price == 101.85
    assert result.reason_exit == "atr_tp_tp_ladder_complete"
    assert result.events == ("TP1_HIT", "STOP_MOVED_TO_BREAKEVEN", "TP2_HIT", "TP3_HIT")
    assert [(item.reason, item.fraction) for item in result.partial_exits] == [
        ("TP1_HIT", 0.4),
        ("TP2_HIT", 0.35),
        ("TP3_HIT", 0.25),
    ]
    assert result.hold_bars == 3
    assert result.tp1_reached is True


def test_short_hits_tp_ladder_weighted_exit():
    result = simulate_atr_tp_exit(
        side="SHORT",
        entry_time=0,
        entry_price=100.0,
        bars_after_entry=[
            bar(900, high=99.9, low=98.9),
            bar(1800, high=98.6, low=97.9),
            bar(2700, high=97.4, low=96.8),
        ],
        atr_pct=0.01,
        config=AtrTpExitConfig(atr_stop_mult=1.0, min_stop_pct=0.01, max_stop_pct=0.01),
    )

    assert result is not None
    assert result.exit_time == 2700
    assert result.average_exit_price == 98.15
    assert result.reason_exit == "atr_tp_tp_ladder_complete"


def test_initial_stop_closes_remaining_position():
    result = simulate_atr_tp_exit(
        side="LONG",
        entry_time=0,
        entry_price=100.0,
        bars_after_entry=[bar(900, high=100.2, low=98.8)],
        atr_pct=0.01,
        config=AtrTpExitConfig(atr_stop_mult=1.0, min_stop_pct=0.01, max_stop_pct=0.01),
    )

    assert result is not None
    assert result.average_exit_price == 99.0
    assert result.reason_exit == "atr_tp_stop_hit"
    assert result.events == ("STOP_HIT",)


def test_same_bar_stop_and_tp_uses_conservative_stop_first():
    result = simulate_atr_tp_exit(
        side="LONG",
        entry_time=0,
        entry_price=100.0,
        bars_after_entry=[bar(900, high=101.5, low=98.8)],
        atr_pct=0.01,
        config=AtrTpExitConfig(atr_stop_mult=1.0, min_stop_pct=0.01, max_stop_pct=0.01),
    )

    assert result is not None
    assert result.average_exit_price == 99.0
    assert result.events == ("STOP_HIT",)


def test_tp1_moves_stop_to_breakeven_for_remaining_position():
    result = simulate_atr_tp_exit(
        side="LONG",
        entry_time=0,
        entry_price=100.0,
        bars_after_entry=[
            bar(900, high=101.1, low=100.2),
            bar(1800, high=100.5, low=99.9),
        ],
        atr_pct=0.01,
        config=AtrTpExitConfig(atr_stop_mult=1.0, min_stop_pct=0.01, max_stop_pct=0.01),
    )

    assert result is not None
    assert result.average_exit_price == 100.46
    assert result.reason_exit == "atr_tp_breakeven_stop_hit"
    assert result.events == ("TP1_HIT", "STOP_MOVED_TO_BREAKEVEN", "BREAKEVEN_STOP_HIT")
    assert result.partial_exits[-1].price == 100.1
    assert result.breakeven_active is True


def test_breakeven_price_includes_fee_buffer_for_short():
    result = simulate_atr_tp_exit(
        side="SHORT",
        entry_time=0,
        entry_price=100.0,
        bars_after_entry=[
            bar(900, high=99.8, low=98.9),
            bar(1800, high=100.2, low=99.5),
        ],
        atr_pct=0.01,
        config=AtrTpExitConfig(atr_stop_mult=1.0, min_stop_pct=0.01, max_stop_pct=0.01),
    )

    assert result is not None
    assert result.reason_exit == "atr_tp_breakeven_stop_hit"
    assert result.partial_exits[-1].price == 99.9
    assert result.average_exit_price == 99.54


def test_timeout_closes_remaining_at_last_close():
    result = simulate_atr_tp_exit(
        side="LONG",
        entry_time=0,
        entry_price=100.0,
        bars_after_entry=[
            bar(900, high=100.4, low=99.8, close=100.2),
            bar(1800, high=100.5, low=99.9, close=100.4),
        ],
        atr_pct=0.01,
        config=AtrTpExitConfig(atr_stop_mult=1.0, min_stop_pct=0.01, max_stop_pct=0.01, max_hold_bars=2),
    )

    assert result is not None
    assert result.exit_time == 1800
    assert result.average_exit_price == 100.4
    assert result.reason_exit == "atr_tp_max_hold_exit"
    assert result.partial_exits == (result.partial_exits[0],)
    assert result.partial_exits[0].reason == "MAX_HOLD_EXIT"
    assert result.partial_exits[0].bar_offset == 2
    assert result.hold_bars == 2


def test_atr_falls_back_to_default_when_signal_value_is_invalid():
    result = simulate_atr_tp_exit(
        side="LONG",
        entry_time=0,
        entry_price=100.0,
        bars_after_entry=[bar(900, high=101.6, low=100.0)],
        atr_pct=0.0,
        config=AtrTpExitConfig(default_atr_pct=0.01, atr_stop_mult=1.5, max_hold_bars=1),
    )

    assert result is not None
    assert result.partial_exits[0].price == 101.5


def test_adverse_volume_spike_reduces_half_before_stop():
    result = simulate_atr_tp_exit(
        side="LONG",
        entry_time=0,
        entry_price=100.0,
        bars_after_entry=[
            bar(900, high=100.2, low=99.35, close=99.5, volume=40.0),
            bar(1800, high=99.7, low=98.8, close=99.0, volume=20.0),
        ],
        atr_pct=0.01,
        config=AtrTpExitConfig(
            atr_stop_mult=1.0,
            min_stop_pct=0.01,
            max_stop_pct=0.01,
            adverse_reduce_enabled=True,
            adverse_reduce_r=0.6,
            adverse_reduce_fraction=0.5,
            adverse_volume_spike_mult=1.5,
            adverse_volume_lookback=1,
        ),
    )

    assert result is not None
    assert result.partial_exits[0].reason == "ADVERSE_REDUCE_0_6R"
    assert result.partial_exits[0].fraction == 0.5
    assert result.partial_exits[-1].reason == "STOP_HIT"
    assert result.average_exit_price == 99.2


def test_time_reduce_closes_half_when_trade_stalls_before_tp1():
    result = simulate_atr_tp_exit(
        side="LONG",
        entry_time=0,
        entry_price=100.0,
        bars_after_entry=[
            bar(900, high=100.2, low=99.9, close=100.1),
            bar(1800, high=100.2, low=99.9, close=100.15),
        ],
        atr_pct=0.01,
        config=AtrTpExitConfig(
            atr_stop_mult=1.0,
            min_stop_pct=0.01,
            max_stop_pct=0.01,
            max_hold_bars=2,
            time_reduce_enabled=True,
            time_reduce_bars=2,
            time_reduce_min_profit_r=0.3,
            time_reduce_fraction=0.5,
        ),
    )

    assert result is not None
    assert result.partial_exits[0].reason == "TIME_REDUCE_STALLED"
    assert result.partial_exits[0].fraction == 0.5
