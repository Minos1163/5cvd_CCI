from pathlib import Path

from src.signals.entry_chain_config import EntryChainConfig, load_entry_chain_config


def test_load_entry_chain_config_from_json(tmp_path):
    path = tmp_path / "entry_chain.json"
    path.write_text(
        '{"direct_threshold": 86, "daily_max_trades_base": 2, '
        '"min_daily_trades": 2, '
        '"disable_probe": true, "blacklist_symbols": ["XRPUSDT"], '
        '"watch_only_symbols": ["ADAUSDT"], '
        '"observation_only_symbols": ["xlmusdt"], '
        '"scout_micro_symbols": [" xlmusdt "], '
        '"scout_micro_rr_gap_block_symbols": ["xlmusdt"], '
        '"scout_micro_targeted_long_symbols": ["ccusdt"], '
        '"scout_micro_scout_only_symbols": ["xmrusdt", " zecusdt "], '
        '"scout_micro_min_score": 82, '
        '"scout_micro_non_rr_min_score": 85, '
        '"scout_micro_targeted_long_min_score": 82, '
        '"scout_micro_targeted_long_min_pa_score": 18, '
        '"scout_micro_targeted_long_min_rr_score": 3, '
        '"scout_micro_scout_only_min_score": 85, '
        '"scout_micro_scout_only_min_fib_score": 12, '
        '"scout_micro_scout_only_min_pa_score": 10, '
        '"scout_micro_scout_only_min_rr_score": 4, '
        '"scout_micro_high_score_long_offset_min_score": 85, '
        '"scout_micro_high_score_long_offset_min_pa_score": 18, '
        '"scout_micro_high_score_long_offset_min_fib_score": 15, '
        '"scout_micro_high_score_long_offset_min_cvd_score": 14, '
        '"scout_micro_high_score_long_offset_min_rr_score": 2, '
        '"scout_micro_fib_continuation_min_score": 82, '
        '"scout_micro_fib_continuation_min_ema_score": 16, '
        '"scout_micro_fib_continuation_min_cvd_score": 14, '
        '"scout_micro_fib_continuation_min_pa_score": 18, '
        '"scout_micro_watch_only_promotion_min_score": 85, '
        '"quadrant_trend_ema_min": 15, '
        '"quadrant_price_action_min": 10, '
        '"quadrant_flow_cvd_min": 14, '
        '"quadrant_cci_min": 7, '
        '"scout_micro_q1_rr_gap_enabled": true, '
        '"scout_micro_q1_rr_gap_min_score": 82, '
        '"scout_micro_q1_rr_gap_min_cvd_score": 16, '
        '"scout_micro_q3_to_q1_enabled": true, '
        '"scout_micro_q3_to_q1_min_score": 85, '
        '"scout_micro_q3_to_q1_min_cvd_score": 16, '
        '"scout_micro_q3_to_q1_confirm_bars": 3, '
        '"scout_micro_q3_to_q1_confirm_pa_score": 15, '
        '"scout_micro_q2_pending_enabled": true, '
        '"scout_micro_q2_pending_min_score": 85, '
        '"scout_micro_q2_pending_min_pa_score": 18, '
        '"scout_micro_q2_pending_confirm_bars": 6, '
        '"scout_micro_q2_pending_confirm_cci_score": 9, '
        '"quadrant_pending_state_enabled": true, '
        '"dry_run_q1_trend_launch_enabled": true, '
        '"dry_run_q1_trend_launch_min_score": 82, '
        '"dry_run_q1_trend_launch_min_pa_score": 18, '
        '"dry_run_q1_trend_launch_min_fib_score": 15, '
        '"dry_run_q1_trend_launch_min_cvd_score": 16, '
        '"dry_run_q1_trend_launch_min_rr_score": 0.5, '
        '"dry_run_q1_trend_launch_base_exposure_pct": 0.025, '
        '"dry_run_q1_trend_launch_exit_mode": "trend_capture", '
        '"dry_run_q1_trend_launch_allow_degraded_data": true, '
        '"mirror_ab_enabled": true, '
        '"mirror_ab_min_score": 85, '
        '"mirror_ab_notional": 50, '
        '"mirror_ab_allowed_reasons": ["below_risk_reward_geometry", " SYMBOL_WATCH_ONLY "], '
        '"mirror_ab_include_q1_watch": true, '
        '"paper_ab_auto_report_enabled": true, '
        '"paper_ab_report_closed_trade_interval": 20, '
        '"paper_ab_auto_switch_enabled": true, '
        '"paper_ab_auto_switch_min_reports": 2, '
        '"paper_ab_auto_switch_min_closed_trades": 40, '
        '"paper_ab_auto_switch_payoff_mult": 1.3, '
        '"dry_run_q1_green_channel_enabled": true, '
        '"dry_run_q1_green_channel_notional_mult": 0.5, '
        '"dry_run_q1_green_channel_min_score": 85, '
        '"dry_run_q1_green_channel_min_pa_score": 18, '
        '"dry_run_q1_green_channel_min_cvd_score": 16, '
        '"dry_run_q1_green_channel_base_exposure_pct": 0.05, '
        '"dry_run_q1_green_channel_exit_mode": "trend_capture", '
        '"experiment_war_fund_loss_limit": -150, '
        '"experiment_daily_loss_limit": -200, '
        '"scout_micro_same_side_cooldown_hours": 2, '
        '"scout_micro_initial_stop_cooldown_hours": 6, '
        '"scout_micro_mission_stop_circuit_enabled": true, '
        '"scout_micro_mission_stop_circuit_count": 3, '
        '"scout_micro_mission_stop_circuit_hours": 12, '
        '"scout_micro_allow_degraded_data": true, '
        '"scout_micro_reversal_pivot_enabled": true, '
        '"scout_micro_reversal_pivot_min_score": 70, '
        '"scout_micro_reversal_pivot_max_cvd_score": 16, '
        '"scout_micro_reversal_pivot_max_cci_score": 10, '
        '"scout_micro_reversal_pivot_notional": 25, '
        '"scout_micro_notional": 50, '
        '"scout_micro_leverage": 1, '
        '"paper_exit_mode": "legacy", '
        '"paper_exit_trend_trigger_r": 1.5, '
        '"paper_exit_trailing_r_mult": 1.0, '
        '"scout_micro_exit_mode": "trend_capture", '
        '"scout_micro_exit_trend_trigger_r": 1.5, '
        '"scout_micro_exit_trailing_r_mult": 1.0, '
        '"dry_run_symbols": ["bnbusdt", " solusdt "], '
        '"dry_run_symbol_source": "market_cap_rank", '
        '"dry_run_rank_start": 3, "dry_run_rank_end": 25, '
        '"dry_run_warmup_15m_bars": 240, '
        '"weak_edge_direct_min_score": 82, "weak_edge_direct_max_score": 85, '
        '"weak_edge_probe_min_score": 77, "weak_edge_probe_max_score": 85, '
        '"rolling_symbol_cooldown_enabled": true, "rolling_symbol_cooldown_stop_threshold": 2, '
        '"rolling_symbol_cooldown_window_hours": 48, "rolling_symbol_cooldown_hours": 24, '
        '"probe_conditions": {"enabled": true, "min_score": 72, "min_fib_score": 12}, '
        '"long_threshold_offset": 10, "short_threshold_offset": 0, '
        '"long_min_cvd_direct_score": 0.7, '
        '"long_overextension_watch_enabled": true, "long_chase_watch_enabled": true, '
        '"post_initial_stop_cooldown_enabled": true, "post_initial_stop_cooldown_hours": 4, '
        '"portfolio_stop_circuit_enabled": true, "portfolio_stop_circuit_count": 3, '
        '"portfolio_stop_circuit_hours": 4, '
        '"portfolio_daily_loss_circuit_enabled": true, "portfolio_daily_loss_limit": -30.0}',
        encoding="utf-8",
    )

    config = load_entry_chain_config(path)

    assert isinstance(config, EntryChainConfig)
    assert config.direct_threshold == 86
    assert config.daily_max_trades_base == 2
    assert config.min_daily_trades == 2
    assert config.probe_threshold == 70.0
    assert config.disable_probe is True
    assert config.blacklist_symbols == ("XRPUSDT",)
    assert config.watch_only_symbols == ("ADAUSDT",)
    assert config.observation_only_symbols == ("XLMUSDT",)
    assert config.scout_micro_symbols == ("XLMUSDT",)
    assert config.scout_micro_rr_gap_block_symbols == ("XLMUSDT",)
    assert config.scout_micro_targeted_long_symbols == ("CCUSDT",)
    assert config.scout_micro_scout_only_symbols == ("XMRUSDT", "ZECUSDT")
    assert config.scout_micro_min_score == 82
    assert config.scout_micro_non_rr_min_score == 85
    assert config.scout_micro_targeted_long_min_score == 82
    assert config.scout_micro_targeted_long_min_pa_score == 18
    assert config.scout_micro_targeted_long_min_rr_score == 3
    assert config.scout_micro_scout_only_min_score == 85
    assert config.scout_micro_scout_only_min_fib_score == 12
    assert config.scout_micro_scout_only_min_pa_score == 10
    assert config.scout_micro_scout_only_min_rr_score == 4
    assert config.scout_micro_high_score_long_offset_min_score == 85
    assert config.scout_micro_high_score_long_offset_min_pa_score == 18
    assert config.scout_micro_high_score_long_offset_min_fib_score == 15
    assert config.scout_micro_high_score_long_offset_min_cvd_score == 14
    assert config.scout_micro_high_score_long_offset_min_rr_score == 2
    assert config.scout_micro_fib_continuation_min_score == 82
    assert config.scout_micro_fib_continuation_min_ema_score == 16
    assert config.scout_micro_fib_continuation_min_cvd_score == 14
    assert config.scout_micro_fib_continuation_min_pa_score == 18
    assert config.scout_micro_watch_only_promotion_min_score == 85
    assert config.quadrant_trend_ema_min == 15
    assert config.quadrant_price_action_min == 10
    assert config.quadrant_flow_cvd_min == 14
    assert config.quadrant_cci_min == 7
    assert config.scout_micro_q1_rr_gap_enabled is True
    assert config.scout_micro_q1_rr_gap_min_score == 82
    assert config.scout_micro_q1_rr_gap_min_cvd_score == 16
    assert config.scout_micro_q3_to_q1_enabled is True
    assert config.scout_micro_q3_to_q1_min_score == 85
    assert config.scout_micro_q3_to_q1_min_cvd_score == 16
    assert config.scout_micro_q3_to_q1_confirm_bars == 3
    assert config.scout_micro_q3_to_q1_confirm_pa_score == 15
    assert config.scout_micro_q2_pending_enabled is True
    assert config.scout_micro_q2_pending_min_score == 85
    assert config.scout_micro_q2_pending_min_pa_score == 18
    assert config.scout_micro_q2_pending_confirm_bars == 6
    assert config.scout_micro_q2_pending_confirm_cci_score == 9
    assert config.quadrant_pending_state_enabled is True
    assert config.dry_run_q1_trend_launch_enabled is True
    assert config.dry_run_q1_trend_launch_min_score == 82
    assert config.dry_run_q1_trend_launch_min_pa_score == 18
    assert config.dry_run_q1_trend_launch_min_fib_score == 15
    assert config.dry_run_q1_trend_launch_min_cvd_score == 16
    assert config.dry_run_q1_trend_launch_min_rr_score == 0.5
    assert config.dry_run_q1_trend_launch_base_exposure_pct == 0.025
    assert config.dry_run_q1_trend_launch_exit_mode == "trend_capture"
    assert config.dry_run_q1_trend_launch_allow_degraded_data is True
    assert config.mirror_ab_enabled is True
    assert config.mirror_ab_min_score == 85
    assert config.mirror_ab_notional == 50
    assert config.mirror_ab_allowed_reasons == ("BELOW_RISK_REWARD_GEOMETRY", "SYMBOL_WATCH_ONLY")
    assert config.mirror_ab_include_q1_watch is True
    assert config.paper_ab_auto_report_enabled is True
    assert config.paper_ab_report_closed_trade_interval == 20
    assert config.paper_ab_auto_switch_enabled is True
    assert config.paper_ab_auto_switch_min_reports == 2
    assert config.paper_ab_auto_switch_min_closed_trades == 40
    assert config.paper_ab_auto_switch_payoff_mult == 1.3
    assert config.dry_run_q1_green_channel_enabled is True
    assert config.dry_run_q1_green_channel_notional_mult == 0.5
    assert config.dry_run_q1_green_channel_min_score == 85
    assert config.dry_run_q1_green_channel_min_pa_score == 18
    assert config.dry_run_q1_green_channel_min_cvd_score == 16
    assert config.dry_run_q1_green_channel_base_exposure_pct == 0.05
    assert config.dry_run_q1_green_channel_exit_mode == "trend_capture"
    assert config.experiment_war_fund_loss_limit == -150
    assert config.experiment_daily_loss_limit == -200
    assert config.scout_micro_same_side_cooldown_hours == 2
    assert config.scout_micro_initial_stop_cooldown_hours == 6
    assert config.scout_micro_mission_stop_circuit_enabled is True
    assert config.scout_micro_mission_stop_circuit_count == 3
    assert config.scout_micro_mission_stop_circuit_hours == 12
    assert config.scout_micro_allow_degraded_data is True
    assert config.scout_micro_reversal_pivot_enabled is True
    assert config.scout_micro_reversal_pivot_min_score == 70
    assert config.scout_micro_reversal_pivot_max_cvd_score == 16
    assert config.scout_micro_reversal_pivot_max_cci_score == 10
    assert config.scout_micro_reversal_pivot_notional == 25
    assert config.scout_micro_notional == 50
    assert config.scout_micro_leverage == 1
    assert config.paper_exit_mode == "legacy"
    assert config.paper_exit_trend_trigger_r == 1.5
    assert config.paper_exit_trailing_r_mult == 1.0
    assert config.scout_micro_exit_mode == "trend_capture"
    assert config.scout_micro_exit_trend_trigger_r == 1.5
    assert config.scout_micro_exit_trailing_r_mult == 1.0
    assert config.dry_run_symbols == ("BNBUSDT", "SOLUSDT")
    assert config.dry_run_symbol_source == "market_cap_rank"
    assert config.dry_run_rank_start == 3
    assert config.dry_run_rank_end == 25
    assert config.dry_run_warmup_15m_bars == 240
    assert config.weak_edge_direct_min_score == 82
    assert config.weak_edge_direct_max_score == 85
    assert config.weak_edge_probe_min_score == 77
    assert config.weak_edge_probe_max_score == 85
    assert config.rolling_symbol_cooldown_enabled is True
    assert config.rolling_symbol_cooldown_stop_threshold == 2
    assert config.rolling_symbol_cooldown_window_hours == 48
    assert config.rolling_symbol_cooldown_hours == 24
    assert config.probe_conditions == {"enabled": True, "min_score": 72, "min_fib_score": 12}
    assert config.long_threshold_offset == 10
    assert config.short_threshold_offset == 0
    assert config.long_min_cvd_direct_score == 0.7
    assert config.long_overextension_watch_enabled is True
    assert config.long_chase_watch_enabled is True
    assert config.post_initial_stop_cooldown_enabled is True
    assert config.post_initial_stop_cooldown_hours == 4
    assert config.portfolio_stop_circuit_enabled is True
    assert config.portfolio_stop_circuit_count == 3
    assert config.portfolio_stop_circuit_hours == 4
    assert config.portfolio_daily_loss_circuit_enabled is True
    assert config.portfolio_daily_loss_limit == -30.0


def test_load_v5_long_context_discount_fields(tmp_path):
    path = tmp_path / "entry_chain_v5.json"
    path.write_text(
        '{"enable_long_context_discounts": true, '
        '"long_overextension_quality_mult": 0.7, '
        '"long_upper_wick_trigger_mult": 0.6, '
        '"long_chase_trigger_mult": 0.75, '
        '"long_cvd_weak_mult": 0.8}',
        encoding="utf-8",
    )

    config = load_entry_chain_config(path)

    assert config.enable_long_context_discounts is True
    assert config.long_overextension_quality_mult == 0.7
    assert config.long_upper_wick_trigger_mult == 0.6
    assert config.long_chase_trigger_mult == 0.75
    assert config.long_cvd_weak_mult == 0.8


def test_load_fib_pa_fields_from_json(tmp_path):
    path = tmp_path / "entry_chain_fib_pa.json"
    path.write_text(
        '{"use_fib_pa_architecture": true, '
        '"fib_swing_fractal_k": 2, '
        '"fib_swing_min_atr_mult": 1.2, '
        '"fib_extension_exhaustion_mult": 1.618, '
        '"pa_min_direct_score": 6.0, '
        '"fib_min_direct_score": 6.0, '
        '"rr_min_direct_score": 2.0, '
        '"leverage_5x_fib_min": 13.0, '
        '"leverage_5x_pa_min": 9.0, '
        '"leverage_5x_cci_min": 7.0, '
        '"leverage_5x_rr_min": 4.0}',
        encoding="utf-8",
    )

    config = load_entry_chain_config(path)

    assert config.use_fib_pa_architecture is True
    assert config.fib_swing_fractal_k == 2
    assert config.fib_swing_min_atr_mult == 1.2
    assert config.fib_extension_exhaustion_mult == 1.618
    assert config.pa_min_direct_score == 6.0
    assert config.fib_min_direct_score == 6.0
    assert config.rr_min_direct_score == 2.0
    assert config.leverage_5x_fib_min == 13.0
    assert config.leverage_5x_pa_min == 9.0
    assert config.leverage_5x_cci_min == 7.0
    assert config.leverage_5x_rr_min == 4.0


def test_unknown_config_key_is_rejected(tmp_path):
    path = tmp_path / "entry_chain.json"
    path.write_text('{"unknown": 1}', encoding="utf-8")

    try:
        load_entry_chain_config(path)
    except ValueError as exc:
        assert "unknown entry-chain config keys" in str(exc)
    else:
        raise AssertionError("expected unknown key rejection")


def test_dry_run_config_is_conservative_and_parseable():
    config = load_entry_chain_config(Path("configs/entry_chain.dry_run.json"))

    assert config.direct_threshold >= 85
    assert config.daily_max_trades_base <= 3
    assert config.max_active_symbols <= 5
