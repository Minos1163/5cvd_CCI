import pytest

from src.risk.exit_engine import (
    EXIT_PRIORITY,
    ExitAction,
    ExitActionType,
    breakeven_stop,
    cooldown_until,
    forced_exit_actions,
    plan_take_profit_actions,
    select_highest_priority_action,
    trailing_stop_from_structure,
)
from src.risk.stop_engine import initial_atr_stop


def test_initial_atr_stop_uses_atr_distance_for_long():
    stop = initial_atr_stop(entry_price=100, atr=2, atr_mult=1.5, side="LONG")
    assert stop.stop_price == 97
    assert stop.stop_distance == 3
    assert stop.stop_pct == pytest.approx(0.03)
    assert stop.reason == "initial ATR stop"


def test_initial_atr_stop_uses_atr_distance_for_short():
    stop = initial_atr_stop(entry_price=100, atr=2, atr_mult=1.5, side="SHORT")
    assert stop.stop_price == 103
    assert stop.stop_distance == 3
    assert stop.stop_pct == pytest.approx(0.03)


def test_exit_priority_matches_spec_order():
    assert EXIT_PRIORITY == [
        ExitActionType.FORCED_STOP,
        ExitActionType.PORTFOLIO_RISK,
        ExitActionType.DIRECTION_REVERSAL,
        ExitActionType.VOLATILITY_ANOMALY,
        ExitActionType.TRAILING_STOP,
        ExitActionType.PARTIAL_TAKE_PROFIT,
    ]


def test_select_highest_priority_action_prevents_lower_priority_override():
    actions = [
        ExitAction(ExitActionType.PARTIAL_TAKE_PROFIT, "take tp1", reduce_pct=0.30),
        ExitAction(ExitActionType.FORCED_STOP, "stop hit", reduce_pct=1.0),
    ]
    selected = select_highest_priority_action(actions)
    assert selected is not None
    assert selected.action_type == ExitActionType.FORCED_STOP
    assert selected.reason == "stop hit"


def test_plan_take_profit_actions_are_r_based_partials_for_long():
    actions = plan_take_profit_actions(entry_price=100, stop_price=95, side="LONG")
    assert [action.target_price for action in actions] == [105, 110, 115]
    assert [action.reduce_pct for action in actions] == [0.30, 0.40, 0.30]
    assert all(action.action_type == ExitActionType.PARTIAL_TAKE_PROFIT for action in actions)


def test_plan_take_profit_actions_are_r_based_partials_for_short():
    actions = plan_take_profit_actions(entry_price=100, stop_price=105, side="SHORT", r_levels=(1, 2, 4))
    assert [action.target_price for action in actions] == [95, 90, 80]


def test_breakeven_stop_covers_fee_slippage_and_safety_buffer():
    stop = breakeven_stop(entry_price=100, side="LONG", fee_bps=5, slippage_bps=5, safety_bps=10)
    assert stop == pytest.approx(100.2)


def test_trailing_stop_uses_structure_without_widening_long_stop():
    action = trailing_stop_from_structure(
        side="LONG",
        current_stop=100,
        structure_price=103,
        buffer_pct=0.01,
    )
    assert action is not None
    assert action.stop_price == pytest.approx(101.97)
    assert action.action_type == ExitActionType.TRAILING_STOP


def test_trailing_stop_returns_none_when_it_would_widen_stop():
    action = trailing_stop_from_structure(
        side="LONG",
        current_stop=100,
        structure_price=99,
        buffer_pct=0.01,
    )
    assert action is None


def test_forced_exit_actions_use_highest_priority_flags():
    actions = forced_exit_actions(
        stop_hit=True,
        portfolio_risk=True,
        direction_reversal=True,
        volatility_anomaly=True,
    )
    selected = select_highest_priority_action(actions)
    assert selected is not None
    assert selected.action_type == ExitActionType.FORCED_STOP


def test_cooldown_until_counts_completed_bars():
    assert cooldown_until(now_ts=1_000, bars=4, timeframe_seconds=900) == 4_600
