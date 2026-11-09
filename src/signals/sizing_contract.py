"""仓位轨迹契约：让每笔交易能回答"最终名义是哪个 cap 卡的、每个 cap 各是多少"。

三个 cap（`entry_chain._notional_cap_diagnostics` 已经算过一次，这里**只读不重算**）：
- ``raw_notional``：按单笔风险比例 / 止损宽度反推的名义
- ``leveraged_cap_notional``：杠杆对应的风险上限
- ``remaining_exposure_notional``：单币种敞口剩余额度

``final_notional = min(三者)`` 且 ``binding_cap`` 必须指向那个最小值——这两条是
"仓位由谁决定"的唯一可验证表述。违反只**告警不拦单**（P0 只加观测）。
"""

from __future__ import annotations

from typing import Any, Mapping

SIZING_TRACE_KEYS = (
    "raw_notional",
    "leveraged_cap_notional",
    "remaining_exposure_notional",
    "final_notional",
    "binding_cap",
    "leverage",
    "leverage_reason",
)

_CAP_KEYS = (
    "raw_notional",
    "leveraged_cap_notional",
    "remaining_exposure_notional",
)


def assert_sizing_trace(trace: Mapping[str, Any]) -> None:
    # 非入场路径：entry_chain.py 在 action 非 PROBE/DIRECT、数据无效、敞口耗尽时
    # 返回 binding_cap="none"，此时三 cap 不存在。这类路径必须豁免，
    # 否则每根无效 bar 都会触发误报。
    if str(trace.get("binding_cap")) == "none":
        return

    missing = [key for key in SIZING_TRACE_KEYS if key not in trace]
    if missing:
        raise AssertionError(f"missing sizing trace keys: {missing}")

    caps = {key: float(trace[key]) for key in _CAP_KEYS}
    expected = min(caps.values())
    if abs(float(trace["final_notional"]) - expected) > 1e-6:
        raise AssertionError(
            f"final_notional {trace['final_notional']} != min(caps) {expected}"
        )

    binding = str(trace["binding_cap"])
    if binding not in caps:
        raise AssertionError(f"binding_cap {binding} 不是三种 cap 之一")
    if abs(caps[binding] - expected) > 1e-6:
        raise AssertionError(
            f"binding_cap {binding} 的数值 {caps[binding]} 不是最小 cap {expected}"
        )


def summarize_sizing_trace(trace: Mapping[str, Any]) -> dict[str, Any]:
    """压缩成固定 6 键，便于逐笔入账与横向比较。

    `capped_by_ratio = final/raw`：1.0 表示没被任何 cap 削，越小说明削得越狠。
    raw 为 0（非入场路径）时返回 0.0，不做除法。
    """
    raw = float(trace["raw_notional"])
    final = float(trace["final_notional"])
    return {
        "raw_notional": raw,
        "leveraged_cap_notional": float(trace["leveraged_cap_notional"]),
        "remaining_exposure_notional": float(trace["remaining_exposure_notional"]),
        "final_notional": final,
        "binding_cap": str(trace["binding_cap"]),
        "capped_by_ratio": (final / raw) if raw else 0.0,
    }
