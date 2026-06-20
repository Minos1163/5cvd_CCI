# V8 Rolling Window Robustness Report

Date: 2026-06-19

Purpose: add rolling-window validation infrastructure for V6/V7 candidates and check whether the local dataset can support the requested 9-12 month robustness test. This is research evidence only. It does not approve live trading.

---

## Decision

Rolling validation is not complete.

The new runner is implemented and can execute rolling 30D windows, but the local dataset only covers about 30 days. That is insufficient for the requested 12-month validation.

Current status:

```text
status: insufficient_coverage
available_days: 30.0
required_days: 365
```

Do not promote V7 or deploy from this result. V6 dynamic 3-5x remains the best latest-30D single-window baseline, not a validated robust strategy.

---

## Implemented

New files:

- `scripts/run_rolling_backtest.py`
- `tests/test_rolling_backtest.py`

Artifacts produced:

- `reports/backtests/v8_coverage_check/rolling_summary.json`
- `reports/backtests/v8_short_smoke/rolling_summary.json`
- `reports/backtests/v8_short_smoke/rolling_windows.csv`
- `reports/backtests/v8_short_smoke_v7_time_reduce/rolling_summary.json`
- `reports/backtests/v8_short_smoke_v7_time_reduce/rolling_windows.csv`

The runner supports:

- manifest coverage inspection
- 30D window generation stepped by 7D
- insufficient-coverage failure mode
- V6 dynamic 3-5x candidate
- V7 time-reduce candidate
- per-window result artifacts
- aggregate median/IQR/worst/best statistics
- margin-call proxy counts

---

## Coverage Check

Command:

```powershell
python scripts/run_rolling_backtest.py --data-dir data/raw/binance_futures/latest_30d --run-id v8_coverage_check
```

Result:

```text
status: insufficient_coverage
candidate: v6_dynamic
available_days: 30.0
required_days: 365
```

This is the correct behavior. The runner refuses to pretend that one 30D sample is a 12-month rolling validation.

---

## Short-Coverage Smoke Tests

These smoke tests prove the runner can execute the existing backtest path. They are not robustness evidence.

| Candidate | Return | Win Rate | PF | Max DD | Sharpe | Trades | Margin Proxy |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| V6 dynamic 3-5x | +40.21% | 76.99% | 2.1277 | 6.09% | 2.7812 | 113 | 0 |
| V7 time reduce | +39.06% | 76.99% | 2.2299 | 6.09% | 2.8546 | 113 | 0 |

Interpretation:

- V6 dynamic remains the best single-window return baseline.
- V7 time reduce still improves PF and Sharpe but slightly lowers return.
- Neither result validates robustness because each has only one window.

---

## Required Next Commands

Download a longer local dataset:

```powershell
python scripts/download_latest_30d_market_data.py --days 365 --output-dir data/raw/binance_futures/latest_365d
```

Run V6 dynamic rolling validation:

```powershell
python scripts/run_rolling_backtest.py --data-dir data/raw/binance_futures/latest_365d --run-id v8_v6_dynamic_12m --candidate v6_dynamic --required-days 365 --window-days 30 --step-days 7
```

Run V7 time-reduce rolling validation:

```powershell
python scripts/run_rolling_backtest.py --data-dir data/raw/binance_futures/latest_365d --run-id v8_v7_time_reduce_12m --candidate v7_time_reduce --required-days 365 --window-days 30 --step-days 7
```

---

## Pass Criteria For The Next Report

The next report should include:

- rolling monthly return median and IQR
- worst window and best window
- negative-window count
- max consecutive negative windows
- median and worst win rate
- median and max drawdown
- median Sharpe
- profit factor distribution
- trade count distribution
- margin-call proxy count
- notes on failed regimes

Suggested rejection lines:

- any month below `-15%`
- two consecutive negative 30D windows
- max drawdown above `15%` for dynamic 3-5x
- median win rate below `70%`
- frequent margin-call proxy events

---

## Bottom Line

V8 completed the validation framework, not the validation conclusion.

The local evidence still says:

```text
single-window V6 dynamic is strong,
V7 time reduce is a plausible risk-adjusted candidate,
but 12-month robustness is blocked until longer data is available.
```

No live deployment should be discussed until the rolling-window report exists.
