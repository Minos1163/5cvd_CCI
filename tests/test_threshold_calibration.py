import pytest

from src.utils.threshold_calibration import (
    InsufficientSamplesError,
    calibrate_threshold_from_distribution,
    percentile,
)


def test_percentile_linear_interpolation():
    values = [0.0, 10.0, 20.0, 30.0]
    assert percentile(values, 0) == 0.0
    assert percentile(values, 100) == 30.0
    assert percentile(values, 50) == 15.0
    assert percentile(values, 25) == 7.5


def test_percentile_validation():
    with pytest.raises(ValueError):
        percentile([1.0], -1)
    with pytest.raises(ValueError):
        percentile([1.0], 101)
    with pytest.raises(ValueError):
        percentile([], 50)


def test_calibrate_default_pass_rate_is_p95():
    # 5% pass rate → threshold at P95 of a 1000-sample uniform-ish distribution.
    scores = list(range(1000))
    threshold = calibrate_threshold_from_distribution(scores, target_pass_rate=0.05)
    assert abs(threshold - 950.0) < 1.0


def test_calibrate_pass_rate_maps_to_quantile():
    scores = list(range(1000))
    # 10% pass rate → P90 ≈ 900
    threshold = calibrate_threshold_from_distribution(scores, target_pass_rate=0.10)
    assert abs(threshold - 900.0) < 1.0
    # 1% pass rate → P99 ≈ 990
    strict = calibrate_threshold_from_distribution(scores, target_pass_rate=0.01)
    assert abs(strict - 990.0) < 1.0
    assert strict > threshold


def test_calibrate_insufficient_samples_raises():
    with pytest.raises(InsufficientSamplesError):
        calibrate_threshold_from_distribution([50.0, 60.0, 70.0])


def test_calibrate_min_samples_override():
    scores = [10.0, 20.0, 30.0, 40.0]
    threshold = calibrate_threshold_from_distribution(scores, target_pass_rate=0.25, min_samples=4)
    # P75 of 4 values with linear interpolation
    assert threshold == pytest.approx(32.5)


def test_calibrate_min_absolute_floor_applies():
    scores = list(range(1000))
    # Calibrated P90 ≈ 900, but floor forces it up.
    threshold = calibrate_threshold_from_distribution(
        scores, target_pass_rate=0.10, min_absolute_floor=950.0
    )
    assert threshold == 950.0
    # Floor below the calibrated value leaves it untouched.
    threshold = calibrate_threshold_from_distribution(
        scores, target_pass_rate=0.10, min_absolute_floor=500.0
    )
    assert threshold < 950.0


def test_calibrate_invalid_pass_rate():
    with pytest.raises(ValueError):
        calibrate_threshold_from_distribution(list(range(100)), target_pass_rate=0.0)
    with pytest.raises(ValueError):
        calibrate_threshold_from_distribution(list(range(100)), target_pass_rate=1.0)
