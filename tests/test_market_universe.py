from src.data.universe_filter import (
    UniverseCandidate,
    choose_by_correlation_preference,
    filter_universe,
    get_risk_tier,
    max_position_multiplier,
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
