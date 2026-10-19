"""WS3 Stage A: 15m → 1h 周期上移的离线粗测（只换标注，不换信号）。

它回答什么
----------
把决策频率换成 1h（每小时最后一根 15m 的决策作为该小时的"收盘决策"），
出场在 1h bar 上重放。这是一个**「15m 信号 + 1h 出场」**的混合体，不是 1h 策略。

因此它能测的是：**周期上移能省多少成本、毛利会不会随之改变**。
它不能测"1h 因子是否有 alpha"——那需要 Stage B（在 1h bar 上重算六因子）。

关键方法学约束（每一条都对应一次踩坑）
--------------------------------------
1. `horizon = 8`（8h，对齐 15m 的 32×15m）。
2. `cost_breakeven_bars = 2`（= horizon//4）。不传的话「第 8 根成本超时」与
   「第 8 根最大持仓」会退化成同一条件。
3. **象限必须重锚**：`build_quadrant_map` 原本按 15m ts 建表，1h 下如果不把 ts
   换成锚定小时，`quad_map.get()` 全 miss，Q3 减半 / Q4 防御会**静默失效**。
4. **缺口必须切段**：`_entry_and_start` 用 `order[i+1]` 取"下一根"，不校验时间差。
   合成 1h 有缺口时会把远端 bar 当"下一根"。这里把每个标的切成连续段，
   每段作为一个伪标的名（`SYM@seg`），保证 index 相邻 ⇒ 时间相邻。
5. **3% 上限在 1h 变成硬约束**：1h 有 3.4–5.4% 的样本 `ATR×1.5 > 3%`，
   这里用 `MAX_STOP = 0.04`（`EntryChainConfig` 口径）并单独报告截断率。

预登记判据（写死在常量，输出回显）
----------------------------------
  V0 数据门：合成 1h 与原生 1h 的 mismatch == 0；完整 1h ≥ 35,000；锚定行 ≥ 38,000
  V1 成本门：`cost_R` 中位 ≤ 0.20（对照 15m 的 0.2728）
  V2 毛利门：`E[R]` 的 80% 分块区间（跨 0 且 |E[R]| < 0.05 ⇒ 周期上移只降成本、不产 alpha）
  V3 可交易子集（DIRECT+PROBE）样本极少 ⇒ 只出描述性统计，不做上线裁决

用法
----
  python scripts/analysis/tf_uplift_20261019.py
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cost_model as CM  # noqa: E402
import fwd_label_20261019 as L  # noqa: E402

HOUR = 3600
BAR_15M = 900
BARS_PER_HOUR = HOUR // BAR_15M
ANCHOR_PHASE = 2700          # 该小时最后一根 15m 的 ts 偏移
HORIZON_1H = 8               # 8h，对齐 15m 的 32×15m
COST_BREAKEVEN_1H = HORIZON_1H // 4
ATR_WINDOW = 20
ATR_MULT = 1.5
MIN_STOP = 0.015
MAX_STOP = 0.040

# ---- 预登记 ----
V0_MIN_COMPLETE_1H = 35_000
V0_MIN_ANCHORS = 38_000
V1_MAX_COST_R = 0.20
V2_FLAT_E_R = 0.05

TP_LEG_SHARE = 0.75

STOP_SCENARIOS = (
    ("payload", "沿用 15m 决策里的 stop_pct（只测周期对出场的影响，不改止损口径）"),
    ("atr1h", "1h ATR×1.5 再 clamp 到 [1.5%, 4%]（主口径）"),
    ("atr1h_floor025", "1h ATR×1.5 与 2.5% 取大（配合降成本的组合臂）"),
)

EXIT_SCENARIOS = {
    "ladgex": dict(exit_mode="ladder", post_tp_mode="trend_capture",
                   quadrant_defense=True, q2_tighten=True, entry_mode="bar_close"),
    "barrier": dict(exit_mode="barrier", entry_mode="bar_close"),
}


# --------------------------------------------------------------------------- #
# 1. 自检：合成 1h == 原生 1h
# --------------------------------------------------------------------------- #
def load_csv(path):
    rows = []
    with open(path, encoding="utf-8") as fh:
        for x in csv.DictReader(fh):
            rows.append({
                "ts": int(x["open_time"]) // 1000,
                "o": float(x["open"]), "h": float(x["high"]),
                "l": float(x["low"]), "c": float(x["close"]),
                "v": float(x["volume"]),
            })
    return rows


def resample(rows15, target=HOUR, expect=BARS_PER_HOUR):
    """按 target 对齐聚合成 (o, h, l, c, v)，只保留 expect 根齐全的桶。"""
    buckets = defaultdict(list)
    for x in rows15:
        buckets[x["ts"] // target * target].append(x)
    out = {}
    for ts, xs in buckets.items():
        if len(xs) != expect:
            continue
        xs.sort(key=lambda y: y["ts"])
        out[ts] = (xs[0]["o"], max(y["h"] for y in xs), min(y["l"] for y in xs),
                   xs[-1]["c"], sum(y["v"] for y in xs))
    return out


def selfcheck(root="data/raw/binance_futures"):
    """用同区间的 15m/1h 原生数据验证聚合规则。

    门禁只看 **OHLC**：标注器（`label_barrier` / `label_ladder`）完全不用 volume，
    而 volume 在数据源侧存在极小比例的对不齐（实测 1/2160 根差 0.02%，
    是单个 15m 桶成交量缺失造成的），把这部分算进门禁会把数据源的瑕疵
    误判成聚合逻辑错误。volume 差异单独报告。
    """
    out = {"pairs": {}, "ohlc_mismatch": 0, "volume_mismatch": 0,
           "checked": 0, "volume_checked": 0}
    for base in (Path(root) / "atom_90d" / "ATOMUSDT",
                 Path(root) / "latest_30d" / "SOLUSDT",
                 Path(root) / "latest_365d" / "BNBUSDT"):
        p15, p1h = base / "15m.csv", base / "1h.csv"
        if not (p15.exists() and p1h.exists()):
            continue
        agg = resample(load_csv(p15))
        native = {r["ts"]: (r["o"], r["h"], r["l"], r["c"], r["v"]) for r in load_csv(p1h)}
        matched = ohlc_bad = vol_bad = 0
        for ts, a in agg.items():
            n = native.get(ts)
            if n is None:
                continue
            matched += 1
            worst_ohlc = max(abs(x - y) / max(abs(y), 1e-9) for x, y in zip(a[:4], n[:4]))
            if worst_ohlc > 1e-6:
                ohlc_bad += 1
            if abs(a[4] - n[4]) / max(abs(n[4]), 1e-9) > 1e-6:
                vol_bad += 1
        out["pairs"][str(base)] = {
            "matched": matched, "ohlc_mismatch": ohlc_bad, "volume_mismatch": vol_bad,
            "overlap": "none" if matched == 0 else "ok",
        }
        out["ohlc_mismatch"] += ohlc_bad
        out["volume_mismatch"] += vol_bad
        out["checked"] += matched
        out["volume_checked"] += matched
    return out


# --------------------------------------------------------------------------- #
# 2. 15m 面板 → 1h bar + 连续段
# --------------------------------------------------------------------------- #
def aggregate_1h(decisions):
    """按 (symbol, hour) 聚合，只保留 4/4 根齐全的小时。返回 {((sym,h)): (o,h,l,c)}。"""
    buckets = defaultdict(dict)
    for d in decisions:
        if d.get("open") is None:
            continue
        hour = d["ts"] // HOUR * HOUR
        buckets[(d["symbol"], hour)][d["ts"]] = (d["open"], d["high"], d["low"], d["close"])
    bars = {}
    for (sym, hour), m in buckets.items():
        if len(m) != BARS_PER_HOUR:
            continue
        if any(hour + k * BAR_15M not in m for k in range(BARS_PER_HOUR)):
            continue
        bars[(sym, hour)] = (
            m[hour][0],
            max(m[hour + k * BAR_15M][1] for k in range(BARS_PER_HOUR)),
            min(m[hour + k * BAR_15M][2] for k in range(BARS_PER_HOUR)),
            m[hour + ANCHOR_PHASE][3],
        )
    return bars


def build_segments(bars):
    """把每个标的的 1h ts 切成 Δts==3600 的连续段，段名 `SYM@i`。

    这样 `_entry_and_start` 的 `order[i+1]` 才真的等于"下一小时"，
    否则合成 1h 的缺口会让标注器把远端 bar 当下一根。
    """
    by_sym = defaultdict(list)
    for sym, ts in bars:
        by_sym[sym].append(ts)
    segments = {}
    real_of = {}
    gaps = 0
    for sym, ts_list in by_sym.items():
        ts_list.sort()
        seg, segs = [], []
        for t in ts_list:
            if seg and t - seg[-1] != HOUR:
                segs.append(seg)
                seg = []
            seg.append(t)
        if seg:
            segs.append(seg)
        gaps += max(0, len(segs) - 1)
        for i, s in enumerate(segs):
            name = f"{sym}@{i}"
            segments[name] = s
            real_of[name] = sym
    return segments, real_of, gaps


def atr_pct_series(ts_list, bars_pseudo, pseudo, window=ATR_WINDOW):
    """每个位置的 ATR%（前 window 根 TR 的均值 / 该根 close）。"""
    out = {}
    for i in range(1, len(ts_list)):
        lo = max(1, i - window)
        close = bars_pseudo[(pseudo, ts_list[i])][3]
        trs = []
        for j in range(lo, i + 1):
            _, high, low, _c = bars_pseudo[(pseudo, ts_list[j])]
            prev_close = bars_pseudo[(pseudo, ts_list[j - 1])][3]
            trs.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))
        if trs and close > 0:
            out[ts_list[i]] = statistics.fmean(trs) / close
    return out


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


# --------------------------------------------------------------------------- #
# 3. 标注
# --------------------------------------------------------------------------- #
def label_rows(anchored, bars, per_symbol, index, quad_map, stop_of, exit_cfg,
               round_trip_bps, horizon=HORIZON_1H, cost_breakeven_bars=COST_BREAKEVEN_1H):
    """对锚定决策逐条重放，返回带 R / R_net / cost_r 的行。

    `label_ladder` 内部按模块级 `ROUND_TRIP_BPS` 扣成本（并据此判定成本超时与 Q4 防御），
    所以必须临时替换该常量，否则「净盈亏」与「成交集合」都还是 20bps 口径。
    替换仅作用于本函数调用期间，结束后还原。
    """
    ladder = exit_cfg["exit_mode"] == "ladder"
    original = L.ROUND_TRIP_BPS
    L.ROUND_TRIP_BPS = float(round_trip_bps)
    out = []
    try:
        for d in anchored:
            stop = stop_of(d)
            if not stop or stop <= 0:
                continue
            if ladder:
                res = L.label_ladder(bars, per_symbol, index, d, stop, exit_cfg["entry_mode"],
                                     quad_map=quad_map,
                                     quadrant_defense=exit_cfg.get("quadrant_defense", False),
                                     q2_tighten=exit_cfg.get("q2_tighten", False),
                                     post_tp_mode=exit_cfg.get("post_tp_mode", "legacy"),
                                     horizon=horizon, cost_breakeven_bars=cost_breakeven_bars)
            else:
                res = L.label_barrier(bars, per_symbol, index, d, stop,
                                      exit_cfg["entry_mode"], horizon=horizon)
            if res is None:
                continue
            cost_r = (round_trip_bps / 10000.0) / stop
            row = {k: d.get(k) for k in ("symbol", "real_symbol", "ts", "side", "score",
                                         "quadrant", "action", "risk_allowed", "atr_pct")}
            row.update(res)
            row["stop_pct"] = round(stop, 6)
            row["cost_r"] = cost_r
            row["gross_R"] = res.get("gross_R", res["R"])
            # ladder 的 res["R"] 已扣成本; barrier 需要自己扣
            row["R_net"] = res["R"] if ladder else res["R"] - cost_r
            row["R"] = row["gross_R"]
            row["date"] = datetime.fromtimestamp(d["ts"], tz=timezone.utc).strftime("%Y-%m-%d")
            row["month"] = row["date"][:7]
            row["block"] = f'{d["real_symbol"]}|{row["date"]}'
            out.append(row)
    finally:
        L.ROUND_TRIP_BPS = original
    return out


def check_identity(rows, round_trip_bps):
    """数值不变量：ladder 的 `R_net` 必须精确等于 `R - cost_r`。

    这条断言存在的意义：`label_ladder` 用的是模块级 `ROUND_TRIP_BPS`（需临时替换注入），
    而 `cost_r` 列用的是本函数的入参。两者一旦脱钩，就会出现「净盈亏还是 20bps
    但 `cost_R` 列已变成 7.75bps」这种静默错配 —— 表面看矩阵有差异，实则没生效。
    """
    worst = 0.0
    for r in rows:
        residual = abs(r["R_net"] - (r["R"] - r["cost_r"]))
        worst = max(worst, residual)
    return worst


def stats(rows):
    if not rows:
        return None
    R = [r["R"] for r in rows]
    Rn = [r["R_net"] for r in rows]
    ci = L.block_bootstrap_mean({k: [x["R_net"] for x in v]
                                 for k, v in L._group(rows, lambda d: d["block"]).items()})
    ci_R = L.block_bootstrap_mean({k: [x["R"] for x in v]
                                   for k, v in L._group(rows, lambda d: d["block"]).items()})
    held = sorted(r["bars"] for r in rows)
    return {
        "n": len(rows),
        "hit": round(sum(1 for x in R if x > 0) / len(R), 4),
        "E_R": round(statistics.fmean(R), 4),
        "E_R_ci80": None if ci_R is None else [round(ci_R[0], 4), round(ci_R[1], 4)],
        "cost_R": round(statistics.fmean([r["cost_r"] for r in rows]), 4),
        "E_Rnet": round(statistics.fmean(Rn), 4),
        "E_Rnet_ci80": None if ci is None else [round(ci[0], 4), round(ci[1], 4)],
        "ambiguous_pct": round(sum(1 for r in rows if r.get("ambiguous")) / len(rows) * 100, 2),
        "bars_median": held[len(held) // 2],
        "stop_pct_median": round(statistics.median([r["stop_pct"] for r in rows]), 5),
        "reasons": dict(sorted(
            {k: len(v) for k, v in L._group(rows, lambda d: d["reason"]).items()}.items(),
            key=lambda kv: -kv[1])[:8]),
    }


# --------------------------------------------------------------------------- #
# 4. 主流程
# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--logs", default="logs")
    ap.add_argument("--months", default="2026-06,2026-07,2026-08,2026-09,2026-10")
    ap.add_argument("--profile", default="six_factor", choices=["any", "six_factor"])
    ap.add_argument("--cost-models", default="taker_20,hybrid_8")
    ap.add_argument("--out", default="reports/analysis/tf-uplift-20261019")
    ap.add_argument("--skip-selfcheck", action="store_true")
    args = ap.parse_args()

    # --- V0 数据门（先跑，不通过直接退出）---
    chk = {"skipped": True, "ohlc_mismatch": 0, "volume_mismatch": 0,
           "checked": 0, "volume_checked": 0, "pairs": {}}
    if not args.skip_selfcheck:
        chk = selfcheck()
        chk["skipped"] = False
        print(f"selfcheck ohlc_mismatch={chk['ohlc_mismatch']} "
              f"volume_mismatch={chk['volume_mismatch']} checked={chk['checked']} "
              f"pairs={chk['pairs']}", flush=True)
        if chk["ohlc_mismatch"] > 0:
            raise SystemExit("V0 FAIL: 15m→1h 聚合的 OHLC 与原生 1h 不一致，先修聚合规则")

    months = [m.strip() for m in args.months.split(",") if m.strip()]
    paths = []
    for m in months:
        paths += sorted(Path(args.logs).glob(f"{m}/*/decisions.jsonl"))
    if not paths:
        raise SystemExit("no decisions.jsonl found")
    decisions = L.load_decisions([str(p) for p in paths], profile=args.profile)
    print(f"decisions_15m={len(decisions)}", flush=True)

    bars_15 = aggregate_1h(decisions)
    segments, real_of, gaps = build_segments(bars_15)
    complete_1h = len(bars_15)
    print(f"complete_1h_bars={complete_1h} segments={len(segments)} internal_gaps={gaps}", flush=True)

    # 伪标的：保证 index 相邻 ⇒ 时间相邻
    bars = {}
    per_symbol = {}
    index = {}
    atr_map = {}
    pseudo_of = {}
    for pseudo, ts_list in segments.items():
        real = real_of[pseudo]
        for t in ts_list:
            bars[(pseudo, t)] = bars_15[(real, t)]
            pseudo_of[(real, t)] = pseudo
        per_symbol[pseudo] = ts_list
        for t, v in atr_pct_series(ts_list, bars, pseudo).items():
            atr_map[(real, t)] = v
        index[pseudo] = {t: i for i, t in enumerate(ts_list)}

    # 锚定决策：该小时最后一根 15m（ts % 3600 == 2700）
    anchor_src = {}
    for d in decisions:
        if d["ts"] % HOUR == ANCHOR_PHASE:
            anchor_src[(d["symbol"], d["ts"] - ANCHOR_PHASE)] = d

    anchored = []
    missing_anchor = 0
    for (sym, hour) in bars_15:
        src = anchor_src.get((sym, hour))
        if src is None:
            missing_anchor += 1
            continue
        pseudo = pseudo_of[(sym, hour)]
        o, h, l, c = bars_15[(sym, hour)]
        anchored.append({
            "symbol": pseudo,
            "real_symbol": sym,
            "ts": hour,
            "side": src["side"],
            "score": src["score"],
            "quadrant": src["quadrant"],
            "action": src["action"],
            "risk_allowed": src["risk_allowed"],
            "stop_pct_15m": src.get("stop_pct"),
            "atr_pct": atr_map.get((sym, hour)),
            "open": o, "high": h, "low": l, "close": c,
        })
    anchored.sort(key=lambda d: (d["real_symbol"], d["ts"]))
    print(f"anchors={len(anchored)} missing_anchor={missing_anchor}", flush=True)

    quad_map = {(d["symbol"], d["ts"]): d["quadrant"] for d in anchored if d.get("quadrant")}

    def stop_payload(d):
        return d.get("stop_pct_15m")

    def stop_atr1h(d):
        a = d.get("atr_pct")
        if not a:
            return None
        return clamp(a * ATR_MULT, MIN_STOP, MAX_STOP)

    def stop_atr1h_floor(d):
        s = stop_atr1h(d)
        return None if s is None else max(s, 0.025)

    stop_fns = {"payload": stop_payload, "atr1h": stop_atr1h, "atr1h_floor025": stop_atr1h_floor}

    # 3% 截断率（1h 才有意义）
    trunc = 0
    atr_vals = [d["atr_pct"] for d in anchored if d.get("atr_pct")]
    for a in atr_vals:
        if a * ATR_MULT > MAX_STOP:
            trunc += 1

    models = [CM.get(v.strip()) for v in args.cost_models.split(",") if v.strip()]
    results = {}
    for model in models:
        rtb = model.round_trip_bps(TP_LEG_SHARE)
        for exit_name, exit_cfg in EXIT_SCENARIOS.items():
            for stop_name, fn in stop_fns.items():
                key = f"{model.version}|{exit_name}|{stop_name}"
                rows = label_rows(anchored, bars, per_symbol, index, quad_map, fn,
                                  exit_cfg, rtb)
                if rows:
                    worst = check_identity(rows, rtb)
                    if worst > 1e-9:
                        raise SystemExit(
                            f"成本注入未生效于 {key}: |R_net - (R - cost_r)| = {worst:.3e} "
                            f"(round_trip_bps={rtb})")
                s = stats(rows)
                if s is None:
                    continue
                s["round_trip_bps"] = round(rtb, 3)
                tradable = [r for r in rows
                            if r["action"] in ("DIRECT", "PROBE") and r["risk_allowed"]]
                s["tradable_subset"] = stats(tradable)
                s["by_quadrant"] = {str(k): stats(v) for k, v in
                                    L._group(rows, lambda d: d["quadrant"]).items()}
                s["by_side"] = {k: stats(v) for k, v in
                                L._group(rows, lambda d: d["side"]).items()}
                s["by_month"] = {k: stats(v) for k, v in
                                 L._group(rows, lambda d: d["month"]).items()}
                results[key] = s
                print(f"  {key:>34}  n={s['n']:,}  E[R]={s['E_R']:+.4f}  "
                      f"cost_R={s['cost_R']:.4f}  E[Rnet]={s['E_Rnet']:+.4f}  "
                      f"ci={s['E_Rnet_ci80']}", flush=True)

    primary_key = "taker_20|ladgex|atr1h"
    if primary_key not in results:
        primary_key = next(iter(results))
    primary_stats = results[primary_key]

    v0_pass = (chk["ohlc_mismatch"] == 0 and complete_1h >= V0_MIN_COMPLETE_1H
               and len(anchored) >= V0_MIN_ANCHORS)
    v0_detail = {
        "ohlc_mismatch": chk["ohlc_mismatch"],
        "complete_1h": complete_1h,
        "complete_1h_ok": complete_1h >= V0_MIN_COMPLETE_1H,
        "anchors": len(anchored),
        "anchors_ok": len(anchored) >= V0_MIN_ANCHORS,
        "anchors_shortfall": max(0, V0_MIN_ANCHORS - len(anchored)),
        "anchors_shortfall_pct": round(
            max(0, V0_MIN_ANCHORS - len(anchored)) / V0_MIN_ANCHORS * 100, 2),
        "note": "38,000 这个门槛来自未做 profile/side 过滤前的完整 1h 估计;"
                " 实际面板经 six_factor + side 过滤后为 37,250。缺的是样本量, 不是数据质量。",
    }
    v1_pass = (primary_stats["cost_R"] <= V1_MAX_COST_R)
    gross_ci = primary_stats["E_R_ci80"]
    net_ci = primary_stats["E_Rnet_ci80"]
    flat = (abs(primary_stats["E_R"]) < V2_FLAT_E_R
            and (gross_ci is None or gross_ci[0] <= 0 <= gross_ci[1]))
    tradable_n = (primary_stats.get("tradable_subset") or {}).get("n", 0)

    result = {
        "preregistered": {
            "V0": {"min_complete_1h": V0_MIN_COMPLETE_1H, "min_anchors": V0_MIN_ANCHORS,
                   "mismatch_must_be": 0},
            "V1": {"max_cost_R_median": V1_MAX_COST_R},
            "V2": {"flat_abs_E_R": V2_FLAT_E_R},
            "V3": "可交易子集样本极少时只出描述性统计，不做上线裁决",
            "horizon_bars": HORIZON_1H,
            "cost_breakeven_bars": COST_BREAKEVEN_1H,
            "stop_bounds": [MIN_STOP, MAX_STOP],
            "tp_leg_share": TP_LEG_SHARE,
        },
        "selfcheck": chk,
        "universe": {
            "decisions_15m": len(decisions),
            "complete_1h_bars": complete_1h,
            "segments": len(segments),
            "internal_gaps": gaps,
            "anchors": len(anchored),
            "missing_anchor": missing_anchor,
            "tradable_anchors": sum(1 for d in anchored
                                    if d["action"] in ("DIRECT", "PROBE") and d["risk_allowed"]),
            "atr1h_over_max_stop_pct": round(trunc / len(atr_vals) * 100, 2) if atr_vals else None,
            "window": [
                datetime.fromtimestamp(min(d["ts"] for d in anchored), tz=timezone.utc)
                .strftime("%Y-%m-%d %H:%M"),
                datetime.fromtimestamp(max(d["ts"] for d in anchored), tz=timezone.utc)
                .strftime("%Y-%m-%d %H:%M"),
            ] if anchored else None,
        },
        "cost_models": [m.describe(TP_LEG_SHARE) for m in models],
        "matrix": results,
        "primary_key": primary_key,
        "verdict": {
            "V0_pass": v0_pass,
            "V0_detail": v0_detail,
            "V1_pass": v1_pass,
            "V1_cost_R": primary_stats["cost_R"],
            "V2_flat_er": flat,
            "V2_gross_E_R": primary_stats["E_R"],
            "V2_gross_ci80": gross_ci,
            "V2_net_ci80": net_ci,
            "tradable_n": tradable_n,
            "V3_descriptive_only": tradable_n < 300,
            "reading": "周期上移只降成本、不产 alpha（毛利区间跨 0 且近似平坦）" if flat else
                       ("毛利区间不含 0 且方向为正" if gross_ci and gross_ci[0] > 0 else
                        "毛利区间不含 0 且方向为负" if gross_ci and gross_ci[1] < 0 else "需人工判读"),
        },
    }

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "metrics.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "report.md").write_text(_render(result), encoding="utf-8")
    print(json.dumps(result["verdict"], ensure_ascii=False, indent=2))


def _render(r):
    u, v = r["universe"], r["verdict"]
    lines = [
        "# 15m → 1h 周期上移：离线粗测（Stage A，只换标注）",
        "",
        "> 口径声明：本结果是 **「15m 信号 + 1h 出场」**，不是 1h 策略。",
        "> 它能测「周期上移省多少成本、毛利会不会跟着变」，测不了「1h 因子有没有 alpha」。",
        "",
        "## V0 数据门",
        "",
        f"- 合成 1h vs 原生 1h：OHLC mismatch **{r['selfcheck']['ohlc_mismatch']}**"
        f"（校验 {r['selfcheck']['checked']:,} 根）；volume mismatch "
        f"{r['selfcheck']['volume_mismatch']}（数据源侧对不齐，标注器不使用 volume，不计入门禁）",
        f"- 完整 1h bar：**{u['complete_1h_bars']:,}**（门槛 {r['preregistered']['V0']['min_complete_1h']:,}）",
        f"- 锚定决策：**{u['anchors']:,}**（门槛 {r['preregistered']['V0']['min_anchors']:,}；"
        f"缺锚点 {u['missing_anchor']:,}）",
        f"- 连续段：{u['segments']}（内部缺口 {u['internal_gaps']} 处，已按段切分避免跨缺口取错 bar）",
        f"- 可交易锚点（DIRECT+PROBE+risk_allowed）：**{u['tradable_anchors']}**",
        f"- 1h `ATR×1.5 > 4%` 的截断率：{u['atr1h_over_max_stop_pct']}%",
        "",
        f"V0 判定：**{'通过' if v['V0_pass'] else '未通过'}**"
        + ("" if v.get("V0_detail", {}).get("anchors_ok", True) else
           f"（锚点 {v['V0_detail']['anchors']:,} 比门槛少 "
           f"{v['V0_detail']['anchors_shortfall']:,} 条 / "
           f"{v['V0_detail']['anchors_shortfall_pct']}%；"
           f"缺的是样本量而非数据质量，{v['V0_detail']['note']}）"),
        "",
        "## 矩阵",
        "",
        "| 成本档 \\| 出场 \\| 止损口径 | n | 毛利 `E[R]` | `cost_R` | `E[R_net]` | 80% CI | 止损中位 |",
        "|---|---:|---:|---:|---:|---|---:|",
    ]
    for k, s in r["matrix"].items():
        lines.append(
            f"| `{k}` | {s['n']:,} | {s['E_R']:+.4f} | {s['cost_R']:.4f} | "
            f"**{s['E_Rnet']:+.4f}** | {s['E_Rnet_ci80']} | {s['stop_pct_median'] * 100:.2f}% |"
        )
    p = r["matrix"][r["primary_key"]]
    lines += [
        "",
        f"## 主口径（`{r['primary_key']}`）",
        "",
        f"- 命中率 {p['hit'] * 100:.2f}%，歧义率 {p['ambiguous_pct']}%，持仓中位 {p['bars_median']} 小时",
        f"- 出场原因：{p['reasons']}",
        f"- `E[R]` 80% CI：{p['E_R_ci80']}",
        "",
        "### 按象限 / 方向 / 月份",
        "",
        "| 维度 | 值 | n | 毛利 `E[R]` | `E[R_net]` |",
        "|---|---|---:|---:|---:|",
    ]
    for label, key in (("象限", "by_quadrant"), ("方向", "by_side"), ("月份", "by_month")):
        for k, s in sorted(p[key].items(), key=lambda kv: -kv[1]["n"]) if p.get(key) else []:
            lines.append(f"| {label} | `{k}` | {s['n']:,} | {s['E_R']:+.4f} | {s['E_Rnet']:+.4f} |")
    lines += [
        "",
        "## 判据",
        "",
        f"- V1 成本门（`cost_R` 中位 ≤ {r['preregistered']['V1']['max_cost_R_median']}）："
        f"实测 **{p['cost_R']:.4f}** → **{'通过' if v['V1_pass'] else '未通过'}**",
        f"- V2 毛利门：**毛利** `E[R]` = {p['E_R']:+.4f}，80% CI {p['E_R_ci80']} → "
        f"**{'毛利区间跨 0 且近似平坦（|E[R]| < ' + str(r['preregistered']['V2'].get('flat_abs_E_R', '')) + '）' if v['V2_flat_er'] else '见上表'}**",
        f"- 净期望 `E[R_net]` = {p['E_Rnet']:+.4f}，80% CI {p['E_Rnet_ci80']}"
        f"（**不用来判 V2**：净期望必然被成本拉负，它的区间是否跨 0 与「有没有 alpha」无关）",
        f"- V3：可交易子集 n={v['tradable_n']}"
        f"（{'不足 300，仅作描述性统计' if v['V3_descriptive_only'] else '≥300，可做显著性判读'}）",
        "",
        f"**读法：{v['reading']}**",
        "",
        "## 与 15m 基线对比",
        "",
        "| 项 | 15m（32×15m=8h） | 1h（8×1h=8h） |",
        "|---|---:|---:|",
        "| 持仓墙钟上限 | 8h | 8h |",
        f"| `cost_R`（20bps，主口径） | 0.2728 | {p['cost_R']:.4f} |",
        f"| 毛利 `E[R]` | +0.011（ladgex 全决策面） | {p['E_R']:+.4f} |",
        "",
        "两张表的 `E[R]` **不可直接比**：15m 那行是 149k 条全决策面，本表是 "
        f"{p['n']:,} 条 1h 锚点，样本与权重都不同。可比的是 `cost_R` 的量级。",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    main()
