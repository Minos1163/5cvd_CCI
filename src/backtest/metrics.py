from __future__ import annotations


def profit_factor(profits: list[float]) -> float | None:
    gross_profit = sum(value for value in profits if value > 0)
    gross_loss = abs(sum(value for value in profits if value < 0))
    if gross_loss == 0:
        return None
    return gross_profit / gross_loss


def win_rate(profits: list[float]) -> float | None:
    if not profits:
        return None
    return len([value for value in profits if value > 0]) / len(profits)
