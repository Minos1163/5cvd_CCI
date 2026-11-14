"""交易几何统一对象：把「止损宽度 / 止损价 / TP 阶梯 / 净 R」收敛到一处。

背景（2026-11-14 评审 §12、§13）：同一套止损宽度在仓库里有**三套口径**同时存在——

1. `EntryChainContext.stop_pct`（live 侧构造，用于仓位与风控）；
2. `risk_reward_geometry_detail` 内部 `max(close×0.005, min(close×0.030, atr×1.5))`
   （评分侧的 RR 打分）；
3. 报告/分析脚本各自的 R 倍数换算。

三套口径数值上未必一致，而"净 TP1 R"这种量在讨论成本时又必须在**同一个几何**上算。
本模块只做一件事：把 2 号口径（也是唯一进入 `score` 的口径）显式化成一个不可变对象，
让 `risk_reward_geometry_detail` 与测试共用同一处定义。

零行为变化约束（P0 铁律）：
`stop_dist` 刻意按**价格空间**写成 `max(entry×min, min(entry×max, atr×mult))`，
与重构前 `entry_chain_features.py` 的一行式逐位相同。**不要**改写成
`entry_price × clamp(atr/entry_price×mult, min, max)`——两者数学等价但浮点结果可能
差 1 ulp，而 `stop_dist` 直接进入 `net_tp1_r` 与 1.3/1.1/0.9 三个评分阈值比较，
1 ulp 的漂移在边界样本上足以翻转 `score` → 翻转 `action`。
`stop_pct` 因此是由 `stop_dist / entry_price` **反推**的派生量，而不是主口径。

成本口径注意：
`net_tp1_r(cost_bps)` 里的 `cost_bps` 是**往返总成本**（开+平），以 bps(1bp=0.01%) 计。
当前评分实际只扣了 10bps（`cost_bps_used_by_score = 10.0`），而实盘往返更接近 20bps，
所以 20bps 口径的净 R 只作为诊断字段输出，**不参与打分**。
"""

from __future__ import annotations

from dataclasses import dataclass

# 与 `risk_reward_geometry_detail` 历史硬编码完全一致（不是新参数，是同一组常量的唯一出处）。
DEFAULT_STOP_MULT = 1.5
DEFAULT_MIN_STOP_PCT = 0.005
DEFAULT_MAX_STOP_PCT = 0.030
DEFAULT_TP_LEVELS: tuple[float, float, float] = (1.2, 2.0, 3.0)
DEFAULT_COST_BPS_ROUND_TRIP = 20.0

LONG = "LONG"
SHORT = "SHORT"


@dataclass(frozen=True)
class TradeGeometry:
    """单笔交易的几何：入场价 + 方向 + ATR 决定止损，止损决定 TP 阶梯与 R 倍数。

    所有属性都是纯函数式派生，不改外部状态、不做 IO。
    """

    entry_price: float
    side: str
    atr: float
    stop_mult: float = DEFAULT_STOP_MULT
    min_stop_pct: float = DEFAULT_MIN_STOP_PCT
    max_stop_pct: float = DEFAULT_MAX_STOP_PCT
    tp_levels: tuple[float, float, float] = DEFAULT_TP_LEVELS
    cost_bps_round_trip: float = DEFAULT_COST_BPS_ROUND_TRIP

    @property
    def is_short(self) -> bool:
        """方向判定沿用仓库既有口径：只有 `SHORT` 是空，其余按多处理。

        历史上 `nearest_opposition_price` 就是 `if side == "SHORT": ... else 多`。
        这里**不做严格校验/抛错**——geometry 被真实决策链路调用，为非法 side 抛异常
        等于把"日志口径问题"升级成"停机",属于行为变更。
        """
        return str(self.side).strip().upper() == SHORT

    @property
    def side_sign(self) -> float:
        return -1.0 if self.is_short else 1.0

    @property
    def stop_dist(self) -> float:
        """止损距离（价格单位）。与历史一行式逐位相同，见模块 docstring。

        刻意**不**对 `atr <= 0` 特判：历史 clamp 在 atr=0 时落到 `min_stop_pct` 下限
        （`max(entry×0.005, min(entry×0.030, 0))` = `entry×0.005`），保持同一行为。
        唯一的除以零风险在 `stop_pct`（`entry_price == 0`），那里单独兜住。
        """
        return max(
            self.entry_price * self.min_stop_pct,
            min(self.entry_price * self.max_stop_pct, self.atr * self.stop_mult),
        )

    @property
    def stop_pct(self) -> float:
        """止损宽度（占入场价比例），由 `stop_dist / entry_price` 反推。

        数学上等于 `clamp(atr/entry × stop_mult, min_stop_pct, max_stop_pct)`，
        但保留反推形式以保证与 `stop_dist` 自洽（不引入第二次浮点舍入差异）。
        """
        if self.entry_price <= 0:
            return 0.0
        return self.stop_dist / self.entry_price

    @property
    def stop_price(self) -> float:
        if self.is_short:
            return self.entry_price * (1.0 + self.stop_pct)
        return self.entry_price * (1.0 - self.stop_pct)

    @property
    def tp_prices(self) -> tuple[float, float, float]:
        sign = self.side_sign
        return tuple(
            self.entry_price * (1.0 + sign * self.stop_pct * level) for level in self.tp_levels
        )

    @property
    def gross_r_per_tp(self) -> tuple[float, float, float]:
        """毛 R 倍数（未扣成本）：按定义就是 TP 阶梯本身（TP 以止损距离的倍数定义）。"""
        return tuple(float(level) for level in self.tp_levels)

    def net_tp1_r(self, cost_bps: float | None = None) -> float:
        """扣往返成本后的 TP1 净 R。

        ``net = tp_levels[0] − (cost_bps/10000) / stop_pct``

        成本是按**名义**计的比例（bps），除以 `stop_pct` 折算成 R：止损越窄，
        同样的成本吃掉越多 R——这正是"窄止损 + 固定成本"的核心问题。
        """
        stop_pct = self.stop_pct
        if stop_pct <= 0:
            return 0.0
        bps = self.cost_bps_round_trip if cost_bps is None else float(cost_bps)
        return float(self.tp_levels[0]) - (bps / 10000.0) / stop_pct
