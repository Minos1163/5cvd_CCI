from src.data.universe_filter import (
    MAX_MISSING_BAR_RATIO,
    MAX_SPREAD_PCT,
    MAX_SYMBOLS,
    MAX_SYMBOLS_HARD_CAP,
    MIN_LISTING_DAYS,
    RECOMMENDED_MIN_24H_VOLUME_USD,
    REQUIRED_TIMEFRAMES,
    UNIVERSE_SCOPE,
    UNIVERSE_STATUSES,
    UniverseCandidate,
    UniverseMember,
    UniverseSnapshot,
    build_universe_snapshot,
    choose_by_correlation_preference,
    filter_universe,
    get_risk_tier,
    max_position_multiplier,
    validate_candidate,
    validate_snapshot_for_backtest,
)


def test_filter_universe_keeps_valid_usdt_perps_only():
    candidates = [
        UniverseCandidate("BTCUSDT", 1, 2_000_000_000, 500, 365, False, False),
        UniverseCandidate("DOGEUSDT", 9, 500_000_000, 0.25, 365, True, False),
        UniverseCandidate("NEWUSDT", 18, 100_000_000, 10, 10, False, False),
        UniverseCandidate("ETHBTC", 2, 1_000_000_000, 1, 365, False, False),
    ]
    selected = filter_universe(candidates, max_symbols=20, min_volume_24h=50_000_000)
    assert [item.symbol for item in selected] == ["BTCUSDT"]


def test_risk_tiers_and_multipliers():
    assert get_risk_tier("BTCUSDT") == "A"
    assert max_position_multiplier("ETHUSDT") == 2.0
    assert max_position_multiplier("SOLUSDT") == 1.0
    assert max_position_multiplier("LINKUSDT") == 0.75


def test_correlation_preference_prefers_btc_over_eth():
    selected = choose_by_correlation_preference(["ETHUSDT", "BTCUSDT"])
    assert selected == ["BTCUSDT"]


def test_universe_v1_thresholds_match_doc():
    assert UNIVERSE_SCOPE == "binance_usdt_perpetual"
    assert MAX_SYMBOLS == 20
    assert MAX_SYMBOLS_HARD_CAP == 30
    assert RECOMMENDED_MIN_24H_VOLUME_USD == 300_000_000
    assert MIN_LISTING_DAYS == 365
    assert MAX_SPREAD_PCT == 0.05
    assert MAX_MISSING_BAR_RATIO == 0.005
    assert REQUIRED_TIMEFRAMES == ("15m", "30m", "1h", "4h")
    assert UNIVERSE_STATUSES == ("ACTIVE", "SUSPENDED", "REMOVED")


def test_validate_candidate_rejects_spread_missing_history_and_monitoring_tag():
    good = UniverseCandidate(
        "BTCUSDT",
        market_cap_rank=1,
        volume_24h=1_000_000_000,
        price=50_000,
        listed_days=1000,
        contract_type="USDT_PERPETUAL",
        quote_asset="USDT",
        volume_rank=1,
        spread_pct=0.03,
        missing_bar_ratio=0.0,
        timeframes=("15m", "30m", "1h", "4h"),
    )
    assert validate_candidate(good).passed is True

    wide = good.with_updates(symbol="WIDEUSDT", spread_pct=0.20)
    assert validate_candidate(wide).passed is False

    missing = good.with_updates(symbol="MISSUSDT", missing_bar_ratio=0.01)
    assert validate_candidate(missing).passed is False

    monitored = good.with_updates(symbol="TAGUSDT", monitoring_tag=True)
    assert validate_candidate(monitored).passed is False


def test_universe_snapshot_tracks_version_status_and_reasons():
    member = UniverseMember(
        symbol="BTCUSDT",
        market_cap_rank=1,
        volume_rank=1,
        status="ACTIVE",
        added_time=1_700_000_000,
        removed_time=None,
        version="2026W01",
        reason="passes_v1_filters",
    )
    snapshot = build_universe_snapshot("2026W01", [member], created_at=1_700_000_000)

    assert snapshot.version == "2026W01"
    assert snapshot.active_symbols() == ["BTCUSDT"]
    assert snapshot.members[0].reason == "passes_v1_filters"


def test_backtest_must_use_historical_universe_version():
    snapshot = UniverseSnapshot(
        version="2026W01",
        members=[],
        created_at=1_700_000_000,
        effective_from=1_700_000_000,
        effective_to=1_700_604_800,
        update_reason="weekly_refresh",
    )
    assert validate_snapshot_for_backtest(snapshot, backtest_start=1_700_100_000).passed is True
    assert validate_snapshot_for_backtest(snapshot, backtest_start=1_600_000_000).passed is False
