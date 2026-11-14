"""q1 通道 shadow 开关守卫（P0 A5，2026-11-14 评审 §14）。

背景：`green_channel_decision` 每个周期**无条件调用**，返回非 None 就覆盖主决策。
也就是说 q1 通道现在有权替换主决策，而"替换 vs 不替换"的样本差从未被测量过。

`q1_trend_launch_shadow_only` 提供第三条路：**只记录不覆盖**。
- 默认 `False` → 走原路径（`annotate_replacement`），生产行为逐位不变；
- `True` → 走 `annotate_shadow_decision`，主决策对象原样返回，q1 只写进 payload 的
  `shadow_decision` 键。

本文件锁三件事：
1. 默认值是 False（否则生产行为会变）；
2. `annotate_shadow_decision` 返回的第一项**就是**传入的 base_decision（同一对象），
   因此 action/score/leverage/notional 机械不变——不是靠调用方自觉；
3. shadow 模式**不写** `replaced_decision_id`（没替换就不能标替换，否则账本里
   "被替换"与"被记录"无法区分）。
"""

from __future__ import annotations

import pytest

from src.signals.decision_provenance import annotate_replacement, annotate_shadow_decision
from src.signals.entry_chain import EntryChainContext, evaluate_entry_chain
from src.signals.entry_chain_config import EntryChainConfig, load_entry_chain_config

PRODUCTION_CONFIG = "configs/entry_chain.dry_run_regime_shadow.json"


class _Decision:
    """最小决策替身：只带 SNAPSHOT_FIELDS + reasons/notional_hint/risk_allowed。"""

    def __init__(self, action: str, score: float, leverage: int = 2, notional: float = 250.0):
        self.action = action
        self.score = score
        self.side = "LONG"
        self.leverage = leverage
        self.notional_hint = notional
        self.risk_allowed = action in {"PROBE", "DIRECT"}
        self.exit_mode = "trend_capture"
        self.entry_channel = "q1_green_channel"
        self.reasons = ("Q1_TREND_LAUNCH",)


def _payload(action: str, score: float, **extra):
    payload = {
        "symbol": "BTCUSDT",
        "timestamp": 1_700_000_000,
        "side": "LONG",
        "action": action,
        "score": score,
        "exit_mode": "trend_capture",
        "quadrant": "Q1",
    }
    payload.update(extra)
    return payload


def test_switch_defaults_to_false_and_production_config_keeps_it_false() -> None:
    """默认 False = 现状。生产配置显式写 false，防止有人"顺手打开"。"""
    assert EntryChainConfig().q1_trend_launch_shadow_only is False
    assert load_entry_chain_config(PRODUCTION_CONFIG).q1_trend_launch_shadow_only is False


def test_shadow_annotation_returns_the_primary_decision_object() -> None:
    """返回值第一项必须**是** base_decision 本身（同一对象），四个值因此机械不变。"""
    primary = _Decision("PROBE", 84.0, leverage=2, notional=250.0)
    shadow = _Decision("DIRECT", 88.0, leverage=4, notional=800.0)

    decision, payload = annotate_shadow_decision(
        primary,
        _payload("PROBE", 84.0),
        shadow,
        _payload("DIRECT", 88.0, exit_mode="trend_capture"),
    )

    assert decision is primary
    assert decision.action == "PROBE"
    assert decision.score == 84.0
    assert decision.leverage == 2
    assert decision.notional_hint == 250.0


def test_shadow_annotation_records_shadow_without_replacement_markers() -> None:
    primary = _Decision("PROBE", 84.0)
    shadow = _Decision("DIRECT", 88.0, leverage=4, notional=800.0)

    _decision, payload = annotate_shadow_decision(
        primary,
        _payload("PROBE", 84.0),
        shadow,
        _payload("DIRECT", 88.0),
    )

    assert payload["decision_origin"] == "primary"
    assert "replaced_decision_id" not in payload
    assert "replaced_snapshot" not in payload
    snapshot = payload["shadow_decision"]
    assert snapshot["action"] == "DIRECT"
    assert snapshot["score"] == 88.0
    assert snapshot["leverage"] == 4
    assert snapshot["notional_hint"] == 800.0
    assert snapshot["exit_mode"] == "trend_capture"
    assert snapshot["entry_channel"] == "q1_green_channel"
    assert snapshot["reasons"] == ["Q1_TREND_LAUNCH"]
    assert snapshot["origin"] == "q1_green_channel"


def test_replacement_path_still_writes_replacement_markers() -> None:
    """对照：开关为 False 的老路径保持原样（这条防"顺手统一"两函数）。"""
    primary = _Decision("PROBE", 84.0)
    shadow = _Decision("DIRECT", 88.0)

    decision, payload = annotate_replacement(
        primary,
        _payload("PROBE", 84.0),
        shadow,
        _payload("DIRECT", 88.0),
        origin="q1_green_channel",
    )

    assert decision is shadow
    assert payload["decision_origin"] == "q1_green_channel"
    assert payload["replaced_decision_id"] == "BTCUSDT:1700000000:LONG"
    assert payload["replaced_snapshot"]["action"] == "PROBE"
    assert "shadow_decision" not in payload


def test_shadow_annotation_without_shadow_decision_is_primary_only() -> None:
    primary = _Decision("PROBE", 84.0)
    decision, payload = annotate_shadow_decision(primary, _payload("PROBE", 84.0), None, None)
    assert decision is primary
    assert payload["decision_origin"] == "primary"
    assert "shadow_decision" not in payload


def test_shadow_annotation_does_not_mutate_inputs() -> None:
    primary = _Decision("PROBE", 84.0)
    base_payload = _payload("PROBE", 84.0)
    before = dict(base_payload)

    annotate_shadow_decision(primary, base_payload, _Decision("DIRECT", 88.0), _payload("DIRECT", 88.0))

    assert base_payload == before, "不得就地修改入参 payload"


def test_real_decisions_can_be_annotated_as_shadow(tmp_path) -> None:
    """端到端形状：真实 EntryChainDecision 也能进 shadow 标注且四个值不变。"""
    context = EntryChainContext(
        symbol="BTCUSDT",
        timestamp=1_700_000_000,
        side="LONG",
        component_scores={
            "trend_ema_context": 1.0,
            "flow_cvd_confirmation": 1.0,
            "cci_momentum_quality": 1.0,
            "price_action_structure": 1.0,
            "fibonacci_location": 1.0,
            "risk_reward_geometry": 0.75,
            "fib_action_cap": 1.0,
        },
        quote_volume_24h=5e9,
        atr_pct=0.01,
        expected_order_size=1_000.0,
        account_equity=10_000.0,
        available_margin=8_000.0,
        stop_pct=0.015,
    )
    cfg = EntryChainConfig(use_fib_pa_architecture=True, q1_trend_launch_shadow_only=True)
    primary = evaluate_entry_chain(context, cfg)
    shadow = evaluate_entry_chain(context, EntryChainConfig(use_fib_pa_architecture=True, direct_risk_pct=0.02))

    decision, payload = annotate_shadow_decision(
        primary,
        {"symbol": "BTCUSDT", "timestamp": primary.metadata.get("symbol") or 0},
        shadow,
        {"action": shadow.action, "score": shadow.score},
    )

    assert decision is primary
    assert decision.action == primary.action
    assert decision.notional_hint == primary.notional_hint
    assert payload["decision_origin"] == "primary"
    assert payload["shadow_decision"]["action"] == shadow.action
    assert payload["shadow_decision"]["notional_hint"] == shadow.notional_hint
    assert "replaced_decision_id" not in payload


@pytest.mark.parametrize("shadow_only", [False, True])
def test_switch_does_not_change_resolved_decision_values(shadow_only: bool) -> None:
    """开关只改"谁进 payload"，不改决策本身：同一配置下两态 decision 完全相同。"""
    context = EntryChainContext(
        symbol="BTCUSDT",
        timestamp=1_700_000_000,
        side="LONG",
        component_scores={
            "trend_ema_context": 1.0,
            "flow_cvd_confirmation": 1.0,
            "cci_momentum_quality": 1.0,
            "price_action_structure": 1.0,
            "fibonacci_location": 1.0,
            "risk_reward_geometry": 0.75,
            "fib_action_cap": 1.0,
        },
        quote_volume_24h=5e9,
        atr_pct=0.01,
        expected_order_size=1_000.0,
        account_equity=10_000.0,
        available_margin=8_000.0,
        stop_pct=0.015,
    )
    base = EntryChainConfig(use_fib_pa_architecture=True)
    switched = EntryChainConfig(use_fib_pa_architecture=True, q1_trend_launch_shadow_only=shadow_only)

    left = evaluate_entry_chain(context, base)
    right = evaluate_entry_chain(context, switched)

    assert (left.action, left.score, left.leverage, left.notional_hint) == (
        right.action,
        right.score,
        right.leverage,
        right.notional_hint,
    )
