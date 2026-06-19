from __future__ import annotations


def exposure_allowed(current_exposure: float, new_notional: float, equity: float, max_exposure_pct: float) -> bool:
    if equity <= 0:
        return False
    return (current_exposure + new_notional) / equity <= max_exposure_pct
