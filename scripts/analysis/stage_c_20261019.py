# -*- coding: utf-8 -*-
"""Stage C:因子构造 / 权重 / 出场天花板 —— 2026-10-19。

前置:三条轴已关闭(止损宽度 / 降成本 / 周期上移),Stage B 证明 1h 也无 alpha。
剩下唯一未动过的变量是「因子本身的构造与权重」以及「出场结构是否吃掉毛利」。

**执行顺序**:C3 先跑,它是决定性击杀门 —— 若连 hindsight 最优出场都无法覆盖
成本,则 C1/C2/C4 全部无意义,脚本直接停止。

任务:
  c3  MFE 上界(决定性击杀门 H3c)
  c1  影子五因子预测审计(C1,无真 OOS,描述性)
  c2  六因子逐因子 IC 审计(C2,有真 IS/OOS)
  c4  权重重拟合(仅当 C1/C2 至少一因子过 H5)

复用 `fwd_label_20261019` / `edge_scan_20261019` / `tf_uplift_20261019` 的现成机器,
不重写标注、Spearman、分块 bootstrap、BH-FDR。
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import fwd_label_20261019 as L  # noqa: E402

# --------------------------------------------------------------------------- #
# 预登记(跑前不得改;会原样回显到 metrics.json)
# --------------------------------------------------------------------------- #
PREREG = {
    "breakeven_E_R": {
        "15m": {"basis": "中位止损 0.65%", "bps20": 0.295, "bps11": 0.162, "bps7_75": 0.114},
        "1h": {"basis": "中位止损 1.59%", "bps20": 0.1254, "bps11": 0.0690, "bps7_75": 0.0486},
        "note": "C1/C2 跑在 15m -> 经济性判据用 15m 一行的 0.295 / 0.114",
    },
    "H0": {
        "a_identity": "每次标注后 check_identity <= 1e-9",
        "b_replicate": "C1 复刻臂六因子 IC 与 RELABEL 新值之差 <= 1e-4",
        "c_assert": "全样本标注无 AssertionError(证明 0<=remaining<=1 修复在全样本成立)",
        "d_shadow_coverage": {"min_rows": 30000, "min_days": 20, "min_symbols": 12},
    },
    "H1": {
        "c2_oos": {"min_rows": 20000, "min_days": 30, "min_symbols": 12},
        "c1": {"min_rows": 20000, "min_days": 20, "min_symbols": 12},
        "note": "20,000 锚点下限不放宽。Stage B 的 17,798 缺口来自 side 自推丢掉 32% 的小时,是策略属性不是数据缺口。",
    },
    "H2": {
        "stat": "日频 Spearman IC(每日 >= 20 行)",
        "target": "gross R(不用 R_net:stop_pct 由 ATR% 决定,而 ATR% 与 F4 强相关,用 R_net 会引入纯成本伪相关)",
        "bh_q": 0.10,
        "min_mean_ic": 0.020,
        "min_t": 1.5,
        "both_halves_positive": True,
        "basis": "现役六因子合成 IC=0.0012(约等于 0);0.020 是其 ~17 倍。按日 IC sd 0.04-0.05、days=22 算 SE~0.0085-0.0107,落在 t=1.9-2.4 临界带。t>=1.5 防两三个异常日顶起大均值。",
    },
    "H3": {
        "a_top_layer": "顶层 gross E[R] 的 80% 分块 CI 下界 > 0.295(15m @20bps 盈亏平衡)",
        "b_avoid_list": "底层 gross E[R] 的 80% CI 上界 < 0 -> 该因子可作排除过滤器",
        "c_c3_hardkill": "E[UB1] 80% CI 上界 < 0.114 且 顶十分位 E[UB1] 上界 < 0.114 -> 任何出场规则都无法让 15m 在 7.75bps 下转正",
        "d_c3_ceiling": "E[UB2] - 0.114 = 出场重设计的诚实上限",
        "e_capture_rate": "E[R_gross] / E[UB2] < 0.30 -> 出场重设计是剩余最高价值轴",
    },
    "H4": {
        "leave_one_symbol_min_ic": 0.0,
        "leave_one_day_min_ic": -0.01,
        "both_time_halves_min_ic": 0.0,
        "both_symbol_halves_min_ic": 0.0,
        "gross_and_net_sign_match": True,
    },
    "H5": "H0 and H1 and H2 and H3a and H4 至少一因子成立 -> 进 C4;否则 C4 SKIPPED(拟合噪声)",
    "multiplicity": {
        "c1_family": {"tests": 6, "q": 0.10},
        "c1_f4_variants": "不构成检验:clip v1 进门,3 个 sigma 仅描述性",
        "c2_family_a": {"tests": 6, "q": 0.10},
        "c2_family_b": {"tests": 12, "q": 0.05},
        "c3_exit_variants": {"tests": 5, "q": 0.10, "note": "仅 H3c 通过后另起一轮"},
        "c4_grid": {"tests": 10, "q": 0.10, "note": "仅 H5 通过后"},
        "total_max": 42,
    },
    "strata_rule": {
        "distinct>=20": "十分位",
        "5<=distinct<20": "按取值分层,每层 n>=500",
        "distinct<5": "不做分位,改两组差 E[R|高]-E[R|低] 的分块 bootstrap CI",
        "zero_fraction>0.60": "标记 degenerate,排除出 H2/H3 与 FDR 家族",
    },
}

SIX_WEIGHTED = (
    "trend_ema_context",
    "flow_cvd_confirmation",
    "cci_momentum_quality",
    "price_action_structure",
    "fibonacci_location",
    "risk_reward_geometry",
)

FAMILY_B = (
    "ema_50_quality", "ema_momentum", "ema_200_gate", "direction_1h",
    "background_4h", "quality_30m", "trigger_15m", "market_regime",
    "volatility_stop", "liquidity_execution", "cvd_flow", "fib_action_cap",
)

FIVE_FACTORS = (
    "trend_persistence",
    "structure_location",
    "payoff_geometry",
    "volatility_regime",
    "order_flow",
)

IS_END = "2026-09-13"
OOS_START = "2026-09-14"

BOOT_ITERS = 2000
BOOT_SEED = 7
MIN_ROWS_PER_DAY = 20


# --------------------------------------------------------------------------- #
# 通用统计
# --------------------------------------------------------------------------- #
def mean(v):
    return statistics.fmean(v) if v else None


def _blocks(rows):
    b = defaultdict(list)
    for r in rows:
        b[r["block"]].append(r)
    return b


def _block_sums(rows, key):
    """块的 (sum, count),用于 O(iters*nblocks) 的重采样(而不是 O(iters*n))。"""
    s = defaultdict(float)
    c = defaultdict(int)
    for r in rows:
        s[r["block"]] += r[key]
        c[r["block"]] += 1
    return [(s[b], c[b]) for b in s if c[b] > 0]


def boot_ci(rows, key="R", iters=BOOT_ITERS, seed=BOOT_SEED):
    """分块 bootstrap 80% 区间(块 = symbol|date)。"""
    blocks = _block_sums(rows, key)
    if len(blocks) < 8:
        return None
    rng = random.Random(seed)
    out = []
    n = len(blocks)
    for _ in range(iters):
        tot = 0.0
        cnt = 0
        for _ in range(n):
            s, c = blocks[rng.randrange(n)]
            tot += s
            cnt += c
        if cnt:
            out.append(tot / cnt)
    if not out:
        return None
    out.sort()
    return [out[int(0.10 * len(out))], out[int(0.90 * len(out))]]


def boot_diff(rows, hi_key, lo_key, iters=BOOT_ITERS, seed=BOOT_SEED):
    """两组差的 80% CI:按 block 重采样,在每次重采样内分别取两组均值再相减。"""
    acc = defaultdict(lambda: [0.0, 0, 0.0, 0])  # sum_hi, cnt_hi, sum_lo, cnt_lo
    for r in rows:
        g = "hi" if r.get(hi_key) else ("lo" if r.get(lo_key) else None)
        if not g:
            continue
        a = acc[r["block"]]
        if g == "hi":
            a[0] += r["R"]
            a[1] += 1
        else:
            a[2] += r["R"]
            a[3] += 1
    blocks = [v for v in acc.values() if (v[1] or v[3])]
    n = len(blocks)
    if n < 8:
        return None
    rng = random.Random(seed)
    out = []
    for _ in range(iters):
        sh = ch = sl = cl = 0.0
        for _ in range(n):
            v = blocks[rng.randrange(n)]
            sh += v[0]; ch += v[1]; sl += v[2]; cl += v[3]
        if ch and cl:
            out.append(sh / ch - sl / cl)
    if not out:
        return None
    out.sort()
    return [out[int(0.10 * len(out))], out[int(0.90 * len(out))]]


def daily_ic(rows, factor, target="R"):
    """日频 Spearman IC,返回 (days, mean_ic, positive_days, sd, t)。"""
    by_day = defaultdict(list)
    for r in rows:
        v = r.get(factor)
        if v is None or (isinstance(v, float) and math.isnan(v)):
            continue
        by_day[r["date"]].append((v, r[target]))
    ics = []
    for day, pairs in sorted(by_day.items()):
        if len(pairs) < MIN_ROWS_PER_DAY:
            continue
        rho = L.spearman([p[0] for p in pairs], [p[1] for p in pairs])
        if rho is not None:
            ics.append((day, rho))
    if len(ics) < 5:
        return None
    vals = [x[1] for x in ics]
    sd = statistics.pstdev(vals) if len(vals) > 1 else 0.0
    t = (mean(vals) / (sd / math.sqrt(len(vals)))) if sd > 0 else None
    return {
        "days": len(ics),
        "mean_ic": round(mean(vals), 5),
        "positive_days": sum(1 for v in vals if v > 0),
        "sd_ic": round(sd, 5),
        "t": None if t is None else round(t, 3),
        "series": ics,
    }


def ic_boot(ic_obj, iters=BOOT_ITERS, seed=BOOT_SEED):
    """对日 IC 序列做 bootstrap:80% CI + 单侧 p(mean<=0 的比例)。"""
    if not ic_obj:
        return None, None
    vals = [x[1] for x in ic_obj["series"]]
    rng = random.Random(seed)
    out = []
    for _ in range(iters):
        out.append(mean([vals[rng.randrange(len(vals))] for _ in vals]))
    out.sort()
    ci = [out[int(0.10 * len(out))], out[int(0.90 * len(out))]]
    p = sum(1 for m in out if m <= 0) / len(out)
    return ci, p


def bh_qvalues(pvals):
    n = len(pvals)
    order = sorted(range(n), key=lambda i: pvals[i])
    q = [1.0] * n
    prev = 1.0
    for rank in range(n, 0, -1):
        idx = order[rank - 1]
        val = min(prev, pvals[idx] * n / rank)
        q[idx] = val
        prev = val
    return q


# --------------------------------------------------------------------------- #
# 面板装载(在 L.load_decisions 基础上补五因子影子的逐因子值)
# --------------------------------------------------------------------------- #
def load_panel_v2(paths, profile="six_factor"):
    """镜像 L.load_decisions,额外抓取 component_points_v2_meta 的逐因子归一化值。

    L.load_decisions 只保留了 shadow_total(合成),丢掉了五个分量;FEATURE_KEYS
    也不含新因子名。这里补上,不改 fwd_label(共享标注引擎,本轮不动)。
    """
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
                if profile == "six_factor" and not L._is_six_factor(r.get("weights")):
                    continue
                key = (sym, int(ts))
                if key in seen:
                    continue
                seen.add(key)
                sd = r.get("score_detail") or {}
                meta = r.get("component_points_v2_meta") or {}
                v2 = meta.get("normalized_values") or {}
                atr_pct = float(ec.get("atr_pct") or 0.0)
                d = {
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
                    "feat": L._extract_features(r, ec, sd, atr_pct, int(ts)),
                }
                for k in FIVE_FACTORS:
                    d[f"v2_{k}"] = float(v2[k]) if k in v2 else None
                # F4 双轨:clip v1 现役;gauss v2 三个 sigma 仅描述性
                d["v2_vol_clip_v1"] = meta.get("volatility_regime_clip_v1")
                gauss = meta.get("volatility_regime_gauss_v2") or {}
                d["v2_vol_gauss"] = {str(k): v for k, v in gauss.items()} if gauss else None
                out.append(d)
    return out


def label(decisions, exit_mode="ladder", entry_mode="bar_close", **kw):
    """包装 L.run_labeling,返回 rows。R 列在 ladder 口径下是 gross。"""
    rows, bars, per_symbol, index, quad_map = L.run_labeling(
        decisions, exit_mode=exit_mode, entry_mode=entry_mode, **kw
    )
    return rows, bars, per_symbol, index, quad_map


# --------------------------------------------------------------------------- #
# C3:MFE 上界(决定性击杀门)
# --------------------------------------------------------------------------- #
def label_mfe_only(bars, per_symbol, index, d, stop_pct, entry_mode="bar_close",
                   horizon=L.HORIZON_BARS):
    """全 horizon 的 MFE / MAE 上界,不受出场规则截断。

    注意:`label_ladder` 的 `mfe` 只在 [start, last] 内更新,而 last 由出场规则决定,
    所以它是「当前出场规则内生的」,是全场 MFE 的**下界**,不能拿来当下界结论。
    这里对完整的 [start, start+horizon-1] 窗口取极值:
      UB1 = 逐 bar 最优 tick(high/low)出场 —— 宽松上界
      UB2 = 逐 bar 收盘出场 —— 任何 trailing 规则在 hindsight 下的天花板
    """
    base = L._entry_and_start(bars, per_symbol, index, d, entry_mode, horizon)
    if base is None:
        return None
    entry, start, last, order = base
    if not stop_pct or stop_pct <= 0 or not entry:
        return None
    sym = d["symbol"]
    sign = 1.0 if d["side"] == "LONG" else -1.0
    risk = entry * stop_pct
    if risk <= 0:
        return None
    ub1 = float("-inf")
    ub2 = float("-inf")
    mae = float("inf")
    for j in range(start, last + 1):
        _o, high, low, close = bars[(sym, order[j])]
        best = high if sign > 0 else low
        worst = low if sign > 0 else high
        ub1 = max(ub1, (best - entry) * sign / risk)
        ub2 = max(ub2, (close - entry) * sign / risk)
        mae = min(mae, (worst - entry) * sign / risk)
    return {"ub1": ub1, "ub2": ub2, "mae": mae, "mfe_bars": last - start + 1}


def task_c3(decisions, out_dir):
    print("[C3] 装载 + 标注(ladgex,线上口径)...")
    rows, bars, per_symbol, index, _ = label(
        decisions, exit_mode="ladder", entry_mode="bar_close",
        post_tp_mode="trend_capture", quadrant_defense=True, q2_tighten=True,
    )
    print(f"[C3] 标注完成 n={len(rows)}")

    # 同一批决策再走一遍 MFE-only(共用同一套 bars,不重复 I/O)
    mfe_rows = []
    for d in decisions:
        stop = L.resolve_stop(d.get("stop_pct"), d.get("atr_pct"), None, None)
        m = label_mfe_only(bars, per_symbol, index, d, stop, "bar_close")
        if m is None:
            continue
        d = dict(d)
        d.update(m)
        d["date"] = datetime.fromtimestamp(d["ts"], tz=timezone.utc).strftime("%Y-%m-%d")
        d["month"] = d["date"][:7]
        d["block"] = f'{d["symbol"]}|{d["date"]}'
        mfe_rows.append(d)

    def st(rs, key):
        if not rs:
            return None
        ci = boot_ci(rs, key=key)
        return {
            "n": len(rs),
            "E": round(mean([r[key] for r in rs]), 4),
            "ci80": None if ci is None else [round(ci[0], 4), round(ci[1], 4)],
        }

    res = {
        "n_labeled": len(rows),
        "n_mfe": len(mfe_rows),
        "UB1": st(mfe_rows, "ub1"),
        "UB2": st(mfe_rows, "ub2"),
        "MAE": st(mfe_rows, "mae"),
        "R_gross": st(rows, "R"),
        "cost_R": round(mean([r["cost_r"] for r in rows]), 4) if rows else None,
        "stop_pct_median": round(statistics.median([r["stop_pct_eff"] for r in rows]), 5) if rows else None,
    }

    # 按分数十分位(检验高分组是否有更高的天花板)
    scored = [r for r in mfe_rows if r.get("score") is not None]
    scored.sort(key=lambda r: r["score"])
    dec = []
    k = 10
    for i in range(k):
        seg = scored[int(i * len(scored) / k): int((i + 1) * len(scored) / k)]
        if not seg:
            continue
        dec.append({
            "decile": i + 1, "n": len(seg),
            "score_lo": round(seg[0]["score"], 2), "score_hi": round(seg[-1]["score"], 2),
            "E_UB1": round(mean([x["ub1"] for x in seg]), 4),
            "E_UB2": round(mean([x["ub2"] for x in seg]), 4),
            "UB1_ci80": (lambda c: None if c is None else [round(c[0], 4), round(c[1], 4)])(boot_ci(seg, "ub1")),
            "UB2_ci80": (lambda c: None if c is None else [round(c[0], 4), round(c[1], 4)])(boot_ci(seg, "ub2")),
        })
    res["ub_by_score_decile"] = dec

    # 判据
    thr = PREREG["breakeven_E_R"]["15m"]["bps7_75"]
    ub1 = res["UB1"]
    top = dec[-1] if dec else None
    kill = bool(
        ub1 and ub1["ci80"] and ub1["ci80"][1] < thr
        and top and top["UB1_ci80"] and top["UB1_ci80"][1] < thr
    )
    e_r = res["R_gross"]["E"] if res["R_gross"] else None
    e_ub2 = res["UB2"]["E"] if res["UB2"] else None
    capture = (e_r / e_ub2) if (e_r and e_ub2) else None
    res["verdict"] = {
        "H3c_hardkill": kill,
        "threshold": thr,
        "UB1_ci80_upper": None if not (ub1 and ub1["ci80"]) else ub1["ci80"][1],
        "top_decile_UB1_ci80_upper": None if not (top and top["UB1_ci80"]) else top["UB1_ci80"][1],
        "H3d_ceiling_UB2_minus_thr": None if e_ub2 is None else round(e_ub2 - thr, 4),
        "H3e_capture_rate": None if capture is None else round(capture, 4),
        "H3e_pass": None if capture is None else bool(capture < 0.30),
    }

    # C3-2:1h trades.csv 捕获率(秒级,不需要重建面板)
    p = Path("reports/analysis/six-factor-1h-20261019/trades.csv")
    if p.exists():
        with open(p, encoding="utf-8") as fh:
            tr = list(csv.DictReader(fh))
        b4 = [r for r in tr if r["arm"] == "B4"]
        for r in b4:
            r["R"] = float(r["R"]); r["mfe_r"] = float(r["mfe_r"])
            r["block"] = f'{r["real_symbol"]}|{r["date"]}'
        def st1(rs, key="mfe_r"):
            if not rs: return None
            ci = boot_ci(rs, key=key)
            return {"n": len(rs), "E": round(mean([x[key] for x in rs]), 4),
                    "ci80": None if ci is None else [round(ci[0], 4), round(ci[1], 4)]}
        by_reason = {}
        for kk, v in L._group(b4, lambda d: d["reason"]).items():
            by_reason[kk] = {"n": len(v), "E_R": round(mean([x["R"] for x in v]), 4),
                             "E_mfe": round(mean([x["mfe_r"] for x in v]), 4)}
        res["c3_2_1h"] = {
            "n": len(b4),
            "E_R": round(mean([x["R"] for x in b4]), 4),
            "E_mfe": st1(b4),
            "capture_rate": round(mean([x["R"] for x in b4]) / mean([x["mfe_r"] for x in b4]), 4)
            if b4 and mean([x["mfe_r"] for x in b4]) else None,
            "by_reason": by_reason,
        }
    return res


# --------------------------------------------------------------------------- #
# D:因果出场变体重放(C3 触发后才跑)
# --------------------------------------------------------------------------- #
# 触发条件:C3-1 的 E[UB1] 80% CI 下界 > 0.114(实测 1.944,远超)。
# 注意:UB2/MAE 对称(+1.60 / -1.86)说明天花板是波动不是 alpha,所以这里测的是
# **因果**规则(只用截至当根 bar 的信息),不是 hindsight 最优 tick。
# `quad_def` = 线上象限防御(Q3 减半 / Q4 两连击防御平仓 / Q2 收紧);`post_trail_*` =
# post_tp_mode="trend_capture" 的 post-TP 追踪(mfe>=1.5R 后回撤 1.0R)。
# V0 必须逐位复刻线上 ladgex —— 否则「变体 vs 基线」的对比没有意义。
_BASE = dict(quad_def=True, post_trail_trig=1.5, post_trail_r=1.0)
VARIANTS = {
    "V0_baseline_ladgex": dict(tp=(1.2, 2.0, 3.0), frac=(0.40, 0.35, 0.25),
                               breakeven=True, trail_trig=None, trail_r=None, cb=8, hold=32, **_BASE),
    "V1_trail_0.5_0.5": dict(tp=(), frac=(), breakeven=False, trail_trig=0.5, trail_r=0.5, cb=8, hold=32, **_BASE),
    "V2_trail_1.0_0.5": dict(tp=(), frac=(), breakeven=False, trail_trig=1.0, trail_r=0.5, cb=8, hold=32, **_BASE),
    "V3_trail_1.0_1.0": dict(tp=(), frac=(), breakeven=False, trail_trig=1.0, trail_r=1.0, cb=8, hold=32, **_BASE),
    "V4_trail_1.5_0.75": dict(tp=(), frac=(), breakeven=False, trail_trig=1.5, trail_r=0.75, cb=8, hold=32, **_BASE),
    "V5_tp2_full": dict(tp=(2.0,), frac=(1.0,), breakeven=False, trail_trig=None, trail_r=None, cb=8, hold=32, **_BASE),
    "V6_tp3_full": dict(tp=(3.0,), frac=(1.0,), breakeven=False, trail_trig=None, trail_r=None, cb=8, hold=32, **_BASE),
    "V7_ladder_no_be": dict(tp=(1.2, 2.0, 3.0), frac=(0.40, 0.35, 0.25),
                            breakeven=False, trail_trig=None, trail_r=None, cb=8, hold=32, **_BASE),
    "V8_hold32_only": dict(tp=(), frac=(), breakeven=False, trail_trig=None, trail_r=None, cb=None, hold=32, **_BASE),
    "V9_trail_1.0_0.5_nocb": dict(tp=(), frac=(), breakeven=False, trail_trig=1.0, trail_r=0.5, cb=None, hold=32, **_BASE),
    "V10_ladder_no_posttrail": dict(tp=(1.2, 2.0, 3.0), frac=(0.40, 0.35, 0.25),
                                    breakeven=True, trail_trig=None, trail_r=None, cb=8, hold=32,
                                    quad_def=True, post_trail_trig=None, post_trail_r=None),
    "V11_hold32_with_trail": dict(tp=(), frac=(), breakeven=False, trail_trig=1.0, trail_r=0.5,
                                  cb=None, hold=32, quad_def=True, post_trail_trig=None, post_trail_r=None),
}


def label_variant(bars, per_symbol, index, d, stop_pct, entry_mode="bar_close",
                  cfg=None, horizon=L.HORIZON_BARS, round_trip_bps=20.0, quad_map=None):
    """因果出场变体:只用截至当根 bar 的信息,不含任何 hindsight。

    与 `label_ladder` 的差异:TP 阶梯 / 保本移动 / 成本超时全部可关,新增「追踪止损」
    (按**运行峰值**回撤 trail_r 个 R 触发,只向有利方向移动)。
    """
    base = L._entry_and_start(bars, per_symbol, index, d, entry_mode, horizon)
    if base is None:
        return None
    entry, start, last, order = base
    if not stop_pct or stop_pct <= 0 or not entry:
        return None
    sym = d["symbol"]
    sign = 1.0 if d["side"] == "LONG" else -1.0
    risk = entry * stop_pct
    if risk <= 0:
        return None
    cost_r = (round_trip_bps / 10000.0) / stop_pct
    stop = entry * (1 - sign * stop_pct)
    breakeven = entry * (1 + sign * L.POST_TP_STOP_OFFSET)
    levels = [entry * (1 + sign * stop_pct * t) for t in cfg["tp"]]
    realized = 0.0
    remaining = 1.0
    consumed = 0
    peak = entry
    q3_done = False
    q4_streak = 0

    def pnl(px):
        return (px - entry) * sign / risk

    def out_at(px, reason, hold):
        assert -1e-9 <= remaining <= 1.0 + 1e-9, f"remaining out of range: {remaining}"
        gross = realized + remaining * pnl(px)
        return {"R": gross, "gross_R": gross, "R_net": gross - cost_r,
                "cost_r": cost_r, "bars": hold, "reason": reason,
                "entry_price": entry, "stop_price": stop, "mfe_r": pnl(peak)}

    for j in range(start, last + 1):
        _o, high, low, close = bars[(sym, order[j])]
        hold = j - start + 1
        best = high if sign > 0 else low
        if (best - entry) * sign > (peak - entry) * sign:
            peak = best
        mfe_now = pnl(peak)

        # 1) 已 TP 后的止损更新(线上 post_tp_mode):优先 trend_capture 追踪,否则保本。
        #    注意:线上用**当根 bar 的极值** best 而非运行峰值(见 label_ladder 第 330 行),
        #    这里逐位复刻,否则 V0 会偏离基线 0.0035R。
        if consumed >= 1:
            if cfg["post_trail_trig"] is not None and mfe_now >= cfg["post_trail_trig"]:
                cand = best - sign * cfg["post_trail_r"] * risk
                stop = max(stop, cand) if sign > 0 else min(stop, cand)
            elif cfg["breakeven"]:
                stop = breakeven

        # 2) 全局追踪止损(新增机制,按**运行峰值**回撤,只向有利方向移动)
        if cfg["trail_trig"] is not None and mfe_now >= cfg["trail_trig"]:
            cand = peak - sign * cfg["trail_r"] * risk
            stop = max(stop, cand) if sign > 0 else min(stop, cand)

        # 3) 止损最高优先级
        if (low <= stop) if sign > 0 else (high >= stop):
            return out_at(stop, "INITIAL_STOP_HIT" if consumed == 0 else "POST_TP_STOP_HIT", hold)

        # 4) 象限防御(线上要求 experiment_id 非空)
        if quad_map is not None and cfg.get("quad_def"):
            quad = quad_map.get((sym, order[j]))
            if quad == "Q2":  # q2_tighten
                stop = max(stop, breakeven) if sign > 0 else min(stop, breakeven)
            if quad == "Q3" and not q3_done:
                realized += remaining * 0.5 * pnl(close)
                remaining *= 0.5
                q3_done = True
                continue
            q4_streak = q4_streak + 1 if quad == "Q4" else 0
            if q4_streak >= 2 and (realized + remaining * pnl(close) - cost_r) < 0:
                return out_at(close, "Q4_DEFENSIVE_EXIT", hold)

        # 5) TP 阶梯,每根最多一档(必须 clamp 到剩余仓位)
        if consumed < len(levels) and remaining > 1e-12:
            lv = levels[consumed]
            if (high >= lv) if sign > 0 else (low <= lv):
                frac = min(remaining, cfg["frac"][consumed])
                realized += frac * cfg["tp"][consumed]
                remaining -= frac
                consumed += 1

        # 6) 成本保本超时
        if cfg["cb"] is not None and hold >= cfg["cb"] and consumed == 0:
            if pnl(close) < L.COST_BREAKEVEN_BUFFER_MULT * cost_r:
                return out_at(close, "COST_BREAKEVEN_TIMEOUT", hold)

        # 7) 最大持仓
        if hold >= horizon:
            return out_at(close, "MAX_HOLD", hold)

    return out_at(bars[(sym, order[last])][3], "MAX_HOLD", last - start + 1)


def run_variant(decisions, bars, per_symbol, index, cfg, round_trip_bps=20.0, quad_map=None):
    out = []
    for d in decisions:
        stop = L.resolve_stop(d.get("stop_pct"), d.get("atr_pct"), None, None)
        r = label_variant(bars, per_symbol, index, d, stop, "bar_close", cfg,
                          round_trip_bps=round_trip_bps, quad_map=quad_map)
        if r is None:
            continue
        row = dict(d)
        row.update(r)
        row["stop_pct_eff"] = stop
        row["date"] = datetime.fromtimestamp(d["ts"], tz=timezone.utc).strftime("%Y-%m-%d")
        row["month"] = row["date"][:7]
        row["block"] = f'{d["symbol"]}|{row["date"]}'
        out.append(row)
    return out


def task_d(decisions, out_dir):
    """因果出场变体重放:IS/OOS + 分块 bootstrap + BH-FDR。"""
    bars, per_symbol, index = L.build_bars(decisions)
    quad_map = L.build_quadrant_map(decisions)
    thr20 = PREREG["breakeven_E_R"]["15m"]["bps20"]
    thr775 = PREREG["breakeven_E_R"]["15m"]["bps7_75"]
    rows_by_v = {}
    for name, cfg in VARIANTS.items():
        rows_by_v[name] = run_variant(decisions, bars, per_symbol, index, cfg, 20.0, quad_map)
    # H0a:不变量
    ident = max(
        abs(r["R_net"] - (r["R"] - r["cost_r"]))
        for rs in rows_by_v.values() for r in rs
    ) if rows_by_v else 0.0
    out = []
    for name, rs in rows_by_v.items():
        isr = [r for r in rs if r["date"] <= IS_END]
        osr = [r for r in rs if r["date"] >= OOS_START]
        def st(sub):
            if not sub:
                return None
            ci = boot_ci(sub, key="R")
            cin = boot_ci(sub, key="R_net")
            return {
                "n": len(sub),
                "hit": round(sum(1 for x in sub if x["R"] > 0) / len(sub), 4),
                "E_R": round(mean([x["R"] for x in sub]), 4),
                "E_R_ci80": None if ci is None else [round(ci[0], 4), round(ci[1], 4)],
                "cost_R": round(mean([x["cost_r"] for x in sub]), 4),
                "E_Rnet": round(mean([x["R_net"] for x in sub]), 4),
                "E_Rnet_ci80": None if cin is None else [round(cin[0], 4), round(cin[1], 4)],
                "bars_median": sorted(x["bars"] for x in sub)[len(sub) // 2],
            }
        o = st(osr)
        e = {
            "variant": name,
            "cfg": {k: v for k, v in VARIANTS[name].items()},
            "is": st(isr),
            "oos": o,
        }
        if o and o["E_R_ci80"]:
            e["D1_pass_gross_gt_cost20"] = bool(o["E_R_ci80"][0] > thr20)
            e["D2_pass_gross_gt_cost775"] = bool(o["E_R_ci80"][0] > thr775)
        e["p_one_sided"] = boot_p(osr, key="R")
        out.append(e)
    # BH-FDR over variants (q<=0.10)
    idx = [i for i, e in enumerate(out) if e["p_one_sided"] is not None]
    if idx:
        qs = bh_qvalues([out[i]["p_one_sided"] for i in idx])
        for j, i in enumerate(idx):
            out[i]["q"] = round(qs[j], 4)
            out[i]["D0_pass_fdr"] = bool(qs[j] <= 0.10)
    for e in out:
        e.setdefault("q", None)
        e.setdefault("D0_pass_fdr", False)
    return {
        "H0a_identity_max_residual": ident,
        "H0a_pass": ident <= 1e-9,
        "thresholds": {"gross_at_20bps": thr20, "gross_at_7_75bps": thr775},
        "variants": out,
        "any_pass": any(e.get("D1_pass_gross_gt_cost20") for e in out),
    }


def boot_p(rows, key="R", iters=BOOT_ITERS, seed=BOOT_SEED):
    """单侧 p:按块重采样后均值 <= 0 的比例。"""
    blocks = _block_sums(rows, key)
    n = len(blocks)
    if n < 8:
        return None
    rng = random.Random(seed)
    le = 0
    for _ in range(iters):
        tot = 0.0
        cnt = 0
        for _ in range(n):
            s, c = blocks[rng.randrange(n)]
            tot += s
            cnt += c
        if cnt and tot / cnt <= 0:
            le += 1
    return round(le / iters, 4)


# --------------------------------------------------------------------------- #
# C1 / C2:因子预测力
# --------------------------------------------------------------------------- #
def _cardinality(rows, key):
    vals = [r.get(key) for r in rows]
    vals = [v for v in vals if v is not None and not (isinstance(v, float) and math.isnan(v))]
    if not vals:
        return 0, 1.0
    return len(set(vals)), sum(1 for v in vals if v == 0) / len(vals)


def strata_table(rows, key, target="R"):
    """按预登记的分桶规则产出分层表:distinct>=20 走十分位,5-19 按取值,<5 不做。"""
    sub = [r for r in rows if r.get(key) is not None and not (isinstance(r.get(key), float) and math.isnan(r.get(key)))]
    if len(sub) < 200:
        return None
    distinct, zero_frac = _cardinality(sub, key)
    out = {"key": key, "distinct": distinct, "zero_fraction": round(zero_frac, 4), "n": len(sub)}
    if zero_frac > 0.60:
        out["degenerate"] = True
        return out
    out["degenerate"] = False
    if distinct < 5:
        # 两组差检验
        med = statistics.median([r[key] for r in sub])
        for r in sub:
            r["_hi"] = r[key] > med
            r["_lo"] = r[key] <= med
        ci = boot_diff(sub, "_hi", "_lo")
        hi = [r[target] for r in sub if r["_hi"]]
        lo = [r[target] for r in sub if r["_lo"]]
        out["mode"] = "two_group"
        # 基数极低时中位数切分可能让高位组为空(如 flow_cvd 只有 0.2/1.0 两个取值,
        # 中位数落在 1.0 上则 hi 为空)——必须显式判空,否则 mean() 返回 None 会炸。
        if len(hi) < 30 or len(lo) < 30:
            out["degenerate"] = True
            out["note"] = f"两组差不可算: 中位数切分后 n_hi={len(hi)} n_lo={len(lo)}"
            return out
        out["n_hi"] = len(hi)
        out["n_lo"] = len(lo)
        out["E_hi"] = round(mean(hi), 4)
        out["E_lo"] = round(mean(lo), 4)
        out["diff"] = round(mean(hi) - mean(lo), 4)
        out["diff_ci80"] = None if ci is None else [round(ci[0], 4), round(ci[1], 4)]
        return out
    if distinct < 20:
        groups = defaultdict(list)
        for r in sub:
            groups[round(r[key], 4)].append(r)
        vals = sorted(groups)
        layers = []
        for v in vals:
            g = groups[v]
            ci = boot_ci(g, key=target)
            layers.append({"value": v, "n": len(g), "E": round(mean([x[target] for x in g]), 4),
                           "ci80": None if ci is None else [round(ci[0], 4), round(ci[1], 4)]})
        out["mode"] = "by_value"
        out["layers"] = layers
        out["top"] = layers[-1] if layers else None
        out["bottom"] = layers[0] if layers else None
        out["band_spearman"] = None
        return out
    sub.sort(key=lambda r: r[key])
    k = 10
    layers = []
    for i in range(k):
        seg = sub[int(i * len(sub) / k): int((i + 1) * len(sub) / k)]
        if not seg:
            continue
        ci = boot_ci(seg, key=target)
        layers.append({"decile": i + 1, "n": len(seg),
                       "lo": round(seg[0][key], 4), "hi": round(seg[-1][key], 4),
                       "E": round(mean([x[target] for x in seg]), 4),
                       "ci80": None if ci is None else [round(ci[0], 4), round(ci[1], 4)]})
    out["mode"] = "decile"
    out["layers"] = layers
    out["top"] = layers[-1] if layers else None
    out["bottom"] = layers[0] if layers else None
    out["band_spearman"] = (
        round(L.spearman([x["decile"] for x in layers], [x["E"] for x in layers]), 4)
        if len(layers) >= 4 else None
    )
    return out


def audit_factors(rows, keys, label, target="R", halves=True):
    """对一组因子做:日频 IC + bootstrap + 分层表 + 稳健性。"""
    res = []
    for k in keys:
        ic = daily_ic(rows, k, target=target)
        ci, p = ic_boot(ic) if ic else (None, None)
        entry = {
            "factor": k,
            "ic": None if ic is None else {x: ic[x] for x in ("days", "mean_ic", "positive_days", "sd_ic", "t")},
            "ic_ci80": None if ci is None else [round(ci[0], 5), round(ci[1], 5)],
            "p_one_sided": None if p is None else round(p, 4),
        }
        if ic is None:
            entry["note"] = "日频样本不足(<5 天或每日<20 行)"
            res.append(entry)
            continue
        st = strata_table(rows, k, target=target)
        entry["strata"] = st
        if halves:
            days = sorted({r["date"] for r in rows})
            mid = days[len(days) // 2]
            h1 = [r for r in rows if r["date"] <= mid]
            h2 = [r for r in rows if r["date"] > mid]
            syms = sorted({r["symbol"] for r in rows})
            sm = syms[len(syms) // 2:]
            sh1 = [r for r in rows if r["symbol"] not in sm]
            sh2 = [r for r in rows if r["symbol"] in sm]
            entry["halves"] = {
                "time_h1_days": len({r["date"] for r in h1}),
                "time_h2_days": len({r["date"] for r in h2}),
                "ic_time_h1": None if not (x := daily_ic(h1, k, target)) else x["mean_ic"],
                "ic_time_h2": None if not (x := daily_ic(h2, k, target)) else x["mean_ic"],
                "ic_sym_h1": None if not (x := daily_ic(sh1, k, target)) else x["mean_ic"],
                "ic_sym_h2": None if not (x := daily_ic(sh2, k, target)) else x["mean_ic"],
            }
            # 留一标的 / 留一日
            worst_sym = None
            for s in sorted({r["symbol"] for r in rows}):
                sub = [r for r in rows if r["symbol"] != s]
                x = daily_ic(sub, k, target)
                if x:
                    worst_sym = x["mean_ic"] if worst_sym is None else min(worst_sym, x["mean_ic"])
            worst_day = None
            for dd in sorted({r["date"] for r in rows}):
                sub = [r for r in rows if r["date"] != dd]
                x = daily_ic(sub, k, target)
                if x:
                    worst_day = x["mean_ic"] if worst_day is None else min(worst_day, x["mean_ic"])
            entry["robustness"] = {"min_ic_leave_one_symbol": worst_sym, "min_ic_leave_one_day": worst_day}
        # gross / net 符号一致性
        x = daily_ic(rows, k, target="R_net")
        entry["ic_on_R_net"] = None if x is None else x["mean_ic"]
        res.append(entry)
    return res


def apply_fdr(entries, q_thr):
    """家族内 BH-FDR,写回 q 与 pass。"""
    idx = [i for i, e in enumerate(entries) if e.get("p_one_sided") is not None and not (e.get("strata") or {}).get("degenerate")]
    if not idx:
        for e in entries:
            e["q"] = None
            e["H2_pass"] = False
        return entries
    qs = bh_qvalues([entries[i]["p_one_sided"] for i in idx])
    for j, i in enumerate(idx):
        entries[i]["q"] = round(qs[j], 4)
        ic = entries[i].get("ic") or {}
        t = ic.get("t")
        entries[i]["H2_pass"] = bool(
            qs[j] <= q_thr
            and (ic.get("mean_ic") or 0) >= PREREG["H2"]["min_mean_ic"]
            and t is not None and t >= PREREG["H2"]["min_t"]
        )
    for e in entries:
        e.setdefault("q", None)
        e.setdefault("H2_pass", False)
    return entries


def task_c1(rows, out_dir):
    """影子五因子:窗口 2026-09-27 起,无真 OOS,仅描述性。"""
    shadow = [r for r in rows if r.get("v2_trend_persistence") is not None]
    if not shadow:
        return {"error": "no shadow rows"}
    days = sorted({r["date"] for r in shadow})
    syms = sorted({r["symbol"] for r in shadow})
    cov = {"rows": len(shadow), "days": len(days), "symbols": len(syms),
           "window": [days[0], days[-1]]}
    h0d = PREREG["H0"]["d_shadow_coverage"]
    keys = [f"v2_{k}" for k in FIVE_FACTORS] + ["shadow"]
    # shadow 是合成总分(0-100),归一化到 0-1 便于与分量同口径比较
    for r in shadow:
        r["shadow"] = (r.get("shadow") or 0.0) / 100.0
    entries = audit_factors(shadow, keys, "C1", target="R")
    entries = apply_fdr(entries, PREREG["multiplicity"]["c1_family"]["q"])
    # F4 双轨:仅描述性
    f4 = []
    for r in shadow:
        r["v2_vol_clip_v1"] = r.get("v2_vol_clip_v1")
    f4.append({"variant": "clip_v1", "factor": "v2_vol_clip_v1",
               "ic": (lambda x: None if x is None else {kk: x[kk] for kk in ("days", "mean_ic", "positive_days", "t")})(daily_ic(shadow, "v2_vol_clip_v1"))})
    g = [r for r in shadow if r.get("v2_vol_gauss")]
    for sig in ("sigma_0.20", "sigma_0.25", "sigma_0.30"):
        for r in g:
            r[f"_g{sig}"] = r["v2_vol_gauss"].get(sig)
        sub = [r for r in g if r.get(f"_g{sig}") is not None]
        f4.append({"variant": f"gauss_v2_sigma_{sig}", "factor": f"_g{sig}",
                   "days": len({r["date"] for r in sub}),
                   "ic": (lambda x: None if x is None else {kk: x[kk] for kk in ("days", "mean_ic", "positive_days", "t")})(daily_ic(sub, f"_g{sig}"))})
    return {
        "coverage": cov,
        "H0d_pass": bool(cov["rows"] >= h0d["min_rows"] and cov["days"] >= h0d["min_days"] and cov["symbols"] >= h0d["min_symbols"]),
        "H1_pass": bool(cov["rows"] >= PREREG["H1"]["c1"]["min_rows"] and cov["days"] >= PREREG["H1"]["c1"]["min_days"] and cov["symbols"] >= PREREG["H1"]["c1"]["min_symbols"]),
        "note": "影子 09-27 才上线(22 天 / ~32k 行),标准 IS/OOS 边界 09-13/09-14 全在其之前 -> C1 无真 OOS,仅描述性,不得据此改代码",
        "factors": entries,
        "f4_variants_descriptive_only": f4,
        "H5_any": any(e.get("H2_pass") for e in entries),
    }


def task_c2(rows, out_dir):
    """六因子逐因子 IC:有真 IS/OOS(边界 09-13 / 09-14)。"""
    # 六个加权子分与非加权分量都存在 `feat` 子字典里(L._extract_features 的产物),
    # 而 daily_ic 读顶层键 —— 必须先提升到顶层,否则 C2 会静默返回全 None。
    def hoist(rs):
        out = []
        for r in rs:
            d = dict(r)
            for k, v in (r.get("feat") or {}).items():
                if k not in d:
                    d[k] = v
            out.append(d)
        return out

    rows = hoist(rows)
    is_rows = [r for r in rows if r["date"] <= IS_END]
    oos_rows = [r for r in rows if r["date"] >= OOS_START]
    fam_a_oos = audit_factors(oos_rows, list(SIX_WEIGHTED), "C2-A", target="R")
    fam_a_oos = apply_fdr(fam_a_oos, PREREG["multiplicity"]["c2_family_a"]["q"])
    fam_a_is = audit_factors(is_rows, list(SIX_WEIGHTED), "C2-A-IS", target="R", halves=False)
    fam_b_oos = audit_factors(oos_rows, list(FAMILY_B), "C2-B", target="R")
    fam_b_oos = apply_fdr(fam_b_oos, PREREG["multiplicity"]["c2_family_b"]["q"])
    cov = {
        "oos_rows": len(oos_rows), "oos_days": len({r["date"] for r in oos_rows}),
        "oos_symbols": len({r["symbol"] for r in oos_rows}),
        "is_rows": len(is_rows), "is_days": len({r["date"] for r in is_rows}),
    }
    h = PREREG["H1"]["c2_oos"]
    return {
        "coverage": cov,
        "H1_pass": bool(cov["oos_rows"] >= h["min_rows"] and cov["oos_days"] >= h["min_days"] and cov["oos_symbols"] >= h["min_symbols"]),
        "family_a_oos": fam_a_oos,
        "family_a_is": fam_a_is,
        "family_b_oos": fam_b_oos,
        "H5_any": any(e.get("H2_pass") for e in fam_a_oos + fam_b_oos),
    }


def task_c4(rows, out_dir, h5):
    if not h5:
        return {"skipped": True, "reason": "C4 SKIPPED: H5 false — 拟合噪声", "weights": None}
    return {"skipped": True, "reason": "H5 true but C4 grid not implemented in this round", "weights": None}


# --------------------------------------------------------------------------- #
# C3-2 之外:把 panel 装载与标注串起来
# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--logs", default="logs")
    ap.add_argument("--months", default="2026-06,2026-07,2026-08,2026-09,2026-10")
    ap.add_argument("--profile", default="six_factor", choices=["any", "six_factor"])
    ap.add_argument("--task", default="all", choices=["c1", "c2", "c3", "c4", "d", "all"])
    ap.add_argument("--out", default="reports/analysis/stage-c-20261019")
    args = ap.parse_args()

    months = [m.strip() for m in args.months.split(",") if m.strip()]
    paths = []
    for m in months:
        paths += sorted(Path(args.logs).glob(f"{m}/*/decisions.jsonl"))
    print(f"[load] {len(paths)} files, profile={args.profile}")
    decisions = load_panel_v2([str(p) for p in paths], profile=args.profile)
    print(f"[load] {len(decisions)} decisions")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    metrics = {"preregistered": PREREG, "profile": args.profile,
               "months": months, "decisions": len(decisions)}

    # ---- C3 先跑(决定性击杀门) ----
    if args.task in ("c3", "all"):
        print("[C3] running (decisive kill gate)")
        c3 = task_c3(decisions, out)
        metrics["c3"] = c3
        v = c3.get("verdict") or {}
        print(f"[C3] UB1={c3['UB1']}")
        print(f"[C3] UB2={c3['UB2']}")
        print(f"[C3] R_gross={c3['R_gross']} cost_R={c3['cost_R']}")
        print(f"[C3] H3c_hardkill={v.get('H3c_hardkill')} (threshold {v.get('threshold')})")
        print(f"[C3] capture_rate={v.get('H3e_capture_rate')} ceiling={v.get('H3d_ceiling_UB2_minus_thr')}")
        if v.get("H3c_hardkill"):
            metrics["STOP"] = "H3c hard-kill: 任何出场规则都无法让 15m 在 7.75bps 下转正 -> C1/C2/C4 不跑"
            print("[STOP] " + metrics["STOP"])
            (out / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
            (out / "report.md").write_text(render(metrics), encoding="utf-8")
            return

    # ---- C1 / C2 ----
    rows, _bars, _ps, _idx, _qm = label(
        decisions, exit_mode="ladder", entry_mode="bar_close",
        post_tp_mode="trend_capture", quadrant_defense=True, q2_tighten=True,
    )
    print(f"[label] {len(rows)} labeled rows")
    metrics["labeled"] = len(rows)
    h5 = False
    if args.task in ("c1", "all"):
        print("[C1] running")
        metrics["c1"] = task_c1(rows, out)
        h5 = h5 or bool(metrics["c1"].get("H5_any"))
        print(f"[C1] coverage={metrics['c1'].get('coverage')} H5_any={metrics['c1'].get('H5_any')}")
    if args.task in ("c2", "all"):
        print("[C2] running")
        metrics["c2"] = task_c2(rows, out)
        h5 = h5 or bool(metrics["c2"].get("H5_any"))
        print(f"[C2] coverage={metrics['c2'].get('coverage')} H5_any={metrics['c2'].get('H5_any')}")
    if args.task in ("c4", "all"):
        metrics["c4"] = task_c4(rows, out, h5)
        print(f"[C4] {metrics['c4']}")
    if args.task in ("d", "all"):
        print("[D] causal exit variant replay")
        metrics["d"] = task_d(decisions, out)
        dd = metrics["d"]
        print(f"[D] H0a identity={dd['H0a_identity_max_residual']} pass={dd['H0a_pass']}")
        for e in dd["variants"]:
            o = e.get("oos") or {}
            print(f"[D] {e['variant']:<24} OOS n={o.get('n')} hit={o.get('hit')} "
                  f"E_R={o.get('E_R')} ci={o.get('E_R_ci80')} cost_R={o.get('cost_R')} "
                  f"E_Rnet={o.get('E_Rnet')} q={e.get('q')} D1={e.get('D1_pass_gross_gt_cost20')}")
        print(f"[D] any_pass={dd['any_pass']}")

    (out / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "report.md").write_text(render(metrics), encoding="utf-8")
    print(f"[done] {out/'metrics.json'}")


def render(m):
    L_ = []
    L_.append("# Stage C 结果(自动渲染)\n")
    c3 = m.get("c3")
    if c3:
        v = c3.get("verdict") or {}
        L_.append("## C3 MFE 上界(决定性击杀门)\n")
        L_.append("| 项 | n | E | 80% CI |")
        L_.append("|---|---:|---:|---|")
        for k in ("R_gross", "UB1", "UB2", "MAE"):
            s = c3.get(k)
            if s:
                L_.append(f"| {k} | {s['n']} | {s['E']} | {s['ci80']} |")
        L_.append(f"\ncost_R={c3.get('cost_R')}  stop_pct_median={c3.get('stop_pct_median')}\n")
        L_.append(f"- H3c 硬杀 = **{v.get('H3c_hardkill')}**(阈值 {v.get('threshold')};UB1 上界 {v.get('UB1_ci80_upper')},顶十分位上界 {v.get('top_decile_UB1_ci80_upper')})")
        L_.append(f"- H3d 出场重设计天花板 = {v.get('H3d_ceiling_UB2_minus_thr')}")
        L_.append(f"- H3e 捕获率 = {v.get('H3e_capture_rate')}\n")
    if m.get("STOP"):
        L_.append(f"> **{m['STOP']}**\n")
    for key in ("c1", "c2"):
        blk = m.get(key)
        if not blk:
            continue
        L_.append(f"## {key.upper()}\n")
        L_.append(f"coverage={blk.get('coverage')} H1_pass={blk.get('H1_pass')}\n")
        for name in ("factors", "family_a_oos", "family_b_oos"):
            for e in (blk.get(name) or []):
                ic = e.get("ic") or {}
                L_.append(
                    f"- `{e['factor']}`: days={ic.get('days')} mean_IC={ic.get('mean_ic')} "
                    f"t={ic.get('t')} p={e.get('p_one_sided')} q={e.get('q')} "
                    f"H2={'PASS' if e.get('H2_pass') else 'fail'}"
                )
        L_.append("")
    return "\n".join(L_)


if __name__ == "__main__":
    main()
