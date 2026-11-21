"""`scoring_repair_v2`（P1-1/P1-2/P1-3）守卫。

三态语义（`off` / `shadow` / `on`）与两个被换掉的分量：

- **RR 两段式**（P1-2）：v1 的 `net_tp1_r = 1.2 − cost/stop_pct` 只是止损宽度的代理
  （Spearman(stop_pct, rr)=+0.859），且 `opposition_dist_r` 在近失样本里 49.5% 缺失。
  v2 拆成 base（ATR 可交易性，保底 1 分，**不归零**）+ bonus（结构空间，缺失只损失加分）。
- **CVD 连续化**（P1-3）：v1 是二值（1.0/0.2），47 笔成交样本全为 1.0、方差 0。
  v2 用成交量加权的方向符号比，`signed_ratio ∈ [-1,1]`。

本文件锁的核心不是"新分数更好"（那是数据的事），而是：
1. `off` 是默认且逐位等于旧行为（`dynamic_weights` 返回 V1 表、v2 分量一个都不算）；
2. `shadow` **不得**改动 action / score / leverage / notional；
3. `on` 只换 fib_pa 分支的权重表，其他架构不受影响；
4. v2 的两个分量在"结构数据缺失"时不会把分数清零（这是修复的真正目的）。
"""

from __future__ import annotations

import pytest

from src.signals.entry_chain import EntryChainContext, evaluate_entry_chain
from src.signals.entry_chain_config import EntryChainConfig
from src.signals.entry_chain_features import (
    component_scores,
    fib_pa_component_scores,
    risk_reward_geometry_detail_v2,
    volume_flow_score,
    volume_flow_score_v2,
)
from src.signals.entry_chain_scoring import (
    BASE_WEIGHTS,
    FIB_PA_WEIGHTS,
    FIB_PA_WEIGHTS_V2,
    dynamic_weights,
    repair_v2_enabled,
    repair_v2_score,
    resolve_architecture,
)
from src.backtest.engine import BacktestBar

FIB_PA_SCORES = {
    "trend_ema_context": 0.8,
    "flow_cvd_confirmation": 0.5,
    "cci_momentum_quality": 0.6,
    "price_action_structure": 0.7,
    "fibonacci_location": 0.9,
    "risk_reward_geometry": 0.75,
    "fib_action_cap": 1.0,
}


def _ctx(scores: dict[str, float], *, side: str = "LONG") -> EntryChainContext:
    return EntryChainContext(
        symbol="BTCUSDT",
        timestamp=1_700_000_000,
        side=side,
        component_scores=scores,
        quote_volume_24h=5e9,
        atr_pct=0.01,
        expected_order_size=1_000.0,
        account_equity=10_000.0,
        available_margin=8_000.0,
        stop_pct=0.015,
    )


def _bars(closes, volumes=None, opens=None) -> list[BacktestBar]:
    volumes = volumes or [100.0] * len(closes)
    opens = opens or closes
    return [
        BacktestBar("XUSDT", 1000 + i * 900, opens[i], max(opens[i], closes[i]), min(opens[i], closes[i]), closes[i], volumes[i])
        for i in range(len(closes))
    ]


# ---------------------------------------------------------------- 配置与三态


def test_default_mode_is_off_and_invalid_value_is_rejected() -> None:
    assert EntryChainConfig().scoring_repair_v2 == "off"
    assert repair_v2_enabled(EntryChainConfig()) is False
    assert repair_v2_enabled(EntryChainConfig(scoring_repair_v2="shadow")) is True
    with pytest.raises(ValueError):
        EntryChainConfig.from_mapping({"scoring_repair_v2": "on_maybe"})


def test_mode_is_normalised_and_empty_means_off() -> None:
    assert EntryChainConfig.from_mapping({"scoring_repair_v2": "  SHADOW "}).scoring_repair_v2 == "shadow"
    cfg = EntryChainConfig(scoring_repair_v2="")
    assert repair_v2_enabled(cfg) is False


def test_v2_weight_table_sums_to_100() -> None:
    """**合计必须正好 100**——`total_score` 与 V1 同尺度、入场阈值 82/77/72 才可比。

    初版任务书写 `RR→12` 使合计 98（+4/−4/−2 净 −2），已由 team-lead 裁定改为 RR→14，
    合计 14+14+20+(20+14+18)=100。这条断言就是防止再有人改表时算错总量。
    """
    assert sum(FIB_PA_WEIGHTS_V2.values()) == 100.0, "V2 权重合计不是 100，入场阈值不再可比"


def test_v2_weight_table_differs_exactly_in_three_keys() -> None:
    """三项改动逐键核对。"""
    changed = {k for k in FIB_PA_WEIGHTS if FIB_PA_WEIGHTS[k] != FIB_PA_WEIGHTS_V2.get(k)}
    assert changed == {"risk_reward_geometry", "flow_cvd_confirmation", "price_action_structure"}
    assert FIB_PA_WEIGHTS_V2["risk_reward_geometry"] == 14.0
    assert FIB_PA_WEIGHTS_V2["flow_cvd_confirmation"] == 14.0
    assert FIB_PA_WEIGHTS_V2["price_action_structure"] == 20.0
    assert set(FIB_PA_WEIGHTS_V2) == set(FIB_PA_WEIGHTS)


@pytest.mark.parametrize("mode", ["off", "shadow"])
def test_non_on_modes_keep_the_v1_weight_table(mode: str) -> None:
    """`shadow` 必须返回 V1 表——这是"影子模式不改 action"的第一道保证。"""
    cfg = EntryChainConfig(use_fib_pa_architecture=True, scoring_repair_v2=mode)
    weights, reasons = dynamic_weights(0.01, cfg)
    assert weights == dict(FIB_PA_WEIGHTS)
    assert "FIB_PA_WEIGHTS_V2" not in reasons


def test_on_mode_switches_to_the_v2_table() -> None:
    cfg = EntryChainConfig(use_fib_pa_architecture=True, scoring_repair_v2="on")
    weights, reasons = dynamic_weights(0.01, cfg)
    assert weights == dict(FIB_PA_WEIGHTS_V2)
    assert "FIB_PA_WEIGHTS_V2" in reasons


def test_on_mode_does_not_touch_non_fib_pa_architectures() -> None:
    """v2 表只属于 fib_pa；base / ema 架构不受 `on` 影响。"""
    base_on = EntryChainConfig(scoring_repair_v2="on")
    assert dynamic_weights(0.02, base_on)[0] == dict(BASE_WEIGHTS)
    ema_on = EntryChainConfig(use_ema_architecture=True, scoring_repair_v2="on")
    ema_off = EntryChainConfig(use_ema_architecture=True)
    assert dynamic_weights(0.02, ema_on)[0] == dynamic_weights(0.02, ema_off)[0]
    assert resolve_architecture(ema_on)[0] == "ema"


def test_repair_v2_score_uses_v2_weights() -> None:
    score, points = repair_v2_score(FIB_PA_SCORES)
    expected = sum(
        round(max(0.0, min(1.0, FIB_PA_SCORES[k])) * w, 4) for k, w in FIB_PA_WEIGHTS_V2.items()
    )
    assert score == pytest.approx(round(expected, 4))
    assert set(points) == set(FIB_PA_WEIGHTS_V2)


# ---------------------------------------------------------------- shadow 不改判定


def test_shadow_mode_keeps_action_score_leverage_notional_identical() -> None:
    """端到端：`shadow` 与 `off` 的四个值必须逐位相同（分数由调用方注入）。"""
    off = EntryChainConfig(use_fib_pa_architecture=True, scoring_repair_v2="off")
    shadow = EntryChainConfig(use_fib_pa_architecture=True, scoring_repair_v2="shadow")

    left = evaluate_entry_chain(_ctx(dict(FIB_PA_SCORES)), off)
    right = evaluate_entry_chain(_ctx(dict(FIB_PA_SCORES)), shadow)

    assert (left.action, left.score, left.leverage, left.notional_hint) == (
        right.action,
        right.score,
        right.leverage,
        right.notional_hint,
    )
    assert left.weights == right.weights
    assert left.reasons == right.reasons


# ---------------------------------------------------------------- RR 两段式


@pytest.mark.parametrize(
    ("atr_pct", "expected_base"),
    [(0.010, 4.0), (0.008, 4.0), (0.025, 4.0), (0.006, 2.0), (0.005, 2.0), (0.004, 1.0), (0.030, 1.0)],
)
def test_rr_v2_base_follows_the_same_atr_bands_as_v1(atr_pct: float, expected_base: float) -> None:
    detail = risk_reward_geometry_detail_v2(100.0, "LONG", 1.0, atr_pct, [])
    assert detail["base"] == expected_base
    assert detail["geometry_version"] == "2"


@pytest.mark.parametrize(
    ("opposition_price", "expected_bonus"),
    [(103.0, 4.0), (102.5, 3.0), (101.6, 1.5), (101.1, 0.5), (100.5, 0.0)],
)
def test_rr_v2_bonus_bands_scale_with_structure_room(opposition_price: float, expected_bonus: float) -> None:
    """stop_dist=1.5（close=100, atr=1.0, ×1.5），对手价 103 → opp_r = 2.0 → 满额 bonus。"""
    swing = type("Swing", (), {"kind": "HIGH", "price": opposition_price})()
    detail = risk_reward_geometry_detail_v2(100.0, "LONG", 1.0, 0.01, [swing])
    assert detail["bonus"] == expected_bonus
    assert detail["opposition_dist_r"] == pytest.approx((opposition_price - 100.0) / 1.5, abs=1e-3)


def test_rr_v2_missing_structure_loses_bonus_but_never_zeroes_the_score() -> None:
    """这是修复的核心：结构缺失（真实样本里 49.5%）只损失 bonus，base 仍然给分。"""
    missing = risk_reward_geometry_detail_v2(100.0, "LONG", 1.0, 0.01, [])
    assert missing["opposition_dist_r"] is None
    assert missing["bonus"] == 0.0
    assert missing["score"] == 4.0  # base 全额，不是 0
    assert missing["score"] > 0.0


def test_rr_v2_score_is_clamped_and_bounded() -> None:
    swing = type("Swing", (), {"kind": "HIGH", "price": 110.0})()
    detail = risk_reward_geometry_detail_v2(100.0, "LONG", 1.0, 0.01, [swing])
    assert detail["score"] == pytest.approx(8.0)  # base 4 + bonus 4，钳在 8
    assert risk_reward_geometry_detail_v2(0.0, "LONG", 1.0, 0.01, [])["rr_zero_reason"] == "INVALID_INPUT"
    assert risk_reward_geometry_detail_v2(100.0, "LONG", 0.0, 0.01, [])["score"] == 0.0


# ---------------------------------------------------------------- CVD 连续化


def test_cvd_v2_is_continuous_not_binary() -> None:
    """构造四种成交量方向比，分数必须落在不止三档上（v1 只有 1.0 / 0.5 / 0.2）。

    全部手算得出（`signed_ratio = Σ(sign(close−open)×vol) / Σvol`）：
      A 六根全阳、等量                       → (600)/600 = **+1.0**
      B 三阳三阴、等量                       → (300−300)/600 = **0.0**
      C 六根全阴、等量                       → **−1.0**
      D 四阳(100) + 两阴(50)                 → (400−100)/500 = **+0.6**  ← v1 给不出来
    """
    cases = {
        "A": _bars([100, 101, 102, 103, 104, 105], volumes=[100] * 6, opens=[99, 100, 101, 102, 103, 104]),
        "B": _bars(
            [101, 102, 103, 102, 101, 100],
            volumes=[100] * 6,
            opens=[100, 101, 102, 103, 102, 101],
        ),
        "C": _bars([99, 98, 97, 96, 95, 94], volumes=[100] * 6, opens=[100, 99, 98, 97, 96, 95]),
        "D": _bars(
            [101, 102, 103, 104, 102, 101],
            volumes=[100, 100, 100, 100, 50, 50],
            opens=[100, 101, 102, 103, 103, 102],
        ),
    }
    ratios = {name: volume_flow_score_v2("LONG", bars)["signed_ratio"] for name, bars in cases.items()}
    assert ratios["A"] == pytest.approx(1.0)
    assert ratios["B"] == pytest.approx(0.0)
    assert ratios["C"] == pytest.approx(-1.0)
    assert ratios["D"] == pytest.approx(0.6)
    scores = {round(volume_flow_score_v2("LONG", bars)["score"], 6) for bars in cases.values()}
    assert len(scores) == 4, f"分数仍有重复档位，没有连续化: {sorted(scores)}"


def test_cvd_v2_score_is_side_symmetric_and_bounded() -> None:
    bullish = _bars([100, 101, 102, 103, 104, 105])
    long_score = volume_flow_score_v2("LONG", bullish)["score"]
    short_score = volume_flow_score_v2("SHORT", bullish)["score"]
    assert long_score == pytest.approx(1.0)
    assert short_score == pytest.approx(0.0)
    assert 0.0 <= short_score <= 1.0 <= long_score


def test_cvd_v2_short_history_is_neutral_not_zero() -> None:
    """不足 6 根 → 中性 0.5。v1 返回 0.0 会把 14 分权重直接归零（数据不足≠信号极差）。"""
    short = _bars([100, 101, 102])
    assert volume_flow_score("LONG", short) == 0.0
    assert volume_flow_score_v2("LONG", short)["score"] == 0.5
    assert volume_flow_score_v2("LONG", short)["signed_ratio"] == 0.0


def test_cvd_v2_zero_volume_is_neutral() -> None:
    flat = _bars([100] * 6, volumes=[0.0] * 6)
    assert volume_flow_score_v2("LONG", flat) == {"score": 0.5, "signed_ratio": 0.0}


# ---------------------------------------------------------------- 分量装配


def _histories(direction: float):
    bars = [
        BacktestBar("XUSDT", 1000 + i * 900, 100 + i * direction, 101 + i * direction, 99 + i * direction, 100 + i * direction, 1000.0)
        for i in range(240)
    ]
    return {"15m": bars, "30m": bars[-80:], "1h": bars[-80:], "4h": bars[-80:]}


def test_fib_pa_component_scores_v2_path_adds_diagnostic_keys_only() -> None:
    histories = _histories(0.2)
    v1 = fib_pa_component_scores("LONG", histories, 0.01, use_repair_v2=False)
    v2 = fib_pa_component_scores("LONG", histories, 0.01, use_repair_v2=True)

    assert "rr_base" not in v1 and "rr_bonus" not in v1
    assert "rr_base" in v2 and "rr_bonus" in v2
    # 只有两个分量换了实现，其余四项必须逐位相同
    for key in ("trend_ema_context", "cci_momentum_quality", "price_action_structure", "fibonacci_location", "fib_action_cap"):
        assert v1[key] == v2[key], key
    # 归一化后都落在 0-1
    for key in FIB_PA_WEIGHTS:
        assert 0.0 <= v2[key] <= 1.0, key


def test_component_scores_passes_repair_flag_through() -> None:
    histories = _histories(0.2)
    off = component_scores("LONG", histories, 0.01, use_fib_pa_architecture=True, use_repair_v2=False)
    on = component_scores("LONG", histories, 0.01, use_fib_pa_architecture=True, use_repair_v2=True)
    assert "rr_base" in on and "rr_base" not in off
    # v2 的 RR 分归一化后仍是 0-1，且与 v1 的口径不同（两条路各自自洽即可，不要求相等）
    assert 0.0 <= off["risk_reward_geometry"] <= 1.0
    assert 0.0 <= on["risk_reward_geometry"] <= 1.0
    assert on["rr_base"] in {1.0, 2.0, 4.0}
    assert on["rr_bonus"] in {0.0, 0.5, 1.5, 3.0, 4.0}


def test_on_mode_can_move_the_score_but_shadow_cannot() -> None:
    """用真实分量走一遍：`on` 允许改分，`shadow` 不允许。"""
    histories = _histories(0.2)
    scores_v1 = component_scores("LONG", histories, 0.01, use_fib_pa_architecture=True, use_repair_v2=False)
    scores_v2 = component_scores("LONG", histories, 0.01, use_fib_pa_architecture=True, use_repair_v2=True)

    off = evaluate_entry_chain(_ctx(scores_v1), EntryChainConfig(use_fib_pa_architecture=True))
    shadow = evaluate_entry_chain(
        _ctx(scores_v1), EntryChainConfig(use_fib_pa_architecture=True, scoring_repair_v2="shadow")
    )
    on = evaluate_entry_chain(
        _ctx(scores_v2), EntryChainConfig(use_fib_pa_architecture=True, scoring_repair_v2="on")
    )

    assert off.score == shadow.score, "shadow 不得改分"
    assert off.action == shadow.action
    assert on.weights == dict(FIB_PA_WEIGHTS_V2), "on 必须用 V2 权重表"


# ---------------------------------------------------------------- 裁定 2：CVD 独立开关


def test_cvd_switch_defaults_off() -> None:
    assert EntryChainConfig().repair_v2_cvd_enabled is False


def test_rr_and_cvd_are_independent_switches() -> None:
    """RR v2 与 CVD v2 必须能单独开：只切 RR 时 CVD 仍是旧二值实现。"""
    histories = _histories(0.2)
    base = fib_pa_component_scores("LONG", histories, 0.01, use_repair_v2=False, use_cvd_v2=False)
    rr_only = fib_pa_component_scores("LONG", histories, 0.01, use_repair_v2=True, use_cvd_v2=False)
    cvd_only = fib_pa_component_scores("LONG", histories, 0.01, use_repair_v2=False, use_cvd_v2=True)
    both = fib_pa_component_scores("LONG", histories, 0.01, use_repair_v2=True, use_cvd_v2=True)

    # 只切 RR：CVD 分量必须与旧实现逐位相同
    assert rr_only["flow_cvd_confirmation"] == base["flow_cvd_confirmation"]
    assert "rr_base" in rr_only and "rr_base" not in base
    # 只切 CVD：RR 分量必须与旧实现逐位相同
    assert cvd_only["risk_reward_geometry"] == base["risk_reward_geometry"]
    assert "rr_base" not in cvd_only
    # 两个都切 = 各自单独切的结果拼起来
    assert both["flow_cvd_confirmation"] == cvd_only["flow_cvd_confirmation"]
    assert both["risk_reward_geometry"] == rr_only["risk_reward_geometry"]


def test_component_scores_passes_cvd_flag_through() -> None:
    histories = _histories(0.2)
    off = component_scores("LONG", histories, 0.01, use_fib_pa_architecture=True)
    rr_only = component_scores("LONG", histories, 0.01, use_fib_pa_architecture=True, use_repair_v2=True)
    both = component_scores(
        "LONG", histories, 0.01, use_fib_pa_architecture=True, use_repair_v2=True, use_cvd_v2=True
    )
    assert rr_only["flow_cvd_confirmation"] == off["flow_cvd_confirmation"]
    # CVD 开时取值必须等于 v2 函数的输出（单调上行样本里 v1/v2 恰好都是 1.0，
    # 所以这里不比较"是否不同"，而是钉住"取的是哪个实现"）
    expected_v2 = volume_flow_score_v2("LONG", _histories(0.2)["15m"])["score"]
    assert both["flow_cvd_confirmation"] == pytest.approx(expected_v2)


def test_shadow_with_rr_only_keeps_cvd_weight_at_v2_but_value_at_v1() -> None:
    """CVD 关 + `on` 时：CVD **取值**仍是旧二值，但**权重**用 V2 的 14（不是 18）。"""
    off_cfg = EntryChainConfig(use_fib_pa_architecture=True)
    on_cfg = EntryChainConfig(use_fib_pa_architecture=True, scoring_repair_v2="on")
    assert dynamic_weights(0.02, off_cfg)[0]["flow_cvd_confirmation"] == 18.0
    assert dynamic_weights(0.02, on_cfg)[0]["flow_cvd_confirmation"] == 14.0
    assert on_cfg.repair_v2_cvd_enabled is False  # 默认不跟着开
