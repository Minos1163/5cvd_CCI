from __future__ import annotations

from dataclasses import asdict, dataclass

from src.execution.execution_engine import ExecutionRequest
from src.signals.entry_chain import EntryChainDecision


@dataclass(frozen=True)
class LiveEntryOrderDraft:
    approved: bool
    reason: str
    request: ExecutionRequest | None
    audit: dict

    def to_dict(self) -> dict:
        return {
            "approved": self.approved,
            "reason": self.reason,
            "request": None if self.request is None else self.request.to_dict(),
            "audit": self.audit,
        }


def build_live_entry_order_draft(
    decision: EntryChainDecision,
    *,
    event_id: str,
    trace_id: str,
    correlation_id: str,
    price: float,
    timestamp: int,
    strategy_version: str,
    min_quantity: float = 0.0,
) -> LiveEntryOrderDraft:
    audit = _decision_audit(decision)
    if decision.action not in {"PROBE", "DIRECT"} or not decision.risk_allowed:
        return LiveEntryOrderDraft(
            approved=False,
            reason="entry chain action does not allow live order draft",
            request=None,
            audit=audit,
        )
    if price <= 0:
        return LiveEntryOrderDraft(False, "price must be positive", None, audit)
    quantity = decision.notional_hint / price
    if quantity <= 0 or quantity < min_quantity:
        return LiveEntryOrderDraft(False, "entry chain notional does not meet quantity requirements", None, audit)
    position_side = decision.side
    order_side = "BUY" if decision.side == "LONG" else "SELL"
    request = ExecutionRequest(
        request_id=f"{event_id}:{decision.action.lower()}",
        event_id=event_id,
        trace_id=trace_id,
        correlation_id=correlation_id,
        symbol=str(decision.metadata.get("symbol", "")),
        side=order_side,
        order_type="MARKET",
        quantity=quantity,
        price=price,
        reduce_only=False,
        position_side=position_side,
        time_in_force=None,
        stop_price=None,
        take_profit_price=None,
        entry_mode=decision.action,
        strategy_state=f"{decision.action}_{position_side}",
        strategy_version=strategy_version,
        risk_tag="entry",
        expected_position_qty=quantity,
        expected_position_side=position_side,
        timestamp=timestamp,
        risk_snapshot={
            "allow_trade": decision.risk_allowed,
            "entry_chain_score": decision.score,
            "entry_chain_reasons": list(decision.reasons),
        },
        position_snapshot={},
        entry_chain_snapshot=audit,
    )
    return LiveEntryOrderDraft(True, "approved", request, audit)


def build_rejected_live_entry_order_draft(decision: EntryChainDecision) -> LiveEntryOrderDraft:
    return LiveEntryOrderDraft(
        approved=False,
        reason="entry chain rejected live entry",
        request=None,
        audit=_decision_audit(decision),
    )


def _decision_audit(decision: EntryChainDecision) -> dict:
    payload = asdict(decision)
    payload["reasons"] = list(decision.reasons)
    return payload

