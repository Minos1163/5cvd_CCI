"""分腿交易成本模型。

为什么需要它
------------
`src/observability/paper_trading.py` 只用两个标量 `FEE_BPS = 5.0` / `SLIPPAGE_BPS = 5.0`
描述全部成本, 等价于「每边 10bps、往返 20bps、所有腿都是 taker」。这个模型有两个问题:

1. **没有 maker/taker 之分**。止损腿(TM_STOP_MARKET)天然是 taker, 无法 maker 化;
   入场腿与分腿止盈(TP1/TP2/TP3)才可能挂 post-only。用一个标量描述,
   会让「入场改 maker」这种局部优化被误算成「往返成本降到 8bps」。
2. **没有腿的权重**。20bps 里出场那一半其实是「75% 名义走 TP + 25% 名义走止损」的加权,
   两者成本不同, 折叠成一个数就丢掉了 TP/止损的比例信息。

本模块把成本拆成三条腿 + 各自 fee/slip, 再折算成「等效往返 bps」供标注器使用:

    round_trip_bps = entry_cost + tp_weight * tp_cost + (1 - tp_weight) * stop_cost

其中 `tp_weight` 是「按 TP 阶梯正常离场的名义占比」, 由 TP 阶梯的成交分布决定。
默认取 `0.75`(= TP 阶梯理论全成交时的名义占比 40%+35%+25% 中的前两档 + 第三档),
这是**上界乐观值**: 实际有一部分仓位从未触及 TP、直接走止损。保守口径取实测的
`tp_leg_share`, 见 `docs/analysis/stop_floor_and_edge_scan_2026-10-19.md` 的出场原因分布。

本模块只服务分析脚本, 不进入线上账本。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LegCost:
    """单条腿的成本, 单位 bps(1bps = 0.01%)。"""

    fee_bps: float
    slip_bps: float

    @property
    def total_bps(self) -> float:
        return self.fee_bps + self.slip_bps


@dataclass(frozen=True)
class CostModel:
    """一次往返的成本结构。"""

    version: str
    entry: LegCost
    tp_exit: LegCost
    stop_exit: LegCost
    note: str = ""

    def round_trip_bps(self, tp_leg_share: float = 0.75) -> float:
        """折算成等效往返 bps。

        `tp_leg_share` 是走止盈腿的名义占比; 余下 `1 - tp_leg_share` 走止损腿。
        """
        if not 0.0 <= tp_leg_share <= 1.0:
            raise ValueError("tp_leg_share must be within [0, 1]")
        return (
            self.entry.total_bps
            + tp_leg_share * self.tp_exit.total_bps
            + (1.0 - tp_leg_share) * self.stop_exit.total_bps
        )

    def describe(self, tp_leg_share: float = 0.75) -> dict:
        return {
            "version": self.version,
            "entry": {"fee_bps": self.entry.fee_bps, "slip_bps": self.entry.slip_bps},
            "tp_exit": {"fee_bps": self.tp_exit.fee_bps, "slip_bps": self.tp_exit.slip_bps},
            "stop_exit": {"fee_bps": self.stop_exit.fee_bps, "slip_bps": self.stop_exit.slip_bps},
            "tp_leg_share": tp_leg_share,
            "effective_round_trip_bps": round(self.round_trip_bps(tp_leg_share), 3),
            "note": self.note,
        }


# 币安 USDⓈ-M 永续的名义费率(外部事实, 仓库内无引用文件):
#   VIP0 taker 0.05% = 5bps, VIP0 maker 0.02% = 2bps
# `SLIPPAGE_BPS = 5.0` 是代码里给的每边固定滑点假设, 与费率档无关, 且被同时用于
# 价差 / 冲击 / 跳空三种风险(见 paper_trading.py:294-296 恰好按 stop_price 成交的假设)。
TAKER_FEE_BPS = 5.0
MAKER_FEE_BPS = 2.0
RESIDUAL_SLIP_BPS = 5.0
MAKER_RESIDUAL_SLIP_BPS = 1.0

# 现网口径: 所有腿 taker, 每边 5 fee + 5 slip = 往返 20bps
TAKER_20 = CostModel(
    version="taker_20",
    entry=LegCost(TAKER_FEE_BPS, RESIDUAL_SLIP_BPS),
    tp_exit=LegCost(TAKER_FEE_BPS, RESIDUAL_SLIP_BPS),
    stop_exit=LegCost(TAKER_FEE_BPS, RESIDUAL_SLIP_BPS),
    note="现网基线; 等价于 paper_trading.FEE_BPS=5 / SLIPPAGE_BPS=5 的往返 20bps",
)

# 只有入场改 post-only maker, 出场全 taker
ENTRY_MAKER_13 = CostModel(
    version="entry_maker_13",
    entry=LegCost(MAKER_FEE_BPS, MAKER_RESIDUAL_SLIP_BPS),
    tp_exit=LegCost(TAKER_FEE_BPS, RESIDUAL_SLIP_BPS),
    stop_exit=LegCost(TAKER_FEE_BPS, RESIDUAL_SLIP_BPS),
    note="入场 post-only maker, 出场全 taker; 13bps",
)

# 入场 + 止盈改 maker, 止损仍 taker  —— 这才是「8bps」的现实版本
HYBRID_8 = CostModel(
    version="hybrid_8",
    entry=LegCost(MAKER_FEE_BPS, MAKER_RESIDUAL_SLIP_BPS),
    tp_exit=LegCost(MAKER_FEE_BPS, MAKER_RESIDUAL_SLIP_BPS),
    stop_exit=LegCost(TAKER_FEE_BPS, RESIDUAL_SLIP_BPS),
    note="入场+TP 腿 post-only maker, 止损腿必须 taker; 折算约 7.75bps",
)

# 极限乐观: maker 费率用 VIP3+/返佣后的 1bps, 且 maker 腿零滑点
AGGRESSIVE_4 = CostModel(
    version="aggressive_4",
    entry=LegCost(1.0, 0.0),
    tp_exit=LegCost(1.0, 0.0),
    stop_exit=LegCost(TAKER_FEE_BPS, RESIDUAL_SLIP_BPS),
    note="入场+TP 零滑点、maker 1bps(需 VIP3+/返佣); 折算约 4.25bps, 仅作下界参照",
)

ALL_MODELS = (TAKER_20, ENTRY_MAKER_13, HYBRID_8, AGGRESSIVE_4)


def get(version: str) -> CostModel:
    for m in ALL_MODELS:
        if m.version == version:
            return m
    raise KeyError(f"unknown cost model: {version}")


def breakeven_stop_pct(model: CostModel, required_edge_r: float,
                       tp_leg_share: float = 0.75) -> float | None:
    """给定毛利 `E[R]`，求 `cost_R <= E[R]` 所需的最小止损宽度。

    `cost_R = (round_trip_bps/1e4) / stop_pct` ⇒ `stop_pct = (round_trip_bps/1e4) / E[R]`
    返回 None 表示 `required_edge_r <= 0`(无正毛利, 无论多宽的止损都打不平)。
    """
    if required_edge_r <= 0:
        return None
    return (model.round_trip_bps(tp_leg_share) / 10000.0) / required_edge_r
