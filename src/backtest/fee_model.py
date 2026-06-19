from __future__ import annotations


def fee(notional: float, fee_bps: float) -> float:
    if notional < 0 or fee_bps < 0:
        raise ValueError("notional and fee_bps must be non-negative")
    return notional * fee_bps / 10000
