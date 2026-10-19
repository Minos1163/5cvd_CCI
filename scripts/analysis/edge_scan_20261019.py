"""Stage 2:全决策面入场条件扫描(IS/OOS + 分块 bootstrap + BH-FDR + 稳健性 + 闸门消融)。

问题:在 15m + 20bps 往返成本下,是否存在某个条件子集使 `E[R_net]` 的 80% 下界 > 0?

方法要点(全部预登记,事后不许改):
  - 总体:六因子 profile 全决策面(2026-06-26 → 2026-10-18),不做 233 笔小样本
  - 出场:ladder 模式(复刻线上 1.2/2.0/3.0R + 保本 + 8 根成本超时 + 32 根上限)
  - 止损:按场景 floor(默认 1.5%,另跑 2.0%)
  - IS = 2026-06-26 ~ 2026-09-13;OOS = 2026-09-14 ~ 2026-10-18
  - 候选规则 <= 320 条;IS 用「下界」排序而非均值;OOS 要求 下界>0 且 n>=300 且方向一致 且 BH-FDR q=0.10
  - 稳健性:留一标的 / 留一月 / 剔除 10-04 重启前后 3 天
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fwd_label_20261019 as L  # noqa: E402

NUMERIC_FEATURES = (
    "score_pct", "shadow_pct", "atr_pct", "log_qv", "extreme_pos", "symbol_exposure",
    "total_exposure", "daily_profit", "vol_scale", "btc_daily", "btc_weekly", "bar_pos",
    "trend_ema_context", "ema_50_quality", "ema_momentum", "ema_200_gate", "direction_1h",
    "background_4h", "quality_30m", "trigger_15m", "market_regime", "volatility_stop",
    "liquidity_execution", "cvd_flow", "fib_action_cap", "fibonacci_location",
    "price_action_structure", "flow_cvd_confirmation", "cci_momentum_quality",
    "risk_reward_geometry",
)

GATE_REASONS = (
    "FIB_PA_ARCHITECTURE_WEIGHTS",
    "SIDE_THRESHOLD_OFFSET_LONG",
    "SYMBOL_BLACKLISTED",
    "SYMBOL_WATCH_ONLY",
    "PROBE_BELOW_FIBONACCI_LOCATION_MINIMUM",
    "PROBE_BELOW_RISK_REWARD_GEOMETRY_MINIMUM",
    "FIB_EXTENSION_EXHAUSTION_BLOCK",
    "DAILY_TRADE_BUDGET_USED",
)

IS_END = "2026-09-13"
OOS_START = "2026-09-14"


def mean(v):
    return statistics.fmean(v) if v else None


def ci_and_p(rows, iters=2000, seed=7, with_p=True):
    """分块 bootstrap:返回 80% 区间与单侧 p(均值<=0 的 bootstrap 比例)。

    用块的 (sum, count) 重采样而不是摊平全部样本,复杂度从 O(iters*n) 降到 O(iters*blocks)。
    """
    sums = defaultdict(float)
    counts = defaultdict(int)
    for d in rows:
        sums[d["block"]] += d["R_net"]
        counts[d["block"]] += 1
    blocks = [(sums[b], counts[b]) for b in sums if counts[b] > 0]
    if len(blocks) < 8:
        return None, None, None
    import random
    rng = random.Random(seed)
    means = []
    for _ in range(iters):
        total = 0.0
        count = 0
        for _ in range(len(blocks)):
            s, c = blocks[rng.randrange(len(blocks))]
            total += s
            count += c
        if count:
            means.append(total / count)
    if not means:
        return None, None, None
    means.sort()
    lo = means[int(0.10 * len(means))]
    hi = means[int(0.90 * len(means))]
    p = None
    if with_p:
        p = sum(1 for m in means if m <= 0) / len(means)
    return lo, hi, p


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


def build_rules(is_rows):
    """构造候选规则:单因子阈值 + 类别(<=200 条)。"""
    rules = []
    for feat in NUMERIC_FEATURES:
        vals = sorted(d["feat"].get(feat) for d in is_rows)
        vals = [v for v in vals if v is not None and v == v and abs(v) != float("inf")]
        if len(vals) < 500 or vals[0] == vals[-1]:
            continue
        for q in (0.2, 0.5, 0.8):
            t = vals[int(q * (len(vals) - 1))]
            if t in (vals[0], vals[-1]):
                continue
            rules.append({
                "name": f"{feat}<={t:.4g}",
                "pred": (lambda r, feat=feat, t=t: _val(r, feat) is not None and _val(r, feat) <= t),
            })
            rules.append({
                "name": f"{feat}>{t:.4g}",
                "pred": (lambda r, feat=feat, t=t: _val(r, feat) is not None and _val(r, feat) > t),
            })
    for quad in ("Q1", "Q2", "Q3", "Q4"):
        rules.append({"name": f"quadrant={quad}", "pred": (lambda r, q=quad: r.get("quadrant") == q)})
    for side in ("LONG", "SHORT"):
        rules.append({"name": f"side={side}", "pred": (lambda r, s=side: r.get("side") == s)})
    for name, lo_h, hi_h in (("hour_0_7", 0, 8), ("hour_8_15", 8, 16), ("hour_16_23", 16, 24)):
        rules.append({"name": name, "pred": (lambda r, a=lo_h, b=hi_h: a <= r["feat"]["hour"] < b)})
    return rules


def build_pair_rules(single_eval, name2rule, limit=8):
    """把 IS 表现最好的前 limit 个规则(按特征去重)两两合取,补上交互项。"""
    best_by_feat = {}
    for r in single_eval:
        feat = r["rule"].split("<=")[0].split(">")[0]
        if feat not in best_by_feat:
            best_by_feat[feat] = r["rule"]
        if len(best_by_feat) >= limit:
            break
    names = list(best_by_feat.values())[:limit]
    pairs = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = name2rule[names[i]]["pred"], name2rule[names[j]]["pred"]
            pairs.append({
                "name": f"({names[i]})&({names[j]})",
                "pred": (lambda r, f1=a, f2=b: f1(r) and f2(r)),
            })
    return pairs


def _val(row, feat):
    v = row["feat"].get(feat)
    if v is None or v != v or abs(v) == float("inf"):
        return None
    return v


def apply_rule(rows, rule):
    pred = rule["pred"]
    return [d for d in rows if pred(d)]


def eval_rule(rows, rule, min_n):
    sub = apply_rule(rows, rule)
    if len(sub) < min_n:
        return None
    lo, hi, p = ci_and_p(sub)
    return {
        "rule": rule["name"],
        "n": len(sub),
        "E_R": round(mean([d["R"] for d in sub]), 4),
        "E_Rnet": round(mean([d["R_net"] for d in sub]), 4),
        "ci80": None if lo is None else [round(lo, 4), round(hi, 4)],
        "p": None if p is None else round(p, 4),
        "blocks": len({d["block"] for d in sub}),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--logs", default="logs")
    ap.add_argument("--months", default="2026-06,2026-07,2026-08,2026-09,2026-10")
    ap.add_argument("--profile", default="six_factor")
    ap.add_argument("--floor", type=float, nargs="+", default=[0.015, 0.020])
    ap.add_argument("--exit-mode", default="ladgex", choices=["ladder", "ladgex"],
                    help="ladgex = trend_capture 追踪 + Q2 收紧 + Q3/Q4 防御(与线上账本一致率 90%%)")
    ap.add_argument("--out", default="reports/analysis/edge-scan-20261019")
    ap.add_argument("--top-k", type=int, default=12)
    args = ap.parse_args()

    months = [m.strip() for m in args.months.split(",") if m.strip()]
    paths = []
    for m in months:
        paths += sorted(Path(args.logs).glob(f"{m}/*/decisions.jsonl"))
    decisions = L.load_decisions([str(p) for p in paths], profile=args.profile)
    print(f"loaded decisions={len(decisions)}", flush=True)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    results = {"universe": {"rows": len(decisions)}, "floors": {}}

    for floor in args.floor:
        if args.exit_mode == "ladgex":
            labeled, *_ = L.run_labeling(
                decisions, exit_mode="ladder", stop_floor=floor, entry_mode="bar_close",
                post_tp_mode="trend_capture", quadrant_defense=True, q2_tighten=True,
            )
        else:
            labeled, *_ = L.run_labeling(
                decisions, exit_mode="ladder", stop_floor=floor, entry_mode="bar_close",
                post_tp_mode="legacy",
            )
        is_rows = [d for d in labeled if d["date"] <= IS_END]
        oos_rows = [d for d in labeled if d["date"] >= OOS_START]
        print(f"[floor={floor}] is={len(is_rows)} oos={len(oos_rows)} "
              f"is_E_net={mean([d['R_net'] for d in is_rows]):+.4f} "
              f"oos_E_net={mean([d['R_net'] for d in oos_rows]):+.4f}", flush=True)

        base = {
            "is": {"n": len(is_rows), "E_Rnet": round(mean([d["R_net"] for d in is_rows]), 4),
                   "E_R": round(mean([d["R"] for d in is_rows]), 4)},
            "oos": {"n": len(oos_rows), "E_Rnet": round(mean([d["R_net"] for d in oos_rows]), 4),
                    "E_R": round(mean([d["R"] for d in oos_rows]), 4)},
        }
        lo_b, hi_b, _ = ci_and_p(oos_rows)
        base["oos"]["ci80"] = None if lo_b is None else [round(lo_b, 4), round(hi_b, 4)]

        rules = build_rules(is_rows)
        print(f"  candidate rules={len(rules)}", flush=True)
        is_eval = []
        for rule in rules:
            r = eval_rule(is_rows, rule, min_n=1000)
            if r and r["ci80"]:
                is_eval.append(r)
        is_eval.sort(key=lambda r: r["ci80"][0], reverse=True)
        name2rule = {r["name"]: r for r in rules}
        for pr in build_pair_rules(is_eval, name2rule):
            r = eval_rule(is_rows, pr, min_n=1000)
            if r and r["ci80"]:
                is_eval.append(r)
                name2rule[pr["name"]] = pr
        is_eval.sort(key=lambda r: r["ci80"][0], reverse=True)
        top = is_eval[: args.top_k]
        print(f"  is-evaluated={len(is_eval)} top-first={top[0]['rule'] if top else None} "
              f"lb={top[0]['ci80'][0] if top else None}", flush=True)

        oos_eval = []
        for t in top:
            r = eval_rule(oos_rows, name2rule[t["rule"]], min_n=300)
            if r is None:
                oos_eval.append({**t, "ok": False, "reject": "n_oos<300"})
                continue
            r["ok"] = True
            r["is"] = {k: t[k] for k in ("n", "E_R", "E_Rnet", "ci80")}
            oos_eval.append(r)

        cand_p = [(i, o["p"]) for i, o in enumerate(oos_eval) if o.get("ok") and o.get("p") is not None]
        qs = {i: q for (i, _), q in zip(cand_p, bh_qvalues([p for _, p in cand_p]))}

        passes = []
        for i, o in enumerate(oos_eval):
            if not o.get("ok"):
                continue
            q = qs.get(i)
            o["q"] = None if q is None else round(q, 4)
            reasons = []
            if o["ci80"][0] <= 0:
                reasons.append("oos_lb<=0")
            if o["n"] < 300:
                reasons.append("n_oos<300")
            if o["E_Rnet"] <= o["is"]["E_Rnet"] - 0.10:
                reasons.append("effect_decay>0.10R")
            if q is not None and q > 0.10:
                reasons.append("bh_q>0.10")
            o["reject"] = ",".join(reasons) if reasons else None
            if not reasons:
                passes.append(o["rule"])

        # 稳健性(只对通过者)
        robust = {}
        for name in passes:
            rule = name2rule[name]
            sub_rows = [d for d in oos_rows]
            lo_all, _, _ = ci_and_p(apply_rule(sub_rows, rule))
            per_symbol = {}
            for sym in sorted({d["symbol"] for d in oos_rows}):
                s = [d for d in oos_rows if d["symbol"] != sym]
                sub = apply_rule(s, rule)
                if len(sub) >= 200:
                    per_symbol[sym] = round(mean([d["R_net"] for d in sub]), 4)
            per_month = {}
            for mon in sorted({d["month"] for d in oos_rows}):
                s = [d for d in oos_rows if d["month"] != mon]
                sub = apply_rule(s, rule)
                if len(sub) >= 200:
                    per_month[mon] = round(mean([d["R_net"] for d in sub]), 4)
            robust[name] = {
                "oos_lb": None if lo_all is None else round(lo_all, 4),
                "leave_one_symbol_min": min(per_symbol.values()) if per_symbol else None,
                "leave_one_symbol": per_symbol,
                "leave_one_month": per_month,
            }

        # 闸门消融:按 reasons 分组
        gate_ablation = {}
        reason_map = defaultdict(list)
        for d in oos_rows:
            for rr in (d.get("reasons") or []):
                for g in GATE_REASONS:
                    if rr.startswith(g):
                        reason_map[g].append(d)
                        break
        for g in GATE_REASONS:
            sub = reason_map.get(g) or []
            if len(sub) < 100:
                gate_ablation[g] = {"n": len(sub), "note": "n<100"}
                continue
            s = {"n": len(sub), "E_Rnet": round(mean([d["R_net"] for d in sub]), 4),
                 "E_R": round(mean([d["R"] for d in sub]), 4)}
            lo, hi, _ = ci_and_p(sub, iters=800)
            s["ci80"] = None if lo is None else [round(lo, 4), round(hi, 4)]
            gate_ablation[g] = s

        results["floors"][f"{floor:.3f}"] = {
            "baseline": base,
            "is_candidates": is_eval,
            "oos_top": oos_eval,
            "passes": passes,
            "robustness": robust,
            "gate_ablation": gate_ablation,
            "by_symbol_oos": {
                sym: {"n": len(sub), "E_Rnet": round(mean([d["R_net"] for d in sub]), 4)}
                for sym, sub in sorted(L._group(oos_rows, lambda d: d["symbol"]).items())
                if len(sub) >= 200
            },
            "by_quadrant_oos": {
                str(q): {"n": len(sub), "E_Rnet": round(mean([d["R_net"] for d in sub]), 4)}
                for q, sub in sorted(L._group(oos_rows, lambda d: d.get("quadrant") or "NA").items())
            },
        }
        del labeled

    (out_dir / "scan.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    # 报告
    md = ["# 入场条件扫描：全决策面上的条件子集是否存在正期望", ""]
    for floor, block in results["floors"].items():
        md += [f"## 止损下限 {float(floor)*100:.1f}%", "",
               f"- IS: n={block['baseline']['is']['n']:,}，`E[R_net]={block['baseline']['is']['E_Rnet']:+.4f}`",
               f"- OOS: n={block['baseline']['oos']['n']:,}，`E[R_net]={block['baseline']['oos']['E_Rnet']:+.4f}`，"
               f"80% CI {block['baseline']['oos']['ci80']}",
               f"- 候选 {len(block['is_candidates'])} 条，进 OOS {len(block['oos_top'])} 条，通过 {len(block['passes'])} 条",
               "", "| 规则 | n_IS | E[R_net]_IS | n_OOS | E[R_net]_OOS | OOS 80% CI | q | 否决原因 |",
               "|---|---:|---:|---:|---:|---|---:|---|"]
        for o in block["oos_top"]:
            if not o.get("ok"):
                md.append(f"| `{o['rule']}` | {o['is']['n']:,} | {o['is']['E_Rnet']:+.3f} "
                          f"| - | - | - | - | n_oos<300 |")
            else:
                md.append(
                    f"| `{o['rule']}` | {o['is']['n']:,} | {o['is']['E_Rnet']:+.3f} | {o['n']:,} "
                    f"| {o['E_Rnet']:+.3f} | {o.get('ci80')} | {o.get('q', '-')} | {o.get('reject') or '**通过**'} |"
                )
        md += ["", "### 闸门消融（OOS，被该闸门拦下的行）", "",
               "| 闸门 | 被拦 n | `E[R_net]` | 80% CI |", "|---|---:|---:|---|"]
        for g, s in block["gate_ablation"].items():
            if "E_Rnet" in s:
                md.append(f"| `{g}` | {s['n']:,} | {s['E_Rnet']:+.4f} | {s.get('ci80')} |")
            else:
                md.append(f"| `{g}` | {s['n']} | - | n<100 |")
        md.append("")
    (out_dir / "oos_report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({k: {"passes": v["passes"], "oos_base": v["baseline"]["oos"]["E_Rnet"]}
                      for k, v in results["floors"].items()}, ensure_ascii=False))


if __name__ == "__main__":
    main()
