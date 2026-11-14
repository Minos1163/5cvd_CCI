"""`scoring_architecture` 枚举守卫（P0 A1，2026-11-14 评审 §3.3）。

背景：历史上"用哪组权重"由两个布尔开关 + `dynamic_weights` 的短路顺序**隐式**决定。
生产配置 `entry_chain.dry_run_regime_shadow.json` 曾同时打开
`use_fib_pa_architecture` 与 `use_ema_architecture`，于是每条决策都产生一条
`ARCHITECTURE_FLAGS_BOTH_TRUE` 告警，但实际走的是 fib_pa 权重表。配置里写着两个 true，
却无法从配置直接回答"按哪组权重打分"——本枚举就是为了消灭这个隐式性。

本文件锁三件事：
1. `"auto"`（默认）下 4 种布尔组合 × 3 个 atr 区间的返回值，与引入枚举前**逐项相同**；
   期望值写死在表里，不跟着实现漂移。
2. `dynamic_weights` 的 reasons 一字不多——显式枚举值是"日志新增"，权重来源说明必须
   与 auto 路径逐字相同，否则会改写 `decision.reasons` / `payload.reasons` /
   `leverage_reason`。
3. 显式值优先于布尔开关；非法值报错；生产配置的权重表等于 `FIB_PA_WEIGHTS`。
"""

from __future__ import annotations

import pytest

from src.signals.entry_chain_config import EntryChainConfig, load_entry_chain_config
from src.signals.entry_chain_scoring import (
    BASE_WEIGHTS,
    EMA_WEIGHTS,
    FIB_PA_WEIGHTS,
    dynamic_weights,
    resolve_architecture,
)

PRODUCTION_CONFIG = "configs/entry_chain.dry_run_regime_shadow.json"

# atr_pct 三个代表点：低波动分支 / base 分支 / 高波动分支。
# 端点取默认阈值（low_vol_atr_pct=0.010, high_vol_atr_pct=0.035）之外。
ATR_REGIMES = (
    ("low_vol", 0.001),
    ("base", 0.020),
    ("high_vol", 0.050),
)

# (use_fib_pa, use_ema) → 三个 atr 区间的架构名（auto 模式）。
# 期望值 = 引入 scoring_architecture 之前（HEAD f260b1a）的实测行为。
AUTO_ARCHITECTURE = {
    (True, True): ("fib_pa", "fib_pa", "fib_pa"),
    (True, False): ("fib_pa", "fib_pa", "fib_pa"),
    (False, True): ("ema", "ema", "ema"),
    (False, False): ("low_vol_dynamic", "base", "high_vol_dynamic"),
}

# auto 模式下 `dynamic_weights` 必须返回的 reasons（权重来源说明）。
# 注意 (True, True) 不带 ARCHITECTURE_FLAGS_BOTH_TRUE —— 它被 _NON_WEIGHT_REASONS 过滤。
AUTO_WEIGHT_REASONS = {
    (True, True): ["FIB_PA_ARCHITECTURE_WEIGHTS"],
    (True, False): ["FIB_PA_ARCHITECTURE_WEIGHTS"],
    (False, True): ["EMA_ARCHITECTURE_WEIGHTS"],
    (False, False): [["LOW_VOL_DYNAMIC_WEIGHTS"], [], ["HIGH_VOL_DYNAMIC_WEIGHTS"]],
}


def _cfg(use_fib_pa: bool, use_ema: bool, **overrides) -> EntryChainConfig:
    return EntryChainConfig(
        use_fib_pa_architecture=use_fib_pa,
        use_ema_architecture=use_ema,
        **overrides,
    )


@pytest.mark.parametrize("use_fib_pa", [True, False])
@pytest.mark.parametrize("use_ema", [True, False])
def test_auto_mode_matches_pre_enum_architecture_choice(use_fib_pa: bool, use_ema: bool) -> None:
    """`scoring_architecture="auto"` 必须与引入枚举前的架构选择逐项相同。

    4 种布尔组合 × 3 个 atr 区间 = 12 个断言点（布尔组合本身只有 4 种）。
    """
    cfg = _cfg(use_fib_pa, use_ema)
    assert cfg.scoring_architecture == "auto", "默认值必须是 auto，否则历史配置行为会变"
    expected = AUTO_ARCHITECTURE[(use_fib_pa, use_ema)]
    for (regime, atr_pct), expected_name in zip(ATR_REGIMES, expected):
        name, _reasons = resolve_architecture(cfg, atr_pct=atr_pct)
        assert name == expected_name, f"{regime} 区间架构漂移"


@pytest.mark.parametrize("use_fib_pa", [True, False])
@pytest.mark.parametrize("use_ema", [True, False])
def test_auto_mode_weight_reasons_are_unchanged(use_fib_pa: bool, use_ema: bool) -> None:
    """auto 模式下 `dynamic_weights` 的 reasons 一字不多（锁 decision.reasons）。"""
    cfg = _cfg(use_fib_pa, use_ema)
    expected_reasons = AUTO_WEIGHT_REASONS[(use_fib_pa, use_ema)]
    for index, (regime, atr_pct) in enumerate(ATR_REGIMES):
        _weights, reasons = dynamic_weights(atr_pct, cfg)
        expected = expected_reasons if isinstance(expected_reasons[0], str) else expected_reasons[index]
        assert reasons == expected, f"{regime} 区间 reasons 漂移"


def test_auto_mode_weight_tables_match_legacy_tables() -> None:
    """auto 路径拿到的权重表必须就是那三张表本身（逐键相等）。"""
    weights, _ = dynamic_weights(0.02, _cfg(True, True))
    assert weights == dict(FIB_PA_WEIGHTS)
    weights, _ = dynamic_weights(0.02, _cfg(True, False))
    assert weights == dict(FIB_PA_WEIGHTS)
    weights, _ = dynamic_weights(0.02, _cfg(False, True))
    assert weights == dict(EMA_WEIGHTS)
    weights, _ = dynamic_weights(0.02, _cfg(False, False))
    assert weights == dict(BASE_WEIGHTS)


def test_explicit_fib_pa_overrides_disabled_flags() -> None:
    """显式 `fib_pa` 时，即使 `use_fib_pa_architecture=False` 也返回 fib_pa。"""
    cfg = _cfg(False, False, scoring_architecture="fib_pa")
    name, reasons = resolve_architecture(cfg)
    assert name == "fib_pa"
    assert "SCORING_ARCHITECTURE_EXPLICIT_FIB_PA" in reasons
    weights, weight_reasons = dynamic_weights(0.02, cfg)
    assert weights == dict(FIB_PA_WEIGHTS)
    # 权重来源说明保持与 auto 路径逐字相同：枚举信息只进 resolve 的诊断 reasons。
    assert weight_reasons == ["FIB_PA_ARCHITECTURE_WEIGHTS"]


def test_explicit_ema_overrides_enabled_fib_pa_flag() -> None:
    """显式 `ema` 时以枚举为准，忽略为 true 的 fib_pa 布尔开关。"""
    cfg = _cfg(True, True, scoring_architecture="ema")
    name, reasons = resolve_architecture(cfg)
    assert name == "ema"
    assert "SCORING_ARCHITECTURE_EXPLICIT_EMA" in reasons
    # 两个布尔开关同 true 的冲突告警仍然保留（与架构选择解耦）。
    assert "ARCHITECTURE_FLAGS_BOTH_TRUE" in reasons
    weights, weight_reasons = dynamic_weights(0.02, cfg)
    assert weights == dict(EMA_WEIGHTS)
    assert weight_reasons == ["EMA_ARCHITECTURE_WEIGHTS"]


def test_explicit_base_skips_volatility_branches() -> None:
    """显式 `base` 直接返回 BASE_WEIGHTS，**不经过** atr_pct 的高/低波动分支。"""
    cfg = _cfg(False, False, scoring_architecture="base")
    for atr_pct in (0.001, 0.020, 0.050):
        name, reasons = resolve_architecture(cfg, atr_pct=atr_pct)
        assert name == "base"
        assert "SCORING_ARCHITECTURE_EXPLICIT_BASE" in reasons
        weights, weight_reasons = dynamic_weights(atr_pct, cfg)
        assert weights == dict(BASE_WEIGHTS)
        assert weight_reasons == [], "base 的权重来源从不出现在 reasons 里（历史语义）"


def test_invalid_scoring_architecture_raises() -> None:
    """非法取值必须显式报错，而不是悄悄退回 auto。"""
    cfg = EntryChainConfig(scoring_architecture="xxx")
    with pytest.raises(ValueError):
        resolve_architecture(cfg)
    with pytest.raises(ValueError):
        EntryChainConfig.from_mapping({"scoring_architecture": "xxx"})


def test_scoring_architecture_is_normalised_case_insensitively() -> None:
    cfg = EntryChainConfig.from_mapping({"scoring_architecture": "  FIB_PA "})
    assert cfg.scoring_architecture == "fib_pa"
    assert resolve_architecture(cfg)[0] == "fib_pa"


def test_empty_scoring_architecture_behaves_like_auto() -> None:
    """空串按 auto 处理（历史配置没写这个键时最省事的兼容方式）。"""
    cfg = EntryChainConfig(use_fib_pa_architecture=True, scoring_architecture="")
    assert resolve_architecture(cfg)[0] == "fib_pa"


def test_production_config_weights_equal_fib_pa_table() -> None:
    """生产配置等价性：去掉冲突布尔、改显式 fib_pa 后，权重表逐键不变。

    改前：`use_fib_pa=True, use_ema=True` → 短路顺序选中 fib_pa → `FIB_PA_WEIGHTS`
    改后：`use_fib_pa=True, use_ema=False, scoring_architecture="fib_pa"` → 显式 fib_pa
    两者的权重表与 `dynamic_weights` reasons 都必须逐字相同。
    """
    cfg = load_entry_chain_config(PRODUCTION_CONFIG)

    assert cfg.scoring_architecture == "fib_pa"
    assert cfg.use_ema_architecture is False
    assert cfg.use_fib_pa_architecture is True

    for atr_pct in (0.001, 0.020, 0.050):
        weights, reasons = dynamic_weights(atr_pct, cfg)
        assert weights == dict(FIB_PA_WEIGHTS), "生产配置的权重表必须仍是 FIB_PA_WEIGHTS"
        assert reasons == ["FIB_PA_ARCHITECTURE_WEIGHTS"], "reasons 必须与改动前逐字相同"


def test_production_config_no_longer_reports_flag_conflict_only() -> None:
    """生产配置的架构冲突告警应消失（这正是本次配置去冲突的目的）。"""
    cfg = load_entry_chain_config(PRODUCTION_CONFIG)
    _name, reasons = resolve_architecture(cfg)
    assert "ARCHITECTURE_FLAGS_BOTH_TRUE" not in reasons
    assert "SCORING_ARCHITECTURE_EXPLICIT_FIB_PA" in reasons


# fib_pa 架构下"满分"级别的一组分量（归一化 0-1），用于让 DIRECT 真的可达，
# 避免下面这条测试退化成"两个 NO_TRADE 相等"。
_STRONG_FIB_PA_SCORES = {
    "trend_ema_context": 1.0,
    "flow_cvd_confirmation": 1.0,
    "cci_momentum_quality": 1.0,
    "price_action_structure": 1.0,
    "fibonacci_location": 1.0,
    "risk_reward_geometry": 0.75,
    "fib_action_cap": 1.0,
    # 老路径（use_ema_architecture=True）还会额外产出这三个键，值故意给 0.0
    "ema_200_gate": 0.0,
    "ema_50_quality": 0.0,
    "ema_momentum": 0.0,
}


def _context(scores: dict[str, float]):
    from src.signals.entry_chain import EntryChainContext

    return EntryChainContext(
        symbol="BTCUSDT",
        timestamp=1_700_000_000,
        side="LONG",
        component_scores=scores,
        quote_volume_24h=5e9,
        atr_pct=0.01,
        expected_order_size=1_000.0,
        account_equity=10_000.0,
        available_margin=8_000.0,
        stop_pct=0.015,
    )


def test_disabling_ema_flag_does_not_change_decision_under_fib_pa() -> None:
    """A1.3 的等价性核心：`use_ema_architecture: true → false` 不得动四个值。

    这是本次唯一的"生产配置改动"。风险点在于 `use_ema_architecture=True` 时
    `component_scores()` 会多产出 `ema_200_gate` / `ema_50_quality` / `ema_momentum`
    三个键，而 `entry_chain.py` 里确有读它们的闸门
    （`EMA200_HARD_GATE_FAILED` / `EMA50_DIRECT_MINIMUM_FAILED` / `EMA50_PROBE_MINIMUM_FAILED`）。
    这些闸门都写在 `if cfg.use_fib_pa_architecture: return ...` 之后，因此在 fib_pa 架构下
    不可达——本条测试就是把这个"不可达"钉住：即使 ema 键存在且值为 0.0（最坏情况），
    决策也不变。若将来有人把 ema 闸门挪到 fib_pa 短路之前，这条会红。
    """
    from src.signals.entry_chain import evaluate_entry_chain

    legacy_cfg = EntryChainConfig(use_fib_pa_architecture=True, use_ema_architecture=True)
    new_cfg = EntryChainConfig(
        use_fib_pa_architecture=True,
        use_ema_architecture=False,
        scoring_architecture="fib_pa",
    )

    new_scores = {key: value for key, value in _STRONG_FIB_PA_SCORES.items() if not key.startswith("ema_")}
    legacy_decision = evaluate_entry_chain(_context(dict(_STRONG_FIB_PA_SCORES)), legacy_cfg)
    new_decision = evaluate_entry_chain(_context(new_scores), new_cfg)

    assert legacy_decision.action == "DIRECT", "样本必须真能开仓，否则这条测试没有意义"
    assert new_decision.action == legacy_decision.action
    assert new_decision.score == legacy_decision.score
    assert new_decision.leverage == legacy_decision.leverage
    assert new_decision.notional_hint == legacy_decision.notional_hint
    assert new_decision.reasons == legacy_decision.reasons
    assert new_decision.weights == legacy_decision.weights
