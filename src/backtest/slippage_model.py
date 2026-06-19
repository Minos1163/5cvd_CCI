from __future__ import annotations


def slippage_amount(price: float, slippage_bps: float) -> float:
    if price < 0 or slippage_bps < 0:
        raise ValueError("price and slippage_bps must be non-negative")
    return price * slippage_bps / 10000
