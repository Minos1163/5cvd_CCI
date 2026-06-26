from src.backtest.engine import BacktestBar
from src.signals.pa_structure import score_price_action_structure

try:
    from src.signals.fib_location import SwingPoint
except ModuleNotFoundError:
    from dataclasses import dataclass

    @dataclass(frozen=True)
    class SwingPoint:
        kind: str
        timestamp: int
        index: int
        price: float


def bar(ts: int, open_: float, high: float, low: float, close: float) -> BacktestBar:
    return BacktestBar("TESTUSDT", ts, open_, high, low, close, 1000.0)


def test_lower_high_retest_scores_high_for_short():
    bars = [
        bar(0, 110, 111, 108, 109),
        bar(900, 109, 110, 104, 105),
        bar(1800, 105, 107, 103, 106),
        bar(2700, 106, 106.5, 101, 102),
    ]
    swings = [
        SwingPoint("HIGH", 0, 0, 111),
        SwingPoint("LOW", 900, 1, 104),
        SwingPoint("HIGH", 1800, 2, 107),
    ]

    result = score_price_action_structure(bars, "SHORT", swings, atr=2.0)

    assert result.score >= 15.0
    assert result.structure_tag in {"LOWER_HIGH_RETEST", "BREAKDOWN_RETEST"}


def test_large_move_no_structure_scores_low():
    bars = [
        bar(0, 110, 111, 109, 110),
        bar(900, 110, 110.2, 108, 108.2),
        bar(1800, 108.2, 108.5, 104, 104.5),
    ]

    result = score_price_action_structure(bars, "SHORT", [], atr=2.0)

    assert result.score <= 6.0
    assert result.structure_tag == "NO_STRUCTURE"


def test_reversal_wick_penalizes_short():
    bars = [
        bar(0, 100, 101, 99, 100),
        bar(900, 100, 105, 99.5, 100.5),
    ]

    result = score_price_action_structure(bars, "SHORT", [], atr=2.0)

    assert result.candle_score < 0
    assert "REVERSAL_WICK" in result.reasons


def test_breakdown_retest_scores_high():
    bars = [
        bar(0, 110, 111, 106, 107),
        bar(900, 107, 108, 101, 102),
        bar(1800, 102, 106.2, 101.5, 105.5),
        bar(2700, 105.5, 105.8, 100, 101),
    ]
    swings = [
        SwingPoint("LOW", 0, 0, 106),
        SwingPoint("HIGH", 1800, 2, 106.2),
    ]

    result = score_price_action_structure(bars, "SHORT", swings, atr=2.0)

    assert result.score >= 12.0
    assert result.structure_tag == "BREAKDOWN_RETEST"
