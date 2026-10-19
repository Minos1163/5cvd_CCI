from src.signals.portfolio_state import PortfolioState, SimulatedPosition


def test_portfolio_state_roundtrip_preserves_cooldown_and_counters():
    state = PortfolioState()
    state.record_entry("solusdt", timestamp=86_400 * 3 + 100, side="long", notional=250.0)
    state.start_cooldown("SOLUSDT", 86_400 * 3 + 3600)
    state.record_trade_return(0.5)
    state.simulated_positions.append(
        SimulatedPosition(symbol="ETHUSDT", side="SHORT", notional=100.0, expires_at_ts=999)
    )

    restored = PortfolioState.from_dict(state.to_dict())

    assert restored.cooldown_until("SOLUSDT") == 86_400 * 3 + 3600
    assert restored.is_cooldown_active("SOLUSDT", timestamp=86_400 * 3 + 200) is True
    assert restored.portfolio_trades_today(86_400 * 3 + 200) == 1
    assert restored.symbol_trades_today("SOLUSDT", 86_400 * 3 + 200) == 1
    assert restored.symbol_exposure_pct("SOLUSDT", equity=1000.0) == 0.25
    assert restored.same_direction_exposure_pct("LONG", equity=1000.0) == 0.25
    assert restored.trade_returns == [0.5]
    assert len(restored.simulated_positions) == 1
    assert restored.active_symbols == {"SOLUSDT"}


def test_from_dict_tolerates_missing_or_malformed_payload():
    assert PortfolioState.from_dict(None).cooldown_until_by_symbol == {}
    restored = PortfolioState.from_dict(
        {
            "trades_by_day": {"bad": 1, "3": 2},
            "symbol_trades_by_day": {"sol|bad": 1, "SOLUSDT|3": 4},
            "cooldown_until_by_symbol": {"SOLUSDT": "bad", "ETHUSDT": 100},
        }
    )
    assert restored.trades_by_day == {3: 2}
    assert restored.symbol_trades_by_day_map == {("SOLUSDT", 3): 4}
    assert restored.cooldown_until_by_symbol == {"ETHUSDT": 100}
