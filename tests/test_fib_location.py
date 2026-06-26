from src.backtest.engine import BacktestBar
from src.signals.fib_location import (
    compute_fib_levels,
    detect_fractal_swings,
    score_fibonacci_location,
)


def bar(ts: int, open_: float, high: float, low: float, close: float) -> BacktestBar:
    return BacktestBar("TESTUSDT", ts, open_, high, low, close, 1000.0)


def test_compute_downtrend_fib_levels():
    levels = compute_fib_levels(110.0, 100.0, "DOWN")

    assert levels["r382"] == 103.82
    assert levels["r500"] == 105.0
    assert levels["r618"] == 106.18
    assert levels["e1272"] == 97.28
    assert levels["e1618"] == 93.82


def test_extension_exhaustion_returns_block():
    levels = compute_fib_levels(110.0, 100.0, "DOWN")

    result = score_fibonacci_location(
        close=94.0,
        side="SHORT",
        fib_1h=levels,
        fib_15m=None,
        atr=1.0,
    )

    assert result.score == 0.0
    assert result.action_cap == "NO_TRADE"
    assert result.tag == "FIB_1H_EXTENSION_EXHAUSTION_BLOCK"


def test_optimal_pullback_returns_max_score():
    levels = compute_fib_levels(110.0, 100.0, "DOWN")

    result = score_fibonacci_location(
        close=105.0,
        side="SHORT",
        fib_1h=levels,
        fib_15m=None,
        atr=1.0,
    )

    assert result.score == 18.0
    assert result.action_cap is None
    assert result.tag == "FIB_1H_PULLBACK_OPTIMAL"


def test_neutral_location_returns_mid_score_without_levels():
    result = score_fibonacci_location(
        close=105.0,
        side="SHORT",
        fib_1h=None,
        fib_15m=None,
        atr=1.0,
    )

    assert result.score == 9.0
    assert result.tag == "FIB_NEUTRAL"


def test_fractal_swings_filter_noise_by_atr_and_spacing():
    bars = [
        bar(0, 100, 101, 99, 100),
        bar(900, 100, 102, 99, 101),
        bar(1800, 101, 105, 100, 104),
        bar(2700, 104, 103, 98, 99),
        bar(3600, 99, 101, 97, 100),
        bar(4500, 100, 102, 99, 101),
        bar(5400, 101, 103, 100, 102),
    ]

    swings = detect_fractal_swings(bars, k=2, min_atr_mult=1.0, min_spacing_bars=2, atr=2.0)

    assert any(item.kind == "HIGH" and item.price == 105 for item in swings)
