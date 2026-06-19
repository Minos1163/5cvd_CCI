from __future__ import annotations


def next_bar_market_fill(next_open: float, side: str, slippage_bps: float) -> float:
    adjustment = next_open * slippage_bps / 10000
    if side.upper() in {"BUY", "LONG"}:
        return next_open + adjustment
    if side.upper() in {"SELL", "SHORT"}:
        return next_open - adjustment
    raise ValueError("side must be BUY/LONG or SELL/SHORT")
