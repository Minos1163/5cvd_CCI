from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

from src.execution.live_execution_contract import (
    EXECUTION_FORBIDDEN_ACTIONS,
    EXECUTION_LOG_FIELDS,
    OBSERVABILITY_METRICS,
    ORDER_LIFECYCLE_STATES,
    PROTECTION_MODE_TRIGGERS,
    SUPPORTED_ORDER_TYPES,
    ExecutionInstruction,
    ExecutionResponse,
    ExecutionValidation,
    build_execution_log,
    build_partial_fill_snapshot,
    normalize_reject_reason,
    should_enter_protection_mode,
    validate_execution_instruction,
)


EXECUTION_ENGINE_RESPONSIBILITIES = [
    "validate_request",
    "build_order_instruction",
    "submit_order",
    "cancel_order",
    "query_order_status",
    "handle_partial_fill",
    "sync_position",
    "record_audit_log",
    "emit_execution_events",
    "surface_errors_upward",
]
EXECUTION_REQUEST_FIELDS = [
    "request_id",
    "event_id",
    "trace_id",
    "correlation_id",
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
    "entry_mode",
    "strategy_state",
    "strategy_version",
    "risk_tag",
    "expected_position_qty",
    "expected_position_side",
    "timestamp",
]
EXECUTION_RESULT_FIELDS = [
    "request_id",
    "event_id",
    "order_id",
    "client_order_id",
    "status",
    "filled_qty",
    "avg_price",
    "executed_notional",
    "commission",
    "latency_ms",
    "reject_reason",
    "raw_response",
    "position_snapshot",
    "risk_snapshot",
    "timestamp",
]
EXECUTION_EVENT_TYPES = [
    "ORDER_SUBMITTED",
    "ORDER_ACKNOWLEDGED",
    "ORDER_FILLED",
    "ORDER_REJECTED",
    "ORDER_CANCELED",
    "POSITION_OPENED",
    "POSITION_REDUCED",
    "POSITION_CLOSED",
    "RISK_BLOCKED",
]
EXECUTION_RETRY_POLICY = {
    "max_retries": 2,
    "retryable_reasons": ["NETWORK_TIMEOUT", "TEMPORARY_UNAVAILABLE", "ORDER_QUERY_DELAY"],
    "non_retryable_reasons": ["PRECISION_ERROR", "MIN_NOTIONAL", "LEVERAGE_ERROR", "REDUCE_ONLY_ERROR", "RISK_BLOCKED"],
}
EXECUTION_PRE_CHECKS = [
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
]
EXECUTION_FORBIDDEN_ENGINE_ACTIONS = [
    "rewrite_strategy_intent",
    "rewrite_risk_decision",
    "recalculate_position_size",
    "recalculate_stop_or_take_profit",
    "treat_partial_fill_as_new_signal",
    "retry_with_new_strategy_action",
    "swallow_exchange_error",
]
BINANCE_CLIENT_POLICY = "thin injected adapter only; do not modify stable client"


@dataclass(frozen=True)
class ExecutionRequest:
    request_id: str
    event_id: str
    trace_id: str
    correlation_id: str
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
    entry_mode: str
    strategy_state: str
    strategy_version: str
    risk_tag: str
    expected_position_qty: float
    expected_position_side: str
    timestamp: int
    risk_snapshot: Mapping[str, Any] = field(default_factory=dict)
    position_snapshot: Mapping[str, Any] = field(default_factory=dict)
    entry_chain_snapshot: Mapping[str, Any] = field(default_factory=dict)

    def to_instruction(self, client_order_id: str) -> ExecutionInstruction:
        return ExecutionInstruction(
            symbol=self.symbol,
            side=self.side,
            order_type=self.order_type,
            quantity=self.quantity,
            price=self.price,
            reduce_only=self.reduce_only,
            position_side=self.position_side,
            time_in_force=self.time_in_force,
            stop_price=self.stop_price,
            take_profit_price=self.take_profit_price,
            client_order_id=client_order_id,
            strategy_event_id=self.event_id,
            strategy_state=self.strategy_state,
            expected_position_side=self.expected_position_side,
            expected_risk_tag=self.risk_tag,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExecutionResult:
    request_id: str
    event_id: str
    order_id: str
    client_order_id: str
    status: str
    filled_qty: float
    avg_price: float
    executed_notional: float
    commission: float
    latency_ms: int
    reject_reason: str
    raw_response: dict[str, Any]
    position_snapshot: dict[str, Any]
    risk_snapshot: dict[str, Any]
    timestamp: int
    lifecycle: list[dict[str, Any]]
    events: list[str]
    audit_log: dict[str, Any]
    protection_mode: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ExecutionEngine:
    def __init__(
        self,
        adapter: Any,
        *,
        tradable_symbols: set[str] | None = None,
        min_notional: float = 5.0,
        quantity_step: float = 0.0,
        max_retries: int = 2,
    ) -> None:
        self.adapter = adapter
        self.tradable_symbols = tradable_symbols
        self.min_notional = min_notional
        self.quantity_step = quantity_step
        self.max_retries = max_retries
        self._results_by_idempotency_key: dict[str, ExecutionResult] = {}
        self.lifecycle_log: list[dict[str, Any]] = []
        self.audit_logs: list[dict[str, Any]] = []
        self.consecutive_rejects = 0
        self.consecutive_sync_failures = 0
        self.consecutive_protection_order_failures = 0

    def submit_order(self, request: ExecutionRequest) -> ExecutionResult:
        idempotency_key = build_execution_idempotency_key(request)
        if idempotency_key in self._results_by_idempotency_key:
            return self._results_by_idempotency_key[idempotency_key]

        client_order_id = idempotency_key
        instruction = request.to_instruction(client_order_id)
        lifecycle = [self._lifecycle(client_order_id, "created", request.timestamp, "request accepted")]
        validation = validate_execution_instruction(
            instruction,
            tradable=_is_tradable(request.symbol, self.tradable_symbols),
            min_notional=self.min_notional,
            quantity_step=self.quantity_step,
            current_position_side=request.position_snapshot.get("position_side"),
            account_risk_allows=bool(request.risk_snapshot.get("allow_trade", True)),
            symbol_cooldown_active=bool(request.risk_snapshot.get("symbol_cooldown_active", False)),
        )
        if not validation.passed:
            lifecycle.append(self._lifecycle(client_order_id, "rejected", request.timestamp, validation.reason))
            result = self._result_from_response(
                request,
                instruction,
                ExecutionResponse(
                    order_id="",
                    client_order_id=client_order_id,
                    status="rejected",
                    filled_qty=0.0,
                    avg_price=0.0,
                    commission=0.0,
                    executed_notional=0.0,
                    reject_reason=validation.reason,
                    raw_response={"validation": validation.reason},
                    latency_ms=0,
                    ts=request.timestamp,
                ),
                lifecycle,
                ["ORDER_REJECTED"],
                retry_count=0,
            )
            self.consecutive_rejects += 1
            self._results_by_idempotency_key[idempotency_key] = result
            return result

        entry_chain_validation = validate_entry_chain_execution(request)
        if not entry_chain_validation.passed:
            lifecycle.append(self._lifecycle(client_order_id, "rejected", request.timestamp, entry_chain_validation.reason))
            result = self._result_from_response(
                request,
                instruction,
                ExecutionResponse(
                    order_id="",
                    client_order_id=client_order_id,
                    status="rejected",
                    filled_qty=0.0,
                    avg_price=0.0,
                    commission=0.0,
                    executed_notional=0.0,
                    reject_reason=entry_chain_validation.reason,
                    raw_response={"entry_chain_validation": entry_chain_validation.reason},
                    latency_ms=0,
                    ts=request.timestamp,
                ),
                lifecycle,
                ["ORDER_REJECTED"],
                retry_count=0,
            )
            self.consecutive_rejects += 1
            self._results_by_idempotency_key[idempotency_key] = result
            return result

        lifecycle.append(self._lifecycle(client_order_id, "validated", request.timestamp, "validated"))
        lifecycle.append(self._lifecycle(client_order_id, "submitted", request.timestamp, "submitted to adapter"))
        response, retry_count = self._submit_with_retry(instruction, request.timestamp)
        status = normalize_order_status(response.status)
        lifecycle.append(self._lifecycle(client_order_id, "acknowledged", response.ts, "adapter response received"))
        if status in {"partially_filled", "filled", "rejected"}:
            lifecycle.append(self._lifecycle(client_order_id, status, response.ts, status))

        events = ["ORDER_SUBMITTED"]
        if status == "filled":
            events.extend(["ORDER_FILLED", _position_event(request)])
            self.consecutive_rejects = 0
        elif status == "partially_filled":
            events.append("ORDER_ACKNOWLEDGED")
        elif status == "rejected":
            events.append("ORDER_REJECTED")
            self.consecutive_rejects += 1
        else:
            events.append("ORDER_ACKNOWLEDGED")

        result = self._result_from_response(request, instruction, response, lifecycle, events, retry_count=retry_count)
        self._results_by_idempotency_key[idempotency_key] = result
        return result

    def cancel_order(self, request_id: str, symbol: str, order_id: str | int, timestamp: int = 0) -> ExecutionResult:
        try:
            raw = self.adapter.cancel(symbol, order_id)
            status = normalize_order_status(str(raw.get("status", "canceled")))
            reject_reason = ""
        except Exception as exc:
            raw = {"error": str(exc)}
            status = "rejected"
            reject_reason = normalize_reject_reason(str(exc))
            self.consecutive_rejects += 1
        client_order_id = str(raw.get("client_order_id") or raw.get("clientOrderId") or f"cancel:{symbol}:{order_id}")
        lifecycle = [
            self._lifecycle(client_order_id, "created", timestamp, "cancel requested"),
            self._lifecycle(client_order_id, status if status == "canceled" else "rejected", timestamp, "cancel result"),
        ]
        instruction = ExecutionInstruction(
            symbol=symbol,
            side=str(raw.get("side", "SELL")),
            order_type=str(raw.get("order_type", "MARKET")),
            quantity=float(raw.get("quantity", 0.0)),
            price=None,
            reduce_only=True,
            position_side=str(raw.get("position_side", "BOTH")),
            time_in_force=None,
            stop_price=None,
            take_profit_price=None,
            client_order_id=client_order_id,
            strategy_event_id=request_id,
            strategy_state="CANCEL",
            expected_position_side=str(raw.get("position_side", "BOTH")),
            expected_risk_tag="cancel",
        )
        response = ExecutionResponse(
            order_id=str(order_id),
            client_order_id=client_order_id,
            status=status,
            filled_qty=float(raw.get("filled_qty", 0.0)),
            avg_price=float(raw.get("avg_price", 0.0)),
            commission=float(raw.get("commission", 0.0)),
            executed_notional=float(raw.get("executed_notional", 0.0)),
            reject_reason=reject_reason,
            raw_response=raw,
            latency_ms=int(raw.get("latency_ms", 0)),
            ts=timestamp,
        )
        return self._result_from_response(
            ExecutionRequest(
                request_id=request_id,
                event_id=request_id,
                trace_id=request_id,
                correlation_id=request_id,
                symbol=symbol,
                side=instruction.side,
                order_type=instruction.order_type,
                quantity=instruction.quantity,
                price=None,
                reduce_only=True,
                position_side=instruction.position_side,
                time_in_force=None,
                stop_price=None,
                take_profit_price=None,
                entry_mode="NONE",
                strategy_state="CANCEL",
                strategy_version="",
                risk_tag="cancel",
                expected_position_qty=0.0,
                expected_position_side=instruction.expected_position_side,
                timestamp=timestamp,
            ),
            instruction,
            response,
            lifecycle,
            ["ORDER_CANCELED"] if status == "canceled" else ["ORDER_REJECTED"],
            retry_count=0,
        )

    def sync_position(self, symbol: str | None = None) -> dict[str, Any]:
        try:
            snapshot = self.adapter.sync(symbol)
            self.consecutive_sync_failures = 0
            return {"passed": True, "snapshot": snapshot, "protection_mode": False, "reason": "synced"}
        except Exception as exc:
            self.consecutive_sync_failures += 1
            protection = should_enter_protection_mode(consecutive_sync_failures=self.consecutive_sync_failures)
            return {"passed": False, "snapshot": {}, "protection_mode": protection.passed, "reason": str(exc)}

    def _submit_with_retry(self, instruction: ExecutionInstruction, timestamp: int) -> tuple[ExecutionResponse, int]:
        retry_count = 0
        while True:
            try:
                raw = self.adapter.submit(instruction)
                return _response_from_raw(instruction, raw, timestamp), retry_count
            except Exception as exc:
                reason = normalize_reject_reason(str(exc))
                if reason not in EXECUTION_RETRY_POLICY["retryable_reasons"] or retry_count >= self.max_retries:
                    return (
                        ExecutionResponse(
                            order_id="",
                            client_order_id=instruction.client_order_id,
                            status="rejected",
                            filled_qty=0.0,
                            avg_price=0.0,
                            commission=0.0,
                            executed_notional=0.0,
                            reject_reason=reason,
                            raw_response={"error": str(exc)},
                            latency_ms=0,
                            ts=timestamp,
                        ),
                        retry_count,
                    )
                retry_count += 1

    def _result_from_response(
        self,
        request: ExecutionRequest,
        instruction: ExecutionInstruction,
        response: ExecutionResponse,
        lifecycle: list[dict[str, Any]],
        events: list[str],
        *,
        retry_count: int,
    ) -> ExecutionResult:
        audit_log = build_execution_log(instruction, response, action="submit_order", module="execution_engine")
        self.audit_logs.append(audit_log)
        protection = should_enter_protection_mode(consecutive_rejects=self.consecutive_rejects)
        status = normalize_order_status(response.status)
        metadata: dict[str, Any] = {
            "retry_count": retry_count,
            "idempotency_key": instruction.client_order_id,
            "forbidden_actions": EXECUTION_FORBIDDEN_ENGINE_ACTIONS,
            "partial_fill": None,
            "entry_chain_snapshot": dict(request.entry_chain_snapshot),
        }
        if status == "partially_filled":
            metadata["partial_fill"] = build_partial_fill_snapshot(
                order_qty=request.quantity,
                filled_qty=response.filled_qty,
                avg_price=response.avg_price,
                client_order_id=instruction.client_order_id,
            )
        return ExecutionResult(
            request_id=request.request_id,
            event_id=request.event_id,
            order_id=response.order_id,
            client_order_id=instruction.client_order_id,
            status=status,
            filled_qty=response.filled_qty,
            avg_price=response.avg_price,
            executed_notional=response.executed_notional,
            commission=response.commission,
            latency_ms=response.latency_ms,
            reject_reason=response.reject_reason,
            raw_response=response.raw_response,
            position_snapshot=dict(request.position_snapshot),
            risk_snapshot=dict(request.risk_snapshot),
            timestamp=response.ts,
            lifecycle=lifecycle,
            events=events,
            audit_log=audit_log,
            protection_mode=protection.passed,
            metadata=metadata,
        )

    def _lifecycle(self, client_order_id: str, state: str, ts: int, reason: str) -> dict[str, Any]:
        if state not in ORDER_LIFECYCLE_STATES:
            raise ValueError("unknown lifecycle state")
        row = {"client_order_id": client_order_id, "state": state, "ts": ts, "reason": reason}
        self.lifecycle_log.append(row)
        return row


def build_execution_idempotency_key(request: ExecutionRequest) -> str:
    return ":".join(
        [
            request.symbol.strip().upper(),
            request.event_id,
            request.strategy_state,
            request.side.strip().upper(),
            request.entry_mode.strip().upper(),
        ]
    )


def validate_entry_chain_execution(request: ExecutionRequest) -> ExecutionValidation:
    if request.reduce_only or request.risk_tag.strip().lower() != "entry":
        return ExecutionValidation(True, "validated")
    snapshot = dict(request.entry_chain_snapshot or {})
    if not snapshot:
        return ExecutionValidation(False, "entry chain approval is required for entry orders")
    if not bool(snapshot.get("risk_allowed", False)):
        return ExecutionValidation(False, "entry chain risk approval is false")
    approved_action = str(snapshot.get("action", "NO_TRADE")).strip().upper()
    if approved_action not in {"PROBE", "DIRECT"}:
        return ExecutionValidation(False, "entry chain action does not allow execution")
    if _action_rank(request.entry_mode) > _action_rank(approved_action):
        return ExecutionValidation(False, "execution entry mode exceeds entry chain approval")
    approved_side = str(snapshot.get("side", "")).strip().upper()
    if approved_side in {"LONG", "SHORT"} and approved_side != request.expected_position_side.strip().upper():
        return ExecutionValidation(False, "execution side differs from entry chain approval")
    reference_price = request.price or request.stop_price or request.take_profit_price
    notional_hint = float(snapshot.get("notional_hint", 0.0) or 0.0)
    if reference_price is not None and notional_hint > 0:
        requested_notional = request.quantity * reference_price
        if requested_notional > notional_hint + 1e-9:
            return ExecutionValidation(False, "entry order exceeds entry chain approved notional")
    return ExecutionValidation(True, "validated")


def _action_rank(action: str) -> int:
    return {"NO_TRADE": 0, "NONE": 0, "WATCH": 1, "PROBE": 2, "DIRECT": 3}.get(action.strip().upper(), 0)


def normalize_order_status(status: str) -> str:
    value = str(status).strip().lower()
    aliases = {
        "new": "acknowledged",
        "acknowledged": "acknowledged",
        "submitted": "submitted",
        "partially_filled": "partially_filled",
        "partial": "partially_filled",
        "filled": "filled",
        "canceled": "canceled",
        "cancelled": "canceled",
        "rejected": "rejected",
        "expired": "expired",
    }
    return aliases.get(value, "rejected")


def _response_from_raw(instruction: ExecutionInstruction, raw: Mapping[str, Any], timestamp: int) -> ExecutionResponse:
    status = normalize_order_status(str(raw.get("status", "acknowledged")))
    filled_qty = float(raw.get("filled_qty", raw.get("executedQty", 0.0)))
    avg_price = float(raw.get("avg_price", raw.get("avgPrice", raw.get("price", 0.0)) or 0.0))
    executed_notional = float(raw.get("executed_notional", filled_qty * avg_price))
    reject_reason = str(raw.get("reject_reason", ""))
    if status == "rejected" and not reject_reason:
        reject_reason = normalize_reject_reason(str(raw.get("message", raw.get("error", "exchange rejected"))))
    return ExecutionResponse(
        order_id=str(raw.get("order_id", raw.get("orderId", ""))),
        client_order_id=instruction.client_order_id,
        status=status,
        filled_qty=filled_qty,
        avg_price=avg_price,
        commission=float(raw.get("commission", 0.0)),
        executed_notional=executed_notional,
        reject_reason=reject_reason,
        raw_response=dict(raw),
        latency_ms=int(raw.get("latency_ms", 0)),
        ts=int(raw.get("timestamp", timestamp)),
    )


def _is_tradable(symbol: str, tradable_symbols: set[str] | None) -> bool:
    if tradable_symbols is None:
        return True
    return symbol.strip().upper() in tradable_symbols


def _position_event(request: ExecutionRequest) -> str:
    if request.reduce_only:
        return "POSITION_REDUCED"
    return "POSITION_OPENED"
