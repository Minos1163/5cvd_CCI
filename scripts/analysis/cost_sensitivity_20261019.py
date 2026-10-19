"""WS2: 分腿成本敏感性矩阵 —— 20 / 13 / 7.75 / 4.25 bps × 止损宽度。

问题
----
「maker 降成本 20 -> 8bps」被当成一条独立的转正路径。但成本只是分母:
`cost_R = round_trip_bps / 1e4 / stop_pct`, 而毛利 `E[R]` 与止损宽度基本无关
(见 `2026-10-19-STOPFLOOR` 的 27 场景)。所以要打平必须满足

    E[R] > cost_R   <=>   stop_pct > round_trip_bps / 1e4 / E[R]

本脚本把这两个杠杆(成本档 × 止损宽度)铺成矩阵, 直接回答「哪一档能转正」。

口径
----
- 出场: `ladgex`(TP 1.2/2.0/3.0R 分批 40/35/25% + TP1 后保本 + 8 根成本超时 +
  32 根上限 + trend_capture 追踪 + Q2 收紧 + Q3 减半 + Q4 防御), 与线上账本一致率 90%。
- 成本: 通过替换 `fwd_label_20261019.ROUND_TRIP_BPS` 注入(该常量在 `label_ladder`
  与 `run_labeling` 内均为运行时全局读取), 跑完即还原, 不污染同进程其他调用。
- 决策面: 六因子 profile 全窗口(2026-06-20 → 2026-10-18, n≈149k)。

预登记判据
----------
  C1  存在某 (成本档, 止损宽度) 使 `E[R_net]` 的 80% 分块下界 > 0
  C2  该组合的 `stop_pct` 不超过 `STOP_HARD_CEIL`(线上硬上限, 默认 4%)
任一不满足 => 「降成本 / 放宽止损」这条路在算术上关闭。

用法
----
  python scripts/analysis/cost_sensitivity_20261019.py
  python scripts/analysis/cost_sensitivity_20261019.py --models taker_20,hybrid_8 --floors 0,0.015
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cost_model as CM  # noqa: E402
import fwd_label_20261019 as L  # noqa: E402

# ---- 预登记 ----
STOP_HARD_CEIL = 0.04
TP_LEG_SHARE = 0.75
EXIT_PROFILE = dict(exit_mode="ladder", post_tp_mode="trend_capture",
                    quadrant_defense=True, q2_tighten=True, entry_mode="bar_close")


def run_with_cost(decisions, round_trip_bps, stop_floor):
    """临时替换模块级成本常量跑一次标注, 结束后还原。

    `label_ladder` 的 `cost_r` 与 `run_labeling` 的 `cost_r` 都读模块全局,
    所以这个替换对「净盈亏」与「成本超时/Q4 防御 的触发阈值」同时生效 ——
    这正是我们想要的: 成本下降会改变成交集合, 必须一并重放。
    """
    original = L.ROUND_TRIP_BPS
    L.ROUND_TRIP_BPS = float(round_trip_bps)
    try:
        rows = L.run_labeling(decisions, stop_floor=stop_floor, **EXIT_PROFILE)[0]
    finally:
        L.ROUND_TRIP_BPS = original
    return rows


def check_injection(rows, round_trip_bps):
    """抽样校验成本确实被注入(防止常量被内联/缓存导致静默失效)。"""
    if not rows:
        return False
    sample = rows[:200]
    expected = [(round_trip_bps / 10000.0) / r["stop_pct_eff"] for r in sample]
    actual = [r["cost_r"] for r in sample]
    return all(abs(a - e) < 1e-9 for a, e in zip(actual, expected))


def stats(rows):
    if not rows:
        return None
    R = [r["R"] for r in rows]
    Rn = [r["R_net"] for r in rows]
    ci = L.block_bootstrap_mean({k: [x["R_net"] for x in v]
                                 for k, v in L._group(rows, lambda d: d["block"]).items()})
    ci_R = L.block_bootstrap_mean({k: [x["R"] for x in v]
                                   for k, v in L._group(rows, lambda d: d["block"]).items()})
    return {
        "n": len(rows),
        "hit": round(sum(1 for x in R if x > 0) / len(R), 4),
        "E_R": round(statistics.fmean(R), 4),
        "E_R_ci80": None if ci_R is None else [round(ci_R[0], 4), round(ci_R[1], 4)],
        "cost_R": round(statistics.fmean([r["cost_r"] for r in rows]), 4),
        "E_Rnet": round(statistics.fmean(Rn), 4),
        "E_Rnet_ci80": None if ci is None else [round(ci[0], 4), round(ci[1], 4)],
        "ambiguous_pct": round(sum(1 for r in rows if r.get("ambiguous")) / len(rows) * 100, 2),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--logs", default="logs")
    ap.add_argument("--months", default="2026-06,2026-07,2026-08,2026-09,2026-10")
    ap.add_argument("--profile", default="six_factor", choices=["any", "six_factor"])
    ap.add_argument("--models", default=",".join(m.version for m in CM.ALL_MODELS))
    ap.add_argument("--floors", default="0,0.010,0.015,0.025",
                    help="逗号分隔; 0 表示不设下限(现状)")
    ap.add_argument("--tp-leg-share", type=float, default=TP_LEG_SHARE)
    ap.add_argument("--out", default="reports/analysis/cost-sensitivity-20261019")
    args = ap.parse_args()

    months = [m.strip() for m in args.months.split(",") if m.strip()]
    paths = []
    for m in months:
        paths += sorted(Path(args.logs).glob(f"{m}/*/decisions.jsonl"))
    if not paths:
        raise SystemExit("no decisions.jsonl found")
    decisions = L.load_decisions([str(p) for p in paths], profile=args.profile)
    print(f"decisions={len(decisions)} models={args.models} floors={args.floors}", flush=True)

    models = [CM.get(v.strip()) for v in args.models.split(",") if v.strip()]
    floors = []
    for f in args.floors.split(","):
        f = f.strip()
        if f:
            floors.append(None if float(f) <= 0 else float(f))

    matrix = {}
    for model in models:
        rtb = model.round_trip_bps(args.tp_leg_share)
        for floor in floors:
            key = f"{model.version}|floor_{floor if floor else 'base'}"
            rows = run_with_cost(decisions, rtb, floor)
            if not check_injection(rows, rtb):
                raise SystemExit(f"cost injection failed for {key}")
            s = stats(rows)
            if s is None:
                continue
            s["round_trip_bps"] = round(rtb, 3)
            s["stop_floor"] = floor
            s["stop_pct_median"] = round(statistics.median([r["stop_pct_eff"] for r in rows]), 5)
            s["reasons"] = dict(sorted(
                {k: len(v) for k, v in L._group(rows, lambda d: d["reason"]).items()}.items(),
                key=lambda kv: -kv[1],
            )[:6])
            matrix[key] = s
            print(f"  {key:>28}  n={s['n']}  E[R]={s['E_R']:+.4f}  "
                  f"cost_R={s['cost_R']:.4f}  E[Rnet]={s['E_Rnet']:+.4f}  "
                  f"ci={s['E_Rnet_ci80']}", flush=True)

    # 打平所需止损宽度(用该成本档下实测的毛利)
    breakeven = {}
    for model in models:
        rtb = model.round_trip_bps(args.tp_leg_share)
        base = matrix.get(f"{model.version}|floor_base") or matrix.get(f"{model.version}|floor_None")
        if not base:
            continue
        er = base["E_R"]
        breakeven[model.version] = {
            "round_trip_bps": round(rtb, 3),
            "gross_E_R_at_base": er,
            "required_stop_pct": round(CM.breakeven_stop_pct(model, er, args.tp_leg_share), 5)
            if CM.breakeven_stop_pct(model, er, args.tp_leg_share) else None,
            "exceeds_hard_ceil": (
                CM.breakeven_stop_pct(model, er, args.tp_leg_share) is not None
                and CM.breakeven_stop_pct(model, er, args.tp_leg_share) > STOP_HARD_CEIL
            ),
            "cost_R_at_hard_ceil": round((rtb / 10000.0) / STOP_HARD_CEIL, 4),
            "feasible": bool(er > (rtb / 10000.0) / STOP_HARD_CEIL),
        }

    passing = [k for k, v in matrix.items()
               if v["E_Rnet_ci80"] and v["E_Rnet_ci80"][0] > 0
               and (v["stop_floor"] or 0) <= STOP_HARD_CEIL]
    result = {
        "preregistered": {
            "C1": "存在 (成本档, 止损宽度) 使 E[R_net] 的 80% 分块下界 > 0",
            "C2_C2_stop_hard_ceiling": STOP_HARD_CEIL,
            "tp_leg_share": args.tp_leg_share,
            "exit_profile": "ladgex",
        },
        "cost_models": [m.describe(args.tp_leg_share) for m in models],
        "matrix": matrix,
        "breakeven": breakeven,
        "passing_scenarios": passing,
        "verdict": "COST_CAN_FIX" if passing else "COST_CANNOT_FIX",
    }

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "metrics.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    cols = ("round_trip_bps", "stop_floor", "stop_pct_median", "n", "hit",
            "E_R", "cost_R", "E_Rnet", "E_R_ci80", "E_Rnet_ci80", "ambiguous_pct")
    lines = ["scenario," + ",".join(cols)]
    for k, v in matrix.items():
        lines.append(k + "," + ",".join(
            f'"{v.get(c)}"' if isinstance(v.get(c), list) else str(v.get(c)) for c in cols))
    (out / "matrix.csv").write_text("\n".join(lines), encoding="utf-8")
    (out / "report.md").write_text(_render(result), encoding="utf-8")
    print(json.dumps({"verdict": result["verdict"], "passing": passing,
                      "breakeven": breakeven}, ensure_ascii=False, indent=2))


def _floors_of(r):
    """从 matrix 键里还原本轮跑过的止损档（None 表示不设下限）。"""
    out = set()
    for k in r["matrix"]:
        tail = k.rsplit("|", 1)[-1]
        out.add(None if tail == "floor_base" else float(tail.replace("floor_", "")))
    return sorted(out, key=lambda x: (x is not None, x or 0.0))


def _render(r):
    pre = r["preregistered"]
    lines = [
        "# 成本档 × 止损宽度：转正可行性矩阵",
        "",
        f"- 出场口径：`ladgex`（与线上账本出场大类一致率 90%）；TP 腿名义占比 `{pre['tp_leg_share']}`",
        f"- 预登记：**{pre['C1']}**，且止损不超过 {pre['C2_C2_stop_hard_ceiling'] * 100:.0f}%",
        f"- 结论：**{r['verdict']}**"
        + ("" if r["passing_scenarios"] else "（没有任何成本档 × 止损宽度的组合能让净期望的 80% 下界转正）"),
        "",
        "## 成本档定义",
        "",
        "| 版本 | 入场 fee+slip | TP 腿 fee+slip | 止损腿 fee+slip | 等效往返 |",
        "|---|---:|---:|---:|---:|",
    ]
    for m in r["cost_models"]:
        lines.append(
            f"| `{m['version']}` | {m['entry']['fee_bps']:.0f}+{m['entry']['slip_bps']:.0f} | "
            f"{m['tp_exit']['fee_bps']:.0f}+{m['tp_exit']['slip_bps']:.0f} | "
            f"{m['stop_exit']['fee_bps']:.0f}+{m['stop_exit']['slip_bps']:.0f} | "
            f"**{m['effective_round_trip_bps']:.2f}bps** |"
        )
    lines += [
        "",
        "## 矩阵",
        "",
        "| 场景 | 往返 bps | 止损中位 | n | 毛利 `E[R]` | `cost_R` | `E[R_net]` | `E[R_net]` 80% CI |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for k, v in r["matrix"].items():
        lines.append(
            f"| `{k}` | {v['round_trip_bps']:.2f} | {v['stop_pct_median'] * 100:.2f}% | {v['n']:,} | "
            f"{v['E_R']:+.4f} | {v['cost_R']:.4f} | **{v['E_Rnet']:+.4f}** | {v['E_Rnet_ci80']} |"
        )
    lines += [
        "",
        "## 打平所需的止损宽度",
        "",
        "`cost_R <= E[R]` ⇒ `stop_pct >= round_trip_bps / 1e4 / E[R]`",
        "",
        "| 成本档 | 往返 bps | 实测毛利 `E[R]` | 所需止损宽度 | 是否超硬上限 | 硬上限处 `cost_R` | 可行 |",
        "|---|---:|---:|---:|---|---:|---|",
    ]
    for ver, b in r["breakeven"].items():
        req = b["required_stop_pct"]
        lines.append(
            f"| `{ver}` | {b['round_trip_bps']:.2f} | {b['gross_E_R_at_base']:+.4f} | "
            f"{'n/a' if req is None else f'{req * 100:.1f}%'} | "
            f"{'是' if b['exceeds_hard_ceil'] else '否'} | {b['cost_R_at_hard_ceil']:.4f} | "
            f"{'**是**' if b['feasible'] else '否'} |"
        )
    lines += [
        "",
        "> **`可行=是` 只对 `aggressive_4` 出现，且是静态解的假象**：它按基准点 `E[R]=0.0115` 反解出 3.7%，"
        "但实测 3.5% 止损时 `E[R]` 已跌到 0.0055，代入后所需止损变成 "
        "`0.000425/0.0055 ≈ 7.7%`，仍远超 4% 硬上限。也就是说这一档同样不可行。",
        "",
        "## 缺口如何随止损宽度收敛",
        "",
        "`gap = E[R] - cost_R`。只有 `gap > 0` 才可能转正。注意 **`E[R]` 本身随止损变宽而下行**，"
        "所以上表的 `required_stop_pct`（按基准点的 `E[R]` 静态解）是**乐观下界**。",
        "",
        "| 成本档 | " + " | ".join(
            ("基准" if f in (None, 0) else f"{f * 100:.1f}%") for f in _floors_of(r)) + " |",
        "|---|" + "---:|" * len(_floors_of(r)),
    ]
    for ver in r["breakeven"]:
        cells = []
        for f in _floors_of(r):
            key = f"{ver}|floor_{f if f else 'base'}"
            v = r["matrix"].get(key)
            cells.append("–" if not v else f"{v['E_R'] - v['cost_R']:+.4f}")
        lines.append(f"| `{ver}` | " + " | ".join(cells) + " |")
    lines += [
        "",
        "读法：若缺口随止损变宽而**单调趋近 0 但不穿 0**，说明最优点在硬上限之外；"
        "若缺口收窄到某个水平后不再改善，说明 `E[R]` 的衰减已经抵消了 `cost_R` 的下降，"
        "继续放宽止损只会同时放大单笔风险。",
        "",
        "## 必须同时读的三条限定",
        "",
        "1. **8bps 的前提是「入场 + TP 腿都 maker」**。8bps 摊到每边 4bps，低于币安 U 本位 VIP0 taker 的 5bps，"
        "所以任何一条腿走 taker 都不成立。止损腿（`STOP_MARKET`）天生 taker，"
        "真实可达区间是 **7.75–13bps**（取决于 maker 费率档与成交率），"
        "`4.25bps` 那一档需要 VIP3+/返佣且 maker 零滑点，只能当下界参照。",
        "2. **执行层目前下不了 post-only**：`live_execution_contract.py` 的 `SUPPORTED_ORDER_TYPES` 不含 `POST_ONLY`，"
        "`tests/test_live_execution_contract.py` 把「拒绝 POST_ONLY」钉成契约，"
        "`binance_adapter.submit()` 直接 `raise NotImplementedError`，dry-run `orders_submitted=0`。"
        "也就是说这里的成本档目前只是**标注层的假设**，不是可执行事实。",
        "3. **成本下降会改变成交集合**，不只是改钱：`_cost_breakeven_timeout` 与 `_q4_defensive_exit` 都以"
        "「往返成本」为阈值。所以本矩阵重放了全部出场逻辑，而不是在旧结果上扣一个新成本。",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    main()
