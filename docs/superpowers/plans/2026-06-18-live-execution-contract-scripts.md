# Live Execution Contract Scripts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the scripts required by `docs/10_live_execution_contract.md`.

**Architecture:** Add a pure contract module under `src/execution/live_execution_contract.py` that defines execution instructions, standardized responses, lifecycle records, validation gates, idempotency keys, reject normalization, and protection-mode checks. Keep the existing `binance_client.py` untouched and keep `BinanceAdapter.submit()` disabled; this work only prepares a thin, auditable adapter contract above the stable client.

**Tech Stack:** Python standard library, dataclasses, pytest.

---

## Scope Notes

`docs/10_live_execution_contract.md` defines the live execution boundary. The implementation must enforce the boundary without enabling live trading:

- Execution layer must not make strategy, indicator, sizing, state-machine, or risk decisions.
- Inputs and outputs must be structured.
- Order status, order type, reject reasons, lifecycle events, logs, metrics, and protection-mode triggers must use stable contract lists.
- Validation must reject malformed execution instructions before any adapter call.
- Idempotency must prevent duplicate execution actions for the same strategy event/state/side.
- Partial fills, rejected orders, protection order failures, sync failures, and unknown order states must be represented as data and surfaced upward.

This plan does not call Binance, place orders, set leverage on exchange, fetch balances, persist logs to a database, or implement an async order manager.

## File Structure

- Create: `src/execution/live_execution_contract.py` - execution contract dataclasses, constants, validators, idempotency, lifecycle, response, and protection-mode helpers.
- Create: `scripts/describe_live_execution_contract.py` - prints the completed 10 contract as JSON.
- Create: `tests/test_live_execution_contract.py` - tests required fields, validation, idempotency, lifecycle logs, reject normalization, partial fills, and protection mode.
- Create: `tests/test_describe_live_execution_contract.py` - tests describe script JSON output.
- Modify: `scripts/scaffold_ai300_framework.py` - sync templates for new module, script, and tests.
- Preserve: `src/api/binance_client.py` - do not modify the stable Binance client.

---

### Task 1: Contract Constants and Dataclasses

**Files:**

- Create: `src/execution/live_execution_contract.py`
- Create: `tests/test_live_execution_contract.py`

- [ ] **Step 1: Write failing tests for required fields and typed records**

Create `tests/test_live_execution_contract.py`:

```python
from src.execution.live_execution_contract import (
    EXECUTION_FORBIDDEN_ACTIONS,
    EXECUTION_INPUT_FIELDS,
    EXECUTION_LOG_FIELDS,
    EXECUTION_OUTPUT_FIELDS,
    EXECUTION_RESPONSIBILITIES,
    OBSERVABILITY_METRICS,
    ORDER_LIFECYCLE_STATES,
    SUPPORTED_ORDER_TYPES,
    ExecutionInstruction,
    ExecutionResponse,
    LifecycleEvent,
)


def test_live_execution_contract_lists_doc_fields_and_boundaries():
    assert EXECUTION_RESPONSIBILITIES == [
        "create_order",
        "cancel_order",
        "query_order_status",
        "query_position_status",
        "sync_account_info",
        "sync_leverage_and_margin",
        "maintain_order_lifecycle_log",
        "return_raw_exchange_response",
        "standardize_execution_error",
    ]
    assert EXECUTION_INPUT_FIELDS == [
        "symbol",
        "side",
        "order_type",
        "quantity",
        "price",
        "reduce_only",
        "position_side",
        "time_in_force",
        "stop_price",
        "take_profit_price",
        "client_order_id",
        "strategy_event_id",
        "strategy_state",
        "expected_position_side",
        "expected_risk_tag",
    ]
    assert EXECUTION_OUTPUT_FIELDS == [
        "order_id",
        "client_order_id",
        "status",
        "filled_qty",
        "avg_price",
        "commission",
        "executed_notional",
        "reject_reason",
        "raw_response",
        "latency_ms",
        "ts",
    ]
    assert SUPPORTED_ORDER_TYPES == ["MARKET", "LIMIT", "IOC", "STOP_MARKET", "TAKE_PROFIT_MARKET"]
    assert ORDER_LIFECYCLE_STATES == [
        "created",
        "validated",
        "submitted",
        "acknowledged",
        "partially_filled",
        "filled",
        "canceled",
        "rejected",
        "expired",
        "reconciled",
    ]
    assert "execution layer changes order quantity" in EXECUTION_FORBIDDEN_ACTIONS
    assert "order_success_rate" in OBSERVABILITY_METRICS


def test_execution_records_round_trip_to_dict():
    instruction = ExecutionInstruction(
        symbol="BTCUSDT",
        side="BUY",
        order_type="MARKET",
        quantity=0.1,
        price=None,
        reduce_only=False,
        position_side="LONG",
        time_in_force=None,
        stop_price=95_000,
        take_profit_price=110_000,
        client_order_id="cli-1",
        strategy_event_id="evt-1",
        strategy_state="DIRECT_LONG",
        expected_position_side="LONG",
        expected_risk_tag="entry",
    )
    response = ExecutionResponse(
        order_id="1",
        client_order_id="cli-1",
        status="created",
        filled_qty=0,
        avg_price=0,
        commission=0,
        executed_notional=0,
        reject_reason="",
        raw_response={"ok": True},
        latency_ms=12,
        ts=1_700_000_000,
    )
    event = LifecycleEvent("cli-1", "created", 1_700_000_000, "instruction accepted")
    assert instruction.to_dict()["strategy_event_id"] == "evt-1"
    assert response.to_dict()["status"] == "created"
    assert event.to_dict()["state"] == "created"
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_live_execution_contract.py -q`

Expected: FAIL because the module does not exist.

- [ ] **Step 3: Implement constants and dataclasses**

Create `src/execution/live_execution_contract.py`:

```python
from __future__ import annotations

from dataclasses import asdict, dataclass


EXECUTION_RESPONSIBILITIES = [
    "create_order",
    "cancel_order",
    "query_order_status",
    "query_position_status",
    "sync_account_info",
    "sync_leverage_and_margin",
    "maintain_order_lifecycle_log",
    "return_raw_exchange_response",
    "standardize_execution_error",
]
EXECUTION_INPUT_FIELDS = [
    "symbol",
    "side",
    "order_type",
    "quantity",
    "price",
    "reduce_only",
    "position_side",
    "time_in_force",
    "stop_price",
    "take_profit_price",
    "client_order_id",
    "strategy_event_id",
    "strategy_state",
    "expected_position_side",
    "expected_risk_tag",
]
EXECUTION_OUTPUT_FIELDS = [
    "order_id",
    "client_order_id",
    "status",
    "filled_qty",
    "avg_price",
    "commission",
    "executed_notional",
    "reject_reason",
    "raw_response",
    "latency_ms",
    "ts",
]
SUPPORTED_ORDER_TYPES = ["MARKET", "LIMIT", "IOC", "STOP_MARKET", "TAKE_PROFIT_MARKET"]
ORDER_LIFECYCLE_STATES = [
    "created",
    "validated",
    "submitted",
    "acknowledged",
    "partially_filled",
    "filled",
    "canceled",
    "rejected",
    "expired",
    "reconciled",
]
EXECUTION_LOG_FIELDS = [
    "ts",
    "module",
    "symbol",
    "action",
    "order_type",
    "side",
    "quantity",
    "price",
    "reduce_only",
    "position_side",
    "client_order_id",
    "strategy_event_id",
    "status",
    "reject_reason",
    "order_id",
    "filled_qty",
    "avg_price",
    "commission",
    "latency_ms",
    "raw_response",
]
OBSERVABILITY_METRICS = [
    "order_success_rate",
    "reject_rate",
    "average_latency_ms",
    "protection_order_success_rate",
    "partial_fill_ratio",
    "order_retry_count",
    "sync_failure_count",
    "recovery_time_ms",
]
EXECUTION_FORBIDDEN_ACTIONS = [
    "execution layer changes strategy intent",
    "execution layer changes order quantity",
    "execution layer recalculates position size",
    "execution layer changes strategy state",
    "execution layer swallows exchange errors",
    "execution layer retries as a new strategy",
]


@dataclass(frozen=True)
class ExecutionInstruction:
    symbol: str
    side: str
    order_type: str
    quantity: float
    price: float | None
    reduce_only: bool
    position_side: str
    time_in_force: str | None
    stop_price: float | None
    take_profit_price: float | None
    client_order_id: str
    strategy_event_id: str
    strategy_state: str
    expected_position_side: str
    expected_risk_tag: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ExecutionResponse:
    order_id: str
    client_order_id: str
    status: str
    filled_qty: float
    avg_price: float
    commission: float
    executed_notional: float
    reject_reason: str
    raw_response: dict
    latency_ms: int
    ts: int

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class LifecycleEvent:
    client_order_id: str
    state: str
    ts: int
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_live_execution_contract.py -q`

Expected: PASS for constants and dataclasses.

---

### Task 2: Validation, Idempotency, and Standardized Rejects

**Files:**

- Modify: `src/execution/live_execution_contract.py`
- Modify: `tests/test_live_execution_contract.py`

- [ ] **Step 1: Add failing tests for validation and idempotency**

Append to `tests/test_live_execution_contract.py`:

```python
from src.execution.live_execution_contract import (
    ExecutionValidation,
    build_idempotency_key,
    normalize_reject_reason,
    validate_execution_instruction,
)


def valid_instruction(**overrides):
    values = {
        "symbol": "BTCUSDT",
        "side": "BUY",
        "order_type": "MARKET",
        "quantity": 0.1,
        "price": None,
        "reduce_only": False,
        "position_side": "LONG",
        "time_in_force": None,
        "stop_price": 95_000,
        "take_profit_price": 110_000,
        "client_order_id": "cli-1",
        "strategy_event_id": "evt-1",
        "strategy_state": "DIRECT_LONG",
        "expected_position_side": "LONG",
        "expected_risk_tag": "entry",
    }
    values.update(overrides)
    return ExecutionInstruction(**values)


def test_validate_execution_instruction_approves_clean_market_order():
    validation = validate_execution_instruction(
        valid_instruction(),
        tradable=True,
        in_trade_window=True,
        leverage_ready=True,
        min_notional=5,
        quantity_step=0.001,
        current_position_side="LONG",
        account_risk_allows=True,
        symbol_cooldown_active=False,
    )
    assert validation == ExecutionValidation(True, "validated")


def test_validate_execution_instruction_rejects_bad_side_type_qty_and_reduce_only():
    assert validate_execution_instruction(valid_instruction(side="HOLD")).passed is False
    assert validate_execution_instruction(valid_instruction(order_type="POST_ONLY")).passed is False
    assert validate_execution_instruction(valid_instruction(quantity=0)).passed is False
    assert validate_execution_instruction(
        valid_instruction(reduce_only=True, expected_risk_tag="entry")
    ).passed is False


def test_validate_execution_instruction_rejects_precision_min_notional_and_context_gates():
    assert validate_execution_instruction(
        valid_instruction(quantity=0.1005), quantity_step=0.001
    ).passed is False
    assert validate_execution_instruction(
        valid_instruction(quantity=0.001, price=100, order_type="LIMIT"), min_notional=5
    ).passed is False
    assert validate_execution_instruction(valid_instruction(), tradable=False).passed is False
    assert validate_execution_instruction(valid_instruction(), in_trade_window=False).passed is False
    assert validate_execution_instruction(valid_instruction(), leverage_ready=False).passed is False
    assert validate_execution_instruction(valid_instruction(), account_risk_allows=False).passed is False
    assert validate_execution_instruction(valid_instruction(), symbol_cooldown_active=True).passed is False


def test_idempotency_key_and_reject_normalization_are_stable():
    instruction = valid_instruction()
    assert build_idempotency_key(instruction) == "BTCUSDT:evt-1:DIRECT_LONG:BUY"
    assert normalize_reject_reason("-2019 margin insufficient") == "INSUFFICIENT_MARGIN"
    assert normalize_reject_reason("precision over maximum") == "PRECISION_ERROR"
    assert normalize_reject_reason("timeout waiting exchange") == "NETWORK_TIMEOUT"
    assert normalize_reject_reason("anything else") == "EXCHANGE_ERROR"
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_live_execution_contract.py -q`

Expected: FAIL because validation helpers do not exist.

- [ ] **Step 3: Implement validation and idempotency helpers**

Append to `src/execution/live_execution_contract.py`:

```python
@dataclass(frozen=True)
class ExecutionValidation:
    passed: bool
    reason: str


def build_idempotency_key(instruction: ExecutionInstruction) -> str:
    return ":".join(
        [
            instruction.symbol.strip().upper(),
            instruction.strategy_event_id,
            instruction.strategy_state,
            instruction.side.strip().upper(),
        ]
    )


def normalize_reject_reason(raw_message: str) -> str:
    text = raw_message.lower()
    if "timeout" in text:
        return "NETWORK_TIMEOUT"
    if "margin" in text or "-2019" in text:
        return "INSUFFICIENT_MARGIN"
    if "precision" in text:
        return "PRECISION_ERROR"
    if "leverage" in text:
        return "LEVERAGE_ERROR"
    if "reduce" in text:
        return "REDUCE_ONLY_ERROR"
    return "EXCHANGE_ERROR"


def validate_execution_instruction(
    instruction: ExecutionInstruction,
    *,
    tradable: bool = True,
    in_trade_window: bool = True,
    leverage_ready: bool = True,
    min_notional: float = 5.0,
    quantity_step: float = 0.0,
    current_position_side: str | None = None,
    account_risk_allows: bool = True,
    symbol_cooldown_active: bool = False,
) -> ExecutionValidation:
    side = instruction.side.strip().upper()
    order_type = instruction.order_type.strip().upper()
    if side not in {"BUY", "SELL"}:
        return ExecutionValidation(False, "side must be BUY or SELL")
    if order_type not in SUPPORTED_ORDER_TYPES:
        return ExecutionValidation(False, "unsupported order_type")
    if instruction.quantity <= 0:
        return ExecutionValidation(False, "quantity must be positive")
    if quantity_step > 0 and int(instruction.quantity / quantity_step) * quantity_step != instruction.quantity:
        return ExecutionValidation(False, "quantity precision is invalid")
    reference_price = instruction.price or instruction.stop_price or instruction.take_profit_price
    if reference_price is not None and instruction.quantity * reference_price < min_notional:
        return ExecutionValidation(False, "minimum notional not satisfied")
    if instruction.reduce_only and instruction.expected_risk_tag.lower() == "entry":
        return ExecutionValidation(False, "entry orders must not be reduce_only")
    if current_position_side is not None and current_position_side.upper() != instruction.expected_position_side.upper():
        return ExecutionValidation(False, "current position side mismatch")
    if not tradable:
        return ExecutionValidation(False, "symbol is not tradable")
    if not in_trade_window:
        return ExecutionValidation(False, "outside tradable execution window")
    if not leverage_ready:
        return ExecutionValidation(False, "leverage is not ready")
    if not account_risk_allows:
        return ExecutionValidation(False, "account risk blocks execution")
    if symbol_cooldown_active:
        return ExecutionValidation(False, "symbol execution cooldown is active")
    return ExecutionValidation(True, "validated")
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_live_execution_contract.py -q`

Expected: PASS.

---

### Task 3: Lifecycle, Partial Fill, Logs, and Protection Mode

**Files:**

- Modify: `src/execution/live_execution_contract.py`
- Modify: `tests/test_live_execution_contract.py`

- [ ] **Step 1: Add failing tests for lifecycle, partial fill, logs, and protection mode**

Append to `tests/test_live_execution_contract.py`:

```python
from src.execution.live_execution_contract import (
    PROTECTION_MODE_TRIGGERS,
    build_execution_log,
    build_partial_fill_snapshot,
    lifecycle_transition,
    should_enter_protection_mode,
)


def test_lifecycle_transition_and_execution_log_fields_are_replayable():
    instruction = valid_instruction()
    response = ExecutionResponse(
        order_id="1",
        client_order_id="cli-1",
        status="acknowledged",
        filled_qty=0,
        avg_price=0,
        commission=0,
        executed_notional=0,
        reject_reason="",
        raw_response={"orderId": 1},
        latency_ms=20,
        ts=1_700_000_001,
    )
    event = lifecycle_transition("cli-1", "submitted", "acknowledged", 1_700_000_001, "exchange ack")
    assert event.state == "acknowledged"
    log = build_execution_log(instruction, response, action="create_order", module="execution")
    assert list(log) == EXECUTION_LOG_FIELDS
    assert log["raw_response"] == {"orderId": 1}


def test_lifecycle_transition_rejects_unknown_or_regressive_state():
    assert lifecycle_transition("cli-1", "created", "validated", 1, "ok").state == "validated"
    try:
        lifecycle_transition("cli-1", "submitted", "created", 1, "bad")
    except ValueError as exc:
        assert "regress" in str(exc)
    else:
        raise AssertionError("expected regression rejection")
    try:
        lifecycle_transition("cli-1", "created", "unknown", 1, "bad")
    except ValueError as exc:
        assert "unknown lifecycle state" in str(exc)
    else:
        raise AssertionError("expected unknown state rejection")


def test_partial_fill_snapshot_keeps_remaining_quantity_for_upper_layer():
    snapshot = build_partial_fill_snapshot(
        order_qty=1.0,
        filled_qty=0.4,
        avg_price=100,
        client_order_id="cli-1",
    )
    assert snapshot == {
        "client_order_id": "cli-1",
        "order_qty": 1.0,
        "filled_qty": 0.4,
        "remaining_qty": 0.6,
        "avg_price": 100,
        "status": "partially_filled",
    }


def test_protection_mode_triggers_on_consecutive_failures_and_unknown_state():
    assert PROTECTION_MODE_TRIGGERS == [
        "consecutive_rejects",
        "consecutive_sync_failures",
        "consecutive_protection_order_failures",
        "abnormal_position_state",
        "unknown_order_state",
        "exchange_unavailable",
    ]
    assert should_enter_protection_mode(consecutive_rejects=3).passed is True
    assert should_enter_protection_mode(consecutive_sync_failures=3).passed is True
    assert should_enter_protection_mode(consecutive_protection_order_failures=3).passed is True
    assert should_enter_protection_mode(abnormal_position_state=True).passed is True
    assert should_enter_protection_mode(unknown_order_state=True).passed is True
    assert should_enter_protection_mode(exchange_unavailable=True).passed is True
    assert should_enter_protection_mode().passed is False
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_live_execution_contract.py -q`

Expected: FAIL because lifecycle helpers are missing.

- [ ] **Step 3: Implement lifecycle, logging, partial fill, and protection helpers**

Append to `src/execution/live_execution_contract.py`:

```python
PROTECTION_MODE_TRIGGERS = [
    "consecutive_rejects",
    "consecutive_sync_failures",
    "consecutive_protection_order_failures",
    "abnormal_position_state",
    "unknown_order_state",
    "exchange_unavailable",
]


def lifecycle_transition(
    client_order_id: str,
    previous_state: str,
    next_state: str,
    ts: int,
    reason: str,
) -> LifecycleEvent:
    if previous_state not in ORDER_LIFECYCLE_STATES or next_state not in ORDER_LIFECYCLE_STATES:
        raise ValueError("unknown lifecycle state")
    if ORDER_LIFECYCLE_STATES.index(next_state) < ORDER_LIFECYCLE_STATES.index(previous_state):
        raise ValueError("order lifecycle must not regress")
    return LifecycleEvent(client_order_id, next_state, ts, reason)


def build_execution_log(
    instruction: ExecutionInstruction,
    response: ExecutionResponse,
    *,
    action: str,
    module: str = "execution",
) -> dict:
    return {
        "ts": response.ts,
        "module": module,
        "symbol": instruction.symbol,
        "action": action,
        "order_type": instruction.order_type,
        "side": instruction.side,
        "quantity": instruction.quantity,
        "price": instruction.price,
        "reduce_only": instruction.reduce_only,
        "position_side": instruction.position_side,
        "client_order_id": instruction.client_order_id,
        "strategy_event_id": instruction.strategy_event_id,
        "status": response.status,
        "reject_reason": response.reject_reason,
        "order_id": response.order_id,
        "filled_qty": response.filled_qty,
        "avg_price": response.avg_price,
        "commission": response.commission,
        "latency_ms": response.latency_ms,
        "raw_response": response.raw_response,
    }


def build_partial_fill_snapshot(
    *,
    order_qty: float,
    filled_qty: float,
    avg_price: float,
    client_order_id: str,
) -> dict:
    return {
        "client_order_id": client_order_id,
        "order_qty": order_qty,
        "filled_qty": filled_qty,
        "remaining_qty": order_qty - filled_qty,
        "avg_price": avg_price,
        "status": "partially_filled",
    }


def should_enter_protection_mode(
    *,
    consecutive_rejects: int = 0,
    consecutive_sync_failures: int = 0,
    consecutive_protection_order_failures: int = 0,
    abnormal_position_state: bool = False,
    unknown_order_state: bool = False,
    exchange_unavailable: bool = False,
    threshold: int = 3,
) -> ExecutionValidation:
    if consecutive_rejects >= threshold:
        return ExecutionValidation(True, "consecutive rejects")
    if consecutive_sync_failures >= threshold:
        return ExecutionValidation(True, "consecutive sync failures")
    if consecutive_protection_order_failures >= threshold:
        return ExecutionValidation(True, "consecutive protection order failures")
    if abnormal_position_state:
        return ExecutionValidation(True, "abnormal position state")
    if unknown_order_state:
        return ExecutionValidation(True, "unknown order state")
    if exchange_unavailable:
        return ExecutionValidation(True, "exchange unavailable")
    return ExecutionValidation(False, "normal")
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_live_execution_contract.py -q`

Expected: PASS.

---

### Task 4: Describe Script

**Files:**

- Create: `scripts/describe_live_execution_contract.py`
- Create: `tests/test_describe_live_execution_contract.py`

- [ ] **Step 1: Add failing describe script test**

Create `tests/test_describe_live_execution_contract.py`:

```python
import json
import subprocess
import sys


def test_describe_live_execution_contract_outputs_completed_10_sections():
    completed = subprocess.run(
        [sys.executable, "scripts/describe_live_execution_contract.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["input_fields"][0] == "symbol"
    assert payload["output_fields"][0] == "order_id"
    assert payload["supported_order_types"] == ["MARKET", "LIMIT", "IOC", "STOP_MARKET", "TAKE_PROFIT_MARKET"]
    assert payload["lifecycle_states"][0] == "created"
    assert payload["idempotency_key"] == "symbol + strategy_event_id + strategy_state + side"
    assert payload["protection_mode_triggers"][-1] == "exchange_unavailable"
    assert "execution layer changes order quantity" in payload["forbidden"]
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_describe_live_execution_contract.py -q`

Expected: FAIL because the describe script does not exist.

- [ ] **Step 3: Implement describe script**

Create `scripts/describe_live_execution_contract.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.execution.live_execution_contract import (
    EXECUTION_FORBIDDEN_ACTIONS,
    EXECUTION_INPUT_FIELDS,
    EXECUTION_LOG_FIELDS,
    EXECUTION_OUTPUT_FIELDS,
    EXECUTION_RESPONSIBILITIES,
    OBSERVABILITY_METRICS,
    ORDER_LIFECYCLE_STATES,
    PROTECTION_MODE_TRIGGERS,
    SUPPORTED_ORDER_TYPES,
)


def main() -> None:
    payload = {
        "responsibilities": EXECUTION_RESPONSIBILITIES,
        "input_fields": EXECUTION_INPUT_FIELDS,
        "output_fields": EXECUTION_OUTPUT_FIELDS,
        "supported_order_types": SUPPORTED_ORDER_TYPES,
        "lifecycle_states": ORDER_LIFECYCLE_STATES,
        "idempotency_key": "symbol + strategy_event_id + strategy_state + side",
        "pre_execution_checks": [
            "tradable",
            "trade_window",
            "leverage_ready",
            "quantity_precision",
            "minimum_notional",
            "reduce_only",
            "position_side",
            "current_position_side",
            "account_risk",
            "symbol_cooldown",
        ],
        "log_fields": EXECUTION_LOG_FIELDS,
        "observability_metrics": OBSERVABILITY_METRICS,
        "protection_mode_triggers": PROTECTION_MODE_TRIGGERS,
        "forbidden": EXECUTION_FORBIDDEN_ACTIONS,
        "binance_client_policy": "thin adapter only; do not modify strategy, risk, state, or sizing logic",
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_live_execution_contract.py tests/test_describe_live_execution_contract.py -q`

Expected: PASS.

---

### Task 5: Scaffold Sync and Verification

**Files:**

- Modify: `scripts/scaffold_ai300_framework.py`

- [ ] **Step 1: Sync scaffold templates**

Copy final contents of these files into `scripts/scaffold_ai300_framework.py`:

- `src/execution/live_execution_contract.py`
- `scripts/describe_live_execution_contract.py`
- `tests/test_live_execution_contract.py`
- `tests/test_describe_live_execution_contract.py`

- [ ] **Step 2: Run targeted tests**

Run: `pytest tests/test_live_execution_contract.py tests/test_describe_live_execution_contract.py tests/test_framework_scaffold.py -q`

Expected: PASS.

- [ ] **Step 3: Run full verification**

Run:

```bash
pytest -q
python -m compileall src scripts tests
python scripts/describe_live_execution_contract.py
git diff -- src/api/binance_client.py
```

Expected: all tests pass, compile succeeds, describe JSON includes completed 10 sections, and Binance diff has no output.

- [ ] **Step 4: Clean generated caches**

Run:

```powershell
$root=(Resolve-Path '.').Path; $targets=Get-ChildItem -Path . -Recurse -Directory -Filter '__pycache__' | Where-Object { $_.FullName.StartsWith($root) }; foreach($target in $targets){ Remove-Item -LiteralPath $target.FullName -Recurse -Force }; Get-ChildItem -Path . -Recurse -Directory -Filter '__pycache__' | Select-Object -ExpandProperty FullName
```

Expected: no remaining `__pycache__` directories in the workspace.

---

## Self-Review

- Spec coverage: covers execution boundary, responsibilities, forbidden behaviors, structured input/output, supported order types, lifecycle states, idempotency key, pre-execution validation, position-side/reduce-only safety checks, partial fills, reject normalization, cancellation/sync representation through contract fields, exception categories, cooldown context, log fields, observability metrics, protection-mode triggers, and binance-client thin-adapter policy.
- Placeholder scan: no `TBD`, `TODO`, `implement later`, or unspecified test steps.
- Type consistency: `ExecutionInstruction`, `ExecutionResponse`, `LifecycleEvent`, `ExecutionValidation`, `validate_execution_instruction`, `build_idempotency_key`, `build_execution_log`, and `should_enter_protection_mode` are named consistently across tasks.
