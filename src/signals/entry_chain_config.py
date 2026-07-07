from __future__ import annotations

import json
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class EntryChainConfig:
    direct_threshold: float = 82.0
    probe_threshold: float = 70.0
    watch_threshold: float = 60.0
    min_direction_direct_score: float = 0.64
    min_quality_direct_score: float = 0.73
    min_trigger_direct_score: float = 0.92
    min_cvd_direct_score: float = 0.61
    min_direction_probe_score: float = 0.56
    min_quality_probe_score: float = 0.45
    min_trigger_probe_score: float = 0.67
    min_cvd_probe_score: float = 0.45
    high_vol_atr_pct: float = 0.035
    low_vol_atr_pct: float = 0.010
    macro_daily_drop_block_pct: float = -0.05
    macro_weekly_drop_block_pct: float = -0.15
    direct_liquidity_ratio: float = 20.0
    probe_liquidity_ratio: float = 8.0
    max_active_symbols: int = 5
    daily_max_trades_base: int = 4
    min_daily_trades: int = 1
    max_symbol_trades_per_day: int = 1
    max_same_direction_exposure_pct: float = 1.20
    max_total_exposure_pct: float = 1.50
    margin_buffer_pct: float = 0.20
    base_direct_exposure_pct: float = 0.20
    max_large_cap_exposure_pct: float = 0.30
    max_mainstream_exposure_pct: float = 0.20
    max_high_beta_exposure_pct: float = 0.10
    probe_fraction: float = 0.25
    direct_risk_pct: float = 0.008
    probe_risk_pct: float = 0.003
    min_stop_pct: float = 0.005
    max_stop_pct: float = 0.04
    use_ema_architecture: bool = False
    ema200_gate_mode: str = "hard"
    ema200_buffer_pct: float = 0.003
    ema200_min_bars_stable: int = 3
    ema50_min_for_direct: float = 0.60
    ema50_min_for_probe: float = 0.40
    disable_probe: bool = False
    probe_conditions: Mapping[str, Any] | None = None
    blacklist_symbols: tuple[str, ...] = ()
    watch_only_symbols: tuple[str, ...] = ()
    observation_only_symbols: tuple[str, ...] = ()
    scout_micro_symbols: tuple[str, ...] = ()
    scout_micro_rr_gap_block_symbols: tuple[str, ...] = ()
    scout_micro_targeted_long_symbols: tuple[str, ...] = ()
    scout_micro_scout_only_symbols: tuple[str, ...] = ()
    scout_micro_min_score: float = 82.0
    scout_micro_non_rr_min_score: float = 85.0
    scout_micro_targeted_long_min_score: float = 82.0
    scout_micro_targeted_long_min_pa_score: float = 18.0
    scout_micro_targeted_long_min_rr_score: float = 3.0
    scout_micro_scout_only_min_score: float = 85.0
    scout_micro_scout_only_min_fib_score: float = 12.0
    scout_micro_scout_only_min_pa_score: float = 10.0
    scout_micro_scout_only_min_rr_score: float = 4.0
    scout_micro_same_side_cooldown_hours: int = 2
    scout_micro_initial_stop_cooldown_hours: int = 6
    scout_micro_notional: float = 50.0
    scout_micro_leverage: int = 1
    dry_run_symbols: tuple[str, ...] = ()
    dry_run_symbol_source: str = "configured"
    dry_run_rank_start: int = 3
    dry_run_rank_end: int = 25
    dry_run_warmup_15m_bars: int = 240
    use_fib_pa_architecture: bool = False
    fib_swing_fractal_k: int = 2
    fib_swing_min_atr_mult: float = 1.2
    fib_swing_min_spacing_bars: int = 6
    fib_swing_lookback_15m: int = 50
    fib_swing_lookback_1h: int = 30
    fib_extension_exhaustion_mult: float = 1.618
    fib_level_tolerance_atr_mult: float = 0.5
    pa_min_direct_score: float = 6.0
    fib_min_direct_score: float = 6.0
    rr_min_direct_score: float = 2.0
    leverage_5x_fib_min: float = 13.0
    leverage_5x_pa_min: float = 9.0
    leverage_5x_cci_min: float = 7.0
    leverage_5x_rr_min: float = 4.0
    weak_edge_direct_min_score: float = 82.0
    weak_edge_direct_max_score: float = 85.0
    weak_edge_probe_min_score: float = 77.0
    weak_edge_probe_max_score: float = 85.0
    rolling_symbol_cooldown_enabled: bool = False
    rolling_symbol_cooldown_stop_threshold: int = 2
    rolling_symbol_cooldown_window_hours: int = 48
    rolling_symbol_cooldown_hours: int = 24
    long_threshold_offset: float = 0.0
    short_threshold_offset: float = 0.0
    long_min_direction_direct_score: float | None = None
    long_min_quality_direct_score: float | None = None
    long_min_trigger_direct_score: float | None = None
    long_min_cvd_direct_score: float | None = None
    short_min_direction_direct_score: float | None = None
    short_min_quality_direct_score: float | None = None
    short_min_trigger_direct_score: float | None = None
    short_min_cvd_direct_score: float | None = None
    enable_long_context_discounts: bool = False
    long_overextension_quality_mult: float = 0.70
    long_upper_wick_trigger_mult: float = 0.60
    long_chase_trigger_mult: float = 0.75
    long_cvd_weak_mult: float = 0.80
    long_cvd_weak_threshold: float = 0.80
    long_overextension_watch_enabled: bool = False
    long_chase_watch_enabled: bool = False
    post_initial_stop_cooldown_enabled: bool = False
    post_initial_stop_cooldown_hours: int = 4
    portfolio_stop_circuit_enabled: bool = False
    portfolio_stop_circuit_count: int = 3
    portfolio_stop_circuit_hours: int = 4
    portfolio_daily_loss_circuit_enabled: bool = False
    portfolio_daily_loss_limit: float = -30.0

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "EntryChainConfig":
        allowed = {item.name for item in fields(cls)}
        unknown = sorted(set(data) - allowed)
        if unknown:
            raise ValueError(f"unknown entry-chain config keys: {unknown}")
        values = {key: data[key] for key in data if key in allowed}
        if "blacklist_symbols" in values:
            values["blacklist_symbols"] = _normalize_symbols(values["blacklist_symbols"])
        if "watch_only_symbols" in values:
            values["watch_only_symbols"] = _normalize_symbols(values["watch_only_symbols"])
        if "observation_only_symbols" in values:
            values["observation_only_symbols"] = _normalize_symbols(values["observation_only_symbols"])
        if "scout_micro_symbols" in values:
            values["scout_micro_symbols"] = _normalize_symbols(values["scout_micro_symbols"])
        if "scout_micro_rr_gap_block_symbols" in values:
            values["scout_micro_rr_gap_block_symbols"] = _normalize_symbols(values["scout_micro_rr_gap_block_symbols"])
        if "scout_micro_targeted_long_symbols" in values:
            values["scout_micro_targeted_long_symbols"] = _normalize_symbols(values["scout_micro_targeted_long_symbols"])
        if "scout_micro_scout_only_symbols" in values:
            values["scout_micro_scout_only_symbols"] = _normalize_symbols(values["scout_micro_scout_only_symbols"])
        if "dry_run_symbols" in values:
            values["dry_run_symbols"] = _normalize_symbols(values["dry_run_symbols"])
        return cls(**values)


def load_entry_chain_config(path: str | Path) -> EntryChainConfig:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("entry-chain config must be a JSON object")
    return EntryChainConfig.from_mapping(payload)


def _normalize_symbols(values: Any) -> tuple[str, ...]:
    return tuple(symbol for item in values if (symbol := str(item).strip().upper()))
