from src.backtest.engine import BacktestBar
from src.signals.cci_quality import cci_series, score_cci_momentum_quality


def bar(ts: int, high: float, low: float, close: float) -> BacktestBar:
    return BacktestBar("TESTUSDT", ts, close, high, low, close, 1000.0)


def test_cci_series_returns_values_after_period():
    bars = [bar(i * 900, 101 + i, 99 + i, 100 + i) for i in range(30)]

    values = cci_series(bars, period=20)

    assert len(values) == 11
    assert all(isinstance(item, float) for item in values)


def test_short_exhaustion_below_minus_150_is_penalized():
    result = score_cci_momentum_quality([-90, -130, -170, -190], "SHORT")

    assert result.score <= 3.0
    assert result.tag == "CCI_SHORT_EXHAUSTION"


def test_short_secondary_weakness_scores_high():
    result = score_cci_momentum_quality([-180, -120, -70, -95, -130], "SHORT")

    assert result.score == 14.0
    assert result.tag == "CCI_SHORT_SECONDARY_WEAKNESS"


def test_short_failed_continuation_scores_zero():
    result = score_cci_momentum_quality([-150, -120, -75, -55], "SHORT")

    assert result.score == 0.0
    assert result.tag == "CCI_SHORT_FAILED_CONTINUATION"
