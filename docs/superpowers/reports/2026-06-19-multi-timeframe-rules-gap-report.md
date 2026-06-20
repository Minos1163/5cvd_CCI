# Multi Timeframe Rules Gap Report

Date: 2026-06-19

Scope: reread the refreshed `docs/04_multi_timeframe_rules.md` and compare it with current multi-timeframe context scripts, tests, describe output, and scaffold templates. This report is documentation only; code changes are covered by the follow-up implementation plan.

---

## 1. Executive Summary

`docs/04_multi_timeframe_rules.md` now defines multi-timeframe logic as a structured decision contract: 4H background, 1H direction, 30m quality, and 15m timing must cooperate in a one-way chain, with conservative conflict handling and standardized outputs. The current implementation already has a working first-pass `build_multi_tf_decision()` flow, but it still lacks a formal `TimeframeResult` object, machine-readable priorities, quality handling, forbidden-pattern rules, and complete describe/scaffold coverage.

The safest next step is to extend the context layer without changing signal/risk/execution semantics: keep existing `IndicatorSnapshot` evaluators and `MultiTimeframeDecision` compatibility, add standard result contracts around them, update tests, update describe output, and sync scaffold templates.

---

## 2. Files Reviewed

- `docs/04_multi_timeframe_rules.md`
- `src/context/multi_tf_rules.py`
- `src/context/multi_tf_context.py`
- `tests/test_multi_tf_rules.py`
- `scripts/describe_multi_tf_rules.py`
- `tests/test_describe_multi_tf_rules.py`
- `src/signals/signal_engine.py`
- `tests/test_signal_engine.py`
- `scripts/scaffold_ai300_framework.py`
- `tests/test_framework_scaffold.py`

---

## 3. Document Cleanliness Issue

The refreshed `docs/04_multi_timeframe_rules.md` is not yet canonical markdown:

- It starts with ChatGPT wrapper text.
- It includes an outer ````md wrapper.
- Its final example block uses four backticks where an inner text fence should use three.

Normalize the document so line 1 is `# Multi Timeframe Rules` and all code fences are valid markdown.

---

## 4. Current Implementation Snapshot

Current `src/context/multi_tf_rules.py` provides:

- `TimeframeDecision`
- `MultiTimeframeDecision`
- `evaluate_4h_context()`
- `evaluate_1h_permission()`
- `evaluate_30m_quality()`
- `evaluate_15m_trigger()`
- `build_multi_tf_decision()`

This is useful and should remain compatible. It already supports direct/probe/wait/no-trade flows, but the output is a compact legacy decision object, not the standardized per-timeframe result structure requested by the refreshed 04 document.

---

## 5. Major Gaps

### 5.1 No Standardized Timeframe Result

The document requires every timeframe result to include:

- `symbol`
- `timeframe`
- `timestamp`
- `state`
- `confidence`
- `reason`
- `sub_reasons`
- `quality_flag`
- `metadata`

No `TimeframeResult` dataclass currently exists.

### 5.2 30m States Are Direction-Specific Only

The document defines 30m quality states as `CONFIRMED`, `WEAK`, `INVALID`, and `TRANSITION`. Current code returns `LONG_CONFIRM`, `SHORT_CONFIRM`, and `WEAK`. The compatibility states are useful for the signal engine, but the context layer needs generic quality state plus side metadata.

### 5.3 4H Conflict Handling Is Too Permissive For Direct Entries

The document says a 4H/1H conflict should downgrade to `WAIT` or `PROBE`, and should not allow unconditional `DIRECT`. Current `build_multi_tf_decision()` can return `DIRECT LONG` while `4H=BEAR`.

### 5.4 Data Quality Is Not First-Class

The refreshed 04 spec makes data quality the highest priority. Current logic has no quality flag inputs and no standard way to downgrade invalid/missing/misaligned timeframe results.

### 5.5 Describe Output Is Too Thin

`scripts/describe_multi_tf_rules.py` currently emits only roles, outputs, and one rule string. It should expose roles, standardized output fields, priority order, state sets, conflict rules, forbidden actions, and example mappings.

### 5.6 Scaffold Templates Are Stale

`scripts/scaffold_ai300_framework.py` still contains first-pass 04 templates. Future scaffolding could recreate the old contract unless updated.

---

## 6. Recommended Priority

### P0: Clean Canonical Markdown

Clean `docs/04_multi_timeframe_rules.md` so it is a valid spec file.

### P1: Contract Constants And Standard Results

Extend `src/context/multi_tf_rules.py` with:

- role and priority constants
- state constants
- forbidden actions
- `TimeframeResult`
- `build_timeframe_results()`
- `validate_timeframe_result()`
- conservative conflict helper

### P2: Preserve Compatibility

Keep:

- `evaluate_4h_context()`
- `evaluate_1h_permission()`
- `evaluate_30m_quality()`
- `evaluate_15m_trigger()`
- `build_multi_tf_decision()`

but update conflict behavior so 4H conflict cannot produce `DIRECT`.

### P3: Describe And Scaffold Sync

Update describe output and scaffold templates after the implementation.

---

## 7. Risk Notes

- Do not modify live execution behavior.
- Do not modify risk sizing.
- Do not modify backtest fill assumptions.
- Do not modify `src/api/binance_client.py`.
- Do not let 15m become the direction layer.
- Do not make 4H a hard global veto; it should downgrade, not lock the strategy.
- Do not introduce future candle or unfinished higher-timeframe assumptions.

---

## 8. Proposed Next Plan

Implement the follow-up in `docs/superpowers/plans/2026-06-19-multi-timeframe-rules-gap-fill.md`.
