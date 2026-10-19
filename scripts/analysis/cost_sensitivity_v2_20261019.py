"""成本敏感性三条曲线(6 / 10 / 20bps):净期望到底剩下多少。

问题
----
`fwdlib.labeler.run_labeling` 的净收益是 `R_net = R - cost_R`, 而
`cost_R = (bps/1e4) / stop_pct`。也就是说成本不是一笔固定美元, 而是**按止损宽度
放大的 R 倍数**: 止损 0.5% 时 20bps 就是 0.40R, 止损 2% 时才 0.10R。

`D:/AIDCA/AI300/reports/analysis/cost-audit-20261019/reconciliation.json` 已确认
账面落账成本是 **5bps/腿 × 2 腿(fee)**, 账面另加同额 5bps 假设滑点, 合计 20bps
往返。旧归因文档里的「20.98 USDT」是双错: **只算平仓腿**, 且 **同一个 5bps 被
计成 fee + slip 两次**(见 `ledger_audit_20261019.py` 模块头)。

本脚本只回答一个算术问题: 在 6 / 10 / 20bps 三个成本档下, 同一批决策的
`E[R_net]` 分别是多少, 以及「打平需要多少毛利」。

口径
----
- 场外口径: `exit_mode=barrier`, `horizon=32` 根 15m, `entry=next_open` ——
  与 `fwd_label_20261019.py` 的「入场有没有信息量」检验一致, 不是线上 TP 阶梯。
- 三档成本只改 `LabelConfig.cost_bps`。barrier 口径下 `R` 与成本无关, 因此
  **三档的 `R` 必须逐行相同**; 若不同, 说明成本串进了毛收益, 那是 bug, 脚本直接
  失败而不是继续出数。
- `cost_R` 分布取 `fwdlib.cost.cost_r_distribution(stops, keys=...)`,
  `stops = [r["stop_pct_eff"]]`。
- 置信区间: 按 `(symbol|date)` 分块的 80% bootstrap(`fwdlib.stats.block_bootstrap_mean`)。

成本档名与来源(`fwdlib.cost.SCENARIOS`)
--------------------------------------
- `maker_6`  ── 双边 maker + BNB 折扣的**理论下界**。纸面账户没有队列/成交率模型,
  这一档不可直接引用为可执行成本。
- `hybrid_10` ── 纯 taker 双边手续费(5bps/边), **等于账面 fee 全腿**。
- `taker_20`  ── fee + 假设滑点(5+5 bps/边), **等于账面 fee+slip 全腿**。

用法
----
  python scripts/analysis/cost_sensitivity_v2_20261019.py \
    --logs D:/AIDCA/AI300/logs --months 2026-09,2026-10 \
    --out D:/AIDCA/AI300/reports/analysis/cost-audit-20261019
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fwdlib.config import LabelConfig  # noqa: E402
from fwdlib.cost import SCENARIOS, cost_r_distribution, describe_scenarios  # noqa: E402
from fwdlib.features import load_decisions  # noqa: E402
from fwdlib.labeler import run_labeling  # noqa: E402
from fwdlib.stats import block_bootstrap_mean  # noqa: E402

SCRIPT = "scripts/analysis/cost_sensitivity_v2_20261019.py"
SEED = 7
GROSS_TOL = 1e-12
IDENTITY_TOL = 1e-9

CSV_COLS = (
    "scenario", "bps", "n", "E_R", "E_Rnet", "E_Rnet_ci80",
    "cost_R_mean", "cost_R_median", "cost_R_p10", "cost_R_p90",
    "breakeven_required_E_R",
)

MARK_BEGIN = "<!-- BEGIN cost_sensitivity_v2_20261019 -->"
MARK_END = "<!-- END cost_sensitivity_v2_20261019 -->"


# --------------------------------------------------------------------------- #
# 参数与数据
# --------------------------------------------------------------------------- #

def _parse_args(argv=None):
    ap = argparse.ArgumentParser(description="成本敏感性三条曲线(6/10/20bps)")
    ap.add_argument("--logs", default="D:/AIDCA/AI300/logs")
    ap.add_argument("--months", default="2026-09,2026-10")
    ap.add_argument("--out", default="D:/AIDCA/AI300/reports/analysis/cost-audit-20261019")
    ap.add_argument("--costs", default="6,10,20", help="逗号分隔的往返 bps;必须是 SCENARIOS 里的档位")
    ap.add_argument("--horizon", type=int, default=32)
    ap.add_argument("--exit-mode", default="barrier", choices=("barrier", "ladder"))
    ap.add_argument("--iters", type=int, default=2000)
    return ap.parse_args(argv)


def _scenario_key(bps: float) -> str:
    for scenario in SCENARIOS.values():
        if abs(scenario.bps - bps) < 1e-12:
            return scenario.key
    known = ", ".join(f"{s.key}={s.bps:g}" for s in SCENARIOS.values())
    raise SystemExit(f"未知成本档 {bps:g}bps;可用档位: {known}")


def _decision_paths(logs: str, months: list[str]) -> list[Path]:
    root = Path(logs)
    paths: list[Path] = []
    for month in months:
        found = sorted(root.glob(f"{month}/*/decisions.jsonl"))
        if not found:
            print(f"[warn] {month} 下没有 decisions.jsonl", file=sys.stderr)
        paths += found
    if not paths:
        raise SystemExit(f"{logs} 下找不到任何 decisions.jsonl")
    return paths


# --------------------------------------------------------------------------- #
# 标注与统计
# --------------------------------------------------------------------------- #

def _label(decisions, bps: float, exit_mode: str, horizon: int) -> list[dict]:
    cfg = LabelConfig(cost_bps=bps, exit_mode=exit_mode, horizon_bars=horizon)
    rows = run_labeling(decisions, exit_mode=exit_mode, cfg=cfg)[0]
    if not rows:
        raise SystemExit(f"{bps:g}bps 档没有可标注的决策")
    return rows


def _ci80(rows: list[dict], iters: int) -> list[float] | None:
    by_block: dict[str, list[float]] = {}
    for row in rows:
        by_block.setdefault(row["block"], []).append(row["R_net"])
    ci = block_bootstrap_mean(by_block, iters=iters, seed=SEED)
    return None if ci is None else [ci[0], ci[1]]


def _max_abs_diff(values_a, values_b) -> float:
    """逐行最大绝对差;长度不等视为不可比(返回 inf)。"""
    if len(values_a) != len(values_b):
        return float("inf")
    return max((abs(a - b) for a, b in zip(values_a, values_b)), default=0.0)


def _check_gross_invariance(rows_by_bps: dict[float, list[dict]]) -> dict:
    """三档的 `R` 必须逐行相同: 成本只允许影响 `R_net`。"""
    costs = list(rows_by_bps)
    base_cost = costs[0]
    base_rows = rows_by_bps[base_cost]
    base_keys = [(r["symbol"], r["ts"]) for r in base_rows]
    base_stops = [r["stop_pct_eff"] for r in base_rows]

    keys_identical = True
    stops_identical = True
    pairwise: dict[str, float] = {}
    for cost in costs:
        rows = rows_by_bps[cost]
        if [(r["symbol"], r["ts"]) for r in rows] != base_keys:
            keys_identical = False
        if [r["stop_pct_eff"] for r in rows] != base_stops:
            stops_identical = False
        if cost == base_cost:
            continue
        pairwise[f"{cost:g}_vs_{base_cost:g}"] = _max_abs_diff(
            [r["R"] for r in rows], [r["R"] for r in base_rows]
        )

    # barrier 口径下 R 就是 gross_R, 顺带钉住这一条
    gross_alias = max(
        (abs(r["R"] - r["gross_R"]) for rows in rows_by_bps.values() for r in rows),
        default=0.0,
    )
    worst = max(pairwise.values(), default=0.0)
    passed = keys_identical and stops_identical and worst < GROSS_TOL and gross_alias < GROSS_TOL
    return {
        "window": "三档 cost_bps 分别重跑 run_labeling, 逐行比较 R",
        "row_keys_identical": keys_identical,
        "stop_pct_eff_identical": stops_identical,
        "pairwise_max_abs_diff_R": pairwise,
        "max_abs_diff_R": worst,
        "max_abs_diff_R_vs_gross_R": gross_alias,
        "tolerance": GROSS_TOL,
        "passed": passed,
    }


def _summarize(rows: list[dict], bps: float, dist: dict, iters: int) -> dict:
    scenario = SCENARIOS[_scenario_key(bps)]
    if abs(dist["bps"] - scenario.bps) > 1e-12:
        raise SystemExit(f"cost_r_distribution 的 bps={dist['bps']} 与档位 {scenario.bps} 不符")

    e_r = statistics.fmean([r["R"] for r in rows])
    e_net = statistics.fmean([r["R_net"] for r in rows])
    cost_mean_rows = statistics.fmean([r["cost_r"] for r in rows])
    # 同一批 stop、同一 bps ⇒ 两条路径算出的均值必须逐位相等
    if abs(cost_mean_rows - dist["mean"]) > 1e-12:
        raise SystemExit(
            f"{scenario.key}: 行内 cost_r 均值 {cost_mean_rows!r} "
            f"与 cost_r_distribution 均值 {dist['mean']!r} 不一致"
        )
    return {
        "scenario": scenario.key,
        "bps": scenario.bps,
        "provenance": scenario.provenance,
        "note": scenario.note,
        "n": len(rows),
        "E_R": e_r,
        "E_Rnet": e_net,
        "E_Rnet_ci80": _ci80(rows, iters),
        "cost_R_mean": dist["mean"],
        "cost_R_median": dist["median"],
        "cost_R_p10": dist["p10"],
        "cost_R_p90": dist["p90"],
        "breakeven_required_E_R": dist["breakeven_required_E_R"],
    }


def _identity_check(rows_by_bps: dict[float, list[dict]], summaries: list[dict]) -> dict:
    """`E_Rnet(低) - E_Rnet(高)` 必须等于 `mean(cost_R 高) - mean(cost_R 低)`。"""
    costs = sorted(rows_by_bps)
    lo, hi = costs[0], costs[-1]
    by_cost = {s["bps"]: s for s in summaries}
    lhs = by_cost[lo]["E_Rnet"] - by_cost[hi]["E_Rnet"]
    rhs = by_cost[hi]["cost_R_mean"] - by_cost[lo]["cost_R_mean"]
    rows_lo, rows_hi = rows_by_bps[lo], rows_by_bps[hi]
    row_level = max(
        (abs((a["R_net"] - b["R_net"]) - (b["cost_r"] - a["cost_r"]))
         for a, b in zip(rows_lo, rows_hi)),
        default=0.0,
    )
    return {
        "formula": f"E_Rnet({lo:g}) - E_Rnet({hi:g}) == mean(cost_R{hi:g}) - mean(cost_R{lo:g})",
        "lhs_E_Rnet_diff": lhs,
        "rhs_cost_R_diff": rhs,
        "diff": abs(lhs - rhs),
        "tolerance": IDENTITY_TOL,
        "passed": abs(lhs - rhs) < IDENTITY_TOL,
        "row_level_max_abs_diff": row_level,
        "row_level_passed": row_level < IDENTITY_TOL,
    }


# --------------------------------------------------------------------------- #
# 判据
# --------------------------------------------------------------------------- #

def _verdict(summaries: list[dict]) -> tuple[str, str]:
    """预登记判据只挂在「最便宜那一档」的 80% CI 上, 不给事后调整留口子。"""
    cheapest = min(summaries, key=lambda s: s["bps"])
    ci = cheapest["E_Rnet_ci80"]
    e_net = cheapest["E_Rnet"]
    if ci is None:
        return "INCONCLUSIVE", f"{cheapest['scenario']} 档块数不足 5, 无法给出 80% CI"
    lo, hi = ci
    where = (f"{cheapest['scenario']}({cheapest['bps']:g}bps) 的 E[R_net]={e_net:+.4f}, "
             f"80% CI=[{lo:+.4f}, {hi:+.4f}]")
    if hi <= 0.0:
        return "COST_CANNOT_FIX", f"{where} —— 上界仍 < 0, 仅靠降成本无法转正"
    if lo > 0.0:
        return "COST_CAN_FIX", f"{where} —— 下界 > 0, 降成本可转正(但 maker_6 无队列模型, 见 caveats)"
    return "COST_BOUNDARY", f"{where} —— 区间跨 0, 处于边界"


def _preregistered(summaries: list[dict], args) -> dict:
    return {
        "question": "如果往返成本是 6/10/20bps, 净期望分别是多少",
        "cost_axes_bps": [s["bps"] for s in summaries],
        "primary_metric": "E_Rnet = E_R - cost_R, barrier 口径(horizon=32, entry=next_open)",
        "secondary_metric": "cost_R 分布(mean/median/p10/p90) 与 breakeven_required_E_R",
        "ci": f"按 (symbol|date) 分块的 80% bootstrap, iters={args.iters}, seed={SEED}",
        "exit_mode": args.exit_mode,
        "horizon_bars": args.horizon,
        "decision_rule": {
            "COST_CANNOT_FIX": "最便宜档(6bps)的 E[R_net] 80% CI 上界 <= 0",
            "COST_BOUNDARY": "最便宜档的 80% CI 跨越 0",
            "COST_CAN_FIX": "最便宜档的 80% CI 下界 > 0",
        },
        "invariants": {
            "gross_R_cost_invariance": f"三档 R 逐行相同, max|diff| < {GROSS_TOL:g}",
            "identity": f"E_Rnet(低) - E_Rnet(高) == mean(cost_R 高) - mean(cost_R 低), 差 < {IDENTITY_TOL:g}",
        },
        "note": "判据只看最便宜档: 若连理论下界都打不平, 更贵的档位不必再看;"
                "反之也只在算术意义上成立, 不含队列/成交率/深度冲击。",
    }


# --------------------------------------------------------------------------- #
# 落盘
# --------------------------------------------------------------------------- #

def _write_csv(path: Path, summaries: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(CSV_COLS)
        for s in summaries:
            ci = s["E_Rnet_ci80"]
            writer.writerow([
                s["scenario"],
                f"{s['bps']:g}",
                s["n"],
                f"{s['E_R']:.6f}",
                f"{s['E_Rnet']:.6f}",
                "" if ci is None else f"[{ci[0]:.6f}, {ci[1]:.6f}]",
                f"{s['cost_R_mean']:.6f}",
                f"{s['cost_R_median']:.6f}",
                f"{s['cost_R_p10']:.6f}",
                f"{s['cost_R_p90']:.6f}",
                f"{s['breakeven_required_E_R']:.6f}",
            ])


def _merge_metrics(path: Path, section: dict) -> None:
    """读取既有 metrics.json 后只替换 `cost_sensitivity` 段, 其它段原样保留。"""
    payload = {}
    if path.exists():
        existing = path.read_text(encoding="utf-8").strip()
        if existing:
            payload = json.loads(existing)
    payload["cost_sensitivity"] = section
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _merge_report(path: Path, block: str) -> None:
    """把本脚本的段落写进 report.md; 已有同名段落则原位替换(可重复运行)。"""
    text = path.read_text(encoding="utf-8") if path.exists() else "# 成本审计 2026-10-19\n"
    if MARK_BEGIN in text and MARK_END in text:
        head, rest = text.split(MARK_BEGIN, 1)
        _stale, tail = rest.split(MARK_END, 1)
        text = head.rstrip("\n") + "\n\n" + block + tail.lstrip("\n")
    else:
        text = text.rstrip("\n") + "\n\n" + block + "\n"
    path.write_text(text, encoding="utf-8")


def _load_reconciliation(out: Path) -> dict | None:
    path = out / "reconciliation.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


# --------------------------------------------------------------------------- #
# 报告
# --------------------------------------------------------------------------- #

def _render_block(summaries, gross, identity, prereg, verdict, detail, args, rec, runtime_s) -> str:
    lines = [
        MARK_BEGIN,
        "## 成本敏感性: 6 / 10 / 20bps 三条曲线",
        "",
        f"脚本 `{SCRIPT}`；出场 `{args.exit_mode}`；horizon `{args.horizon}` 根；"
        f"窗口 `{args.months}`；n = {summaries[0]['n']:,}；总耗时 {runtime_s:.1f}s。",
        "",
        "**账面 5bps×2 是常量假设，不是交易所实收。**",
        "",
        "`paper_trading.py` 里的 `FEE_BPS = 5.0` / `SLIPPAGE_BPS = 5.0` 只是两个写死的标量，"
        "`fee` 与 `slip` 由同一常量生成、逐行相等（`fee_equals_slip_share = 1.0`）。"
        "币安 U 本位 VIP0 taker 名义费率碰巧也是 5bps，但账面从没读过交易所的实收流水，"
        "所以「20bps 往返」是**假设**，不是账单。",
        "",
        "### 三条曲线",
        "",
        "| 场景 | 往返 bps | 档位来源 | n | `E[R]`(毛) | `cost_R` 均值 | `E[R_net]` | `E[R_net]` 80% CI | 打平所需 `E[R]` |",
        "|---|---:|---|---:|---:|---:|---:|---|---:|",
    ]
    for s in summaries:
        ci = s["E_Rnet_ci80"]
        ci_txt = "n/a" if ci is None else f"[{ci[0]:+.4f}, {ci[1]:+.4f}]"
        lines.append(
            f"| `{s['scenario']}` | {s['bps']:g} | {s['provenance']} | {s['n']:,} | "
            f"{s['E_R']:+.4f} | {s['cost_R_mean']:.4f} | **{s['E_Rnet']:+.4f}** | "
            f"{ci_txt} | {s['breakeven_required_E_R']:.4f} |"
        )

    lines += [
        "",
        "档位含义（`fwdlib.cost.SCENARIOS`）：",
    ]
    for s in summaries:
        lines.append(f"- `{s['scenario']}` = {s['bps']:g}bps —— {s['note']}")

    lines += [
        "",
        "读法：`E[R]` 三档相同（成本不进毛收益），`cost_R` 随 bps 线性放大，"
        "所以 `E[R_net]` 三条曲线是同一毛期望减去三条平行的成本线。",
        "",
        "### 不变量：三档的 `R` 逐行相同",
        "",
        "| 检查 | 值 | 阈值 | 结论 |",
        "|---|---:|---:|---|",
        f"| 行键 `(symbol, ts)` 序列相同 | — | — | {'是' if gross['row_keys_identical'] else '否'} |",
        f"| `stop_pct_eff` 逐行相同 | — | — | {'是' if gross['stop_pct_eff_identical'] else '否'} |",
        f"| `max abs diff R` | {gross['max_abs_diff_R']:.3e} | {gross['tolerance']:g} | "
        f"{'通过' if gross['max_abs_diff_R'] < gross['tolerance'] else '失败'} |",
        f"| `max abs diff (R - gross_R)` | {gross['max_abs_diff_R_vs_gross_R']:.3e} | "
        f"{gross['tolerance']:g} | "
        f"{'通过' if gross['max_abs_diff_R_vs_gross_R'] < gross['tolerance'] else '失败'} |",
        "",
        "```json",
        json.dumps(gross["pairwise_max_abs_diff_R"], ensure_ascii=False),
        "```",
        "",
        "结论：成本只改 `R_net`，三档的毛收益完全相同。若这里出现非零差值，"
        "说明成本串进了毛收益，是 bug。",
        "",
        "### 恒等式检查",
        "",
        f"`{identity['formula']}`",
        "",
        "| 项 | 值 |",
        "|---|---:|",
        f"| 左式 `E_Rnet(低) - E_Rnet(高)` | {identity['lhs_E_Rnet_diff']:+.12f} |",
        f"| 右式 `mean(cost_R 高) - mean(cost_R 低)` | {identity['rhs_cost_R_diff']:+.12f} |",
        f"| 差值 | {identity['diff']:.3e}（阈值 {identity['tolerance']:g}） |",
        f"| 逐行 `max abs diff` | {identity['row_level_max_abs_diff']:.3e} |",
        f"| 结论 | **{'通过' if identity['passed'] and identity['row_level_passed'] else '失败'}** |",
        "",
    ]

    lines += [
        "### 旧归因「20.98 USDT」错在哪",
        "",
    ]
    if rec and "window" in rec:
        w = rec["window"]
        lines += [
            f"同一窗口（{w['n_close']} 笔平仓 / {w['n_open']} 笔开仓 / {w['n_reduce']} 笔减仓）的账本原始事件：",
            "",
            "| 口径 | 数值 (USDT) | 说明 |",
            "|---|---:|---|",
            f"| 旧归因 `legacy_attribution` | {w['legacy_attribution']:.6f} | 只取 `PAPER_CLOSE` 腿名义 × 10bps（fee 5 + slip 5） |",
            f"| fee 全腿（正确） | {w['correct_fee_only']:.6f} | open + reduce + close 三条腿各 5bps |",
            f"| fee + slip 全腿（账面假设） | {w['double_count_if_slip_is_real']:.6f} | 若滑点也算真实成本，再翻一倍 |",
            "",
            "两个错误叠在一起：",
            "",
            f"1. **只算平仓腿。** `{w['legacy_attribution']:.2f}` = 平仓腿名义 "
            f"{w['by_event']['close']['notional']:.2f} × 10bps，"
            f"漏掉了开仓腿（{w['by_event']['open']['fee']:.2f} USDT）与减仓腿"
            f"（{w['by_event']['reduce']['fee']:.2f} USDT）的落账 fee。",
            f"2. **同一个 5bps 计了两次。** fee 与 slip 由同一常量生成、逐行相等"
            f"（`fee_equals_slip_share = {w['fee_equals_slip_share']}`），"
            "把两者相加不是「两种成本之和」，而是把一个假设重复计了一遍。",
            "",
            f"所以旧文档的 20.98 既不等于真实手续费（{w['correct_fee_only']:.2f}），"
            "也不构成往返成本口径 —— 正确读法是 **5bps/腿 × 2 腿 fee = 10bps 往返**，"
            "另加同额 5bps 假设滑点后才是 20bps。",
            "",
            f"旁证：账本窗口的隐含往返成本 fee-only = {w['implied_bps_fee_only']:.2f}bps、"
            f"fee+slip = {w['implied_bps_fee_plus_slip']:.2f}bps，与本脚本的 10 / 20bps 两档吻合。",
            "",
        ]
    else:
        lines += [
            "旧文档的「20.98 USDT」有两个错误叠加：",
            "",
            "1. **只算平仓腿**：20.98 ≈ 平仓腿名义 20,988.08 × 10bps，漏掉开仓腿与减仓腿的落账 fee；",
            "2. **同一个 5bps 计了两次**：fee 与 slip 由同一常量生成、逐行相等，"
            "`fee + slip` 不是一个假设的两种成本，而是同一假设的重复。",
            "",
            "正确口径是 5bps/腿 × 2 腿 fee = 10bps 往返，另加同额假设滑点后为 20bps。",
            "",
        ]

    lines += [
        "### 预登记与裁决",
        "",
        "```json",
        json.dumps(prereg, ensure_ascii=False, indent=2),
        "```",
        "",
        f"**`verdict = {verdict}`** —— {detail}。",
        "",
    ]
    return "\n".join(lines) + "\n" + MARK_END + "\n"


# --------------------------------------------------------------------------- #
# 主流程
# --------------------------------------------------------------------------- #

def main(argv=None) -> int:
    args = _parse_args(argv)
    started = time.perf_counter()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    months = [m.strip() for m in args.months.split(",") if m.strip()]
    costs = [float(c) for c in args.costs.split(",") if c.strip()]
    if len({round(c, 12) for c in costs}) != len(costs):
        raise SystemExit(f"--costs 有重复档位: {args.costs}")
    keys = tuple(_scenario_key(c) for c in costs)

    paths = _decision_paths(args.logs, months)
    decisions = load_decisions([str(p) for p in paths], profile="any")
    print(f"[load] files={len(paths)} decisions={len(decisions)}", flush=True)

    rows_by_bps: dict[float, list[dict]] = {}
    cost_runtime: dict[str, float] = {}
    for bps in costs:
        t0 = time.perf_counter()
        rows = _label(decisions, bps, args.exit_mode, args.horizon)
        cost_runtime[_scenario_key(bps)] = time.perf_counter() - t0
        rows_by_bps[bps] = rows
        print(f"[label] {_scenario_key(bps):>10} {bps:>4.0f}bps n={len(rows):,} "
              f"({cost_runtime[_scenario_key(bps)]:.1f}s)", flush=True)

    gross = _check_gross_invariance(rows_by_bps)
    if not gross["passed"]:
        raise SystemExit(
            "毛收益不满足成本不变性: 三档的 R 不是逐行相同, 成本串进了毛收益 —— "
            f"{json.dumps(gross, ensure_ascii=False)}"
        )
    print(f"[check] gross R invariant: max|diff|={gross['max_abs_diff_R']:.3e} "
          f"(tol {GROSS_TOL:g})", flush=True)

    stops = [r["stop_pct_eff"] for r in rows_by_bps[costs[0]]]
    dist = cost_r_distribution(stops, keys=keys)
    summaries = [_summarize(rows_by_bps[b], b, dist[_scenario_key(b)], args.iters) for b in costs]

    identity = _identity_check(rows_by_bps, summaries)
    if not (identity["passed"] and identity["row_level_passed"]):
        raise SystemExit(f"恒等式检查失败: {json.dumps(identity, ensure_ascii=False)}")
    print(f"[check] identity diff={identity['diff']:.3e} "
          f"row-level max={identity['row_level_max_abs_diff']:.3e}", flush=True)

    prereg = _preregistered(summaries, args)
    verdict, detail = _verdict(summaries)

    total = time.perf_counter() - started
    generated_at = time.strftime("%Y-%m-%dT%H:%M:%S%z")

    _write_csv(out / "cost_sensitivity.csv", summaries)

    section = {
        "generated_at": generated_at,
        "script": SCRIPT,
        "inputs": {
            "logs": args.logs,
            "months": months,
            "n_files": len(paths),
            "n_decisions": len(decisions),
            "n_labeled": summaries[0]["n"],
            "horizon_bars": args.horizon,
            "exit_mode": args.exit_mode,
            "iters": args.iters,
            "seed": SEED,
            "profile": "any",
        },
        "scenarios": {
            s["scenario"]: {
                "bps": s["bps"],
                "provenance": s["provenance"],
                "note": s["note"],
                "n": s["n"],
                "E_R": s["E_R"],
                "E_Rnet": s["E_Rnet"],
                "E_Rnet_ci80": s["E_Rnet_ci80"],
                "cost_R": {
                    "mean": s["cost_R_mean"],
                    "median": s["cost_R_median"],
                    "p10": s["cost_R_p10"],
                    "p90": s["cost_R_p90"],
                },
                "breakeven_required_E_R": s["breakeven_required_E_R"],
                "runtime_s": cost_runtime[s["scenario"]],
            }
            for s in summaries
        },
        "scenario_catalog": describe_scenarios(),
        "gross_R_invariance": gross,
        "identity_check": identity,
        "preregistered": prereg,
        "verdict": verdict,
        "verdict_detail": detail,
        "caveats": [
            "账面 5bps×2 是常量假设, 不是交易所实收; fee 与 slip 逐行相等, 属同一假设的两次记账。",
            "maker_6 是双边 maker + BNB 折扣的理论下界, 纸面账户无队列/成交率模型, 不可直接当可执行成本。",
            "barrier 口径不是线上 TP 阶梯出场; 它评价的是入场方向在 8 小时里的信息量, 不能反推系统实盘 E[R]。",
            "成本只进 R_net, 不进 R; barrier 下成交集合也不随成本变化(与 ladder 的成本超时不同)。",
        ],
        "runtime_s": total,
    }
    _merge_metrics(out / "metrics.json", section)

    rec = _load_reconciliation(out)
    _merge_report(
        out / "report.md",
        _render_block(summaries, gross, identity, prereg, verdict, detail, args, rec, total),
    )

    print("")
    print(f"{'scenario':>10} {'bps':>4} {'n':>8} {'E_R':>9} {'cost_R':>8} {'E_Rnet':>9}  CI80")
    for s in summaries:
        ci = s["E_Rnet_ci80"]
        ci_txt = "n/a" if ci is None else f"[{ci[0]:+.4f}, {ci[1]:+.4f}]"
        print(f"{s['scenario']:>10} {s['bps']:>4.0f} {s['n']:>8,} {s['E_R']:>+9.4f} "
              f"{s['cost_R_mean']:>8.4f} {s['E_Rnet']:>+9.4f}  {ci_txt}")
    print(f"\nverdict={verdict}  {detail}")
    print(f"elapsed={total:.1f}s  out={out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
