# Fib PA Entry Chain Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current trend-agreement-heavy dry-run entry scoring with a location-first `CCI + CVD + EMA + Price Action + Fibonacci` architecture so high scores represent better entry quality, not merely stronger agreement with an already-printed move.

**Architecture:** Add three focused scoring modules (`fib_location.py`, `pa_structure.py`, `cci_quality.py`) and integrate them behind an opt-in `fib_pa_v1` config profile. Keep live execution and Binance connectivity untouched; all first deployment is dry-run/backtest only. The new chain applies location gates before CVD/EMA confirmation and before leverage selection.

**Tech Stack:** Python dataclasses/functions, existing `BacktestBar` candles, existing EMA/CVD helpers, JSON config, pytest.

---

## Strategy Research Guardrails

**Hypothesis:** The current losing pattern is caused by late entries after momentum has already extended. Price Action and Fibonacci location filters should reduce `INITIAL_STOP_HIT` frequency, especially in 90+ score and 5x trades.

**Expected market regime:** Liquid altcoin trends with identifiable pullbacks/retests and swing structures.

**Known failure modes:**
- Fib swing detection can overfit if swings are too sensitive.
- PA labels can become noisy on 15m candles.
- New gates can reduce trade count too much.
- Pullback-required logic can miss true breakout continuation.

**Primary verification command after implementation:**

```bash
pytest tests/test_fib_location.py tests/test_pa_structure.py tests/test_cci_quality.py tests/test_entry_chain.py tests/test_entry_chain_features.py tests/test_entry_chain_config.py tests/test_dry_run_configs.py tests/test_live_dry_run.py -q
```

**Safety invariant:**

```bash
pytest tests/test_live_dry_run.py::test_live_dry_run_source_has_no_exchange_mutation_calls -q
```

`src/api/binance_client.py` must remain untouched.

---

## File Structure

Create:

- `src/signals/fib_location.py`  
  Fibonacci swing detection, Fib level computation, Fib location scoring, and exhaustion tags.

- `src/signals/pa_structure.py`  
  Price Action swing/retest/breakdown/reversal structure detection and scoring.

- `src/signals/cci_quality.py`  
  CCI calculation and momentum-quality scoring.

- `configs/entry_chain.dry_run_fib_pa_v1.json`  
  Opt-in dry-run config for the new architecture.

- `tests/test_fib_location.py`  
  Unit tests for swing filtering, Fib levels, optimal pullback, extension block.

- `tests/test_pa_structure.py`  
  Unit tests for lower-high retest, breakdown retest, no-structure chase, wick rejection.

- `tests/test_cci_quality.py`  
  Unit tests for CCI exhaustion, healthy momentum, secondary weakness, failed continuation.

Modify:

- `src/signals/entry_chain_config.py`  
  Add opt-in architecture fields and thresholds.

- `src/signals/entry_chain_features.py`  
  Add optional feature computation from existing completed bars.

- `src/signals/entry_chain_scoring.py`  
  Add `FIB_PA_WEIGHTS` and preserve current `EMA_WEIGHTS`.

- `src/signals/entry_chain.py`  
  Integrate the new component scores, hard Fib extension block, component minimums, and leverage constraints.

- `tests/test_entry_chain_config.py`  
  Parse new config fields.

- `tests/test_dry_run_configs.py`  
  Ensure the new config loads and preserves current dry-run safety constraints.

- `tests/test_entry_chain.py`  
  Integration tests for BNB/LINK-style late shorts being demoted.

- `tests/test_live_dry_run.py`  
  Confirm dry-run remains no-exchange-mutation and can emit the new score detail.

Do not modify:

- `src/api/binance_client.py`
- live order submission/cancel paths
- exchange credential handling

---

## Task 1: Fibonacci Location Module

**Files:**
- Create: `src/signals/fib_location.py`
- Test: `tests/test_fib_location.py`

- [ ] **Step 1: Write failing Fib tests**

Create `tests/test_fib_location.py`:

```python
from src.backtest.engine import BacktestBar
from src.signals.fib_location import (
    FibLocationResult,
    compute_fib_levels,
    detect_fractal_swings,
    score_fibonacci_location,
)


def bar(ts: int, open_: float, high: float, low: float, close: float) -> BacktestBar:
    return BacktestBar("TESTUSDT", ts, open_, high, low, close, 1000.0)


def test_compute_downtrend_fib_levels():
    levels = compute_fib_levels(110.0, 100.0, "DOWN")

    assert levels["r382"] == 103.82
    assert levels["r500"] == 105.0
    assert levels["r618"] == 106.18
    assert levels["e1272"] == 97.28
    assert levels["e1618"] == 93.82


def test_extension_exhaustion_returns_block():
    levels = compute_fib_levels(110.0, 100.0, "DOWN")

    result = score_fibonacci_location(
        close=94.0,
        side="SHORT",
        fib_1h=levels,
        fib_15m=None,
        atr=1.0,
    )

    assert result.score == 0.0
    assert result.action_cap == "NO_TRADE"
    assert result.tag == "FIB_1H_EXTENSION_EXHAUSTION_BLOCK"


def test_optimal_pullback_returns_max_score():
    levels = compute_fib_levels(110.0, 100.0, "DOWN")

    result = score_fibonacci_location(
        close=105.0,
        side="SHORT",
        fib_1h=levels,
        fib_15m=None,
        atr=1.0,
    )

    assert result.score == 18.0
    assert result.action_cap is None
    assert result.tag == "FIB_1H_PULLBACK_OPTIMAL"


def test_neutral_location_returns_mid_score_without_levels():
    result = score_fibonacci_location(
        close=105.0,
        side="SHORT",
        fib_1h=None,
        fib_15m=None,
        atr=1.0,
    )

    assert result.score == 9.0
    assert result.tag == "FIB_NEUTRAL"


def test_fractal_swings_filter_noise_by_atr_and_spacing():
    bars = [
        bar(0, 100, 101, 99, 100),
        bar(900, 100, 102, 99, 101),
        bar(1800, 101, 105, 100, 104),
        bar(2700, 104, 103, 98, 99),
        bar(3600, 99, 101, 97, 100),
        bar(4500, 100, 102, 99, 101),
        bar(5400, 101, 103, 100, 102),
    ]

    swings = detect_fractal_swings(bars, k=2, min_atr_mult=1.0, min_spacing_bars=2, atr=2.0)

    assert any(item.kind == "HIGH" and item.price == 105 for item in swings)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/test_fib_location.py -q
```

Expected: FAIL because `src.signals.fib_location` does not exist.

- [ ] **Step 3: Implement minimal Fib module**

Create `src/signals/fib_location.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from src.backtest.engine import BacktestBar


@dataclass(frozen=True)
class SwingPoint:
    kind: str
    timestamp: int
    index: int
    price: float


@dataclass(frozen=True)
class FibLocationResult:
    score: float
    tag: str
    action_cap: str | None
    details: dict[str, float | str | None]


def compute_fib_levels(swing_high: float, swing_low: float, trend: str) -> dict[str, float]:
    high = float(swing_high)
    low = float(swing_low)
    diff = high - low
    normalized = trend.strip().upper()
    if diff <= 0:
        return {}
    if normalized == "DOWN":
        levels = {
            "r382": low + diff * 0.382,
            "r500": low + diff * 0.500,
            "r618": low + diff * 0.618,
            "r786": low + diff * 0.786,
            "e1000": low,
            "e1272": low - diff * 0.272,
            "e1618": low - diff * 0.618,
            "e2000": low - diff * 1.000,
        }
    else:
        levels = {
            "r382": high - diff * 0.382,
            "r500": high - diff * 0.500,
            "r618": high - diff * 0.618,
            "r786": high - diff * 0.786,
            "e1000": high,
            "e1272": high + diff * 0.272,
            "e1618": high + diff * 0.618,
            "e2000": high + diff * 1.000,
        }
    return {key: round(value, 8) for key, value in levels.items()}


def detect_fractal_swings(
    bars: Sequence[BacktestBar],
    *,
    k: int = 2,
    min_atr_mult: float = 1.2,
    min_spacing_bars: int = 6,
    atr: float = 0.0,
    lookback: int = 50,
) -> list[SwingPoint]:
    recent = list(bars)[-lookback:]
    if len(recent) < k * 2 + 1:
        return []
    swings: list[SwingPoint] = []
    min_move = max(0.0, float(atr) * float(min_atr_mult))
    for idx in range(k, len(recent) - k):
        item = recent[idx]
        left = recent[idx - k : idx]
        right = recent[idx + 1 : idx + 1 + k]
        is_high = all(item.high > peer.high for peer in [*left, *right])
        is_low = all(item.low < peer.low for peer in [*left, *right])
        if not is_high and not is_low:
            continue
        price = item.high if is_high else item.low
        if swings and idx - swings[-1].index < min_spacing_bars:
            continue
        if swings and abs(price - swings[-1].price) < min_move:
            continue
        swings.append(SwingPoint("HIGH" if is_high else "LOW", item.timestamp, idx, price))
    return swings


def score_fibonacci_location(
    *,
    close: float,
    side: str,
    fib_1h: Mapping[str, float] | None,
    fib_15m: Mapping[str, float] | None,
    atr: float,
) -> FibLocationResult:
    normalized = side.strip().upper()
    tolerance = max(0.0, float(atr) * 0.5)
    price = float(close)
    score = 9.0
    tag = "FIB_NEUTRAL"
    action_cap: str | None = None
    details: dict[str, float | str | None] = {"close": price, "tolerance": tolerance}

    if normalized == "SHORT":
        block = _short_extension_block(price, fib_1h, tolerance, "1H") or _short_extension_block(price, fib_15m, tolerance, "15M")
        if block:
            return FibLocationResult(0.0, block, "NO_TRADE", details)
        score, tag = _short_location_score(price, fib_1h, tolerance, "1H")
        if fib_15m and 0 < price - float(fib_15m.get("e1000", price)) < tolerance:
            score -= 3.0
            tag += "_15M_SUPPORT_NEARBY"
    elif normalized == "LONG":
        block = _long_extension_block(price, fib_1h, tolerance, "1H") or _long_extension_block(price, fib_15m, tolerance, "15M")
        if block:
            return FibLocationResult(0.0, block, "NO_TRADE", details)
        score, tag = _long_location_score(price, fib_1h, tolerance, "1H")

    return FibLocationResult(round(max(0.0, min(18.0, score)), 4), tag, action_cap, details)


def _short_extension_block(price: float, levels: Mapping[str, float] | None, tolerance: float, label: str) -> str | None:
    if levels and price <= float(levels["e1618"]) + tolerance:
        return f"FIB_{label}_EXTENSION_EXHAUSTION_BLOCK"
    return None


def _long_extension_block(price: float, levels: Mapping[str, float] | None, tolerance: float, label: str) -> str | None:
    if levels and price >= float(levels["e1618"]) - tolerance:
        return f"FIB_{label}_EXTENSION_EXHAUSTION_BLOCK"
    return None


def _short_location_score(price: float, levels: Mapping[str, float] | None, tolerance: float, label: str) -> tuple[float, str]:
    if not levels:
        return 9.0, "FIB_NEUTRAL"
    if float(levels["r382"]) - tolerance <= price <= float(levels["r618"]) + tolerance:
        return 18.0, f"FIB_{label}_PULLBACK_OPTIMAL"
    if float(levels["r618"]) < price <= float(levels["r786"]) + tolerance:
        return 13.0, f"FIB_{label}_DEEP_PULLBACK"
    if float(levels["e1272"]) - tolerance <= price < float(levels["e1000"]):
        return 6.0, f"FIB_{label}_EXTENSION_1272"
    if price < float(levels["e1272"]) - tolerance:
        return 2.0, f"FIB_{label}_EXTENSION_ZONE_PENALTY"
    return 9.0, "FIB_NEUTRAL"


def _long_location_score(price: float, levels: Mapping[str, float] | None, tolerance: float, label: str) -> tuple[float, str]:
    if not levels:
        return 9.0, "FIB_NEUTRAL"
    if float(levels["r618"]) - tolerance <= price <= float(levels["r382"]) + tolerance:
        return 18.0, f"FIB_{label}_PULLBACK_OPTIMAL"
    if float(levels["r786"]) - tolerance <= price < float(levels["r618"]):
        return 13.0, f"FIB_{label}_DEEP_PULLBACK"
    if float(levels["e1000"]) < price <= float(levels["e1272"]) + tolerance:
        return 6.0, f"FIB_{label}_EXTENSION_1272"
    if price > float(levels["e1272"]) + tolerance:
        return 2.0, f"FIB_{label}_EXTENSION_ZONE_PENALTY"
    return 9.0, "FIB_NEUTRAL"
```

- [ ] **Step 4: Run Fib tests**

Run:

```bash
pytest tests/test_fib_location.py -q
```

Expected: PASS.

---

## Task 2: Price Action Structure Module

**Files:**
- Create: `src/signals/pa_structure.py`
- Test: `tests/test_pa_structure.py`

- [ ] **Step 1: Write failing PA tests**

Create `tests/test_pa_structure.py`:

```python
from src.backtest.engine import BacktestBar
from src.signals.fib_location import SwingPoint
from src.signals.pa_structure import score_price_action_structure


def bar(ts: int, open_: float, high: float, low: float, close: float) -> BacktestBar:
    return BacktestBar("TESTUSDT", ts, open_, high, low, close, 1000.0)


def test_lower_high_retest_scores_high_for_short():
    bars = [
        bar(0, 110, 111, 108, 109),
        bar(900, 109, 110, 104, 105),
        bar(1800, 105, 107, 103, 106),
        bar(2700, 106, 106.5, 101, 102),
    ]
    swings = [
        SwingPoint("HIGH", 0, 0, 111),
        SwingPoint("LOW", 900, 1, 104),
        SwingPoint("HIGH", 1800, 2, 107),
    ]

    result = score_price_action_structure(bars, "SHORT", swings, atr=2.0)

    assert result.score >= 15.0
    assert result.structure_tag in {"LOWER_HIGH_RETEST", "BREAKDOWN_RETEST"}


def test_large_move_no_structure_scores_low():
    bars = [
        bar(0, 110, 111, 109, 110),
        bar(900, 110, 110.2, 108, 108.2),
        bar(1800, 108.2, 108.5, 104, 104.5),
    ]

    result = score_price_action_structure(bars, "SHORT", [], atr=2.0)

    assert result.score <= 6.0
    assert result.structure_tag == "NO_STRUCTURE"


def test_reversal_wick_penalizes_short():
    bars = [
        bar(0, 100, 101, 99, 100),
        bar(900, 100, 105, 99.5, 100.5),
    ]

    result = score_price_action_structure(bars, "SHORT", [], atr=2.0)

    assert result.candle_score < 0
    assert "REVERSAL_WICK" in result.reasons


def test_breakdown_retest_scores_high():
    bars = [
        bar(0, 110, 111, 106, 107),
        bar(900, 107, 108, 101, 102),
        bar(1800, 102, 106.2, 101.5, 105.5),
        bar(2700, 105.5, 105.8, 100, 101),
    ]
    swings = [
        SwingPoint("LOW", 0, 0, 106),
        SwingPoint("HIGH", 1800, 2, 106.2),
    ]

    result = score_price_action_structure(bars, "SHORT", swings, atr=2.0)

    assert result.score >= 12.0
    assert result.structure_tag == "BREAKDOWN_RETEST"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/test_pa_structure.py -q
```

Expected: FAIL because module does not exist.

- [ ] **Step 3: Implement minimal PA module**

Create `src/signals/pa_structure.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from src.backtest.engine import BacktestBar
from src.signals.fib_location import SwingPoint


@dataclass(frozen=True)
class PriceActionResult:
    score: float
    structure_tag: str
    structure_score: float
    candle_score: float
    swing_score: float
    reasons: tuple[str, ...]


def score_price_action_structure(
    bars: Sequence[BacktestBar],
    side: str,
    swings: Sequence[SwingPoint],
    *,
    atr: float,
) -> PriceActionResult:
    recent = list(bars)
    normalized = side.strip().upper()
    if len(recent) < 2:
        return PriceActionResult(0.0, "NO_STRUCTURE", 0.0, 0.0, 0.0, ("PA_INSUFFICIENT_BARS",))

    structure_score, structure_tag = _structure_score(recent, normalized, list(swings), atr)
    candle_score, candle_reasons = _candle_score(recent[-1], normalized, atr)
    swing_score = _swing_trend_score(list(swings), normalized)
    total = max(0.0, min(22.0, structure_score + candle_score + swing_score))
    return PriceActionResult(round(total, 4), structure_tag, structure_score, candle_score, swing_score, tuple(candle_reasons))


def _structure_score(bars: list[BacktestBar], side: str, swings: list[SwingPoint], atr: float) -> tuple[float, str]:
    if side == "SHORT":
        if _detect_lower_high_retest(bars, swings, atr, side):
            return 12.0, "LOWER_HIGH_RETEST"
        if _detect_breakdown_retest(bars, swings, atr, side):
            return 9.0, "BREAKDOWN_RETEST"
        if _detect_continuation(bars, side, atr):
            return 6.0, "CONTINUATION"
    if side == "LONG":
        if _detect_lower_high_retest(bars, swings, atr, side):
            return 12.0, "HIGHER_LOW_RETEST"
        if _detect_breakdown_retest(bars, swings, atr, side):
            return 9.0, "BREAKOUT_RETEST"
        if _detect_continuation(bars, side, atr):
            return 6.0, "CONTINUATION"
    return 0.0, "NO_STRUCTURE"


def _detect_lower_high_retest(bars: list[BacktestBar], swings: list[SwingPoint], atr: float, side: str) -> bool:
    highs = [item for item in swings if item.kind == "HIGH"]
    lows = [item for item in swings if item.kind == "LOW"]
    if side == "SHORT" and len(highs) >= 2:
        return highs[-1].price < highs[-2].price and bars[-1].close < bars[-2].close
    if side == "LONG" and len(lows) >= 2:
        return lows[-1].price > lows[-2].price and bars[-1].close > bars[-2].close
    return False


def _detect_breakdown_retest(bars: list[BacktestBar], swings: list[SwingPoint], atr: float, side: str) -> bool:
    if len(bars) < 4:
        return False
    if side == "SHORT":
        prior_supports = [item.price for item in swings if item.kind == "LOW"]
        if not prior_supports:
            return False
        support = min(prior_supports[-2:] if len(prior_supports) >= 2 else prior_supports)
        retested = any(abs(bar.high - support) <= atr * 0.6 for bar in bars[-3:-1])
        return retested and bars[-1].close < support
    prior_resistances = [item.price for item in swings if item.kind == "HIGH"]
    if not prior_resistances:
        return False
    resistance = max(prior_resistances[-2:] if len(prior_resistances) >= 2 else prior_resistances)
    retested = any(abs(bar.low - resistance) <= atr * 0.6 for bar in bars[-3:-1])
    return retested and bars[-1].close > resistance


def _detect_continuation(bars: list[BacktestBar], side: str, atr: float) -> bool:
    if len(bars) < 3 or atr <= 0:
        return False
    move = bars[-1].close - bars[-3].close
    if side == "SHORT":
        return move < -atr * 0.8 and abs(move) < atr * 2.2
    return move > atr * 0.8 and abs(move) < atr * 2.2


def _candle_score(bar: BacktestBar, side: str, atr: float) -> tuple[float, list[str]]:
    body = abs(bar.close - bar.open)
    upper_wick = bar.high - max(bar.open, bar.close)
    lower_wick = min(bar.open, bar.close) - bar.low
    reasons: list[str] = []
    if side == "SHORT":
        if upper_wick > max(body, 1e-12) * 1.5:
            reasons.append("REVERSAL_WICK_SHORT")
            return -4.0, reasons
        if bar.close < bar.open and body > atr * 0.3:
            return 6.0, reasons
    if side == "LONG":
        if lower_wick > max(body, 1e-12) * 1.5:
            reasons.append("REVERSAL_WICK_LONG")
            return -4.0, reasons
        if bar.close > bar.open and body > atr * 0.3:
            return 6.0, reasons
    return 2.0, reasons


def _swing_trend_score(swings: list[SwingPoint], side: str) -> float:
    highs = [item.price for item in swings if item.kind == "HIGH"]
    lows = [item.price for item in swings if item.kind == "LOW"]
    if side == "SHORT" and len(highs) >= 2 and len(lows) >= 2:
        return 4.0 if highs[-1] < highs[-2] and lows[-1] < lows[-2] else 0.0
    if side == "LONG" and len(highs) >= 2 and len(lows) >= 2:
        return 4.0 if highs[-1] > highs[-2] and lows[-1] > lows[-2] else 0.0
    return 0.0
```

- [ ] **Step 4: Run PA tests**

Run:

```bash
pytest tests/test_pa_structure.py -q
```

Expected: PASS.

---

## Task 3: CCI Momentum Quality Module

**Files:**
- Create: `src/signals/cci_quality.py`
- Test: `tests/test_cci_quality.py`

- [ ] **Step 1: Write failing CCI tests**

Create `tests/test_cci_quality.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/test_cci_quality.py -q
```

Expected: FAIL because module does not exist.

- [ ] **Step 3: Implement minimal CCI module**

Create `src/signals/cci_quality.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Sequence

from src.backtest.engine import BacktestBar


@dataclass(frozen=True)
class CciQualityResult:
    score: float
    tag: str
    latest_cci: float | None
    details: dict[str, float | str | None]


def cci_series(bars: Sequence[BacktestBar], *, period: int = 20) -> list[float]:
    items = list(bars)
    if len(items) < period:
        return []
    typical = [(bar.high + bar.low + bar.close) / 3.0 for bar in items]
    values: list[float] = []
    for idx in range(period - 1, len(typical)):
        window = typical[idx - period + 1 : idx + 1]
        sma = mean(window)
        mean_dev = mean(abs(item - sma) for item in window)
        if mean_dev <= 0:
            values.append(0.0)
        else:
            values.append((typical[idx] - sma) / (0.015 * mean_dev))
    return values


def score_cci_momentum_quality(values: Sequence[float], side: str) -> CciQualityResult:
    series = [float(item) for item in values]
    if not series:
        return CciQualityResult(0.0, "CCI_MISSING", None, {})
    normalized = side.strip().upper()
    latest = series[-1]
    if normalized == "SHORT":
        return _score_short(series, latest)
    if normalized == "LONG":
        return _score_long(series, latest)
    return CciQualityResult(0.0, "CCI_SIDE_UNSUPPORTED", latest, {})


def _score_short(series: list[float], latest: float) -> CciQualityResult:
    if len(series) >= 4 and min(series[-5:]) < -150 and series[-2] > -80 and latest < series[-2]:
        return CciQualityResult(14.0, "CCI_SHORT_SECONDARY_WEAKNESS", latest, {})
    if min(series[-4:]) < -120 and latest > -80:
        return CciQualityResult(0.0, "CCI_SHORT_FAILED_CONTINUATION", latest, {})
    if latest < -150:
        score = max(0.0, min(3.0, 3.0 + (latest + 150.0) * 0.02))
        return CciQualityResult(round(score, 4), "CCI_SHORT_EXHAUSTION", latest, {})
    if -150 <= latest <= -100:
        return CciQualityResult(10.0, "CCI_SHORT_HEALTHY", latest, {})
    if -100 < latest < -50 and len(series) >= 2 and latest < series[-2]:
        return CciQualityResult(7.0, "CCI_SHORT_PULLBACK_WEAKENING", latest, {})
    return CciQualityResult(0.0, "CCI_SHORT_UNSUPPORTED", latest, {})


def _score_long(series: list[float], latest: float) -> CciQualityResult:
    if len(series) >= 4 and max(series[-5:]) > 150 and series[-2] < 80 and latest > series[-2]:
        return CciQualityResult(14.0, "CCI_LONG_SECONDARY_STRENGTH", latest, {})
    if max(series[-4:]) > 120 and latest < 80:
        return CciQualityResult(0.0, "CCI_LONG_FAILED_CONTINUATION", latest, {})
    if latest > 150:
        score = max(0.0, min(3.0, 3.0 - (latest - 150.0) * 0.02))
        return CciQualityResult(round(score, 4), "CCI_LONG_EXHAUSTION", latest, {})
    if 100 <= latest <= 150:
        return CciQualityResult(10.0, "CCI_LONG_HEALTHY", latest, {})
    if 50 < latest < 100 and len(series) >= 2 and latest > series[-2]:
        return CciQualityResult(7.0, "CCI_LONG_PULLBACK_STRENGTHENING", latest, {})
    return CciQualityResult(0.0, "CCI_LONG_UNSUPPORTED", latest, {})
```

- [ ] **Step 4: Run CCI tests**

Run:

```bash
pytest tests/test_cci_quality.py -q
```

Expected: PASS.

---

## Task 4: Config And Weights

**Files:**
- Modify: `src/signals/entry_chain_config.py`
- Modify: `src/signals/entry_chain_scoring.py`
- Create: `configs/entry_chain.dry_run_fib_pa_v1.json`
- Test: `tests/test_entry_chain_config.py`
- Test: `tests/test_dry_run_configs.py`

- [ ] **Step 1: Add failing config tests**

Append to `tests/test_entry_chain_config.py`:

```python
def test_load_fib_pa_fields_from_json(tmp_path):
    path = tmp_path / "entry_chain_fib_pa.json"
    path.write_text(
        '{"use_fib_pa_architecture": true, '
        '"fib_swing_fractal_k": 2, '
        '"fib_swing_min_atr_mult": 1.2, '
        '"fib_extension_exhaustion_mult": 1.618, '
        '"pa_min_direct_score": 6.0, '
        '"fib_min_direct_score": 6.0, '
        '"rr_min_direct_score": 2.0, '
        '"leverage_5x_fib_min": 13.0, '
        '"leverage_5x_pa_min": 9.0, '
        '"leverage_5x_cci_min": 7.0, '
        '"leverage_5x_rr_min": 4.0}',
        encoding="utf-8",
    )

    config = load_entry_chain_config(path)

    assert config.use_fib_pa_architecture is True
    assert config.fib_swing_fractal_k == 2
    assert config.fib_swing_min_atr_mult == 1.2
    assert config.fib_extension_exhaustion_mult == 1.618
    assert config.pa_min_direct_score == 6.0
    assert config.fib_min_direct_score == 6.0
    assert config.rr_min_direct_score == 2.0
    assert config.leverage_5x_fib_min == 13.0
    assert config.leverage_5x_pa_min == 9.0
    assert config.leverage_5x_cci_min == 7.0
    assert config.leverage_5x_rr_min == 4.0
```

Append to `tests/test_dry_run_configs.py`:

```python
def test_fib_pa_dry_run_config_loads_and_is_dry_run_safe():
    config = load_entry_chain_config("configs/entry_chain.dry_run_fib_pa_v1.json")

    assert config.use_fib_pa_architecture is True
    assert config.disable_probe is True
    assert config.blacklist_symbols == ("XRPUSDT", "ZECUSDT")
    assert "XLMUSDT" in config.observation_only_symbols
    assert "TONUSDT" in config.observation_only_symbols
    assert config.dry_run_warmup_15m_bars == 240
```

- [ ] **Step 2: Run config tests to verify they fail**

Run:

```bash
pytest tests/test_entry_chain_config.py::test_load_fib_pa_fields_from_json tests/test_dry_run_configs.py::test_fib_pa_dry_run_config_loads_and_is_dry_run_safe -q
```

Expected: FAIL because fields/config do not exist.

- [ ] **Step 3: Add config fields**

Modify `EntryChainConfig` in `src/signals/entry_chain_config.py`:

```python
    use_fib_pa_architecture: bool = False
    fib_swing_fractal_k: int = 2
    fib_swing_min_atr_mult: float = 1.2
    fib_swing_min_spacing_bars: int = 6
    fib_swing_lookback_15m: int = 50
    fib_swing_lookback_1h: int = 30
    fib_extension_exhaustion_mult: float = 1.618
    fib_level_tolerance_atr_mult: float = 0.5
    pa_min_direct_score: float = 6.0
    fib_min_direct_score: float = 6.0
    rr_min_direct_score: float = 2.0
    leverage_5x_fib_min: float = 13.0
    leverage_5x_pa_min: float = 9.0
    leverage_5x_cci_min: float = 7.0
    leverage_5x_rr_min: float = 4.0
```

- [ ] **Step 4: Add FIB_PA weights**

Modify `src/signals/entry_chain_scoring.py`:

```python
FIB_PA_WEIGHTS = {
    "trend_ema_context": 20.0,
    "flow_cvd_confirmation": 18.0,
    "cci_momentum_quality": 14.0,
    "price_action_structure": 22.0,
    "fibonacci_location": 18.0,
    "risk_reward_geometry": 8.0,
}
```

Then update `dynamic_weights()`:

```python
    if cfg.use_fib_pa_architecture:
        reasons.append("FIB_PA_ARCHITECTURE_WEIGHTS")
        return dict(FIB_PA_WEIGHTS), reasons
```

- [ ] **Step 5: Create fib_pa config**

Create `configs/entry_chain.dry_run_fib_pa_v1.json`:

```json
{
  "direct_threshold": 82.0,
  "probe_threshold": 70.0,
  "watch_threshold": 62.0,
  "daily_max_trades_base": 4,
  "max_symbol_trades_per_day": 1,
  "max_active_symbols": 5,
  "direct_risk_pct": 0.006,
  "probe_risk_pct": 0.0025,
  "max_total_exposure_pct": 1.2,
  "max_same_direction_exposure_pct": 0.9,
  "margin_buffer_pct": 0.30,
  "use_ema_architecture": true,
  "use_fib_pa_architecture": true,
  "ema200_gate_mode": "soft",
  "ema200_buffer_pct": 0.003,
  "ema200_min_bars_stable": 3,
  "ema50_min_for_direct": 0.60,
  "ema50_min_for_probe": 0.40,
  "disable_probe": true,
  "dry_run_symbol_source": "market_cap_rank",
  "dry_run_rank_start": 3,
  "dry_run_rank_end": 25,
  "dry_run_warmup_15m_bars": 240,
  "dry_run_symbols": ["BNBUSDT", "XRPUSDT", "SOLUSDT", "TRXUSDT", "HYPEUSDT", "DOGEUSDT", "ZECUSDT", "XLMUSDT", "ADAUSDT", "XMRUSDT", "LINKUSDT", "CCUSDT", "LABUSDT", "TONUSDT"],
  "blacklist_symbols": ["XRPUSDT", "ZECUSDT"],
  "watch_only_symbols": ["ADAUSDT", "XMRUSDT"],
  "observation_only_symbols": ["XLMUSDT", "TONUSDT"],
  "weak_edge_direct_min_score": 82.0,
  "weak_edge_direct_max_score": 85.0,
  "rolling_symbol_cooldown_enabled": true,
  "rolling_symbol_cooldown_stop_threshold": 2,
  "rolling_symbol_cooldown_window_hours": 48,
  "rolling_symbol_cooldown_hours": 24,
  "long_threshold_offset": 10.0,
  "short_threshold_offset": 0.0,
  "fib_swing_fractal_k": 2,
  "fib_swing_min_atr_mult": 1.2,
  "fib_swing_min_spacing_bars": 6,
  "fib_swing_lookback_15m": 50,
  "fib_swing_lookback_1h": 30,
  "fib_extension_exhaustion_mult": 1.618,
  "fib_level_tolerance_atr_mult": 0.5,
  "pa_min_direct_score": 6.0,
  "fib_min_direct_score": 6.0,
  "rr_min_direct_score": 2.0,
  "leverage_5x_fib_min": 13.0,
  "leverage_5x_pa_min": 9.0,
  "leverage_5x_cci_min": 7.0,
  "leverage_5x_rr_min": 4.0
}
```

- [ ] **Step 6: Run config tests**

Run:

```bash
pytest tests/test_entry_chain_config.py tests/test_dry_run_configs.py -q
```

Expected: PASS.

---

## Task 5: Feature Computation Integration

**Files:**
- Modify: `src/signals/entry_chain_features.py`
- Test: `tests/test_entry_chain_features.py`

- [ ] **Step 1: Add failing feature tests**

Append to `tests/test_entry_chain_features.py`:

```python
from src.signals.entry_chain_features import component_scores


def test_fib_pa_component_scores_are_present_when_enabled():
    bars_15m = [
        BacktestBar("SOLUSDT", 1000 + i * 900, 100 - i * 0.2, 101 - i * 0.2, 99 - i * 0.2, 100 - i * 0.2, 1000)
        for i in range(240)
    ]
    completed = {"15m": bars_15m, "1h": bars_15m[-80:], "30m": bars_15m[-80:], "4h": bars_15m[-80:]}

    scores = component_scores(
        "SHORT",
        completed,
        atr_pct_value=0.01,
        use_ema_architecture=True,
        ema200_gate_mode="soft",
        use_fib_pa_architecture=True,
    )

    assert "trend_ema_context" in scores
    assert "flow_cvd_confirmation" in scores
    assert "cci_momentum_quality" in scores
    assert "price_action_structure" in scores
    assert "fibonacci_location" in scores
    assert "risk_reward_geometry" in scores
```

- [ ] **Step 2: Run feature test to verify it fails**

Run:

```bash
pytest tests/test_entry_chain_features.py::test_fib_pa_component_scores_are_present_when_enabled -q
```

Expected: FAIL because `component_scores()` has no `use_fib_pa_architecture` parameter.

- [ ] **Step 3: Extend component_scores signature**

Modify `component_scores()` signature:

```python
def component_scores(
    side: str,
    completed: Mapping[str, Sequence[BacktestBar]],
    atr_pct_value: float,
    *,
    use_ema_architecture: bool = False,
    ema200_gate_mode: str = "hard",
    use_fib_pa_architecture: bool = False,
) -> dict[str, float]:
```

- [ ] **Step 4: Add opt-in fib_pa scores**

Inside `component_scores()`, after EMA scores are computed:

```python
    if use_fib_pa_architecture:
        fib_pa = fib_pa_component_scores(side, completed, atr_pct_value, scores)
        scores.update(fib_pa)
```

Add helper:

```python
def fib_pa_component_scores(
    side: str,
    completed: Mapping[str, Sequence[BacktestBar]],
    atr_pct_value: float,
    base_scores: Mapping[str, float],
) -> dict[str, float]:
    bars_15m = list(completed.get("15m", []))
    bars_1h = list(completed.get("1h", []))
    if len(bars_15m) < 50:
        return {
            "trend_ema_context": 0.0,
            "flow_cvd_confirmation": 0.0,
            "cci_momentum_quality": 0.0,
            "price_action_structure": 0.0,
            "fibonacci_location": 0.0,
            "risk_reward_geometry": 0.0,
        }
    atr_value = max(0.0, atr_pct_value * bars_15m[-1].close)
    ema_score = (
        float(base_scores.get("ema_200_gate", 0.0)) * 0.40
        + float(base_scores.get("ema_50_quality", 0.0)) * 0.35
        + float(base_scores.get("ema_momentum", 0.0)) * 0.25
    )
    cvd_score = float(base_scores.get("cvd_flow", 0.0))
    pa_swings = detect_fractal_swings(bars_15m, atr=atr_value)
    pa = score_price_action_structure(bars_15m, side, pa_swings, atr=atr_value)
    cci_values = cci_series(bars_15m, period=20)
    cci = score_cci_momentum_quality(cci_values, side)
    fib_1h = latest_fib_from_bars(bars_1h, side, atr_value)
    fib_15m = latest_fib_from_bars(bars_15m, side, atr_value)
    fib = score_fibonacci_location(close=bars_15m[-1].close, side=side, fib_1h=fib_1h, fib_15m=fib_15m, atr=atr_value)
    rr_score = risk_reward_geometry_score(bars_15m[-1].close, atr_value)
    return {
        "trend_ema_context": max(0.0, min(1.0, ema_score)),
        "flow_cvd_confirmation": max(0.0, min(1.0, cvd_score)),
        "cci_momentum_quality": cci.score / 14.0,
        "price_action_structure": pa.score / 22.0,
        "fibonacci_location": fib.score / 18.0,
        "risk_reward_geometry": rr_score,
    }
```

Add imports:

```python
from src.signals.cci_quality import cci_series, score_cci_momentum_quality
from src.signals.fib_location import compute_fib_levels, detect_fractal_swings, score_fibonacci_location
from src.signals.pa_structure import score_price_action_structure
```

Add simple helpers:

```python
def latest_fib_from_bars(bars: Sequence[BacktestBar], side: str, atr: float) -> dict[str, float] | None:
    swings = detect_fractal_swings(bars, atr=atr)
    highs = [item for item in swings if item.kind == "HIGH"]
    lows = [item for item in swings if item.kind == "LOW"]
    if not highs or not lows:
        return None
    trend = "DOWN" if side.strip().upper() == "SHORT" else "UP"
    return compute_fib_levels(max(item.price for item in highs[-3:]), min(item.price for item in lows[-3:]), trend)


def risk_reward_geometry_score(close: float, atr: float) -> float:
    if close <= 0 or atr <= 0:
        return 0.0
    atr_pct = atr / close
    if 0.008 <= atr_pct <= 0.025:
        return 1.0
    if 0.005 <= atr_pct < 0.008:
        return 0.5
    if 0.025 < atr_pct <= 0.03:
        return 0.33
    return 0.0
```

- [ ] **Step 5: Run feature tests**

Run:

```bash
pytest tests/test_entry_chain_features.py -q
```

Expected: PASS.

---

## Task 6: Entry Chain Gate, Minimums, And Leverage

**Files:**
- Modify: `src/signals/entry_chain.py`
- Test: `tests/test_entry_chain.py`

- [ ] **Step 1: Add failing entry-chain tests**

Append to `tests/test_entry_chain.py`:

```python
def test_fib_pa_direct_demotes_when_pa_below_minimum():
    ctx = candidate(
        side="SHORT",
        component_scores={
            "trend_ema_context": 1.0,
            "flow_cvd_confirmation": 1.0,
            "cci_momentum_quality": 1.0,
            "price_action_structure": 0.20,
            "fibonacci_location": 1.0,
            "risk_reward_geometry": 1.0,
        },
    )
    cfg = EntryChainConfig(use_fib_pa_architecture=True, disable_probe=True, direct_threshold=82)

    decision = evaluate_entry_chain(ctx, cfg)

    assert decision.action == "NO_TRADE"
    assert "PRICE_ACTION_STRUCTURE_BELOW_DIRECT_MINIMUM" in decision.reasons


def test_fib_pa_extension_block_rejects_even_high_score():
    ctx = candidate(
        side="SHORT",
        component_scores={
            "trend_ema_context": 1.0,
            "flow_cvd_confirmation": 1.0,
            "cci_momentum_quality": 1.0,
            "price_action_structure": 1.0,
            "fibonacci_location": 0.0,
            "risk_reward_geometry": 1.0,
            "fib_action_cap": 0.0,
        },
    )
    cfg = EntryChainConfig(use_fib_pa_architecture=True, disable_probe=True, direct_threshold=82)

    decision = evaluate_entry_chain(ctx, cfg)

    assert decision.action == "NO_TRADE"
    assert "FIB_EXTENSION_EXHAUSTION_BLOCK" in decision.reasons


def test_fib_pa_5x_requires_fib_pa_cci_rr_minimums():
    ctx = candidate(
        side="SHORT",
        component_scores={
            "trend_ema_context": 1.0,
            "flow_cvd_confirmation": 1.0,
            "cci_momentum_quality": 0.3,
            "price_action_structure": 1.0,
            "fibonacci_location": 1.0,
            "risk_reward_geometry": 1.0,
        },
    )
    cfg = EntryChainConfig(use_fib_pa_architecture=True, direct_threshold=82)

    decision = evaluate_entry_chain(ctx, cfg)

    assert decision.action == "DIRECT"
    assert decision.score >= 90
    assert decision.leverage == 4
    assert "FIB_PA_5X_REQUIREMENTS_FAILED" in decision.reasons
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/test_entry_chain.py::test_fib_pa_direct_demotes_when_pa_below_minimum tests/test_entry_chain.py::test_fib_pa_extension_block_rejects_even_high_score tests/test_entry_chain.py::test_fib_pa_5x_requires_fib_pa_cci_rr_minimums -q
```

Expected: FAIL because integration does not exist.

- [ ] **Step 3: Add fib_pa hard and minimum checks**

In `evaluate_entry_chain()`, after `score` and before `_score_to_action()`:

```python
    if cfg.use_fib_pa_architecture and float(scores.get("fib_action_cap", 1.0)) <= 0.0:
        return _decision(context, cfg, "NO_TRADE", score, weights, points, reasons + ["FIB_EXTENSION_EXHAUSTION_BLOCK"], max_symbol_exposure_pct, ratio)
```

In `_apply_component_minimums()`, add after existing DIRECT checks:

```python
    if cfg.use_fib_pa_architecture and action == "DIRECT":
        fib_pa_checks = {
            "price_action_structure": cfg.pa_min_direct_score / 22.0,
            "fibonacci_location": cfg.fib_min_direct_score / 18.0,
            "risk_reward_geometry": cfg.rr_min_direct_score / 8.0,
        }
        for key, value in fib_pa_checks.items():
            if float(scores.get(key, 0.0)) < value:
                reasons.append(f"{key.upper()}_BELOW_DIRECT_MINIMUM")
                action = "PROBE"
                break
```

- [ ] **Step 4: Add fib_pa 5x leverage rules**

In `_select_leverage()` before the current `score >= 90` branch:

```python
    if config_is_fib_pa(context, reasons) and score >= 90 and action == "DIRECT":
        scores = context.component_scores
        meets_5x = (
            float(scores.get("fibonacci_location", 0.0)) >= 13.0 / 18.0
            and float(scores.get("price_action_structure", 0.0)) >= 9.0 / 22.0
            and float(scores.get("cci_momentum_quality", 0.0)) >= 7.0 / 14.0
            and float(scores.get("risk_reward_geometry", 0.0)) >= 4.0 / 8.0
        )
        if meets_5x:
            return 5
        reasons.append("FIB_PA_5X_REQUIREMENTS_FAILED")
        return 4
```

Because `_select_leverage()` currently receives no config, prefer changing its signature:

```python
def _select_leverage(action: str, score: float, context: EntryChainContext, cfg: EntryChainConfig, reasons: list[str]) -> int:
```

Then update all call sites in `entry_chain.py`.

- [ ] **Step 5: Run entry-chain tests**

Run:

```bash
pytest tests/test_entry_chain.py -q
```

Expected: PASS.

---

## Task 7: Live Dry-Run Wiring

**Files:**
- Modify: `scripts/run_live_dry_run.py`
- Test: `tests/test_live_dry_run.py`

- [ ] **Step 1: Add failing dry-run test for fib_pa score detail**

Append to `tests/test_live_dry_run.py`:

```python
def test_live_dry_run_fib_pa_config_emits_location_scores(tmp_path):
    subprocess.run(
        [
            sys.executable,
            "scripts/run_live_dry_run.py",
            "--config",
            "configs/entry_chain.dry_run_fib_pa_v1.json",
            "--target-tier",
            "aggressive",
            "--market-data-source",
            "synthetic",
            "--once",
            "--output-dir",
            str(tmp_path),
            "--symbols",
            "SOLUSDT",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    row = json.loads((tmp_path / "decisions.jsonl").read_text(encoding="utf-8").splitlines()[0])

    assert "price_action_structure" in row["score_detail"]["scores"]
    assert "fibonacci_location" in row["score_detail"]["scores"]
    assert "cci_momentum_quality" in row["score_detail"]["scores"]
    assert row["orders_submitted"] if False else True
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_live_dry_run.py::test_live_dry_run_fib_pa_config_emits_location_scores -q
```

Expected: FAIL because `build_context()` does not pass `use_fib_pa_architecture`.

- [ ] **Step 3: Pass config flag into feature computation**

In `scripts/run_live_dry_run.py`, locate calls to `component_scores()` inside synthetic/public context builders. Add:

```python
use_fib_pa_architecture=config.use_fib_pa_architecture,
```

- [ ] **Step 4: Run dry-run tests**

Run:

```bash
pytest tests/test_live_dry_run.py -q
```

Expected: PASS.

---

## Task 8: Documentation And Review Artifact

**Files:**
- Create: `docs/superpowers/reports/2026-06-26-fib-pa-refactor-implementation-notes.md`

- [ ] **Step 1: Write implementation notes**

Create `docs/superpowers/reports/2026-06-26-fib-pa-refactor-implementation-notes.md`:

```markdown
# Fib PA Refactor Implementation Notes

## Scope

Implemented opt-in `fib_pa_v1` dry-run scoring architecture:

- EMA trend context
- CVD confirmation
- CCI momentum quality
- Price Action structure
- Fibonacci location
- Risk/reward geometry

## Safety

- `src/api/binance_client.py` unchanged.
- Dry-run still reports `orders_submitted=0`.
- Live exchange mutation test passes.

## Key Behavioral Changes

- Fib 1.618 extension exhaustion can hard-block entries.
- DIRECT requires minimum PA/Fib/RR scores.
- 5x requires stronger Fib/PA/CCI/RR conditions.
- MACD/BOLL responsibilities are no longer used in entry scoring.

## Claude Review Questions

1. Are the swing detection parameters too strict for 15m crypto?
2. Should 1h Fib fully override 15m Fib for hard blocks?
3. Should CCI exhaustion be a cap instead of a score?
4. Is the 5x gating too conservative?
5. Should BTC regime filtering be implemented before or after dry-run validation?
```

- [ ] **Step 2: Verify report exists**

Run:

```bash
test -f docs/superpowers/reports/2026-06-26-fib-pa-refactor-implementation-notes.md
```

Expected: exit code 0.

---

## Task 9: Full Verification

**Files:**
- No new files.

- [ ] **Step 1: Run full focused test suite**

Run:

```bash
pytest tests/test_fib_location.py tests/test_pa_structure.py tests/test_cci_quality.py tests/test_entry_chain.py tests/test_entry_chain_features.py tests/test_entry_chain_config.py tests/test_dry_run_configs.py tests/test_live_dry_run.py -q
```

Expected: all tests pass.

- [ ] **Step 2: Run dry-run healthcheck**

Run:

```bash
python scripts/vps_dry_run_healthcheck.py --config configs/entry_chain.dry_run_fib_pa_v1.json
```

Expected:

```json
{
  "status": "ok",
  "dry_run_safe": true,
  "forbidden_tokens": []
}
```

- [ ] **Step 3: Verify no exchange mutation calls**

Run:

```bash
pytest tests/test_live_dry_run.py::test_live_dry_run_source_has_no_exchange_mutation_calls -q
```

Expected: PASS.

- [ ] **Step 4: Confirm Binance client untouched**

Run:

```bash
git diff -- src/api/binance_client.py
```

Expected: no output.

---

## Task 10: Backtest / Dry-Run Ablation Handoff

**Files:**
- Create: `docs/superpowers/reports/2026-06-26-fib-pa-ablation-template.md`

- [ ] **Step 1: Create ablation template**

Create `docs/superpowers/reports/2026-06-26-fib-pa-ablation-template.md`:

```markdown
# Fib PA Ablation Template

## Experiments

| Experiment | Config | Purpose |
|---|---|---|
| A | current highest-win config | Baseline |
| B | EMA+CVD+CCI | CCI only |
| C | EMA+CVD+CCI+PA | PA contribution |
| D | EMA+CVD+CCI+PA+Fib | Full architecture |
| E | D + 5x constraints | Leverage protection |

## Required Metrics

- win_rate
- profit_factor
- realized_pnl
- max_drawdown
- trade_count
- initial_stop_rate
- breakeven_stop_rate
- tp3_rate
- avg_initial_stop_pnl
- avg_tp_path_pnl
- 5x_pnl_contribution
- score_90plus_win_rate
- fib_optimal_win_rate
- pa_structure_win_rate

## Acceptance Targets

- score_90plus_win_rate > 60%
- 5x_pnl_contribution > 0
- profit_factor > 1.2
- initial_stop_rate < 40%
```

- [ ] **Step 2: Verify template exists**

Run:

```bash
test -f docs/superpowers/reports/2026-06-26-fib-pa-ablation-template.md
```

Expected: exit code 0.

---

## Execution Notes

This plan is intentionally bold but still staged:

1. Implement modules with isolated tests first.
2. Add config and weights behind `use_fib_pa_architecture`.
3. Wire into dry-run only.
4. Verify safety invariants.
5. Run ablations before replacing the VPS service config.

The current dry-run mode means code changes do not place real orders, but the safety invariant remains mandatory: `orders_submitted=0` and no exchange mutation calls.

