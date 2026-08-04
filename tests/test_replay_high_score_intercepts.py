from scripts.replay_high_score_intercepts import (
    DecisionRow,
    replay_intercept,
    select_intercepts,
    summarize_results,
)


def row(
    ts,
    symbol="LINKUSDT",
    side="LONG",
    action="WATCH",
    score=86.0,
    close=100.0,
    high=101.0,
    low=99.0,
    reasons=None,
    stop_pct=0.01,
):
    return DecisionRow(
        day="2026-07-01",
        timestamp=ts,
        symbol=symbol,
        side=side,
        action=action,
        score=score,
        reasons=tuple(reasons or ("SIDE_THRESHOLD_OFFSET_LONG_10.00",)),
        close=close,
        high=high,
        low=low,
        stop_pct=stop_pct,
        component_points={"price_action_structure": 20.0, "risk_reward_geometry": 4.0},
    )


def test_select_intercepts_excludes_live_actions_and_low_scores():
    rows = [
        row(1, action="WATCH", score=85.0),
        row(2, action="NO_TRADE", score=90.0, reasons=("FIB_EXTENSION_EXHAUSTION_BLOCK",)),
        row(3, action="DIRECT", score=91.0),
        row(4, action="WATCH", score=84.9),
    ]

    selected = select_intercepts(rows, min_score=85.0)

    assert [item.timestamp for item in selected] == [1, 2]


def test_select_intercepts_can_include_focus_reason_below_min_score():
    rows = [
        row(1, action="WATCH", score=84.0, reasons=("FIB_EXTENSION_EXHAUSTION_BLOCK",)),
        row(2, action="WATCH", score=84.0, reasons=("SYMBOL_WATCH_ONLY",)),
    ]

    selected = select_intercepts(rows, min_score=85.0, include_reasons=("FIB_EXTENSION_EXHAUSTION_BLOCK",))

    assert [item.timestamp for item in selected] == [1]


def test_replay_long_hits_tp2_before_horizon():
    entry = row(100, close=100.0, stop_pct=0.01)
    future = [
        row(200, close=100.8, high=101.0, low=99.7),
        row(300, close=102.1, high=102.2, low=100.5),
    ]

    result = replay_intercept(entry, future, horizon_bars=4)

    assert result is not None
    assert result.max_tp_hit == 2
    assert result.stop_hit is False
    assert result.mfe_r >= 2.0
    assert result.mae_r <= 0.3


def test_replay_short_stop_hit():
    entry = row(100, side="SHORT", close=100.0, stop_pct=0.01)
    future = [row(200, side="SHORT", close=100.9, high=101.2, low=99.8)]

    result = replay_intercept(entry, future, horizon_bars=4)

    assert result is not None
    assert result.stop_hit is True
    assert result.final_r <= -1.0
    assert result.blended_final_r <= -1.0


def test_replay_stop_first_ignores_same_bar_tp_touch_for_terminal_accounting():
    entry = row(100, close=100.0, stop_pct=0.01)
    future = [row(200, close=100.5, high=103.2, low=98.9)]

    result = replay_intercept(entry, future, horizon_bars=4)

    assert result is not None
    assert result.stop_hit is True
    assert result.max_tp_hit == 0
    assert result.first_terminal == "INITIAL_STOP_HIT"
    assert result.blended_final_r == -1.0


def test_replay_tp_first_counts_same_bar_tp_before_stop_when_requested():
    entry = row(100, close=100.0, stop_pct=0.01)
    future = [row(200, close=100.5, high=103.2, low=98.9)]

    result = replay_intercept(entry, future, horizon_bars=4, bar_order_assumption="tp_first")

    assert result is not None
    assert result.stop_hit is True
    assert result.max_tp_hit == 3
    assert result.first_terminal == "TP_THEN_INITIAL_STOP_HIT"
    assert result.blended_final_r > 1.0


def test_replay_blended_final_r_uses_tp_ladder_and_horizon_close():
    entry = row(100, close=100.0, stop_pct=0.01)
    future = [
        row(200, close=101.3, high=101.3, low=100.2),
        row(300, close=101.0, high=101.1, low=100.8),
    ]

    result = replay_intercept(entry, future, horizon_bars=4)

    assert result is not None
    assert result.max_tp_hit == 1
    assert result.stop_hit is False
    assert result.blended_final_r == 1.08


def test_summarize_results_by_reason_and_symbol():
    entry = row(100, symbol="LINKUSDT")
    future = [row(200, symbol="LINKUSDT", close=102.5, high=102.5, low=99.9)]
    result = replay_intercept(entry, future, horizon_bars=4)

    summary = summarize_results([result])

    assert summary["total"] == 1
    assert summary["by_primary_reason"]["SIDE_THRESHOLD_OFFSET_LONG_10.00"]["count"] == 1
    assert summary["by_symbol"]["LINKUSDT"]["count"] == 1
