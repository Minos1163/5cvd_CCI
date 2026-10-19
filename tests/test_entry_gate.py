import pytest

from src.signals.entry_gate import EntryGate, GateRule, build_gate_features


def test_empty_gate_passes_everything():
    gate = EntryGate.from_config(None)
    assert not gate
    verdict = gate.evaluate({})
    assert verdict.passed is True
    assert verdict.trace == ()


def test_gate_requires_all_rules():
    gate = EntryGate.from_config(
        [
            {"feature": "trend_ema_context", "op": ">=", "value": 0.7},
            {"feature": "atr_pct", "op": "<=", "value": 0.01},
        ]
    )
    assert gate.evaluate({"trend_ema_context": 0.8, "atr_pct": 0.005}).passed
    rejected = gate.evaluate({"trend_ema_context": 0.6, "atr_pct": 0.005})
    assert rejected.passed is False
    assert rejected.rejected_by == ("trend_ema_context>=0.7",)


def test_missing_feature_is_not_a_pass():
    gate = EntryGate.from_config([{"feature": "shadow_pct", "op": ">", "value": 0.5}])
    verdict = gate.evaluate({"other": 1.0})
    assert verdict.passed is False
    assert verdict.missing == ("shadow_pct>0.5",)


def test_nan_feature_is_treated_as_missing():
    gate = EntryGate.from_config([{"feature": "x", "op": ">", "value": 0.5}])
    verdict = gate.evaluate({"x": float("nan")})
    assert verdict.passed is False
    assert verdict.missing == ("x>0.5",)


def test_from_config_rejects_bad_rules():
    with pytest.raises(ValueError):
        EntryGate.from_config([{"feature": "x", "op": "~", "value": 1}])
    with pytest.raises(ValueError):
        EntryGate.from_config([{"feature": "", "op": ">=", "value": 1}])
    with pytest.raises(ValueError):
        EntryGate.from_config([{"feature": "x", "op": ">="}])


def test_rule_describe_prefers_reason():
    rule = GateRule(feature="x", op=">=", value=1, reason="EDGE_V1")
    assert rule.describe() == "EDGE_V1"


def test_build_gate_features_maps_context_and_scores():
    class Context:
        atr_pct = 0.004
        extreme_position_ratio = 1.0
        symbol_exposure_pct = 0.0
        total_exposure_pct = 0.12
        current_volatility_scale = 0.4
        quote_volume_24h = 1_000_000.0

    features = build_gate_features(
        Context(),
        scores={"trend_ema_context": 0.71},
        kline={"open": 100, "high": 110, "low": 90, "close": 105},
        score_total=82.5,
        shadow_total=61.0,
        timestamp=1792281605,
    )
    assert features["atr_pct"] == 0.004
    assert features["score_pct"] == 0.825
    assert features["shadow_pct"] == 0.61
    assert features["trend_ema_context"] == 0.71
    assert features["log_qv"] == 6.0
    assert features["bar_pos"] == pytest.approx(0.75)
    assert features["hour"] == (1792281605 // 3600) % 24
