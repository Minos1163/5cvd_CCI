from scripts.run_rolling_backtest import (
    coverage_days,
    generate_windows,
    max_consecutive_negative,
    summarize_windows,
    validate_coverage,
)


def test_generate_windows_uses_30d_window_and_7d_step():
    windows = generate_windows(0, 40 * 86400, window_days=30, step_days=7)

    assert windows == [(0, 30 * 86400), (7 * 86400, 37 * 86400)]


def test_coverage_days_counts_available_span():
    assert coverage_days(0, 30 * 86400) == 30.0


def test_max_consecutive_negative_counts_streak():
    assert max_consecutive_negative([1.0, -1.0, -2.0, 0.5, -0.1]) == 2


def test_summarize_windows_reports_median_iqr_and_failures():
    rows = [
        {"total_return": 0.10, "win_rate": 0.80, "max_drawdown": 0.05, "sharpe": 2.0},
        {"total_return": -0.05, "win_rate": 0.60, "max_drawdown": 0.10, "sharpe": -1.0},
        {"total_return": 0.20, "win_rate": 0.75, "max_drawdown": 0.03, "sharpe": 3.0},
    ]

    summary = summarize_windows(rows)

    assert summary["window_count"] == 3
    assert summary["median_return"] == 0.10
    assert summary["worst_return"] == -0.05
    assert summary["negative_window_count"] == 1
    assert summary["max_consecutive_negative_windows"] == 1
    assert summary["median_win_rate"] == 0.75


def test_validate_coverage_rejects_short_dataset():
    result = validate_coverage(available_days=30, required_days=365)

    assert result["ok"] is False
    assert result["available_days"] == 30
    assert result["required_days"] == 365
