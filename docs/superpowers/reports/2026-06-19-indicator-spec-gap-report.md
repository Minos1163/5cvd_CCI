# Indicator Spec Gap Report

Date: 2026-06-19

Scope: reread the refreshed `docs/03_indicator_spec.md` and compare it with the current indicator scripts, data contracts, describe output, tests, and scaffold templates. This report is documentation only. No strategy code, live execution code, or Binance client code is changed by this report.

---

## 1. Executive Summary

`docs/03_indicator_spec.md` now defines the indicator layer as a strict contract: V1 indicators are limited to `MACD`, `CCI`, `BOLL`, `RSI`, `CVD`, and `ATR`; every indicator must consume standardized closed candles and output standardized `IndicatorResult` objects with quality flags. The current implementation is still a lightweight first pass: formulas exist, `compute_indicator_snapshot()` exists, and `src/data/data_contract.py` already defines useful shared data contracts, but the indicator layer does not yet enforce the refreshed 03 requirements.

The next safe step is a contract-first indicator pass: clean the markdown, expand `src/indicators/indicator_spec.py`, add standardized result builders around the existing math functions, update tests and describe output, then synchronize scaffold templates. This should not change live execution, signal decisions, risk sizing, backtest fills, or `src/api/binance_client.py`.

---

## 2. Files Reviewed

- `docs/03_indicator_spec.md`
- `src/indicators/indicator_spec.py`
- `src/indicators/indicator_engine.py`
- `src/indicators/macd.py`
- `src/indicators/rsi.py`
- `src/indicators/cci.py`
- `src/indicators/boll.py`
- `src/indicators/atr.py`
- `src/indicators/cvd.py`
- `src/core/models.py`
- `src/data/data_contract.py`
- `scripts/describe_indicator_rules.py`
- `tests/test_indicator_spec_rules.py`
- `tests/test_indicator_engine.py`
- `tests/test_describe_indicator_rules.py`
- `configs/strategy.yaml`
- `scripts/scaffold_ai300_framework.py`

---

## 3. Document Cleanliness Issue

The refreshed `docs/03_indicator_spec.md` is not yet a clean canonical markdown file. It starts with ChatGPT wrapper text and an outer code fence:

- It begins with `下面是重新整理后的...`
- It includes an outer ````md wrapper.
- The final code fence is not cleanly closed in the current file content.

Before using this file as a stable spec source, normalize it so line 1 is `# Indicator Specification` and only the indicator specification remains.

---

## 4. Current Implementation Snapshot

`src/indicators/indicator_spec.py` currently provides:

- `DEFAULT_INDICATOR_PARAMS`
- `INDICATOR_RESPONSIBILITIES`
- `INDICATOR_PRIORITY`
- `validate_indicator_usage()`
- `classify_rsi()`
- `classify_cci()`

`src/indicators/indicator_engine.py` currently provides:

- `compute_indicator_snapshot(candles: list[Candle]) -> IndicatorSnapshot`
- raw computation using existing math helpers.

`src/data/data_contract.py` already provides important reusable contracts:

- `MarketCandle`
- `IndicatorResult`
- `QUALITY_FLAGS`
- `INDICATOR_CONTRACT_FIELDS`
- `INDICATOR_REQUIRED_OUTPUTS`
- `validate_market_candle()`
- `validate_indicator_result()`
- `quality_allows_direct_entry()`

This means the 03 implementation should reuse the data contract instead of creating a parallel `IndicatorResult` type.

---

## 5. Major Gaps

### 5.1 Indicator Spec Module Is Too Thin

The refreshed document requires explicit contracts for:

- V1 indicator names.
- Required candle input fields.
- Unified `IndicatorResult` fields.
- Quality flag semantics.
- Per-indicator required output fields.
- Multi-timeframe indicator responsibilities.
- Conflict priority.
- Cache/version fields.
- Forbidden usages.

The current `indicator_spec.py` only stores params, short responsibilities, a partial priority tuple, and simple RSI/CCI classifiers.

### 5.2 Conflict Priority Does Not Match The Refreshed Spec

Current priority is:

```python
("MACD", "CVD", "RSI", "CCI", "BOLL")
```

The refreshed spec says conflict handling should prioritize:

1. Data quality
2. CVD divergence
3. MACD trend direction
4. CCI strength
5. BOLL structure
6. RSI timing
7. ATR risk

This is materially different. The current tuple omits data quality and ATR, and it puts RSI before CCI/BOLL.

### 5.3 Closed-Candle And Quality Rules Are Not Enforced In The Indicator Engine

The document requires:

- Only completed candles.
- No unfinished bar final values.
- No future data.
- Quality flags on every result.
- `false` and `stale` results cannot drive direct entries.
- `degraded` results only support degraded judgment.

`compute_indicator_snapshot()` accepts `src.core.models.Candle`, which has no `is_closed` or `quality_flag` fields. It also returns `IndicatorSnapshot`, not standardized `IndicatorResult` objects.

### 5.4 Required Output Fields Are Defined But Not Produced By Indicator Engine

`src/data/data_contract.py` already defines:

- MACD: `macd_line`, `signal_line`, `histogram`, `histogram_slope`, `cross_state`
- CCI: `cci`, `cci_slope`, `extreme_flag`, `recovery_flag`
- BOLL: `middle_band`, `upper_band`, `lower_band`, `band_width`, `band_expansion_flag`, `band_contraction_flag`, `price_position`
- RSI: `rsi`, `rsi_slope`, `overbought_flag`, `oversold_flag`, `midline_state`
- CVD: `cvd`, `cvd_delta`, `cvd_slope`, `cvd_divergence_flag`, `buy_pressure`, `sell_pressure`
- ATR: `atr`, `atr_pct`, `volatility_state`

The indicator engine currently returns a compact `IndicatorSnapshot` and does not populate these standardized fields.

### 5.5 Timeframe Usage Contract Is Missing

The refreshed spec defines indicator roles by timeframe:

- `4h`: MACD, BOLL, CCI
- `1h`: MACD, CCI, CVD, RSI
- `30m`: MACD, BOLL, CCI, CVD
- `15m`: RSI, MACD, CVD, BOLL

This does not yet exist as a machine-readable constant or test.

### 5.6 Forbidden Usage Rules Are Incomplete

Only ATR direction usage is blocked today. The refreshed spec also forbids:

- MACD as sole entry reason.
- CCI as sole long/short decision.
- BOLL as sole trend detector or position-sizing input.
- RSI replacing trend or fund-flow confirmation.
- CVD as standalone direction predictor or execution priority.
- ATR generating directional signals.
- Indicators generating orders, final position size, state-machine bypass, or "must trade" conclusions.

### 5.7 Describe Output Is Not Authoritative Enough

`scripts/describe_indicator_rules.py` currently emits only params, responsibilities, the old priority tuple, and `["ATR direction"]`. It does not expose:

- Required input fields.
- Output contract fields.
- Required outputs.
- Quality flags.
- Timeframe map.
- Conflict priority.
- Forbidden usages.
- Cache/version requirements.

### 5.8 Tests Cover The Old Contract

Current indicator tests validate the first implementation pass, not the refreshed 03 spec:

- Priority test expects the old priority tuple.
- No tests assert `IndicatorResult` output.
- No tests assert closed-candle behavior.
- No tests assert degraded/stale quality behavior.
- No tests assert required fields for each indicator.
- No tests assert timeframe mismatch or missing data semantics.

### 5.9 Scaffold Templates Are Stale

`scripts/scaffold_ai300_framework.py` contains templates for indicator-related files. Any 03 implementation must update the scaffold templates and scaffold tests, otherwise future scaffolding can recreate the old thin contract.

---

## 6. Recommended Priority

### P0: Canonical Spec And Contracts

1. Clean `docs/03_indicator_spec.md`.
2. Expand `src/indicators/indicator_spec.py` with machine-readable 03 constants and validation helpers.
3. Reuse `src.data.data_contract.IndicatorResult` and `MarketCandle`.

### P1: Standardized Result Builder

1. Keep `compute_indicator_snapshot()` for compatibility.
2. Add `compute_indicator_results()` that returns one `IndicatorResult` per V1 indicator.
3. Enforce closed-candle and quality behavior for `MarketCandle` inputs.
4. Preserve raw formula helpers without changing their mathematical behavior.

### P2: Tests And Describe Output

1. Expand tests for spec constants, forbidden usages, quality semantics, and timeframe map.
2. Add indicator-engine tests for standardized result fields.
3. Expand `scripts/describe_indicator_rules.py` and tests.

### P3: Scaffold Sync

1. Update indicator-related scaffold templates.
2. Add scaffold tests for new contract names.

---

## 7. Risk Notes

- Do not change live execution behavior in this pass.
- Do not change signal/risk decisions while implementing indicator contracts.
- Do not change backtest fill assumptions.
- Do not modify `src/api/binance_client.py`.
- Do not introduce lookahead bias or same-bar fill assumptions.
- Treat ATR as risk-only. It must not become a direction indicator.
- Indicators must not generate orders, final position sizes, or "must trade" conclusions.

---

## 8. Proposed Next Plan

Implement the follow-up in `docs/superpowers/plans/2026-06-19-indicator-spec-gap-fill.md`.

Recommended execution mode: `superpowers:subagent-driven-development`, task-by-task, after the current uncommitted 02 Market Universe changes are either committed or intentionally kept separate.
