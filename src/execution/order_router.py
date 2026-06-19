from __future__ import annotations

from src.core.models import OrderIntent, RiskDecision


def build_order_intent(decision: RiskDecision, correlation_id: str) -> OrderIntent:
    if not decision.approved:
        raise ValueError(f"risk rejected: {decision.reason}")
    return OrderIntent(
        symbol=decision.symbol,
        side=decision.side,
        position_side=decision.side,
        quantity=decision.quantity,
        order_type="MARKET",
        correlation_id=correlation_id,
    )
