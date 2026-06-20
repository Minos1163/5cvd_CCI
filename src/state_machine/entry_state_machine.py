from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping


ENTRY_STATE_VERSION = "1.0"


class EntryState(str, Enum):
    FLAT = "FLAT"
    WATCH_LONG = "WATCH_LONG"
    WATCH_SHORT = "WATCH_SHORT"
    PROBE_LONG = "PROBE_LONG"
    PROBE_SHORT = "PROBE_SHORT"
    DIRECT_LONG = "DIRECT_LONG"
    DIRECT_SHORT = "DIRECT_SHORT"
    MANAGE_LONG = "MANAGE_LONG"
    MANAGE_SHORT = "MANAGE_SHORT"
    EXIT_LONG = "EXIT_LONG"
    EXIT_SHORT = "EXIT_SHORT"


ALLOWED_TRANSITIONS = {
    EntryState.FLAT: {
        EntryState.WATCH_LONG,
        EntryState.WATCH_SHORT,
        EntryState.PROBE_LONG,
        EntryState.PROBE_SHORT,
        EntryState.DIRECT_LONG,
        EntryState.DIRECT_SHORT,
    },
    EntryState.WATCH_LONG: {EntryState.PROBE_LONG, EntryState.DIRECT_LONG, EntryState.FLAT},
    EntryState.WATCH_SHORT: {EntryState.PROBE_SHORT, EntryState.DIRECT_SHORT, EntryState.FLAT},
    EntryState.PROBE_LONG: {EntryState.MANAGE_LONG, EntryState.EXIT_LONG, EntryState.FLAT, EntryState.DIRECT_LONG},
    EntryState.PROBE_SHORT: {EntryState.MANAGE_SHORT, EntryState.EXIT_SHORT, EntryState.FLAT, EntryState.DIRECT_SHORT},
    EntryState.DIRECT_LONG: {EntryState.MANAGE_LONG, EntryState.EXIT_LONG, EntryState.FLAT},
    EntryState.DIRECT_SHORT: {EntryState.MANAGE_SHORT, EntryState.EXIT_SHORT, EntryState.FLAT},
    EntryState.MANAGE_LONG: {EntryState.EXIT_LONG, EntryState.FLAT},
    EntryState.MANAGE_SHORT: {EntryState.EXIT_SHORT, EntryState.FLAT},
    EntryState.EXIT_LONG: {EntryState.FLAT},
    EntryState.EXIT_SHORT: {EntryState.FLAT},
}

ENTRY_STATE_CATEGORIES = {
    "watch": ("WATCH_LONG", "WATCH_SHORT"),
    "probe": ("PROBE_LONG", "PROBE_SHORT"),
    "direct": ("DIRECT_LONG", "DIRECT_SHORT"),
    "manage": ("MANAGE_LONG", "MANAGE_SHORT"),
    "exit": ("EXIT_LONG", "EXIT_SHORT"),
}
TRANSITION_LOG_FIELDS = (
    "symbol",
    "timestamp",
    "state_before",
    "state_after",
    "reason",
    "signal_type",
    "entry_mode",
    "risk_level",
    "quality_flag",
    "price",
    "version",
)
TRANSITION_SOURCES = (
    "signal_engine",
    "risk_engine",
    "execution_result",
    "position_sync",
    "cooldown",
    "data_quality",
)
TRANSITION_BLOCKERS = (
    "invalid_transition",
    "missing_reason",
    "risk_blocked",
    "data_quality_blocked",
    "cooldown_active",
    "position_not_executable",
)
ENTRY_STATE_FORBIDDEN_ACTIONS = (
    "calculate_indicators",
    "judge_trend_direction",
    "calculate_final_position_size",
    "generate_orders",
    "call_exchange_adapter",
    "rewrite_risk_decision",
    "unlogged_transition",
)


def transition(current: EntryState, target: EntryState) -> EntryState:
    if target not in ALLOWED_TRANSITIONS[current]:
        raise ValueError(f"invalid transition: {current.value} -> {target.value}")
    return target


@dataclass(frozen=True)
class TransitionDecision:
    allowed: bool
    state_before: EntryState
    state_after: EntryState
    reason: str
    blockers: tuple[str, ...] = ()


@dataclass(frozen=True)
class EntryTransition:
    symbol: str
    from_state: EntryState
    to_state: EntryState
    reason: str
    ts: Any
    price: float
    signal_type: str = "NO_TRADE"
    entry_mode: str = "NONE"
    risk_level: str = "NORMAL"
    quality_flag: bool = True
    version: str = ENTRY_STATE_VERSION
    source: str = "state_machine"
    position_size: float = 0.0
    risk_value: float = 0.0

    @property
    def timestamp(self) -> Any:
        return self.ts

    @property
    def state_before(self) -> EntryState:
        return self.from_state

    @property
    def state_after(self) -> EntryState:
        return self.to_state

    def to_log_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timestamp": self.ts,
            "state_before": self.from_state.value,
            "state_after": self.to_state.value,
            "reason": self.reason,
            "signal_type": self.signal_type,
            "entry_mode": self.entry_mode,
            "risk_level": self.risk_level,
            "quality_flag": self.quality_flag,
            "price": self.price,
            "version": self.version,
            "source": self.source,
            "from_state": self.from_state.value,
            "to_state": self.to_state.value,
            "ts": self.ts,
            "position_size": self.position_size,
            "risk_value": self.risk_value,
        }


def evaluate_transition(
    current: EntryState,
    target: EntryState,
    *,
    reason: str,
    risk_allowed: bool = True,
    quality_flag: bool = True,
    cooldown_active: bool = False,
    position_executable: bool = True,
) -> TransitionDecision:
    blockers: list[str] = []
    if target not in ALLOWED_TRANSITIONS[current]:
        blockers.append("invalid_transition")
    if not str(reason).strip():
        blockers.append("missing_reason")
    if not risk_allowed:
        blockers.append("risk_blocked")
    if not quality_flag:
        blockers.append("data_quality_blocked")
    if cooldown_active:
        blockers.append("cooldown_active")
    if not position_executable:
        blockers.append("position_not_executable")
    return TransitionDecision(
        allowed=not blockers,
        state_before=current,
        state_after=target,
        reason=reason,
        blockers=tuple(blockers),
    )


class EntryStateMachine:
    def __init__(self, symbol: str, initial_state: EntryState = EntryState.FLAT):
        self.symbol = symbol
        self.current_state = initial_state
        self.history: list[EntryTransition] = []

    def apply_transition(
        self,
        target: EntryState,
        reason: str,
        ts: Any,
        price: float,
        position_size: float = 0.0,
        risk_value: float = 0.0,
        *,
        signal_type: str = "NO_TRADE",
        entry_mode: str = "NONE",
        risk_level: str = "NORMAL",
        quality_flag: bool = True,
        risk_allowed: bool = True,
        cooldown_active: bool = False,
        position_executable: bool = True,
        source: str = "state_machine",
        version: str = ENTRY_STATE_VERSION,
    ) -> EntryTransition:
        source_state = self.current_state
        decision = evaluate_transition(
            source_state,
            target,
            reason=reason,
            risk_allowed=risk_allowed,
            quality_flag=quality_flag,
            cooldown_active=cooldown_active,
            position_executable=position_executable,
        )
        if not decision.allowed:
            raise ValueError(
                f"blocked transition: {source_state.value} -> {target.value}; blockers={','.join(decision.blockers)}"
            )
        record = EntryTransition(
            symbol=self.symbol,
            from_state=source_state,
            to_state=target,
            reason=reason,
            ts=ts,
            price=price,
            signal_type=signal_type,
            entry_mode=entry_mode,
            risk_level=risk_level,
            quality_flag=quality_flag,
            version=version,
            source=source,
            position_size=position_size,
            risk_value=risk_value,
        )
        self.current_state = target
        self.history.append(record)
        return record

    def apply_signal(
        self,
        signal: Mapping[str, Any],
        ts: Any,
        price: float,
        position_size: float = 0.0,
        risk_value: float = 0.0,
    ) -> list[EntryTransition]:
        signal_type = str(signal.get("signal_type", "")).upper()
        side = str(signal.get("side", signal.get("signal_side", ""))).upper()
        entry_mode = str(signal.get("entry_mode", signal.get("mode", signal_type))).upper()
        reason = str(signal.get("reason", signal_type or entry_mode))
        quality_flag = bool(signal.get("quality_flag", True))
        risk_level = str(signal.get("risk_level", "NORMAL")).upper()

        if signal_type in {"WAIT", "NO_TRADE"} or entry_mode == "NONE":
            return []
        if self.current_state != EntryState.FLAT:
            raise ValueError(f"signal entries require FLAT state, got {self.current_state.value}")

        target = _entry_target(signal_type, side, entry_mode)
        if target is None:
            raise ValueError(f"unsupported signal: {signal_type}/{side}/{entry_mode}")
        return [
            self.apply_transition(
                target,
                reason,
                ts,
                price,
                position_size,
                risk_value,
                signal_type=signal_type,
                entry_mode=_entry_mode_from_state(target),
                risk_level=risk_level,
                quality_flag=quality_flag,
                source="signal_engine",
            )
        ]

    def maybe_upgrade_probe(self, r_multiple: float, ts: Any, price: float) -> EntryTransition | None:
        if r_multiple < 1.0:
            return None
        if self.current_state == EntryState.PROBE_LONG:
            return self.apply_transition(
                EntryState.DIRECT_LONG,
                "probe reached 1R",
                ts,
                price,
                signal_type="LONG",
                entry_mode="DIRECT",
                source="signal_engine",
            )
        if self.current_state == EntryState.PROBE_SHORT:
            return self.apply_transition(
                EntryState.DIRECT_SHORT,
                "probe reached 1R",
                ts,
                price,
                signal_type="SHORT",
                entry_mode="DIRECT",
                source="signal_engine",
            )
        return None

    def mark_position_opened(self, reason: str, ts: Any, price: float) -> EntryTransition | None:
        if self.current_state == EntryState.PROBE_LONG:
            return self.apply_transition(EntryState.MANAGE_LONG, reason, ts, price, source="execution_result")
        if self.current_state == EntryState.PROBE_SHORT:
            return self.apply_transition(EntryState.MANAGE_SHORT, reason, ts, price, source="execution_result")
        if self.current_state == EntryState.DIRECT_LONG:
            return self.apply_transition(EntryState.MANAGE_LONG, reason, ts, price, source="execution_result")
        if self.current_state == EntryState.DIRECT_SHORT:
            return self.apply_transition(EntryState.MANAGE_SHORT, reason, ts, price, source="execution_result")
        return None

    def rollback_rejected_order(self, reason: str, ts: Any, price: float) -> EntryTransition | None:
        if self.current_state in {
            EntryState.PROBE_LONG,
            EntryState.PROBE_SHORT,
            EntryState.DIRECT_LONG,
            EntryState.DIRECT_SHORT,
        }:
            return self.apply_transition(EntryState.FLAT, reason, ts, price, source="execution_result")
        return None

    def exit_current(self, reason: str, ts: Any, price: float) -> list[EntryTransition]:
        if self.current_state in {EntryState.FLAT, EntryState.WATCH_LONG, EntryState.WATCH_SHORT}:
            return []
        if self.current_state in {EntryState.PROBE_LONG, EntryState.DIRECT_LONG, EntryState.MANAGE_LONG}:
            exit_state = EntryState.EXIT_LONG
        elif self.current_state in {EntryState.PROBE_SHORT, EntryState.DIRECT_SHORT, EntryState.MANAGE_SHORT}:
            exit_state = EntryState.EXIT_SHORT
        elif self.current_state in {EntryState.EXIT_LONG, EntryState.EXIT_SHORT}:
            exit_state = self.current_state
        else:
            raise ValueError(f"cannot exit from {self.current_state.value}")

        records: list[EntryTransition] = []
        if self.current_state != exit_state:
            records.append(self.apply_transition(exit_state, reason, ts, price, source="risk_engine"))
        records.append(self.apply_transition(EntryState.FLAT, reason, ts, price, source="position_sync"))
        return records


class EntryStateStore:
    def __init__(self) -> None:
        self._machines: dict[str, EntryStateMachine] = {}

    def get(self, symbol: str) -> EntryStateMachine:
        normalized = symbol.upper()
        if normalized not in self._machines:
            self._machines[normalized] = EntryStateMachine(normalized)
        return self._machines[normalized]

    def state_of(self, symbol: str) -> EntryState:
        return self.get(symbol).current_state


def _entry_target(signal_type: str, side: str, entry_mode: str) -> EntryState | None:
    mode = entry_mode if entry_mode in {"PROBE", "DIRECT"} else signal_type
    direction = side if side in {"LONG", "SHORT"} else signal_type
    if mode == "PROBE" and direction == "LONG":
        return EntryState.PROBE_LONG
    if mode == "PROBE" and direction == "SHORT":
        return EntryState.PROBE_SHORT
    if mode == "DIRECT" and direction == "LONG":
        return EntryState.DIRECT_LONG
    if mode == "DIRECT" and direction == "SHORT":
        return EntryState.DIRECT_SHORT
    return None


def _entry_mode_from_state(state: EntryState) -> str:
    if state in {EntryState.PROBE_LONG, EntryState.PROBE_SHORT}:
        return "PROBE"
    if state in {EntryState.DIRECT_LONG, EntryState.DIRECT_SHORT}:
        return "DIRECT"
    return "NONE"
