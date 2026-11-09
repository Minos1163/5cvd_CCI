"""决策溯源：记录"这笔交易原本是什么信号、被谁替换、替换后又被谁降级"。

背景（2026-10-31 之后的真实结构）：
- `green_channel_decision = build_q1_green_channel_decision(base_decision=decision, ...)`
  每个周期**无条件调用**，返回非 None 即覆盖 `decision`；
- 覆盖后仍继续经过 `apply_dry_run_decision_controls`、`apply_experimental_quadrant_entry_rules`、
  `apply_entry_gates`、`regime_overlay.cap_decision`。

于是"账本里这个 DIRECT 是谁给的"有 5 种可能，改动前完全看不出来。本模块只补留痕：
**不参与任何判定，不删不改既有键。**

字段级行为等价判定：同一输入下 `action` / `score` / `leverage` / `exit_mode` 与改动前相同。
说"逐字节等价"是错的——加了键就不可能逐字节相同。
"""

from __future__ import annotations

from typing import Any, Mapping

SNAPSHOT_FIELDS = (
    "action",
    "score",
    "side",
    "leverage",
    "exit_mode",
    "entry_channel",
)


def _field(obj: Any, name: str) -> Any:
    """同时支持 Mapping 与对象（主循环里的 decision 是 EntryChainDecision 数据类）。"""
    if isinstance(obj, Mapping):
        return obj.get(name)
    return getattr(obj, name, None)


def decision_id(decision: Any, payload: Mapping[str, Any]) -> str:
    symbol = _field(decision, "symbol") or payload.get("symbol") or "UNKNOWN"
    timestamp = _field(decision, "timestamp") or payload.get("timestamp") or 0
    side = _field(decision, "side") or payload.get("side") or "NONE"
    return f"{symbol}:{int(timestamp)}:{side}"


def _snapshot(decision: Any, payload: Mapping[str, Any]) -> dict[str, Any]:
    """快照必须对 payload 兜底。

    真实的 EntryChainDecision（src/signals/entry_chain.py:63-75）只有
    action/side/score/weights/component_points/reasons/risk_allowed/leverage/
    max_symbol_exposure_pct/notional_hint/liquidity_ratio/metadata，
    **没有** symbol/timestamp/exit_mode/entry_channel——这四个只在 payload 里。
    不兜底的话 replaced_snapshot.exit_mode 在生产上恒为 None。
    """
    snapshot: dict[str, Any] = {}
    for field in SNAPSHOT_FIELDS:
        value = _field(decision, field)
        if value is None:
            value = payload.get(field)
        snapshot[field] = value
    snapshot["quadrant"] = payload.get("quadrant")
    return snapshot


def annotate_replacement(
    base_decision: Any,
    base_payload: Mapping[str, Any],
    new_decision: Any | None,
    new_payload: Mapping[str, Any] | None,
    *,
    origin: str = "q1_green_channel",
) -> tuple[Any, dict[str, Any]]:
    """标注"决策被替换"。

    - 未替换（``new_decision is None``）：返回原决策 + 副本 payload，只打
      ``decision_origin="primary"``。
    - 已替换：返回新决策 + 新 payload 的副本，加 ``decision_origin`` /
      ``replaced_decision_id`` / ``replaced_snapshot``。

    两条路径都**不就地修改**入参——调用方可能还持有原件做后续比较。
    """
    if new_decision is None or new_payload is None:
        merged = dict(base_payload)
        merged["decision_origin"] = "primary"
        return base_decision, merged

    merged = dict(new_payload)
    merged["decision_origin"] = origin
    merged["replaced_decision_id"] = decision_id(base_decision, base_payload)
    merged["replaced_snapshot"] = _snapshot(base_decision, base_payload)
    return new_decision, merged
