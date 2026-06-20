# Multi Timeframe Rules Gap Fill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the refreshed `docs/04_multi_timeframe_rules.md` into a clean, testable multi-timeframe context contract.

**Architecture:** Keep the existing legacy `MultiTimeframeDecision` flow for signal-engine compatibility, and add a standard `TimeframeResult` contract around it. The context layer may evaluate 4H/1H/30m/15m states and conservative downgrade rules, but it must not calculate position size, call execution, or make final risk decisions.

**Tech Stack:** Python dataclasses, enums, pure functions, existing `IndicatorSnapshot`, pytest, JSON describe scripts, scaffold template synchronization.

---

## File Structure

Modify:

- `docs/04_multi_timeframe_rules.md`
- `src/context/multi_tf_rules.py`
- `tests/test_multi_tf_rules.py`
- `scripts/describe_multi_tf_rules.py`
- `tests/test_describe_multi_tf_rules.py`
- `scripts/scaffold_ai300_framework.py`
- `tests/test_framework_scaffold.py`

Do not modify:

- `src/api/binance_client.py`
- live execution modules
- risk sizing modules
- backtest fill model modules

---

## Tasks

### Task 1: Clean 04 Markdown

- [ ] Remove ChatGPT wrapper text from `docs/04_multi_timeframe_rules.md`.
- [ ] Remove the outer ````md fence.
- [ ] Fix the sample `timeframe_result` fence to use normal triple backticks.
- [ ] Verify line 1 is `# Multi Timeframe Rules`.

### Task 2: Add Multi-Timeframe Contract Tests

- [ ] Extend `tests/test_multi_tf_rules.py` to cover role constants, priority constants, standardized `TimeframeResult`, quality rejection, 4H conflict downgrade, 30m generic quality result, CVD divergence downgrade, and forbidden actions.

Expected command:

```powershell
pytest tests\test_multi_tf_rules.py -q
```

### Task 3: Implement Multi-Timeframe Contract

- [ ] Extend `src/context/multi_tf_rules.py` with:

```python
TIMEFRAME_ROLES = {
    "4h": "background_reference",
    "1h": "direction_confirmation",
    "30m": "trend_quality_confirmation",
    "15m": "execution_trigger",
}
TIMEFRAME_PRIORITY = (
    "data_quality",
    "risk_constraints",
    "4h_background",
    "1h_direction",
    "30m_quality",
    "15m_trigger",
    "position_executability",
    "execution_layer",
)
TIMEFRAME_OUTPUT_FIELDS = (
    "symbol",
    "timeframe",
    "timestamp",
    "state",
    "confidence",
    "reason",
    "sub_reasons",
    "quality_flag",
    "metadata",
)
TIMEFRAME_FORBIDDEN_ACTIONS = (
    "4h_hard_veto",
    "15m_direction_override",
    "independent_timeframe_commands",
    "unfinished_high_tf_final_signal",
    "nested_patch_conditions",
    "execution_reinterprets_context",
)
```

- [ ] Add `TimeframeResult`.
- [ ] Add `build_timeframe_results()`.
- [ ] Add `validate_timeframe_result()`.
- [ ] Keep `build_multi_tf_decision()` compatibility.
- [ ] Downgrade 4H/1H conflict from `DIRECT` to `PROBE`.

### Task 4: Expand Describe Output

- [ ] Update `scripts/describe_multi_tf_rules.py`.
- [ ] Update `tests/test_describe_multi_tf_rules.py`.

Expected command:

```powershell
pytest tests\test_describe_multi_tf_rules.py -q
```

### Task 5: Sync Scaffold

- [ ] Sync scaffold templates for `src/context/multi_tf_rules.py` and `scripts/describe_multi_tf_rules.py`.
- [ ] Add scaffold assertions for `TimeframeResult`, `TIMEFRAME_PRIORITY`, and `TIMEFRAME_FORBIDDEN_ACTIONS`.

Expected command:

```powershell
pytest tests\test_framework_scaffold.py -q
```

### Task 6: Final Verification

Run:

```powershell
pytest tests\test_multi_tf_rules.py tests\test_describe_multi_tf_rules.py tests\test_signal_engine.py tests\test_framework_scaffold.py -q
pytest -q
python -m compileall src scripts tests
git diff -- src\api\binance_client.py
```

Expected:

- Tests pass.
- Compile succeeds.
- Binance client diff is empty.

---

## Completion Criteria

- `docs/04_multi_timeframe_rules.md` is clean canonical markdown.
- Multi-timeframe layer exposes a standard `TimeframeResult`.
- 4H remains background reference, not a hard veto.
- 4H/1H conflict cannot produce unconditional `DIRECT`.
- 1H remains the direction layer.
- 30m quality is represented as generic quality plus side metadata.
- 15m remains timing/trigger only.
- Describe output and scaffold templates match the new contract.
- No changes to `src/api/binance_client.py`.
