from src.signals.entry_chain_config import EntryChainConfig
from src.signals.entry_chain_scoring import component_points, dynamic_weights


def test_dynamic_weight_boundaries_do_not_switch_at_exact_thresholds():
    config = EntryChainConfig()

    high_edge, high_reasons = dynamic_weights(config.high_vol_atr_pct, config)
    low_edge, low_reasons = dynamic_weights(config.low_vol_atr_pct, config)

    assert high_edge["volatility_stop"] == 10.0
    assert low_edge["trigger_15m"] == 12.0
    assert high_reasons == []
    assert low_reasons == []


def test_component_points_clamps_inputs_and_weights_sum_to_100():
    weights, _ = dynamic_weights(0.04, EntryChainConfig())
    points = component_points({"direction_1h": 2.0, "quality_30m": -1.0}, weights)

    assert round(sum(weights.values()), 6) == 100.0
    assert points["direction_1h"] == round(weights["direction_1h"], 4)
    assert points["quality_30m"] == 0.0


def test_ema_weight_profile_replaces_trigger_timing_component():
    config = EntryChainConfig(use_ema_architecture=True)

    weights, reasons = dynamic_weights(0.02, config)

    assert "EMA_ARCHITECTURE_WEIGHTS" in reasons
    assert weights["ema_50_quality"] == 15.0
    assert weights["ema_momentum"] == 10.0
    assert "rsi_timing" not in weights
    assert round(sum(weights.values()), 6) == 100.0
