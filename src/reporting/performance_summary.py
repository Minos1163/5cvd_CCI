from __future__ import annotations

from src.backtest.metrics import profit_factor, win_rate


def summarize_trade_pnls(pnls: list[float]) -> dict:
    return {
        "trade_count": len(pnls),
        "win_rate": win_rate(pnls),
        "profit_factor": profit_factor(pnls),
        "net_pnl": sum(pnls),
    }
