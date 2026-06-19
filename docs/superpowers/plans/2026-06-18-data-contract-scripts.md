# Data Contract Scripts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the scripts required by `docs/09_data_contract.md` as deterministic data-contract validation utilities.

**Architecture:** Add a focused `src/data/data_contract.py` module that documents required data types, candle fields, supported timeframes, timeframe roles, aggregation rules, indicator input contract, and validators. Keep existing `Candle`, loaders, CVD builders, and indicators compatible; do not add network access or change the stable Binance client.

**Tech Stack:** Python standard library, dataclasses, pytest.

---

## Scope Notes

`docs/09_data_contract.md` currently ends at line 103 with an open code block:

```text
candles: list[OHLCV]
```

This plan implements only the explicit requirements present in the file:

- Required data types: K-line, volume, active buy/sell, position or funding, universe list.
- Required K-line fields: `open_time`, `close_time`, `open`, `high`, `low`, `close`, `volume`, `quote_volume`, `trade_count`.
- Supported timeframes and roles: 15m execution, 30m confirmation, 1H direction, 4H background.
- UTC-aligned multi-timeframe aggregation rules with no future leakage.
- CVD must expose cumulative value, delta, slope, and divergence judgment.
- Indicator modules must accept a unified `candles: list[OHLCV]` input.

This plan does not invent order book formats, funding-rate schemas, persistence tables, exchange precision policy, or live data sync behavior.

## File Structure

- Create: `src/data/data_contract.py` - contract constants, `CVDPoint`, candle validation, timeframe alignment, indicator input validation, and CVD feature generation.
- Modify: `src/data/cvd_builder.py` - keep `build_cvd`, add a thin wrapper returning CVD contract points.
- Create: `scripts/describe_data_contract.py` - prints 09 data contract as JSON.
- Create: `tests/test_data_contract.py` - tests required fields, timeframes, candle validation, UTC alignment, indicator input validation, and CVD features.
- Create: `tests/test_describe_data_contract.py` - tests describe script JSON.
- Modify: `scripts/scaffold_ai300_framework.py` - keep generated framework template aligned with new module, script, and tests.
- Preserve: `src/api/binance_client.py` - do not modify the stable Binance client.

---

### Task 1: Contract Constants and Candle Validation

**Files:**

- Create: `src/data/data_contract.py`
- Create: `tests/test_data_contract.py`

- [ ] **Step 1: Write failing tests for contract constants and candle validation**

```python
import pytest

from src.core.models import Candle
from src.data.data_contract import (
    REQUIRED_CANDLE_FIELDS,
    REQUIRED_DATA_TYPES,
    SUPPORTED_TIMEFRAMES,
    TIMEFRAME_ROLES,
    validate_ohlcv_contract,
)


def candle(**overrides) -> Candle:
    values = {
        "symbol": "BTCUSDT",
        "timeframe": "15m",
        "open_time": 0,
        "close_time": 900,
        "open": 100.0,
        "high": 105.0,
        "low": 95.0,
        "close": 101.0,
        "volume": 10.0,
        "quote_volume": 1_000.0,
        "trade_count": 20,
        "taker_buy_volume": 6.0,
    }
    values.update(overrides)
    return Candle(**values)


def test_data_contract_constants_match_doc():
    assert REQUIRED_DATA_TYPES == [
        "kline",
        "volume",
        "active_buy_sell",
        "position_or_funding",
        "universe",
    ]
    assert REQUIRED_CANDLE_FIELDS == [
        "open_time",
        "close_time",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "quote_volume",
        "trade_count",
    ]
    assert SUPPORTED_TIMEFRAMES == ["15m", "30m", "1h", "4h"]
    assert TIMEFRAME_ROLES["15m"] == "execution"
    assert TIMEFRAME_ROLES["4h"] == "background"


def test_validate_ohlcv_contract_accepts_valid_candle():
    result = validate_ohlcv_contract(candle())
    assert result.passed is True
    assert result.reason == "candle contract approved"


def test_validate_ohlcv_contract_rejects_bad_timeframe_and_ohlc():
    result = validate_ohlcv_contract(candle(timeframe="5m", high=99))
    assert result.passed is False
    assert "timeframe" in result.reason


def test_validate_ohlcv_contract_rejects_missing_volume_fields():
    result = validate_ohlcv_contract(candle(quote_volume=0, trade_count=0))
    assert result.passed is False
    assert "quote_volume" in result.reason
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_data_contract.py -q`

Expected: FAIL because `src/data/data_contract.py` does not exist.

- [ ] **Step 3: Implement constants and candle validation**

Create `src/data/data_contract.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

from src.core.models import Candle


REQUIRED_DATA_TYPES = ["kline", "volume", "active_buy_sell", "position_or_funding", "universe"]
REQUIRED_CANDLE_FIELDS = ["open_time", "close_time", "open", "high", "low", "close", "volume", "quote_volume", "trade_count"]
SUPPORTED_TIMEFRAMES = ["15m", "30m", "1h", "4h"]
TIMEFRAME_SECONDS = {"15m": 900, "30m": 1800, "1h": 3600, "4h": 14400}
TIMEFRAME_ROLES = {"15m": "execution", "30m": "confirmation", "1h": "direction", "4h": "background"}


@dataclass(frozen=True)
class ContractCheck:
    name: str
    passed: bool
    reason: str


def normalize_timeframe(timeframe: str) -> str:
    value = timeframe.strip().lower()
    if value == "1h":
        return "1h"
    if value == "4h":
        return "4h"
    return value


def validate_ohlcv_contract(candle: Candle) -> ContractCheck:
    timeframe = normalize_timeframe(candle.timeframe)
    if timeframe not in SUPPORTED_TIMEFRAMES:
        return ContractCheck("ohlcv_contract", False, f"unsupported timeframe: {candle.timeframe}")
    if candle.close_time <= candle.open_time:
        return ContractCheck("ohlcv_contract", False, "close_time must be greater than open_time")
    if candle.high < max(candle.open, candle.close) or candle.low > min(candle.open, candle.close):
        return ContractCheck("ohlcv_contract", False, "invalid OHLC relationship")
    if min(candle.open, candle.high, candle.low, candle.close) <= 0:
        return ContractCheck("ohlcv_contract", False, "prices must be positive")
    if candle.volume <= 0:
        return ContractCheck("ohlcv_contract", False, "volume must be positive")
    if candle.quote_volume <= 0:
        return ContractCheck("ohlcv_contract", False, "quote_volume must be positive")
    if candle.trade_count <= 0:
        return ContractCheck("ohlcv_contract", False, "trade_count must be positive")
    return ContractCheck("ohlcv_contract", True, "candle contract approved")
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_data_contract.py -q`

Expected: PASS for constants and candle validation tests.

---

### Task 2: UTC Alignment and Indicator Input Contract

**Files:**

- Modify: `src/data/data_contract.py`
- Modify: `tests/test_data_contract.py`

- [ ] **Step 1: Add failing tests for UTC alignment and indicator input contract**

Append to `tests/test_data_contract.py`:

```python
from src.data.data_contract import (
    AGGREGATION_RULES,
    validate_indicator_input,
    validate_timeframe_utc_alignment,
)


def test_aggregation_rules_match_doc():
    assert AGGREGATION_RULES == {
        "30m": "15m",
        "1h": ("15m", "30m"),
        "4h": "1h",
    }


def test_validate_timeframe_utc_alignment_accepts_closed_15m_grid():
    result = validate_timeframe_utc_alignment(candle(open_time=900, close_time=1800), base_close_time=1800)
    assert result.passed is True


def test_validate_timeframe_utc_alignment_rejects_future_leakage():
    result = validate_timeframe_utc_alignment(candle(open_time=1800, close_time=2700), base_close_time=1800)
    assert result.passed is False
    assert "future" in result.reason


def test_validate_indicator_input_requires_uniform_symbol_timeframe_and_order():
    candles = [candle(open_time=900, close_time=1800), candle(open_time=0, close_time=900)]
    result = validate_indicator_input(candles)
    assert result.passed is False
    assert "ordered" in result.reason

    ok = validate_indicator_input([candle(open_time=0, close_time=900), candle(open_time=900, close_time=1800)])
    assert ok.passed is True
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_data_contract.py -q`

Expected: FAIL because alignment and input validators are missing.

- [ ] **Step 3: Implement alignment and indicator input validators**

Add to `src/data/data_contract.py`:

```python
AGGREGATION_RULES = {"30m": "15m", "1h": ("15m", "30m"), "4h": "1h"}


def validate_timeframe_utc_alignment(candle: Candle, base_close_time: int) -> ContractCheck:
    timeframe = normalize_timeframe(candle.timeframe)
    if timeframe not in TIMEFRAME_SECONDS:
        return ContractCheck("timeframe_alignment", False, f"unsupported timeframe: {candle.timeframe}")
    seconds = TIMEFRAME_SECONDS[timeframe]
    if candle.open_time % seconds != 0 or candle.close_time % seconds != 0:
        return ContractCheck("timeframe_alignment", False, "candle is not aligned to UTC timeframe grid")
    if candle.close_time > base_close_time:
        return ContractCheck("timeframe_alignment", False, "future data leakage is not allowed")
    return ContractCheck("timeframe_alignment", True, "candle is UTC aligned and closed")


def validate_indicator_input(candles: list[Candle]) -> ContractCheck:
    if not candles:
        return ContractCheck("indicator_input", False, "candles must not be empty")
    first_symbol = candles[0].symbol
    first_timeframe = normalize_timeframe(candles[0].timeframe)
    previous_open_time = -1
    for item in candles:
        if item.symbol != first_symbol:
            return ContractCheck("indicator_input", False, "candles must use one symbol")
        if normalize_timeframe(item.timeframe) != first_timeframe:
            return ContractCheck("indicator_input", False, "candles must use one timeframe")
        if item.open_time <= previous_open_time:
            return ContractCheck("indicator_input", False, "candles must be ordered by open_time")
        check = validate_ohlcv_contract(item)
        if not check.passed:
            return ContractCheck("indicator_input", False, check.reason)
        previous_open_time = item.open_time
    return ContractCheck("indicator_input", True, "candles: list[OHLCV] approved")
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_data_contract.py -q`

Expected: PASS.

---

### Task 3: CVD Contract Features

**Files:**

- Modify: `src/data/data_contract.py`
- Modify: `src/data/cvd_builder.py`
- Modify: `tests/test_data_contract.py`

- [ ] **Step 1: Add failing tests for CVD cumulative, delta, slope, and divergence**

Append to `tests/test_data_contract.py`:

```python
from src.data.cvd_builder import build_cvd_points
from src.data.data_contract import CVD_SOURCES, CVDPoint, build_cvd_contract_points, judge_cvd_divergence


def test_cvd_sources_match_doc():
    assert CVD_SOURCES == ["trades", "taker_buy_sell_estimate", "exchange_active_buy_sell"]


def test_build_cvd_contract_points_outputs_value_delta_slope():
    candles = [
        candle(open_time=0, close_time=900, close=100, volume=10, taker_buy_volume=6),
        candle(open_time=900, close_time=1800, close=101, volume=10, taker_buy_volume=7),
    ]
    points = build_cvd_contract_points(candles)
    assert points == [
        CVDPoint(close_time=900, cumulative=2.0, delta=2.0, slope=0.0, divergence="NONE"),
        CVDPoint(close_time=1800, cumulative=6.0, delta=4.0, slope=4.0, divergence="NONE"),
    ]
    assert build_cvd_points(candles) == points


def test_judge_cvd_divergence_detects_price_up_cvd_down():
    assert judge_cvd_divergence(price_delta=1.0, cvd_delta=-2.0) == "BEARISH"
    assert judge_cvd_divergence(price_delta=-1.0, cvd_delta=2.0) == "BULLISH"
    assert judge_cvd_divergence(price_delta=1.0, cvd_delta=2.0) == "NONE"
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_data_contract.py -q`

Expected: FAIL because CVD contract points are missing.

- [ ] **Step 3: Implement CVD contract points**

Add to `src/data/data_contract.py`:

```python
CVD_SOURCES = ["trades", "taker_buy_sell_estimate", "exchange_active_buy_sell"]


@dataclass(frozen=True)
class CVDPoint:
    close_time: int
    cumulative: float
    delta: float
    slope: float
    divergence: str


def judge_cvd_divergence(price_delta: float, cvd_delta: float) -> str:
    if price_delta > 0 and cvd_delta < 0:
        return "BEARISH"
    if price_delta < 0 and cvd_delta > 0:
        return "BULLISH"
    return "NONE"


def build_cvd_contract_points(candles: list[Candle]) -> list[CVDPoint]:
    total = 0.0
    previous_cumulative = 0.0
    previous_close = None
    points = []
    for item in candles:
        sell_volume = max(item.volume - item.taker_buy_volume, 0.0)
        delta = item.taker_buy_volume - sell_volume
        total += delta
        slope = total - previous_cumulative if points else 0.0
        price_delta = 0.0 if previous_close is None else item.close - previous_close
        points.append(
            CVDPoint(
                close_time=item.close_time,
                cumulative=total,
                delta=delta,
                slope=slope,
                divergence=judge_cvd_divergence(price_delta, delta),
            )
        )
        previous_cumulative = total
        previous_close = item.close
    return points
```

Add to `src/data/cvd_builder.py`:

```python
from src.data.data_contract import CVDPoint, build_cvd_contract_points


def build_cvd_points(candles: Iterable[Candle]) -> list[CVDPoint]:
    return build_cvd_contract_points(list(candles))
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_data_contract.py -q`

Expected: PASS.

---

### Task 4: Describe Script

**Files:**

- Create: `scripts/describe_data_contract.py`
- Create: `tests/test_describe_data_contract.py`

- [ ] **Step 1: Write failing describe-script test**

Create `tests/test_describe_data_contract.py`:

```python
import json
import subprocess
import sys


def test_describe_data_contract_outputs_policy_json():
    completed = subprocess.run(
        [sys.executable, "scripts/describe_data_contract.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["required_candle_fields"][0] == "open_time"
    assert payload["timeframe_roles"]["15m"] == "execution"
    assert payload["aggregation_rules"]["30m"] == "15m"
    assert payload["cvd_features"] == ["cumulative", "delta", "slope", "divergence"]
    assert payload["indicator_input"] == "candles: list[OHLCV]"
```

- [ ] **Step 2: Run test to verify failure**

Run: `pytest tests/test_describe_data_contract.py -q`

Expected: FAIL because the script does not exist.

- [ ] **Step 3: Implement describe script**

Create `scripts/describe_data_contract.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.data_contract import (
    AGGREGATION_RULES,
    CVD_SOURCES,
    REQUIRED_CANDLE_FIELDS,
    REQUIRED_DATA_TYPES,
    SUPPORTED_TIMEFRAMES,
    TIMEFRAME_ROLES,
)


def main() -> None:
    payload = {
        "required_data_types": REQUIRED_DATA_TYPES,
        "required_candle_fields": REQUIRED_CANDLE_FIELDS,
        "supported_timeframes": SUPPORTED_TIMEFRAMES,
        "timeframe_roles": TIMEFRAME_ROLES,
        "aggregation_rules": AGGREGATION_RULES,
        "cvd_sources": CVD_SOURCES,
        "cvd_features": ["cumulative", "delta", "slope", "divergence"],
        "indicator_input": "candles: list[OHLCV]",
        "time_axis": "UTC",
        "future_leakage": "forbidden",
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_data_contract.py tests/test_describe_data_contract.py -q`

Expected: PASS.

---

### Task 5: Scaffold Sync and Verification

**Files:**

- Modify: `scripts/scaffold_ai300_framework.py`

- [ ] **Step 1: Update scaffold templates**

Copy the final contents of these files into the matching string templates in `scripts/scaffold_ai300_framework.py`:

- `src/data/data_contract.py`
- `src/data/cvd_builder.py`
- `scripts/describe_data_contract.py`
- `tests/test_data_contract.py`
- `tests/test_describe_data_contract.py`

- [ ] **Step 2: Run targeted tests**

Run: `pytest tests/test_data_contract.py tests/test_describe_data_contract.py tests/test_framework_scaffold.py -q`

Expected: PASS.

- [ ] **Step 3: Run full verification**

Run:

```bash
pytest -q
python -m compileall src scripts tests
python scripts/describe_data_contract.py
git diff -- src/api/binance_client.py
```

Expected: all tests pass, compile succeeds, describe JSON includes 09 contract fields, and Binance diff has no output.

---

## Self-Review

- Spec coverage: covers required data types, OHLCV fields, UTC timeframes and roles, no future leakage, CVD cumulative/delta/slope/divergence, and unified indicator input.
- Placeholder scan: no `TBD`, `TODO`, `implement later`, or unspecified test steps.
- Type consistency: `ContractCheck`, `CVDPoint`, `validate_ohlcv_contract`, `validate_timeframe_utc_alignment`, `validate_indicator_input`, and `build_cvd_contract_points` are used consistently across tasks.
