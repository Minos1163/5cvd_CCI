from __future__ import annotations


def estimate_stress_loss_pct(exposure_pct: float, leverage: float, adverse_move_pct: float) -> float:
    return round(max(0.0, exposure_pct) * max(0.0, leverage) * max(0.0, adverse_move_pct), 6)


def stress_decision(
    *,
    exposure_pct: float,
    leverage: float,
    adverse_move_pct: float,
    max_loss_pct: float = 0.25,
) -> dict[str, float | str]:
    estimated = estimate_stress_loss_pct(exposure_pct, leverage, adverse_move_pct)
    return {
        "action": "BLOCK" if estimated > max_loss_pct else "ALLOW",
        "estimated_loss_pct": estimated,
        "max_loss_pct": max_loss_pct,
        "adverse_move_pct": adverse_move_pct,
        "leverage": leverage,
        "exposure_pct": exposure_pct,
    }

