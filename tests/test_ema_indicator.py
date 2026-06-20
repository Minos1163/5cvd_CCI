from src.indicators.ema import bars_since_cross, ema, ema_latest, normalized_ema_slope


def test_ema_returns_none_until_period_is_available():
    assert ema([1, 2, 3], period=5) == []
    assert ema_latest([1, 2, 3], period=5) is None


def test_ema_uses_sma_seed_and_standard_multiplier():
    values = [10, 11, 12, 13, 14, 15]
    result = ema(values, period=3)

    assert result[0] == 11.0
    assert round(result[-1], 6) == 14.0
    assert ema_latest(values, period=3) == result[-1]


def test_normalized_ema_slope_uses_completed_series_only():
    series = [100, 101, 102, 103, 104, 105]

    assert round(normalized_ema_slope(series, lookback=5), 6) == 0.05
    assert normalized_ema_slope([100, 101], lookback=5) == 0.0


def test_bars_since_cross_detects_latest_side_stability():
    closes = [99, 100, 101, 102, 103]
    ema_values = [100, 100, 100, 100, 100]
    assert bars_since_cross(closes, ema_values) == 2

    choppy_closes = [99, 101, 99, 101]
    choppy_ema = [100, 100, 100, 100]
    assert bars_since_cross(choppy_closes, choppy_ema) == 0
