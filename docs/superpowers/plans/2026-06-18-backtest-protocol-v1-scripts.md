# Backtest Protocol V1 Scripts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the remaining scripts required by the standalone `docs/08_backtest_protocol.md`.

**Architecture:** Extend the existing `src/backtest/protocol.py` module instead of creating a second protocol layer. Keep the code as deterministic validation helpers and documented constants for data integrity, multi-timeframe alignment, state logs, stratified analysis, walk-forward windows, and required backtest artifacts; do not implement a full historical matching engine in this slice.

**Tech Stack:** Python standard library, dataclasses, pytest.

---

## Scope Notes

The previous 07/08 pass already added base protocol checks for fixed processing order, candle continuity, costs, position model usage, required trade fields, and required performance fields. The standalone `docs/08_backtest_protocol.md` makes several additional requirements explicit:

- UTC multi-timeframe alignment with completed higher-timeframe bars only.
- Data integrity checks beyond continuity: duplicate bar, zero volume, OHLC shape, long wick, extreme gap, price precision.
- State transition log fields.
- Stratified analysis dimensions.
- Walk-forward train/validation window structure.
- Required output artifacts for every backtest run.

This plan implements those as validation utilities and JSON describe output. It does not implement real Binance downloads, strategy optimization, parameter fitting, equity-curve plotting, or a complete event-driven backtest engine.

## File Structure

- Modify: `src/backtest/protocol.py` - add standalone 08 constants and validators for data quality, timeframe alignment, state logs, stratified dimensions, walk-forward windows, and output artifacts.
- Modify: `scripts/describe_backtest_protocol.py` - include the new standalone 08 protocol lists in JSON output.
- Modify: `tests/test_backtest_protocol.py` - add tests for the new validators while keeping existing tests passing.
- Modify: `tests/test_describe_backtest_protocol.py` - assert the new JSON fields are exposed.
- Modify: `scripts/scaffold_ai300_framework.py` - sync templates for the changed module, script, and tests.
- Preserve: `src/api/binance_client.py` - do not modify the stable Binance client.

---

### Task 1: Data Quality Checks

**Files:**

- Modify: `src/backtest/protocol.py`
- Modify: `tests/test_backtest_protocol.py`

- [ ] **Step 1: Add failing tests for data quality checks**

Append to `tests/test_backtest_protocol.py`:

```python
from src.backtest.protocol import DATA_QUALITY_CHECKS, validate_data_quality


def test_data_quality_check_names_cover_doc_requirements():
    assert DATA_QUALITY_CHECKS == [
        "time_continuity",
        "missing_bar",
        "long_wick",
        "extreme_gap",
        "price_precision",
        "zero_volume",
        "duplicate_timestamp",
    ]


def test_validate_data_quality_detects_long_wick_gap_precision_and_zero_volume():
    candles = [
        candle(0, 900, volume=10),
        Candle(
            symbol="BTCUSDT",
            timeframe="15m",
            open_time=900,
            close_time=1800,
            open=101.123456789,
            high=160,
            low=100,
            close=102,
            volume=0,
        ),
    ]
    results = validate_data_quality(
        candles,
        timeframe_seconds=900,
        max_wick_ratio=0.50,
        max_gap_pct=0.20,
        max_price_decimals=4,
    )
    failed = [result.reason for result in results if not result.passed]
    assert any("long wick" in reason for reason in failed)
    assert any("extreme gap" in reason for reason in failed)
    assert any("price precision" in reason for reason in failed)
    assert any("zero volume" in reason for reason in failed)
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_backtest_protocol.py -q`

Expected: FAIL because `DATA_QUALITY_CHECKS` and `validate_data_quality` are missing.

- [ ] **Step 3: Implement data quality constants and validator**

Add to `src/backtest/protocol.py`:

```python
DATA_QUALITY_CHECKS = [
    "time_continuity",
    "missing_bar",
    "long_wick",
    "extreme_gap",
    "price_precision",
    "zero_volume",
    "duplicate_timestamp",
]


def validate_data_quality(
    candles: list[Candle],
    timeframe_seconds: int,
    max_wick_ratio: float = 0.80,
    max_gap_pct: float = 0.20,
    max_price_decimals: int = 8,
) -> list[ProtocolCheck]:
    results = validate_candle_continuity(candles, timeframe_seconds)
    sorted_candles = sorted(candles, key=lambda item: item.open_time)
    previous_close = None
    for item in sorted_candles:
        body = abs(item.close - item.open)
        candle_range = item.high - item.low
        if candle_range <= 0:
            results.append(ProtocolCheck("ohlc_integrity", False, f"invalid range at {item.open_time}"))
        elif body > 0:
            upper_wick = item.high - max(item.open, item.close)
            lower_wick = min(item.open, item.close) - item.low
            if max(upper_wick, lower_wick) / candle_range > max_wick_ratio:
                results.append(ProtocolCheck("long_wick", False, f"long wick at {item.open_time}"))
        if previous_close is not None and previous_close > 0:
            gap_pct = abs(item.open - previous_close) / previous_close
            if gap_pct > max_gap_pct:
                results.append(ProtocolCheck("extreme_gap", False, f"extreme gap at {item.open_time}"))
        for field_name in ("open", "high", "low", "close"):
            if _decimal_places(getattr(item, field_name)) > max_price_decimals:
                results.append(ProtocolCheck("price_precision", False, f"price precision too high at {item.open_time}"))
                break
        previous_close = item.close
    if all(result.passed for result in results):
        return [ProtocolCheck("data_quality", True, "data quality approved")]
    return results


def _decimal_places(value: float) -> int:
    text = f"{value:.12f}".rstrip("0").rstrip(".")
    if "." not in text:
        return 0
    return len(text.split(".", 1)[1])
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_backtest_protocol.py -q`

Expected: PASS.

---

### Task 2: Multi-Timeframe Alignment and State Logs

**Files:**

- Modify: `src/backtest/protocol.py`
- Modify: `tests/test_backtest_protocol.py`

- [ ] **Step 1: Add failing tests for timeframe alignment and state transition fields**

Append to `tests/test_backtest_protocol.py`:

```python
from src.backtest.protocol import REQUIRED_STATE_TRANSITION_FIELDS, validate_state_transition_fields, validate_timeframe_alignment


def test_validate_timeframe_alignment_requires_completed_higher_timeframe_bar():
    result = validate_timeframe_alignment(
        base_close_time=3_600,
        higher_close_time=3_600,
        higher_timeframe_seconds=3_600,
    )
    assert result.passed is True
    leaking = validate_timeframe_alignment(
        base_close_time=3_600,
        higher_close_time=7_200,
        higher_timeframe_seconds=3_600,
    )
    assert leaking.passed is False
    assert "future" in leaking.reason


def test_required_state_transition_fields_match_doc():
    assert REQUIRED_STATE_TRANSITION_FIELDS == [
        "current_state",
        "target_state",
        "reason",
        "transition_time",
        "transition_price",
        "timeframe",
    ]
    ok = validate_state_transition_fields(set(REQUIRED_STATE_TRANSITION_FIELDS))
    assert ok.passed is True
    missing = validate_state_transition_fields({"current_state"})
    assert missing.passed is False
    assert "target_state" in missing.reason
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_backtest_protocol.py -q`

Expected: FAIL because the new constants and validators are missing.

- [ ] **Step 3: Implement timeframe and state validators**

Add to `src/backtest/protocol.py`:

```python
REQUIRED_STATE_TRANSITION_FIELDS = [
    "current_state",
    "target_state",
    "reason",
    "transition_time",
    "transition_price",
    "timeframe",
]


def validate_timeframe_alignment(
    base_close_time: int,
    higher_close_time: int,
    higher_timeframe_seconds: int,
) -> ProtocolCheck:
    if higher_timeframe_seconds <= 0:
        raise ValueError("higher_timeframe_seconds must be positive")
    if higher_close_time > base_close_time:
        return ProtocolCheck("timeframe_alignment", False, "future higher timeframe bar is not allowed")
    if higher_close_time % higher_timeframe_seconds != 0:
        return ProtocolCheck("timeframe_alignment", False, "higher timeframe close is misaligned")
    return ProtocolCheck("timeframe_alignment", True, "higher timeframe uses completed UTC-aligned bar")


def validate_state_transition_fields(fields: set[str]) -> ProtocolCheck:
    missing = sorted(set(REQUIRED_STATE_TRANSITION_FIELDS) - fields)
    if missing:
        return ProtocolCheck("state_transition_fields", False, f"missing state transition fields: {missing}")
    return ProtocolCheck("state_transition_fields", True, "state transition fields complete")
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_backtest_protocol.py -q`

Expected: PASS.

---

### Task 3: Stratified Analysis, Walk-Forward, and Output Artifacts

**Files:**

- Modify: `src/backtest/protocol.py`
- Modify: `tests/test_backtest_protocol.py`

- [ ] **Step 1: Add failing tests for analysis dimensions, walk-forward windows, and output artifacts**

Append to `tests/test_backtest_protocol.py`:

```python
from src.backtest.protocol import (
    REQUIRED_OUTPUT_ARTIFACTS,
    STRATIFIED_ANALYSIS_DIMENSIONS,
    WalkForwardWindow,
    generate_walk_forward_windows,
    validate_output_artifacts,
    validate_stratified_analysis_dimensions,
)


def test_stratified_analysis_dimensions_cover_doc_requirements():
    assert STRATIFIED_ANALYSIS_DIMENSIONS == [
        "symbol",
        "timeframe",
        "market_regime",
        "side",
        "signal_type",
        "single_vs_portfolio",
        "volatility_regime",
    ]
    assert validate_stratified_analysis_dimensions(set(STRATIFIED_ANALYSIS_DIMENSIONS)).passed is True


def test_required_output_artifacts_cover_doc_requirements():
    assert REQUIRED_OUTPUT_ARTIFACTS == [
        "equity_curve",
        "trade_detail",
        "performance_summary",
        "drawdown_summary",
        "state_machine_stats",
        "rejection_stats",
        "failure_samples",
        "strategy_version",
        "parameter_snapshot",
    ]
    assert validate_output_artifacts(set(REQUIRED_OUTPUT_ARTIFACTS)).passed is True


def test_generate_walk_forward_windows_rolls_train_and_validation_ranges():
    windows = generate_walk_forward_windows(start_ts=0, end_ts=10_000, train_seconds=4_000, validation_seconds=2_000, step_seconds=2_000)
    assert windows == [
        WalkForwardWindow(train_start=0, train_end=4_000, validation_start=4_000, validation_end=6_000),
        WalkForwardWindow(train_start=2_000, train_end=6_000, validation_start=6_000, validation_end=8_000),
        WalkForwardWindow(train_start=4_000, train_end=8_000, validation_start=8_000, validation_end=10_000),
    ]
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_backtest_protocol.py -q`

Expected: FAIL because the analysis, artifact, and walk-forward helpers are missing.

- [ ] **Step 3: Implement analysis, artifact, and walk-forward helpers**

Add to `src/backtest/protocol.py`:

```python
STRATIFIED_ANALYSIS_DIMENSIONS = [
    "symbol",
    "timeframe",
    "market_regime",
    "side",
    "signal_type",
    "single_vs_portfolio",
    "volatility_regime",
]

REQUIRED_OUTPUT_ARTIFACTS = [
    "equity_curve",
    "trade_detail",
    "performance_summary",
    "drawdown_summary",
    "state_machine_stats",
    "rejection_stats",
    "failure_samples",
    "strategy_version",
    "parameter_snapshot",
]


@dataclass(frozen=True)
class WalkForwardWindow:
    train_start: int
    train_end: int
    validation_start: int
    validation_end: int


def validate_stratified_analysis_dimensions(dimensions: set[str]) -> ProtocolCheck:
    missing = sorted(set(STRATIFIED_ANALYSIS_DIMENSIONS) - dimensions)
    if missing:
        return ProtocolCheck("stratified_analysis", False, f"missing analysis dimensions: {missing}")
    return ProtocolCheck("stratified_analysis", True, "stratified analysis dimensions complete")


def validate_output_artifacts(artifacts: set[str]) -> ProtocolCheck:
    missing = sorted(set(REQUIRED_OUTPUT_ARTIFACTS) - artifacts)
    if missing:
        return ProtocolCheck("output_artifacts", False, f"missing output artifacts: {missing}")
    return ProtocolCheck("output_artifacts", True, "output artifacts complete")


def generate_walk_forward_windows(
    start_ts: int,
    end_ts: int,
    train_seconds: int,
    validation_seconds: int,
    step_seconds: int,
) -> list[WalkForwardWindow]:
    if end_ts <= start_ts:
        raise ValueError("end_ts must be greater than start_ts")
    if min(train_seconds, validation_seconds, step_seconds) <= 0:
        raise ValueError("window sizes must be positive")
    windows = []
    cursor = start_ts
    while cursor + train_seconds + validation_seconds <= end_ts:
        train_start = cursor
        train_end = cursor + train_seconds
        validation_start = train_end
        validation_end = validation_start + validation_seconds
        windows.append(WalkForwardWindow(train_start, train_end, validation_start, validation_end))
        cursor += step_seconds
    return windows
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_backtest_protocol.py -q`

Expected: PASS.

---

### Task 4: Describe Script and Scaffold Sync

**Files:**

- Modify: `scripts/describe_backtest_protocol.py`
- Modify: `tests/test_describe_backtest_protocol.py`
- Modify: `scripts/scaffold_ai300_framework.py`

- [ ] **Step 1: Add failing describe-script assertions**

Append to `tests/test_describe_backtest_protocol.py`:

```python
def test_describe_backtest_protocol_exposes_standalone_08_requirements():
    completed = subprocess.run(
        [sys.executable, "scripts/describe_backtest_protocol.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["data_quality_checks"][0] == "time_continuity"
    assert payload["required_state_transition_fields"][0] == "current_state"
    assert "walk_forward" in payload["validation_features"]
    assert "equity_curve" in payload["required_output_artifacts"]
    assert "volatility_regime" in payload["stratified_analysis_dimensions"]
```

- [ ] **Step 2: Run test to verify failure**

Run: `pytest tests/test_describe_backtest_protocol.py -q`

Expected: FAIL because the script does not expose the new fields.

- [ ] **Step 3: Update describe script imports and payload**

Modify `scripts/describe_backtest_protocol.py`:

```python
from src.backtest.protocol import (
    BACKTEST_PROCESSING_ORDER,
    DATA_QUALITY_CHECKS,
    REQUIRED_OUTPUT_ARTIFACTS,
    REQUIRED_PERFORMANCE_FIELDS,
    REQUIRED_STATE_TRANSITION_FIELDS,
    REQUIRED_TRADE_FIELDS,
    STRATIFIED_ANALYSIS_DIMENSIONS,
)
```

Add to payload:

```python
"data_quality_checks": DATA_QUALITY_CHECKS,
"required_state_transition_fields": REQUIRED_STATE_TRANSITION_FIELDS,
"stratified_analysis_dimensions": STRATIFIED_ANALYSIS_DIMENSIONS,
"required_output_artifacts": REQUIRED_OUTPUT_ARTIFACTS,
"validation_features": [
    "data_quality",
    "timeframe_alignment",
    "state_transition_logs",
    "walk_forward",
    "output_artifacts",
],
```

- [ ] **Step 4: Sync scaffold templates**

Copy final contents of these files into `scripts/scaffold_ai300_framework.py`:

- `src/backtest/protocol.py`
- `scripts/describe_backtest_protocol.py`
- `tests/test_backtest_protocol.py`
- `tests/test_describe_backtest_protocol.py`

- [ ] **Step 5: Run targeted tests**

Run: `pytest tests/test_backtest_protocol.py tests/test_describe_backtest_protocol.py tests/test_framework_scaffold.py -q`

Expected: PASS.

- [ ] **Step 6: Run full verification**

Run:

```bash
pytest -q
python -m compileall src scripts tests
python scripts/describe_backtest_protocol.py
git diff -- src/api/binance_client.py
```

Expected: all tests pass, compile succeeds, describe JSON includes standalone 08 fields, and Binance diff has no output.

---

## Self-Review

- Spec coverage: covers data requirements, integrity checks, completed-bar and UTC alignment, fixed strategy order, costs, position model, exit model by existing 07/08 helpers, state transition logs, trade logs, performance fields, stratified analysis, walk-forward windows, forbidden shortcuts, and output artifacts.
- Placeholder scan: no `TBD`, `TODO`, `implement later`, or unspecified test steps.
- Type consistency: `ProtocolCheck`, `WalkForwardWindow`, `DATA_QUALITY_CHECKS`, `REQUIRED_STATE_TRANSITION_FIELDS`, `STRATIFIED_ANALYSIS_DIMENSIONS`, and `REQUIRED_OUTPUT_ARTIFACTS` are used consistently across tasks.
