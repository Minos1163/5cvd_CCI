"""前向标签检验:用决策日志内嵌的 15m K 线,判断入场分数有没有信息量。

不依赖外部行情:decisions.jsonl 每行都带该时刻的 15m OHLC,实测单标的单日覆盖 96/96。

标注口径(默认 barrier 模式,与系统出场逻辑无关,避免循环论证):
  entry = 决策时间之后第一根 15m 的开盘价
  R     = 该决策的 entry_context.stop_pct
  label = 三重障碍,up=+1R / down=-1R,horizon=32 根(8 小时)
          同一根 K 线同时触及两侧 → 按最不利一侧,并单独计数
  R_net = label_R - round_trip_bps / (stop_pct * 10000)

扩展(2026-10-19,stop_pct 下限影子实验 + 入场条件扫描共用):
  --exit-mode ladder  逐条复刻线上出场(src/observability/paper_trading.py:229-293)
  --stop-floor / --stop-scale  止损宽度场景
  --entry-price bar_close 与线上一致(entry=决策当根 close),next_open 为原口径
  --quadrant-defense  Q3 减半 / Q4 防御全平(线上仅在 experiment_id 非空时生效)
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

# 冻结自 539bc64:scripts/analysis/fwd_label_20261019.py,作为 fwdlib 迁移的
# 独立对照实现。它只 import 标准库,可被 importlib 直接 exec。
# 逻辑一行未改 —— 不要在这里打补丁,否则 parity 测试就失去意义。
__test__ = False

FEE_BPS = 5.0
SLIPPAGE_BPS = 5.0
ROUND_TRIP_BPS = 2.0 * (FEE_BPS + SLIPPAGE_BPS)
HORIZON_BARS = 32
BAR_SECONDS = 900

# 线上出场常量,与 src/observability/paper_trading.py:16-22 逐项对齐
MIN_STOP_PCT = 0.005
MAX_STOP_PCT = 0.03
ATR_STOP_MULT = 1.5
MAX_HOLD_BARS = 32
COST_BREAKEVEN_CHECK_BARS = 8
COST_BREAKEVEN_BUFFER_MULT = 0.5
TP_LEVELS = (1.2, 2.0, 3.0)
TP_FRACTIONS = (0.40, 0.35, 0.25)
POST_TP_STOP_OFFSET = 0.001

# 六因子线上权重 profile(2026-06-26 起);此前是十因子旧架构,语义不同须排除
SIX_FACTOR_WEIGHTS = {
    "cci_momentum_quality": 14.0,
    "fibonacci_location": 18.0,
    "flow_cvd_confirmation": 18.0,
    "price_action_structure": 22.0,
    "risk_reward_geometry": 8.0,
    "trend_ema_context": 20.0,
}

FEATURE_KEYS = (
    "trend_ema_context",
    "ema_50_quality",
    "ema_momentum",
    "ema_200_gate",
    "direction_1h",
    "background_4h",
    "quality_30m",
    "trigger_15m",
    "market_regime",
    "volatility_stop",
    "liquidity_execution",
    "cvd_flow",
    "fib_action_cap",
    "fibonacci_location",
    "price_action_structure",
    "flow_cvd_confirmation",
    "cci_momentum_quality",
    "risk_reward_geometry",
)


def _is_six_factor(weights) -> bool:
    if not isinstance(weights, dict):
        return False
    if len(weights) != len(SIX_FACTOR_WEIGHTS):
        return False
    return all(abs(float(weights.get(k, -1.0)) - v) < 1e-6 for k, v in SIX_FACTOR_WEIGHTS.items())


def _extract_features(r: dict, ec: dict, sd: dict, atr_pct: float, ts: int) -> dict:
    scores = sd.get("scores") or {}
    points = r.get("component_points") or {}
    v2 = (r.get("component_points_v2") or {}).get("normalized_values") or {}
    kline = r.get("kline") or {}
    open_px = kline.get("open")
    high = kline.get("high")
    low = kline.get("low")
    close = kline.get("close")
    bar_pos = None
    if open_px and high and low and close and high > low:
        bar_pos = (close - low) / (high - low)
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    feat = {
        "score_pct": (sd.get("total_score") or 0.0) / 100.0,
        "shadow_pct": ((r.get("component_points_v2_meta") or {}).get("shadow_total") or 0.0) / 100.0,
        "atr_pct": atr_pct,
        "log_qv": math.log10(max(1.0, float(ec.get("quote_volume_24h") or 1.0))),
        "extreme_pos": float(ec.get("extreme_position_ratio") or 0.0),
        "symbol_exposure": float(ec.get("symbol_exposure_pct") or 0.0),
        "total_exposure": float(ec.get("total_exposure_pct") or 0.0),
        "daily_profit": float(ec.get("daily_profit_pct") or 0.0),
        "vol_scale": float(ec.get("current_volatility_scale") or 0.0),
        "btc_daily": float((r.get("market_snapshot") or {}).get("btc_daily_return") or 0.0),
        "btc_weekly": float((r.get("market_snapshot") or {}).get("btc_weekly_return") or 0.0),
        "bar_pos": bar_pos if bar_pos is not None else 0.5,
        "hour": dt.hour,
        "weekday": dt.weekday(),
    }
    for k in FEATURE_KEYS:
        if k in scores:
            feat[k] = float(scores.get(k) or 0.0)
        elif k in points:
            feat[k] = float(points.get(k) or 0.0) / 100.0
        elif k in v2:
            feat[k] = float(v2.get(k) or 0.0)
        else:
            feat[k] = float("nan")
    return feat


def load_decisions(paths: list[str], profile: str = "any"):
    """去重后返回候选决策。side 取 entry_context.side(方向候选),不是 decision.side。"""
    seen = set()
    out = []
    for p in paths:
        with open(p, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                kline = r.get("kline") or {}
                ts = kline.get("timestamp")
                sym = r.get("symbol")
                if ts is None or not sym:
                    continue
                ec = r.get("entry_context") or {}
                side = (ec.get("side") or "").upper()
                if side not in {"LONG", "SHORT"}:
                    continue
                if profile == "six_factor" and not _is_six_factor(r.get("weights")):
                    continue
                key = (sym, int(ts))
                if key in seen:
                    continue
                seen.add(key)
                sd = r.get("score_detail") or {}
                meta = r.get("component_points_v2_meta") or {}
                atr_pct = float(ec.get("atr_pct") or 0.0)
                out.append(
                    {
                        "symbol": sym,
                        "ts": int(ts),
                        "side": side,
                        "score": sd.get("total_score"),
                        "shadow": meta.get("shadow_total"),
                        "stop_pct": ec.get("stop_pct"),
                        "quadrant": r.get("quadrant"),
                        "action": r.get("action"),
                        "risk_allowed": bool(r.get("risk_allowed")),
                        "open": kline.get("open"),
                        "high": kline.get("high"),
                        "low": kline.get("low"),
                        "close": kline.get("close"),
                        "atr_pct": atr_pct,
                        "reasons": r.get("reasons") or [],
                        "feat": _extract_features(r, ec, sd, atr_pct, int(ts)),
                    }
                )
    return out


def build_bars(decisions):
    bars = {}
    for d in decisions:
        if d["open"] is None:
            continue
        bars[(d["symbol"], d["ts"])] = (d["open"], d["high"], d["low"], d["close"])
    per_symbol = defaultdict(list)
    for sym, ts in bars:
        per_symbol[sym].append(ts)
    index = defaultdict(dict)
    for sym in per_symbol:
        per_symbol[sym].sort()
        for i, ts in enumerate(per_symbol[sym]):
            index[sym][ts] = i
    return bars, per_symbol, index


def build_quadrant_map(decisions):
    return {(d["symbol"], d["ts"]): d["quadrant"] for d in decisions if d.get("quadrant")}


def _entry_and_start(bars, per_symbol, index, d, entry_mode, horizon):
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


def label_barrier(bars, per_symbol, index, d, stop_pct, entry_mode="next_open", horizon=HORIZON_BARS):
    base = _entry_and_start(bars, per_symbol, index, d, entry_mode, horizon)
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


TREND_TRIGGER_R = 1.5
TRAILING_R_MULT = 1.0


def label_ladder(
    bars,
    per_symbol,
    index,
    d,
    stop_pct,
    entry_mode="bar_close",
    quad_map=None,
    quadrant_defense=False,
    q2_tighten=False,
    post_tp_mode="legacy",
    horizon=HORIZON_BARS,
    cost_breakeven_bars=None,
):
    """逐条复刻线上出场:TP 1.2/2.0/3.0R 分批 40/35/25%、同 bar 止损优先、
    每根最多成交一档、TP1 后止损移到成本 ±0.1%(trend_capture 下按 1R 追踪)、
    第 8 根成本保本超时、第 32 根 close 平仓;可选 Q2 收紧 / Q3 减半 / Q4 全平。

    `cost_breakeven_bars`: 成本超时的检查根数。默认 None ⇒ 用模块常量 8(15m 口径)。
    换周期时必须按 `horizon // 4` 传入, 否则 1h + horizon=8 会让
    「第 8 根成本超时」与「第 8 根最大持仓」退化成同一条件。
    """
    base = _entry_and_start(bars, per_symbol, index, d, entry_mode, horizon)
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
    breakeven = entry * (1.001 if sign > 0 else 0.999)
    levels = [entry + sign * risk * lv for lv in TP_LEVELS]
    cost_r = (ROUND_TRIP_BPS / 10000.0) / stop_pct
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
            "R": realized + remaining * _pnl(price) - cost_r,
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
                if q4_streak >= 2 and (realized + remaining * _pnl(close) - cost_r) < 0:
                    return _result(close, "Q4_DEFENSIVE_EXIT", hold)

        # 4) TP 阶梯,每根最多一档
        if consumed < len(levels) and remaining > 1e-12:
            level_px = levels[consumed]
            if (high >= level_px) if sign > 0 else (low <= level_px):
                # 必须 clamp 到剩余仓位:Q3 减半后 remaining 只剩 0.5,
                # 若仍按原始 40/35/25% 扣减会变成负仓位,把趋势赢家记成反向仓
                # (线上 `paper_trading.py:322` 用的就是 min(remaining, tp_fraction))。
                fraction = min(remaining, TP_FRACTIONS[consumed])
                realized += fraction * TP_LEVELS[consumed]
                remaining -= fraction
                consumed += 1
                if consumed == 1:
                    stop = breakeven

        # 5) 成本保本超时
        if hold >= (cost_breakeven_bars or COST_BREAKEVEN_CHECK_BARS) and consumed == 0:
            if _pnl(close) < COST_BREAKEVEN_BUFFER_MULT * cost_r:
                return _result(close, "COST_BREAKEVEN_TIMEOUT", hold)

        # 6) 最大持仓
        if hold >= horizon:
            return _result(close, "MAX_HOLD", hold)

    return _result(bars[(sym, order[last])][3], "MAX_HOLD", last - start + 1)


def resolve_stop(raw_stop, atr_pct, stop_floor, stop_scale):
    """还原线上止损:先 clamp(atr*1.5, 0.005, 0.03),再套场景(floor 只升不降 / scale 全量乘)。"""
    if raw_stop and raw_stop > 0:
        base = float(raw_stop)
    else:
        base = min(MAX_STOP_PCT, max(MIN_STOP_PCT, (atr_pct or 0.0) * ATR_STOP_MULT))
    if stop_floor:
        base = max(base, float(stop_floor))
    if stop_scale and stop_scale != 1.0:
        base = base * float(stop_scale)
    return base


def spearman(xs, ys):
    n = len(xs)
    if n < 3:
        return None

    def ranks(v):
        order = sorted(range(n), key=lambda i: v[i])
        r = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r

    rx, ry = ranks(xs), ranks(ys)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    dy = math.sqrt(sum((b - my) ** 2 for b in ry))
    if dx == 0 or dy == 0:
        return None
    return num / (dx * dy)


def block_bootstrap_mean(values_by_block, iters=2000, seed=7):
    """按 (symbol,date) 分块重采样,返回 80% 区间。"""
    blocks = [v for v in values_by_block.values() if v]
    if len(blocks) < 5:
        return None
    rng = random.Random(seed)
    means = []
    for _ in range(iters):
        pick = [blocks[rng.randrange(len(blocks))] for _ in blocks]
        flat = [x for b in pick for x in b]
        if flat:
            means.append(sum(flat) / len(flat))
    if not means:
        return None
    means.sort()
    return means[int(0.10 * len(means))], means[int(0.90 * len(means))]


def run_labeling(decisions, exit_mode="barrier", stop_floor=None, stop_scale=None,
                 entry_mode="next_open", quadrant_defense=False, q2_tighten=False,
                 post_tp_mode="legacy", horizon=HORIZON_BARS, cost_breakeven_bars=None):
    bars, per_symbol, index = build_bars(decisions)
    quad_map = build_quadrant_map(decisions) if (quadrant_defense or q2_tighten) else None
    fn = label_ladder if exit_mode == "ladder" else label_barrier
    labeled = []
    for d in decisions:
        stop_eff = resolve_stop(d.get("stop_pct"), d.get("atr_pct"), stop_floor, stop_scale)
        if exit_mode == "ladder":
            res = fn(bars, per_symbol, index, d, stop_eff, entry_mode,
                     quad_map=quad_map, quadrant_defense=quadrant_defense,
                     q2_tighten=q2_tighten, post_tp_mode=post_tp_mode, horizon=horizon,
                     cost_breakeven_bars=cost_breakeven_bars)
        else:
            res = fn(bars, per_symbol, index, d, stop_eff, entry_mode, horizon=horizon)
        if res is None:
            continue
        cost_r = (ROUND_TRIP_BPS / 10000.0) / stop_eff
        row = dict(d)
        row.update(res)
        row["stop_pct_eff"] = stop_eff
        row["cost_r"] = cost_r
        if exit_mode == "ladder":
            # ladder 的 res["R"] 已扣成本,拆回 gross / net 两列,与 barrier 口径一致
            row["R"] = res.get("gross_R", res["R"])
            row["R_net"] = res["R"]
        else:
            row["R_net"] = res["R"] - cost_r
        row["date"] = datetime.fromtimestamp(d["ts"], tz=timezone.utc).strftime("%Y-%m-%d")
        row["month"] = row["date"][:7]
        row["block"] = f'{d["symbol"]}|{row["date"]}'
        labeled.append(row)
    return labeled, bars, per_symbol, index, quad_map


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--logs", default="logs")
    ap.add_argument("--out", default="reports/analysis/fwd-label-20261019")
    ap.add_argument("--months", default="2026-09,2026-10", help="逗号分隔的月份目录")
    ap.add_argument("--profile", default="any", choices=["any", "six_factor"])
    ap.add_argument("--exit-mode", default="barrier", choices=["barrier", "ladder"])
    ap.add_argument("--entry-price", default=None, choices=["next_open", "bar_close"])
    ap.add_argument("--stop-floor", type=float, default=None)
    ap.add_argument("--stop-scale", type=float, default=None)
    ap.add_argument("--quadrant-defense", action="store_true")
    ap.add_argument("--q2-tighten", action="store_true")
    ap.add_argument("--post-tp-mode", default="legacy", choices=["legacy", "trend_capture"])
    args = ap.parse_args()

    months = [m.strip() for m in args.months.split(",") if m.strip()]
    paths = []
    for m in months:
        paths += sorted(Path(args.logs).glob(f"{m}/*/decisions.jsonl"))
    decisions = load_decisions([str(p) for p in paths], profile=args.profile)
    entry_mode = args.entry_price or ("bar_close" if args.exit_mode == "ladder" else "next_open")
    labeled, _, _, _, _ = run_labeling(
        decisions, exit_mode=args.exit_mode, stop_floor=args.stop_floor,
        stop_scale=args.stop_scale, entry_mode=entry_mode,
        quadrant_defense=args.quadrant_defense, q2_tighten=args.q2_tighten,
        post_tp_mode=args.post_tp_mode,
    )
    if not labeled:
        raise SystemExit("no labeled rows")
    span = (min(d["ts"] for d in labeled), max(d["ts"] for d in labeled))
    fmt = lambda t: datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
    print(f"decisions={len(decisions)} labeled={len(labeled)} span={fmt(span[0])} .. {fmt(span[1])}")
    amb = sum(1 for d in labeled if d["ambiguous"])
    print(f"ambiguous={amb} ({amb/len(labeled)*100:.2f}%)")

    def stats(rows):
        if not rows:
            return None
        R = [d["R"] for d in rows]
        Rn = [d["R_net"] for d in rows]
        return {
            "n": len(rows),
            "hit": round(sum(1 for x in R if x > 0) / len(R), 4),
            "E_R": round(statistics.fmean(R), 4),
            "E_Rnet": round(statistics.fmean(Rn), 4),
            "cost_R": round(statistics.fmean([d["cost_r"] for d in rows]), 4),
        }

    overall = stats(labeled)
    buckets_def = [
        ("score>=92", lambda d: d["score"] is not None and d["score"] >= 92),
        ("score 82-92", lambda d: d["score"] is not None and 82 <= d["score"] < 92),
        ("score 78-82", lambda d: d["score"] is not None and 78 <= d["score"] < 82),
        ("score 68-78", lambda d: d["score"] is not None and 68 <= d["score"] < 78),
        ("score<68", lambda d: d["score"] is not None and d["score"] < 68),
    ]
    bucket_rows = []
    for name, pred in buckets_def:
        rows = [d for d in labeled if pred(d)]
        s = stats(rows)
        if s:
            bucket_rows.append({"bucket": name, **s})

    shadow_rows = [d for d in labeled if d["shadow"] is not None]
    s_buckets = []
    if len(shadow_rows) >= 200:
        vals = sorted(d["shadow"] for d in shadow_rows)
        cuts = [vals[int(len(vals) * q)] for q in (0.2, 0.4, 0.6, 0.8)]
        names = ["Q1(最低)", "Q2", "Q3", "Q4", "Q5(最高)"]
        for i, lab in enumerate(names):
            lo = cuts[i - 1] if i > 0 else -1e9
            hi = cuts[i] if i < len(cuts) else 1e9
            rows = [d for d in shadow_rows if lo <= d["shadow"] < hi]
            s = stats(rows)
            if s:
                s_buckets.append({"bucket": lab, **s})

    def daily_ic(field):
        ics = []
        for _date, rows in _group(labeled, lambda d: d["date"]).items():
            rows = [d for d in rows if d.get(field) is not None]
            if len(rows) < 20:
                continue
            v = spearman([d[field] for d in rows], [d["R_net"] for d in rows])
            if v is not None:
                ics.append(v)
        if not ics:
            return None
        return {"days": len(ics), "mean_ic": round(statistics.fmean(ics), 4),
                "positive_days": sum(1 for x in ics if x > 0)}

    ci = block_bootstrap_mean({k: [x["R_net"] for x in v] for k, v in _group(labeled, lambda d: d["block"]).items()})
    result = {
        "window": [fmt(span[0]), fmt(span[1])],
        "decisions_total": len(decisions),
        "labeled": len(labeled),
        "ambiguous_pct": round(amb / len(labeled) * 100, 2),
        "round_trip_bps": ROUND_TRIP_BPS,
        "horizon_bars": HORIZON_BARS,
        "exit_mode": args.exit_mode,
        "entry_price_mode": entry_mode,
        "stop_floor": args.stop_floor,
        "stop_scale": args.stop_scale,
        "quadrant_defense": bool(args.quadrant_defense),
        "overall": overall,
        "E_Rnet_ci80": None if ci is None else [round(ci[0], 4), round(ci[1], 4)],
        "score_buckets": bucket_rows,
        "shadow_quintiles": s_buckets,
        "ic_six_factor": daily_ic("score"),
        "ic_five_factor": daily_ic("shadow"),
        "by_side": {k: stats(v) for k, v in _group(labeled, lambda d: d["side"]).items()},
        "by_quadrant": {str(k): stats(v) for k, v in _group(labeled, lambda d: d["quadrant"]).items()},
        "by_reason": {k: stats(v) for k, v in _group(labeled, lambda d: d["reason"]).items()},
        "by_month": {k: stats(v) for k, v in _group(labeled, lambda d: d["month"]).items()},
    }

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "metrics.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    cols = ("symbol", "ts", "side", "score", "shadow", "stop_pct", "stop_pct_eff", "quadrant",
            "R", "R_net", "cost_r", "ambiguous", "entry_price", "stop_price", "bars", "reason", "mfe_r")
    (out / "labels.jsonl").write_text(
        "\n".join(json.dumps({k: d.get(k) for k in cols}, ensure_ascii=False) for d in labeled),
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


def _group(rows, keyfn):
    g = defaultdict(list)
    for r in rows:
        g[keyfn(r)].append(r)
    return g


if __name__ == "__main__":
    main()
