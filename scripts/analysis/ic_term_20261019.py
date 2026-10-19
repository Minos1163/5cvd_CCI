"""分量 × 周期 IC 期限结构矩阵(2026-10-19)。

为什么重做
----------
旧报告按**日池化**算 Spearman IC,把日内时间序列效应混进截面;目标列又是净
``R_net``(含成本),当分数与 ``stop_pct`` 相关时 IC 会混入「分数-成本」相关。
且只报 ±1R/32 根一个口径,看不到「1–4 根内有正漂移、之后被反转抵消」这种
期限结构 —— 而这恰恰决定出场规则还有没有价值。

本脚本口径(预登记,事后不许改)
------------------------------
* 特征 13 个:六因子分量 6 + v2 分量 5 + ``score_pct`` + ``shadow_pct``;
* 周期 6 档:1/2/4/8/16/32 根 15m;
* 目标列用**毛 R**(``exit_mode="barrier"`` / ``entry_mode="next_open"``),
  不扣成本,因此不含「分数-成本」相关;
* **逐时间戳横截面**:同一 UTC 时刻同一根 bar 上全部标的的截面 Spearman
  (``min_cs=8``),再对时间取均值;不再按日池化;
* 块 bootstrap 按 **UTC 日**重采样 2000 次,``se`` 为日块重采样均值的标准差;
* ``neff = (sd(ic_t)/se_boot)**2``(由 ``fwdlib.stats.neff`` 实现),不用
  ``n_obs/32`` 猜测;``design_effect = n_obs/neff``;
* 每格附加 ``ic_partial_stop``:逐 bar 对 ``stop_pct`` 秩做偏 Spearman
  (``fwdlib.stats.partial_spearman``),控制止损宽度;
* 非重叠敏感性:按 UTC 固定 8 小时网格(每 32 根 15m)子采样,``ic_nonoverlap``
  与 ``se_nonoverlap`` 与主列并列,供「两个 SE 取保守」复核。

预登记门槛:alpha=0.05 / power=0.80 / BH q=0.10 / min_cs=8 /
min_bars_per_cell=200 / min_neff=50。

产出(目录由 ``--out`` 指定)
----------------------------
``ic_matrix.csv``(78 行)、``ic_by_bar.csv``(h=32 的逐 bar IC)、
``tercile_spread.csv``(78 行)、``tests_ledger.jsonl``(159 行)、
``metrics.json``、``report.md``。

用法
----
  python scripts/analysis/ic_term_20261019.py \
    --logs D:/AIDCA/AI300/logs --months 2026-09,2026-10 \
    --out D:/AIDCA/AI300/reports/analysis/ic-term-20261019
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fwdlib.features import FEATURE_FAMILIES, load_decisions  # noqa: E402
from fwdlib.labeler import label_at_horizons, run_labeling  # noqa: E402
from fwdlib.stats import (  # noqa: E402
    TestLedger,
    bh_adjust,
    block_bootstrap,
    boot_p,
    cross_sectional_ic,
    mde,
    partial_spearman,
)

# ---- 预登记 ----
ALPHA = 0.05
POWER = 0.80
BH_Q = 0.10
MIN_CS = 8
MIN_BARS_PER_CELL = 200
MIN_NEFF = 50
ITERS = 2000
SEED = 7

#: 13 个特征,顺序即报告顺序(六因子 → v2 → 总分 → 影子)
FEATURES: tuple[str, ...] = (
    FEATURE_FAMILIES["six_factor"]
    + FEATURE_FAMILIES["v2"]
    + FEATURE_FAMILIES["score"]
    + FEATURE_FAMILIES["shadow"]
)

#: 非重叠子采样步长(32 根 15m = 8 小时,与 15m 栅格对齐)
NONOVERLAP_STRIDE_SECONDS = 32 * 900

FAMILY_IC = "ic"
FAMILY_TERCILE = "tercile"
FAMILY_DESCRIPTIVE = "descriptive"


# --------------------------------------------------------------------------- #
# 小工具
# --------------------------------------------------------------------------- #

def _finite(v) -> float | None:
    """把 None / nan / inf / 非数值统一收敛成 None(避免 nan 进 spearman)。"""
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _r(value, nd: int):
    """CSV 友好数值:None 保持 None,其余保留 ``nd`` 位。"""
    return None if value is None else round(float(value), nd)


def _utc_date(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


def _fmt(value, nd: int = 4, dash: str = "-") -> str:
    return dash if value is None else f"{value:.{nd}f}"


# --------------------------------------------------------------------------- #
# 数据装配
# --------------------------------------------------------------------------- #

def find_logs(logs: Path, months: list[str]) -> list[Path]:
    paths: list[Path] = []
    for m in months:
        paths += sorted(logs.glob(f"{m}/*/decisions.jsonl"))
    return paths


def build_rows(labeled, bars, per_symbol, index, horizons) -> tuple[list[dict], dict]:
    """给每行补上 ``R_h`` 与清洗后的 13 个特征。

    只对 ``run_labeling`` 已成功标注的行做多周期扩展(与 32 根口径同一入场
    过滤),避免把无入场价/无止损的行混进截面。``R32`` 以 ``run_labeling``
    的 ``gross_R`` 为准,``label_at_horizons`` 的 h=32 结果仅用于一致性核对。
    """
    rows: list[dict] = []
    mismatch = 0
    missing = 0
    for r in labeled:
        res = label_at_horizons(
            bars, per_symbol, index, r, r["stop_pct_eff"], horizons=horizons
        )
        if any(v is None for v in res.values()):
            missing += 1
        rec = {
            "symbol": r["symbol"],
            "ts": r["ts"],
            "date": r["date"],
            "stop_pct": _finite(r.get("stop_pct_eff")),
        }
        for h in horizons:
            hit = res.get(h)
            rec[f"R{h}"] = None if hit is None else _finite(hit.get("R"))
        ref = _finite(r.get("gross_R"))
        if rec["R32"] is not None and ref is not None and abs(rec["R32"] - ref) > 1e-9:
            mismatch += 1
        for k in FEATURES:
            rec[k] = _finite((r.get("feat") or {}).get(k))
        rows.append(rec)
    return rows, {"r32_mismatch_vs_run_labeling": mismatch, "rows_with_missing_horizon": missing}


def ic_cell(rows, feature: str, horizon: int, *, min_cs: int, iters: int) -> dict:
    return cross_sectional_ic(
        rows, feature, f"R{horizon}", min_cs=min_cs, block_key="date",
        iters=iters, seed=SEED,
    )


def partial_stop_cell(rows, feature: str, horizon: int, *, min_cs: int) -> dict:
    """逐 bar 偏 Spearman(控制 stop_pct 秩)后取时间均值。"""
    groups: dict[int, list[tuple[float, float, float]]] = defaultdict(list)
    for r in rows:
        v = r.get(feature)
        t = r.get(f"R{horizon}")
        z = r.get("stop_pct")
        if v is None or t is None or z is None:
            continue
        groups[r["ts"]].append((v, t, z))
    vals: list[float] = []
    for items in groups.values():
        if len(items) < min_cs:
            continue
        ic = partial_spearman([a for a, _b, _c in items],
                              [b for _a, b, _c in items],
                              [c for _a, _b, c in items])
        if ic is not None:
            vals.append(ic)
    return {
        "ic": statistics.fmean(vals) if vals else None,
        "n_bars": len(vals),
    }


def tercile_cell(rows, feature: str, horizon: int, *, min_cs: int, iters: int) -> dict:
    """逐 bar 分数三分位,E[R] 的 top-bottom 差,再按日块 bootstrap。"""
    groups: dict[int, list[tuple[float, float, str]]] = defaultdict(list)
    for r in rows:
        v = r.get(feature)
        t = r.get(f"R{horizon}")
        if v is None or t is None:
            continue
        groups[r["ts"]].append((v, t, r.get("date")))
    spreads: list[float] = []
    by_block: dict[str, list[float]] = defaultdict(list)
    n_obs = 0
    for items in groups.values():
        if len(items) < min_cs:
            continue
        items.sort(key=lambda x: x[0])
        k = len(items) // 3
        if k < 1:
            continue
        bottom = items[:k]
        top = items[-k:]
        spread = statistics.fmean([t for _v, t, _d in top]) - statistics.fmean(
            [t for _v, t, _d in bottom]
        )
        spreads.append(spread)
        by_block[items[0][2]].append(spread)
        n_obs += len(items)
    out = {
        "n_bars": len(spreads),
        "n_obs": n_obs,
        "spread": statistics.fmean(spreads) if spreads else None,
        "se": None,
        "ci95": None,
        "p": None,
    }
    if not spreads:
        return out
    bb = block_bootstrap(by_block, iters=iters, seed=SEED, ci=0.95)
    out["se"] = bb["se"]
    out["p"] = boot_p(bb["samples"]) if bb["samples"] else None
    if bb["lo"] is not None:
        out["ci95"] = (bb["lo"], bb["hi"])
    return out


# --------------------------------------------------------------------------- #
# 期限结构形态
# --------------------------------------------------------------------------- #

def classify_shape(ics: list[float | None]) -> str:
    """按 |IC| 随周期变化归类:flat / monotonic_decay / monotonic_rise / mid_peak / mixed。

    描述性口径,不参与任何显著性判定:

    * ``flat``:|IC| 全程低于 0.01 的噪声地板,或极差不超过最大值的 30%(同一水平带);
    * ``mid_peak``:内部周期(2–16)最大,且高出两端至少 0.005;
    * ``monotonic_decay`` / ``monotonic_rise``:h=32 的 |IC| 不到 h=1 的 75% / 超过 125%;
    * 其余 ``mixed``。

    用**相对**幅度而非绝对极差,避免把「0.024 → 0.016」这种明显衰减误判成 flat。
    """
    mags = [abs(v) if v is not None else None for v in ics]
    if any(v is None for v in mags):
        return "n/a"
    peak_mag = max(mags)
    if peak_mag < 0.01:
        return "flat"
    if (peak_mag - min(mags)) <= 0.30 * peak_mag:
        return "flat"
    peak = mags.index(peak_mag)
    if 0 < peak < len(mags) - 1 and peak_mag >= max(mags[0], mags[-1]) + 0.005:
        return "mid_peak"
    if mags[-1] <= 0.75 * mags[0]:
        return "monotonic_decay"
    if mags[-1] >= 1.25 * mags[0]:
        return "monotonic_rise"
    return "mixed"


# --------------------------------------------------------------------------- #
# 主流程
# --------------------------------------------------------------------------- #

def main() -> int:
    ap = argparse.ArgumentParser(description="分量 × 周期 IC 期限结构矩阵")
    ap.add_argument("--logs", default="D:/AIDCA/AI300/logs")
    ap.add_argument("--months", default="2026-09,2026-10")
    ap.add_argument("--out", default="D:/AIDCA/AI300/reports/analysis/ic-term-20261019")
    ap.add_argument("--horizons", default="1,2,4,8,16,32")
    ap.add_argument("--min-cs", type=int, default=MIN_CS)
    ap.add_argument("--bh-q", type=float, default=BH_Q)
    ap.add_argument("--iters", type=int, default=ITERS)
    ap.add_argument("--profile", default="six_factor",
                    choices=["any", "six_factor"], help="决策面档位(默认六因子 profile)")
    args = ap.parse_args()

    t0 = time.time()
    horizons = [int(x) for x in args.horizons.split(",") if x.strip()]
    months = [m.strip() for m in args.months.split(",") if m.strip()]

    paths = find_logs(Path(args.logs), months)
    print(f"[load] files={len(paths)} months={months}", flush=True)
    if not paths:
        print("[fatal] 未解析到任何 decisions.jsonl", flush=True)
        raise SystemExit(2)

    decisions = load_decisions([str(p) for p in paths], profile=args.profile)
    print(f"[load] decisions={len(decisions)}", flush=True)
    if not decisions:
        print("[fatal] 决策行数为 0", flush=True)
        raise SystemExit(2)

    labeled, bars, per_symbol, index, _ = run_labeling(
        decisions, exit_mode="barrier", entry_mode="next_open"
    )
    print(f"[label] labeled={len(labeled)} bars={len(bars)} symbols={len(per_symbol)}",
          flush=True)

    rows, row_audit = build_rows(labeled, bars, per_symbol, index, horizons)
    print(f"[label] multi-horizon rows={len(rows)} "
          f"r32_mismatch={row_audit['r32_mismatch_vs_run_labeling']}", flush=True)

    ts_all = sorted({r["ts"] for r in rows})
    nonoverlap_ts = {t for t in ts_all if t % NONOVERLAP_STRIDE_SECONDS == 0}
    rows_nonoverlap = [r for r in rows if r["ts"] in nonoverlap_ts]
    nonnull = Counter()
    date_sets: dict[str, set[str]] = defaultdict(set)
    for r in rows:
        for f in FEATURES:
            if r.get(f) is not None:
                nonnull[f] += 1
                date_sets[f].add(r["date"])
    coverage = {
        f: {
            "nonnull": nonnull[f],
            "pct": round(nonnull[f] / len(rows), 4) if rows else 0.0,
            "dates": len(date_sets[f]),
        }
        for f in FEATURES
    }
    cs_sizes = Counter(r["ts"] for r in rows if r.get(FEATURES[0]) is not None)
    cs_widths = sorted(Counter(r["ts"] for r in rows).values())
    print(f"[design] ts={len(ts_all)} dates={len({r['date'] for r in rows})} "
          f"nonoverlap_ts={len(nonoverlap_ts)} median_cs={statistics.median(cs_widths)}",
          flush=True)

    # ---- 78 格 ----
    cells: list[dict] = []
    ic_pvals: list[float | None] = []
    per_bar_h32: dict[str, list[tuple[int, float, int]]] = {}
    for feature in FEATURES:
        feat_cells = []
        for h in horizons:
            main = ic_cell(rows, feature, h, min_cs=args.min_cs, iters=args.iters)
            alt = ic_cell(rows_nonoverlap, feature, h, min_cs=args.min_cs, iters=args.iters)
            part = partial_stop_cell(rows, feature, h, min_cs=args.min_cs)
            se = main["se"]
            neff = main["neff"]
            cell = {
                "feature": feature,
                "horizon": h,
                "n_bars": main["n_bars"],
                "n_obs": main["n_obs"],
                "ic": main["mean_ic"],
                "se": se,
                "neff": neff,
                "design_effect": (main["n_obs"] / neff) if neff else None,
                "mde_ic": mde(se, alpha=ALPHA, power=POWER) if se else None,
                "p": main["p"],
                "q_bh": None,
                "ic_partial_stop": part["ic"],
                "n_bars_partial": part["n_bars"],
                "ic_nonoverlap": alt["mean_ic"],
                "se_nonoverlap": alt["se"],
                "n_bars_nonoverlap": alt["n_bars"],
                "status": "ok",
            }
            if cell["n_bars"] < MIN_BARS_PER_CELL or (neff or 0) < MIN_NEFF:
                cell["status"] = "insufficient"
            cells.append(cell)
            feat_cells.append(cell)
            ic_pvals.append(cell["p"])
            if h == 32:
                per_bar_h32[feature] = main["ics"]
        print(f"[ic] {feature:<26} " + " ".join(
            f"h{c['horizon']}={_fmt(c['ic'], 4)}({_fmt(c['se'], 4)})" for c in feat_cells
        ), flush=True)

    idx_with_p = [i for i, p in enumerate(ic_pvals) if p is not None]
    if idx_with_p:
        adj = bh_adjust([ic_pvals[i] for i in idx_with_p], q=args.bh_q)
        for pos, i in enumerate(idx_with_p):
            cells[i]["q_bh"] = adj["q"][pos]

    # ---- tercile ----
    terciles: list[dict] = []
    for feature in FEATURES:
        for h in horizons:
            res = tercile_cell(rows, feature, h, min_cs=args.min_cs, iters=args.iters)
            terciles.append({
                "feature": feature,
                "horizon": h,
                "n_bars": res["n_bars"],
                "n_obs": res["n_obs"],
                "spread": res["spread"],
                "se": res["se"],
                "ci95_lo": None if res["ci95"] is None else res["ci95"][0],
                "ci95_hi": None if res["ci95"] is None else res["ci95"][1],
                "p": res["p"],
                "q_bh": None,
            })
    t_idx = [i for i, t in enumerate(terciles) if t["p"] is not None]
    if t_idx:
        t_adj = bh_adjust([terciles[i]["p"] for i in t_idx], q=args.bh_q)
        for pos, i in enumerate(t_idx):
            terciles[i]["q_bh"] = t_adj["q"][pos]

    # ---- 台账:78 IC + 78 tercile + 3 描述性 = 159 ----
    ledger = TestLedger()
    for c in cells:
        ledger.add(
            FAMILY_IC, f"{c['feature']}|h{c['horizon']}",
            stat=c["ic"], se=c["se"], p=c["p"], n=c["n_obs"],
            n_eff=c["neff"], mde=c["mde_ic"],
            meta={
                "horizon": c["horizon"], "n_bars": c["n_bars"],
                "design_effect": _r(c["design_effect"], 2),
                "q_bh": _r(c["q_bh"], 6),
                "ic_partial_stop": _r(c["ic_partial_stop"], 6),
                "ic_nonoverlap": _r(c["ic_nonoverlap"], 6),
                "se_nonoverlap": _r(c["se_nonoverlap"], 6),
                "status": c["status"],
            },
        )
    for t in terciles:
        ledger.add(
            FAMILY_TERCILE, f"{t['feature']}|h{t['horizon']}",
            stat=t["spread"], se=t["se"], p=t["p"], n=t["n_obs"],
            n_eff=None, mde=mde(t["se"], alpha=ALPHA, power=POWER) if t["se"] else None,
            meta={
                "horizon": t["horizon"], "n_bars": t["n_bars"],
                "ci95": None if t["ci95_lo"] is None else [_r(t["ci95_lo"], 6), _r(t["ci95_hi"], 6)],
                "q_bh": _r(t["q_bh"], 6),
            },
        )
    ledger.add(
        FAMILY_DESCRIPTIVE, "universe",
        stat=len(rows), n=len(decisions),
        meta={
            "files": len(paths), "months": months, "profile": args.profile,
            "labeled": len(labeled), "symbols": len(per_symbol),
            **row_audit,
        },
    )
    ledger.add(
        FAMILY_DESCRIPTIVE, "cross_section_width",
        stat=statistics.median(cs_widths), n=len(ts_all),
        meta={
            "min": cs_widths[0], "median": statistics.median(cs_widths),
            "max": cs_widths[-1], "ts_ge_min_cs": len(cs_sizes),
            "ts_ge_min_cs_pct": round(len(cs_sizes) / len(ts_all), 4) if ts_all else None,
        },
    )
    ledger.add(
        FAMILY_DESCRIPTIVE, "nonoverlap_subsample",
        stat=len(nonoverlap_ts), n=len(ts_all),
        meta={
            "stride_bars": 32, "stride_seconds": NONOVERLAP_STRIDE_SECONDS,
            "rows": len(rows_nonoverlap),
            "frac_ts": round(len(nonoverlap_ts) / len(ts_all), 4) if ts_all else None,
        },
    )

    # ---- 汇总 ----
    ok = [c for c in cells if c["status"] == "ok"]
    sig = [c for c in ok
           if c["q_bh"] is not None and c["q_bh"] < args.bh_q
           and c["ic"] is not None and c["mde_ic"] is not None
           and abs(c["ic"]) > c["mde_ic"] and (c["neff"] or 0) >= MIN_NEFF]
    sig_conservative = [
        c for c in sig
        if c["se_nonoverlap"] is not None
        and abs(c["ic"]) > mde(max(c["se"] or 0.0, c["se_nonoverlap"]), alpha=ALPHA, power=POWER)
    ]
    shapes = {
        f: classify_shape([c["ic"] for c in cells if c["feature"] == f])
        for f in FEATURES
    }
    shape_counts = Counter(shapes.values())
    dominant = shape_counts.most_common(1)[0][0] if shape_counts else None
    # 「有量级」的特征:max|ic| >= 0.015;避免 6 个近零分量把形态分布拖成 flat
    informative = [
        f for f in FEATURES
        if max((abs(c["ic"]) for c in cells if c["feature"] == f and c["ic"] is not None),
               default=0.0) >= 0.015
    ]
    shape_counts_informative = Counter(shapes[f] for f in informative)
    tercile_sig = sum(
        1 for t in terciles if t["q_bh"] is not None and t["q_bh"] < args.bh_q
    )
    nonoverlap_flip = sum(
        1 for c in sig
        if c["ic_nonoverlap"] is not None and c["ic"] * c["ic_nonoverlap"] < 0
    )

    def _de(values):
        vals = [v for v in values if v is not None]
        if not vals:
            return None
        return {
            "mean": round(statistics.fmean(vals), 2),
            "median": round(statistics.median(vals), 2),
            "min": round(min(vals), 2),
            "max": round(max(vals), 2),
        }

    design_summary = {
        "overall": _de([c["design_effect"] for c in cells]),
        "by_horizon": {
            str(h): _de([c["design_effect"] for c in cells if c["horizon"] == h])
            for h in horizons
        },
    }

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # ic_matrix.csv
    matrix_cols = [
        "feature", "horizon", "n_bars", "n_obs", "ic", "se", "neff",
        "design_effect", "mde_ic", "p", "q_bh", "ic_partial_stop",
        "ic_nonoverlap", "se_nonoverlap", "status",
    ]
    with (out_dir / "ic_matrix.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(matrix_cols)
        for c in cells:
            w.writerow([
                c["feature"], c["horizon"], c["n_bars"], c["n_obs"],
                _r(c["ic"], 6), _r(c["se"], 6), _r(c["neff"], 1),
                _r(c["design_effect"], 2), _r(c["mde_ic"], 6), _r(c["p"], 6),
                _r(c["q_bh"], 6), _r(c["ic_partial_stop"], 6),
                _r(c["ic_nonoverlap"], 6), _r(c["se_nonoverlap"], 6),
                c["status"],
            ])

    # ic_by_bar.csv(h=32;全周期版本体量约 6 倍,按约定只落最长周期)
    with (out_dir / "ic_by_bar.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["feature", "horizon", "ts", "date", "ic", "n_symbols"])
        for feature in FEATURES:
            for ts, ic, n in per_bar_h32.get(feature, []):
                w.writerow([feature, 32, ts, _utc_date(ts), round(ic, 6), n])

    # tercile_spread.csv
    with (out_dir / "tercile_spread.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["feature", "horizon", "n_bars", "n_obs", "spread", "se",
                    "ci95_lo", "ci95_hi", "p", "q_bh"])
        for t in terciles:
            w.writerow([
                t["feature"], t["horizon"], t["n_bars"], t["n_obs"],
                _r(t["spread"], 6), _r(t["se"], 6), _r(t["ci95_lo"], 6),
                _r(t["ci95_hi"], 6), _r(t["p"], 6), _r(t["q_bh"], 6),
            ])

    ledger.write(out_dir / "tests_ledger.jsonl")

    elapsed = time.time() - t0
    metrics = {
        "preregistered": {
            "alpha": ALPHA, "power": POWER, "bh_q": args.bh_q,
            "min_cs": args.min_cs, "min_bars_per_cell": MIN_BARS_PER_CELL,
            "min_neff": MIN_NEFF, "iters": args.iters, "block_key": "date",
            "target": "gross_R (barrier, entry=next_open)",
            "nonoverlap_stride_bars": 32,
        },
        "universe": {
            "files": len(paths), "months": months, "profile": args.profile,
            "decisions": len(decisions), "labeled": len(labeled), "rows": len(rows),
            "symbols": len(per_symbol), "timestamps": len(ts_all),
            "dates": len({r["date"] for r in rows}),
            "median_cross_section": statistics.median(cs_widths),
            "nonoverlap_timestamps": len(nonoverlap_ts),
            **row_audit,
        },
        "design_effect_summary": design_summary,
        "feature_coverage": coverage,
        "shape_by_feature": shapes,
        "shape_counts": dict(shape_counts),
        "informative_features": informative,
        "shape_counts_informative": dict(shape_counts_informative),
        "dominant_shape": dominant,
        "n_tests": len(ledger),
        "n_tests_by_family": dict(Counter(r["family"] for r in ledger.rows())),
        "n_cells": len(cells),
        "n_ok": len(ok),
        "n_bh_reject": sum(1 for c in cells if c["q_bh"] is not None and c["q_bh"] < args.bh_q),
        "n_tercile_bh_reject": tercile_sig,
        "n_sig_bh_mde_neff": len(sig),
        "n_sig_conservative_two_se": len(sig_conservative),
        "n_sig_nonoverlap_sign_flip": nonoverlap_flip,
        "significant_cells": [
            {
                "feature": c["feature"], "horizon": c["horizon"],
                "ic": _r(c["ic"], 6), "se": _r(c["se"], 6),
                "mde_ic": _r(c["mde_ic"], 6), "q_bh": _r(c["q_bh"], 6),
                "neff": _r(c["neff"], 1),
                "ic_nonoverlap": _r(c["ic_nonoverlap"], 6),
                "mde_ic_conservative": _r(
                    mde(max(c["se"] or 0.0, c["se_nonoverlap"] or 0.0),
                        alpha=ALPHA, power=POWER), 6),
            }
            for c in sig
        ],
        "elapsed_seconds": round(elapsed, 2),
        "verdict": {
            "summary": (
                f"{len(cells)} 格中 {len(ok)} 格达到最小样本门槛;"
                f"BH q<{args.bh_q} 的 {sum(1 for c in cells if c['q_bh'] is not None and c['q_bh'] < args.bh_q)} 格,"
                f"同时 |ic|>mde 且 neff>={MIN_NEFF} 的 {len(sig)} 格"
                f"(双 SE 取保守后 {len(sig_conservative)} 格)。"
                f"期限结构:13 特征中 {dominant} 最多"
                f"({', '.join(f'{k}={v}' for k, v in sorted(shape_counts.items()))});"
                f"max|ic|≥0.015 的 {len(informative)} 个特征中"
                f"({', '.join(f'{k}={v}' for k, v in sorted(shape_counts_informative.items()))})。"
                f"Tercile spread 族 BH 显著 {tercile_sig} 格。"
            ),
            "note": "仅陈述统计口径与形态,不据此判定是否存在 alpha。",
        },
    }
    (out_dir / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8"
    )

    write_report(out_dir, cells, terciles, shapes, shape_counts, dominant,
                 sig, sig_conservative, metrics, args, horizons)
    print(f"[done] out={out_dir} elapsed={elapsed:.1f}s ledger={len(ledger)}", flush=True)
    print(json.dumps(metrics["verdict"], ensure_ascii=False), flush=True)
    return 0


# --------------------------------------------------------------------------- #
# 报告
# --------------------------------------------------------------------------- #

def write_report(out_dir, cells, terciles, shapes, shape_counts, dominant,
                 sig, sig_conservative, metrics, args, horizons) -> None:
    by_feat = defaultdict(dict)
    for c in cells:
        by_feat[c["feature"]][c["horizon"]] = c

    def tag(c) -> str:
        marks = []
        if c["status"] != "ok":
            marks.append("!")
        if c["q_bh"] is not None and c["q_bh"] < args.bh_q:
            marks.append("q")
        if c["ic"] is not None and c["mde_ic"] is not None and abs(c["ic"]) > c["mde_ic"]:
            marks.append("m")
        return "".join(marks) or " "

    ranked = sorted([c for c in cells if c["ic"] is not None], key=lambda c: -abs(c["ic"]))

    md = [
        "# 分量 × 周期 IC 期限结构矩阵(2026-10-19)",
        "",
        "## 1. 口径",
        "",
        f"- 决策面:`{args.profile}` profile,{','.join(metrics['universe']['months'])},"
        f"{metrics['universe']['files']} 个 `decisions.jsonl`,"
        f"{metrics['universe']['decisions']:,} 行决策 → {metrics['universe']['labeled']:,} 行可标注",
        f"- 特征 {len(FEATURES)} 个:六因子 6 + v2 5 + `score_pct` + `shadow_pct`;"
        f"周期 {horizons} 根 15m",
        "- 目标列:**毛 `R`**(`exit_mode=barrier`,`entry_mode=next_open`),不扣成本",
        f"- IC:**逐 UTC 时间戳横截面** Spearman(同一根 bar 上 ≥{args.min_cs} 个标的),"
        "再对时间取均值;不做日池化",
        f"- 标准误:按 **UTC 日** 块 bootstrap,{args.iters} 次;"
        "`neff=(sd(ic_t)/se_boot)^2`,`design_effect=n_obs/neff`",
        f"- 多重检验:BH q={args.bh_q}(IC 族 78 格内校正);显著性另要求 |ic|>mde 且 neff≥{MIN_NEFF}",
        "- `ic_partial_stop`:逐 bar 用 `partial_spearman(score, R | stop_pct)` 剔除止损宽度影响后的均值",
        "- `ic_nonoverlap`:按 UTC 8 小时网格(每 32 根)子采样的同口径 IC;"
        "`se_nonoverlap` 为其块 bootstrap SE,用于「两个 SE 取保守」复核",
        "",
        "## 2. 结论页",
        "",
        f"- 矩阵格数 **{metrics['n_cells']}**(13 特征 × 6 周期),达到样本门槛(`ok`)"
        f"**{metrics['n_ok']}** 格",
        f"- BH q<{args.bh_q}:**{metrics['n_bh_reject']}** 格",
        f"- 同时满足 BH q<{args.bh_q}、|ic|>mde、neff≥{MIN_NEFF}:**{len(sig)}** 格;"
        f"再用 max(主 SE, 非重叠 SE) 重算 mde 后剩 **{len(sig_conservative)}** 格",
        f"- Tercile spread 族(78 格)BH q<{args.bh_q}:**{metrics['n_tercile_bh_reject']}** 格",
        f"- 期限结构形态(13 特征):**{dominant}**"
        f"({', '.join(f'{k}={v}' for k, v in sorted(shape_counts.items()))})",
        f"- 只看 max|ic|≥0.015 的 {len(metrics['informative_features'])} 个特征:"
        f"{', '.join(f'{k}={v}' for k, v in sorted(metrics['shape_counts_informative'].items()))}"
        f"(近零分量会机械地被归入 flat,故单列)",
        "",
        "## 3. IC 矩阵(数值为 ic,括号内为 se)",
        "",
        "标记:`q`=BH q<门槛,`m`=|ic|>mde,`!`=样本不足",
        "",
        "| 特征 | " + " | ".join(f"h={h}" for h in horizons) + " | 形态 |",
        "|---|" + "---:|" * len(horizons) + "---|",
    ]
    for f in FEATURES:
        line = f"| `{f}` |"
        for h in horizons:
            c = by_feat[f][h]
            line += f" {_fmt(c['ic'], 4)}{tag(c)} ({_fmt(c['se'], 4)}) |"
        line += f" {shapes[f]} |"
        md.append(line)

    md += ["", "## 4. 最强 / 最弱 3 格(按 |ic|)", "",
           "| 排名 | 特征 | 周期 | ic | se | mde | q_bh | neff | ic_partial_stop | ic_nonoverlap |",
           "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for i, c in enumerate(ranked[:3], 1):
        md.append(f"| {i} | `{c['feature']}` | {c['horizon']} | {_fmt(c['ic'], 4)} | "
                  f"{_fmt(c['se'], 4)} | {_fmt(c['mde_ic'], 4)} | {_fmt(c['q_bh'], 4)} | "
                  f"{_fmt(c['neff'], 0)} | {_fmt(c['ic_partial_stop'], 4)} | "
                  f"{_fmt(c['ic_nonoverlap'], 4)} |")
    md += ["", "最弱 3 格(|ic| 最小):", "",
           "| 排名 | 特征 | 周期 | ic | se | mde | q_bh | neff |",
           "|---:|---|---:|---:|---:|---:|---:|---:|"]
    for i, c in enumerate(ranked[-3:][::-1], 1):
        md.append(f"| {i} | `{c['feature']}` | {c['horizon']} | {_fmt(c['ic'], 4)} | "
                  f"{_fmt(c['se'], 4)} | {_fmt(c['mde_ic'], 4)} | {_fmt(c['q_bh'], 4)} | "
                  f"{_fmt(c['neff'], 0)} |")

    md += ["", "## 5. 通过全部门槛的格子", ""]
    if sig:
        md += ["| 特征 | 周期 | ic | se | mde | mde(保守,双 SE) | q_bh | neff | ic_nonoverlap |",
               "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for c in sorted(sig, key=lambda c: -abs(c["ic"])):
            cons = mde(max(c["se"] or 0.0, c["se_nonoverlap"] or 0.0),
                       alpha=ALPHA, power=POWER)
            md.append(f"| `{c['feature']}` | {c['horizon']} | {_fmt(c['ic'], 4)} | "
                      f"{_fmt(c['se'], 4)} | {_fmt(c['mde_ic'], 4)} | {_fmt(cons, 4)} | "
                      f"{_fmt(c['q_bh'], 4)} | {_fmt(c['neff'], 1)} | "
                      f"{_fmt(c['ic_nonoverlap'], 4)} |")
    else:
        md.append("无。")

    de = metrics["design_effect_summary"]["overall"]
    md += ["", "## 6. 设计效应", "",
           f"`design_effect = n_obs/neff` 总体:中位 {de['median'] if de else '-'}、"
           f"均值 {de['mean'] if de else '-'}、区间 "
           f"[{de['min'] if de else '-'}, {de['max'] if de else '-'}]。",
           "",
           "| 周期 | neff 中位 | design_effect 中位 |", "|---:|---:|---:|"]
    for h in horizons:
        sub = [c for c in cells if c["horizon"] == h and c["neff"]]
        md.append(f"| {h} | {statistics.median([c['neff'] for c in sub]):.1f} | "
                  f"{statistics.median([c['design_effect'] for c in sub]):.1f} |")

    md += ["", "## 7. 期限结构形态", "",
           "判定规则(描述性,不参与显著性):|IC| 峰值 <0.01(噪声地板)或极差 ≤ 峰值的 30% 记 "
           "`flat`;内部周期(2–16)最大且高出两端 ≥0.005 记 `mid_peak`;"
           "h=32 的 |IC| ≤ h=1 的 75% 记 `monotonic_decay`,≥125% 记 `monotonic_rise`;"
           "其余 `mixed`。表内 `*` 标记 max|ic|≥0.015 的特征。",
           "",
           "| 特征 | 形态 | " + " | ".join(f"|ic| h={h}" for h in horizons) + " |",
           "|---|---|" + "---:|" * len(horizons)]
    informative = set(metrics.get("informative_features") or [])
    for f in FEATURES:
        mark = "*" if f in informative else ""
        md.append(f"| `{f}` | {shapes[f]}{mark} | " +
                  " | ".join(_fmt(abs(by_feat[f][h]["ic"]), 4) if by_feat[f][h]["ic"] is not None
                             else "-" for h in horizons) + " |")

    md += ["", "## 8. Tercile spread(top − bottom 的 E[R],逐 bar 三分位后按日块 bootstrap)", "",
           "| 特征 | " + " | ".join(f"h={h}" for h in horizons) + " |",
           "|---|" + "---:|" * len(horizons)]
    t_by = defaultdict(dict)
    for t in terciles:
        t_by[t["feature"]][t["horizon"]] = t
    for f in FEATURES:
        md.append(f"| `{f}` | " + " | ".join(_fmt(t_by[f][h]["spread"], 4) for h in horizons) + " |")
    md += ["", f"78 格中 BH q<{args.bh_q} 的 {metrics['n_tercile_bh_reject']} 格;"
               "spread 为逐 bar 三分位后对时间取均值(top−bottom),非池化。"]

    sparse = {f: v for f, v in metrics.get("feature_coverage", {}).items() if v["pct"] < 0.999}
    if sparse:
        pcts = sorted({v["pct"] for v in sparse.values()})
        sparse_dates = sorted({v["dates"] for v in sparse.values()})
        pct_txt = f"{min(pcts):.1%}" if min(pcts) == max(pcts) else f"{min(pcts):.1%}–{max(pcts):.1%}"
        day_txt = (f"{min(sparse_dates)}" if min(sparse_dates) == max(sparse_dates)
                   else f"{min(sparse_dates)}–{max(sparse_dates)}")
        coverage_note = (
            f"- 特征覆盖:{', '.join(f'`{f}`' for f in sparse)} 非空 {pct_txt},"
            f"仅覆盖 {day_txt} 天(其余特征 100%)。"
            f"这些格的 `n_obs` 相应减半,跨族比较需注意时间窗不同。"
        )
    else:
        coverage_note = "- 13 个特征在全部行上均非空。"

    md += ["", "## 9. 偏离与备注", "",
           coverage_note,
           "- `ic_by_bar.csv` 只落 h=32(按任务允许的裁剪),其余周期的逐 bar IC 未落盘。",
           "- `ic_matrix.csv` 在要求列之外追加了 `se_nonoverlap`,用于并列展示两个 SE;"
           "`metrics.json` 的 `n_sig_conservative_two_se` 用保守 SE 重算 mde。",
           "- 非重叠子采样按 UTC 固定 8 小时网格取点(不做逐标的错位抽样,以保住截面宽度);"
           f"命中 {metrics['universe'].get('nonoverlap_timestamps')} / "
           f"{metrics['universe'].get('timestamps')} 个时间戳,即只落在 00/08/16 UTC 三个时点,"
           "除样本量降到 1/32 外还混入时段差异。"
           f"{len(sig)} 个主列显著格中有 {metrics['n_sig_nonoverlap_sign_flip']} 格在该子样本上符号相反;"
           "该子样本仅 143 个时间戳,不足以独立复核或推翻主列,"
           "因此「双 SE 保守」列只用于显示结论对抽样密度/时段的敏感性。",
           "- 日块 bootstrap 的 p 值分辨率为 1/iters;表中 `p=0.0` 表示 2000 次重采样无一跨零,"
           "并非数学上的 0,故相应的 `q_bh=0.0` 同样只是分辨率下限。",
           f"- 运行耗时 {metrics['elapsed_seconds']}s。",
           "",
           "> 本报告只给数字与形态,不替使用者下「是否存在 alpha」的结论。",
           ""]
    (out_dir / "report.md").write_text("\n".join(md), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
