"""Stage 1:stop_pct 下限影子实验。

全决策面(六因子 profile,2026-06-26 → 2026-10-18)上,把止损宽度按场景抬高/放大,
用两种出场口径重新标注,给出 E[R_net] 随止损下限的曲线与 required_edge 表。

预登记判据(写死在 PREREGISTERED 里,事后不许改):
  R1 通过:存在某 floor 使 E[R_net] 的 80% 分块 bootstrap 下界 > 0
  R2 否决:全部场景下界 <= 0 → 抬下限单独不构成正收益,转 required_edge 靶子

用法:
  python scripts/analysis/stop_floor_20261019.py
  python scripts/analysis/stop_floor_20261019.py --exit-modes ladder --months 2026-09,2026-10
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fwd_label_20261019 as L  # noqa: E402

SCENARIOS = (
    ("baseline", None, None),
    ("floor_0.75", 0.0075, None),
    ("floor_1.00", 0.0100, None),
    ("floor_1.25", 0.0125, None),
    ("floor_1.50", 0.0150, None),
    ("floor_2.00", 0.0200, None),
    ("floor_2.50", 0.0250, None),
    ("scale_1.25", None, 1.25),
    ("scale_1.50", None, 1.50),
)

PREREGISTERED = {
    "R1_pass": "存在场景 E[R_net] 的 80% 分块 bootstrap 下界 > 0",
    "R2_reject": "全部场景下界 <= 0 → 抬下限单独不构成正收益,不部署,转 required_edge 表",
    "select_rule": "R1 命中时取「下界最高」的场景,不取均值最高",
    "ladder_consistency": "ladder 模式全样本 E[R] 与 230 笔真实成交反推均值 R 之差须 <= 0.05R",
}

COST_TARGETS = (0.10, 0.15, 0.20, 0.30)
STOP_BUCKETS = (
    ("<=0.60%", 0.0, 0.006),
    ("0.60-0.80%", 0.006, 0.008),
    ("0.80-1.10%", 0.008, 0.011),
    ("1.10-1.60%", 0.011, 0.016),
    ("1.60-2.20%", 0.016, 0.022),
    (">2.20%", 0.022, 9.9),
)


def _stats(rows):
    if not rows:
        return None
    R = [d["R"] for d in rows]
    Rn = [d["R_net"] for d in rows]
    return {
        "n": len(rows),
        "hit": round(sum(1 for x in R if x > 0) / len(R), 4),
        "E_R": round(statistics.fmean(R), 4),
        "cost_R": round(statistics.fmean([d["cost_r"] for d in rows]), 4),
        "E_Rnet": round(statistics.fmean(Rn), 4),
        "net_win": round(sum(1 for x in Rn if x > 0) / len(Rn), 4),
    }


def _ci(rows):
    by_block = defaultdict(list)
    for d in rows:
        by_block[d["block"]].append(d["R_net"])
    ci = L.block_bootstrap_mean(dict(by_block))
    if ci is None:
        return None, None, None
    sd = statistics.pstdev([statistics.fmean(v) for v in by_block.values() if v])
    return round(ci[0], 4), round(ci[1], 4), round(sd, 4)


def summarize(rows):
    out = dict(_stats(rows) or {})
    lo, hi, sd = _ci(rows)
    out["ci80"] = [lo, hi]
    out["block_sd"] = sd
    out["blocks"] = len({d["block"] for d in rows})
    out["reasons"] = dict(Counter(d["reason"] for d in rows).most_common())
    out["by_month"] = {k: _stats(v) for k, v in sorted(L._group(rows, lambda d: d["month"]).items())}
    out["by_quadrant"] = {str(k): _stats(v) for k, v in sorted(
        L._group(rows, lambda d: d["quadrant"] or "NA").items())}
    buckets = []
    for name, lo_b, hi_b in STOP_BUCKETS:
        sub = [d for d in rows if lo_b <= d["stop_pct_eff"] < hi_b]
        s = _stats(sub)
        if s:
            buckets.append({"bucket": name, **s})
    out["by_stop_width"] = buckets
    out["cost_coverage"] = {
        f"cost_r<={t}": round(sum(1 for d in rows if d["cost_r"] <= t) / len(rows), 4)
        for t in COST_TARGETS
    }
    return out


MODE_CONFIG = {
    # barrier: 对称 ±1R 障碍,与系统出场无关,用于「结构上 E[R] 是否为零」
    "barrier": dict(exit_mode="barrier", post_tp_mode="legacy", quadrant_defense=False, q2_tighten=False),
    # ladder: 复刻 TP 阶梯 + 保本 + 成本超时 + 32 根上限(机械口径,不含象限防御)
    "ladder": dict(exit_mode="ladder", post_tp_mode="legacy", quadrant_defense=False, q2_tighten=False),
    # ladgex: 再叠加 trend_capture 追踪 + Q2 收紧 + Q3/Q4 防御,与线上账本一致率 90%(见 ladder_consistency.json)
    "ladgex": dict(exit_mode="ladder", post_tp_mode="trend_capture", quadrant_defense=True, q2_tighten=True),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--logs", default="logs")
    ap.add_argument("--months", default="2026-06,2026-07,2026-08,2026-09,2026-10")
    ap.add_argument("--profile", default="six_factor")
    ap.add_argument("--exit-modes", default="barrier,ladder,ladgex")
    ap.add_argument("--out", default="reports/analysis/stop-floor-20261019")
    args = ap.parse_args()

    months = [m.strip() for m in args.months.split(",") if m.strip()]
    paths = []
    for m in months:
        paths += sorted(Path(args.logs).glob(f"{m}/*/decisions.jsonl"))
    decisions = L.load_decisions([str(p) for p in paths], profile=args.profile)
    print(f"loaded decisions={len(decisions)} files={len(paths)}", flush=True)
    if not decisions:
        raise SystemExit("no decisions")

    stops = sorted(d["stop_pct"] for d in decisions if d.get("stop_pct"))
    pct = lambda q: stops[int(q * (len(stops) - 1))]
    universe = {
        "rows": len(decisions),
        "symbols": len({d["symbol"] for d in decisions}),
        "days": len({d["ts"] // 86400 for d in decisions}),
        "stop_pct_p10": round(pct(0.10), 5),
        "stop_pct_p50": round(pct(0.50), 5),
        "stop_pct_p90": round(pct(0.90), 5),
        "stop_pct_mean": round(statistics.fmean(stops), 5),
    }

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    all_scen = {}
    for mode in [m.strip() for m in args.exit_modes.split(",") if m.strip()]:
        cfg = MODE_CONFIG[mode]
        entry_mode = "bar_close" if cfg["exit_mode"] == "ladder" else "next_open"
        for name, floor, scale in SCENARIOS:
            labeled, *_ = L.run_labeling(
                decisions, stop_floor=floor, stop_scale=scale, entry_mode=entry_mode, **cfg
            )
            summary = summarize(labeled)
            key = f"{mode}|{name}"
            all_scen[key] = summary
            print(
                f"[{key}] n={summary['n']} hit={summary['hit']} E_R={summary['E_R']} "
                f"cost={summary['cost_R']} E_net={summary['E_Rnet']} ci={summary['ci80']}",
                flush=True,
            )
            del labeled

    # required_edge:每个止损档需要多少 E[R] 才能让下界 > 0
    required = {}
    for key, s in all_scen.items():
        lo, hi = s["ci80"]
        if lo is None:
            continue
        required[key] = {
            "E_R": s["E_R"],
            "cost_R": s["cost_R"],
            "E_Rnet": s["E_Rnet"],
            "ci80_lo": lo,
            "required_ER_breakeven": round(s["cost_R"], 4),
            "required_ER_ci_positive": round(s["cost_R"] + max(0.0, s["E_Rnet"] - lo), 4),
        }

    passed = [k for k, s in all_scen.items() if s["ci80"][0] is not None and s["ci80"][0] > 0]
    verdict = "R1_PASS" if passed else "R2_REJECT"

    result = {
        "universe": universe,
        "preregistered": PREREGISTERED,
        "verdict": verdict,
        "passing_scenarios": passed,
        "scenarios": all_scen,
        "required_edge": required,
    }
    (out_dir / "metrics.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    rows = ["scenario,n,hit,E_R,cost_R,E_Rnet,ci80_lo,ci80_hi,net_win"]
    for key, s in all_scen.items():
        rows.append(",".join(str(x) for x in (
            key, s["n"], s["hit"], s["E_R"], s["cost_R"], s["E_Rnet"],
            s["ci80"][0], s["ci80"][1], s["net_win"])))
    (out_dir / "floor_curve.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")

    # 人读报告
    def sgn(v):
        return "−" if (v is not None and v < 0) else "+"

    md = [
        "# stop_pct 下限影子实验：E[R_net] 随止损宽度的曲线",
        "",
        f"**裁决：{verdict}**" + (f"（通过场景：{', '.join(passed)}）" if passed else "（全部场景下界 ≤ 0）"),
        "",
        f"- 样本：{universe['rows']:,} 条决策 / {universe['symbols']} 标的 / 六因子 profile",
        f"- 止损中位 {universe['stop_pct_p50']*100:.2f}%、均值 {universe['stop_pct_mean']*100:.2f}%",
        f"- 成本口径：往返 {L.ROUND_TRIP_BPS:.0f}bps，`cost_R = 0.002 / stop_pct`",
        "",
        "## 场景曲线",
        "",
        "| 场景 | n | 命中率 | `E[R]` | `cost_R` | `E[R_net]` | 80% CI | 净胜率 |",
        "|---|---:|---:|---:|---:|---:|---|---:|",
    ]
    for key, s in all_scen.items():
        md.append(
            f"| {key} | {s['n']:,} | {s['hit']*100:.1f}% | {s['E_R']:+.3f} | {s['cost_R']:.3f} "
            f"| **{s['E_Rnet']:+.3f}** | [{s['ci80'][0]:+.3f}, {s['ci80'][1]:+.3f}] | {s['net_win']*100:.1f}% |"
        )
    md += ["", "## 需要多少 edge 才打平", "",
           "| 场景 | 打平所需 `E[R]` | 下界转正所需 `E[R]` | 覆盖率 `cost_R≤0.20` | `cost_R≤0.10` |",
           "|---|---:|---:|---:|---:|"]
    for key, s in all_scen.items():
        rq = required.get(key, {})
        md.append(
            f"| {key} | {rq.get('required_ER_breakeven')} | {rq.get('required_ER_ci_positive')} "
            f"| {s['cost_coverage']['cost_r<=0.2']*100:.1f}% | {s['cost_coverage']['cost_r<=0.1']*100:.1f}% |"
        )
    (out_dir / "report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({"verdict": verdict, "passing": passed}, ensure_ascii=False))


if __name__ == "__main__":
    main()
