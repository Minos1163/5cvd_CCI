# Indicator Spec Scripts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the scripts required by `docs/03_indicator_spec.md` as pure indicator-layer utilities.

**Architecture:** Keep indicator math in `src/indicators/*.py`, add an `indicator_spec` module for documented parameters, responsibilities, priorities, and interpretation helpers, then add an `indicator_engine` module that computes an `IndicatorSnapshot` from candles. The indicator layer must not create trade signals or call execution/risk code.

**Tech Stack:** Python standard library, dataclasses, pytest.

---

## File Structure

- Create: `src/indicators/indicator_spec.py` - documented default parameters, responsibilities, priority order, and interpretation helpers from `03_indicator_spec.md`.
- Create: `src/indicators/indicator_engine.py` - computes a combined `IndicatorSnapshot` from candle data using existing indicator math functions.
- Modify: `src/indicators/cvd.py` - add cumulative CVD helper while keeping `cvd_delta`.
- Create: `scripts/describe_indicator_rules.py` - prints documented indicator rules as JSON.
- Create: `tests/test_indicator_spec_rules.py` - tests parameters, responsibilities, priority, and interpretation labels.
- Create: `tests/test_indicator_engine.py` - tests snapshot calculation uses closed candle inputs and populates expected fields.
- Create: `tests/test_describe_indicator_rules.py` - tests CLI JSON output.
- Preserve: `src/api/binance_client.py` - do not modify the stable Binance client.

---

### Task 1: Indicator Spec Rules

**Files:**

- Create: `src/indicators/indicator_spec.py`
- Create: `tests/test_indicator_spec_rules.py`

- [ ] **Step 1: Write failing tests**

```python
from src.indicators.indicator_spec import (
    DEFAULT_INDICATOR_PARAMS,
    INDICATOR_PRIORITY,
    INDICATOR_RESPONSIBILITIES,
    classify_cci,
    classify_rsi,
    validate_indicator_usage,
)


def test_default_indicator_params_match_doc():
    assert DEFAULT_INDICATOR_PARAMS["MACD"] == {"fast": 12, "slow": 26, "signal": 9}
    assert DEFAULT_INDICATOR_PARAMS["RSI"] == {"period": 14}
    assert DEFAULT_INDICATOR_PARAMS["BOLL"] == {"period": 20, "std": 2.0}
    assert DEFAULT_INDICATOR_PARAMS["ATR"] == {"period": 14}


def test_priority_matches_doc():
    assert INDICATOR_PRIORITY == ("MACD", "CVD", "RSI", "CCI", "BOLL")


def test_atr_cannot_be_used_for_direction():
    ok, reason = validate_indicator_usage("ATR", "direction")
    assert ok is False
    assert "risk" in reason


def test_rsi_classification():
    assert classify_rsi(75) == "overheated"
    assert classify_rsi(25) == "oversold"
    assert classify_rsi(50) == "range"


def test_cci_classification():
    assert classify_cci(120) == "strong"
    assert classify_cci(-120) == "weak"
    assert classify_cci(0) == "neutral"
    assert INDICATOR_RESPONSIBILITIES["CVD"] == "fund_flow"
```

- [ ] **Step 2: Run test to verify failure**

Run: `pytest tests/test_indicator_spec_rules.py -q`

Expected: FAIL because `src.indicators.indicator_spec` does not exist.

- [ ] **Step 3: Implement indicator spec module**

```python
from __future__ import annotations

DEFAULT_INDICATOR_PARAMS = {
    "MACD": {"fast": 12, "slow": 26, "signal": 9},
    "RSI": {"period": 14},
    "CCI": {"period": 20},
    "BOLL": {"period": 20, "std": 2.0},
    "ATR": {"period": 14},
    "CVD": {},
}

INDICATOR_RESPONSIBILITIES = {
    "MACD": "trend",
    "RSI": "pullback",
    "CCI": "strength",
    "BOLL": "structure",
    "CVD": "fund_flow",
    "ATR": "risk",
}

INDICATOR_PRIORITY = ("MACD", "CVD", "RSI", "CCI", "BOLL")


def validate_indicator_usage(indicator: str, usage: str) -> tuple[bool, str]:
    key = indicator.upper()
    responsibility = INDICATOR_RESPONSIBILITIES.get(key)
    if responsibility is None:
        return False, f"unknown indicator: {indicator}"
    if key == "ATR" and usage == "direction":
        return False, "ATR is reserved for risk and must not be used for direction"
    return True, f"{key} allowed for {usage}"


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

- [ ] **Step 4: Run test to verify pass**

Run: `pytest tests/test_indicator_spec_rules.py -q`

Expected: PASS.

---

### Task 2: CVD and Indicator Engine

**Files:**

- Modify: `src/indicators/cvd.py`
- Create: `src/indicators/indicator_engine.py`
- Create: `tests/test_indicator_engine.py`

- [ ] **Step 1: Write failing tests**

```python
from src.core.models import Candle
from src.indicators.cvd import cumulative_cvd
from src.indicators.indicator_engine import compute_indicator_snapshot


def make_candles(count: int) -> list[Candle]:
    candles = []
    for i in range(count):
        close = 100 + i
        candles.append(
            Candle(
                symbol="BTCUSDT",
                timeframe="15m",
                open_time=i * 900,
                close_time=(i + 1) * 900,
                open=close - 0.5,
                high=close + 1,
                low=close - 1,
                close=close,
                volume=100,
                taker_buy_volume=60,
            )
        )
    return candles


def test_cumulative_cvd_uses_taker_buy_minus_sell():
    candles = make_candles(3)
    assert cumulative_cvd(candles) == [20.0, 40.0, 60.0]


def test_compute_indicator_snapshot_populates_fields():
    snapshot = compute_indicator_snapshot(make_candles(40))
    assert snapshot.symbol == "BTCUSDT"
    assert snapshot.timeframe == "15m"
    assert snapshot.macd is not None
    assert snapshot.rsi is not None
    assert snapshot.cci is not None
    assert snapshot.boll_mid is not None
    assert snapshot.atr is not None
    assert snapshot.cvd == 800.0
    assert snapshot.cvd_delta == 20.0
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_indicator_engine.py -q`

Expected: FAIL because `cumulative_cvd` and `indicator_engine` do not exist.

- [ ] **Step 3: Implement CVD helper**

```python
from __future__ import annotations

from src.core.models import Candle


def cvd_delta(taker_buy_volume: float, total_volume: float) -> float:
    sell_volume = max(total_volume - taker_buy_volume, 0.0)
    return taker_buy_volume - sell_volume


def cumulative_cvd(candles: list[Candle]) -> list[float]:
    total = 0.0
    values: list[float] = []
    for candle in candles:
        total += cvd_delta(candle.taker_buy_volume, candle.volume)
        values.append(total)
    return values
```

- [ ] **Step 4: Implement indicator engine**

```python
from __future__ import annotations

from src.core.models import Candle, IndicatorSnapshot
from src.indicators.atr import atr
from src.indicators.boll import bollinger
from src.indicators.cci import cci
from src.indicators.cvd import cumulative_cvd, cvd_delta
from src.indicators.macd import macd
from src.indicators.rsi import rsi


def compute_indicator_snapshot(candles: list[Candle]) -> IndicatorSnapshot:
    if not candles:
        raise ValueError("candles must not be empty")
    last = candles[-1]
    closes = [candle.close for candle in candles]
    macd_values = macd(closes)
    boll_values = bollinger(closes)
    cvd_values = cumulative_cvd(candles)
    return IndicatorSnapshot(
        symbol=last.symbol,
        timeframe=last.timeframe,
        close_time=last.close_time,
        macd=macd_values[0] if macd_values else None,
        macd_signal=macd_values[1] if macd_values else None,
        macd_hist=macd_values[2] if macd_values else None,
        cci=cci(candles),
        rsi=rsi(closes),
        boll_mid=boll_values[0] if boll_values else None,
        boll_upper=boll_values[1] if boll_values else None,
        boll_lower=boll_values[2] if boll_values else None,
        atr=atr(candles),
        cvd=cvd_values[-1] if cvd_values else None,
        cvd_delta=cvd_delta(last.taker_buy_volume, last.volume),
    )
```

- [ ] **Step 5: Run tests to verify pass**

Run: `pytest tests/test_indicator_engine.py -q`

Expected: PASS.

---

### Task 3: Indicator Rules CLI

**Files:**

- Create: `scripts/describe_indicator_rules.py`
- Create: `tests/test_describe_indicator_rules.py`

- [ ] **Step 1: Write failing CLI test**

```python
import json
import subprocess
import sys


def test_describe_indicator_rules_outputs_json():
    result = subprocess.run(
        [sys.executable, "scripts/describe_indicator_rules.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    assert payload["params"]["MACD"]["fast"] == 12
    assert payload["responsibilities"]["ATR"] == "risk"
    assert payload["priority"][0] == "MACD"
```

- [ ] **Step 2: Run test to verify failure**

Run: `pytest tests/test_describe_indicator_rules.py -q`

Expected: FAIL because CLI does not exist.

- [ ] **Step 3: Implement CLI**

```python
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.indicators.indicator_spec import DEFAULT_INDICATOR_PARAMS, INDICATOR_PRIORITY, INDICATOR_RESPONSIBILITIES


def main() -> None:
    payload = {
        "params": DEFAULT_INDICATOR_PARAMS,
        "responsibilities": INDICATOR_RESPONSIBILITIES,
        "priority": INDICATOR_PRIORITY,
        "forbidden": ["ATR direction"],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify pass**

Run: `pytest tests/test_describe_indicator_rules.py -q`

Expected: PASS.

---

## Verification

Run:

```powershell
pytest tests/test_indicator_spec_rules.py tests/test_indicator_engine.py tests/test_describe_indicator_rules.py -q
pytest tests/test_project_spec.py tests/test_strategy_philosophy.py tests/test_market_universe.py tests/test_describe_project_rules.py tests/test_framework_scaffold.py -q
python -m compileall src scripts tests
python scripts/describe_indicator_rules.py
git diff -- src/api/binance_client.py
```

Expected:

- all tests pass
- compile succeeds
- CLI prints valid JSON
- `src/api/binance_client.py` diff is empty

