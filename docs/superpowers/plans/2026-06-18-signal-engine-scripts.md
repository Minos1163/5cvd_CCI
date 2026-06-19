# Signal Engine Scripts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `docs/16_signal_engine.md` contract as executable Python scripts: a pure signal engine, a describe script, tests, and scaffold templates.

**Architecture:** The signal layer remains a pure decision boundary: it reads a normalized strategy context and emits `SignalResult` with intent, entry mode, score, confidence, reasons, required state, and replay metadata. It does not size positions, set stops or take-profits, place orders, mutate portfolio state, or modify live execution.

**Tech Stack:** Python dataclasses, standard-library JSON scripts, pytest.

---

### Task 1: Signal Engine Contract And Decisions

**Files:**
- Modify: `src/signals/signal_engine.py`
- Test: `tests/test_signal_engine.py`
- Modify: `tests/test_describe_multi_tf_rules.py`

- [ ] **Step 1: Write failing tests for structured signal results**

Add tests that build dictionary contexts and assert:

```python
def test_direct_long_records_evidence_and_required_state():
    result = generate_signal(base_context())
    assert result.signal_type == "LONG"
    assert result.signal_side == "LONG"
    assert result.entry_mode == "DIRECT"
    assert result.required_state == "DIRECT_LONG"
    assert result["side"] == "LONG"
    assert "TREND_ALIGNED" in result.sub_reasons
    assert result.metadata["evidence"]["trigger_state_15m"] == "LONG"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_signal_engine.py -q`

Expected: FAIL because the current module only returns a small dictionary and does not expose `SignalResult`.

- [ ] **Step 3: Implement the signal contract**

Replace `src/signals/signal_engine.py` with dataclasses and deterministic helpers:

```python
@dataclass(frozen=True)
class SignalResult:
    symbol: str
    timestamp: Any
    signal_type: str
    signal_side: str
    entry_mode: str
    score: float
    confidence: float
    reason: str
    sub_reasons: tuple[str, ...]
    required_state: str
    quality_flag: bool
    metadata: dict[str, Any]

    def __getitem__(self, key: str) -> Any:
        if key == "side":
            return self.signal_side
        return self.to_dict()[key]
```

`generate_signal(context)` must support both the new strategy-context field names and the older multi-timeframe decision object by mapping legacy `DIRECT`/`PROBE` into `entry_mode`.

- [ ] **Step 4: Run signal tests**

Run: `pytest tests/test_signal_engine.py tests/test_describe_multi_tf_rules.py -q`

Expected: PASS.

### Task 2: Signal Engine Describe Script

**Files:**
- Create: `scripts/describe_signal_engine.py`
- Test: `tests/test_describe_signal_engine.py`

- [ ] **Step 1: Write failing describe-script tests**

Add a subprocess test that asserts the JSON exposes:

```python
assert payload["allowed_outputs"]["signal_type"] == ["LONG", "SHORT", "WAIT", "NO_TRADE"]
assert payload["allowed_outputs"]["entry_mode"] == ["PROBE", "DIRECT", "NONE"]
assert payload["state_machine_mapping"]["DIRECT"] == "DIRECT_*"
assert "execution layer" in payload["forbidden_actions"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_describe_signal_engine.py -q`

Expected: FAIL because the script does not exist.

- [ ] **Step 3: Implement `scripts/describe_signal_engine.py`**

The script imports public constants from `src.signals.signal_engine` and prints sorted JSON containing decision flow, timeframe roles, indicator roles, score components, standard sub-reasons, state mapping, evidence fields, forbidden actions, downgrade policies, and a sample direct long.

- [ ] **Step 4: Run describe tests**

Run: `pytest tests/test_describe_signal_engine.py -q`

Expected: PASS.

### Task 3: Scaffold Template Sync

**Files:**
- Modify: `scripts/scaffold_ai300_framework.py`
- Test: `tests/test_framework_scaffold.py`

- [ ] **Step 1: Add scaffold assertions**

Extend scaffold checks so generated templates include `src/signals/signal_engine.py`, `scripts/describe_signal_engine.py`, and `tests/test_signal_engine.py`.

- [ ] **Step 2: Sync templates**

Update the `FILES` mapping in `scripts/scaffold_ai300_framework.py` with the final signal engine module, describe script, and tests. Keep the existing protected Binance client guard unchanged.

- [ ] **Step 3: Run scaffold tests**

Run: `pytest tests/test_framework_scaffold.py tests/test_signal_engine.py tests/test_describe_signal_engine.py -q`

Expected: PASS.

### Task 4: Verification

**Files:**
- Read-only verification of `src/api/binance_client.py`

- [ ] **Step 1: Run targeted tests**

Run: `pytest tests/test_signal_engine.py tests/test_describe_signal_engine.py tests/test_describe_multi_tf_rules.py tests/test_framework_scaffold.py -q`

Expected: PASS.

- [ ] **Step 2: Run full tests**

Run: `pytest -q`

Expected: PASS.

- [ ] **Step 3: Compile Python files**

Run: `python -m compileall src scripts tests`

Expected: all files compile.

- [ ] **Step 4: Confirm Binance client untouched**

Run: `git diff -- src/api/binance_client.py`

Expected: no output.

- [ ] **Step 5: Remove generated cache directories**

Run:

```powershell
$root=(Resolve-Path '.').Path
$targets=Get-ChildItem -Path . -Recurse -Directory -Filter '__pycache__' | Where-Object { $_.FullName.StartsWith($root) }
foreach($target in $targets){ Remove-Item -LiteralPath $target.FullName -Recurse -Force }
```

Expected: no remaining `__pycache__` directories under the workspace.

---

## Scope Review

- Covered: structured `SignalResult`, LONG/SHORT/WAIT/NO_TRADE, PROBE/DIRECT/NONE, score components, evidence fields, data quality, cooldown, risk block, trend conflict, trigger readiness, CVD divergence, volatility downgrade, RSI anti-chase, BOLL extension downgrade, state-machine mapping, describe script, scaffold sync.
- Explicitly out of scope: position sizing, stop loss, take profit, order placement, balance sync, Binance adapter changes, live risk final verdict.
