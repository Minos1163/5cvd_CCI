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
PROTECTION_MODE_TRIGGERS = [
    "consecutive_rejects",
    "consecutive_sync_failures",
    "consecutive_protection_order_failures",
    "abnormal_position_state",
    "unknown_order_state",
    "exchange_unavailable",
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
