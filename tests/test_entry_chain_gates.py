from src.signals.entry_chain import EntryChainContext
from src.signals.entry_chain_config import EntryChainConfig
from src.signals.entry_chain_gates import daily_max_trades, hard_block_reason


def context(**overrides):
    values = {
        "symbol": "HYPEUSDT",
        "timestamp": 100,
        "side": "LONG",
        "component_scores": {},
        "quote_volume_24h": 10_000_000.0,
        "atr_pct": 0.04,
        "expected_order_size": 1_000.0,
        "account_equity": 10_000.0,
        "available_margin": 8_000.0,
        "macro_weekly_drop_pct": -0.16,
    }
    values.update(overrides)
    return EntryChainContext(**values)


def test_weekly_risk_overrides_other_conditions():
    assert hard_block_reason(context(wick_anomaly_active=True), EntryChainConfig()) == "MACRO_WEEKLY_RISK"


def test_cooldown_ends_exactly_at_until_timestamp():
    config = EntryChainConfig()

    active = hard_block_reason(context(macro_weekly_drop_pct=0.0, cooldown_until_ts=101), config)
    ended = hard_block_reason(context(macro_weekly_drop_pct=0.0, cooldown_until_ts=100), config)

    assert active == "SYMBOL_COOLDOWN_ACTIVE"
    assert ended is None


def test_daily_max_trades_respects_configured_floor_in_low_volatility():
    config = EntryChainConfig(daily_max_trades_base=16, min_daily_trades=2)

    limit = daily_max_trades(
        context(
            macro_weekly_drop_pct=0.0,
            current_volatility_scale=0.05,
            normal_volatility_scale=1.0,
        ),
        config,
    )

    assert limit == 2
