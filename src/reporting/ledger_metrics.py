"""账本级度量：把逐事件日志还原成"仓位级"记录，并给出可复核的统计量。

依据 2026-11-09 的策略优化建议（ChatGPT）§2、§10、§11、§12(E1/E7)、§16.5、
附录 A 的要求实现。三条硬约束：

1. **PnL 只认 ``net_pnl_full``**（毛利 − 出场成本 − 摊分后的建仓成本）。
   ``net_pnl`` 是 close-only，``margin_pnl`` 已被标记为杠杆双计，二者只做对照列，
   不得替代权威值。
2. **不做跨文档求和**：``summary.json`` 里的 realized 是**累计计数器**，按日相加会
   重复计数。本模块只从事件流重建，每次重建的合计必须等于账本自身写下的值。
3. **样本不足必须说 INCONCLUSIVE**，而不是给一个看起来能用的点估计。

本模块是纯函数 + 只读，不写任何运行时状态，也不参与交易判定。
"""

from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Callable, Iterable, Mapping, Sequence

# 账面口径版本：与 paper_trading.PNL_SCHEMA_VERSION 对齐；不一致时报告里显式写出。
EXPECTED_PNL_SCHEMA_VERSION = 2

# 样本量门槛（附录 B 的 INCONCLUSIVE 判据）。用**有效块数**而不是名义笔数：
# 同一 symbol 同一 UTC 日的多笔交易共享行情环境，不是独立样本。
MIN_EFFECTIVE_BLOCKS_FOR_CONCLUSION = 30


def utc_date(ts: int) -> str:
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d")


@dataclass(frozen=True)
class PositionRecord:
    """一笔仓位的完整生命周期（可能包含多次 PAPER_REDUCE）。"""

    position_id: str
    ledger: str
    symbol: str
    side: str
    entry_ts: int
    exit_ts: int | None
    closed: bool
    notional: float
    leverage: int
    stop_pct: float
    gross_pnl: float
    net_close_only: float
    net_full: float
    entry_fee: float
    entry_slippage: float
    exit_fee: float
    exit_slippage: float
    entry_channel: str | None = None
    source_quadrant: str | None = None
    exit_mode: str | None = None
    exit_reason: str | None = None
    experiment_id: str | None = None
    score: float | None = None
    reduce_count: int = 0

    @property
    def total_cost(self) -> float:
        return self.entry_fee + self.entry_slippage + self.exit_fee + self.exit_slippage

    @property
    def block_key(self) -> str:
        return f"{self.symbol}|{utc_date(self.entry_ts)}"

    @property
    def hold_bars(self) -> int | None:
        if self.exit_ts is None:
            return None
        return int((self.exit_ts - self.entry_ts) // 900)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["total_cost"] = round(self.total_cost, 6)
        payload["block_key"] = self.block_key
        payload["hold_bars"] = self.hold_bars
        return payload


def load_event_files(paths: Iterable[str | Path]) -> list[dict[str, Any]]:
    """按给定顺序读取所有 ``paper_trades.jsonl``，保留原始顺序（不排序、不去重）。

    重复事件的处理交给调用方：本函数不假设日志一定干净。
    """
    events: list[dict[str, Any]] = []
    for path in paths:
        p = Path(path)
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return events


def rebuild_positions(events: Sequence[Mapping[str, Any]], *, ledger: str) -> list[PositionRecord]:
    """把 OPEN / REDUCE / CLOSE 事件还原成仓位级记录。

    - 建仓成本在 PAPER_OPEN 上一次性记录（fee + slippage），平仓事件的 ``net_pnl``
      不含它；``net_full = Σnet_pnl − 建仓成本``，这是唯一权威口径。
    - 没有 ``position_id`` 的历史事件直接跳过（无法配对，宁可少算也不错配）。
    """
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for event in events:
        pid = event.get("position_id")
        if not pid:
            continue
        grouped.setdefault(str(pid), []).append(event)

    records: list[PositionRecord] = []
    for pid, items in grouped.items():
        opens = [e for e in items if e.get("event") == "PAPER_OPEN"]
        if not opens:
            continue
        opened = opens[0]
        closes = [e for e in items if e.get("event") in ("PAPER_CLOSE", "PAPER_REDUCE")]
        final = next((e for e in items if e.get("event") == "PAPER_CLOSE"), None)

        entry_cost_fee = float(opened.get("fee") or 0.0)
        entry_cost_slip = float(opened.get("slippage") or 0.0)
        exit_fee = sum(float(e.get("fee") or 0.0) for e in closes)
        exit_slip = sum(float(e.get("slippage") or 0.0) for e in closes)
        net_close_only = sum(float(e.get("net_pnl") or 0.0) for e in closes)
        gross = sum(float(e.get("gross_pnl") or 0.0) for e in closes)

        records.append(
            PositionRecord(
                position_id=pid,
                ledger=ledger,
                symbol=str(opened.get("symbol") or ""),
                side=str(opened.get("side") or ""),
                entry_ts=int(opened.get("timestamp") or 0),
                exit_ts=int(final.get("timestamp")) if final and final.get("timestamp") else None,
                closed=final is not None,
                notional=float(opened.get("notional") or 0.0),
                leverage=int(opened.get("leverage") or 1),
                stop_pct=float(opened.get("stop_pct") or 0.0),
                gross_pnl=gross,
                net_close_only=net_close_only,
                net_full=net_close_only - entry_cost_fee - entry_cost_slip,
                entry_fee=entry_cost_fee,
                entry_slippage=entry_cost_slip,
                exit_fee=exit_fee,
                exit_slippage=exit_slip,
                entry_channel=opened.get("entry_channel"),
                source_quadrant=opened.get("source_quadrant"),
                exit_mode=opened.get("exit_mode"),
                exit_reason=(final or {}).get("reason"),
                experiment_id=opened.get("experiment_id"),
                score=float(opened["score"]) if opened.get("score") is not None else None,
                reduce_count=sum(1 for e in closes if e.get("event") == "PAPER_REDUCE"),
            )
        )
    records.sort(key=lambda r: (r.entry_ts, r.position_id))
    return records


def select_window(
    records: Sequence[PositionRecord],
    *,
    since_ts: int | None = None,
    until_ts: int | None = None,
    closed_only: bool = True,
) -> list[PositionRecord]:
    """按**建仓时间**筛选窗口。用建仓时间而不是平仓时间，保证同一笔不会被两个窗口各算一次。"""
    out = []
    for r in records:
        if closed_only and not r.closed:
            continue
        if since_ts is not None and r.entry_ts < since_ts:
            continue
        if until_ts is not None and r.entry_ts > until_ts:
            continue
        out.append(r)
    return out


# --------------------------------------------------------------------------- #
# 基础统计
# --------------------------------------------------------------------------- #


def profit_factor(values: Sequence[float]) -> float | None:
    wins = sum(v for v in values if v > 0)
    losses = abs(sum(v for v in values if v < 0))
    if losses == 0:
        return None if wins == 0 else float("inf")
    return wins / losses


def win_rate(values: Sequence[float]) -> float:
    return sum(1 for v in values if v > 0) / len(values) if values else 0.0


def payoff_ratio(values: Sequence[float]) -> float | None:
    wins = [v for v in values if v > 0]
    losses = [v for v in values if v < 0]
    if not wins or not losses:
        return None
    return (sum(wins) / len(wins)) / (abs(sum(losses)) / len(losses))


def break_even_win_rate(values: Sequence[float]) -> float | None:
    """使期望为零的胜率：p·avg_win = (1-p)·avg_loss。"""
    wins = [v for v in values if v > 0]
    losses = [v for v in values if v < 0]
    if not wins or not losses:
        return None
    avg_win = sum(wins) / len(wins)
    avg_loss = abs(sum(losses)) / len(losses)
    return avg_loss / (avg_win + avg_loss)


def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float] | None:
    """Wilson 区间（不做连续性校正）。total=0 返回 None 而不是 (0,0)。"""
    if total <= 0:
        return None
    p = successes / total
    denom = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denom
    margin = z * ((p * (1 - p) / total + z * z / (4 * total * total)) ** 0.5) / denom
    return (max(0.0, center - margin), min(1.0, center + margin))


def summary_metrics(records: Sequence[PositionRecord]) -> dict[str, Any]:
    values = [r.net_full for r in records]
    wins = sum(1 for v in values if v > 0)
    gross = sum(r.gross_pnl for r in records)
    total_cost = sum(r.total_cost for r in records)
    return {
        "trade_count": len(values),
        "wins": wins,
        "losses": sum(1 for v in values if v < 0),
        "flats": sum(1 for v in values if v == 0),
        "win_rate": round(win_rate(values), 6),
        "profit_factor": _round_or_none(profit_factor(values)),
        "payoff_ratio": _round_or_none(payoff_ratio(values)),
        "break_even_win_rate": _round_or_none(break_even_win_rate(values)),
        "expectancy": round(mean(values), 6) if values else 0.0,
        "net_pnl_full": round(sum(values), 6),
        "gross_pnl": round(gross, 6),
        "total_cost": round(total_cost, 6),
        "cost_to_gross": round(total_cost / gross, 6) if gross > 0 else None,
        # 对照列：close-only 与 deprecated 口径，只用于说明差多少，不作结论
        "net_close_only": round(sum(r.net_close_only for r in records), 6),
        "full_minus_close_only": round(-sum(r.entry_fee + r.entry_slippage for r in records), 6),
    }


def _round_or_none(value: float | None, digits: int = 6) -> float | None:
    if value is None:
        return None
    if value == float("inf"):
        return float("inf")
    return round(value, digits)


def concentration_metrics(records: Sequence[PositionRecord]) -> dict[str, Any]:
    """盈利集中度。

    **两个分母必须分开报**，否则会得出两个都"对"但差 25 个百分点的数字：

    - ``*_share_of_gross_profit``：分母是全部盈利单之和 45.36 那一类，
      回答"盈利单之间是否集中"。
    - ``*_share_of_net``：分母是净额 33.76 那一类，回答"净收益是否靠一笔撑着"。
      2026-11-08 归因报告的 97.59% 用的是这个分母。

    历史文档只写"占比 97.59%"而不写分母，是本次重复计算才发现的口径隐患。
    """
    values = [r.net_full for r in records]
    total = sum(values)
    profits = [v for v in values if v > 0]
    gross_profit = sum(profits)
    abs_sum = sum(abs(v) for v in values)
    ordered = sorted(values, reverse=True)
    top = sorted(records, key=lambda r: r.net_full, reverse=True)

    def share(k: int, denom: float) -> float | None:
        if denom == 0:
            return None
        return round(sum(ordered[:k]) / denom, 6)

    return {
        "net_pnl_full": round(total, 6),
        "gross_profit": round(gross_profit, 6),
        "hhi_abs": round(sum((abs(v) / abs_sum) ** 2 for v in values), 6) if abs_sum else None,
        "hhi_uniform_benchmark": round(1 / len(values), 6) if values else None,
        "top1_share_of_gross_profit": share(1, gross_profit),
        "top2_share_of_gross_profit": share(2, gross_profit),
        "top1_share_of_net": share(1, total),
        "top2_share_of_net": share(2, total),
        "share_basis_note": "share_of_gross_profit 与 share_of_net 分母不同，引用时必须写明是哪一个",
        "ex_top1_net_pnl": round(total - ordered[0], 6) if ordered else 0.0,
        "ex_top2_net_pnl": round(total - sum(ordered[:2]), 6) if len(ordered) >= 2 else None,
        "top_contributors": [
            {
                "position_id": r.position_id,
                "symbol": r.symbol,
                "side": r.side,
                "net_pnl_full": round(r.net_full, 6),
                "share_of_gross_profit": round(r.net_full / gross_profit, 6)
                if gross_profit > 0 and r.net_full > 0
                else None,
                "share_of_net": round(r.net_full / total, 6) if total else None,
            }
            for r in top[:3]
        ],
    }


def cost_metrics(records: Sequence[PositionRecord]) -> dict[str, Any]:
    entry_fee = sum(r.entry_fee for r in records)
    entry_slip = sum(r.entry_slippage for r in records)
    exit_fee = sum(r.exit_fee for r in records)
    exit_slip = sum(r.exit_slippage for r in records)
    total = entry_fee + entry_slip + exit_fee + exit_slip
    gross = sum(r.gross_pnl for r in records)
    return {
        "entry_fee": round(entry_fee, 6),
        "entry_slippage": round(entry_slip, 6),
        "exit_fee": round(exit_fee, 6),
        "exit_slippage": round(exit_slip, 6),
        "total_cost": round(total, 6),
        "cost_to_gross": round(total / gross, 6) if gross > 0 else None,
        "cost_per_trade": round(total / len(records), 6) if records else None,
        "note": "fee/slippage 均为常数假设 5+5bps（cost_source=constant_assumption），不含 funding",
    }


# 成本压力的标准档位（建议文档 §12.7 E6）
COST_STRESS_SCENARIOS: tuple[dict[str, Any], ...] = (
    {"name": "slippage_+25%", "fee_mult": 1.0, "slip_mult": 1.25},
    {"name": "slippage_+50%", "fee_mult": 1.0, "slip_mult": 1.5},
    {"name": "fee_+25%", "fee_mult": 1.25, "slip_mult": 1.0},
    {"name": "combined_+50%", "fee_mult": 1.5, "slip_mult": 1.5},
)


def cost_stress_metrics(records: Sequence[PositionRecord]) -> dict[str, Any]:
    """成本压力：把 fee/slippage 按倍数放大，看净额还剩多少。

    **近似**：出场名义按建仓名义计（忽略持仓期价格变动）。误差量级约等于平均
    单笔毛收益率（本策略 ≈1%），远小于成本档位差（25%）。此近似在报告里显式声明，
    不要当成精确值。

    同时给出"成本安全边际"：成本整体上升多少比例会让净额归零。
    这是比"当前 PF 多少"更该看的数——它回答"离亏钱还有多远"。
    """

    def extra_cost(fee_mult: float, slip_mult: float) -> float:
        extra = 0.0
        for r in records:
            notional = abs(r.notional)
            # 进出各一次；5bps 基准由 record 里的实际成本/名义反推不稳健，直接用基准假设
            base_fee_bps, base_slip_bps = 5.0, 5.0
            extra += notional * (base_fee_bps / 1e4) * (fee_mult - 1) * 2
            extra += notional * (base_slip_bps / 1e4) * (slip_mult - 1) * 2
        return extra

    base_net = sum(r.net_full for r in records)
    base_cost = sum(r.total_cost for r in records)
    scenarios = []
    for sc in COST_STRESS_SCENARIOS:
        extra = extra_cost(sc["fee_mult"], sc["slip_mult"])
        scenarios.append(
            {
                "scenario": sc["name"],
                "fee_mult": sc["fee_mult"],
                "slip_mult": sc["slip_mult"],
                "extra_cost": round(extra, 6),
                "net_pnl_full": round(base_net - extra, 6),
                "still_profitable": bool(base_net - extra > 0),
            }
        )

    # 成本整体 +x% 时净额归零 → x = base_net / base_cost
    margin = (base_net / base_cost) if base_cost > 0 else None

    # 集中度极高时，"成本安全边际 230%" 这种数完全由单笔撑着。
    # 必须同时给出剔除最大赢家后的版本，否则会误导读者以为很安全。
    ex_top1 = sorted(records, key=lambda r: r.net_full, reverse=True)[1:] if len(records) > 1 else []
    if ex_top1:
        ex_net = sum(r.net_full for r in ex_top1)
        ex_cost = sum(r.total_cost for r in ex_top1)
        ex_scenarios = []
        for sc in COST_STRESS_SCENARIOS:
            extra = sum(
                abs(r.notional) * (5.0 / 1e4) * (sc["fee_mult"] - 1) * 2
                + abs(r.notional) * (5.0 / 1e4) * (sc["slip_mult"] - 1) * 2
                for r in ex_top1
            )
            ex_scenarios.append(
                {
                    "scenario": sc["name"],
                    "net_pnl_full": round(ex_net - extra, 6),
                    "still_profitable": bool(ex_net - extra > 0),
                }
            )
        ex_block = {
            "base_net_pnl_full": round(ex_net, 6),
            "base_total_cost": round(ex_cost, 6),
            "scenarios": ex_scenarios,
            "cost_inflation_to_breakeven": round(ex_net / ex_cost, 4) if ex_cost > 0 else None,
        }
    else:
        ex_block = None

    return {
        "base_net_pnl_full": round(base_net, 6),
        "base_total_cost": round(base_cost, 6),
        "note": "出场名义按建仓名义近似；档位为建议文档 §12.7 E6 的标准四档",
        "scenarios": scenarios,
        "cost_inflation_to_breakeven": round(margin, 4) if margin is not None else None,
        "cost_inflation_to_breakeven_note": (
            "成本整体上升该比例后净额归零；<0 表示当前已是成本上升的净亏损方"
        ),
        "excluding_top1": ex_block,
        "excluding_top1_note": "剔除最大赢家后重算；集中度高时这一组才是可外推的口径",
    }


def block_metrics(records: Sequence[PositionRecord]) -> dict[str, Any]:
    """有效样本量：块 = symbol|utc_date(建仓日)。"""
    blocks: dict[str, int] = {}
    for r in records:
        blocks[r.block_key] = blocks.get(r.block_key, 0) + 1
    counts = list(blocks.values())
    n = len(records)
    return {
        "n_nominal": n,
        "n_effective_blocks": len(blocks),
        "max_positions_in_one_block": max(counts) if counts else 0,
        "overlap_ratio": round(n / len(blocks), 3) if blocks else None,
        "blocks": dict(sorted(blocks.items())),
    }


# --------------------------------------------------------------------------- #
# 块 bootstrap
# --------------------------------------------------------------------------- #

_STAT_FUNCS: dict[str, Callable[[Sequence[PositionRecord]], float]] = {
    "expectancy": lambda rs: mean([r.net_full for r in rs]) if rs else 0.0,
    "net_total": lambda rs: sum(r.net_full for r in rs),
    "win_rate": lambda rs: win_rate([r.net_full for r in rs]),
}


def block_bootstrap_ci(
    records: Sequence[PositionRecord],
    *,
    stat: str = "expectancy",
    n_boot: int = 10000,
    seed: int = 20261109,
    alpha: float = 0.05,
) -> dict[str, Any]:
    """按块重抽样的百分位区间。

    重抽样单位是 ``symbol|utc_date`` 块而不是单笔交易：同一 block 内的交易共享
    同一段行情，按笔重抽会把相关样本当独立样本，区间会过窄。
    """
    if stat not in _STAT_FUNCS:
        raise ValueError(f"unknown stat '{stat}' (allowed: {sorted(_STAT_FUNCS)})")
    if not records:
        return {"stat": stat, "n_boot": n_boot, "point": None, "ci_low": None, "ci_high": None, "note": "empty"}

    grouped: dict[str, list[PositionRecord]] = {}
    for r in records:
        grouped.setdefault(r.block_key, []).append(r)
    keys = sorted(grouped)
    rng = random.Random(seed)
    fn = _STAT_FUNCS[stat]
    point = fn(records)

    samples: list[float] = []
    for _ in range(n_boot):
        drawn: list[PositionRecord] = []
        for _ in keys:
            drawn.extend(grouped[rng.choice(keys)])
        samples.append(fn(drawn))
    samples.sort()
    lo = samples[int((alpha / 2) * len(samples))]
    hi = samples[int((1 - alpha / 2) * len(samples)) - 1]
    return {
        "stat": stat,
        "n_boot": n_boot,
        "seed": seed,
        "blocks": len(keys),
        "point": round(point, 6),
        "ci_low": round(lo, 6),
        "ci_high": round(hi, 6),
        "ci_crosses_zero": bool(lo <= 0 <= hi),
    }


# --------------------------------------------------------------------------- #
# 滚动窗口
# --------------------------------------------------------------------------- #


def rolling_window_metrics(
    records: Sequence[PositionRecord],
    *,
    window_days: int = 30,
    min_trades_per_window: int = 1,
) -> dict[str, Any]:
    """按平仓日聚合到日，再取滚动窗口。样本不足的窗口标记 INCONCLUSIVE。"""
    closed = [r for r in records if r.closed and r.exit_ts]
    if not closed:
        return {"window_days": window_days, "windows": [], "verdict": "INCONCLUSIVE"}

    daily: dict[str, list[float]] = {}
    for r in closed:
        daily.setdefault(utc_date(r.exit_ts or 0), []).append(r.net_full)
    days = sorted(daily)
    start = datetime.strptime(days[0], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end = datetime.strptime(days[-1], "%Y-%m-%d").replace(tzinfo=timezone.utc)

    windows: list[dict[str, Any]] = []
    cursor = start
    while cursor <= end:
        lo = cursor.strftime("%Y-%m-%d")
        hi = (cursor.toordinal() + window_days - 1)
        hi_date = datetime.fromordinal(hi).replace(tzinfo=timezone.utc).strftime("%Y-%m-%d")
        values = [v for d in days if lo <= d <= hi_date for v in daily[d]]
        windows.append(
            {
                "start": lo,
                "end": hi_date,
                "trades": len(values),
                "net_pnl_full": round(sum(values), 6),
                "verdict": "PASS" if len(values) >= min_trades_per_window else "INCONCLUSIVE",
            }
        )
        cursor = datetime.fromordinal(cursor.toordinal() + window_days).replace(tzinfo=timezone.utc)

    full = [w for w in windows if w["verdict"] == "PASS"]
    totals = [w["net_pnl_full"] for w in full]
    return {
        "window_days": window_days,
        "window_count": len(windows),
        "usable_window_count": len(full),
        "median_net": round(_median(totals), 6) if totals else None,
        "worst_net": round(min(totals), 6) if totals else None,
        "best_net": round(max(totals), 6) if totals else None,
        "windows": windows,
        "verdict": "PASS" if len(full) >= 2 else "INCONCLUSIVE",
    }


def _median(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


# --------------------------------------------------------------------------- #
# 结论判定
# --------------------------------------------------------------------------- #


def decide_verdict(
    records: Sequence[PositionRecord],
    *,
    min_effective_blocks: int = MIN_EFFECTIVE_BLOCKS_FOR_CONCLUSION,
) -> dict[str, Any]:
    """把"能不能下结论"和"结论是什么"拆成两个字段。

    早期版本只输出一个 PASS/INCONCLUSIVE，被读成"策略通过"——那是误读：
    它只回答样本够不够。这里显式拆开：

    - ``sample_verdict``：有效块数是否达标、样本是否单边。
    - ``edge_verdict``：只有在样本达标**且**期望的块 bootstrap 区间排除 0
      **且**剔除最大赢家后仍为正时，才叫 ESTABLISHED。

    三个条件缺一即 NOT_ESTABLISHED——这是保守定义，宁可漏报也不虚报。
    """
    blocks = block_metrics(records)
    values = [r.net_full for r in records]
    reasons: list[str] = []
    if blocks["n_effective_blocks"] < min_effective_blocks:
        reasons.append(f"effective blocks {blocks['n_effective_blocks']} < {min_effective_blocks}")
    if values and all(v >= 0 for v in values):
        reasons.append("no losing trades in window (one-sided sample)")
    if values and all(v <= 0 for v in values):
        reasons.append("no winning trades in window (one-sided sample)")
    sample_ok = not reasons

    boot = block_bootstrap_ci(records, stat="expectancy")
    total = sum(values)
    ex_top1 = total - max(values) if values else 0.0
    edge_reasons: list[str] = []
    if not sample_ok:
        edge_reasons.append("sample insufficient")
    if boot.get("ci_low") is None or boot["ci_low"] <= 0:
        edge_reasons.append("expectancy bootstrap 95% CI includes 0")
    if ex_top1 <= 0:
        edge_reasons.append("net negative after removing top-1 winner")

    return {
        "sample_verdict": "SUFFICIENT" if sample_ok else "INCONCLUSIVE",
        "edge_verdict": "ESTABLISHED" if (sample_ok and not edge_reasons) else "NOT_ESTABLISHED",
        "reasons": reasons,
        "edge_reasons": edge_reasons,
        "min_effective_blocks": min_effective_blocks,
        "n_effective_blocks": blocks["n_effective_blocks"],
        "n_nominal": blocks["n_nominal"],
        "ex_top1_net_pnl": round(ex_top1, 6),
        "expectancy_ci": [boot.get("ci_low"), boot.get("ci_high")],
    }


# --------------------------------------------------------------------------- #
# 报告组装（对应建议文档附录 A 的字段表）
# --------------------------------------------------------------------------- #


def build_report(
    records: Sequence[PositionRecord],
    *,
    window: Mapping[str, Any],
    ledger: str,
    source_files: Sequence[str] = (),
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    summary = summary_metrics(records)
    concentration = concentration_metrics(records)
    blocks = block_metrics(records)
    verdict = decide_verdict(records)
    values = [r.net_full for r in records]
    wins = sum(1 for v in values if v > 0)
    wilson_nominal = wilson_interval(wins, len(values))
    wilson_cluster = wilson_interval(wins, blocks["n_effective_blocks"]) if blocks["n_effective_blocks"] else None
    break_even = break_even_win_rate(values)

    report: dict[str, Any] = {
        "ledger": ledger,
        "window": dict(window),
        "pnl_schema_version": EXPECTED_PNL_SCHEMA_VERSION,
        "pnl_accounting_mode": "notional_primary_margin_reporting",
        "authoritative_field": "net_pnl_full",
        "source_files": list(source_files),
        "summary": summary,
        "concentration": concentration,
        "cost": cost_metrics(records),
        "cost_stress": cost_stress_metrics(records),
        "rolling": rolling_window_metrics(records, window_days=30),
        "sample": blocks,
        "verdict": verdict,
        "bootstrap": {
            "expectancy": block_bootstrap_ci(records, stat="expectancy"),
            "net_total": block_bootstrap_ci(records, stat="net_total"),
            "win_rate": block_bootstrap_ci(records, stat="win_rate"),
        },
        "wilson_win_rate": {
            "nominal": _pair(wilson_nominal),
            "cluster_adjusted": _pair(wilson_cluster),
            "break_even_win_rate": _round_or_none(break_even),
            # 两个问题要分开回答：胜率是否高于打平线（Wilson），与期望是否为正（bootstrap）。
            # 它们可以给出相反结论，报告里必须同时出现，不能只挑一个。
            "cluster_ci_excludes_break_even": (
                None
                if (wilson_cluster is None or break_even is None)
                else bool(wilson_cluster[0] > break_even)
            ),
            "note": "Wilson 用二项近似，不处理收益幅度；bootstrap 处理幅度但对极值敏感。两者不一致时以区间更宽的为准。",
        },
        "by_side": _group(records, lambda r: r.side),
        "by_symbol": _group(records, lambda r: r.symbol),
        "by_exit_reason": _group(records, lambda r: r.exit_reason or "UNKNOWN"),
        "by_channel": _group(records, lambda r: r.entry_channel or "UNKNOWN"),
        "trades": [r.to_dict() for r in records],
    }
    if extra:
        report.update(dict(extra))
    return report


def _pair(interval: tuple[float, float] | None) -> list[float] | None:
    return None if interval is None else [round(interval[0], 6), round(interval[1], 6)]


def _group(records: Sequence[PositionRecord], key: Callable[[PositionRecord], str]) -> dict[str, Any]:
    buckets: dict[str, list[PositionRecord]] = {}
    for r in records:
        buckets.setdefault(key(r) or "UNKNOWN", []).append(r)
    out: dict[str, Any] = {}
    for name, items in sorted(buckets.items()):
        values = [r.net_full for r in items]
        out[name] = {
            "trades": len(items),
            "net_pnl_full": round(sum(values), 6),
            "win_rate": round(win_rate(values), 6),
            "expectancy": round(mean(values), 6),
        }
    return out


def render_markdown(report: Mapping[str, Any]) -> str:
    """把报告渲染成可评审的 Markdown（附录 A 的字段顺序）。"""
    s = report["summary"]
    c = report["concentration"]
    cost = report["cost"]
    sample = report["sample"]
    verdict = report["verdict"]

    lines: list[str] = []
    lines.append(f"# 账本度量报告 · {report['ledger']}")
    lines.append("")
    w = report["window"]
    lines.append(f"- 窗口：**{w.get('since', 'ALL')} → {w.get('until', 'ALL')}**（按建仓时间筛选）")
    lines.append(f"- 权威口径：`{report['authoritative_field']}`（pnl_schema_version={report['pnl_schema_version']}）")
    lines.append(f"- 结论：样本 **{verdict['sample_verdict']}**，边际 **{verdict['edge_verdict']}**")
    if verdict["reasons"]:
        lines.append(f"  - 样本不足原因：{'；'.join(verdict['reasons'])}")
    if verdict["edge_reasons"]:
        lines.append(f"  - 未确立边际原因：{'；'.join(verdict['edge_reasons'])}")
    lines.append("")
    lines.append("## 1. 汇总")
    lines.append("")
    lines.append("| 指标 | 值 |")
    lines.append("|---|---:|")
    for key in ("trade_count", "wins", "losses", "win_rate", "profit_factor", "payoff_ratio",
                "break_even_win_rate", "expectancy", "net_pnl_full", "gross_pnl", "total_cost", "cost_to_gross"):
        lines.append(f"| {key} | {_fmt(s[key])} |")
    lines.append("")
    lines.append(f"> 对照：close-only 合计 `{s['net_close_only']}`，与全成本相差 `{s['full_minus_close_only']}`"
                 f"（= 建仓成本）。close-only 不得用于结论。")
    lines.append("")
    lines.append("## 2. 集中度（首要风险提示）")
    lines.append("")
    lines.append("| 指标 | 值 |")
    lines.append("|---|---:|")
    for key in ("hhi_abs", "hhi_uniform_benchmark",
                "top1_share_of_gross_profit", "top2_share_of_gross_profit",
                "top1_share_of_net", "top2_share_of_net",
                "ex_top1_net_pnl", "ex_top2_net_pnl"):
        lines.append(f"| {key} | {_fmt(c[key])} |")
    lines.append("")
    lines.append(f"> {c['share_basis_note']}。2026-11-08 归因报告的 97.59% 用的是 **share_of_net**。")
    lines.append("")
    if c["top_contributors"]:
        lines.append("贡献前三：")
        for t in c["top_contributors"]:
            share = t["share_of_gross_profit"]
            net_share = t["share_of_net"]
            parts = []
            if share is not None:
                parts.append(f"占毛利 {share:.2%}")
            if net_share is not None:
                parts.append(f"占净额 {net_share:.2%}")
            lines.append(f"- `{t['position_id']}` {t['net_pnl_full']:+.6f}"
                         + (f"（{'，'.join(parts)}）" if parts else ""))
    lines.append("")
    lines.append("## 3. 成本")
    lines.append("")
    lines.append("| 项 | USDT |")
    lines.append("|---|---:|")
    for key in ("entry_fee", "entry_slippage", "exit_fee", "exit_slippage", "total_cost"):
        lines.append(f"| {key} | {_fmt(cost[key])} |")
    lines.append(f"| cost_per_trade | {_fmt(cost['cost_per_trade'])} |")
    lines.append("")
    lines.append(f"> {cost['note']}")
    lines.append("")
    stress = report.get("cost_stress") or {}
    if stress.get("scenarios"):
        lines.append("### 成本压力（§12.7 E6）")
        lines.append("")
        lines.append("| 情景 | 额外成本 | 净额 | 仍盈利 |")
        lines.append("|---|---:|---:|:--:|")
        for sc in stress["scenarios"]:
            lines.append(f"| {sc['scenario']} | {sc['extra_cost']:+.6f} | {sc['net_pnl_full']:+.6f} | {'是' if sc['still_profitable'] else '否'} |")
        lines.append("")
        margin = stress.get("cost_inflation_to_breakeven")
        if margin is not None:
            lines.append(f"- **成本安全边际：成本整体上升 {margin:+.2%} 后净额归零。**")
            lines.append(f"  > {stress['cost_inflation_to_breakeven_note']}；{stress['note']}")
        ex = stress.get("excluding_top1")
        if ex:
            lines.append(f"- 剔除最大赢家后：净额 {ex['base_net_pnl_full']:+.6f}，"
                         f"成本上升 {ex['cost_inflation_to_breakeven']:+.2%} 即归零"
                         f"（{stress['excluding_top1_note']}）。")
        lines.append("")
    lines.append("## 4. 样本与不确定性")
    lines.append("")
    lines.append(f"- 名义笔数 `{sample['n_nominal']}`，有效块数 `{sample['n_effective_blocks']}`"
                 f"（块 = symbol|utc_date，重叠率 {sample['overlap_ratio']}）")
    wl = report["wilson_win_rate"]
    if wl["nominal"]:
        lines.append(f"- 胜率 Wilson 95%（名义 n）：[{wl['nominal'][0]:.4f}, {wl['nominal'][1]:.4f}]")
    if wl["cluster_adjusted"]:
        lines.append(f"- 胜率 Wilson 95%（按块数）：[{wl['cluster_adjusted'][0]:.4f}, {wl['cluster_adjusted'][1]:.4f}]")
    if wl["break_even_win_rate"] is not None:
        lines.append(f"- 打平胜率（由实测赔率反解）：{wl['break_even_win_rate']:.4f}；"
                     f"聚类区间是否排除打平线：**{wl['cluster_ci_excludes_break_even']}**")
        lines.append(f"  > {wl['note']}")
    for name, boot in report["bootstrap"].items():
        if boot.get("point") is None:
            continue
        lines.append(f"- `{name}` 点估计 {boot['point']}，块 bootstrap 95% CI "
                     f"[{boot['ci_low']}, {boot['ci_high']}]{'（跨 0）' if boot['ci_crosses_zero'] else ''}")
    lines.append("")
    lines.append("## 5. 分组")
    lines.append("")
    for dim in ("by_side", "by_symbol", "by_exit_reason", "by_channel"):
        rows = report[dim]
        if not rows:
            continue
        lines.append(f"**{dim}**")
        lines.append("")
        lines.append("| 组 | 笔数 | 净额 | 胜率 | 期望 |")
        lines.append("|---|---:|---:|---:|---:|")
        for name, v in rows.items():
            lines.append(f"| {name} | {v['trades']} | {v['net_pnl_full']:+.6f} | {v['win_rate']:.4f} | {v['expectancy']:+.6f} |")
        lines.append("")
    lines.append("## 6. 复现")
    lines.append("")
    lines.append("```bash")
    lines.append("python scripts/report_strategy_review.py --ledger main \\")
    lines.append(f"  --since {w.get('since', '')} --until {w.get('until', '')}")
    lines.append("```")
    lines.append("")
    lines.append("> ⚠️ 本报告由脚本从事件流重建，不构成投资建议。样本不足时结论为 INCONCLUSIVE，"
                 "不得当作策略有效的证据。")
    return "\n".join(lines)


def _fmt(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        if value == float("inf"):
            return "inf"
        return f"{value:.6f}"
    return str(value)
