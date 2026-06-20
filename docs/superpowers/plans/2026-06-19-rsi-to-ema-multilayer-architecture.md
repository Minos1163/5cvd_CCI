# RSI To EMA Multilayer Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace RSI as a main strategy input with a three-layer EMA architecture: EMA200 direction gate, EMA50 trend-quality score, and EMA9/21 momentum-resonance score.

**Architecture:** Keep RSI code as a legacy/reference indicator during the transition, but remove it from the standard strategy contract, default strategy config, entry-chain scoring, and dry-run EMA profiles. Add EMA as a standard indicator result and then wire EMA-derived scores into entry-chain feature scoring for controlled A/B/C/D ablation backtests. No live execution, Binance client, TP/SL, or position-sizing behavior changes are included in this plan.

**Tech Stack:** Python dataclasses, existing indicator/result contracts, existing entry-chain scoring modules, JSON/YAML configs, pytest, offline backtest runner.

---

## Trading Hypothesis

RSI and CCI are both oscillator-style momentum filters. Keeping both gives repeated votes to a similar signal family and can reject strong trend-continuation entries as "overheated." EMA adds a lower-correlation trend-following signal:

- EMA200 answers whether the trade direction is structurally legal.
- EMA50 answers whether trend quality is good enough.
- EMA9/21 answers whether short-term momentum aligns with the planned side.

Expected regime:

- Helps most in directional 15m/30m/1H trend continuation.
- Helps avoid countertrend probes during established EMA200 trends.

Failure mode:

- EMA can lag fast reversals.
- EMA200 hard gate may reject early reversal trades.
- Range-bound markets can whipsaw around EMA200 unless a buffer and stability window are enforced.

Verification:

- Use closed bars only.
- Run ablation experiments A/B/C/D on the same latest-30D data before interpreting performance.
- Do not tune TP/SL, leverage, or position size during the first EMA replacement test.

## Success Criteria

- `src/api/binance_client.py` remains untouched.
- EMA indicator functions are deterministic and use only completed historical bars supplied to them.
- Standard indicator results include `EMA` and no longer include `RSI` for the main strategy contract.
- Strategy config replaces `indicators.rsi` and `entry.rsi_reclaim` with explicit EMA settings.
- Entry-chain scoring supports EMA components without breaking existing non-EMA profiles.
- New EMA dry-run configs exist for soft and hard EMA200 modes.
- Offline backtest can run:
  - Experiment A: current entry-chain baseline.
  - Experiment B: RSI removed / no EMA, weight redistribution.
  - Experiment C: EMA soft filter.
  - Experiment D: EMA hard gate.
- A report compares trade count, return, win rate, profit factor, max drawdown, Sharpe, Sortino, expectancy, direct/probe split, and symbol contribution.

## File Structure

- Create: `src/indicators/ema.py`  
  Pure EMA sequence, latest EMA, normalized slope, bars-since-cross helpers.
- Create: `tests/test_ema_indicator.py`  
  Unit tests for EMA math, warmup, slope, cross stability, and no future data.
- Modify: `src/core/models.py`  
  Add EMA fields to `IndicatorSnapshot`.
- Modify: `src/data/data_contract.py`  
  Add `EMA` required output fields.
- Modify: `tests/test_data_contract.py`  
  Assert the EMA contract fields.
- Modify: `src/indicators/indicator_spec.py`  
  Replace RSI in the main indicator contract with EMA.
- Modify: `tests/test_indicator_spec_rules.py`  
  Update indicator names, responsibilities, conflict priority, timeframe maps, and usage checks.
- Modify: `src/indicators/indicator_engine.py`  
  Compute EMA result and stop emitting RSI from `compute_indicator_results()`.
- Modify: `tests/test_indicator_engine.py`  
  Expect EMA standard result and validate its fields.
- Create: `src/signals/ema_scorer.py`  
  Three-layer EMA scoring primitives for entry-chain use.
- Create: `tests/test_ema_scorer.py`  
  Cover EMA200 hard/soft direction behavior, EMA50 quality, EMA9/21 momentum, and leverage-state classification.
- Modify: `src/signals/entry_chain_config.py`  
  Add EMA configuration fields while preserving default backward-compatible non-EMA behavior unless enabled.
- Modify: `src/signals/entry_chain_scoring.py`  
  Add EMA component support and EMA-specific weight profiles.
- Modify: `src/signals/entry_chain_features.py`  
  Add EMA-derived component scores from completed bars.
- Modify: `scripts/run_offline_backtest.py`  
  Allow selecting EMA experiment profiles through config files already passed by `--entry-chain-config`.
- Create: `configs/entry_chain.dry_run_no_rsi.json`
- Create: `configs/entry_chain.dry_run_ema_soft.json`
- Create: `configs/entry_chain.dry_run_ema_hard.json`
- Modify: `configs/strategy.yaml`
- Modify: `src/config/config_schema.py`
- Modify: `tests/test_config_schema.py`
- Modify docs:
  - `docs/03_indicator_spec.md`
  - `docs/09_data_contract.md`
  - `docs/04_multi_timeframe_rules.md`
  - `docs/superpowers/reports/2026-06-19-claude-live-entry-chain-risk-review.md`
- Create: `docs/superpowers/reports/2026-06-19-rsi-to-ema-ablation-backtest-report.md`

## Task 1: Add EMA Indicator Primitive

**Files:**
- Create: `src/indicators/ema.py`
- Create: `tests/test_ema_indicator.py`

- [ ] **Step 1: Write failing EMA primitive tests**

Create `tests/test_ema_indicator.py`:

```python
from src.indicators.ema import bars_since_cross, ema, ema_latest, normalized_ema_slope


def test_ema_returns_none_until_period_is_available():
    assert ema([1, 2, 3], period=5) == []
    assert ema_latest([1, 2, 3], period=5) is None


def test_ema_uses_sma_seed_and_standard_multiplier():
    values = [10, 11, 12, 13, 14, 15]
    result = ema(values, period=3)
    assert result[0] == 11.0
    assert round(result[-1], 6) == 14.03125
    assert ema_latest(values, period=3) == result[-1]


def test_normalized_ema_slope_uses_completed_series_only():
    series = [100, 101, 102, 103, 104, 105]
    assert round(normalized_ema_slope(series, lookback=5), 6) == 0.05
    assert normalized_ema_slope([100, 101], lookback=5) == 0.0


def test_bars_since_cross_detects_latest_side_stability():
    closes = [99, 100, 101, 102, 103]
    ema_values = [100, 100, 100, 100, 100]
    assert bars_since_cross(closes, ema_values) == 3

    choppy_closes = [99, 101, 99, 101]
    choppy_ema = [100, 100, 100, 100]
    assert bars_since_cross(choppy_closes, choppy_ema) == 0
```

- [ ] **Step 2: Run tests to confirm failure**

Run:

```powershell
pytest tests/test_ema_indicator.py -q
```

Expected: import failure because `src.indicators.ema` does not exist.

- [ ] **Step 3: Implement EMA primitive**

Create `src/indicators/ema.py`:

```python
from __future__ import annotations


def ema(values: list[float], period: int) -> list[float]:
    if period <= 0:
        raise ValueError("period must be positive")
    if len(values) < period:
        return []
    seed = sum(values[:period]) / period
    multiplier = 2 / (period + 1)
    results = [seed]
    previous = seed
    for value in values[period:]:
        previous = (float(value) - previous) * multiplier + previous
        results.append(previous)
    return results


def ema_latest(values: list[float], period: int) -> float | None:
    results = ema(values, period)
    return results[-1] if results else None


def normalized_ema_slope(ema_values: list[float], lookback: int = 5) -> float:
    if lookback <= 0:
        raise ValueError("lookback must be positive")
    if len(ema_values) <= lookback:
        return 0.0
    current = float(ema_values[-1])
    prior = float(ema_values[-1 - lookback])
    if prior == 0:
        return 0.0
    return (current - prior) / prior


def bars_since_cross(values: list[float], reference_values: list[float]) -> int | None:
    length = min(len(values), len(reference_values))
    if length < 2:
        return None
    pairs = list(zip(values[-length:], reference_values[-length:]))
    current_side = _side(pairs[-1][0], pairs[-1][1])
    if current_side == 0:
        return 0
    count = 0
    for value, reference in reversed(pairs[:-1]):
        if _side(value, reference) != current_side:
            return count
        count += 1
    return count


def _side(value: float, reference: float) -> int:
    if value > reference:
        return 1
    if value < reference:
        return -1
    return 0
```

- [ ] **Step 4: Verify EMA primitive**

Run:

```powershell
pytest tests/test_ema_indicator.py -q
```

Expected: all tests pass.

## Task 2: Add EMA To Indicator And Data Contracts

**Files:**
- Modify: `src/core/models.py`
- Modify: `src/data/data_contract.py`
- Modify: `src/indicators/indicator_spec.py`
- Modify: `tests/test_data_contract.py`
- Modify: `tests/test_indicator_spec_rules.py`

- [ ] **Step 1: Update contract tests for EMA replacing RSI**

Change `tests/test_indicator_spec_rules.py` expectations:

```python
def test_default_indicator_params_match_doc():
    assert DEFAULT_INDICATOR_PARAMS["MACD"] == {"fast": 12, "slow": 26, "signal": 9}
    assert DEFAULT_INDICATOR_PARAMS["CCI"] == {"period": 20}
    assert DEFAULT_INDICATOR_PARAMS["BOLL"] == {"period": 20, "std": 2.0}
    assert DEFAULT_INDICATOR_PARAMS["EMA"] == {"fast": 9, "slow": 21, "trend": 50, "gate": 200, "slope_lookback": 5}
    assert DEFAULT_INDICATOR_PARAMS["ATR"] == {"period": 14}
    assert DEFAULT_INDICATOR_PARAMS["CVD"] == {}


def test_indicator_names_responsibilities_and_contract_fields_match_doc():
    assert INDICATOR_NAMES == ("MACD", "CCI", "BOLL", "EMA", "CVD", "ATR")
    assert INDICATOR_RESPONSIBILITIES == {
        "MACD": "trend_momentum",
        "CCI": "strength_deviation_recovery",
        "BOLL": "volatility_structure",
        "EMA": "trend_direction_quality_momentum",
        "CVD": "active_buy_sell_pressure",
        "ATR": "volatility_stop_position_risk",
    }
```

Change conflict priority and timeframe map assertions:

```python
assert INDICATOR_CONFLICT_PRIORITY == (
    "data_quality",
    "cvd_divergence",
    "ema200_direction_gate",
    "macd_trend_direction",
    "ema50_trend_quality",
    "cci_strength",
    "boll_structure",
    "ema9_21_momentum",
    "atr_risk",
)
assert TIMEFRAME_INDICATOR_MAP["4h"] == ("EMA", "MACD", "BOLL", "CCI")
assert TIMEFRAME_INDICATOR_MAP["1h"] == ("EMA", "MACD", "CCI", "CVD")
assert TIMEFRAME_INDICATOR_MAP["30m"] == ("EMA", "MACD", "BOLL", "CCI", "CVD")
assert TIMEFRAME_INDICATOR_MAP["15m"] == ("EMA", "MACD", "CVD", "BOLL")
```

Replace RSI usage check with EMA:

```python
ok, reason = validate_indicator_usage("EMA", "trend_quality")
assert ok is True
assert reason == "EMA allowed for trend_quality"
assert "countertrend_direct" in INDICATOR_FORBIDDEN_USAGES["EMA"]
```

- [ ] **Step 2: Update data contract test**

Append to `test_indicator_contract_fields_and_required_outputs_match_doc()` in `tests/test_data_contract.py`:

```python
assert INDICATOR_REQUIRED_OUTPUTS["EMA"] == [
    "ema_9",
    "ema_21",
    "ema_50",
    "ema_200",
    "ema50_slope",
    "ema9_21_gap",
    "bars_since_ema50_cross",
    "bars_since_ema200_cross",
]
```

- [ ] **Step 3: Run tests to confirm failures**

Run:

```powershell
pytest tests/test_indicator_spec_rules.py tests/test_data_contract.py -q
```

Expected: failures showing old RSI contract is still encoded.

- [ ] **Step 4: Update `IndicatorSnapshot`**

Modify `src/core/models.py`:

```python
@dataclass(frozen=True)
class IndicatorSnapshot:
    symbol: str
    timeframe: str
    close_time: int
    macd: float | None = None
    macd_signal: float | None = None
    macd_hist: float | None = None
    cci: float | None = None
    rsi: float | None = None
    ema_9: float | None = None
    ema_21: float | None = None
    ema_50: float | None = None
    ema_200: float | None = None
    ema50_slope: float | None = None
    ema9_21_gap: float | None = None
    bars_since_ema50_cross: int | None = None
    bars_since_ema200_cross: int | None = None
    boll_mid: float | None = None
    boll_upper: float | None = None
    boll_lower: float | None = None
    atr: float | None = None
    cvd: float | None = None
    cvd_delta: float | None = None
```

Keep `rsi` temporarily for legacy reads and ablation. Do not emit RSI in the main standard result after Task 3.

- [ ] **Step 5: Update data contract constants**

Modify `src/data/data_contract.py`:

```python
INDICATOR_REQUIRED_OUTPUTS = {
    "MACD": ["macd_line", "signal_line", "histogram", "histogram_slope", "cross_state"],
    "EMA": [
        "ema_9",
        "ema_21",
        "ema_50",
        "ema_200",
        "ema50_slope",
        "ema9_21_gap",
        "bars_since_ema50_cross",
        "bars_since_ema200_cross",
    ],
    "CCI": ["cci", "cci_slope", "extreme_flag", "recovery_flag"],
    "BOLL": [
        "middle_band",
        "upper_band",
        "lower_band",
        "band_width",
        "band_expansion_flag",
        "band_contraction_flag",
        "price_position",
    ],
    "CVD": ["cvd", "cvd_delta", "cvd_slope", "cvd_divergence_flag", "buy_pressure", "sell_pressure"],
    "ATR": ["atr", "atr_pct", "volatility_state"],
}
```

- [ ] **Step 6: Update indicator spec constants**

Modify `src/indicators/indicator_spec.py`:

```python
DEFAULT_INDICATOR_PARAMS = {
    "MACD": {"fast": 12, "slow": 26, "signal": 9},
    "CCI": {"period": 20},
    "BOLL": {"period": 20, "std": 2.0},
    "EMA": {"fast": 9, "slow": 21, "trend": 50, "gate": 200, "slope_lookback": 5},
    "CVD": {},
    "ATR": {"period": 14},
}

INDICATOR_NAMES = ("MACD", "CCI", "BOLL", "EMA", "CVD", "ATR")
INDICATOR_RESPONSIBILITIES = {
    "MACD": "trend_momentum",
    "CCI": "strength_deviation_recovery",
    "BOLL": "volatility_structure",
    "EMA": "trend_direction_quality_momentum",
    "CVD": "active_buy_sell_pressure",
    "ATR": "volatility_stop_position_risk",
}
INDICATOR_CONFLICT_PRIORITY = (
    "data_quality",
    "cvd_divergence",
    "ema200_direction_gate",
    "macd_trend_direction",
    "ema50_trend_quality",
    "cci_strength",
    "boll_structure",
    "ema9_21_momentum",
    "atr_risk",
)
TIMEFRAME_INDICATOR_MAP = {
    "4h": ("EMA", "MACD", "BOLL", "CCI"),
    "1h": ("EMA", "MACD", "CCI", "CVD"),
    "30m": ("EMA", "MACD", "BOLL", "CCI", "CVD"),
    "15m": ("EMA", "MACD", "CVD", "BOLL"),
}
INDICATOR_FORBIDDEN_USAGES = {
    "MACD": ("sole_entry", "position_size", "unfinished_bar_final", "execution_reinterpretation"),
    "CCI": ("sole_direction", "risk_control", "only_trend_proof"),
    "BOLL": ("sole_direction", "position_size", "replace_trend_logic"),
    "EMA": ("sole_entry", "position_size", "countertrend_direct", "unfinished_bar_final"),
    "CVD": ("sole_direction", "replace_price_structure", "force_signal_without_data", "execution_priority"),
    "ATR": ("direction", "long_short_signal", "replace_trend", "non_risk_module_mixing"),
}
```

Keep `classify_rsi()` for legacy compatibility in this task. Remove it only after all old docs/tests stop referencing it.

- [ ] **Step 7: Verify contracts**

Run:

```powershell
pytest tests/test_indicator_spec_rules.py tests/test_data_contract.py -q
```

Expected: all updated contract tests pass.

## Task 3: Emit EMA Standard Indicator Result

**Files:**
- Modify: `src/indicators/indicator_engine.py`
- Modify: `tests/test_indicator_engine.py`

- [ ] **Step 1: Update engine tests for EMA output**

Modify `tests/test_indicator_engine.py`:

```python
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
```

Use at least `220` candles for EMA200 tests:

```python
def test_compute_indicator_snapshot_populates_fields():
    snapshot = compute_indicator_snapshot(make_candles(220))
    assert snapshot.symbol == "BTCUSDT"
    assert snapshot.timeframe == "15m"
    assert snapshot.macd is not None
    assert snapshot.ema_9 is not None
    assert snapshot.ema_21 is not None
    assert snapshot.ema_50 is not None
    assert snapshot.ema_200 is not None
    assert snapshot.ema50_slope is not None
    assert snapshot.ema9_21_gap is not None
    assert snapshot.cci is not None
    assert snapshot.boll_mid is not None
    assert snapshot.atr is not None
    assert snapshot.cvd == 4400.0
    assert snapshot.cvd_delta == 20.0
```

Update standard result expectation:

```python
def test_compute_indicator_results_returns_standard_contracts():
    results = compute_indicator_results(make_market_candles(220))
    by_name = {item.name: item for item in results}

    assert set(by_name) == {"MACD", "CCI", "BOLL", "EMA", "CVD", "ATR"}
    assert set(by_name["EMA"].value) >= {
        "ema_9",
        "ema_21",
        "ema_50",
        "ema_200",
        "ema50_slope",
        "ema9_21_gap",
        "bars_since_ema50_cross",
        "bars_since_ema200_cross",
    }
```

- [ ] **Step 2: Run tests to confirm failures**

Run:

```powershell
pytest tests/test_indicator_engine.py -q
```

Expected: failures because EMA fields/result are not computed yet.

- [ ] **Step 3: Wire EMA computation**

Modify imports in `src/indicators/indicator_engine.py`:

```python
from src.indicators.ema import bars_since_cross, ema, ema_latest, normalized_ema_slope
```

Inside `compute_indicator_snapshot()` after `closes`:

```python
ema_9_series = ema(closes, 9)
ema_21_series = ema(closes, 21)
ema_50_series = ema(closes, 50)
ema_200_series = ema(closes, 200)
ema_9 = ema_9_series[-1] if ema_9_series else None
ema_21 = ema_21_series[-1] if ema_21_series else None
ema_50 = ema_50_series[-1] if ema_50_series else None
ema_200 = ema_200_series[-1] if ema_200_series else None
```

Set snapshot fields:

```python
ema_9=ema_9,
ema_21=ema_21,
ema_50=ema_50,
ema_200=ema_200,
ema50_slope=normalized_ema_slope(ema_50_series, 5) if ema_50_series else None,
ema9_21_gap=(ema_9 - ema_21) / ema_21 if ema_9 is not None and ema_21 not in (None, 0) else None,
bars_since_ema50_cross=bars_since_cross(closes[-len(ema_50_series):], ema_50_series) if ema_50_series else None,
bars_since_ema200_cross=bars_since_cross(closes[-len(ema_200_series):], ema_200_series) if ema_200_series else None,
```

Replace `_build_rsi_result(...)` in `compute_indicator_results()` with `_build_ema_result(...)`.

- [ ] **Step 4: Add EMA result builder**

Add to `src/indicators/indicator_engine.py`:

```python
def _build_ema_result(snapshot: IndicatorSnapshot, closes: list[float], quality_flag: bool | str) -> IndicatorResult:
    close = closes[-1]
    ema_200 = snapshot.ema_200
    ema_50 = snapshot.ema_50
    ema_9 = snapshot.ema_9
    ema_21 = snapshot.ema_21
    if ema_200 is not None and close > ema_200:
        gate_state = "long_allowed"
    elif ema_200 is not None and close < ema_200:
        gate_state = "short_allowed"
    else:
        gate_state = "neutral"
    if ema_9 is not None and ema_21 is not None and ema_9 > ema_21:
        momentum_state = "bullish"
    elif ema_9 is not None and ema_21 is not None and ema_9 < ema_21:
        momentum_state = "bearish"
    else:
        momentum_state = "neutral"
    slope = snapshot.ema50_slope or 0.0
    trend = "UP" if gate_state == "long_allowed" and slope >= 0 else "DOWN" if gate_state == "short_allowed" and slope <= 0 else "NEUTRAL"
    signal = "BULLISH" if trend == "UP" and momentum_state == "bullish" else "BEARISH" if trend == "DOWN" and momentum_state == "bearish" else "NEUTRAL"
    value = {
        "ema_9": snapshot.ema_9,
        "ema_21": snapshot.ema_21,
        "ema_50": snapshot.ema_50,
        "ema_200": snapshot.ema_200,
        "ema50_slope": snapshot.ema50_slope,
        "ema9_21_gap": snapshot.ema9_21_gap,
        "bars_since_ema50_cross": snapshot.bars_since_ema50_cross,
        "bars_since_ema200_cross": snapshot.bars_since_ema200_cross,
        "gate_state": gate_state,
        "momentum_state": momentum_state,
    }
    return _base_result(snapshot, "EMA", value, signal, trend, min(abs(slope) * 100, 1.0), quality_flag)
```

- [ ] **Step 5: Verify indicator engine**

Run:

```powershell
pytest tests/test_ema_indicator.py tests/test_indicator_engine.py tests/test_indicator_spec_rules.py tests/test_data_contract.py -q
```

Expected: all tests pass.

## Task 4: Add EMA Scorer For Entry Chain

**Files:**
- Create: `src/signals/ema_scorer.py`
- Create: `tests/test_ema_scorer.py`

- [ ] **Step 1: Write EMA scorer tests**

Create `tests/test_ema_scorer.py`:

```python
from src.signals.ema_scorer import (
    EmaContext,
    ema_direction_gate,
    ema_trend_state,
    score_ema50_quality,
    score_ema_momentum,
)


def test_ema200_hard_gate_rejects_countertrend_long():
    context = EmaContext(
        close=99,
        ema_9=101,
        ema_21=100,
        ema_50=100,
        ema_200=100,
        ema50_slope=0.001,
        ema9_21_gap=0.01,
        bars_since_ema50_cross=4,
        bars_since_ema200_cross=4,
    )

    assert ema_direction_gate("LONG", context, mode="hard").allowed is False
    assert ema_direction_gate("LONG", context, mode="hard").reason == "EMA200_COUNTER_DIRECTION"


def test_ema200_soft_gate_returns_penalty_not_rejection():
    context = EmaContext(99, 101, 100, 100, 100, 0.001, 0.01, 4, 4)

    decision = ema_direction_gate("LONG", context, mode="soft")

    assert decision.allowed is True
    assert decision.penalty == -0.20


def test_score_ema50_quality_rewards_aligned_slope_and_stability():
    context = EmaContext(105, 104, 103, 100, 90, 0.004, 0.01, 5, 20)

    assert score_ema50_quality("LONG", context) == 0.95


def test_score_ema50_quality_penalizes_fresh_cross():
    context = EmaContext(105, 104, 103, 100, 90, 0.004, 0.01, 1, 20)

    assert score_ema50_quality("LONG", context) == 0.75


def test_score_ema_momentum_uses_fast_slow_alignment_and_gap():
    context = EmaContext(105, 104, 103, 100, 90, 0.002, 0.01, 5, 20)

    assert score_ema_momentum("LONG", context) == 0.8
    assert score_ema_momentum("SHORT", context) == 0.0


def test_ema_trend_state_maps_to_leverage_tiers():
    strong = EmaContext(105, 104, 103, 100, 90, 0.004, 0.01, 5, 20)
    mild = EmaContext(105, 104, 103, 100, 90, 0.0015, 0.01, 5, 20)
    flat = EmaContext(105, 104, 103, 100, 90, 0.0001, 0.01, 5, 20)

    assert ema_trend_state("LONG", strong) == "STRONG_TREND"
    assert ema_trend_state("LONG", mild) == "MILD_TREND"
    assert ema_trend_state("LONG", flat) == "FLAT_OR_TRANSITION"
```

- [ ] **Step 2: Run tests to confirm failure**

Run:

```powershell
pytest tests/test_ema_scorer.py -q
```

Expected: import failure because `src.signals.ema_scorer` does not exist.

- [ ] **Step 3: Implement EMA scorer**

Create `src/signals/ema_scorer.py`:

```python
from __future__ import annotations

from dataclasses import dataclass


SLOPE_STEEP = 0.003
SLOPE_MILD = 0.001


@dataclass(frozen=True)
class EmaContext:
    close: float
    ema_9: float | None
    ema_21: float | None
    ema_50: float | None
    ema_200: float | None
    ema50_slope: float
    ema9_21_gap: float
    bars_since_ema50_cross: int | None
    bars_since_ema200_cross: int | None


@dataclass(frozen=True)
class EmaGateDecision:
    allowed: bool
    reason: str
    penalty: float = 0.0


def ema_direction_gate(side: str, context: EmaContext, *, mode: str = "hard", buffer_pct: float = 0.003, min_bars_stable: int = 3) -> EmaGateDecision:
    normalized_side = side.strip().upper()
    if context.ema_200 is None:
        return EmaGateDecision(False, "EMA200_UNAVAILABLE")
    upper = context.ema_200 * (1 + buffer_pct)
    lower = context.ema_200 * (1 - buffer_pct)
    in_buffer = lower <= context.close <= upper
    unstable = context.bars_since_ema200_cross is not None and context.bars_since_ema200_cross < min_bars_stable
    counter = (normalized_side == "LONG" and context.close < lower) or (normalized_side == "SHORT" and context.close > upper)
    if in_buffer or unstable or counter:
        if mode == "soft":
            return EmaGateDecision(True, "EMA200_SOFT_PENALTY", -0.20)
        return EmaGateDecision(False, "EMA200_COUNTER_DIRECTION" if counter else "EMA200_UNSTABLE")
    return EmaGateDecision(True, "PASS")


def score_ema50_quality(side: str, context: EmaContext) -> float:
    if context.ema_50 is None:
        return 0.0
    normalized_side = side.strip().upper()
    score = 0.0
    if normalized_side == "LONG":
        score += 0.80 if context.close > context.ema_50 else 0.20
        if context.ema50_slope > SLOPE_STEEP:
            score += 0.15
        elif context.ema50_slope > SLOPE_MILD:
            score += 0.07
        elif context.ema50_slope < -SLOPE_MILD:
            score -= 0.15
    elif normalized_side == "SHORT":
        score += 0.80 if context.close < context.ema_50 else 0.20
        if context.ema50_slope < -SLOPE_STEEP:
            score += 0.15
        elif context.ema50_slope < -SLOPE_MILD:
            score += 0.07
        elif context.ema50_slope > SLOPE_MILD:
            score -= 0.15
    if context.bars_since_ema50_cross is not None and context.bars_since_ema50_cross <= 2:
        score -= 0.20
    return round(max(0.0, min(1.0, score)), 4)


def score_ema_momentum(side: str, context: EmaContext) -> float:
    if context.ema_9 is None or context.ema_21 is None:
        return 0.0
    normalized_side = side.strip().upper()
    long_aligned = context.ema_9 > context.ema_21
    short_aligned = context.ema_9 < context.ema_21
    score = 0.0
    if normalized_side == "LONG" and long_aligned:
        score += 0.70
    elif normalized_side == "SHORT" and short_aligned:
        score += 0.70
    else:
        score -= 0.50
    if abs(context.ema9_21_gap) > 0.005:
        score += 0.10
    return round(max(0.0, min(1.0, score)), 4)


def ema_trend_state(side: str, context: EmaContext) -> str:
    quality = score_ema50_quality(side, context)
    momentum = score_ema_momentum(side, context)
    if quality >= 0.90 and momentum >= 0.80 and abs(context.ema50_slope) >= SLOPE_STEEP:
        return "STRONG_TREND"
    if quality >= 0.70 and momentum >= 0.70 and abs(context.ema50_slope) >= SLOPE_MILD:
        return "MILD_TREND"
    return "FLAT_OR_TRANSITION"
```

- [ ] **Step 4: Verify EMA scorer**

Run:

```powershell
pytest tests/test_ema_scorer.py -q
```

Expected: all EMA scorer tests pass.

## Task 5: Wire EMA Scores Into Entry-Chain Features

**Files:**
- Modify: `src/signals/entry_chain_config.py`
- Modify: `src/signals/entry_chain_scoring.py`
- Modify: `src/signals/entry_chain_features.py`
- Modify: `tests/test_entry_chain_scoring.py`
- Modify: `tests/test_entry_chain_features.py`

- [ ] **Step 1: Add tests for EMA scoring components**

Append to `tests/test_entry_chain_scoring.py`:

```python
def test_ema_weight_profile_replaces_trigger_timing_component():
    config = EntryChainConfig(use_ema_architecture=True)
    weights, reasons = dynamic_weights(0.02, config)

    assert "EMA_ARCHITECTURE_WEIGHTS" in reasons
    assert weights["ema_50_quality"] == 15.0
    assert weights["ema_momentum"] == 10.0
    assert "rsi_timing" not in weights
    assert round(sum(weights.values()), 6) == 100.0
```

Append to `tests/test_entry_chain_features.py`:

```python
from src.signals.entry_chain_features import component_scores


def test_component_scores_include_ema_when_enabled():
    bars = [bar(index * 900, 100 + index * 0.2) for index in range(240)]
    completed = {"15m": bars, "30m": bars, "1h": bars, "4h": bars}

    scores = component_scores("LONG", completed, atr_pct_value=0.01, use_ema_architecture=True)

    assert "ema_50_quality" in scores
    assert "ema_momentum" in scores
    assert scores["ema_50_quality"] > 0
    assert scores["ema_momentum"] > 0
```

- [ ] **Step 2: Run tests to confirm failures**

Run:

```powershell
pytest tests/test_entry_chain_scoring.py tests/test_entry_chain_features.py -q
```

Expected: failures because `EntryChainConfig.use_ema_architecture` and EMA components do not exist.

- [ ] **Step 3: Extend entry-chain config**

Add fields to `EntryChainConfig` in `src/signals/entry_chain_config.py`:

```python
use_ema_architecture: bool = False
ema200_gate_mode: str = "hard"
ema200_buffer_pct: float = 0.003
ema200_min_bars_stable: int = 3
ema50_min_for_direct: float = 0.60
ema50_min_for_probe: float = 0.40
```

`from_mapping()` already rejects unknown keys, so these fields must be listed directly in the dataclass.

- [ ] **Step 4: Add EMA weight profile**

Modify `src/signals/entry_chain_scoring.py`:

```python
EMA_WEIGHTS = {
    "background_4h": 5.0,
    "direction_1h": 18.0,
    "quality_30m": 12.0,
    "trigger_15m": 7.0,
    "ema_50_quality": 15.0,
    "ema_momentum": 10.0,
    "cvd_flow": 18.0,
    "volatility_stop": 10.0,
    "liquidity_execution": 3.0,
    "market_regime": 2.0,
}
```

Update `dynamic_weights()`:

```python
if cfg.use_ema_architecture:
    reasons.append("EMA_ARCHITECTURE_WEIGHTS")
    return dict(EMA_WEIGHTS), reasons
```

Place this before high/low volatility rules for the first ablation pass. Do not combine EMA and volatility dynamic weighting until the EMA A/B/C/D experiments are reported.

- [ ] **Step 5: Add EMA component score generation**

Modify `component_scores()` signature in `src/signals/entry_chain_features.py`:

```python
def component_scores(
    side: str,
    completed: Mapping[str, Sequence[BacktestBar]],
    atr_pct_value: float,
    *,
    use_ema_architecture: bool = False,
    ema200_gate_mode: str = "hard",
) -> dict[str, float]:
```

Inside the function:

```python
scores = {
    "background_4h": agreement_score(side, completed.get("4h", []), 3),
    "direction_1h": agreement_score(side, completed.get("1h", []), 4),
    "quality_30m": agreement_score(side, completed.get("30m", []), 6),
    "trigger_15m": trigger_score(side, completed.get("15m", [])),
    "cvd_flow": volume_flow_score(side, completed.get("15m", [])),
    "volatility_stop": 1.0 if 0.005 <= atr_pct_value <= 0.04 else 0.2,
    "liquidity_execution": 1.0,
    "market_regime": 0.8,
}
if use_ema_architecture:
    ema_context = ema_context_from_bars(completed.get("15m", []))
    if ema_context is None:
        scores["ema_50_quality"] = 0.0
        scores["ema_momentum"] = 0.0
    else:
        scores["ema_50_quality"] = score_ema50_quality(side, ema_context)
        scores["ema_momentum"] = score_ema_momentum(side, ema_context)
return scores
```

Add imports:

```python
from src.indicators.ema import bars_since_cross, ema, normalized_ema_slope
from src.signals.ema_scorer import EmaContext, score_ema50_quality, score_ema_momentum
```

Add helper:

```python
def ema_context_from_bars(bars: Sequence[BacktestBar]) -> EmaContext | None:
    if len(bars) < 200:
        return None
    closes = [bar.close for bar in bars]
    ema_9_series = ema(closes, 9)
    ema_21_series = ema(closes, 21)
    ema_50_series = ema(closes, 50)
    ema_200_series = ema(closes, 200)
    if not all((ema_9_series, ema_21_series, ema_50_series, ema_200_series)):
        return None
    ema_9 = ema_9_series[-1]
    ema_21 = ema_21_series[-1]
    ema9_21_gap = (ema_9 - ema_21) / ema_21 if ema_21 else 0.0
    return EmaContext(
        close=closes[-1],
        ema_9=ema_9,
        ema_21=ema_21,
        ema_50=ema_50_series[-1],
        ema_200=ema_200_series[-1],
        ema50_slope=normalized_ema_slope(ema_50_series, 5),
        ema9_21_gap=ema9_21_gap,
        bars_since_ema50_cross=bars_since_cross(closes[-len(ema_50_series):], ema_50_series),
        bars_since_ema200_cross=bars_since_cross(closes[-len(ema_200_series):], ema_200_series),
    )
```

- [ ] **Step 6: Verify feature scoring**

Run:

```powershell
pytest tests/test_ema_scorer.py tests/test_entry_chain_scoring.py tests/test_entry_chain_features.py -q
```

Expected: all tests pass.

## Task 6: Apply EMA Gate In Entry Chain

**Files:**
- Modify: `src/signals/entry_chain.py`
- Modify: `scripts/run_offline_backtest.py`
- Modify: `tests/test_entry_chain.py`

- [ ] **Step 1: Add entry-chain gate tests**

Append to `tests/test_entry_chain.py`:

```python
from src.signals.entry_chain_config import EntryChainConfig


def test_ema_component_minimums_downgrade_direct_and_probe():
    direct = evaluate_entry_chain(
        candidate(component_scores={**candidate().component_scores, "ema_50_quality": 0.50, "ema_momentum": 1.0}),
        EntryChainConfig(use_ema_architecture=True, direct_threshold=80, probe_threshold=70),
    )
    assert direct.action == "PROBE"
    assert "EMA50_DIRECT_MINIMUM_FAILED" in direct.reasons

    probe = evaluate_entry_chain(
        candidate(component_scores={**candidate().component_scores, "ema_50_quality": 0.20, "ema_momentum": 1.0}),
        EntryChainConfig(use_ema_architecture=True, direct_threshold=90, probe_threshold=70),
    )
    assert probe.action == "WATCH"
    assert "EMA50_PROBE_MINIMUM_FAILED" in probe.reasons
```

- [ ] **Step 2: Run tests to confirm failure**

Run:

```powershell
pytest tests/test_entry_chain.py -q
```

Expected: failure because EMA minimum reasons are not implemented.

- [ ] **Step 3: Add EMA component minimum checks**

In `_apply_component_minimums()` in `src/signals/entry_chain.py`, after existing component minimum checks:

```python
if cfg.use_ema_architecture and action == "DIRECT":
    if float(scores.get("ema_50_quality", 0.0)) < cfg.ema50_min_for_direct:
        reasons.append("EMA50_DIRECT_MINIMUM_FAILED")
        action = "PROBE"
if cfg.use_ema_architecture and action == "PROBE":
    if float(scores.get("ema_50_quality", 0.0)) < cfg.ema50_min_for_probe:
        reasons.append("EMA50_PROBE_MINIMUM_FAILED")
        action = "WATCH"
```

- [ ] **Step 4: Pass EMA config into offline component scores**

Modify `scripts/run_offline_backtest.py`:

```python
scores = component_scores(
    side,
    completed,
    atr_pct_value,
    use_ema_architecture=cfg.use_ema_architecture,
    ema200_gate_mode=cfg.ema200_gate_mode,
)
```

- [ ] **Step 5: Verify entry chain**

Run:

```powershell
pytest tests/test_entry_chain.py tests/test_entry_chain_features.py tests/test_entry_chain_scoring.py -q
```

Expected: all tests pass.

## Task 7: Update Strategy Config And Config Schema

**Files:**
- Modify: `configs/strategy.yaml`
- Modify: `src/config/config_schema.py`
- Modify: `tests/test_config_schema.py`

- [ ] **Step 1: Update config schema tests**

Modify `tests/test_config_schema.py` expected `CONFIG_REQUIRED_FIELDS["strategy.yaml"]` to require:

```python
"indicators.ema.fast",
"indicators.ema.slow",
"indicators.ema.trend",
"indicators.ema.gate",
"indicators.ema.slope_lookback",
"entry.ema200_gate_mode",
"entry.ema200_buffer_pct",
"entry.ema200_min_bars_stable",
```

Remove expectations for:

```python
"indicators.rsi.period",
"entry.rsi_reclaim",
```

- [ ] **Step 2: Run config tests to confirm failure**

Run:

```powershell
pytest tests/test_config_schema.py -q
```

Expected: failures because config/schema still expect RSI.

- [ ] **Step 3: Update `configs/strategy.yaml`**

Replace:

```yaml
  rsi:
    period: 14
```

with:

```yaml
  ema:
    fast: 9
    slow: 21
    trend: 50
    gate: 200
    slope_lookback: 5
```

Replace:

```yaml
  rsi_reclaim: 50
```

with:

```yaml
  ema200_gate_mode: hard
  ema200_buffer_pct: 0.003
  ema200_min_bars_stable: 3
```

Change strategy name:

```yaml
  name: macd_cci_cvd_ema_v1
```

- [ ] **Step 4: Update config schema required fields**

Modify `src/config/config_schema.py` strategy required fields to match Step 1.

- [ ] **Step 5: Verify config schema**

Run:

```powershell
pytest tests/test_config_schema.py -q
```

Expected: all config schema tests pass.

## Task 8: Add EMA Ablation Configs

**Files:**
- Create: `configs/entry_chain.dry_run_no_rsi.json`
- Create: `configs/entry_chain.dry_run_ema_soft.json`
- Create: `configs/entry_chain.dry_run_ema_hard.json`
- Modify: `tests/test_dry_run_configs.py`

- [ ] **Step 1: Add config tests**

Append to `tests/test_dry_run_configs.py`:

```python
def test_ema_ablation_configs_load_and_order_by_strictness():
    no_rsi = load_entry_chain_config("configs/entry_chain.dry_run_no_rsi.json")
    soft = load_entry_chain_config("configs/entry_chain.dry_run_ema_soft.json")
    hard = load_entry_chain_config("configs/entry_chain.dry_run_ema_hard.json")

    assert no_rsi.use_ema_architecture is False
    assert soft.use_ema_architecture is True
    assert soft.ema200_gate_mode == "soft"
    assert hard.use_ema_architecture is True
    assert hard.ema200_gate_mode == "hard"
    assert hard.direct_threshold >= soft.direct_threshold
```

- [ ] **Step 2: Run config tests to confirm failure**

Run:

```powershell
pytest tests/test_dry_run_configs.py -q
```

Expected: failures because config files do not exist.

- [ ] **Step 3: Create no-RSI redistribution config**

Create `configs/entry_chain.dry_run_no_rsi.json`:

```json
{
  "direct_threshold": 84.0,
  "probe_threshold": 72.0,
  "watch_threshold": 61.0,
  "daily_max_trades_base": 3,
  "max_symbol_trades_per_day": 1,
  "max_active_symbols": 5,
  "direct_risk_pct": 0.006,
  "probe_risk_pct": 0.0025,
  "max_total_exposure_pct": 1.2,
  "max_same_direction_exposure_pct": 0.9,
  "margin_buffer_pct": 0.30,
  "use_ema_architecture": false
}
```

- [ ] **Step 4: Create EMA soft config**

Create `configs/entry_chain.dry_run_ema_soft.json`:

```json
{
  "direct_threshold": 82.0,
  "probe_threshold": 70.0,
  "watch_threshold": 60.0,
  "daily_max_trades_base": 4,
  "max_symbol_trades_per_day": 1,
  "max_active_symbols": 5,
  "direct_risk_pct": 0.006,
  "probe_risk_pct": 0.0025,
  "max_total_exposure_pct": 1.2,
  "max_same_direction_exposure_pct": 0.9,
  "margin_buffer_pct": 0.30,
  "use_ema_architecture": true,
  "ema200_gate_mode": "soft",
  "ema200_buffer_pct": 0.003,
  "ema200_min_bars_stable": 3,
  "ema50_min_for_direct": 0.60,
  "ema50_min_for_probe": 0.40
}
```

- [ ] **Step 5: Create EMA hard config**

Create `configs/entry_chain.dry_run_ema_hard.json`:

```json
{
  "direct_threshold": 84.0,
  "probe_threshold": 72.0,
  "watch_threshold": 60.0,
  "daily_max_trades_base": 4,
  "max_symbol_trades_per_day": 1,
  "max_active_symbols": 5,
  "direct_risk_pct": 0.006,
  "probe_risk_pct": 0.0025,
  "max_total_exposure_pct": 1.2,
  "max_same_direction_exposure_pct": 0.9,
  "margin_buffer_pct": 0.30,
  "use_ema_architecture": true,
  "ema200_gate_mode": "hard",
  "ema200_buffer_pct": 0.003,
  "ema200_min_bars_stable": 3,
  "ema50_min_for_direct": 0.60,
  "ema50_min_for_probe": 0.40
}
```

- [ ] **Step 6: Verify configs**

Run:

```powershell
pytest tests/test_dry_run_configs.py tests/test_entry_chain_config.py -q
```

Expected: all config tests pass.

## Task 9: Update Documentation Contracts

**Files:**
- Modify: `docs/03_indicator_spec.md`
- Modify: `docs/09_data_contract.md`
- Modify: `docs/04_multi_timeframe_rules.md`
- Modify: `docs/superpowers/reports/2026-06-19-claude-live-entry-chain-risk-review.md`

- [ ] **Step 1: Update indicator spec**

In `docs/03_indicator_spec.md`:

- Replace the V1 indicator list `MACD / CCI / BOLL / RSI / CVD / ATR` with `MACD / CCI / BOLL / EMA / CVD / ATR`.
- Replace section `# 11. RSI 规范` with `# 11. EMA 规范`.
- Define EMA outputs:

```text
ema_9
ema_21
ema_50
ema_200
ema50_slope
ema9_21_gap
bars_since_ema50_cross
bars_since_ema200_cross
```

- Define EMA responsibilities:

```text
EMA200: direction gate
EMA50: trend quality
EMA9/21: short-term momentum resonance
```

- Add explicit forbidden usage:

```text
EMA cannot directly size positions.
EMA cannot bypass CVD, risk, or state-machine checks.
EMA200 hard gate cannot use unfinished bars.
EMA cannot be used as a guaranteed trend-continuation promise.
```

- [ ] **Step 2: Update data contract doc**

In `docs/09_data_contract.md`, replace the RSI indicator contract section with EMA fields listed in Step 1.

- [ ] **Step 3: Update multi-timeframe rules doc**

In `docs/04_multi_timeframe_rules.md`, replace RSI timing references:

```text
1H: EMA200/EMA50 direction and quality, MACD, CCI, CVD
30m: EMA50 quality, MACD, BOLL, CCI, CVD
15m: EMA9/21 momentum, MACD, CVD, BOLL
```

- [ ] **Step 4: Update Claude review report**

In `docs/superpowers/reports/2026-06-19-claude-live-entry-chain-risk-review.md`, add a section:

```text
EMA replacement review note:
- RSI is removed from main entry-chain scoring because it overlaps with CCI.
- EMA200 is the direction legality gate.
- EMA50 quality and EMA9/21 momentum are weighted score components.
- Claude should challenge hard-vs-soft EMA200 gating and the risk of lag in fast reversals.
```

## Task 10: Run EMA Ablation Backtests

**Files:**
- Read/write under `reports/backtests/`
- Create: `docs/superpowers/reports/2026-06-19-rsi-to-ema-ablation-backtest-report.md`

- [ ] **Step 1: Run Experiment A baseline**

Run the current conservative profile:

```powershell
python scripts/run_offline_backtest.py --data-dir data/raw/binance_futures/latest_30d --timeframe 15m --strategy entry-chain --entry-chain-config configs/entry_chain.dry_run_conservative.json --simulated-hold-bars 2 --cooldown-bars 8 --run-id latest_30d_ema_exp_a_baseline
```

- [ ] **Step 2: Run Experiment B no-RSI redistribution**

```powershell
python scripts/run_offline_backtest.py --data-dir data/raw/binance_futures/latest_30d --timeframe 15m --strategy entry-chain --entry-chain-config configs/entry_chain.dry_run_no_rsi.json --simulated-hold-bars 2 --cooldown-bars 8 --run-id latest_30d_ema_exp_b_no_rsi
```

- [ ] **Step 3: Run Experiment C EMA soft**

```powershell
python scripts/run_offline_backtest.py --data-dir data/raw/binance_futures/latest_30d --timeframe 15m --strategy entry-chain --entry-chain-config configs/entry_chain.dry_run_ema_soft.json --simulated-hold-bars 2 --cooldown-bars 8 --run-id latest_30d_ema_exp_c_soft
```

- [ ] **Step 4: Run Experiment D EMA hard**

```powershell
python scripts/run_offline_backtest.py --data-dir data/raw/binance_futures/latest_30d --timeframe 15m --strategy entry-chain --entry-chain-config configs/entry_chain.dry_run_ema_hard.json --simulated-hold-bars 2 --cooldown-bars 8 --run-id latest_30d_ema_exp_d_hard
```

- [ ] **Step 5: Write ablation report**

Create `docs/superpowers/reports/2026-06-19-rsi-to-ema-ablation-backtest-report.md` with:

```markdown
# RSI To EMA Ablation Backtest Report

Date: 2026-06-19

## Runs

| Experiment | Run ID | Config | Purpose |
| --- | --- | --- | --- |
| A | `latest_30d_ema_exp_a_baseline` | conservative | Existing reference |
| B | `latest_30d_ema_exp_b_no_rsi` | no_rsi | Remove RSI-style timing weight |
| C | `latest_30d_ema_exp_c_soft` | ema_soft | EMA200 soft penalty |
| D | `latest_30d_ema_exp_d_hard` | ema_hard | EMA200 hard gate |

## Metrics

Include trade count, return, win rate, profit factor, max drawdown, Sharpe, Sortino, expectancy, gross PnL, fees, slippage, side split, entry-mode split, and symbol split.

## Interpretation

State whether EMA improved win rate, reduced countertrend trades, preserved 90-120 monthly trade count, and improved cost-adjusted expectancy.

## Deployment Decision

State one of:

- reject EMA hard gate for now,
- keep EMA soft for more research,
- promote EMA soft to VPS dry-run,
- promote EMA hard only after rolling-window validation.
```

## Task 11: Final Verification

**Files:**
- No intended changes to `src/api/binance_client.py`.

- [ ] **Step 1: Run full focused verification**

Run:

```powershell
python -m compileall src scripts tests
pytest tests/test_ema_indicator.py tests/test_ema_scorer.py tests/test_indicator_engine.py tests/test_indicator_spec_rules.py tests/test_data_contract.py tests/test_entry_chain.py tests/test_entry_chain_features.py tests/test_entry_chain_scoring.py tests/test_entry_chain_config.py tests/test_dry_run_configs.py tests/test_config_schema.py -q
git diff -- src/api/binance_client.py
```

Expected:

- Compile exits `0`.
- All listed tests pass.
- `git diff -- src/api/binance_client.py` prints nothing.

- [ ] **Step 2: Validate no accidental live execution changes**

Run:

```powershell
git diff -- src/execution scripts/run_live_dry_run.py deploy configs/execution.yaml
```

Expected:

- No live order submission behavior changes.
- Dry-run files may be unchanged or only documentation-adjacent; any execution diff must be reviewed before continuing.

- [ ] **Step 3: Final response**

Report:

- Plan execution completed or blocked.
- Best ablation experiment.
- Whether the result meets the strategy target.
- Whether `src/api/binance_client.py` remained untouched.
- Paths to the ablation report and updated Claude review document.

## Out Of Scope For This Plan

- Real order submission.
- Binance client changes.
- TP/SL optimization.
- Leverage formula changes beyond EMA review documentation.
- Position-size formula changes.
- 6-12 month historical validation.
- Parameter search beyond the A/B/C/D ablation configs listed above.

These items should be planned after the EMA replacement has a clean 30D ablation result.

