"""S1 影子核:4h 趋势过滤(long/flat),**只写日志、不参与任何决策**。

规则(与 `docs/analysis/s1_overlay_oos_2026-10-20.md` 的验证口径一致)
---------------------------------------------------------------------
- 4h 收盘价序列,`SMA50 > SMA200` → `LONG`,否则 `FLAT`;
- 每 42 根(7 天)才检查一次换仓,但影子层每个周期都算,`rebalance_due` 由外部
  (持有根数)决定 —— 这里只输出"当前状态",不做时序状态机;
- 序列不足 `slow + 1` 根 → `INSUFFICIENT`。

为什么放在影子层
----------------
`entry_chain` 的 15m 评分已被证明没有毛边际;S1 是一个**不同周期**的方向规则,
直接替换决策核风险太大。按 v3 §8 的迁移纪律,先做影子:写 `s1_core` 字段,
由 `tests/test_score_core_s1.py` 断言它不会改动 `score / action / notional`。

开关
----
`EntryChainConfig.score_core`:
- `"legacy"`(默认):完全不算,`s1_core` 字段不出现 → 历史行为逐字段不变;
- `"s1_shadow"`:只计算并写入日志。
"""

from __future__ import annotations

from typing import Any, Sequence

SCHEMA_VERSION = "s1-core-v1"

#: 影子层允许的取值。写进 config 时会被校验。
VALID_MODES = ("legacy", "s1_shadow")


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values)


def s1_regime(closes: Sequence[float], *, fast: int = 50, slow: int = 200) -> dict[str, Any]:
    """返回当前 4h 趋势状态。纯函数,无副作用。

    ``direction`` 取 ``1``(LONG)/``0``(FLAT);``ready=False`` 时也返回 0,
    但 ``state`` 会是 ``"INSUFFICIENT"``,便于下游区分"空仓"与"没数据"。
    """
    needed = max(fast, slow) + 1
    series = [float(x) for x in closes if x is not None]
    if len(series) < needed:
        return {
            "schema_version": SCHEMA_VERSION,
            "state": "INSUFFICIENT",
            "ready": False,
            "direction": 0,
            "bars": len(series),
            "required_bars": needed,
        }
    sma_fast = _mean(series[-fast:])
    sma_slow = _mean(series[-slow:])
    direction = 1 if sma_fast > sma_slow else 0
    return {
        "schema_version": SCHEMA_VERSION,
        "state": "LONG" if direction else "FLAT",
        "ready": True,
        "direction": direction,
        "sma_fast": sma_fast,
        "sma_slow": sma_slow,
        "spread_pct": (sma_fast / sma_slow - 1.0) if sma_slow else 0.0,
        "bars": len(series),
        "required_bars": needed,
    }


def s1_shadow(closes_4h: Sequence[float], *, mode: str = "s1_shadow") -> dict[str, Any] | None:
    """影子入口:``legacy`` 模式返回 ``None``(下游据此不写字段)。"""
    if mode == "legacy":
        return None
    if mode not in VALID_MODES:
        raise ValueError(f"unknown score_core mode: {mode!r}")
    payload = s1_regime(closes_4h)
    payload["mode"] = mode
    return payload
