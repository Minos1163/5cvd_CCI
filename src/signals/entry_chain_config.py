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
    blacklist_symbols: tuple[str, ...] = ()
    watch_only_symbols: tuple[str, ...] = ()
    dry_run_symbols: tuple[str, ...] = ()
    dry_run_symbol_source: str = "configured"
    dry_run_rank_start: int = 3
    dry_run_rank_end: int = 25
    dry_run_warmup_15m_bars: int = 240
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
