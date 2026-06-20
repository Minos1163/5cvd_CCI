from src.signals.portfolio_state import PortfolioState


def test_portfolio_state_tracks_daily_and_symbol_budget_by_utc_day():
    state = PortfolioState()
    ts = 1_766_000_000

    state.record_entry("SOLUSDT", ts, "LONG", 500)

    assert state.portfolio_trades_today(ts) == 1
    assert state.symbol_trades_today("SOLUSDT", ts) == 1
    assert state.symbol_trades_today("BNBUSDT", ts) == 0


def test_release_position_reduces_exposure_and_active_symbols():
    state = PortfolioState()
    ts = 1_766_000_000

    state.record_entry("SOLUSDT", ts, "LONG", 500)
    state.release_position("SOLUSDT", "LONG", 500)

    assert state.active_symbol_count() == 0
    assert state.symbol_exposure_pct("SOLUSDT", 10_000) == 0.0
    assert state.same_direction_exposure_pct("LONG", 10_000) == 0.0


def test_expire_positions_releases_synthetic_backtest_positions():
    state = PortfolioState()
    ts = 1_766_000_000

    state.record_entry("SOLUSDT", ts, "LONG", 500, expires_at_ts=ts + 1_800)
    state.record_entry("BNBUSDT", ts, "SHORT", 700, expires_at_ts=ts + 3_600)

    state.expire_positions(ts + 1_800)

    assert state.active_symbol_count() == 1
    assert state.symbol_exposure_pct("SOLUSDT", 10_000) == 0.0
    assert state.symbol_exposure_pct("BNBUSDT", 10_000) == 0.07
    assert state.same_direction_exposure_pct("SHORT", 10_000) == 0.07


def test_symbol_cooldown_is_timestamp_based_and_symbol_specific():
    state = PortfolioState()
    state.start_cooldown("SOLUSDT", until_ts=1_000)

    assert state.cooldown_until("SOLUSDT") == 1_000
    assert state.cooldown_until("BNBUSDT") is None
    assert state.is_cooldown_active("SOLUSDT", 999) is True
    assert state.is_cooldown_active("SOLUSDT", 1_000) is False


def test_rolling_sharpe_defaults_to_none_until_enough_trades():
    state = PortfolioState()
    for pnl in [1, -1, 2]:
        state.record_trade_return(pnl)

    assert state.rolling_sharpe_20() is None


def test_rolling_sharpe_is_available_after_twenty_trades():
    state = PortfolioState()
    for index in range(20):
        state.record_trade_return(1.0 if index % 2 == 0 else -0.2)

    assert state.rolling_sharpe_20() is not None
