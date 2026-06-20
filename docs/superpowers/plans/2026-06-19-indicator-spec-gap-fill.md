# Indicator Spec Gap Fill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the refreshed `docs/03_indicator_spec.md` into a clean, testable indicator-layer contract with standardized `IndicatorResult` output.

**Architecture:** Keep existing raw indicator math functions intact and add contract helpers around them. Reuse `src.data.data_contract.MarketCandle`, `IndicatorResult`, `QUALITY_FLAGS`, and `INDICATOR_REQUIRED_OUTPUTS` instead of creating duplicate types. Preserve the legacy `compute_indicator_snapshot()` compatibility path while adding a stricter `compute_indicator_results()` path for the refreshed 03 contract.

**Tech Stack:** Python dataclasses, pure functions, existing indicator modules, `src.data.data_contract`, pytest, JSON describe scripts, scaffold template synchronization.

---

## Preflight

The current working tree already has unrelated uncommitted 02 Market Universe changes. Before executing this plan, keep those changes separate from the 03 work. Do not modify or revert unrelated 02 files unless the user explicitly asks.

Protected file:

- `src/api/binance_client.py` must not be modified.

Run before starting implementation:

```powershell
git status --short
git diff -- src\api\binance_client.py
```

Expected:

- Existing 02 changes may appear.
- `git diff -- src\api\binance_client.py` prints no output.

---

## File Structure

Modify:

- `docs/03_indicator_spec.md`  
  Clean wrapper text and keep only the canonical indicator specification.

- `src/indicators/indicator_spec.py`  
  Add V1 indicator names, input/output contract constants, quality rules, timeframe map, conflict priority, forbidden usage validation, and result-contract helpers.

- `src/indicators/indicator_engine.py`  
  Keep `compute_indicator_snapshot()` and add standardized `compute_indicator_results()` using existing math functions and `IndicatorResult`.

- `tests/test_indicator_spec_rules.py`  
  Replace old priority expectations and add tests for refreshed 03 constants and helpers.

- `tests/test_indicator_engine.py`  
  Keep snapshot compatibility tests and add standardized result tests.

- `scripts/describe_indicator_rules.py`  
  Export the refreshed 03 contract as JSON.

- `tests/test_describe_indicator_rules.py`  
  Assert the describe output includes the expanded contract.

- `scripts/scaffold_ai300_framework.py`  
  Sync indicator-related templates.

- `tests/test_framework_scaffold.py`  
  Assert scaffold templates include the refreshed 03 contract.

Do not modify:

- `src/api/binance_client.py`
- live execution modules
- risk sizing modules
- backtest fill-model modules

---

## Shared Contract Decisions

Use these indicator constants:

```python
INDICATOR_NAMES = ("MACD", "CCI", "BOLL", "RSI", "CVD", "ATR")
INDICATOR_INPUT_FIELDS = (
    "symbol",
    "timeframe",
    "open_time",
    "close_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "quote_volume",
    "trade_count",
    "taker_buy_base_volume",
    "taker_buy_quote_volume",
    "is_closed",
    "quality_flag",
)
INDICATOR_OUTPUT_FIELDS = (
    "name",
    "symbol",
    "timeframe",
    "timestamp",
    "value",
    "signal",
    "trend",
    "strength",
    "quality_flag",
    "metadata",
)
INDICATOR_CONFLICT_PRIORITY = (
    "data_quality",
    "cvd_divergence",
    "macd_trend_direction",
    "cci_strength",
    "boll_structure",
    "rsi_timing",
    "atr_risk",
)
TIMEFRAME_INDICATOR_MAP = {
    "4h": ("MACD", "BOLL", "CCI"),
    "1h": ("MACD", "CCI", "CVD", "RSI"),
    "30m": ("MACD", "BOLL", "CCI", "CVD"),
    "15m": ("RSI", "MACD", "CVD", "BOLL"),
}
INDICATOR_CACHE_FIELDS = ("version", "timestamp", "timeframe", "indicator", "quality_flag")
```

Use these forbidden usage rules:

```python
INDICATOR_FORBIDDEN_USAGES = {
    "MACD": ("sole_entry", "position_size", "unfinished_bar_final", "execution_reinterpretation"),
    "CCI": ("sole_direction", "risk_control", "only_trend_proof"),
    "BOLL": ("sole_direction", "position_size", "replace_trend_logic"),
    "RSI": ("replace_trend", "replace_fund_flow", "guaranteed_reversal"),
    "CVD": ("sole_direction", "replace_price_structure", "force_signal_without_data", "execution_priority"),
    "ATR": ("direction", "long_short_signal", "replace_trend", "non_risk_module_mixing"),
}
GLOBAL_FORBIDDEN_INDICATOR_ACTIONS = (
    "create_order",
    "final_position_size",
    "bypass_state_machine",
    "must_trade",
)
```

Use `IndicatorSpecCheck` for local indicator-spec validation:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class IndicatorSpecCheck:
    passed: bool
    reason: str
```

---

### Task 1: Clean Indicator Markdown

**Files:**

- Modify: `docs/03_indicator_spec.md`

- [ ] **Step 1: Inspect current wrapper**

Run:

```powershell
Get-Content docs\03_indicator_spec.md -TotalCount 12
Select-String -Path docs\03_indicator_spec.md -Pattern "下面是重新整理后的|````md|```$" -Context 1,1
```

Expected: output shows ChatGPT wrapper text and an outer markdown fence.

- [ ] **Step 2: Clean the document**

Edit `docs/03_indicator_spec.md` so:

- Line 1 is exactly `# Indicator Specification`.
- The outer ````md wrapper is removed.
- The ChatGPT wrapper sentence is removed.
- Inner code fences remain valid markdown.
- The document still contains sections `# 1. 目的` through `# 25. 结论`.

- [ ] **Step 3: Verify cleaned document**

Run:

```powershell
$first = Get-Content docs\03_indicator_spec.md -TotalCount 1
if ($first -ne "# Indicator Specification") { throw "unexpected first line: $first" }
$wrapper = Select-String -Path docs\03_indicator_spec.md -Pattern "下面是重新整理后的|````md" -Quiet
if ($wrapper) { throw "wrapper text still present" }
Select-String -Path docs\03_indicator_spec.md -Pattern "# 25. 结论" -Quiet
```

Expected: no exception and final command prints `True`.

- [ ] **Step 4: Commit**

```powershell
git add docs\03_indicator_spec.md
git commit -m "docs: clean indicator specification"
```

Expected: commit succeeds if the user has approved committing this execution branch. If commits are not desired in the current session, skip the commit and keep the file staged or unstaged according to the session policy.

---

### Task 2: Expand Indicator Spec Contract

**Files:**

- Modify: `src/indicators/indicator_spec.py`
- Modify: `tests/test_indicator_spec_rules.py`

- [ ] **Step 1: Replace indicator spec tests with refreshed contract tests**

Replace `tests/test_indicator_spec_rules.py` with:

```python
from src.data.data_contract import INDICATOR_REQUIRED_OUTPUTS
from src.indicators.indicator_spec import (
    DEFAULT_INDICATOR_PARAMS,
    GLOBAL_FORBIDDEN_INDICATOR_ACTIONS,
    INDICATOR_CACHE_FIELDS,
    INDICATOR_CONFLICT_PRIORITY,
    INDICATOR_FORBIDDEN_USAGES,
    INDICATOR_INPUT_FIELDS,
    INDICATOR_NAMES,
    INDICATOR_OUTPUT_FIELDS,
    INDICATOR_RESPONSIBILITIES,
    TIMEFRAME_INDICATOR_MAP,
    classify_cci,
    classify_rsi,
    quality_allows_signal_use,
    required_outputs_for,
    validate_indicator_input_contract,
    validate_indicator_usage,
)


def test_default_indicator_params_match_doc():
    assert DEFAULT_INDICATOR_PARAMS["MACD"] == {"fast": 12, "slow": 26, "signal": 9}
    assert DEFAULT_INDICATOR_PARAMS["CCI"] == {"period": 20}
    assert DEFAULT_INDICATOR_PARAMS["BOLL"] == {"period": 20, "std": 2.0}
    assert DEFAULT_INDICATOR_PARAMS["RSI"] == {"period": 14}
    assert DEFAULT_INDICATOR_PARAMS["ATR"] == {"period": 14}
    assert DEFAULT_INDICATOR_PARAMS["CVD"] == {}


def test_indicator_names_responsibilities_and_contract_fields_match_doc():
    assert INDICATOR_NAMES == ("MACD", "CCI", "BOLL", "RSI", "CVD", "ATR")
    assert INDICATOR_RESPONSIBILITIES == {
        "MACD": "trend_momentum",
        "CCI": "strength_deviation_recovery",
        "BOLL": "volatility_structure",
        "RSI": "pullback_quality_overheat",
        "CVD": "active_buy_sell_pressure",
        "ATR": "volatility_stop_position_risk",
    }
    assert "is_closed" in INDICATOR_INPUT_FIELDS
    assert "quality_flag" in INDICATOR_INPUT_FIELDS
    assert INDICATOR_OUTPUT_FIELDS == (
        "name",
        "symbol",
        "timeframe",
        "timestamp",
        "value",
        "signal",
        "trend",
        "strength",
        "quality_flag",
        "metadata",
    )


def test_required_outputs_are_reused_from_data_contract():
    assert required_outputs_for("MACD") == tuple(INDICATOR_REQUIRED_OUTPUTS["MACD"])
    assert required_outputs_for("CVD") == tuple(INDICATOR_REQUIRED_OUTPUTS["CVD"])
    assert required_outputs_for("ATR") == tuple(INDICATOR_REQUIRED_OUTPUTS["ATR"])


def test_conflict_priority_and_timeframe_map_match_doc():
    assert INDICATOR_CONFLICT_PRIORITY == (
        "data_quality",
        "cvd_divergence",
        "macd_trend_direction",
        "cci_strength",
        "boll_structure",
        "rsi_timing",
        "atr_risk",
    )
    assert TIMEFRAME_INDICATOR_MAP["4h"] == ("MACD", "BOLL", "CCI")
    assert TIMEFRAME_INDICATOR_MAP["1h"] == ("MACD", "CCI", "CVD", "RSI")
    assert TIMEFRAME_INDICATOR_MAP["30m"] == ("MACD", "BOLL", "CCI", "CVD")
    assert TIMEFRAME_INDICATOR_MAP["15m"] == ("RSI", "MACD", "CVD", "BOLL")


def test_forbidden_usage_rules_are_explicit():
    ok, reason = validate_indicator_usage("ATR", "direction")
    assert ok is False
    assert "forbidden" in reason
    ok, reason = validate_indicator_usage("MACD", "sole_entry")
    assert ok is False
    assert "forbidden" in reason
    ok, reason = validate_indicator_usage("RSI", "timing")
    assert ok is True
    assert reason == "RSI allowed for timing"
    assert "must_trade" in GLOBAL_FORBIDDEN_INDICATOR_ACTIONS
    assert "sole_direction" in INDICATOR_FORBIDDEN_USAGES["CVD"]


def test_quality_signal_semantics_are_conservative():
    assert quality_allows_signal_use(True) is True
    assert quality_allows_signal_use("degraded") is True
    assert quality_allows_signal_use(False) is False
    assert quality_allows_signal_use("stale") is False


def test_validate_indicator_input_contract_requires_closed_quality_fields():
    required = {field: 1 for field in INDICATOR_INPUT_FIELDS}
    required["is_closed"] = True
    required["quality_flag"] = True
    assert validate_indicator_input_contract(required).passed is True

    missing_closed = dict(required)
    missing_closed.pop("is_closed")
    assert validate_indicator_input_contract(missing_closed).passed is False

    unfinished = dict(required)
    unfinished["is_closed"] = False
    assert validate_indicator_input_contract(unfinished).passed is False

    stale = dict(required)
    stale["quality_flag"] = "stale"
    assert validate_indicator_input_contract(stale).passed is False


def test_rsi_and_cci_classification():
    assert classify_rsi(75) == "overheated"
    assert classify_rsi(25) == "oversold"
    assert classify_rsi(50) == "range"
    assert classify_cci(120) == "strong"
    assert classify_cci(-120) == "weak"
    assert classify_cci(0) == "neutral"


def test_cache_fields_match_doc():
    assert INDICATOR_CACHE_FIELDS == ("version", "timestamp", "timeframe", "indicator", "quality_flag")
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```powershell
pytest tests\test_indicator_spec_rules.py -q
```

Expected: FAIL because the refreshed constants and helpers do not exist.

- [ ] **Step 3: Implement the expanded spec module**

Replace `src/indicators/indicator_spec.py` with:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from src.data.data_contract import INDICATOR_REQUIRED_OUTPUTS, QUALITY_FLAGS


DEFAULT_INDICATOR_PARAMS = {
    "MACD": {"fast": 12, "slow": 26, "signal": 9},
    "CCI": {"period": 20},
    "BOLL": {"period": 20, "std": 2.0},
    "RSI": {"period": 14},
    "CVD": {},
    "ATR": {"period": 14},
}

INDICATOR_NAMES = ("MACD", "CCI", "BOLL", "RSI", "CVD", "ATR")
INDICATOR_RESPONSIBILITIES = {
    "MACD": "trend_momentum",
    "CCI": "strength_deviation_recovery",
    "BOLL": "volatility_structure",
    "RSI": "pullback_quality_overheat",
    "CVD": "active_buy_sell_pressure",
    "ATR": "volatility_stop_position_risk",
}
INDICATOR_INPUT_FIELDS = (
    "symbol",
    "timeframe",
    "open_time",
    "close_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "quote_volume",
    "trade_count",
    "taker_buy_base_volume",
    "taker_buy_quote_volume",
    "is_closed",
    "quality_flag",
)
INDICATOR_OUTPUT_FIELDS = (
    "name",
    "symbol",
    "timeframe",
    "timestamp",
    "value",
    "signal",
    "trend",
    "strength",
    "quality_flag",
    "metadata",
)
INDICATOR_CONFLICT_PRIORITY = (
    "data_quality",
    "cvd_divergence",
    "macd_trend_direction",
    "cci_strength",
    "boll_structure",
    "rsi_timing",
    "atr_risk",
)
INDICATOR_PRIORITY = INDICATOR_CONFLICT_PRIORITY
TIMEFRAME_INDICATOR_MAP = {
    "4h": ("MACD", "BOLL", "CCI"),
    "1h": ("MACD", "CCI", "CVD", "RSI"),
    "30m": ("MACD", "BOLL", "CCI", "CVD"),
    "15m": ("RSI", "MACD", "CVD", "BOLL"),
}
INDICATOR_CACHE_FIELDS = ("version", "timestamp", "timeframe", "indicator", "quality_flag")
INDICATOR_FORBIDDEN_USAGES = {
    "MACD": ("sole_entry", "position_size", "unfinished_bar_final", "execution_reinterpretation"),
    "CCI": ("sole_direction", "risk_control", "only_trend_proof"),
    "BOLL": ("sole_direction", "position_size", "replace_trend_logic"),
    "RSI": ("replace_trend", "replace_fund_flow", "guaranteed_reversal"),
    "CVD": ("sole_direction", "replace_price_structure", "force_signal_without_data", "execution_priority"),
    "ATR": ("direction", "long_short_signal", "replace_trend", "non_risk_module_mixing"),
}
GLOBAL_FORBIDDEN_INDICATOR_ACTIONS = (
    "create_order",
    "final_position_size",
    "bypass_state_machine",
    "must_trade",
)


@dataclass(frozen=True)
class IndicatorSpecCheck:
    passed: bool
    reason: str


def required_outputs_for(indicator: str) -> tuple[str, ...]:
    return tuple(INDICATOR_REQUIRED_OUTPUTS.get(indicator.upper(), ()))


def quality_allows_signal_use(quality_flag: bool | str) -> bool:
    return quality_flag in (True, "degraded")


def validate_indicator_input_contract(payload: Mapping[str, object]) -> IndicatorSpecCheck:
    missing = sorted(field for field in INDICATOR_INPUT_FIELDS if field not in payload)
    if missing:
        return IndicatorSpecCheck(False, f"missing indicator input fields: {missing}")
    if payload["is_closed"] is not True:
        return IndicatorSpecCheck(False, "indicator input candle must be closed")
    if payload["quality_flag"] not in QUALITY_FLAGS:
        return IndicatorSpecCheck(False, "unsupported quality_flag")
    if not quality_allows_signal_use(payload["quality_flag"]):
        return IndicatorSpecCheck(False, "quality_flag cannot drive indicator signal use")
    return IndicatorSpecCheck(True, "indicator input contract approved")


def validate_indicator_usage(indicator: str, usage: str) -> tuple[bool, str]:
    key = indicator.upper()
    if key not in INDICATOR_NAMES:
        return False, f"unknown indicator: {indicator}"
    normalized_usage = usage.strip().lower()
    if normalized_usage in GLOBAL_FORBIDDEN_INDICATOR_ACTIONS:
        return False, f"{normalized_usage} is globally forbidden for indicator layer"
    if normalized_usage in INDICATOR_FORBIDDEN_USAGES.get(key, ()):
        return False, f"{key} usage forbidden: {normalized_usage}"
    return True, f"{key} allowed for {normalized_usage}"


def classify_rsi(value: float) -> str:
    if value > 70:
        return "overheated"
    if value < 30:
        return "oversold"
    if 40 <= value <= 60:
        return "range"
    return "neutral"


def classify_cci(value: float) -> str:
    if value > 100:
        return "strong"
    if value < -100:
        return "weak"
    return "neutral"
```

- [ ] **Step 4: Run spec tests**

Run:

```powershell
pytest tests\test_indicator_spec_rules.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src\indicators\indicator_spec.py tests\test_indicator_spec_rules.py
git commit -m "feat: expand indicator specification contract"
```

Expected: commit succeeds if commits are enabled for this execution.

---

### Task 3: Add Standardized Indicator Results

**Files:**

- Modify: `src/indicators/indicator_engine.py`
- Modify: `tests/test_indicator_engine.py`

- [ ] **Step 1: Add failing standardized result tests**

Append to `tests/test_indicator_engine.py`:

```python
from src.data.data_contract import MarketCandle, validate_indicator_result
from src.indicators.indicator_engine import compute_indicator_results


def make_market_candles(count: int, *, is_closed: bool = True, quality_flag=True) -> list[MarketCandle]:
    candles = []
    for i in range(count):
        close = 100 + i
        candles.append(
            MarketCandle(
                symbol="BTCUSDT",
                timeframe="15m",
                open_time=i * 900,
                close_time=(i + 1) * 900,
                open=close - 0.5,
                high=close + 1,
                low=close - 1,
                close=close,
                volume=100,
                quote_volume=10_000,
                trade_count=100,
                taker_buy_base_volume=60,
                taker_buy_quote_volume=6_000,
                is_closed=is_closed,
                source="unit_test",
                quality_flag=quality_flag,
            )
        )
    return candles


def test_compute_indicator_results_returns_standard_contracts():
    results = compute_indicator_results(make_market_candles(40))
    by_name = {item.name: item for item in results}

    assert set(by_name) == {"MACD", "CCI", "BOLL", "RSI", "CVD", "ATR"}
    assert set(by_name["MACD"].value) >= {"macd_line", "signal_line", "histogram", "histogram_slope", "cross_state"}
    assert set(by_name["BOLL"].value) >= {
        "middle_band",
        "upper_band",
        "lower_band",
        "band_width",
        "band_expansion_flag",
        "band_contraction_flag",
        "price_position",
    }
    assert set(by_name["CVD"].value) >= {
        "cvd",
        "cvd_delta",
        "cvd_slope",
        "cvd_divergence_flag",
        "buy_pressure",
        "sell_pressure",
    }
    for result in results:
        assert validate_indicator_result(result).passed is True
        assert result.symbol == "BTCUSDT"
        assert result.timeframe == "15m"
        assert result.timestamp == 40 * 900


def test_compute_indicator_results_rejects_unclosed_market_candles():
    try:
        compute_indicator_results(make_market_candles(40, is_closed=False))
    except ValueError as exc:
        assert "closed" in str(exc)
    else:
        raise AssertionError("unfinished candles must be rejected")


def test_compute_indicator_results_marks_degraded_when_source_quality_degraded():
    results = compute_indicator_results(make_market_candles(40, quality_flag="degraded"))
    assert {item.quality_flag for item in results} == {"degraded"}


def test_compute_indicator_results_rejects_stale_quality():
    try:
        compute_indicator_results(make_market_candles(40, quality_flag="stale"))
    except ValueError as exc:
        assert "quality" in str(exc)
    else:
        raise AssertionError("stale candles must be rejected")
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```powershell
pytest tests\test_indicator_engine.py -q
```

Expected: FAIL because `compute_indicator_results()` does not exist.

- [ ] **Step 3: Implement standardized result helpers**

Add these imports to `src/indicators/indicator_engine.py`:

```python
from src.data.data_contract import IndicatorResult, MarketCandle, market_candle_to_candle
from src.indicators.indicator_spec import quality_allows_signal_use
```

Add these helpers below `compute_indicator_snapshot()`:

```python
def compute_indicator_results(candles: list[MarketCandle]) -> list[IndicatorResult]:
    if not candles:
        raise ValueError("candles must not be empty")
    _validate_market_candles_for_indicator_results(candles)
    core_candles = [market_candle_to_candle(item) for item in candles]
    snapshot = compute_indicator_snapshot(core_candles)
    closes = [item.close for item in core_candles]
    quality_flag = _combined_quality_flag(candles)

    return [
        _build_macd_result(snapshot, closes, quality_flag),
        _build_cci_result(snapshot, core_candles, quality_flag),
        _build_boll_result(snapshot, closes, quality_flag),
        _build_rsi_result(snapshot, closes, quality_flag),
        _build_cvd_result(snapshot, core_candles, quality_flag),
        _build_atr_result(snapshot, core_candles, quality_flag),
    ]


def _validate_market_candles_for_indicator_results(candles: list[MarketCandle]) -> None:
    first_symbol = candles[0].symbol
    first_timeframe = candles[0].timeframe
    previous_open_time = -1
    for candle in candles:
        if candle.symbol != first_symbol:
            raise ValueError("indicator candles must use one symbol")
        if candle.timeframe != first_timeframe:
            raise ValueError("indicator candles must use one timeframe")
        if candle.open_time <= previous_open_time:
            raise ValueError("indicator candles must be ordered by open_time")
        if candle.is_closed is not True:
            raise ValueError("indicator candles must be closed")
        if not quality_allows_signal_use(candle.quality_flag):
            raise ValueError("indicator candle quality cannot drive indicator signal use")
        previous_open_time = candle.open_time


def _combined_quality_flag(candles: list[MarketCandle]) -> bool | str:
    if any(item.quality_flag == "degraded" for item in candles):
        return "degraded"
    return True


def _base_result(snapshot: IndicatorSnapshot, name: str, value: dict, signal: str, trend: str, strength: float, quality_flag: bool | str) -> IndicatorResult:
    return IndicatorResult(
        name=name,
        symbol=snapshot.symbol,
        timeframe=snapshot.timeframe,
        value=value,
        signal=signal,
        trend=trend,
        strength=max(0.0, min(float(strength), 1.0)),
        timestamp=snapshot.close_time,
        metadata=dict(value),
        quality_flag=quality_flag,
    )
```

Add these indicator-specific builders:

```python
def _build_macd_result(snapshot: IndicatorSnapshot, closes: list[float], quality_flag: bool | str) -> IndicatorResult:
    previous = macd(closes[:-1]) if len(closes) > 1 else None
    histogram = snapshot.macd_hist if snapshot.macd_hist is not None else 0.0
    previous_histogram = previous[2] if previous else histogram
    slope = histogram - previous_histogram
    if snapshot.macd is not None and snapshot.macd_signal is not None and snapshot.macd > snapshot.macd_signal:
        cross_state = "golden_cross"
    elif snapshot.macd is not None and snapshot.macd_signal is not None and snapshot.macd < snapshot.macd_signal:
        cross_state = "death_cross"
    else:
        cross_state = "neutral"
    trend = "UP" if histogram > 0 else "DOWN" if histogram < 0 else "NEUTRAL"
    signal = "BULLISH" if histogram > 0 and slope >= 0 else "BEARISH" if histogram < 0 and slope <= 0 else "NEUTRAL"
    value = {
        "macd_line": snapshot.macd,
        "signal_line": snapshot.macd_signal,
        "histogram": snapshot.macd_hist,
        "histogram_slope": slope,
        "cross_state": cross_state,
    }
    return _base_result(snapshot, "MACD", value, signal, trend, min(abs(histogram), 1.0), quality_flag)


def _build_cci_result(snapshot: IndicatorSnapshot, candles: list[Candle], quality_flag: bool | str) -> IndicatorResult:
    previous = cci(candles[:-1]) if len(candles) > 1 else None
    current = snapshot.cci if snapshot.cci is not None else 0.0
    slope = current - (previous if previous is not None else current)
    extreme = abs(current) > 150
    recovery = previous is not None and abs(previous) > 100 and abs(current) <= 100
    trend = "UP" if current > 100 else "DOWN" if current < -100 else "NEUTRAL"
    signal = "STRONG" if current > 100 else "WEAK" if current < -100 else "NEUTRAL"
    value = {"cci": snapshot.cci, "cci_slope": slope, "extreme_flag": extreme, "recovery_flag": recovery}
    return _base_result(snapshot, "CCI", value, signal, trend, min(abs(current) / 200, 1.0), quality_flag)


def _build_boll_result(snapshot: IndicatorSnapshot, closes: list[float], quality_flag: bool | str) -> IndicatorResult:
    previous = bollinger(closes[:-1]) if len(closes) > 1 else None
    width = 0.0
    previous_width = 0.0
    if snapshot.boll_upper is not None and snapshot.boll_lower is not None and snapshot.boll_mid:
        width = (snapshot.boll_upper - snapshot.boll_lower) / snapshot.boll_mid
    if previous and previous[0]:
        previous_width = (previous[1] - previous[2]) / previous[0]
    expansion = width > previous_width
    contraction = width < previous_width
    close = closes[-1]
    if snapshot.boll_upper is not None and close >= snapshot.boll_upper:
        position = "above_upper"
    elif snapshot.boll_lower is not None and close <= snapshot.boll_lower:
        position = "below_lower"
    elif snapshot.boll_mid is not None and close >= snapshot.boll_mid:
        position = "above_middle"
    else:
        position = "below_middle"
    trend = "UP" if position in {"above_upper", "above_middle"} else "DOWN"
    signal = "EXPANSION" if expansion else "CONTRACTION" if contraction else "NEUTRAL"
    value = {
        "middle_band": snapshot.boll_mid,
        "upper_band": snapshot.boll_upper,
        "lower_band": snapshot.boll_lower,
        "band_width": width,
        "band_expansion_flag": expansion,
        "band_contraction_flag": contraction,
        "price_position": position,
    }
    return _base_result(snapshot, "BOLL", value, signal, trend, min(width, 1.0), quality_flag)


def _build_rsi_result(snapshot: IndicatorSnapshot, closes: list[float], quality_flag: bool | str) -> IndicatorResult:
    previous = rsi(closes[:-1]) if len(closes) > 1 else None
    current = snapshot.rsi if snapshot.rsi is not None else 50.0
    slope = current - (previous if previous is not None else current)
    overbought = current > 70
    oversold = current < 30
    midline_state = "above_midline" if current > 55 else "below_midline" if current < 45 else "near_midline"
    trend = "UP" if current > 55 else "DOWN" if current < 45 else "NEUTRAL"
    signal = "OVERBOUGHT" if overbought else "OVERSOLD" if oversold else "NEUTRAL"
    value = {
        "rsi": snapshot.rsi,
        "rsi_slope": slope,
        "overbought_flag": overbought,
        "oversold_flag": oversold,
        "midline_state": midline_state,
    }
    return _base_result(snapshot, "RSI", value, signal, trend, abs(current - 50) / 50, quality_flag)


def _build_cvd_result(snapshot: IndicatorSnapshot, candles: list[Candle], quality_flag: bool | str) -> IndicatorResult:
    cvd_values = cumulative_cvd(candles)
    previous_cvd = cvd_values[-2] if len(cvd_values) > 1 else cvd_values[-1]
    current_cvd = cvd_values[-1]
    slope = current_cvd - previous_cvd
    price_delta = candles[-1].close - candles[-2].close if len(candles) > 1 else 0.0
    divergence = (price_delta > 0 and slope < 0) or (price_delta < 0 and slope > 0)
    buy_pressure = max(snapshot.cvd_delta or 0.0, 0.0)
    sell_pressure = abs(min(snapshot.cvd_delta or 0.0, 0.0))
    trend = "UP" if slope > 0 else "DOWN" if slope < 0 else "NEUTRAL"
    signal = "DIVERGENCE" if divergence else "BUY_PRESSURE" if slope > 0 else "SELL_PRESSURE" if slope < 0 else "NEUTRAL"
    value = {
        "cvd": snapshot.cvd,
        "cvd_delta": snapshot.cvd_delta,
        "cvd_slope": slope,
        "cvd_divergence_flag": divergence,
        "buy_pressure": buy_pressure,
        "sell_pressure": sell_pressure,
    }
    return _base_result(snapshot, "CVD", value, signal, trend, min(abs(slope) / 100, 1.0), quality_flag)


def _build_atr_result(snapshot: IndicatorSnapshot, candles: list[Candle], quality_flag: bool | str) -> IndicatorResult:
    current_atr = snapshot.atr if snapshot.atr is not None else 0.0
    close = candles[-1].close
    atr_pct = current_atr / close if close else 0.0
    if atr_pct >= 0.05:
        volatility_state = "high"
    elif atr_pct <= 0.01:
        volatility_state = "low"
    else:
        volatility_state = "normal"
    value = {"atr": snapshot.atr, "atr_pct": atr_pct, "volatility_state": volatility_state}
    return _base_result(snapshot, "ATR", value, "RISK_ONLY", "NEUTRAL", min(atr_pct * 10, 1.0), quality_flag)
```

- [ ] **Step 4: Run engine tests**

Run:

```powershell
pytest tests\test_indicator_engine.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src\indicators\indicator_engine.py tests\test_indicator_engine.py
git commit -m "feat: add standardized indicator results"
```

Expected: commit succeeds if commits are enabled for this execution.

---

### Task 4: Expand Indicator Describe Output

**Files:**

- Modify: `scripts/describe_indicator_rules.py`
- Modify: `tests/test_describe_indicator_rules.py`

- [ ] **Step 1: Replace describe test**

Replace `tests/test_describe_indicator_rules.py` with:

```python
import json
import subprocess
import sys


def test_describe_indicator_rules_outputs_completed_03_contract():
    result = subprocess.run(
        [sys.executable, "scripts/describe_indicator_rules.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["indicator_names"] == ["MACD", "CCI", "BOLL", "RSI", "CVD", "ATR"]
    assert payload["params"]["MACD"]["fast"] == 12
    assert payload["responsibilities"]["ATR"] == "volatility_stop_position_risk"
    assert payload["input_fields"][-2:] == ["is_closed", "quality_flag"]
    assert payload["output_fields"] == [
        "name",
        "symbol",
        "timeframe",
        "timestamp",
        "value",
        "signal",
        "trend",
        "strength",
        "quality_flag",
        "metadata",
    ]
    assert payload["required_outputs"]["MACD"] == [
        "macd_line",
        "signal_line",
        "histogram",
        "histogram_slope",
        "cross_state",
    ]
    assert payload["timeframe_indicator_map"]["15m"] == ["RSI", "MACD", "CVD", "BOLL"]
    assert payload["conflict_priority"][0] == "data_quality"
    assert "direction" in payload["forbidden_usages"]["ATR"]
    assert payload["cache_fields"] == ["version", "timestamp", "timeframe", "indicator", "quality_flag"]
```

- [ ] **Step 2: Run describe test and confirm failure**

Run:

```powershell
pytest tests\test_describe_indicator_rules.py -q
```

Expected: FAIL because current describe output is too thin.

- [ ] **Step 3: Replace describe script**

Replace `scripts/describe_indicator_rules.py` with:

```python
from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.data_contract import INDICATOR_REQUIRED_OUTPUTS, QUALITY_FLAGS
from src.indicators.indicator_spec import (
    DEFAULT_INDICATOR_PARAMS,
    GLOBAL_FORBIDDEN_INDICATOR_ACTIONS,
    INDICATOR_CACHE_FIELDS,
    INDICATOR_CONFLICT_PRIORITY,
    INDICATOR_FORBIDDEN_USAGES,
    INDICATOR_INPUT_FIELDS,
    INDICATOR_NAMES,
    INDICATOR_OUTPUT_FIELDS,
    INDICATOR_RESPONSIBILITIES,
    TIMEFRAME_INDICATOR_MAP,
)


def main() -> None:
    payload = {
        "indicator_names": INDICATOR_NAMES,
        "params": DEFAULT_INDICATOR_PARAMS,
        "responsibilities": INDICATOR_RESPONSIBILITIES,
        "input_fields": INDICATOR_INPUT_FIELDS,
        "output_fields": INDICATOR_OUTPUT_FIELDS,
        "quality_flags": QUALITY_FLAGS,
        "required_outputs": INDICATOR_REQUIRED_OUTPUTS,
        "timeframe_indicator_map": TIMEFRAME_INDICATOR_MAP,
        "conflict_priority": INDICATOR_CONFLICT_PRIORITY,
        "forbidden_usages": INDICATOR_FORBIDDEN_USAGES,
        "global_forbidden_actions": GLOBAL_FORBIDDEN_INDICATOR_ACTIONS,
        "cache_fields": INDICATOR_CACHE_FIELDS,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run describe test**

Run:

```powershell
pytest tests\test_describe_indicator_rules.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add scripts\describe_indicator_rules.py tests\test_describe_indicator_rules.py
git commit -m "feat: describe indicator specification contract"
```

Expected: commit succeeds if commits are enabled for this execution.

---

### Task 5: Sync Scaffold Templates

**Files:**

- Modify: `scripts/scaffold_ai300_framework.py`
- Modify: `tests/test_framework_scaffold.py`

- [ ] **Step 1: Add scaffold assertions**

Append to `tests/test_framework_scaffold.py`:

```python
def test_scaffold_includes_refreshed_indicator_spec_templates():
    spec_template = FILES["src/indicators/indicator_spec.py"]
    engine_template = FILES["src/indicators/indicator_engine.py"]
    describe_template = FILES["scripts/describe_indicator_rules.py"]

    assert "INDICATOR_CONFLICT_PRIORITY" in spec_template
    assert "TIMEFRAME_INDICATOR_MAP" in spec_template
    assert "INDICATOR_FORBIDDEN_USAGES" in spec_template
    assert "compute_indicator_results" in engine_template
    assert "IndicatorResult" in engine_template
    assert "required_outputs" in describe_template
```

- [ ] **Step 2: Run scaffold test and confirm failure**

Run:

```powershell
pytest tests\test_framework_scaffold.py -q
```

Expected: FAIL until scaffold templates are synchronized.

- [ ] **Step 3: Update scaffold templates**

In `scripts/scaffold_ai300_framework.py`, update the `FILES` entries for:

- `src/indicators/indicator_spec.py`
- `src/indicators/indicator_engine.py`
- `scripts/describe_indicator_rules.py`
- `tests/test_indicator_spec_rules.py`
- `tests/test_indicator_engine.py`
- `tests/test_describe_indicator_rules.py`

Use the same final contents from Tasks 2, 3, and 4.

- [ ] **Step 4: Run scaffold test**

Run:

```powershell
pytest tests\test_framework_scaffold.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add scripts\scaffold_ai300_framework.py tests\test_framework_scaffold.py
git commit -m "feat: sync indicator scaffold templates"
```

Expected: commit succeeds if commits are enabled for this execution.

---

### Task 6: Final Verification

**Files:**

- No planned source edits.

- [ ] **Step 1: Run targeted tests**

Run:

```powershell
pytest tests\test_indicator_spec_rules.py tests\test_indicator_engine.py tests\test_describe_indicator_rules.py tests\test_framework_scaffold.py -q
```

Expected: PASS.

- [ ] **Step 2: Run related contract tests**

Run:

```powershell
pytest tests\test_data_contract.py tests\test_project_spec.py tests\test_strategy_philosophy.py tests\test_multi_tf_rules.py tests\test_signal_engine.py -q
```

Expected: PASS or only failures caused by old tests expecting the previous 03 priority/responsibility strings. If failures are old-contract expectations, update only those tests or scripts that directly encode 03 indicator semantics.

- [ ] **Step 3: Run full tests and compile**

Run:

```powershell
pytest -q
python -m compileall src scripts tests
```

Expected: PASS.

- [ ] **Step 4: Confirm Binance client untouched**

Run:

```powershell
git diff -- src\api\binance_client.py
```

Expected: no output.

- [ ] **Step 5: Inspect final diff**

Run:

```powershell
git status --short
git diff -- docs\03_indicator_spec.md src\indicators\indicator_spec.py src\indicators\indicator_engine.py scripts\describe_indicator_rules.py tests\test_indicator_spec_rules.py tests\test_indicator_engine.py tests\test_describe_indicator_rules.py scripts\scaffold_ai300_framework.py tests\test_framework_scaffold.py
```

Expected: only 03-related files appear in this diff. Existing 02 changes may still appear in `git status --short`, but they should not be mixed into 03 commits unless the user asks.

---

## Non-Goals

- Do not change live execution behavior.
- Do not change signal generation decisions.
- Do not change risk sizing logic.
- Do not change backtest fill assumptions.
- Do not add new indicators beyond `MACD`, `CCI`, `BOLL`, `RSI`, `CVD`, `ATR`.
- Do not modify `src/api/binance_client.py`.
- Do not make ATR directional.
- Do not let indicators create orders, final position sizes, state-machine transitions, or "must trade" decisions.

---

## Completion Criteria

- `docs/03_indicator_spec.md` is clean canonical markdown.
- `src/indicators/indicator_spec.py` exposes the refreshed 03 machine-readable contract.
- `compute_indicator_snapshot()` remains compatible.
- `compute_indicator_results()` returns standardized `IndicatorResult` objects for all V1 indicators.
- Closed-candle and quality semantics are enforced for standardized result computation.
- Describe output exports the full indicator contract.
- Scaffold templates match the implemented 03 contract.
- Targeted tests, related contract tests, full tests, and compileall pass.
- `git diff -- src\api\binance_client.py` has no output.
