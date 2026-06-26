from pathlib import Path

from src.signals.entry_chain_config import load_entry_chain_config


def test_dry_run_config_tiers_are_parseable_and_ordered():
    conservative = load_entry_chain_config("configs/entry_chain.dry_run_conservative.json")
    balanced = load_entry_chain_config("configs/entry_chain.dry_run_balanced.json")
    aggressive = load_entry_chain_config("configs/entry_chain.dry_run_aggressive.json")

    assert conservative.direct_threshold > balanced.direct_threshold > aggressive.direct_threshold
    assert conservative.daily_max_trades_base < balanced.daily_max_trades_base < aggressive.daily_max_trades_base
    assert conservative.max_total_exposure_pct <= balanced.max_total_exposure_pct <= aggressive.max_total_exposure_pct


def test_default_dry_run_config_matches_conservative_tier():
    default = Path("configs/entry_chain.dry_run.json").read_text(encoding="utf-8")
    conservative = Path("configs/entry_chain.dry_run_conservative.json").read_text(encoding="utf-8")

    assert default == conservative


def test_ema_ablation_configs_load_and_order_by_strictness():
    no_rsi = load_entry_chain_config("configs/entry_chain.dry_run_no_rsi.json")
    soft = load_entry_chain_config("configs/entry_chain.dry_run_ema_soft.json")
    hard = load_entry_chain_config("configs/entry_chain.dry_run_ema_hard.json")
    lifecycle_hardened = load_entry_chain_config("configs/entry_chain.dry_run_ema_soft_lifecycle_hardened.json")

    assert no_rsi.use_ema_architecture is False
    assert soft.use_ema_architecture is True
    assert soft.ema200_gate_mode == "soft"
    assert hard.use_ema_architecture is True
    assert hard.ema200_gate_mode == "hard"
    assert hard.direct_threshold >= soft.direct_threshold
    assert lifecycle_hardened.use_ema_architecture is True
    assert lifecycle_hardened.ema200_gate_mode == "soft"
    assert lifecycle_hardened.disable_probe is True
    assert lifecycle_hardened.blacklist_symbols == ("XRPUSDT",)
    assert lifecycle_hardened.long_threshold_offset == 10.0


def test_v4_side_and_symbol_configs_load():
    side_split = load_entry_chain_config("configs/entry_chain.dry_run_v4_side_split.json")
    symbol_bucket = load_entry_chain_config("configs/entry_chain.dry_run_v4_side_symbol_bucket.json")

    assert side_split.disable_probe is True
    assert side_split.long_threshold_offset == 14.0
    assert side_split.long_min_cvd_direct_score == 0.70
    assert symbol_bucket.watch_only_symbols == ("ADAUSDT", "XMRUSDT")
    assert symbol_bucket.blacklist_symbols == ("XRPUSDT",)


def test_v5_configs_load_without_v4_hard_long_minima():
    bucket = load_entry_chain_config("configs/entry_chain.dry_run_v5_symbol_bucket_only.json")
    context = load_entry_chain_config("configs/entry_chain.dry_run_v5_long_context_discount.json")
    combined = load_entry_chain_config("configs/entry_chain.dry_run_v5_symbol_bucket_long_context.json")

    assert bucket.watch_only_symbols == ("ADAUSDT", "XMRUSDT")
    assert bucket.long_threshold_offset == 10.0
    assert bucket.long_min_quality_direct_score is None
    assert context.enable_long_context_discounts is True
    assert context.long_threshold_offset == 10.0
    assert context.long_min_trigger_direct_score is None
    assert combined.watch_only_symbols == ("ADAUSDT", "XMRUSDT")
    assert combined.enable_long_context_discounts is True


def test_highest_win_dry_run_config_matches_v5_combined_entry_profile():
    highest_win = load_entry_chain_config("configs/entry_chain.dry_run_highest_win.json")

    assert highest_win.disable_probe is True
    assert highest_win.blacklist_symbols == ("XRPUSDT", "ZECUSDT")
    assert highest_win.watch_only_symbols == ("ADAUSDT", "XMRUSDT")
    assert highest_win.observation_only_symbols == ("XLMUSDT",)
    assert highest_win.rolling_symbol_cooldown_enabled is True
    assert highest_win.rolling_symbol_cooldown_stop_threshold == 2
    assert highest_win.rolling_symbol_cooldown_window_hours == 48
    assert highest_win.rolling_symbol_cooldown_hours == 24
    assert highest_win.dry_run_symbols == (
        "BNBUSDT",
        "XRPUSDT",
        "SOLUSDT",
        "TRXUSDT",
        "HYPEUSDT",
        "DOGEUSDT",
        "ZECUSDT",
        "XLMUSDT",
        "ADAUSDT",
        "XMRUSDT",
        "LINKUSDT",
        "CCUSDT",
        "TONUSDT",
    )
    assert highest_win.dry_run_symbol_source == "market_cap_rank"
    assert highest_win.dry_run_rank_start == 3
    assert highest_win.dry_run_rank_end == 25
    assert highest_win.dry_run_warmup_15m_bars == 240
    assert highest_win.enable_long_context_discounts is True
    assert highest_win.long_threshold_offset == 10.0


def test_fib_pa_dry_run_config_loads_and_is_dry_run_safe():
    config = load_entry_chain_config("configs/entry_chain.dry_run_fib_pa_v1.json")

    assert config.use_fib_pa_architecture is True
    assert config.disable_probe is True
    assert config.blacklist_symbols == ("XRPUSDT", "ZECUSDT")
    assert "XLMUSDT" in config.observation_only_symbols
    assert "TONUSDT" in config.observation_only_symbols
    assert config.dry_run_warmup_15m_bars == 240
