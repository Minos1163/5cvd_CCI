from __future__ import annotations

import json
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class ExplicitWatchlistEntry:
    """显式白名单条目(评审 7.2 规格):新增符号一律先 scout_only,达标后 promotion。"""

    symbol: str
    added_date: str = ""
    rationale: str = ""
    scan_scope: str = "scout_only"  # scout_only | full_pipeline
    review_period_days: int = 14
    promotion_criteria: Mapping[str, Any] = field(default_factory=lambda: {"min_samples": 15, "pf_min": 1.0})

    @property
    def normalized_symbol(self) -> str:
        return self.symbol.strip().upper()


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
    scout_micro_high_score_long_offset_min_score: float = 85.0
    scout_micro_high_score_long_offset_min_pa_score: float = 18.0
    scout_micro_high_score_long_offset_min_fib_score: float = 15.0
    scout_micro_high_score_long_offset_min_cvd_score: float = 14.0
    scout_micro_high_score_long_offset_min_rr_score: float = 2.0
    scout_micro_high_score_long_offset_quadrants: tuple[str, ...] = ("Q1", "Q3")
    scout_micro_fib_continuation_min_score: float = 82.0
    scout_micro_fib_continuation_min_ema_score: float = 16.0
    scout_micro_fib_continuation_min_cvd_score: float = 14.0
    scout_micro_fib_continuation_min_pa_score: float = 18.0
    scout_micro_watch_only_promotion_min_score: float = 85.0
    quadrant_trend_ema_min: float = 15.0
    quadrant_price_action_min: float = 10.0
    quadrant_flow_cvd_min: float = 14.0
    quadrant_cci_min: float = 7.0
    scout_micro_q1_rr_gap_enabled: bool = False
    scout_micro_q1_rr_gap_min_score: float = 82.0
    scout_micro_q1_rr_gap_min_cvd_score: float = 0.0
    scout_micro_q3_to_q1_enabled: bool = False
    scout_micro_q3_to_q1_min_score: float = 85.0
    scout_micro_q3_to_q1_min_cvd_score: float = 16.0
    scout_micro_q3_to_q1_confirm_bars: int = 3
    scout_micro_q3_to_q1_confirm_pa_score: float = 15.0
    scout_micro_q2_pending_enabled: bool = False
    scout_micro_q2_pending_min_score: float = 70.0
    scout_micro_q2_pending_min_pa_score: float = 18.0
    scout_micro_q2_pending_confirm_bars: int = 6
    scout_micro_q2_pending_confirm_cci_score: float = 9.0
    quadrant_pending_state_enabled: bool = True
    dry_run_q1_trend_launch_enabled: bool = False
    dry_run_q1_trend_launch_min_score: float = 82.0
    dry_run_q1_trend_launch_min_pa_score: float = 18.0
    dry_run_q1_trend_launch_min_fib_score: float = 15.0
    dry_run_q1_trend_launch_min_cvd_score: float = 16.0
    dry_run_q1_trend_launch_min_rr_score: float = 0.5
    dry_run_q1_trend_launch_extreme_ratio_min: float = 0.20
    dry_run_q1_trend_launch_extreme_ratio_max: float = 0.80
    dry_run_q1_trend_launch_base_exposure_pct: float = 0.025
    dry_run_q1_trend_launch_exit_mode: str = "trend_capture"
    dry_run_q1_trend_launch_allow_degraded_data: bool = False
    mirror_ab_enabled: bool = False
    mirror_ab_mode: str = "active"  # active | shadow_only(08-18 评审:mirror 降级 shadow,记录不计敞口/熔断)
    mirror_ab_payoff_pilot_enabled: bool = False
    mirror_ab_payoff_early_breakeven_trigger_r: float = 1.0
    mirror_ab_payoff_trend_trigger_r: float = 1.2
    mirror_ab_min_score: float = 85.0
    mirror_ab_notional: float = 50.0
    mirror_ab_allowed_reasons: tuple[str, ...] = ()
    mirror_ab_include_q1_watch: bool = False
    paper_ab_auto_report_enabled: bool = False
    paper_ab_report_closed_trade_interval: int = 20
    paper_ab_auto_switch_enabled: bool = False
    paper_ab_auto_switch_min_reports: int = 2
    paper_ab_auto_switch_min_closed_trades: int = 40
    paper_ab_auto_switch_payoff_mult: float = 1.3
    dry_run_q1_green_channel_enabled: bool = False
    dry_run_q1_green_channel_notional_mult: float = 0.5
    dry_run_q1_green_channel_min_score: float = 85.0
    dry_run_q1_green_channel_min_pa_score: float = 18.0
    dry_run_q1_green_channel_min_cvd_score: float = 16.0
    dry_run_q1_green_channel_base_exposure_pct: float = 0.05
    dry_run_q1_green_channel_exit_mode: str = "trend_capture"
    experiment_war_fund_loss_limit: float = -150.0
    experiment_daily_loss_limit: float = -200.0
    scout_micro_same_side_cooldown_hours: int = 2
    scout_micro_initial_stop_cooldown_hours: int = 6
    scout_micro_mission_stop_circuit_enabled: bool = False
    scout_micro_mission_stop_circuit_count: int = 3
    scout_micro_mission_stop_circuit_hours: int = 12
    scout_micro_allow_degraded_data: bool = False
    scout_micro_reversal_pivot_enabled: bool = False
    scout_micro_reversal_pivot_min_score: float = 70.0
    scout_micro_reversal_pivot_max_cvd_score: float = 16.0
    scout_micro_reversal_pivot_max_cci_score: float = 10.0
    scout_micro_reversal_pivot_notional: float = 25.0
    scout_micro_notional: float = 50.0
    scout_micro_leverage: int = 1
    paper_exit_mode: str = "legacy"
    paper_exit_trend_trigger_r: float = 1.5
    paper_exit_trailing_r_mult: float = 1.0
    scout_micro_exit_mode: str = "legacy"
    scout_micro_exit_trend_trigger_r: float = 1.5
    scout_micro_exit_trailing_r_mult: float = 1.0
    dry_run_symbols: tuple[str, ...] = ()
    explicit_watchlist: tuple[ExplicitWatchlistEntry, ...] = ()
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
        if "mirror_ab_allowed_reasons" in values:
            values["mirror_ab_allowed_reasons"] = _normalize_strings(values["mirror_ab_allowed_reasons"])
        if "mirror_ab_mode" in values:
            mode = str(values["mirror_ab_mode"]).strip().lower()
            if mode not in {"active", "shadow_only"}:
                raise ValueError(f"invalid mirror_ab_mode '{mode}' (allowed: active, shadow_only)")
            values["mirror_ab_mode"] = mode
        if "dry_run_symbols" in values:
            values["dry_run_symbols"] = _normalize_symbols(values["dry_run_symbols"])
        if "explicit_watchlist" in values:
            values["explicit_watchlist"] = _parse_explicit_watchlist(values["explicit_watchlist"], data.get("blacklist_symbols", ()))
        return cls(**values)


def load_entry_chain_config(path: str | Path) -> EntryChainConfig:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("entry-chain config must be a JSON object")
    return EntryChainConfig.from_mapping(payload)


def _normalize_symbols(values: Any) -> tuple[str, ...]:
    return tuple(symbol for item in values if (symbol := str(item).strip().upper()))


def _normalize_strings(values: Any) -> tuple[str, ...]:
    return tuple(value for item in values if (value := str(item).strip().upper()))


_ALLOWED_SCOPES = ("scout_only", "full_pipeline")


def _parse_explicit_watchlist(values: Any, blacklist: Any) -> tuple[ExplicitWatchlistEntry, ...]:
    """解析 explicit_watchlist 配置,校验:重复符号、非法 scan_scope、与黑名单冲突。"""
    if not isinstance(values, list):
        raise ValueError("explicit_watchlist must be a list")
    blacklist_set = {str(s).strip().upper() for s in (blacklist or ())}
    seen: set[str] = set()
    entries: list[ExplicitWatchlistEntry] = []
    for item in values:
        if not isinstance(item, dict):
            raise ValueError("each explicit_watchlist entry must be an object")
        symbol = str(item.get("symbol") or "").strip().upper()
        if not symbol:
            raise ValueError("explicit_watchlist entry missing symbol")
        if symbol in seen:
            raise ValueError(f"duplicate explicit_watchlist symbol: {symbol}")
        if symbol in blacklist_set:
            raise ValueError(f"explicit_watchlist symbol conflicts with blacklist: {symbol}")
        raw_scope = item.get("scan_scope")
        if raw_scope is None:
            scope = "scout_only"  # 缺失 → 首次添加默认 scout_only(评审规格)
        else:
            scope = str(raw_scope).strip().lower()
            if scope not in _ALLOWED_SCOPES:
                raise ValueError(f"invalid scan_scope '{scope}' for {symbol} (allowed: {_ALLOWED_SCOPES})")
        promotion = item.get("promotion_criteria")
        if promotion is not None and not isinstance(promotion, dict):
            raise ValueError(f"promotion_criteria for {symbol} must be an object")
        seen.add(symbol)
        entries.append(
            ExplicitWatchlistEntry(
                symbol=symbol,
                added_date=str(item.get("added_date") or ""),
                rationale=str(item.get("rationale") or ""),
                scan_scope=scope,
                review_period_days=int(item.get("review_period_days") or 14),
                promotion_criteria=dict(promotion) if promotion else {"min_samples": 15, "pf_min": 1.0},
            )
        )
    return tuple(entries)
