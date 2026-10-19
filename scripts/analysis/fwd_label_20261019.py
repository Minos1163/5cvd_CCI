"""前向标签检验(薄 shim):标注实现在 ``fwdlib``,本文件只保留下游依赖的公开名字。

口径说明见 ``fwdlib/labeler.py``;本文件保证两件事:

1. ``ROUND_TRIP_BPS`` 是本模块**自己的**全局变量。``cost_sensitivity`` / ``tf_uplift``
   通过 ``L.ROUND_TRIP_BPS = x`` 注入成本,包装函数必须在**调用时**读取它并写进
   ``LabelConfig.cost_bps``。若直接 ``from fwdlib import ROUND_TRIP_BPS``,改的只是
   副本,实际仍按 20bps 算,报告却写 8bps —— 这种错误不会报错,只会静默算错。
2. ``label_barrier`` 不涉及成本,纯转发;默认值与旧脚本逐项一致。
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

try:
    from fwdlib import config as _config, features as _features, labeler as _labeler, stats as _stats
except ImportError:  # 下游只把 scripts/analysis 放进 sys.path 时走这条
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from scripts.analysis.fwdlib import (
        config as _config,
        features as _features,
        labeler as _labeler,
        stats as _stats,
    )

LabelConfig = _config.LabelConfig
ATR_STOP_MULT = _config.ATR_STOP_MULT
COST_BREAKEVEN_BUFFER_MULT = _config.COST_BREAKEVEN_BUFFER_MULT
COST_BREAKEVEN_CHECK_BARS = _config.COST_BREAKEVEN_CHECK_BARS
HORIZON_BARS = _config.HORIZON_BARS
MAX_STOP_PCT = _config.MAX_STOP_PCT
MIN_STOP_PCT = _config.MIN_STOP_PCT
POST_TP_STOP_OFFSET = _config.POST_TP_STOP_OFFSET
TP_FRACTIONS = _config.TP_FRACTIONS
TP_LEVELS = _config.TP_LEVELS
TRAILING_R_MULT = _config.TRAILING_R_MULT
TREND_TRIGGER_R = _config.TREND_TRIGGER_R

# 成本注入点:必须留在本模块,且包装函数在「调用时」读取(见模块 docstring)
ROUND_TRIP_BPS = 20.0

SIX_FACTOR_WEIGHTS = _features.SIX_FACTOR_WEIGHTS
FEATURE_KEYS = _features.FEATURE_KEYS


def load_decisions(paths, profile="any"):
    """旧口径转发:``include_v2=False`` 保持 ``feat`` 的键集合与旧脚本一致。"""
    return _features.load_decisions(paths, profile=profile, include_v2=False)


build_bars = _labeler.build_bars
build_quadrant_map = _labeler.build_quadrant_map
resolve_stop = _labeler.resolve_stop
spearman = _stats.spearman
block_bootstrap_mean = _stats.block_bootstrap_mean
_entry_and_start = _labeler.entry_and_start
_extract_features = _features._extract_features
_is_six_factor = _features.is_six_factor


def _inject_cost(cfg=None, **fields):
    """把模块级 ``ROUND_TRIP_BPS`` 写进 cfg,并同步调用参数,避免 fwdlib 的
    「值等于旧默认即视为未覆盖」规则把 cfg 里的默认值当成调用方意图。"""
    base = LabelConfig() if cfg is None else cfg
    updates = {k: v for k, v in fields.items() if v is not None}
    updates["cost_bps"] = float(ROUND_TRIP_BPS)
    return base.replaced(**updates)


def label_barrier(bars, per_symbol, index, d, stop_pct, entry_mode="next_open",
                  horizon=None, cfg=None):
    """纯转发:barrier 不用 cost_bps,不得注入成本。"""
    return _labeler.label_barrier(bars, per_symbol, index, d, stop_pct, entry_mode,
                                  cfg=cfg, horizon=horizon)


def label_ladder(bars, per_symbol, index, d, stop_pct, entry_mode="bar_close",
                 quad_map=None, quadrant_defense=False, q2_tighten=False,
                 post_tp_mode="legacy", horizon=None, cost_breakeven_bars=None, cfg=None):
    cfg = _inject_cost(cfg, entry_mode=entry_mode, post_tp_mode=post_tp_mode,
                       quadrant_defense=quadrant_defense, q2_tighten=q2_tighten)
    return _labeler.label_ladder(
        bars, per_symbol, index, d, stop_pct, entry_mode, quad_map=quad_map,
        quadrant_defense=quadrant_defense, q2_tighten=q2_tighten,
        post_tp_mode=post_tp_mode, horizon=horizon,
        cost_breakeven_bars=cost_breakeven_bars, cfg=cfg,
    )


def run_labeling(decisions, exit_mode="barrier", stop_floor=None, stop_scale=None,
                 entry_mode="next_open", quadrant_defense=False, q2_tighten=False,
                 post_tp_mode="legacy", horizon=None, cost_breakeven_bars=None, cfg=None):
    cfg = _inject_cost(cfg, exit_mode=exit_mode, entry_mode=entry_mode,
                       post_tp_mode=post_tp_mode, quadrant_defense=quadrant_defense,
                       q2_tighten=q2_tighten)
    return _labeler.run_labeling(
        decisions, exit_mode=exit_mode, stop_floor=stop_floor, stop_scale=stop_scale,
        entry_mode=entry_mode, quadrant_defense=quadrant_defense, q2_tighten=q2_tighten,
        post_tp_mode=post_tp_mode, cfg=cfg, horizon=horizon,
        cost_breakeven_bars=cost_breakeven_bars,
    )


def _group(rows, keyfn):
    g = defaultdict(list)
    for r in rows:
        g[keyfn(r)].append(r)
    return g


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

    buckets_def = [
        ("score>=92", lambda d: d["score"] is not None and d["score"] >= 92),
        ("score 82-92", lambda d: d["score"] is not None and 82 <= d["score"] < 92),
        ("score 78-82", lambda d: d["score"] is not None and 78 <= d["score"] < 82),
        ("score 68-78", lambda d: d["score"] is not None and 68 <= d["score"] < 78),
        ("score<68", lambda d: d["score"] is not None and d["score"] < 68),
    ]
    bucket_rows = [{"bucket": name, **s} for name, pred in buckets_def
                   if (s := stats([d for d in labeled if pred(d)]))]

    shadow_rows = [d for d in labeled if d["shadow"] is not None]
    s_buckets = []
    if len(shadow_rows) >= 200:
        vals = sorted(d["shadow"] for d in shadow_rows)
        cuts = [vals[int(len(vals) * q)] for q in (0.2, 0.4, 0.6, 0.8)]
        names = ["Q1(最低)", "Q2", "Q3", "Q4", "Q5(最高)"]
        for i, lab in enumerate(names):
            lo = cuts[i - 1] if i > 0 else -1e9
            hi = cuts[i] if i < len(cuts) else 1e9
            s = stats([d for d in shadow_rows if lo <= d["shadow"] < hi])
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
    overall = stats(labeled)
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


if __name__ == "__main__":
    main()
