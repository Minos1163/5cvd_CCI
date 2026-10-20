"""`regime_overlay`:组合层的仓位规则(4h 趋势 → 目标仓位 0/1)。

定位
----
这东西**不是信号**,是**仓位上限**:
- `SMA50 > SMA200`(4h)→ 目标仓位 1(允许持有);
- 否则目标仓位 0(不许新开,已有仓位按出场逻辑正常管理)。

为什么放 `portfolio` 层
-----------------------
它输出的是"组合允许的最大仓位",不是"某根 bar 该不该开单"。放进 `entry_chain` 的评分链
会把"仓位规则"伪装成"信号",这是前面失败过的思路。分层上 `portfolio` 只依赖 `config`,
不 import `signals`,避免跨层引用。

参数来源(预登记,不可事后改)
--------------------------
`MA(50,200)` + 每 24 根 4h 检查一次:由 `scripts/analysis/regime_overlay_wf_20261020.py`
在**训练窗口 2021-10-21~2024-12-31** 上从 4 组候选里选出,检验窗口只跑一次,3/3 标的过门。
见 `logs/analysis/long-history/2026-10-20/regime-overlay-wf.md`。

模式
----
- `off`(默认):完全不计算,历史行为逐字段不变;
- `shadow`:只计算并写入 `decisions.jsonl` 的 `regime_overlay` 字段;
- `cap`:在 shadow 基础上,目标仓位为 0 时**拦截新开仓**(把 DIRECT/PROBE 降为 NO_TRADE,
  `notional_hint` 归零,reason 追加 `REGIME_OVERLAY_FLAT`)。已有持仓不在此处处理。
"""

from __future__ import annotations

from typing import Any, Sequence

SCHEMA_VERSION = "regime-overlay-v1"

MA_FAST = 50
MA_SLOW = 200
#: 检查频率(4h 根)。来自预登记的 walk-forward 选择,不要随手改。
REBALANCE_BARS = 24

VALID_MODES = ("off", "shadow", "cap")


def regime_target(
    closes_4h: Sequence[float],
    *,
    fast: int = MA_FAST,
    slow: int = MA_SLOW,
) -> dict[str, Any]:
    """返回目标仓位(1=允许持有,0=不允许新开)。纯函数。"""
    needed = max(fast, slow) + 1
    series = [float(x) for x in closes_4h if x is not None]
    if len(series) < needed:
        return {
            "schema_version": SCHEMA_VERSION,
            "ready": False,
            "state": "INSUFFICIENT",
            "target": 0,
            "bars": len(series),
            "required_bars": needed,
        }
    ma_fast = sum(series[-fast:]) / fast
    ma_slow = sum(series[-slow:]) / slow
    target = 1 if ma_fast > ma_slow else 0
    return {
        "schema_version": SCHEMA_VERSION,
        "ready": True,
        "state": "RISK_ON" if target else "RISK_OFF",
        "target": target,
        "ma_fast": ma_fast,
        "ma_slow": ma_slow,
        "spread_pct": (ma_fast / ma_slow - 1.0) if ma_slow else 0.0,
        "rebalance_bars": REBALANCE_BARS,
        "bars": len(series),
        "required_bars": needed,
    }


def should_block_entry(mode: str, target: int) -> bool:
    """`cap` 模式下、目标仓位为 0 时拦截新开仓。"""
    if mode not in VALID_MODES:
        raise ValueError(f"unknown regime_overlay mode: {mode!r}")
    return mode == "cap" and int(target) == 0


#: 被拦截时追加的 reason,便于在日志里回溯是哪一层挡的。
BLOCK_REASON = "REGIME_OVERLAY_FLAT"


def cap_decision(
    *,
    mode: str,
    target: int,
    action: str,
    notional_hint: float,
    reasons: tuple[str, ...] | list[str],
) -> tuple[str, float, tuple[str, ...], bool]:
    """把"目标仓位为 0"落到一条决策上。

    只降级新开仓(`DIRECT`/`PROBE`),**不动已有持仓**——平仓仍由出场逻辑负责。
    返回 ``(action, notional_hint, reasons, blocked)``。
    """
    action_upper = str(action).upper()
    if not should_block_entry(mode, target):
        return action_upper, float(notional_hint), tuple(reasons), False
    if action_upper not in {"DIRECT", "PROBE"}:
        return action_upper, float(notional_hint), tuple(reasons), False
    return "NO_TRADE", 0.0, tuple(reasons) + (BLOCK_REASON,), True


def overlay_payload(closes_4h: Sequence[float], *, mode: str) -> dict[str, Any] | None:
    """按模式产出要落盘的字段;`off` 返回 None(不写字段)。"""
    if mode not in VALID_MODES:
        raise ValueError(f"unknown regime_overlay mode: {mode!r}")
    if mode == "off":
        return None
    payload = regime_target(closes_4h)
    payload["mode"] = mode
    return payload
