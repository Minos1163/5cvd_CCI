from __future__ import annotations

from typing import Mapping

from src.signals.entry_chain_config import EntryChainConfig


SCORE_COMPONENTS = (
    "background_4h",
    "direction_1h",
    "quality_30m",
    "trigger_15m",
    "cvd_flow",
    "volatility_stop",
    "liquidity_execution",
    "market_regime",
)

BASE_WEIGHTS = {
    "background_4h": 8.0,
    "direction_1h": 25.0,
    "quality_30m": 22.0,
    "trigger_15m": 12.0,
    "cvd_flow": 18.0,
    "volatility_stop": 10.0,
    "liquidity_execution": 3.0,
    "market_regime": 2.0,
}

EMA_WEIGHTS = {
    "background_4h": 5.0,
    "direction_1h": 18.0,
    "quality_30m": 12.0,
    "trigger_15m": 7.0,
    "ema_50_quality": 15.0,
    "ema_momentum": 10.0,
    "cvd_flow": 18.0,
    "volatility_stop": 10.0,
    "liquidity_execution": 3.0,
    "market_regime": 2.0,
}


def dynamic_weights(atr_pct: float, config: EntryChainConfig | None = None) -> tuple[dict[str, float], list[str]]:
    cfg = config or EntryChainConfig()
    reasons: list[str] = []
    if cfg.use_ema_architecture:
        reasons.append("EMA_ARCHITECTURE_WEIGHTS")
        return dict(EMA_WEIGHTS), reasons
    if atr_pct > cfg.high_vol_atr_pct:
        fixed = {"volatility_stop": 20.0, "cvd_flow": 10.0}
        reasons.append("HIGH_VOL_DYNAMIC_WEIGHTS")
        return rescale_weights(fixed), reasons
    if atr_pct < cfg.low_vol_atr_pct:
        fixed = {"trigger_15m": 18.0, "cvd_flow": 18.0}
        reasons.append("LOW_VOL_DYNAMIC_WEIGHTS")
        return rescale_weights(fixed), reasons
    return dict(BASE_WEIGHTS), reasons


def rescale_weights(fixed: Mapping[str, float]) -> dict[str, float]:
    remaining_keys = [key for key in SCORE_COMPONENTS if key not in fixed]
    fixed_total = sum(fixed.values())
    base_remaining_total = sum(BASE_WEIGHTS[key] for key in remaining_keys)
    scale = (100.0 - fixed_total) / base_remaining_total
    weights = {key: round(BASE_WEIGHTS[key] * scale, 6) for key in remaining_keys}
    weights.update({key: float(value) for key, value in fixed.items()})
    drift = 100.0 - sum(weights.values())
    first_key = remaining_keys[0] if remaining_keys else next(iter(weights))
    weights[first_key] = round(weights[first_key] + drift, 6)
    return {key: weights[key] for key in SCORE_COMPONENTS}


def component_points(component_scores: Mapping[str, float], weights: Mapping[str, float]) -> dict[str, float]:
    return {
        key: round(max(0.0, min(1.0, float(component_scores.get(key, 0.0)))) * weight, 4)
        for key, weight in weights.items()
    }
