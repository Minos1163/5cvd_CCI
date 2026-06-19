# Execution Engine Scripts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `docs/18_execution_engine.md` contract as executable Python scripts: a thin execution engine, a describe script, tests, and scaffold templates.

**Architecture:** Add `src/execution/execution_engine.py` above the existing `live_execution_contract.py`. The engine accepts standardized `ExecutionRequest`, validates it, builds idempotent `ExecutionResult`, delegates submit/cancel/sync to an injected adapter, records lifecycle/audit data, and never recalculates signal, risk, stop, or final quantity.

**Tech Stack:** Python dataclasses, standard-library JSON scripts, pytest, injected fake adapters for tests.

---

### Task 1: Execution Request, Result, And Thin Engine

**Files:**
- Create: `src/execution/execution_engine.py`
- Test: `tests/test_execution_engine.py`

- [ ] **Step 1: Write failing tests for normal execution**

Create tests that assert a clean market request validates, submits through a fake adapter, records lifecycle, and emits `ORDER_SUBMITTED`/`ORDER_FILLED`:

```python
def test_submit_market_order_records_result_lifecycle_and_events():
    engine = ExecutionEngine(FakeAdapter(submit_response={"order_id": "ord-1", "status": "filled", "filled_qty": 0.1, "avg_price": 50000}))
    result = engine.submit_order(valid_request())
    assert result.status == "filled"
    assert result.client_order_id == "BTCUSDT:evt-1:DIRECT_LONG:BUY:DIRECT"
    assert [item["state"] for item in result.lifecycle] == ["created", "validated", "submitted", "acknowledged", "filled"]
    assert result.events == ["ORDER_SUBMITTED", "ORDER_FILLED"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_execution_engine.py -q`

Expected: FAIL because `src.execution.execution_engine` does not exist.

- [ ] **Step 3: Implement execution dataclasses and submit flow**

Create:

```python
@dataclass(frozen=True)
class ExecutionRequest: ...

@dataclass(frozen=True)
class ExecutionResult: ...

class ExecutionEngine:
    def submit_order(self, request: ExecutionRequest) -> ExecutionResult: ...
```

The engine should call `validate_execution_instruction()`, build a stable client order id, call `adapter.submit(instruction)`, normalize status, build lifecycle rows, audit logs, and events. It must not import `src.api.binance_client`.

- [ ] **Step 4: Run execution tests**

Run: `pytest tests/test_execution_engine.py -q`

Expected: PASS for normal submit behavior.

### Task 2: Rejections, Partial Fills, Idempotency, Cancel, Sync, Retry, Protection Mode

**Files:**
- Modify: `tests/test_execution_engine.py`
- Modify: `src/execution/execution_engine.py`

- [ ] **Step 1: Add failing tests for required 18 execution cases**

Cover:

```python
def test_idempotent_duplicate_request_returns_cached_result():
    engine = ExecutionEngine(FakeAdapter())
    first = engine.submit_order(valid_request())
    second = engine.submit_order(valid_request())
    assert first is second
    assert engine.adapter.submit_calls == 1

def test_reject_partial_cancel_sync_retry_and_protection_paths():
    assert engine.submit_order(valid_request(quantity=0)).status == "rejected"
    assert partial_result.status == "partially_filled"
    assert cancel_result.status == "canceled"
    assert sync_failure.protection_mode is True
    assert retry_result.metadata["retry_count"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_execution_engine.py -q`

Expected: FAIL until rejection, idempotency, cancel, sync, retry, and protection paths exist.

- [ ] **Step 3: Implement bounded behaviors**

Implement:
- validation rejection without adapter submit
- partial fill snapshot
- idempotent result cache by `symbol:event_id:strategy_state:side:entry_mode`
- `cancel_order(request_id, symbol, order_id)`
- `sync_position(symbol=None)`
- retry only for recoverable errors: timeout, temporary unavailable, query delay
- protection mode when rejects/sync/protection failures exceed threshold or order state is unknown

- [ ] **Step 4: Run execution tests**

Run: `pytest tests/test_execution_engine.py -q`

Expected: PASS.

### Task 3: Execution Engine Describe Script

**Files:**
- Create: `scripts/describe_execution_engine.py`
- Test: `tests/test_describe_execution_engine.py`

- [ ] **Step 1: Write failing describe-script tests**

Add a subprocess test:

```python
assert payload["engine"] == "execution_engine"
assert payload["order_lifecycle_states"][0] == "created"
assert payload["idempotency_key"] == "symbol + event_id + strategy_state + side + entry_mode"
assert "ORDER_FILLED" in payload["event_types"]
assert payload["binance_client_policy"] == "thin injected adapter only; do not modify stable client"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_describe_execution_engine.py -q`

Expected: FAIL because the script does not exist.

- [ ] **Step 3: Implement `scripts/describe_execution_engine.py`**

The script imports public constants from `src.execution.execution_engine` and `live_execution_contract`, then prints JSON containing responsibilities, input/output fields, lifecycle states, supported order types, pre-execution checks, retry policy, protection mode triggers, event types, log fields, observability metrics, forbidden actions, and sample result.

- [ ] **Step 4: Run describe tests**

Run: `pytest tests/test_describe_execution_engine.py -q`

Expected: PASS.

### Task 4: Scaffold Template Sync

**Files:**
- Modify: `scripts/scaffold_ai300_framework.py`
- Test: `tests/test_framework_scaffold.py`

- [ ] **Step 1: Add scaffold assertions**

Extend scaffold checks:

```python
def test_scaffold_includes_execution_engine_18_templates():
    assert "src/execution/execution_engine.py" in FILES
    assert "scripts/describe_execution_engine.py" in FILES
    assert "tests/test_execution_engine.py" in FILES
    assert "tests/test_describe_execution_engine.py" in FILES
    assert "ExecutionEngine" in FILES["src/execution/execution_engine.py"]
```

- [ ] **Step 2: Sync templates**

Update the `FILES` mapping in `scripts/scaffold_ai300_framework.py` with the final execution engine module, describe script, and tests. Keep the protected Binance client guard unchanged.

- [ ] **Step 3: Run scaffold tests**

Run: `pytest tests/test_framework_scaffold.py tests/test_execution_engine.py tests/test_describe_execution_engine.py -q`

Expected: PASS.

### Task 5: Verification

**Files:**
- Read-only verification of `src/api/binance_client.py`

- [ ] **Step 1: Run targeted tests**

Run: `pytest tests/test_execution_engine.py tests/test_describe_execution_engine.py tests/test_live_execution_contract.py tests/test_framework_scaffold.py -q`

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

- Covered: standardized execution request/result, thin adapter boundary, pre-execution validation, lifecycle, submit/cancel/query/sync representation, partial fills, rejection normalization, idempotency, bounded retry, protection mode, logs, events, observability, describe script, scaffold sync.
- Explicitly out of scope: live Binance order submission wiring, strategy/risk/position recalculation, exchange precision correction, database writes, WebSocket listeners, and any modification to `src/api/binance_client.py`.
