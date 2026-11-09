"""出场参数唯一 spec。

**叶子模块**：不 import `paper_trading`，也不 import `lifecycle_exit`——两个方向都由
它们反向 import 本模块，否则会循环 import。

为什么要有这个文件：paper 主账本用 `TP 1.2/2.0/3.0 + max_hold 32`，回测默认用
`TP 1.0/2.0/3.0 + max_hold 16`。同一策略给出两套结论，根因就是这两组默认值从未
被放在一处对照过。P0 只把差异**显式化并登记**，不切换回测默认值（切换会让所有
历史离线结论静默换口径）。切换动作在 P1-E8。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExitSpec:
    tp_levels: tuple[float, float, float] = (1.2, 2.0, 3.0)
    tp_fractions: tuple[float, float, float] = (0.40, 0.35, 0.25)
    max_hold_bars: int = 32
    stop_first_intrabar: bool = True

    def __post_init__(self) -> None:
        if any(f <= 0 for f in self.tp_fractions):
            raise ValueError("tp_fractions must all be positive")
        if sum(self.tp_fractions) > 1.0 + 1e-9:
            raise ValueError("tp_fractions must not exceed a total of 1.0")
        if list(self.tp_levels) != sorted(self.tp_levels):
            raise ValueError("tp_levels must be ascending")
        if self.max_hold_bars <= 0:
            raise ValueError("max_hold_bars must be positive")


CANONICAL_EXIT_SPEC = ExitSpec()

# 2026-10-31 之前离线回测使用的参数。仅为复现旧结论保留，
# 新实验必须显式传入，避免与 paper 主账本混为一谈。
LEGACY_BACKTEST_EXIT_SPEC = ExitSpec(
    tp_levels=(1.0, 2.0, 3.0),
    tp_fractions=(0.40, 0.35, 0.25),
    max_hold_bars=16,
)

# P0 阶段**不切换**回测默认值：改默认会让所有历史离线结论静默换口径。
# 本常量是"已知分歧"的显式登记，P1 重跑完历史结论后才允许移除。
KNOWN_EXIT_SPEC_DIVERGENCE = (
    "paper=canonical(TP 1.2/2.0/3.0, max_hold 32) "
    "backtest=legacy(TP 1.0/2.0/3.0, max_hold 16); converge in P1 after re-running prior backtests"
)
