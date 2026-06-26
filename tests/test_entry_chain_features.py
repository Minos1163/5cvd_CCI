from src.backtest.engine import BacktestBar
from src.signals.entry_chain_features import completed_bars, component_scores, direction_from_history, trigger_score


def bar(ts, close, open_=None):
    return BacktestBar("SOLUSDT", ts, open_ if open_ is not None else close, close + 1, close - 1, close, 10)


def test_completed_bars_never_returns_future_timestamp():
    bars = [bar(100, 10), bar(200, 11), bar(300, 12)]

    result = completed_bars(bars, 200)

    assert [item.timestamp for item in result] == [100, 200]


def test_direction_from_history_uses_completed_history_only():
    bars = [bar(100, 100), bar(200, 100.2), bar(300, 100.5), bar(400, 101.0)]

    assert direction_from_history(bars) == "LONG"


def test_trigger_score_is_side_symmetric():
    long_bars = [bar(100, 100), bar(200, 100.1), bar(300, 100.4)]
    short_bars = [bar(100, 100), bar(200, 99.9), bar(300, 99.5)]

    assert trigger_score("LONG", long_bars) == 1.0
    assert trigger_score("SHORT", short_bars) == 1.0


def test_component_scores_include_ema_when_enabled():
    bars = [bar(index * 900, 100 + index * 0.2) for index in range(240)]
    completed = {"15m": bars, "30m": bars, "1h": bars, "4h": bars}

    scores = component_scores("LONG", completed, atr_pct_value=0.01, use_ema_architecture=True)

    assert "ema_50_quality" in scores
    assert "ema_momentum" in scores
    assert scores["ema_200_gate"] == 1.0
    assert scores["ema_50_quality"] > 0
    assert scores["ema_momentum"] > 0


def test_fib_pa_component_scores_are_present_when_enabled():
    bars_15m = [
        BacktestBar("SOLUSDT", 1000 + index * 900, 100 - index * 0.2, 101 - index * 0.2, 99 - index * 0.2, 100 - index * 0.2, 1000)
        for index in range(240)
    ]
    completed = {"15m": bars_15m, "1h": bars_15m[-80:], "30m": bars_15m[-80:], "4h": bars_15m[-80:]}

    scores = component_scores(
        "SHORT",
        completed,
        atr_pct_value=0.01,
        use_ema_architecture=True,
        ema200_gate_mode="soft",
        use_fib_pa_architecture=True,
    )

    assert "trend_ema_context" in scores
    assert "flow_cvd_confirmation" in scores
    assert "cci_momentum_quality" in scores
    assert "price_action_structure" in scores
    assert "fibonacci_location" in scores
    assert "risk_reward_geometry" in scores
