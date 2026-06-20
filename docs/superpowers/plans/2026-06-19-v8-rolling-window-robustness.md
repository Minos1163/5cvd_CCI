# V8 Rolling Window Robustness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add rolling 30D window robustness validation for the current V6/V7 candidates and produce an honest data-coverage report before any further optimization.

**Architecture:** Do not change strategy logic. Build a research runner that slices an existing multi-month Binance Futures dataset into rolling 30D windows stepped by 7 days, invokes the existing offline backtest code path with frozen V5/V6/V7 controls, and writes per-window summaries plus aggregate statistics. If the available dataset is shorter than the requested rolling horizon, the runner must fail cleanly with a coverage report instead of inventing results.

**Tech Stack:** Python, pytest, existing AI300 offline backtest runner, CSV OHLCV data, Markdown reports.

---

## Success Criteria

- V8 plan is saved under `docs/superpowers/plans/`.
- A new rolling runner can inspect data coverage from a dataset manifest and report available days.
- The runner rejects insufficient coverage for a 12-month rolling test with a clear error/report.
- The runner can run at least one 30D window when coverage is sufficient.
- Aggregate output includes median return, IQR return, worst return, best return, median win rate, worst win rate, median/max drawdown, median Sharpe, negative-window count, and consecutive-negative-window count.
- Latest available local data is checked; if only `latest_30d` exists, report that rolling robustness is blocked by insufficient data.
- A V8 report is created under `docs/superpowers/reports/`.
- `src/api/binance_client.py` remains untouched.

## Research Hypothesis

- **Hypothesis:** V6 dynamic 3x-5x may look strong in the latest 30D window but could be regime-sensitive. Rolling windows are required before any deployment or further leverage tuning.
- **Expected regime:** Some windows should underperform; the strategy is credible only if median performance remains positive and drawdowns stay bounded.
- **Failure mode:** The current local dataset has only one 30D window, so robustness validation cannot yet prove stability. The correct output is a blocked coverage report and a reproducible command to download longer history.
- **Verification command:** Run the V8 rolling runner against `data/raw/binance_futures/latest_30d` and confirm it reports insufficient coverage for a 12-month rolling test.

## File Structure

- Create: `scripts/run_rolling_backtest.py`  
  Rolling-window dataset coverage, slicing, execution, and aggregate summary.
- Create: `tests/test_rolling_backtest.py`  
  Unit tests for window generation, coverage checks, and aggregate metrics.
- Create: `docs/superpowers/reports/2026-06-19-v8-rolling-window-robustness-report.md`  
  Report local coverage and next required data command.

## Frozen Candidate Commands

Primary candidate:

```text
V6 dynamic 3x-5x:
configs/entry_chain.dry_run_v5_symbol_bucket_long_context.json
--enable-leverage-simulation --min-leverage 3 --max-leverage 5
```

Secondary candidate:

```text
V7 time reduce:
same as V6 dynamic plus --time-reduce-enabled
```

Full lifecycle controls:

```text
--exit-model atr_tp
--atr-stop-mult 1.5
--tp-levels 1,2,3
--tp-fractions 0.4,0.35,0.25
--max-hold-bars 32
--default-atr-pct 0.010
--simulated-hold-bars 2
--cooldown-bars 8
```

## Task 1: Rolling Window Utility Functions

**Files:**
- Create: `scripts/run_rolling_backtest.py`
- Create: `tests/test_rolling_backtest.py`

- [ ] **Step 1: Add window-generation tests**

Create `tests/test_rolling_backtest.py` with:

```python
from scripts.run_rolling_backtest import coverage_days, generate_windows, max_consecutive_negative, summarize_windows


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
```

- [ ] **Step 2: Implement utility functions**

In `scripts/run_rolling_backtest.py`, implement:

```python
SECONDS_PER_DAY = 86400

def coverage_days(start_ts: int, end_ts: int) -> float:
    return max(0, end_ts - start_ts) / SECONDS_PER_DAY

def generate_windows(start_ts: int, end_ts: int, *, window_days: int, step_days: int) -> list[tuple[int, int]]:
    ...

def max_consecutive_negative(values: list[float]) -> int:
    ...

def summarize_windows(rows: list[dict[str, float]]) -> dict[str, float | int | None]:
    ...
```

Use `statistics.median` and a simple percentile helper for IQR.

- [ ] **Step 3: Verify Task 1**

Run:

```powershell
pytest tests/test_rolling_backtest.py -q
```

Expected: tests pass.

## Task 2: Dataset Coverage And Rolling Runner CLI

**Files:**
- Modify: `scripts/run_rolling_backtest.py`
- Modify: `tests/test_rolling_backtest.py`

- [ ] **Step 1: Add coverage validation test**

Add:

```python
from scripts.run_rolling_backtest import validate_coverage


def test_validate_coverage_rejects_short_dataset():
    result = validate_coverage(available_days=30, required_days=365)

    assert result["ok"] is False
    assert result["available_days"] == 30
    assert result["required_days"] == 365
```

- [ ] **Step 2: Implement manifest loading**

Add:

```python
def load_manifest(data_dir: Path) -> dict[str, object]:
    return json.loads((data_dir / "manifest.json").read_text(encoding="utf-8"))

def manifest_coverage_seconds(manifest: Mapping[str, object]) -> tuple[int, int]:
    ...
```

Use `start_time_ms` and `end_time_ms`.

- [ ] **Step 3: Implement coverage validation**

Add:

```python
def validate_coverage(*, available_days: float, required_days: int) -> dict[str, object]:
    return {
        "ok": available_days >= required_days,
        "available_days": round(available_days, 2),
        "required_days": required_days,
    }
```

- [ ] **Step 4: Add CLI**

CLI arguments:

```text
--data-dir
--output-dir
--run-id
--window-days
--step-days
--required-days
--candidate {v6_dynamic,v7_time_reduce}
--allow-short-coverage
```

If coverage is short and `--allow-short-coverage` is not set, write `rolling_summary.json` with status `insufficient_coverage` and exit code `2`.

- [ ] **Step 5: Verify Task 2**

Run:

```powershell
python scripts/run_rolling_backtest.py --data-dir data/raw/binance_futures/latest_30d --run-id v8_coverage_check
```

Expected: exits with code `2` and writes a summary showing insufficient coverage.

## Task 3: Window Execution

**Files:**
- Modify: `scripts/run_rolling_backtest.py`

- [ ] **Step 1: Implement data slicing**

Implement:

```python
def filter_bars_by_window(bars: list[BacktestBar], start_ts: int, end_ts: int) -> list[BacktestBar]:
    return [bar for bar in bars if start_ts <= bar.timestamp <= end_ts]
```

- [ ] **Step 2: Reuse offline strategy builder**

Import from `scripts.run_offline_backtest.py`:

```python
load_bars
load_multi_timeframe_bars
build_entry_chain_strategy
```

Build `BacktestRequest` with the same V6/V7 candidate risk constraints.

- [ ] **Step 3: Run each window**

For each `(start_ts, end_ts)`:

- filter all symbol bars,
- skip if any symbol lacks enough 15m bars,
- run `run_backtest()`,
- collect headline metrics,
- write each window result under `reports/backtests/<run_id>/<window_id>/backtest_result.json`.

- [ ] **Step 4: Write aggregate artifacts**

Write:

- `rolling_windows.csv`
- `rolling_summary.json`
- `rolling_summary.md`

Fields:

```text
window_id,start_ts,end_ts,total_return,win_rate,max_drawdown,profit_factor,sharpe,sortino,expectancy,trade_count,margin_call_proxy_count
```

- [ ] **Step 5: Verify short coverage smoke test**

Run:

```powershell
python scripts/run_rolling_backtest.py --data-dir data/raw/binance_futures/latest_30d --run-id v8_short_smoke --allow-short-coverage --required-days 30 --window-days 30 --step-days 7 --candidate v6_dynamic
```

Expected: at least one window completes.

## Task 4: V8 Report

**Files:**
- Create: `docs/superpowers/reports/2026-06-19-v8-rolling-window-robustness-report.md`

- [ ] **Step 1: Document local coverage**

State that local data currently covers only about 30 days and is insufficient for 9-12 month robustness validation.

- [ ] **Step 2: Include smoke result if available**

If `v8_short_smoke` ran, include its one-window result and explicitly state it is not a robustness result.

- [ ] **Step 3: Provide exact next command**

Include:

```powershell
python scripts/download_latest_30d_market_data.py --days 365 --output-dir data/raw/binance_futures/latest_365d
python scripts/run_rolling_backtest.py --data-dir data/raw/binance_futures/latest_365d --run-id v8_v6_dynamic_12m --candidate v6_dynamic --required-days 365 --window-days 30 --step-days 7
python scripts/run_rolling_backtest.py --data-dir data/raw/binance_futures/latest_365d --run-id v8_v7_time_reduce_12m --candidate v7_time_reduce --required-days 365 --window-days 30 --step-days 7
```

- [ ] **Step 4: State decision**

Do not promote V7 or deploy. Mark V6 dynamic as latest single-window baseline and rolling validation as blocked pending data.

## Task 5: Final Verification

**Files:**
- No intended changes to `src/api/binance_client.py`.

- [ ] **Step 1: Run verification**

```powershell
python -m compileall scripts tests
pytest tests/test_rolling_backtest.py tests/test_lifecycle_exit.py tests/test_backtest_engine.py -q
git diff -- src/api/binance_client.py
```

Expected: compile succeeds, tests pass, and Binance client diff is empty.

- [ ] **Step 2: Final response**

Report whether rolling validation completed or was blocked by coverage, paths to plan/report, and exact next data command.
