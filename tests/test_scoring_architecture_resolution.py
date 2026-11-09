from __future__ import annotations

from src.signals.entry_chain_config import EntryChainConfig, load_entry_chain_config
from src.signals.entry_chain_scoring import (
    FIB_PA_WEIGHTS,
    dynamic_weights,
    resolve_architecture,
)


def test_both_flags_resolve_to_fib_pa_with_warning():
    cfg = EntryChainConfig(use_fib_pa_architecture=True, use_ema_architecture=True)
    name, reasons = resolve_architecture(cfg)
    assert name == "fib_pa"
    assert "ARCHITECTURE_FLAGS_BOTH_TRUE" in reasons


def test_ema_only_resolves_to_ema():
    cfg = EntryChainConfig(use_fib_pa_architecture=False, use_ema_architecture=True)
    name, reasons = resolve_architecture(cfg)
    assert name == "ema"
    assert "EMA_ARCHITECTURE_WEIGHTS" in reasons


def test_neither_resolves_to_base_or_dynamic():
    cfg = EntryChainConfig(use_fib_pa_architecture=False, use_ema_architecture=False)
    name, _ = resolve_architecture(cfg, atr_pct=0.01)
    assert name in {"base", "high_vol_dynamic", "low_vol_dynamic"}


def test_regime_shadow_config_resolves_to_fib_pa():
    cfg = load_entry_chain_config("configs/entry_chain.dry_run_regime_shadow.json")
    name, _ = resolve_architecture(cfg)
    assert name == "fib_pa"


def test_active_weights_match_fib_pa_table():
    cfg = EntryChainConfig(use_fib_pa_architecture=True, use_ema_architecture=True)
    name, _ = resolve_architecture(cfg)
    assert name == "fib_pa"
    assert FIB_PA_WEIGHTS["price_action_structure"] == 22.0


def test_all_weight_tables_sum_to_100():
    """三张权重表都是 100 分制——这是 `total_score` 可跨架构比较的前提。

    任何一个表被改到不等于 100，阈值（92/77/72 等）的含义就随之漂移，
    所以这里锁死合计，而不是只在 fib_pa 上看一眼。
    """
    from src.signals.entry_chain_scoring import BASE_WEIGHTS, EMA_WEIGHTS

    for name, table in (("base", BASE_WEIGHTS), ("ema", EMA_WEIGHTS), ("fib_pa", FIB_PA_WEIGHTS)):
        assert sum(table.values()) == 100.0, f"{name} 权重合计 {sum(table.values())}"


def test_dynamic_weights_behavior_is_unchanged():
    """P0 铁律：改架构解析不得改动 `dynamic_weights` 的返回值。

    两开关同 true 时，`resolve_architecture` 会额外产出 `ARCHITECTURE_FLAGS_BOTH_TRUE`
    告警。若把它原样透传给 `dynamic_weights`，`decision.reasons` 就多一条字符串，
    进而改写 payload 的 `reasons` 与 Task 6 的 `leverage_reason`——那是行为变更。
    本测试锁死"reasons 一字不多"。
    """
    both = EntryChainConfig(use_fib_pa_architecture=True, use_ema_architecture=True)

    weights, reasons = dynamic_weights(0.01, both)
    assert weights == FIB_PA_WEIGHTS
    assert reasons == ["FIB_PA_ARCHITECTURE_WEIGHTS"]

    ema = EntryChainConfig(use_fib_pa_architecture=False, use_ema_architecture=True)
    _, ema_reasons = dynamic_weights(0.01, ema)
    assert ema_reasons == ["EMA_ARCHITECTURE_WEIGHTS"]

    base = EntryChainConfig(use_fib_pa_architecture=False, use_ema_architecture=False)
    _, base_reasons = dynamic_weights(0.01, base)
    assert base_reasons == []

    high_vol = EntryChainConfig(
        use_fib_pa_architecture=False,
        use_ema_architecture=False,
        high_vol_atr_pct=0.02,
        low_vol_atr_pct=0.005,
    )
    _, hv_reasons = dynamic_weights(0.05, high_vol)
    assert hv_reasons == ["HIGH_VOL_DYNAMIC_WEIGHTS"]
    _, lv_reasons = dynamic_weights(0.001, high_vol)
    assert lv_reasons == ["LOW_VOL_DYNAMIC_WEIGHTS"]
