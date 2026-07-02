from src.signals.entry_chain import EntryChainContext, evaluate_entry_chain
from src.signals.entry_chain_config import EntryChainConfig


def candidate(**overrides):
    base = EntryChainContext(
        symbol="SOLUSDT",
        timestamp=1_766_000_000,
        side="LONG",
        component_scores={
            "background_4h": 1.0,
            "direction_1h": 1.0,
            "quality_30m": 1.0,
            "trigger_15m": 1.0,
            "cvd_flow": 1.0,
            "volatility_stop": 1.0,
            "liquidity_execution": 1.0,
            "market_regime": 1.0,
        },
        quote_volume_24h=200_000_000.0,
        atr_pct=0.018,
        expected_order_size=2_000.0,
        account_equity=10_000.0,
        available_margin=8_000.0,
    )
    return base.with_updates(**overrides)


def test_macro_daily_drop_blocks_direct_but_allows_probe():
    decision = evaluate_entry_chain(candidate(macro_daily_drop_pct=-0.06))

    assert decision.action == "PROBE"
    assert "MACRO_DAILY_RISK_DIRECT_BLOCK" in decision.reasons
    assert decision.risk_allowed is True


def test_weekly_macro_drop_blocks_all_trades():
    decision = evaluate_entry_chain(candidate(macro_weekly_drop_pct=-0.16))

    assert decision.action == "NO_TRADE"
    assert decision.risk_allowed is False
    assert "MACRO_WEEKLY_RISK" in decision.reasons


def test_high_volatility_uses_dynamic_weights():
    decision = evaluate_entry_chain(candidate(atr_pct=0.04))

    assert decision.weights["volatility_stop"] == 20.0
    assert decision.weights["cvd_flow"] == 10.0
    assert round(sum(decision.weights.values()), 6) == 100.0
    assert "HIGH_VOL_DYNAMIC_WEIGHTS" in decision.reasons


def test_low_volatility_raises_trigger_weight():
    decision = evaluate_entry_chain(candidate(atr_pct=0.006))

    assert decision.weights["trigger_15m"] == 18.0
    assert decision.weights["cvd_flow"] == 18.0
    assert round(sum(decision.weights.values()), 6) == 100.0
    assert "LOW_VOL_DYNAMIC_WEIGHTS" in decision.reasons


def test_high_beta_symbol_is_probe_only_and_capped():
    decision = evaluate_entry_chain(candidate(symbol="HYPEUSDT"))

    assert decision.action == "PROBE"
    assert decision.max_symbol_exposure_pct == 0.10
    assert "HIGH_BETA_PROBE_ONLY" in decision.reasons


def test_liquidity_ratio_blocks_direct_and_probe_at_thresholds():
    direct_blocked = evaluate_entry_chain(candidate(quote_volume_24h=250_000.0, expected_order_size=10_000.0))
    probe_blocked = evaluate_entry_chain(candidate(quote_volume_24h=30_000.0, expected_order_size=10_000.0))

    assert direct_blocked.action == "PROBE"
    assert "LIQUIDITY_DIRECT_BLOCK" in direct_blocked.reasons
    assert probe_blocked.action == "NO_TRADE"
    assert "LIQUIDITY_PROBE_BLOCK" in probe_blocked.reasons


def test_wick_anomaly_blocks_current_and_following_two_bars():
    current = evaluate_entry_chain(candidate(wick_anomaly_active=True))
    followup = evaluate_entry_chain(candidate(timestamp=1_766_000_900, polluted_until_ts=1_766_001_800))

    assert current.action == "NO_TRADE"
    assert followup.action == "NO_TRADE"
    assert "DATA_WICK_ANOMALY" in current.reasons
    assert "DATA_POLLUTION_COOLDOWN" in followup.reasons


def test_trade_budget_and_symbol_cooldown_block_entries():
    daily_budget = evaluate_entry_chain(candidate(portfolio_trades_today=4))
    symbol_cooldown = evaluate_entry_chain(candidate(cooldown_until_ts=1_766_001_000))

    assert daily_budget.action == "NO_TRADE"
    assert "DAILY_TRADE_BUDGET_USED" in daily_budget.reasons
    assert symbol_cooldown.action == "NO_TRADE"
    assert "SYMBOL_COOLDOWN_ACTIVE" in symbol_cooldown.reasons


def test_min_daily_trades_keeps_low_volatility_budget_open():
    cfg = EntryChainConfig(daily_max_trades_base=16, min_daily_trades=2)
    allowed = evaluate_entry_chain(
        candidate(
            portfolio_trades_today=1,
            current_volatility_scale=0.05,
            normal_volatility_scale=1.0,
        ),
        cfg,
    )
    blocked = evaluate_entry_chain(
        candidate(
            portfolio_trades_today=2,
            current_volatility_scale=0.05,
            normal_volatility_scale=1.0,
        ),
        cfg,
    )

    assert allowed.action != "NO_TRADE"
    assert blocked.action == "NO_TRADE"
    assert "DAILY_TRADE_BUDGET_USED" in blocked.reasons


def test_daily_budget_block_includes_budget_detail_metadata():
    cfg = EntryChainConfig(daily_max_trades_base=16, min_daily_trades=2)

    decision = evaluate_entry_chain(
        candidate(
            portfolio_trades_today=2,
            current_volatility_scale=0.05,
            normal_volatility_scale=1.0,
            daily_profit_pct=0.0,
        ),
        cfg,
    )

    assert decision.action == "NO_TRADE"
    assert "DAILY_TRADE_BUDGET_USED" in decision.reasons
    assert decision.metadata["daily_max_trades"] == 2
    assert decision.metadata["daily_budget_detail"] == {
        "dynamic_limit": 2,
        "used_today": 2,
        "current_volatility_scale": 0.05,
        "normal_volatility_scale": 1.0,
        "min_daily_trades": 2,
        "daily_profit_pct": 0.0,
    }


def test_symbol_caps_and_margin_buffer_reject_oversized_context():
    active_limit = evaluate_entry_chain(candidate(active_symbols=5))
    margin_buffer = evaluate_entry_chain(candidate(available_margin=1_000.0))

    assert active_limit.action == "NO_TRADE"
    assert "MAX_ACTIVE_SYMBOLS" in active_limit.reasons
    assert margin_buffer.action == "NO_TRADE"
    assert "MARGIN_BUFFER_TOO_LOW" in margin_buffer.reasons


def test_rolling_sharpe_caps_leverage_to_two():
    decision = evaluate_entry_chain(candidate(rolling_sharpe_20=-0.2))

    assert decision.leverage == 2
    assert "ROLLING_SHARPE_LEVERAGE_CAP" in decision.reasons


def test_ema_component_minimums_downgrade_direct_and_probe():
    direct = evaluate_entry_chain(
        candidate(component_scores={**candidate().component_scores, "ema_50_quality": 0.50, "ema_momentum": 1.0}),
        EntryChainConfig(use_ema_architecture=True, direct_threshold=80, probe_threshold=70),
    )
    assert direct.action == "PROBE"
    assert "EMA50_DIRECT_MINIMUM_FAILED" in direct.reasons

    probe = evaluate_entry_chain(
        candidate(component_scores={**candidate().component_scores, "ema_50_quality": 0.20, "ema_momentum": 1.0}),
        EntryChainConfig(use_ema_architecture=True, direct_threshold=90, probe_threshold=70),
    )
    assert probe.action == "WATCH"
    assert "EMA50_PROBE_MINIMUM_FAILED" in probe.reasons


def test_ema200_hard_gate_blocks_trade():
    decision = evaluate_entry_chain(
        candidate(component_scores={**candidate().component_scores, "ema_200_gate": 0.0, "ema_50_quality": 1.0, "ema_momentum": 1.0}),
        EntryChainConfig(use_ema_architecture=True, ema200_gate_mode="hard"),
    )

    assert decision.action == "NO_TRADE"
    assert "EMA200_HARD_GATE_FAILED" in decision.reasons


def test_configured_blacklist_blocks_symbol():
    decision = evaluate_entry_chain(candidate(symbol="XRPUSDT"), EntryChainConfig(blacklist_symbols=("XRPUSDT",)))

    assert decision.action == "NO_TRADE"
    assert "SYMBOL_BLACKLISTED" in decision.reasons


def test_configured_watch_only_symbol_blocks_trade():
    decision = evaluate_entry_chain(candidate(symbol="ADAUSDT"), EntryChainConfig(watch_only_symbols=("ADAUSDT",)))

    assert decision.action == "NO_TRADE"
    assert "SYMBOL_WATCH_ONLY" in decision.reasons


def test_disable_probe_downgrades_probe_to_watch():
    decision = evaluate_entry_chain(
        candidate(component_scores={**candidate().component_scores, "trigger_15m": 0.75}),
        EntryChainConfig(direct_threshold=90, probe_threshold=70, disable_probe=True),
    )

    assert decision.action == "NO_TRADE"
    assert decision.risk_allowed is False
    assert "PROBE_DISABLED" in decision.reasons


def test_long_threshold_offset_makes_long_stricter_than_short():
    scores = {
        "background_4h": 0.80,
        "direction_1h": 0.82,
        "quality_30m": 0.82,
        "trigger_15m": 0.92,
        "cvd_flow": 0.82,
        "volatility_stop": 0.82,
        "liquidity_execution": 0.82,
        "market_regime": 0.82,
    }
    cfg = EntryChainConfig(direct_threshold=82, probe_threshold=70, long_threshold_offset=10)

    long_decision = evaluate_entry_chain(candidate(side="LONG", component_scores=scores), cfg)
    short_decision = evaluate_entry_chain(candidate(side="SHORT", component_scores=scores), cfg)

    assert long_decision.action == "PROBE"
    assert "SIDE_THRESHOLD_OFFSET_LONG_10.00" in long_decision.reasons
    assert short_decision.action == "DIRECT"


def test_side_specific_direct_component_minimums_only_affect_matching_side():
    scores = {
        "background_4h": 1.0,
        "direction_1h": 1.0,
        "quality_30m": 1.0,
        "trigger_15m": 0.96,
        "cvd_flow": 0.68,
        "volatility_stop": 1.0,
        "liquidity_execution": 1.0,
        "market_regime": 1.0,
    }
    cfg = EntryChainConfig(direct_threshold=82, long_min_cvd_direct_score=0.70)

    long_decision = evaluate_entry_chain(candidate(side="LONG", component_scores=scores), cfg)
    short_decision = evaluate_entry_chain(candidate(side="SHORT", component_scores=scores), cfg)

    assert long_decision.action == "PROBE"
    assert "SIDE_COMPONENT_MINIMUMS_LONG" in long_decision.reasons
    assert short_decision.action == "DIRECT"


def test_long_context_discounts_reduce_scores_before_action_selection():
    base_scores = {
        "background_4h": 1.0,
        "direction_1h": 1.0,
        "quality_30m": 1.0,
        "trigger_15m": 1.0,
        "cvd_flow": 0.7,
        "volatility_stop": 1.0,
        "liquidity_execution": 1.0,
        "market_regime": 1.0,
        "ema_50_quality": 1.0,
        "ema_momentum": 1.0,
    }
    cfg = EntryChainConfig(
        use_ema_architecture=True,
        ema200_gate_mode="soft",
        direct_threshold=82,
        probe_threshold=70,
        enable_long_context_discounts=True,
    )

    decision = evaluate_entry_chain(
        candidate(
            side="LONG",
            component_scores=base_scores,
            long_overextension_active=True,
            long_upper_wick_risk_active=True,
            long_chase_risk_active=True,
            long_cvd_weak_active=True,
        ),
        cfg,
    )

    assert decision.component_points["quality_30m"] == 8.4
    assert decision.component_points["trigger_15m"] == 3.15
    assert decision.component_points["cvd_flow"] == 10.08
    assert "LONG_OVEREXTENSION_QUALITY_DISCOUNT" in decision.reasons
    assert "LONG_UPPER_WICK_TRIGGER_DISCOUNT" in decision.reasons
    assert "LONG_CHASE_TRIGGER_DISCOUNT" in decision.reasons
    assert "LONG_CVD_WEAK_DISCOUNT" in decision.reasons


def test_long_context_discounts_do_not_affect_shorts():
    cfg = EntryChainConfig(enable_long_context_discounts=True)
    short = evaluate_entry_chain(
        candidate(
            side="SHORT",
            long_overextension_active=True,
            long_upper_wick_risk_active=True,
            long_chase_risk_active=True,
            long_cvd_weak_active=True,
        ),
        cfg,
    )

    assert short.action == "DIRECT"
    assert not any(reason.startswith("LONG_") for reason in short.reasons)


def test_long_low_liquidity_session_caps_direct_to_watch():
    cfg = EntryChainConfig(enable_long_context_discounts=True, disable_probe=True)

    decision = evaluate_entry_chain(
        candidate(side="LONG", long_low_liquidity_session_active=True),
        cfg,
    )

    assert decision.action == "WATCH"
    assert decision.risk_allowed is False
    assert "LONG_LOW_LIQUIDITY_SESSION_WATCH" in decision.reasons


def fib_pa_scores(**overrides):
    scores = {
        "trend_ema_context": 1.0,
        "flow_cvd_confirmation": 1.0,
        "cci_momentum_quality": 1.0,
        "price_action_structure": 1.0,
        "fibonacci_location": 1.0,
        "risk_reward_geometry": 1.0,
        "fib_action_cap": 1.0,
    }
    scores.update(overrides)
    return scores


def test_fib_pa_direct_demotes_when_pa_below_minimum():
    cfg = EntryChainConfig(use_fib_pa_architecture=True, direct_threshold=82.0, disable_probe=True)
    decision = evaluate_entry_chain(
        candidate(side="SHORT", component_scores=fib_pa_scores(price_action_structure=5.0 / 22.0)),
        cfg,
    )

    assert decision.action == "NO_TRADE"
    assert "DIRECT_BELOW_PRICE_ACTION_STRUCTURE_MINIMUM_GAP_1.0" in decision.reasons
    assert "PROBE_DISABLED" in decision.reasons


def test_fib_pa_extension_block_rejects_even_high_score():
    cfg = EntryChainConfig(use_fib_pa_architecture=True, direct_threshold=82.0)
    decision = evaluate_entry_chain(
        candidate(side="SHORT", component_scores=fib_pa_scores(fib_action_cap=0.0)),
        cfg,
    )

    assert decision.action == "NO_TRADE"
    assert decision.score == 100.0
    assert "FIB_EXTENSION_EXHAUSTION_BLOCK" in decision.reasons


def test_fib_pa_5x_requires_fib_pa_cci_rr_minimums():
    cfg = EntryChainConfig(use_fib_pa_architecture=True, direct_threshold=82.0)
    decision = evaluate_entry_chain(
        candidate(
            side="SHORT",
            atr_pct=0.01,
            component_scores=fib_pa_scores(
                cci_momentum_quality=6.0 / 14.0,
            ),
        ),
        cfg,
    )

    assert decision.action == "DIRECT"
    assert decision.score >= 90.0
    assert decision.leverage == 4
    assert "FIB_PA_5X_REQUIREMENTS_FAILED" in decision.reasons


def test_fib_pa_conditional_probe_requires_fib_pa_quality():
    cfg = EntryChainConfig(
        use_fib_pa_architecture=True,
        direct_threshold=95.0,
        probe_threshold=70.0,
        probe_conditions={
            "enabled": True,
            "min_score": 72.0,
            "min_fib_score": 12.0,
            "min_pa_score": 6.0,
            "min_rr_score": 2.0,
        },
    )

    allowed = evaluate_entry_chain(
        candidate(
            side="SHORT",
            component_scores=fib_pa_scores(
                trend_ema_context=0.85,
                flow_cvd_confirmation=1.0,
                cci_momentum_quality=10.0 / 14.0,
                price_action_structure=15.0 / 22.0,
                fibonacci_location=18.0 / 18.0,
                risk_reward_geometry=3.5 / 8.0,
            ),
        ),
        cfg,
    )
    blocked = evaluate_entry_chain(
        candidate(
            side="SHORT",
            component_scores=fib_pa_scores(
                trend_ema_context=0.85,
                flow_cvd_confirmation=1.0,
                cci_momentum_quality=10.0 / 14.0,
                price_action_structure=21.0 / 22.0,
                fibonacci_location=9.0 / 18.0,
                risk_reward_geometry=3.0 / 8.0,
            ),
        ),
        cfg,
    )

    assert allowed.action == "PROBE"
    assert blocked.action == "WATCH"
    assert "PROBE_BELOW_FIBONACCI_LOCATION_MINIMUM_GAP_3.0" in blocked.reasons


def test_fib_pa_high_beta_probe_requires_extra_rr():
    cfg = EntryChainConfig(
        use_fib_pa_architecture=True,
        direct_threshold=82.0,
        probe_threshold=70.0,
        probe_conditions={
            "enabled": True,
            "min_score": 72.0,
            "min_fib_score": 12.0,
            "min_pa_score": 10.0,
            "min_rr_score": 2.0,
            "high_beta_min_pa_score": 12.0,
            "high_beta_min_rr_score": 3.0,
        },
    )

    decision = evaluate_entry_chain(
        candidate(
            symbol="HYPEUSDT",
            side="SHORT",
            component_scores=fib_pa_scores(
                trend_ema_context=18.0 / 20.0,
                flow_cvd_confirmation=1.0,
                cci_momentum_quality=10.0 / 14.0,
                price_action_structure=12.0 / 22.0,
                fibonacci_location=18.0 / 18.0,
                risk_reward_geometry=2.5 / 8.0,
            ),
        ),
        cfg,
    )

    assert decision.action == "WATCH"
    assert "HIGH_BETA_PROBE_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_0.5" in decision.reasons


def test_fib_pa_high_beta_probe_requires_extra_cci_and_ema():
    cfg = EntryChainConfig(
        use_fib_pa_architecture=True,
        direct_threshold=95.0,
        probe_threshold=70.0,
        probe_conditions={
            "enabled": True,
            "min_score": 72.0,
            "min_fib_score": 12.0,
            "min_pa_score": 10.0,
            "min_rr_score": 4.0,
            "high_beta_min_pa_score": 12.0,
            "high_beta_min_rr_score": 5.0,
            "high_beta_min_cci_score": 9.0,
            "high_beta_min_ema_score": 12.0,
        },
    )

    weak_cci = evaluate_entry_chain(
        candidate(
            symbol="LABUSDT",
            side="LONG",
            component_scores=fib_pa_scores(
                trend_ema_context=14.0 / 20.0,
                flow_cvd_confirmation=1.0,
                cci_momentum_quality=8.5 / 14.0,
                price_action_structure=16.0 / 22.0,
                fibonacci_location=18.0 / 18.0,
                risk_reward_geometry=6.0 / 8.0,
            ),
        ),
        cfg,
    )
    weak_ema = evaluate_entry_chain(
        candidate(
            symbol="HYPEUSDT",
            side="SHORT",
            component_scores=fib_pa_scores(
                trend_ema_context=11.0 / 20.0,
                flow_cvd_confirmation=1.0,
                cci_momentum_quality=10.0 / 14.0,
                price_action_structure=16.0 / 22.0,
                fibonacci_location=18.0 / 18.0,
                risk_reward_geometry=6.0 / 8.0,
            ),
        ),
        cfg,
    )

    assert weak_cci.action == "WATCH"
    assert "HIGH_BETA_PROBE_BELOW_CCI_MOMENTUM_QUALITY_MINIMUM_GAP_0.5" in weak_cci.reasons
    assert weak_ema.action == "WATCH"
    assert "HIGH_BETA_PROBE_BELOW_TREND_EMA_CONTEXT_MINIMUM_GAP_1.0" in weak_ema.reasons


def test_fib_pa_high_beta_direct_downgrade_rechecks_probe_conditions():
    cfg = EntryChainConfig(
        use_fib_pa_architecture=True,
        direct_threshold=82.0,
        probe_threshold=70.0,
        fib_min_direct_score=6.0,
        pa_min_direct_score=6.0,
        rr_min_direct_score=4.0,
        probe_conditions={
            "enabled": True,
            "min_score": 72.0,
            "min_fib_score": 12.0,
            "min_pa_score": 10.0,
            "min_rr_score": 4.0,
            "high_beta_min_pa_score": 12.0,
            "high_beta_min_rr_score": 5.0,
            "high_beta_min_cci_score": 9.0,
            "high_beta_min_ema_score": 12.0,
        },
    )

    decision = evaluate_entry_chain(
        candidate(
            symbol="HYPEUSDT",
            side="SHORT",
            component_scores=fib_pa_scores(
                trend_ema_context=16.19 / 20.0,
                flow_cvd_confirmation=1.0,
                cci_momentum_quality=1.0,
                price_action_structure=21.0 / 22.0,
                fibonacci_location=9.0 / 18.0,
                risk_reward_geometry=5.0 / 8.0,
            ),
        ),
        cfg,
    )

    assert decision.action == "WATCH"
    assert "HIGH_BETA_PROBE_ONLY" in decision.reasons
    assert "HIGH_BETA_DIRECT_TO_PROBE_FAILED_CONDITIONS" in decision.reasons
    assert "PROBE_BELOW_FIBONACCI_LOCATION_MINIMUM_GAP_3.0" in decision.reasons


def test_fib_pa_overextended_or_chasing_long_caps_to_watch_even_when_high_score():
    cfg = EntryChainConfig(
        use_fib_pa_architecture=True,
        direct_threshold=95.0,
        probe_threshold=70.0,
        long_overextension_watch_enabled=True,
        long_chase_watch_enabled=True,
        probe_conditions={
            "enabled": True,
            "min_score": 72.0,
            "min_fib_score": 12.0,
            "min_pa_score": 10.0,
            "min_rr_score": 4.0,
        },
    )

    overextended = evaluate_entry_chain(
        candidate(
            side="LONG",
            long_overextension_active=True,
            component_scores=fib_pa_scores(),
        ),
        cfg,
    )
    chasing = evaluate_entry_chain(
        candidate(
            side="LONG",
            long_chase_risk_active=True,
            component_scores=fib_pa_scores(),
        ),
        cfg,
    )

    assert overextended.action == "WATCH"
    assert chasing.action == "WATCH"
    assert "LONG_OVEREXTENSION_OR_CHASE_RISK_WATCH" in overextended.reasons
    assert "LONG_OVEREXTENSION_OR_CHASE_RISK_WATCH" in chasing.reasons


def test_fib_pa_long_chase_with_weak_pa_caps_to_watch():
    cfg = EntryChainConfig(
        use_fib_pa_architecture=True,
        direct_threshold=95.0,
        probe_threshold=70.0,
        probe_conditions={
            "enabled": True,
            "min_score": 72.0,
            "min_fib_score": 12.0,
            "min_pa_score": 6.0,
            "min_rr_score": 2.0,
            "long_chase_min_pa_score": 12.0,
        },
    )

    decision = evaluate_entry_chain(
        candidate(
            side="LONG",
            long_chase_risk_active=True,
            component_scores=fib_pa_scores(
                trend_ema_context=17.25 / 20.0,
                flow_cvd_confirmation=1.0,
                cci_momentum_quality=10.0 / 14.0,
                price_action_structure=8.0 / 22.0,
                fibonacci_location=1.0,
                risk_reward_geometry=6.5 / 8.0,
            ),
        ),
        cfg,
    )

    assert decision.action == "WATCH"
    assert "LONG_CHASE_WEAK_PA_WATCH" in decision.reasons
