from src.core.events import (
    DeadLetterRecord,
    EVENT_CATEGORIES,
    EVENT_DEDUPE_KEY_FIELDS,
    EVENT_ERROR_TYPES,
    EVENT_LIFECYCLE_STATES,
    EVENT_REQUIRED_FIELDS,
    KEY_EVENT_TYPES,
    Event,
    EventBus,
    EventPriority,
    EventStatus,
    EventType,
    HandlerResult,
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
    bus.replay(
        events,
        start_ts=1,
        end_ts=3,
        symbol="BTCUSDT",
        event_type=EventType.MARKET_DATA_UPDATED,
        ignore_low_priority=True,
    )
    assert seen == [("MARKET_DATA_UPDATED", "BTCUSDT")]
