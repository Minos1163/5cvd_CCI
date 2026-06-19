from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


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
    EntryState.FLAT: {EntryState.WATCH_LONG, EntryState.WATCH_SHORT},
    EntryState.WATCH_LONG: {EntryState.PROBE_LONG, EntryState.DIRECT_LONG, EntryState.FLAT},
    EntryState.WATCH_SHORT: {EntryState.PROBE_SHORT, EntryState.DIRECT_SHORT, EntryState.FLAT},
    EntryState.PROBE_LONG: {EntryState.DIRECT_LONG, EntryState.EXIT_LONG},
    EntryState.PROBE_SHORT: {EntryState.DIRECT_SHORT, EntryState.EXIT_SHORT},
    EntryState.DIRECT_LONG: {EntryState.MANAGE_LONG, EntryState.EXIT_LONG},
    EntryState.DIRECT_SHORT: {EntryState.MANAGE_SHORT, EntryState.EXIT_SHORT},
    EntryState.MANAGE_LONG: {EntryState.EXIT_LONG},
    EntryState.MANAGE_SHORT: {EntryState.EXIT_SHORT},
    EntryState.EXIT_LONG: {EntryState.FLAT},
    EntryState.EXIT_SHORT: {EntryState.FLAT},
}


def transition(current: EntryState, target: EntryState) -> EntryState:
    if target not in ALLOWED_TRANSITIONS[current]:
        raise ValueError(f"invalid transition: {current.value} -> {target.value}")
    return target


@dataclass(frozen=True)
class EntryTransition:
    symbol: str
    from_state: EntryState
    to_state: EntryState
    reason: str
    ts: int
    price: float
    position_size: float = 0.0
    risk_value: float = 0.0

    def to_log_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "from_state": self.from_state.value,
            "to_state": self.to_state.value,
            "reason": self.reason,
            "ts": self.ts,
            "price": self.price,
            "position_size": self.position_size,
            "risk_value": self.risk_value,
        }


class EntryStateMachine:
    def __init__(self, symbol: str, initial_state: EntryState = EntryState.FLAT):
        self.symbol = symbol
        self.current_state = initial_state
        self.history: list[EntryTransition] = []

    def apply_transition(
        self,
        target: EntryState,
        reason: str,
        ts: int,
        price: float,
        position_size: float = 0.0,
        risk_value: float = 0.0,
    ) -> EntryTransition:
        source = self.current_state
        transition(source, target)
        record = EntryTransition(
            symbol=self.symbol,
            from_state=source,
            to_state=target,
            reason=reason,
            ts=ts,
            price=price,
            position_size=position_size,
            risk_value=risk_value,
        )
        self.current_state = target
        self.history.append(record)
        return record

    def apply_signal(
        self,
        signal: dict,
        ts: int,
        price: float,
        position_size: float = 0.0,
        risk_value: float = 0.0,
    ) -> list[EntryTransition]:
        signal_type = str(signal.get("signal_type", "")).upper()
        side = str(signal.get("side", "")).upper()
        reason = str(signal.get("reason", signal_type))

        if signal_type in {"WAIT", "NO_TRADE"}:
            return []
        if self.current_state != EntryState.FLAT:
            raise ValueError(f"signal entries require FLAT state, got {self.current_state.value}")

        if signal_type == "DIRECT" and side == "LONG":
            return [
                self.apply_transition(EntryState.WATCH_LONG, reason, ts, price, position_size, risk_value),
                self.apply_transition(EntryState.DIRECT_LONG, reason, ts, price, position_size, risk_value),
            ]
        if signal_type == "DIRECT" and side == "SHORT":
            return [
                self.apply_transition(EntryState.WATCH_SHORT, reason, ts, price, position_size, risk_value),
                self.apply_transition(EntryState.DIRECT_SHORT, reason, ts, price, position_size, risk_value),
            ]
        if signal_type == "PROBE" and side == "LONG":
            return [
                self.apply_transition(EntryState.WATCH_LONG, reason, ts, price, position_size, risk_value),
                self.apply_transition(EntryState.PROBE_LONG, reason, ts, price, position_size, risk_value),
            ]
        if signal_type == "PROBE" and side == "SHORT":
            return [
                self.apply_transition(EntryState.WATCH_SHORT, reason, ts, price, position_size, risk_value),
                self.apply_transition(EntryState.PROBE_SHORT, reason, ts, price, position_size, risk_value),
            ]
        raise ValueError(f"unsupported signal: {signal_type}/{side}")

    def maybe_upgrade_probe(self, r_multiple: float, ts: int, price: float) -> EntryTransition | None:
        if r_multiple < 1.0:
            return None
        if self.current_state == EntryState.PROBE_LONG:
            return self.apply_transition(EntryState.DIRECT_LONG, "probe reached 1R", ts, price)
        if self.current_state == EntryState.PROBE_SHORT:
            return self.apply_transition(EntryState.DIRECT_SHORT, "probe reached 1R", ts, price)
        return None

    def exit_current(self, reason: str, ts: int, price: float) -> list[EntryTransition]:
        if self.current_state in {EntryState.FLAT, EntryState.WATCH_LONG, EntryState.WATCH_SHORT}:
            return []
        if self.current_state in {EntryState.PROBE_LONG, EntryState.DIRECT_LONG, EntryState.MANAGE_LONG}:
            exit_state = EntryState.EXIT_LONG
        elif self.current_state in {EntryState.PROBE_SHORT, EntryState.DIRECT_SHORT, EntryState.MANAGE_SHORT}:
            exit_state = EntryState.EXIT_SHORT
        else:
            raise ValueError(f"cannot exit from {self.current_state.value}")
        return [
            self.apply_transition(exit_state, reason, ts, price),
            self.apply_transition(EntryState.FLAT, reason, ts, price),
        ]
