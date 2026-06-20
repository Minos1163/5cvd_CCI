from pathlib import Path

from src.signals.entry_chain_config import EntryChainConfig, load_entry_chain_config


def test_load_entry_chain_config_from_json(tmp_path):
    path = tmp_path / "entry_chain.json"
    path.write_text(
        '{"direct_threshold": 86, "daily_max_trades_base": 2, '
        '"disable_probe": true, "blacklist_symbols": ["XRPUSDT"], '
        '"watch_only_symbols": ["ADAUSDT"], '
        '"dry_run_symbols": ["bnbusdt", " solusdt "], '
        '"dry_run_symbol_source": "market_cap_rank", '
        '"dry_run_rank_start": 3, "dry_run_rank_end": 25, '
        '"dry_run_warmup_15m_bars": 84, '
        '"long_threshold_offset": 10, "short_threshold_offset": 0, '
        '"long_min_cvd_direct_score": 0.7}',
        encoding="utf-8",
    )

    config = load_entry_chain_config(path)

    assert isinstance(config, EntryChainConfig)
    assert config.direct_threshold == 86
    assert config.daily_max_trades_base == 2
    assert config.probe_threshold == 70.0
    assert config.disable_probe is True
    assert config.blacklist_symbols == ("XRPUSDT",)
    assert config.watch_only_symbols == ("ADAUSDT",)
    assert config.dry_run_symbols == ("BNBUSDT", "SOLUSDT")
    assert config.dry_run_symbol_source == "market_cap_rank"
    assert config.dry_run_rank_start == 3
    assert config.dry_run_rank_end == 25
    assert config.dry_run_warmup_15m_bars == 84
    assert config.long_threshold_offset == 10
    assert config.short_threshold_offset == 0
    assert config.long_min_cvd_direct_score == 0.7


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
