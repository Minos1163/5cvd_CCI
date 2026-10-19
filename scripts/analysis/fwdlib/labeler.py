"""前向标注引擎:把 ``fwd_label_20261019.py`` 的标注逻辑搬成可参数化组件。

与旧脚本的关系
--------------
本模块是旧脚本 ``build_bars`` / ``_entry_and_start`` / ``label_barrier`` /
``label_ladder`` / ``resolve_stop`` / ``run_labeling`` 的**逐位等价**迁移:
同样的价格序列、同样的止损宽度、同样的默认参数下,输出的 ``R`` / ``R_net`` /
``reason`` / ``bars`` 与旧脚本完全一致(浮点运算顺序也保持不变)。

差异只有两类,且都是**新增**:

* 硬编码常量改为参数/``LabelConfig`` 字段(horizon、成本 bps、止损 clamp、
  TP 阶梯、成本保本根数、象限防御开关);
* 每行结果新增 ``gross_R`` / ``entry_ts`` / ``exit_ts`` / ``hold_seconds`` /
  ``horizon`` 五个键,旧键一个不删、不改名(下游 8 个脚本仍按旧键读)。

参数优先级
----------
``cfg`` 提供基线,显式传参覆盖 ``cfg``。由于函数签名必须保留旧默认值
(``label_barrier`` 的 ``entry_mode="next_open"``、``label_ladder`` 的
``entry_mode="bar_close"`` 等),实现上把「值等于旧默认值」视为未覆盖 ——
调用方若要压过 ``cfg``,传一个非旧默认的值即可;不传 ``cfg`` 时行为与旧脚本
完全相同。
"""

from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone

from .config import (
    COST_BREAKEVEN_BUFFER_MULT,
    POST_TP_STOP_OFFSET,
    TRAILING_R_MULT,
    TREND_TRIGGER_R,
    LabelConfig,
)
from .cost import cost_r

__all__ = [
    "Bar",
    "Bars",
    "Index",
    "PerSymbol",
    "build_bars",
    "build_quadrant_map",
    "entry_and_start",
    "grid_audit",
    "label_at_horizons",
    "label_barrier",
    "label_ladder",
    "resolve_stop",
    "run_labeling",
    "timeout_profile",
]

Bar = tuple[float, float, float, float]
Bars = dict[tuple[str, int], Bar]
PerSymbol = dict[str, list[int]]
Index = dict[str, dict[int, int]]

#: 旧脚本的默认值,用于判断「调用方是否真的覆盖了 cfg」。
_LEGACY_ENTRY_BARRIER = "next_open"
_LEGACY_ENTRY_LADDER = "bar_close"
_LEGACY_EXIT_MODE = "barrier"
_LEGACY_POST_TP = "legacy"
_LEGACY_FLAG = False

#: 时间型离场原因(用于 ``timeout_profile``):barrier 的 TIMEOUT、ladder 的
#: 成本保本超时与最大持仓。
_TIMEOUT_REASONS = frozenset({"TIMEOUT", "COST_BREAKEVEN_TIMEOUT", "MAX_HOLD"})


def _cfg(cfg: LabelConfig | None) -> LabelConfig:
    return LabelConfig() if cfg is None else cfg


def _pick(value, legacy_default, cfg_value, cfg_given: bool):
    """显式参数优先;值仍等于旧默认(即调用方没真的覆盖)时退回 ``cfg``。"""
    if not cfg_given:
        return value
    return cfg_value if value == legacy_default else value


def _resolve_horizon(horizon: int | None, cfg: LabelConfig) -> int:
    h = cfg.horizon_bars if horizon is None else int(horizon)
    if h < 1:
        raise ValueError(f"horizon 必须 >= 1, 实际 {h!r}")
    return h


# --------------------------------------------------------------------------- #
# 价格面板
# --------------------------------------------------------------------------- #

def build_bars(decisions) -> tuple[Bars, PerSymbol, Index]:
    """把决策行内嵌的 15m OHLC 拼成按标的索引的价格面板。

    ``per_symbol`` / ``index`` 返回普通 dict(内容排序与旧脚本一致),便于 JSON 化。
    """
    bars: Bars = {}
    for d in decisions:
        if d["open"] is None:
            continue
        bars[(d["symbol"], d["ts"])] = (d["open"], d["high"], d["low"], d["close"])
    per_symbol: PerSymbol = defaultdict(list)
    for sym, ts in bars:
        per_symbol[sym].append(ts)
    index: Index = defaultdict(dict)
    for sym in per_symbol:
        per_symbol[sym].sort()
        for i, ts in enumerate(per_symbol[sym]):
            index[sym][ts] = i
    return bars, per_symbol, index


def build_quadrant_map(decisions) -> dict[tuple[str, int], str]:
    return {(d["symbol"], d["ts"]): d["quadrant"] for d in decisions if d.get("quadrant")}


def entry_and_start(bars, per_symbol, index, d, entry_mode="next_open", horizon=32) -> tuple | None:
    """定位入场价与首根可平仓 bar。

    ``next_open``: entry=次根开盘, start=i+2;``bar_close``: entry=当根收盘, start=i+1。
    """
    sym, ts = d["symbol"], d["ts"]
    order = per_symbol.get(sym) or []
    i = index.get(sym, {}).get(ts)
    if i is None:
        return None
    if entry_mode == "bar_close":
        bar = bars.get((sym, ts))
        if not bar:
            return None
        entry, start = bar[3], i + 1
    else:
        if i + 1 >= len(order):
            return None
        entry, start = bars[(sym, order[i + 1])][0], i + 2
    if not entry or start >= len(order):
        return None
    last = min(start + horizon - 1, len(order) - 1)
    return entry, start, last, order


# --------------------------------------------------------------------------- #
# 止损
# --------------------------------------------------------------------------- #

def resolve_stop(raw_stop, atr_pct, stop_floor=None, stop_scale=None, *, cfg=None) -> float:
    """还原线上止损:先 clamp(atr*mult, min, max),再套场景(floor 只升不降 / scale 全量乘)。"""
    c = _cfg(cfg)
    floor = stop_floor if stop_floor is not None else c.stop_floor
    scale = stop_scale if stop_scale is not None else c.stop_scale
    if raw_stop and raw_stop > 0:
        base = float(raw_stop)
    else:
        base = min(
            c.max_stop_pct,
            max(c.min_stop_pct, (atr_pct or 0.0) * c.atr_stop_mult),
        )
    if floor:
        base = max(base, float(floor))
    if scale and scale != 1.0:
        base = base * float(scale)
    return base


# --------------------------------------------------------------------------- #
# 三重障碍
# --------------------------------------------------------------------------- #

def label_barrier(bars, per_symbol, index, d, stop_pct, entry_mode="next_open", *,
                  cfg: LabelConfig | None = None, horizon: int | None = None) -> dict | None:
    """三重障碍标注:up=+1R / down=-1R,同根双触按最不利(AMBIGUOUS),超时按 close 折算。"""
    c = _cfg(cfg)
    h = _resolve_horizon(horizon, c)
    base = entry_and_start(bars, per_symbol, index, d, entry_mode, h)
    if base is None:
        return None
    entry, start, last, order = base
    if not stop_pct or stop_pct <= 0:
        return None
    sym = d["symbol"]
    sign = 1.0 if d["side"] == "LONG" else -1.0
    target = entry * (1 + sign * stop_pct)
    stop = entry * (1 - sign * stop_pct)
    for j in range(start, last + 1):
        _, high, low, _close = bars[(sym, order[j])]
        hit_target = (high >= target - 1e-12) if sign > 0 else (low <= target + 1e-12)
        hit_stop = (low <= stop + 1e-12) if sign > 0 else (high >= stop - 1e-12)
        if hit_target and hit_stop:
            return {"R": -1.0, "ambiguous": True, "bars": j - start + 1, "reason": "AMBIGUOUS",
                    "entry_price": entry, "stop_price": stop, "mfe_r": None}
        if hit_target:
            return {"R": 1.0, "ambiguous": False, "bars": j - start + 1, "reason": "TARGET_HIT",
                    "entry_price": entry, "stop_price": stop, "mfe_r": None}
        if hit_stop:
            return {"R": -1.0, "ambiguous": False, "bars": j - start + 1, "reason": "STOP_HIT",
                    "entry_price": entry, "stop_price": stop, "mfe_r": None}
    close = bars[(sym, order[last])][3]
    move = (close - entry) / entry * sign
    return {"R": move / stop_pct, "ambiguous": False, "bars": last - start + 1, "reason": "TIMEOUT",
            "entry_price": entry, "stop_price": stop, "mfe_r": None}


def label_at_horizons(bars, per_symbol, index, d, stop_pct,
                      horizons=(1, 2, 4, 8, 16, 32), entry_mode="next_open", *,
                      cfg: LabelConfig | None = None) -> dict[int, dict | None]:
    """一次遍历同时给出多个 horizon 的 barrier 标注。

    对每个 ``h``,结果与 ``label_barrier(..., horizon=h)`` **逐字段一致**
    (仅多一个 ``horizon`` 键):单次扫描到 ``max(horizons)``,在某根 bar 上
    触障即对「尚未结束」的 horizon 一起结算;每个 horizon 在其最后一根 bar
    用该 bar 的 close 结算超时。

    ``entry_mode`` 与其它标注函数同规则解析:``cfg`` 提供基线,显式传入非旧默认
    值时才覆盖 ``cfg``(签名默认 ``next_open`` 视为未覆盖)。``cfg`` 的其它字段
    (horizon / 成本 / 止损)不参与 —— horizon 由 ``horizons`` 显式给出。
    """
    # horizon 由 horizons 显式给出,cfg 只在 entry_mode 上提供基线,与其它函数对齐
    cfg_given = cfg is not None
    c = _cfg(cfg)
    entry_mode = _pick(entry_mode, _LEGACY_ENTRY_BARRIER, c.entry_mode, cfg_given)

    hs = sorted({int(h) for h in horizons})
    out: dict[int, dict | None] = {h: None for h in hs}
    if not hs:
        return out
    for h in hs:
        if h < 1:
            raise ValueError(f"horizon 必须 >= 1, 实际 {h!r}")

    base = entry_and_start(bars, per_symbol, index, d, entry_mode, max(hs))
    if base is None:
        return out
    entry, start, _last, order = base
    if not stop_pct or stop_pct <= 0:
        return out

    sym = d["symbol"]
    sign = 1.0 if d["side"] == "LONG" else -1.0
    target = entry * (1 + sign * stop_pct)
    stop = entry * (1 - sign * stop_pct)

    last_of = {h: min(start + h - 1, len(order) - 1) for h in hs}
    max_last = max(last_of.values())
    pending = list(hs)

    for j in range(start, max_last + 1):
        _, high, low, close = bars[(sym, order[j])]
        hit_target = (high >= target - 1e-12) if sign > 0 else (low <= target + 1e-12)
        hit_stop = (low <= stop + 1e-12) if sign > 0 else (high >= stop - 1e-12)

        if hit_target or hit_stop:
            if hit_target and hit_stop:
                res = {"R": -1.0, "ambiguous": True, "reason": "AMBIGUOUS"}
            elif hit_target:
                res = {"R": 1.0, "ambiguous": False, "reason": "TARGET_HIT"}
            else:
                res = {"R": -1.0, "ambiguous": False, "reason": "STOP_HIT"}
            hit = {
                **res,
                "bars": j - start + 1,
                "entry_price": entry,
                "stop_price": stop,
                "mfe_r": None,
            }
            for h in [x for x in pending if last_of[x] >= j]:
                out[h] = {**hit, "horizon": h}
                pending.remove(h)
            if not pending:
                break

        done = [x for x in pending if last_of[x] == j]
        if done:
            move = (close - entry) / entry * sign
            for h in done:
                out[h] = {
                    "R": move / stop_pct,
                    "ambiguous": False,
                    "bars": last_of[h] - start + 1,
                    "reason": "TIMEOUT",
                    "entry_price": entry,
                    "stop_price": stop,
                    "mfe_r": None,
                    "horizon": h,
                }
                pending.remove(h)

    return out


# --------------------------------------------------------------------------- #
# 线上出场阶梯
# --------------------------------------------------------------------------- #

def label_ladder(
    bars,
    per_symbol,
    index,
    d,
    stop_pct,
    entry_mode="bar_close",
    *,
    quad_map=None,
    quadrant_defense=False,
    q2_tighten=False,
    post_tp_mode="legacy",
    horizon: int | None = None,
    cost_breakeven_bars: int | None = None,
    cfg: LabelConfig | None = None,
) -> dict | None:
    """逐条复刻线上出场:TP 阶梯分批、同 bar 止损优先、每根最多成交一档、
    TP1 后止损移到成本 ±offset(trend_capture 下按 1R 追踪)、成本保本超时、
    最大持仓 close 平仓;可选 Q2 收紧 / Q3 减半 / Q4 全平。

    ``horizon=None`` ⇒ ``cfg.horizon_bars``;``cost_breakeven_bars=None`` ⇒
    ``cfg.replaced(horizon_bars=h).resolved_breakeven_bars()``(15m / horizon=32
    时为 8 根,与旧常量一致)。注意默认值必须按**最终 h**(显式 ``horizon`` 实参
    优先)解析:用 ``cfg.horizon_bars`` 会让 ``label_ladder(horizon=8)``、
    ``run_labeling(horizon=8)`` 与 ``cfg.horizon_bars=8`` 三条路径取到不同的
    保本根数(8 vs 2 vs 2),同一 horizon 却换了一套出场判定。
    换周期时必须让两者随周期一起缩放,否则「成本超时」与「最大持仓」会退化成同一条件。
    """
    cfg_given = cfg is not None
    c = _cfg(cfg)
    h = _resolve_horizon(horizon, c)
    entry_mode = _pick(entry_mode, _LEGACY_ENTRY_LADDER, c.entry_mode, cfg_given)
    quadrant_defense = _pick(quadrant_defense, _LEGACY_FLAG, c.quadrant_defense, cfg_given)
    q2_tighten = _pick(q2_tighten, _LEGACY_FLAG, c.q2_tighten, cfg_given)
    post_tp_mode = _pick(post_tp_mode, _LEGACY_POST_TP, c.post_tp_mode, cfg_given)
    breakeven_bars = (
        cost_breakeven_bars if cost_breakeven_bars is not None
        else c.replaced(horizon_bars=h).resolved_breakeven_bars()
    )

    base = entry_and_start(bars, per_symbol, index, d, entry_mode, h)
    if base is None:
        return None
    entry, start, last, order = base
    if not stop_pct or stop_pct <= 0:
        return None
    sym = d["symbol"]
    sign = 1.0 if d["side"] == "LONG" else -1.0
    risk = entry * stop_pct
    if risk <= 0:
        return None
    stop = entry - sign * risk
    breakeven = entry * (1.0 + sign * POST_TP_STOP_OFFSET)
    levels = [entry + sign * risk * lv for lv in c.tp_levels]
    fractions = c.tp_fractions
    cost_r_value = cost_r(c.cost_bps, stop_pct)
    remaining = 1.0
    realized = 0.0
    consumed = 0
    mfe = 0.0
    q3_done = False
    q4_streak = 0

    def _pnl(px):
        return (px - entry) * sign / risk

    def _result(price, reason, hold):
        # 不变量:剩余仓位必须始终落在 [0, 1]。一旦为负,后续 `remaining * _pnl()`
        # 会变成反向仓位,把趋势赢家记成亏损单(2026-10-19 修复的 Q3 减半缺陷)。
        assert -1e-9 <= remaining <= 1.0 + 1e-9, f"remaining out of range: {remaining}"
        return {
            "R": realized + remaining * _pnl(price) - cost_r_value,
            "gross_R": realized + remaining * _pnl(price),
            "ambiguous": False,
            "bars": hold,
            "reason": reason,
            "entry_price": entry,
            "stop_price": stop,
            "mfe_r": mfe,
        }

    for j in range(start, last + 1):
        ts_j = order[j]
        _o, high, low, close = bars[(sym, ts_j)]
        hold = j - start + 1
        best = high if sign > 0 else low
        mfe = max(mfe, _pnl(best))

        # 1) 已 TP 后更新止损(线上 _apply_post_tp_stop,发生在止损检查之前)
        if consumed >= 1:
            if post_tp_mode == "trend_capture" and mfe >= TREND_TRIGGER_R:
                trailed = best - sign * risk * TRAILING_R_MULT
                stop = max(stop, trailed) if sign > 0 else min(stop, trailed)
            else:
                stop = breakeven

        # 2) 止损最高优先级
        if (low <= stop) if sign > 0 else (high >= stop):
            return _result(stop, "INITIAL_STOP_HIT" if consumed == 0 else "BREAKEVEN_STOP_HIT", hold)

        # 3) 象限防御(线上要求 experiment_id 非空)
        if quad_map is not None and (quadrant_defense or q2_tighten):
            quad = quad_map.get((sym, ts_j))
            if q2_tighten and quad == "Q2":
                stop = max(stop, breakeven) if sign > 0 else min(stop, breakeven)
            q4_streak = q4_streak + 1 if quad == "Q4" else 0
            if quadrant_defense:
                if not q3_done and quad == "Q3":
                    realized += remaining * 0.5 * _pnl(close)
                    remaining *= 0.5
                    q3_done = True
                    continue
                if q4_streak >= 2 and (realized + remaining * _pnl(close) - cost_r_value) < 0:
                    return _result(close, "Q4_DEFENSIVE_EXIT", hold)

        # 4) TP 阶梯,每根最多一档
        if consumed < len(levels) and remaining > 1e-12:
            level_px = levels[consumed]
            if (high >= level_px) if sign > 0 else (low <= level_px):
                # 必须 clamp 到剩余仓位:Q3 减半后 remaining 只剩 0.5,
                # 若仍按原始 40/35/25% 扣减会变成负仓位,把趋势赢家记成反向仓
                # (线上 `paper_trading.py:322` 用的就是 min(remaining, tp_fraction))。
                fraction = min(remaining, fractions[consumed])
                realized += fraction * c.tp_levels[consumed]
                remaining -= fraction
                consumed += 1
                if consumed == 1:
                    stop = breakeven

        # 5) 成本保本超时
        if breakeven_bars is not None and hold >= breakeven_bars and consumed == 0:
            if _pnl(close) < COST_BREAKEVEN_BUFFER_MULT * cost_r_value:
                return _result(close, "COST_BREAKEVEN_TIMEOUT", hold)

        # 6) 最大持仓
        if hold >= h:
            return _result(close, "MAX_HOLD", hold)

    return _result(bars[(sym, order[last])][3], "MAX_HOLD", last - start + 1)


# --------------------------------------------------------------------------- #
# 批量标注
# --------------------------------------------------------------------------- #

def run_labeling(decisions, exit_mode="barrier", stop_floor=None, stop_scale=None,
                 entry_mode="next_open", quadrant_defense=False, q2_tighten=False,
                 post_tp_mode="legacy", *, cfg: LabelConfig | None = None,
                 horizon: int | None = None, cost_breakeven_bars: int | None = None
                 ) -> tuple[list[dict], Bars, PerSymbol, Index, dict | None]:
    """批量标注。返回 ``(labeled, bars, per_symbol, index, quad_map)``。

    每行 = 决策原字段 + 旧标注字段 + ``gross_R / entry_ts / exit_ts /
    hold_seconds / horizon``。``quad_map`` 仅在启用象限相关开关时非 None。
    """
    cfg_given = cfg is not None
    c = _cfg(cfg)
    h = _resolve_horizon(horizon, c)
    exit_mode = _pick(exit_mode, _LEGACY_EXIT_MODE, c.exit_mode, cfg_given)
    entry_mode = _pick(entry_mode, _LEGACY_ENTRY_BARRIER, c.entry_mode, cfg_given)
    quadrant_defense = _pick(quadrant_defense, _LEGACY_FLAG, c.quadrant_defense, cfg_given)
    q2_tighten = _pick(q2_tighten, _LEGACY_FLAG, c.q2_tighten, cfg_given)
    post_tp_mode = _pick(post_tp_mode, _LEGACY_POST_TP, c.post_tp_mode, cfg_given)
    stop_floor = _pick(stop_floor, None, c.stop_floor, cfg_given)
    stop_scale = _pick(stop_scale, None, c.stop_scale, cfg_given)

    # 把合并结果写回 cfg:h 决定成本保本根数(horizon//4),必须一起带下去,
    # 否则显式 horizon 与 cfg.horizon_bars 不一致时「成本超时」会用错阈值。
    ecfg = c.replaced(
        horizon_bars=h,
        exit_mode=exit_mode,
        entry_mode=entry_mode,
        post_tp_mode=post_tp_mode,
        quadrant_defense=bool(quadrant_defense),
        q2_tighten=bool(q2_tighten),
        stop_floor=stop_floor,
        stop_scale=stop_scale,
    )

    bars, per_symbol, index = build_bars(decisions)
    quad_map = build_quadrant_map(decisions) if (quadrant_defense or q2_tighten) else None
    ladder = exit_mode == "ladder"
    labeled = []
    for d in decisions:
        stop_eff = resolve_stop(d.get("stop_pct"), d.get("atr_pct"), cfg=ecfg)
        if ladder:
            res = label_ladder(bars, per_symbol, index, d, stop_eff, entry_mode,
                               quad_map=quad_map, quadrant_defense=quadrant_defense,
                               q2_tighten=q2_tighten, post_tp_mode=post_tp_mode,
                               horizon=h, cost_breakeven_bars=cost_breakeven_bars, cfg=ecfg)
        else:
            res = label_barrier(bars, per_symbol, index, d, stop_eff, entry_mode,
                                cfg=ecfg, horizon=h)
        if res is None:
            continue
        cost_r_value = cost_r(ecfg.cost_bps, stop_eff)
        row = dict(d)
        row.update(res)
        row["stop_pct_eff"] = stop_eff
        row["cost_r"] = cost_r_value
        if ladder:
            # ladder 的 res["R"] 已扣成本,拆回 gross / net 两列,与 barrier 口径一致
            row["R"] = res.get("gross_R", res["R"])
            row["R_net"] = res["R"]
        else:
            row["gross_R"] = res["R"]
            row["R_net"] = res["R"] - cost_r_value
        row["date"] = datetime.fromtimestamp(d["ts"], tz=timezone.utc).strftime("%Y-%m-%d")
        row["month"] = row["date"][:7]
        row["block"] = f'{d["symbol"]}|{row["date"]}'
        row["horizon"] = h
        entry_ts, exit_ts = _entry_exit_ts(index, per_symbol, d, entry_mode, res["bars"])
        if entry_ts is not None:
            row["entry_ts"] = entry_ts
            row["exit_ts"] = exit_ts
            row["hold_seconds"] = exit_ts - entry_ts
        labeled.append(row)
    return labeled, bars, per_symbol, index, quad_map


def _entry_exit_ts(index, per_symbol, d, entry_mode: str, bars_held: int):
    """入场/结算 bar 的时间戳。``bars_held`` 即标注结果的 ``bars`` 字段。"""
    sym, ts = d["symbol"], d["ts"]
    i = index.get(sym, {}).get(ts)
    order = per_symbol.get(sym) or []
    if i is None:
        return None, None
    start = i + 1 if entry_mode == "bar_close" else i + 2
    pos_in, pos_out = start - 1, start + bars_held - 1
    if pos_in < 0 or pos_out >= len(order):
        return None, None
    return order[pos_in], order[pos_out]


# --------------------------------------------------------------------------- #
# 面板体检与超时画像
# --------------------------------------------------------------------------- #

def grid_audit(decisions) -> dict:
    """决策日志的时间栅格体检:重复键、bar 间隔直方图、每日 bar 数、截面宽度。"""
    n = len(decisions)
    keys = [(d["symbol"], d["ts"]) for d in decisions]
    dup = n - len(set(keys))

    bars, per_symbol, _index = build_bars(decisions)

    gap_hist: Counter[int] = Counter()
    for tss in per_symbol.values():
        for a, b in zip(tss, tss[1:]):
            gap_hist[int(b - a)] += 1

    per_day: Counter[str] = Counter(
        datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d") for _sym, ts in bars
    )
    cs: Counter[int] = Counter(ts for _sym, ts in bars)
    sizes = sorted(cs.values())
    cs_size = {
        "min": sizes[0] if sizes else None,
        "median": statistics.median(sizes) if sizes else None,
        "max": sizes[-1] if sizes else None,
    }
    return {
        "n_decisions": n,
        "dup_symbol_ts": dup,
        "bar_gap_hist": {k: gap_hist[k] for k in sorted(gap_hist)},
        "bars_per_day": {k: per_day[k] for k in sorted(per_day)},
        "cs_size": cs_size,
        "n_ts": len(cs),
        "n_ts_ge_8": sum(1 for v in cs.values() if v >= 8),
    }


_SCORE_BUCKETS = (
    (">=92", lambda s: s >= 92),
    ("82-92", lambda s: 82 <= s < 92),
    ("78-82", lambda s: 78 <= s < 82),
    ("68-78", lambda s: 68 <= s < 78),
    ("<68", lambda s: s < 68),
)
_STOP_BUCKETS = (
    ("<0.005", lambda s: s < 0.005),
    ("0.005-0.0075", lambda s: 0.005 <= s < 0.0075),
    ("0.0075-0.01", lambda s: 0.0075 <= s < 0.01),
    ("0.01-0.02", lambda s: 0.01 <= s < 0.02),
    (">=0.02", lambda s: s >= 0.02),
)


def _is_timeout(row: dict) -> bool:
    return row.get("reason") in _TIMEOUT_REASONS


def _timeout_stats(rows: list[dict]) -> dict:
    n = len(rows)
    timeouts = [r for r in rows if _is_timeout(r)]
    others = [r for r in rows if not _is_timeout(r)]
    tout_r = [r["R_net"] for r in timeouts]
    other_r = [r["R_net"] for r in others]
    tout_g = [r["R"] for r in timeouts]
    other_g = [r["R"] for r in others]
    return {
        "n": n,
        "timeout_n": len(timeouts),
        "timeout_pct": (len(timeouts) / n) if n else None,
        "timeout_R_p50": statistics.median(tout_r) if tout_r else None,
        "E_R_excl_timeout": statistics.fmean(other_r) if other_r else None,
        # 毛口径:与报告里的 E[R] 同量级,避免把净 R 误读成毛边际
        "timeout_R_p50_gross": statistics.median(tout_g) if tout_g else None,
        "E_R_excl_timeout_gross": statistics.fmean(other_g) if other_g else None,
        "E_R_timeout_gross": statistics.fmean(tout_g) if tout_g else None,
    }


def timeout_profile(labeled) -> dict:
    """超时单画像:按分数档 / 止损宽度档 / 方向分组,看超时占比与「剔除超时后的 E[R]」。

    R 列有两种口径:不带 ``_gross`` 后缀的(``timeout_R_p50`` /
    ``E_R_excl_timeout``)是净口径(``R_net``),带 ``_gross`` 后缀的
    (``timeout_R_p50_gross`` / ``E_R_excl_timeout_gross`` /
    ``E_R_timeout_gross``)是毛口径(``R``)。
    超时口径含 barrier 的 ``TIMEOUT`` 与 ladder 的 ``COST_BREAKEVEN_TIMEOUT`` /
    ``MAX_HOLD``。
    """
    rows = list(labeled)

    def _bucketed(defs, getter, na_key: str) -> dict:
        out = {}
        for name, pred in defs:
            sel = [r for r in rows if (v := getter(r)) is not None and pred(float(v))]
            if sel:
                out[name] = _timeout_stats(sel)
        na = [r for r in rows if getter(r) is None]
        if na:
            out[na_key] = _timeout_stats(na)
        return out

    by_side = {}
    for side in sorted({r.get("side") for r in rows if r.get("side")}):
        sel = [r for r in rows if r.get("side") == side]
        if sel:
            by_side[side] = _timeout_stats(sel)

    return {
        "by_score": _bucketed(_SCORE_BUCKETS, lambda r: r.get("score"), "score_na"),
        "by_stop": _bucketed(_STOP_BUCKETS, lambda r: r.get("stop_pct_eff"), "stop_na"),
        "by_side": by_side,
        "overall": _timeout_stats(rows),
    }
