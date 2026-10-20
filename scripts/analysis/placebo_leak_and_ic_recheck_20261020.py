"""2026-10-20 复审:安慰剂前视泄漏判别 + 组件 IC 口径重算。

背景
----
外部评审对 v2 计划提出两条核心质疑,都要用数据回答:

1. **配对安慰剂可能有前视泄漏**。``fwdlib.baseline.placebo_pool`` 只排除决策
   自身那根 bar,同一 UTC 日内的**更早时点**也会被抽到。而方向是决策时点
   ``t`` 用"过去 4 根 1h 收盘变化"判定的;当安慰剂时点 ``t' < t`` 时,它的
   32 根前向窗口会把"促成该方向的那段走势"吃进去 → LONG 的安慰剂 R 机械偏正。
   判别:按 ``t' - t`` 分桶看 ``E[R]``。泄漏的签名是**正效应只出现在 t'<t**。

2. **组件 IC 可能被成本污染**。``cost_and_walkforward_20261019.py`` 的
   walk-forward 用的是 ``R_net`` 作目标(第 164 行),而 ``R_net = R - 20bps/stop``。
   若组件分与 ``stop_pct`` 相关,IC 会混入"组件-成本"相关。判别:同一批样本上
   分别对 ``gross_R`` 与 ``R_net`` 算日截面 IC,并给出去掉 ``stop_pct`` 后的
   近似偏相关。

用法
----
    FWD_LOGS=D:/AIDCA/AI300-fwdlib/logs \
    python scripts/analysis/placebo_leak_and_ic_recheck_20261020.py \
        --months 2026-08,2026-09,2026-10 --draws 8 --stride 3

产出
----
``logs/analysis/recheck/2026-10-20/report.md`` 与 ``metrics.json``。

注意
----
- 本脚本**不改任何生产代码**,只读日志、复用 ``fwdlib`` 的标注与抽样。
- 近似偏相关是在"日内秩残差"上做的,不是严格的偏 Spearman;报告里已标注。
- 安慰剂与真实样本的前向窗口允许重叠(原实现如此),这里不改变该行为,
  只按 ``t'-t`` 分桶把泄漏与"方向持续性"分开。
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:  # 直接 python scripts/analysis/x.py 时走这条
    from fwdlib.baseline import placebo_pool
    from fwdlib.config import LabelConfig
    from fwdlib.features import load_decisions
    from fwdlib.labeler import label_barrier, run_labeling
except ImportError:  # 作为包导入时
    from scripts.analysis.fwdlib.baseline import placebo_pool
    from scripts.analysis.fwdlib.config import LabelConfig
    from scripts.analysis.fwdlib.features import load_decisions
    from scripts.analysis.fwdlib.labeler import label_barrier, run_labeling

BAR_SECONDS = 900
SECONDS_PER_DAY = 86400
#: 分桶边界(单位:根,一根 15m)。负数 = 安慰剂时点早于决策。
BUCKETS: list[tuple[str, int, int]] = [
    ("t' < t 且窗口完全在 t 之前 (<-32)", -10**9, -32),
    ("t' < t 窗口部分覆盖 [-32,-9)", -32, -8),
    ("t' < t 紧邻 [-8,-2)", -8, -1),
    ("t' < t 最近 [-1,-1]", -1, 0),
    ("t' > t 最近 [1,8]", 1, 8),
    ("t' > t 中距 [9,32]", 9, 32),
    ("t' > t 远距 (>32)", 33, 10**9),
]


def _logs_root(arg: str | None) -> Path:
    if arg:
        return Path(arg)
    env = os.environ.get("FWD_LOGS")
    if env:
        return Path(env)
    return ROOT / "logs"


def _reports_root(arg: str | None) -> Path:
    if arg:
        return Path(arg)
    env = os.environ.get("FWD_REPORTS")
    if env:
        return Path(env)
    return ROOT / "logs" / "analysis"


def _rank(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def _pearson(x: list[float], y: list[float]) -> float:
    n = len(x)
    if n < 3:
        return float("nan")
    mx = sum(x) / n
    my = sum(y) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(x, y))
    sx = math.sqrt(sum((a - mx) ** 2 for a in x))
    sy = math.sqrt(sum((b - my) ** 2 for b in y))
    if sx == 0 or sy == 0:
        return float("nan")
    return cov / (sx * sy)


def _spearman(x: list[float], y: list[float]) -> float:
    return _pearson(_rank(x), _rank(y))


def _residual_on(rank_y: list[float], rank_x: list[float]) -> list[float]:
    """把 rank_y 对 rank_x 做最小二乘残差(近似偏相关用)。"""
    n = len(rank_y)
    mx = sum(rank_x) / n
    my = sum(rank_y) / n
    sxx = sum((a - mx) ** 2 for a in rank_x)
    if sxx == 0:
        return [b - my for b in rank_y]
    sxy = sum((a - mx) * (b - my) for a, b in zip(rank_x, rank_y))
    beta = sxy / sxx
    return [b - my - beta * (a - mx) for a, b in zip(rank_x, rank_y)]


def _bucket_of(dt_bars: int) -> str | None:
    for name, lo, hi in BUCKETS:
        if lo <= dt_bars <= hi:
            return name
    return None


def _day_cluster_ci(values_by_day: dict[str, list[float]], *, iters: int = 2000,
                    seed: int = 7, lo: float = 0.10, hi: float = 0.90) -> tuple[float, float]:
    """按 UTC 日聚类的 bootstrap 区间(80%)。"""
    days = list(values_by_day)
    if len(days) < 5:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    means: list[float] = []
    for _ in range(iters):
        pick = [days[rng.randrange(len(days))] for _ in days]
        flat = [v for d in pick for v in values_by_day[d]]
        if flat:
            means.append(sum(flat) / len(flat))
    if not means:
        return (float("nan"), float("nan"))
    means.sort()
    return (means[int(lo * (len(means) - 1))], means[int(hi * (len(means) - 1))])


def leak_test(labeled, bars, per_symbol, index, cfg, *, draws: int, stride: int,
              seed: int = 7) -> dict:
    """按 t'-t 分桶统计安慰剂毛 R。"""
    bucket_vals: dict[str, list[float]] = defaultdict(list)
    bucket_by_day: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    side_split: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    used = 0

    for pos, row in enumerate(labeled):
        if pos % stride:
            continue
        symbol = row["symbol"]
        ts = int(row["ts"])
        side = row["side"]
        stop = row.get("stop_pct_eff") or row.get("stop_pct")
        if not stop or stop <= 0:
            continue
        day = row.get("date") or ""
        pool = placebo_pool(bars, per_symbol, index, symbol, day, exclude_ts=ts)
        if len(pool) < 4:
            continue
        rng = random.Random(f"{seed}|{symbol}|{ts}|{side}")
        got = 0
        for _ in range(draws * 6):
            if got >= draws:
                break
            pick = pool[rng.randrange(len(pool))]
            dt_bars = (pick - ts) // BAR_SECONDS
            name = _bucket_of(dt_bars)
            if name is None:
                continue
            fake = {"symbol": symbol, "ts": pick, "side": side, "stop_pct": stop,
                    "atr_pct": row.get("atr_pct")}
            res = label_barrier(bars, per_symbol, index, fake, stop,
                                cfg.entry_mode, cfg=cfg, horizon=cfg.horizon_bars)
            if res is None:
                continue
            r = float(res["R"])
            bucket_vals[name].append(r)
            bucket_by_day[name][day].append(r)
            side_split[name][side].append(r)
            got += 1
        if got:
            used += 1

    table = []
    for name, _lo, _hi in BUCKETS:
        vals = bucket_vals.get(name) or []
        if not vals:
            table.append({"bucket": name, "n": 0, "mean_R": None, "ci80": None, "se": None})
            continue
        ci = _day_cluster_ci(bucket_by_day[name])
        table.append({
            "bucket": name,
            "n": len(vals),
            "mean_R": statistics.fmean(vals),
            "se": statistics.stdev(vals) / math.sqrt(len(vals)) if len(vals) > 1 else None,
            "ci80": ci,
            "by_side": {k: statistics.fmean(v) for k, v in side_split[name].items()},
        })
    return {"rows_used": used, "draws_per_row": draws, "table": table}


def ic_recheck(labeled, components: dict[tuple[str, int], dict], *, min_symbols: int = 8) -> dict:
    """同一批样本上分别对 gross_R / R_net 算日截面 IC,并给近似偏相关。"""
    names: list[str] = []
    for comp in components.values():
        for key in comp:
            if key not in names:
                names.append(key)

    rows: list[dict] = []
    for row in labeled:
        key = (row["symbol"], int(row["ts"]))
        comp = components.get(key)
        if not comp:
            continue
        gross = row.get("gross_R")
        net = row.get("R_net")
        stop = row.get("stop_pct_eff") or row.get("stop_pct")
        if gross is None or net is None or not stop:
            continue
        item = {"day": row.get("date") or "", "symbol": row["symbol"],
                "gross": float(gross), "net": float(net), "stop": float(stop)}
        for name in names:
            value = comp.get(name)
            if value is None:
                break
            item[name] = float(value)
        else:
            rows.append(item)

    out: dict[str, dict] = {}
    by_day: dict[str, list[dict]] = defaultdict(list)
    for item in rows:
        by_day[item["day"]].append(item)

    for name in names:
        ic_gross: list[float] = []
        ic_net: list[float] = []
        ic_partial: list[float] = []
        for day, items in by_day.items():
            if len(items) < min_symbols:
                continue
            x = [it[name] for it in items]
            g = [it["gross"] for it in items]
            n = [it["net"] for it in items]
            s = [it["stop"] for it in items]
            rx, rs = _rank(x), _rank(s)
            cg = _spearman(x, g)
            cn = _spearman(x, n)
            if not math.isnan(cg):
                ic_gross.append(cg)
            if not math.isnan(cn):
                ic_net.append(cn)
            # 近似偏相关:组件与收益都先对 stop 的秩做残差
            rx_res = _residual_on(rx, rs)
            rg_res = _residual_on(_rank(g), rs)
            cp = _pearson(rx_res, rg_res)
            if not math.isnan(cp):
                ic_partial.append(cp)
        def _summ(values: list[float]) -> dict:
            if not values:
                return {"days": 0, "mean": None, "se": None, "t": None}
            mean = statistics.fmean(values)
            se = statistics.stdev(values) / math.sqrt(len(values)) if len(values) > 1 else None
            return {"days": len(values), "mean": mean, "se": se,
                    "t": (mean / se) if se else None}
        out[name] = {
            "ic_gross": _summ(ic_gross),
            "ic_net": _summ(ic_net),
            "ic_partial_stop_gross": _summ(ic_partial),
        }

    # 总分单列
    ic_gross = []
    ic_net = []
    for day, items in by_day.items():
        if len(items) < min_symbols:
            continue
        x = [it.get("__score__", float("nan")) for it in items]
        if any(math.isnan(v) for v in x):
            continue
        ic_gross.append(_spearman(x, [it["gross"] for it in items]))
        ic_net.append(_spearman(x, [it["net"] for it in items]))
    out["__score__"] = {
        "ic_gross": {"days": len(ic_gross),
                     "mean": statistics.fmean(ic_gross) if ic_gross else None},
        "ic_net": {"days": len(ic_net),
                   "mean": statistics.fmean(ic_net) if ic_net else None},
    }
    return {"rows": len(rows), "components": out}


def _fmt(value, digits: int = 4) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "-"
    if isinstance(value, float):
        return f"{value:+.{digits}f}"
    return str(value)


def build_report(leak: dict, ic: dict, months: str) -> str:
    lines = ["# 安慰剂泄漏判别 + 组件 IC 口径重算", "",
             f"- 窗口:{months}", f"- 标注口径:barrier / next_open / horizon 32 根 / 20bps",
             f"- 安慰剂:同 symbol、同 UTC 日、同 side、同 stop_pct,随机 bar(原实现不改)", ""]
    lines.append("## 1. 安慰剂按 t'-t 分桶(泄漏判别)")
    lines.append("")
    lines.append("| 桶(单位:15m 根) | n | E[R] 毛 | SE | 80% CI(日聚类) |")
    lines.append("|---|---:|---:|---:|---|")
    for item in leak["table"]:
        ci = item.get("ci80") or (None, None)
        ci_text = "-" if ci[0] is None else f"[{ci[0]:+.3f}, {ci[1]:+.3f}]"
        lines.append(f"| {item['bucket']} | {item['n']} | {_fmt(item['mean_R'], 4)} | "
                     f"{_fmt(item.get('se'), 4)} | {ci_text} |")
    lines.append("")
    lines.append(f"- 参与抽样的决策行:{leak['rows_used']},每行 {leak['draws_per_row']} 个安慰剂时点")
    lines.append("")
    lines.append("> 读法:**泄漏的签名是正效应只出现在 `t'<t` 一侧,且越靠近 0 越大**;"
                 "若 `t'>t` 一侧仍显著为正,才是\"方向在决策之后仍持续\"的证据。")
    lines.append("")
    lines.append("## 2. 组件 IC:毛 R vs 净 R vs 控 stop 偏相关")
    lines.append("")
    lines.append("| 组件 | IC(毛) | 天数 | IC(净) | 天数 | 近似偏相关(控 stop) | 天数 |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for name, item in ic["components"].items():
        if name == "__score__":
            continue
        g, n, p = item["ic_gross"], item["ic_net"], item["ic_partial_stop_gross"]
        lines.append(f"| {name} | {_fmt(g['mean'])} | {g['days']} | {_fmt(n['mean'])} | "
                     f"{n['days']} | {_fmt(p['mean'])} | {p['days']} |")
    score = ic["components"].get("__score__") or {}
    if score:
        lines.append(f"| **total_score** | {_fmt((score.get('ic_gross') or {}).get('mean'))} | "
                     f"{(score.get('ic_gross') or {}).get('days', 0)} | "
                     f"{_fmt((score.get('ic_net') or {}).get('mean'))} | "
                     f"{(score.get('ic_net') or {}).get('days', 0)} | - | - |")
    lines.append("")
    lines.append(f"- 参与 IC 计算的样本行:{ic['rows']}")
    lines.append("")
    lines.append("> 读法:若某组件的 `IC(毛)` 与 `IC(净)` **符号相反**,说明净口径的符号由成本项"
                 "贡献 —— 这正是外部评审指出的污染。近似偏相关是在日内秩残差上算的,"
                 "不是严格偏 Spearman,只用于判方向。")
    lines.append("")
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description="安慰剂泄漏判别 + 组件 IC 重算")
    ap.add_argument("--logs", default=None, help="日志根(默认 FWD_LOGS 或仓库根 logs)")
    ap.add_argument("--out", default=None, help="报告根(默认 FWD_REPORTS 或 logs/analysis)")
    ap.add_argument("--months", default="2026-08,2026-09,2026-10")
    ap.add_argument("--draws", type=int, default=8)
    ap.add_argument("--stride", type=int, default=3, help="每 N 条决策抽 1 条做安慰剂")
    ap.add_argument("--date", default="2026-10-20")
    args = ap.parse_args()

    logs = _logs_root(args.logs)
    months = [m.strip() for m in args.months.split(",") if m.strip()]
    paths: list[str] = []
    for month in months:
        paths += [str(p) for p in sorted(logs.glob(f"{month}/*/decisions.jsonl"))]
    if not paths:
        raise SystemExit(f"no decisions.jsonl under {logs} for {months}")
    print(f"[load] {len(paths)} files under {logs}")

    decisions = load_decisions(paths)
    print(f"[load] {len(decisions)} decisions")

    # 组件分:直接从原始行取 component_points,与 (symbol, ts) 对齐
    components: dict[tuple[str, int], dict] = {}
    for path in paths:
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                kline = row.get("kline") or {}
                ts = kline.get("timestamp")
                symbol = row.get("symbol")
                comp = row.get("component_points")
                if ts is None or not symbol or not comp:
                    continue
                item = {k: float(v) for k, v in comp.items() if isinstance(v, (int, float))}
                sd = row.get("score_detail") or {}
                total = sd.get("total_score")
                if isinstance(total, (int, float)):
                    item["__score__"] = float(total)
                components[(symbol, int(ts))] = item
    print(f"[load] {len(components)} component rows")

    cfg = LabelConfig()
    labeled, bars, per_symbol, index, _quad = run_labeling(decisions, cfg=cfg)
    print(f"[label] {len(labeled)} labeled rows")

    # 把总分塞进 labeled 供 IC 使用
    for row in labeled:
        comp = components.get((row["symbol"], int(row["ts"])))
        if comp and "__score__" in comp:
            row["__score__"] = comp["__score__"]

    leak = leak_test(labeled, bars, per_symbol, index, cfg,
                     draws=args.draws, stride=args.stride)
    print("[leak] done")
    ic = ic_recheck(labeled, components)
    print("[ic] done")

    out_dir = _reports_root(args.out) / "recheck" / args.date
    out_dir.mkdir(parents=True, exist_ok=True)
    report = build_report(leak, ic, args.months)
    (out_dir / "report.md").write_text(report, encoding="utf-8")
    (out_dir / "metrics.json").write_text(
        json.dumps({"leak": leak, "ic": ic, "months": args.months},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    print(report)
    print(f"[written] {out_dir / 'report.md'}")


if __name__ == "__main__":
    main()
