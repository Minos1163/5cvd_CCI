from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Callable, Iterable, Mapping
from uuid import uuid4


class EventType(str, Enum):
    MARKET_DATA_UPDATED = "MARKET_DATA_UPDATED"
    INDICATOR_UPDATED = "INDICATOR_UPDATED"
    MULTI_TF_CONTEXT_READY = "MULTI_TF_CONTEXT_READY"
    WATCH_ENTERED = "WATCH_ENTERED"
    PROBE_ENTERED = "PROBE_ENTERED"
    DIRECT_ENTERED = "DIRECT_ENTERED"
    POSITION_OPENED = "POSITION_OPENED"
    POSITION_REDUCED = "POSITION_REDUCED"
    POSITION_CLOSED = "POSITION_CLOSED"
    STOP_HIT = "STOP_HIT"
    TP_HIT = "TP_HIT"
    RISK_BLOCKED = "RISK_BLOCKED"
    COOLDOWN_STARTED = "COOLDOWN_STARTED"
    COOLDOWN_ENDED = "COOLDOWN_ENDED"
    BACKTEST_STEP_COMPLETED = "BACKTEST_STEP_COMPLETED"
    REPORT_GENERATED = "REPORT_GENERATED"
    MARKET_CANDLE_CLOSED = "MARKET_CANDLE_CLOSED"
    INDICATORS_UPDATED = "INDICATORS_UPDATED"
    MULTI_TIMEFRAME_CONTEXT_UPDATED = "MULTI_TIMEFRAME_CONTEXT_UPDATED"
    SIGNAL_CREATED = "SIGNAL_CREATED"
    SIGNAL_REJECTED = "SIGNAL_REJECTED"
    STATE_TRANSITION = "STATE_TRANSITION"
    RISK_APPROVED = "RISK_APPROVED"
    RISK_REJECTED = "RISK_REJECTED"
    ORDER_INTENT_CREATED = "ORDER_INTENT_CREATED"
    ORDER_SUBMITTED = "ORDER_SUBMITTED"
    ORDER_ACKNOWLEDGED = "ORDER_ACKNOWLEDGED"
    ORDER_REJECTED = "ORDER_REJECTED"
    ORDER_FILLED = "ORDER_FILLED"
    HANDLER_FAILED = "HANDLER_FAILED"


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


KEY_EVENT_TYPES = [
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
EVENT_LIFECYCLE_STATES = [
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
EVENT_REQUIRED_FIELDS = [
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
EVENT_DEDUPE_KEY_FIELDS = ["symbol", "event_type", "strategy_event_id", "timeframe"]
EVENT_ERROR_TYPES = [
    "INVALID_PAYLOAD",
    "UNKNOWN_EVENT_TYPE",
    "HANDLER_ERROR",
    "TIMEOUT",
    "DUPLICATE_EVENT",
    "STATE_CONFLICT",
    "DEPENDENCY_UNAVAILABLE",
]
EVENT_CATEGORIES = {
    "Market Events": ["MARKET_DATA_UPDATED"],
    "Indicator Events": ["INDICATOR_UPDATED"],
    "Context Events": ["MULTI_TF_CONTEXT_READY"],
    "Signal Events": ["SIGNAL_CREATED", "WATCH_ENTERED", "PROBE_ENTERED", "DIRECT_ENTERED"],
    "Risk Events": ["STOP_HIT", "TP_HIT", "RISK_BLOCKED", "COOLDOWN_STARTED", "COOLDOWN_ENDED"],
    "Execution Events": ["ORDER_SUBMITTED", "ORDER_FILLED", "ORDER_REJECTED"],
    "Position Events": ["POSITION_OPENED", "POSITION_REDUCED", "POSITION_CLOSED"],
    "Backtest Events": ["BACKTEST_STEP_COMPLETED"],
    "Reporting Events": ["REPORT_GENERATED"],
}
EVENT_PRIORITY_RANK = {
    EventPriority.CRITICAL: 0,
    EventPriority.HIGH: 1,
    EventPriority.NORMAL: 2,
    EventPriority.LOW: 3,
}


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
                            retry_count=attempts - 1,
                            handler_name=getattr(handler, "__name__", handler.__class__.__name__),
                        )
                    )
                    return HandlerResult(False, errors=[str(exc)], metadata={"dead_lettered": True})

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
