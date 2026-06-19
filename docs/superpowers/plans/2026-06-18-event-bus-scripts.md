# Event Bus Scripts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the scripts required by `docs/14_event_bus_spec.md`.

**Architecture:** Extend the existing `src/core/events.py` module into a deterministic in-memory event contract and bus while preserving the old `EventType` and `Event` imports. Keep the event bus infrastructure pure and dependency-light: handlers receive structured events, return explicit results, failed handling is recorded in a dead-letter queue, and replay uses the same publish path.

**Tech Stack:** Python standard library, dataclasses, enum, collections, pytest.

---

## Scope Notes

`docs/14_event_bus_spec.md` requires:

- Structured event names, categories, priorities, lifecycle states, and error categories.
- A standard event shape with `event_id`, `event_type`, `ts`, `source`, `symbol`, `timeframe`, `version`, `payload`, `priority`, `correlation_id`, `parent_event_id`, `trace_id`, and `status`.
- A handler interface returning `success`, `next_events`, `logs`, `errors`, and `metadata`.
- Synchronous dispatch, subscription/filtering, event logging, replay, deduplication, idempotency, and dead-letter handling.
- A describe script that outputs the completed EventBus contract.

This plan implements a synchronous in-memory bus suitable for tests, backtests, and deterministic local use. It does not add live async workers, disk persistence, Parquet export, or production monitoring.

## File Structure

- Modify: `src/core/events.py` - event enums, structured event record, handler result, in-memory event store, replay filters, and synchronous EventBus.
- Create: `scripts/describe_event_bus_spec.py` - prints the completed 14 EventBus contract as JSON.
- Create: `tests/test_event_bus_spec.py` - tests event constants, event serialization, subscription/publish behavior, dedupe/idempotency, replay filters, priority ordering, and dead-letter handling.
- Create: `tests/test_describe_event_bus_spec.py` - tests describe script JSON output.
- Modify: `scripts/scaffold_ai300_framework.py` - sync templates for modified/new files.
- Preserve: `src/api/binance_client.py` - do not modify the stable Binance client.

---

### Task 1: Event Contract, Priorities, Lifecycle, and Serialization

**Files:**
- Modify: `src/core/events.py`
- Create: `tests/test_event_bus_spec.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_event_bus_spec.py`:

```python
from src.core.events import (
    EVENT_CATEGORIES,
    EVENT_DEDUPE_KEY_FIELDS,
    EVENT_ERROR_TYPES,
    EVENT_LIFECYCLE_STATES,
    EVENT_REQUIRED_FIELDS,
    KEY_EVENT_TYPES,
    Event,
    EventPriority,
    EventStatus,
    EventType,
)


def test_event_contract_constants_match_doc():
    assert KEY_EVENT_TYPES == [
        "MARKET_DATA_UPDATED",
        "INDICATOR_UPDATED",
        "MULTI_TF_CONTEXT_READY",
        "SIGNAL_CREATED",
        "WATCH_ENTERED",
        "PROBE_ENTERED",
        "DIRECT_ENTERED",
        "ORDER_SUBMITTED",
        "ORDER_FILLED",
        "ORDER_REJECTED",
        "POSITION_OPENED",
        "POSITION_REDUCED",
        "POSITION_CLOSED",
        "STOP_HIT",
        "TP_HIT",
        "RISK_BLOCKED",
        "COOLDOWN_STARTED",
        "COOLDOWN_ENDED",
        "BACKTEST_STEP_COMPLETED",
        "REPORT_GENERATED",
    ]
    assert EVENT_LIFECYCLE_STATES == [
        "created",
        "published",
        "dispatched",
        "handled",
        "persisted",
        "archived",
        "failed",
        "retried",
        "dead_lettered",
    ]
    assert EVENT_REQUIRED_FIELDS == [
        "event_id",
        "event_type",
        "ts",
        "source",
        "symbol",
        "timeframe",
        "version",
        "payload",
        "priority",
        "correlation_id",
        "parent_event_id",
        "trace_id",
        "status",
    ]
    assert EVENT_DEDUPE_KEY_FIELDS == ["symbol", "event_type", "strategy_event_id", "timeframe"]
    assert EVENT_ERROR_TYPES == [
        "INVALID_PAYLOAD",
        "UNKNOWN_EVENT_TYPE",
        "HANDLER_ERROR",
        "TIMEOUT",
        "DUPLICATE_EVENT",
        "STATE_CONFLICT",
        "DEPENDENCY_UNAVAILABLE",
    ]
    assert EVENT_CATEGORIES["Market Events"] == ["MARKET_DATA_UPDATED"]
    assert EVENT_CATEGORIES["Execution Events"] == ["ORDER_SUBMITTED", "ORDER_FILLED", "ORDER_REJECTED"]


def test_event_serializes_with_standard_fields_and_dedupe_key():
    event = Event(
        event_type=EventType.SIGNAL_CREATED,
        ts=1_700_000_000,
        source="signal_engine",
        symbol="BTCUSDT",
        timeframe="15m",
        payload={"strategy_event_id": "sig-1", "signal": "DIRECT_LONG"},
        priority=EventPriority.HIGH,
        correlation_id="corr-1",
        parent_event_id="evt-parent",
        trace_id="trace-1",
    )
    payload = event.to_dict()
    assert list(payload) == EVENT_REQUIRED_FIELDS
    assert payload["event_type"] == "SIGNAL_CREATED"
    assert payload["priority"] == "HIGH"
    assert payload["status"] == "created"
    assert event.dedupe_key() == "BTCUSDT:SIGNAL_CREATED:sig-1:15m"
    assert event.with_status(EventStatus.PUBLISHED).status == EventStatus.PUBLISHED
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_event_bus_spec.py -q`

Expected: FAIL because new constants, enums, and methods do not exist.

- [ ] **Step 3: Implement event contract**

Modify `src/core/events.py` by keeping existing names and adding:

```python
class EventPriority(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    NORMAL = "NORMAL"
    LOW = "LOW"


class EventStatus(str, Enum):
    CREATED = "created"
    PUBLISHED = "published"
    DISPATCHED = "dispatched"
    HANDLED = "handled"
    PERSISTED = "persisted"
    ARCHIVED = "archived"
    FAILED = "failed"
    RETRIED = "retried"
    DEAD_LETTERED = "dead_lettered"
    DUPLICATE = "duplicate"
```

Extend `EventType` with all key events from the doc while preserving old enum members. Replace the `Event` dataclass with a backward-compatible version that includes the new optional fields and methods:

```python
@dataclass(frozen=True)
class Event:
    event_type: EventType
    ts: int
    source: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    symbol: str | None = None
    timeframe: str | None = None
    correlation_id: str | None = None
    event_id: str = field(default_factory=lambda: str(uuid4()))
    version: str = "1.0"
    priority: EventPriority = EventPriority.NORMAL
    parent_event_id: str | None = None
    trace_id: str | None = None
    status: EventStatus = EventStatus.CREATED

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "ts": self.ts,
            "source": self.source,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "version": self.version,
            "payload": dict(self.payload),
            "priority": self.priority.value,
            "correlation_id": self.correlation_id,
            "parent_event_id": self.parent_event_id,
            "trace_id": self.trace_id,
            "status": self.status.value,
        }

    def with_status(self, status: EventStatus) -> "Event":
        return replace(self, status=status)

    def dedupe_key(self) -> str:
        strategy_event_id = self.payload.get("strategy_event_id", self.event_id)
        return f"{self.symbol}:{self.event_type.value}:{strategy_event_id}:{self.timeframe}"
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_event_bus_spec.py -q`

Expected: PASS for Task 1 tests.

---

### Task 2: Handler Result, Sync EventBus, Dedupe, and Dead Letter Queue

**Files:**
- Modify: `src/core/events.py`
- Modify: `tests/test_event_bus_spec.py`

- [ ] **Step 1: Add failing tests**

Append to `tests/test_event_bus_spec.py`:

```python
from src.core.events import DeadLetterRecord, EventBus, HandlerResult


def test_event_bus_publish_subscribe_logs_and_idempotency():
    bus = EventBus()
    handled = []

    def handler(event):
        handled.append(event.event_id)
        return HandlerResult(success=True, logs=["handled"])

    bus.subscribe(EventType.SIGNAL_CREATED, handler)
    event = Event(
        EventType.SIGNAL_CREATED,
        1,
        "signal_engine",
        {"strategy_event_id": "sig-1"},
        symbol="BTCUSDT",
        timeframe="15m",
    )
    first = bus.publish(event)
    duplicate = bus.publish(event)
    assert first.success is True
    assert duplicate.success is True
    assert duplicate.metadata["duplicate"] is True
    assert handled == [event.event_id]
    assert [stored.status for stored in bus.event_log] == [EventStatus.HANDLED, EventStatus.DUPLICATE]


def test_event_bus_dispatches_next_events_and_priority_order():
    bus = EventBus()
    seen = []

    def signal_handler(event):
        seen.append(event.event_type.value)
        return HandlerResult(
            success=True,
            next_events=[
                Event(EventType.REPORT_GENERATED, 3, "report_engine", priority=EventPriority.LOW),
                Event(EventType.RISK_BLOCKED, 2, "risk_engine", priority=EventPriority.CRITICAL),
            ],
        )

    def record(event):
        seen.append(event.event_type.value)
        return HandlerResult(success=True)

    bus.subscribe(EventType.SIGNAL_CREATED, signal_handler)
    bus.subscribe(EventType.RISK_BLOCKED, record)
    bus.subscribe(EventType.REPORT_GENERATED, record)
    bus.publish(Event(EventType.SIGNAL_CREATED, 1, "signal_engine", {"strategy_event_id": "sig-2"}))
    assert seen == ["SIGNAL_CREATED", "RISK_BLOCKED", "REPORT_GENERATED"]


def test_event_bus_dead_letters_handler_failures():
    bus = EventBus(max_retries=1)

    def failing_handler(event):
        raise RuntimeError("boom")

    event = Event(EventType.ORDER_FILLED, 1, "execution_engine", {"strategy_event_id": "ord-1"})
    bus.subscribe(EventType.ORDER_FILLED, failing_handler)
    result = bus.publish(event)
    assert result.success is False
    assert len(bus.dead_letters) == 1
    assert isinstance(bus.dead_letters[0], DeadLetterRecord)
    assert bus.dead_letters[0].reason == "HANDLER_ERROR"
    assert bus.dead_letters[0].retry_count == 1
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_event_bus_spec.py -q`

Expected: FAIL because `EventBus`, `HandlerResult`, and `DeadLetterRecord` do not exist.

- [ ] **Step 3: Implement EventBus**

Add these dataclasses and class to `src/core/events.py`:

```python
Handler = Callable[[Event], "HandlerResult"]


@dataclass(frozen=True)
class HandlerResult:
    success: bool
    next_events: list[Event] = field(default_factory=list)
    logs: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DeadLetterRecord:
    event: Event
    reason: str
    errors: list[str]
    retry_count: int
    handler_name: str


class EventBus:
    def __init__(self, *, max_retries: int = 0, max_queue_size: int = 1000) -> None:
        self.max_retries = max_retries
        self.max_queue_size = max_queue_size
        self._handlers: dict[EventType, list[Handler]] = {}
        self._processed_event_ids: set[str] = set()
        self._processed_dedupe_keys: set[str] = set()
        self.event_log: list[Event] = []
        self.dead_letters: list[DeadLetterRecord] = []

    def subscribe(self, event_type: EventType, handler: Handler) -> None:
        self._handlers.setdefault(event_type, []).append(handler)

    def publish(self, event: Event) -> HandlerResult:
        if event.event_id in self._processed_event_ids or event.dedupe_key() in self._processed_dedupe_keys:
            self.event_log.append(event.with_status(EventStatus.DUPLICATE))
            return HandlerResult(True, logs=["duplicate ignored"], metadata={"duplicate": True})
        self._processed_event_ids.add(event.event_id)
        self._processed_dedupe_keys.add(event.dedupe_key())
        return self._dispatch(event.with_status(EventStatus.PUBLISHED))

    def _dispatch(self, event: Event) -> HandlerResult:
        handlers = self._handlers.get(event.event_type, [])
        all_logs: list[str] = []
        all_errors: list[str] = []
        next_events: list[Event] = []
        for handler in handlers:
            result = self._call_handler(handler, event)
            all_logs.extend(result.logs)
            all_errors.extend(result.errors)
            next_events.extend(result.next_events)
            if not result.success:
                self.event_log.append(event.with_status(EventStatus.FAILED))
                return HandlerResult(False, next_events, all_logs, all_errors, {"failed_event_id": event.event_id})
        self.event_log.append(event.with_status(EventStatus.HANDLED))
        for next_event in sorted(next_events, key=lambda item: EVENT_PRIORITY_RANK[item.priority]):
            self.publish(next_event)
        return HandlerResult(True, next_events, all_logs, all_errors)

    def _call_handler(self, handler: Handler, event: Event) -> HandlerResult:
        attempts = 0
        while True:
            try:
                return handler(event)
            except Exception as exc:
                attempts += 1
                if attempts > self.max_retries:
                    self.dead_letters.append(
                        DeadLetterRecord(
                            event=event.with_status(EventStatus.DEAD_LETTERED),
                            reason="HANDLER_ERROR",
                            errors=[str(exc)],
                            retry_count=attempts,
                            handler_name=getattr(handler, "__name__", handler.__class__.__name__),
                        )
                    )
                    return HandlerResult(False, errors=[str(exc)], metadata={"dead_lettered": True})
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_event_bus_spec.py -q`

Expected: PASS for Task 1 and Task 2 tests.

---

### Task 3: Replay, Filtering, Describe Script

**Files:**
- Modify: `src/core/events.py`
- Create: `scripts/describe_event_bus_spec.py`
- Create: `tests/test_describe_event_bus_spec.py`
- Modify: `tests/test_event_bus_spec.py`

- [ ] **Step 1: Add failing tests**

Append to `tests/test_event_bus_spec.py`:

```python
def test_event_bus_replay_filters_by_time_symbol_type_and_priority():
    bus = EventBus()
    seen = []

    def record(event):
        seen.append((event.event_type.value, event.symbol))
        return HandlerResult(success=True)

    bus.subscribe(EventType.MARKET_DATA_UPDATED, record)
    bus.subscribe(EventType.REPORT_GENERATED, record)
    events = [
        Event(EventType.MARKET_DATA_UPDATED, 1, "data_loader", symbol="BTCUSDT", priority=EventPriority.NORMAL),
        Event(EventType.MARKET_DATA_UPDATED, 2, "data_loader", symbol="ETHUSDT", priority=EventPriority.NORMAL),
        Event(EventType.REPORT_GENERATED, 3, "report_engine", symbol="BTCUSDT", priority=EventPriority.LOW),
    ]
    bus.replay(events, start_ts=1, end_ts=3, symbol="BTCUSDT", event_type=EventType.MARKET_DATA_UPDATED, ignore_low_priority=True)
    assert seen == [("MARKET_DATA_UPDATED", "BTCUSDT")]
```

Create `tests/test_describe_event_bus_spec.py`:

```python
import json
import subprocess
import sys


def test_describe_event_bus_spec_outputs_completed_14_sections():
    completed = subprocess.run(
        [sys.executable, "scripts/describe_event_bus_spec.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["event_model_fields"][0] == "event_id"
    assert payload["key_event_types"][0] == "MARKET_DATA_UPDATED"
    assert payload["priorities"] == ["CRITICAL", "HIGH", "NORMAL", "LOW"]
    assert payload["lifecycle_states"][-1] == "dead_lettered"
    assert payload["dedupe_key"] == ["symbol", "event_type", "strategy_event_id", "timeframe"]
    assert payload["handler_result_fields"] == ["success", "next_events", "logs", "errors", "metadata"]
    assert "HANDLER_ERROR" in payload["error_types"]
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_event_bus_spec.py tests/test_describe_event_bus_spec.py -q`

Expected: FAIL because replay and describe script do not exist.

- [ ] **Step 3: Implement replay and describe script**

Add `replay` to `EventBus`:

```python
    def replay(
        self,
        events: Iterable[Event],
        *,
        start_ts: int | None = None,
        end_ts: int | None = None,
        symbol: str | None = None,
        event_type: EventType | None = None,
        ignore_low_priority: bool = False,
    ) -> list[HandlerResult]:
        selected = sorted(events, key=lambda item: item.ts)
        results: list[HandlerResult] = []
        for event in selected:
            if start_ts is not None and event.ts < start_ts:
                continue
            if end_ts is not None and event.ts > end_ts:
                continue
            if symbol is not None and event.symbol != symbol:
                continue
            if event_type is not None and event.event_type != event_type:
                continue
            if ignore_low_priority and event.priority == EventPriority.LOW:
                continue
            results.append(self.publish(event))
        return results
```

Create `scripts/describe_event_bus_spec.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.events import (
    EVENT_CATEGORIES,
    EVENT_DEDUPE_KEY_FIELDS,
    EVENT_ERROR_TYPES,
    EVENT_LIFECYCLE_STATES,
    EVENT_REQUIRED_FIELDS,
    KEY_EVENT_TYPES,
    EventPriority,
    HandlerResult,
)


def main() -> None:
    payload = {
        "event_model_fields": EVENT_REQUIRED_FIELDS,
        "key_event_types": KEY_EVENT_TYPES,
        "categories": EVENT_CATEGORIES,
        "priorities": [item.value for item in EventPriority],
        "lifecycle_states": EVENT_LIFECYCLE_STATES,
        "dedupe_key": EVENT_DEDUPE_KEY_FIELDS,
        "handler_result_fields": list(HandlerResult.__dataclass_fields__),
        "error_types": EVENT_ERROR_TYPES,
        "modes": ["sync", "async_contract_only"],
        "replay_filters": ["start_ts", "end_ts", "symbol", "event_type", "ignore_low_priority"],
        "bus_boundary": "message transport only; no strategy, risk, sizing, or execution decisions",
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_event_bus_spec.py tests/test_describe_event_bus_spec.py -q`

Expected: PASS.

---

### Task 4: Scaffold Sync and Verification

**Files:**
- Modify: `scripts/scaffold_ai300_framework.py`

- [ ] **Step 1: Sync scaffold templates**

Copy final contents into `scripts/scaffold_ai300_framework.py` for:

- `src/core/events.py`
- `scripts/describe_event_bus_spec.py`
- `tests/test_event_bus_spec.py`
- `tests/test_describe_event_bus_spec.py`

- [ ] **Step 2: Run targeted tests**

Run: `pytest tests/test_event_bus_spec.py tests/test_describe_event_bus_spec.py tests/test_framework_scaffold.py -q`

Expected: PASS.

- [ ] **Step 3: Run full verification**

Run:

```bash
pytest -q
python -m compileall src scripts tests
python scripts/describe_event_bus_spec.py
git diff -- src/api/binance_client.py
```

Expected: all tests pass, compile succeeds, describe JSON includes completed 14 sections, and Binance diff has no output.

- [ ] **Step 4: Clean generated caches**

Run:

```powershell
$root=(Resolve-Path '.').Path; $targets=Get-ChildItem -Path . -Recurse -Directory -Filter '__pycache__' | Where-Object { $_.FullName.StartsWith($root) }; foreach($target in $targets){ Remove-Item -LiteralPath $target.FullName -Recurse -Force }; Get-ChildItem -Path . -Recurse -Directory -Filter '__pycache__' | Select-Object -ExpandProperty FullName
```

Expected: no remaining `__pycache__` directories in the workspace.

---

## Self-Review

- Spec coverage: covers event naming, event categories, event model fields, payload structure, priorities, sources/subscribers, sync mode, queue limits as contract fields, dedupe, idempotency, replay, dead-letter handling, key events, handler result, trace fields, debug filters, tests, and forbidden business logic boundaries.
- Placeholder scan: no `TBD`, `TODO`, `implement later`, or unspecified test steps.
- Type consistency: `Event`, `EventType`, `EventPriority`, `EventStatus`, `HandlerResult`, `DeadLetterRecord`, `EventBus`, and describe payload keys are named consistently across tasks.
