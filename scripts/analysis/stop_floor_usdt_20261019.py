"""WS1-1A: stop_pct 下限抬升的 USDT 口径验收(零行为改动)。

问题
----
`ladgex|baseline` -> `ladgex|floor_1.50` 的 `E[R_net]` 从 -0.284R 改善到 -0.124R,
但 `1R = final_notional * stop_pct`, 而 `final_notional = min(raw, lev_cap, remaining)`。
抬下限时:
  - raw_notional / leveraged_cap_notional 都与 stop_pct 成反比 => 名义额缩小 => 1R 守恒
  - remaining_exposure_notional 与 stop_pct 无关   => 名义额不变 => 1R 随 stop 放大
所以 R 口径的改善不能直接换算成 USDT: 亏的 R 少了, 但每个 R 更贵了。

本脚本逐笔重算 1R, 给出权益口径的期望盈亏, 以及把「R 口径改善」换算到
「USDT 口径改善」的真实折扣系数。

预登记判据(写死在常量里, 输出回显)
----
  P1  sum(E[R_net] * 1R) 的改善 >= P1_MIN_IMPROVEMENT (20%)
  P2  单笔最大 1R_new <= NOMINAL_EQUITY * P2_MAX_R1_PCT (eq 的 0.30%)
任一不满足 => 不进 1B(不抬线上下限)。

样本口径
--------
`metadata.risk_budget` 只在 2026-09 起落盘, 因此:
  - 精确臂(exact): 同时有 action in {DIRECT,PROBE} + risk_allowed + risk_budget 的行,
    逐笔 1R 可精确重算(用 raw/lev/rem 三个 cap 各自随 stop 的重标定)。
  - 对照臂(R-only): 全部可执行行, 只报 E[R_net] 的 R 口径改善, 不做 USDT 换算。
两臂分列, 不得混用。

用法
----
  python scripts/analysis/stop_floor_usdt_20261019.py
  python scripts/analysis/stop_floor_usdt_20261019.py --floor 0.020 --exit-profile ladder
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fwd_label_20261019 as L  # noqa: E402

# ---- 预登记判据(勿事后修改; 改了就写进报告) ----
P1_MIN_IMPROVEMENT = 0.20
P2_MAX_R1_PCT = 0.0030
NOMINAL_EQUITY = 10_000.0
REPORT_WINDOW_DAYS = 30.0

STOP_CEIL = 0.040  # EntryChainConfig.max_stop_pct; floor 只升不降, 上限保持

EXIT_PROFILES = {
    # 线上出场口径的三档近似; ladgex = 当前最贴近线上的一项
    "ladgex": dict(exit_mode="ladder", post_tp_mode="trend_capture",
                   quadrant_defense=True, q2_tighten=True, entry_mode="bar_close"),
    "ladder": dict(exit_mode="ladder", post_tp_mode="legacy",
                   quadrant_defense=False, q2_tighten=False, entry_mode="bar_close"),
    "barrier": dict(exit_mode="barrier"),
}


def load_risk_budget(paths):
    """(symbol, kline_ts) -> risk_budget 快照(含三个 cap 的重标定底座)。"""
    out = {}
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
                rb = (r.get("metadata") or {}).get("risk_budget") or {}
                if not rb:
                    continue
                kline = r.get("kline") or {}
                ts = kline.get("timestamp")
                sym = r.get("symbol")
                if ts is None or not sym:
                    continue
                out[(sym, int(ts))] = {
                    "stop_pct": _f(rb.get("stop_pct")),
                    "final_notional": _f(rb.get("final_notional")),
                    "raw_notional": _f(rb.get("raw_notional")),
                    "lev_notional": _f(rb.get("leveraged_cap_notional")),
                    "rem_notional": _f(rb.get("remaining_exposure_notional")),
                    "binding_cap": rb.get("binding_cap"),
                    "leverage": rb.get("selected_leverage") or r.get("leverage"),
                    "action": r.get("action"),
                    "risk_allowed": bool(r.get("risk_allowed")),
                    "channel": r.get("entry_channel"),
                }
    return out


def _f(v):
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def resized_1r(snap, stop_old, stop_new):
    """按三个 cap 各自对 stop 的依赖重新标定, 返回 (final_notional_new, 1R_old, 1R_new)。

    raw = eq*risk_pct/stop        -> 与 stop 成反比
    lev = eq*0.0075/(stop*lev)    -> 与 stop 成反比
    rem = (cap-exposure)*eq       -> 与 stop 无关
    """
    if not stop_old or not stop_new or stop_old <= 0 or stop_new <= 0:
        return None
    final_old = snap["final_notional"]
    if final_old is None or final_old <= 0:
        return None
    ratio = stop_old / stop_new
    raw_new = (snap["raw_notional"] or 0.0) * ratio
    lev_new = (snap["lev_notional"] or 0.0) * ratio
    rem_new = snap["rem_notional"] if snap["rem_notional"] is not None else float("inf")
    candidates = [c for c in (raw_new, lev_new, rem_new) if c is not None]
    if not candidates:
        return None
    final_new = max(0.0, min(candidates))
    return final_new, final_old * stop_old, final_new * stop_new


def label(decisions, profile_cfg, stop_floor):
    kwargs = dict(profile_cfg)
    return L.run_labeling(decisions, stop_floor=stop_floor, **kwargs)[0]


def summarize(rows):
    if not rows:
        return None
    R = [r["R"] for r in rows]
    Rn = [r["R_net"] for r in rows]
    return {
        "n": len(rows),
        "hit": round(sum(1 for x in R if x > 0) / len(R), 4),
        "E_R": round(statistics.fmean(R), 4),
        "E_Rnet": round(statistics.fmean(Rn), 4),
        "cost_R": round(statistics.fmean([r["cost_r"] for r in rows]), 4),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--logs", default="logs")
    ap.add_argument("--months", default="2026-06,2026-07,2026-08,2026-09,2026-10")
    ap.add_argument("--profile", default="six_factor", choices=["any", "six_factor"])
    ap.add_argument("--stop-profile", default="six_factor",
                    help="保留给将来扩展; 当前与 --profile 同义")
    ap.add_argument("--exit-profile", default="ladgex", choices=sorted(EXIT_PROFILES))
    ap.add_argument("--floor", type=float, default=0.015)
    ap.add_argument("--out", default="reports/analysis/stop-floor-usdt-20261019")
    args = ap.parse_args()

    months = [m.strip() for m in args.months.split(",") if m.strip()]
    paths = []
    for m in months:
        paths += sorted(Path(args.logs).glob(f"{m}/*/decisions.jsonl"))
    if not paths:
        raise SystemExit("no decisions.jsonl found")

    cfg = EXIT_PROFILES[args.exit_profile]
    decisions = L.load_decisions([str(p) for p in paths], profile=args.profile)
    rb_map = load_risk_budget(paths)
    print(f"decisions={len(decisions)} risk_budget_snapshots={len(rb_map)} exit_profile={args.exit_profile}")

    base = label(decisions, cfg, None)
    lifted = label(decisions, cfg, args.floor)
    print(f"labeled base={len(base)} lifted={len(lifted)}")

    base_by = {(d["symbol"], d["ts"]): d for d in base}
    lifted_by = {(d["symbol"], d["ts"]): d for d in lifted}
    exec_base = [d for d in base if d.get("action") in ("DIRECT", "PROBE") and d.get("risk_allowed")]
    exec_lift = [lifted_by[(d["symbol"], d["ts"])] for d in exec_base
                 if (d["symbol"], d["ts"]) in lifted_by]

    # ---- 对照臂: 只算 R ----
    r_only = {
        "n": len(exec_base),
        "baseline": summarize(exec_base),
        "lifted": summarize(exec_lift),
    }
    if r_only["baseline"] and r_only["lifted"]:
        b0 = r_only["baseline"]["E_Rnet"]
        b1 = r_only["lifted"]["E_Rnet"]
        r_only["E_Rnet_improvement"] = None if b0 == 0 else round((b1 - b0) / abs(b0), 4)

    # ---- 精确臂: 逐笔 1R ----
    trades = []
    for d in exec_base:
        key = (d["symbol"], d["ts"])
        snap = rb_map.get(key)
        if not snap:
            continue
        lf = lifted_by.get(key)
        if lf is None:
            continue
        stop_old = snap["stop_pct"] or d.get("stop_pct")
        if not stop_old:
            continue
        stop_new = min(STOP_CEIL, max(stop_old, args.floor))
        sized = resized_1r(snap, stop_old, stop_new)
        if sized is None:
            continue
        final_new, r1_old, r1_new = sized
        trades.append({
            "symbol": d["symbol"],
            "ts": d["ts"],
            "date": d["date"],
            "month": d["month"],
            "action": snap["action"],
            "channel": snap["channel"] or "",
            "binding_cap": snap["binding_cap"],
            "stop_pct_old": round(stop_old, 6),
            "stop_pct_new": round(stop_new, 6),
            "notional_old": round(snap["final_notional"], 4),
            "notional_new": round(final_new, 4),
            "r1_old": round(r1_old, 4),
            "r1_new": round(r1_new, 4),
            "r1_ratio": round(r1_new / r1_old, 4) if r1_old else None,
            "R_old": round(d["R"], 4),
            "R_new": round(lf["R"], 4),
            "Rnet_old": round(d["R_net"], 4),
            "Rnet_new": round(lf["R_net"], 4),
            "pnl_old": round(d["R_net"] * r1_old, 4),
            "pnl_new": round(lf["R_net"] * r1_new, 4),
        })

    if not trades:
        raise SystemExit("no exact-arm trades: risk_budget snapshots missing")

    ts_span = (min(t["ts"] for t in trades), max(t["ts"] for t in trades))
    span_days = max((ts_span[1] - ts_span[0]) / 86400.0, 1.0)
    def per30(x):
        return x * REPORT_WINDOW_DAYS / span_days

    pnl_old = sum(t["pnl_old"] for t in trades)
    pnl_new = sum(t["pnl_new"] for t in trades)
    r1_old_sum = sum(t["r1_old"] for t in trades)
    r1_new_sum = sum(t["r1_new"] for t in trades)
    improvement = None if pnl_old == 0 else (pnl_new - pnl_old) / abs(pnl_old)
    max_r1_new = max(t["r1_new"] for t in trades)
    max_r1_old = max(t["r1_old"] for t in trades)

    def agg(keyfn):
        g = defaultdict(list)
        for t in trades:
            g[keyfn(t)].append(t)
        out = {}
        for k, v in g.items():
            po = sum(x["pnl_old"] for x in v)
            pn = sum(x["pnl_new"] for x in v)
            out[str(k)] = {
                "n": len(v),
                "share": round(len(v) / len(trades), 4),
                "r1_old_sum": round(sum(x["r1_old"] for x in v), 2),
                "r1_new_sum": round(sum(x["r1_new"] for x in v), 2),
                "r1_ratio": round(sum(x["r1_new"] for x in v) / sum(x["r1_old"] for x in v), 4)
                if sum(x["r1_old"] for x in v) else None,
                "pnl_old": round(po, 2),
                "pnl_new": round(pn, 2),
                "improvement": round((pn - po) / abs(po), 4) if po else None,
            }
        return out

    p2_limit = NOMINAL_EQUITY * P2_MAX_R1_PCT
    p1_pass = improvement is not None and improvement >= P1_MIN_IMPROVEMENT
    p2_pass = max_r1_new <= p2_limit

    result = {
        "preregistered": {
            "P1_min_improvement": P1_MIN_IMPROVEMENT,
            "P2_max_r1_pct_of_equity": P2_MAX_R1_PCT,
            "P2_max_r1_usdt": round(p2_limit, 2),
            "nominal_equity": NOMINAL_EQUITY,
            "report_window_days": REPORT_WINDOW_DAYS,
        },
        "config": {
            "exit_profile": args.exit_profile,
            "stop_floor": args.floor,
            "stop_ceil": STOP_CEIL,
            "profile": args.profile,
            "months": months,
        },
        "coverage": {
            "decisions_total": len(decisions),
            "labeled_baseline": len(base),
            "labeled_lifted": len(lifted),
            "executable_total": len(exec_base),
            "exact_arm_trades": len(trades),
            "exact_arm_span_days": round(span_days, 2),
            "exact_arm_window": [
                datetime.fromtimestamp(ts_span[0], tz=timezone.utc).strftime("%Y-%m-%d %H:%M"),
                datetime.fromtimestamp(ts_span[1], tz=timezone.utc).strftime("%Y-%m-%d %H:%M"),
            ],
            "note": "risk_budget 仅 2026-09 起落盘; 6-8 月可执行行无该字段, 只进 R 对照臂",
        },
        "r_only_arm": r_only,
        "exact_arm": {
            "n": len(trades),
            "r1_old_sum": round(r1_old_sum, 2),
            "r1_new_sum": round(r1_new_sum, 2),
            "r1_inflation": round(r1_new_sum / r1_old_sum, 4) if r1_old_sum else None,
            "pnl_old_usdt": round(pnl_old, 2),
            "pnl_new_usdt": round(pnl_new, 2),
            "pnl_old_per30": round(per30(pnl_old), 2),
            "pnl_new_per30": round(per30(pnl_new), 2),
            "improvement": None if improvement is None else round(improvement, 4),
            "rnet_improvement": None if not r_only.get("E_Rnet_improvement")
            else r_only["E_Rnet_improvement"],
            "usdt_discount_vs_r": None if not r_only.get("E_Rnet_improvement") or improvement is None
            else round(improvement / r_only["E_Rnet_improvement"], 4),
            "max_r1_old": round(max_r1_old, 2),
            "max_r1_new": round(max_r1_new, 2),
            "max_r1_ratio": round(max_r1_new / max_r1_old, 4) if max_r1_old else None,
        },
        "by_binding_cap": agg(lambda t: t["binding_cap"]),
        "by_channel": agg(lambda t: t["channel"] or "(none)"),
        "by_action": agg(lambda t: t["action"]),
        "by_month": agg(lambda t: t["month"]),
        "verdict": {
            "P1_pass": p1_pass,
            "P2_pass": p2_pass,
            "decision": "GO_1B" if (p1_pass and p2_pass) else "NO_GO",
        },
    }

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "metrics.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    cols = ("symbol", "ts", "date", "month", "action", "channel", "binding_cap",
            "stop_pct_old", "stop_pct_new", "notional_old", "notional_new",
            "r1_old", "r1_new", "r1_ratio", "R_old", "R_new", "Rnet_old", "Rnet_new",
            "pnl_old", "pnl_new")
    (out / "trades.csv").write_text(
        ",".join(cols) + "\n" + "\n".join(",".join(str(t[c]) for c in cols) for t in trades),
        encoding="utf-8",
    )
    (out / "report.md").write_text(_render(result), encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("coverage", "exact_arm", "verdict")},
                     ensure_ascii=False, indent=2))


def _pct(x, digits=1):
    return "n/a" if x is None else f"{x * 100:+.{digits}f}%"


def _render(r):
    e = r["exact_arm"]
    ro = r["r_only_arm"]
    cov = r["coverage"]
    pre = r["preregistered"]
    lines = [
        f"# stop_pct 下限 `{r['config']['stop_floor']:.3f}` 的 USDT 口径验收",
        "",
        f"- 出场口径：`{r['config']['exit_profile']}`；决策面 profile：`{r['config']['profile']}`",
        f"- 精确臂：{cov['exact_arm_trades']} 笔有 `risk_budget` 的可执行决策，"
        f"跨度 {cov['exact_arm_span_days']:.1f} 天（{cov['exact_arm_window'][0]} → {cov['exact_arm_window'][1]}）",
        f"- 对照臂（只算 R）：{cov['executable_total']} 笔可执行决策",
        f"- **覆盖限制**：{cov['note']}",
        "",
        "## 预登记判据",
        "",
        f"- P1：`Σ E[R_net]·1R` 改善 ≥ {pre['P1_min_improvement'] * 100:.0f}% → "
        f"**{'通过' if r['verdict']['P1_pass'] else '未通过'}**（实测 {_pct(e['improvement'])}）",
        f"- P2：单笔最大 1R ≤ {pre['P2_max_r1_usdt']:.2f} USDT（eq 的 {pre['P2_max_r1_pct_of_equity'] * 100:.2f}%）→ "
        f"**{'通过' if r['verdict']['P2_pass'] else '未通过'}**（实测 {e['max_r1_new']:.2f} USDT，"
        f"旧 {e['max_r1_old']:.2f}）",
        f"- 结论：**{r['verdict']['decision']}**",
        "",
        "## 核心数字",
        "",
        "| 口径 | baseline | floor | 改善 |",
        "|---|---:|---:|---:|",
        f"| `E[R_net]`（R 口径，对照臂 n={ro['n']}） | {ro['baseline']['E_Rnet']:+.4f} | "
        f"{ro['lifted']['E_Rnet']:+.4f} | {_pct(ro.get('E_Rnet_improvement'))} |",
        f"| 期望盈亏（USDT，精确臂 n={e['n']}，全窗口） | {e['pnl_old_usdt']:+.2f} | "
        f"{e['pnl_new_usdt']:+.2f} | {_pct(e['improvement'])} |",
        f"| 期望盈亏（USDT，折 {pre['report_window_days']:.0f} 天） | {e['pnl_old_per30']:+.2f} | "
        f"{e['pnl_new_per30']:+.2f} | {_pct(e['improvement'])} |",
        "",
        f"**1R 总量从 {e['r1_old_sum']:.2f} 膨胀到 {e['r1_new_sum']:.2f}（{e['r1_inflation']:.3f}×），"
        f"单笔最大 1R 从 {e['max_r1_old']:.2f} 升到 {e['max_r1_new']:.2f}（{e['max_r1_ratio']:.2f}×）。**",
        "",
        f"USDT 口径的改善只有 R 口径的 **{e['usdt_discount_vs_r']:.3f} 倍**"
        if e["usdt_discount_vs_r"] is not None else
        "USDT 折扣系数无法计算（对照臂改善缺失）。",
        "",
        "## 按绑定上限分解",
        "",
        "| binding_cap | n | 占比 | 1R 倍率 | 盈亏旧 | 盈亏新 | 改善 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for k, v in sorted(r["by_binding_cap"].items(), key=lambda kv: -kv[1]["n"]):
        lines.append(
            f"| `{k}` | {v['n']} | {v['share'] * 100:.1f}% | {v['r1_ratio']:.3f}× | "
            f"{v['pnl_old']:+.2f} | {v['pnl_new']:+.2f} | {_pct(v['improvement'])} |"
        )
    lines += [
        "",
        "## 按通道 / 月份分解",
        "",
        "| 维度 | 值 | n | 1R 倍率 | 盈亏旧 | 盈亏新 | 改善 |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for label, key in (("通道", "by_channel"), ("月份", "by_month"), ("动作", "by_action")):
        for k, v in sorted(r[key].items(), key=lambda kv: -kv[1]["n"]):
            lines.append(
                f"| {label} | `{k}` | {v['n']} | {v['r1_ratio']:.3f}× | "
                f"{v['pnl_old']:+.2f} | {v['pnl_new']:+.2f} | {_pct(v['improvement'])} |"
            )
    lines += [
        "",
        "## 读法",
        "",
        "1. `raw_notional` / `leveraged_cap_notional` 与 `stop_pct` 成反比，抬下限会让名义额按比例缩小，"
        "**1R 守恒**；`remaining_exposure_notional` 与 `stop_pct` 无关，抬下限后**1R 直接放大**。",
        "2. 所以「亏的 R 少了」这件事，在敞口绑定那一半仓位上是假的——每个 R 更贵。"
        "判据必须落在 `Σ E[R_net]·1R` 上。",
        "3. P2 存在的理由：即便 USDT 期望改善，若单笔 1R 冲破 `eq × 0.30%`，"
        "`portfolio_daily_loss_circuit` 与 2 连亏熔断会更早触发，实际笔数反而下降。",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    main()
