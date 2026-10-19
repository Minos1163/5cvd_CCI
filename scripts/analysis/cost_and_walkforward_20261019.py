"""成本分档 + 按日块的显著性检验 + 组件级 walk-forward。

三个问题
--------
1. 20bps 是拍出来的压力口径。按标的流动性分档后,分档 lift / E[R] 会不会翻转?
2. 之前用 ``symbol|utc_date`` bootstrap 给区间,但同日多标的截面相关会放大显著性。
   这里把**交易日**作为独立单元:每天算一个截面 IC,再对日均 IC 做符号翻转置换。
3. 总分的排序能力已被前向标签证伪;那 6 个组件里,哪些在样本外还有独立符号?
   用 4 个连续窗口的日均 IC 符号稳定性来回答"删哪个",而不是调权重。

所有假设都写在输出里;不把"分档映射"伪装成已标定值。
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from collections import OrderedDict, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fwdlib.config import LabelConfig
from fwdlib.features import load_decisions
from fwdlib.labeler import run_labeling
from fwdlib.stats import spearman

#: 成本分档映射(假设,不是标定值)。按标的 24h 报价成交额三分位:
#: 高流动性 → 12bps,中 → 20bps(与现状一致),低 → 30bps。
#: 合理性:top-20 永续 taker 双边约 10bps + 0.5–2bps 滑点;尾部标的滑点显著更宽。
COST_TIERS_BPS = {"high": 12.0, "mid": 20.0, "low": 30.0}

COMPONENTS = (
    "trend_ema_context",
    "flow_cvd_confirmation",
    "cci_momentum_quality",
    "price_action_structure",
    "fibonacci_location",
    "risk_reward_geometry",
)


def _day(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 3:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 0 or syy <= 0:
        return None
    return sxy / math.sqrt(sxx * syy)


def _quantile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, int(round(q * (len(ordered) - 1)))))
    return ordered[idx]


def assign_cost_tiers(decisions: list[dict]) -> dict[str, str]:
    """按标的的 24h 报价成交额中位数分三档。"""
    by_symbol: dict[str, list[float]] = defaultdict(list)
    for d in decisions:
        log_qv = (d.get("feat") or {}).get("log_qv")
        if isinstance(log_qv, (int, float)) and not math.isnan(float(log_qv)):
            by_symbol[str(d["symbol"]).upper()].append(float(log_qv))
    medians = {sym: median(vals) for sym, vals in by_symbol.items() if vals}
    if not medians:
        return {}
    values = sorted(medians.values())
    lo = _quantile(values, 1 / 3)
    hi = _quantile(values, 2 / 3)
    tiers: dict[str, str] = {}
    for sym, value in medians.items():
        tiers[sym] = "low" if value <= lo else ("high" if value > hi else "mid")
    return tiers


def rerun_cost_variants(labeled: list[dict], tiers: dict[str, str]) -> dict:
    """给每条标注重算分档成本下的 R_net,并与固定 20bps 对照。"""
    flat: list[float] = []
    tiered: list[float] = []
    by_score_flat: dict[str, list[float]] = defaultdict(list)
    by_score_tiered: dict[str, list[float]] = defaultdict(list)
    for row in labeled:
        stop = row.get("stop_pct_eff") or row.get("stop_pct")
        if not stop or float(stop) <= 0:
            continue
        r = row.get("R")
        if r is None:
            continue
        stop = float(stop)
        symbol = str(row["symbol"]).upper()
        tier = tiers.get(symbol, "mid")
        bps = COST_TIERS_BPS[tier]
        r_flat = float(r) - 20.0 / 1e4 / stop
        r_tier = float(r) - bps / 1e4 / stop
        flat.append(r_flat)
        tiered.append(r_tier)
        bucket = _score_bucket(row.get("score"))
        by_score_flat[bucket].append(r_flat)
        by_score_tiered[bucket].append(r_tier)

    def summarize(values: list[float]) -> dict:
        return {
            "n": len(values),
            "mean": sum(values) / len(values) if values else None,
        }

    buckets = sorted(set(by_score_flat) | set(by_score_tiered))
    return {
        "tier_counts": {tier: sum(1 for v in tiers.values() if v == tier) for tier in ("high", "mid", "low")},
        "tier_symbols": {tier: sorted(s for s, v in tiers.items() if v == tier) for tier in ("high", "mid", "low")},
        "overall": {"flat_20bps": summarize(flat), "tiered": summarize(tiered)},
        "by_score": {
            bucket: {
                "flat_20bps": summarize(by_score_flat.get(bucket, [])),
                "tiered": summarize(by_score_tiered.get(bucket, [])),
            }
            for bucket in buckets
        },
    }


def _score_bucket(score) -> str:
    try:
        value = float(score)
    except (TypeError, ValueError):
        return "na"
    if value >= 92:
        return ">=92"
    if value >= 82:
        return "82-92"
    if value >= 78:
        return "78-82"
    if value >= 68:
        return "68-78"
    return "<68"


def daily_ic(labeled: list[dict], value_key: str, min_rows: int = 20) -> list[tuple[str, float]]:
    """按 UTC 日算截面 Spearman;每天只产出一个数,天与天之间才近似独立。"""
    by_day: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for row in labeled:
        if row.get("R_net") is None:
            continue
        value = row.get(value_key)
        if value is None:
            value = (row.get("feat") or {}).get(value_key)
        target = row.get("R_net")
        if value is None or target is None:
            continue
        try:
            value = float(value)
            target = float(target)
        except (TypeError, ValueError):
            continue
        if math.isnan(value) or math.isnan(target):
            continue
        by_day[_day(int(row["ts"]))].append((value, target))
    out: list[tuple[str, float]] = []
    for day, pairs in sorted(by_day.items()):
        if len(pairs) < min_rows:
            continue
        xs = [p[0] for p in pairs]
        ys = [p[1] for p in pairs]
        ic = spearman(xs, ys)
        if ic is not None:
            out.append((day, ic))
    return out


def sign_flip_test(ics: list[float], iters: int = 5000, seed: int = 7) -> dict:
    """日均 IC 的符号翻转置换检验:以「天」为独立单元。"""
    n = len(ics)
    if n < 5:
        return {"n_days": n, "mean_ic": None, "p_value": None}
    observed = sum(ics) / n
    rng = random.Random(seed)
    hits = 0
    for _ in range(iters):
        sign = 1.0
        total = 0.0
        for value in ics:
            sign = -sign if rng.random() < 0.5 else sign
            total += value * sign
        if abs(total / n) >= abs(observed):
            hits += 1
    return {
        "n_days": n,
        "mean_ic": observed,
        "p_value": hits / iters,
        "positive_days": sum(1 for v in ics if v > 0),
        "negative_days": sum(1 for v in ics if v < 0),
    }


def walk_forward(labeled: list[dict], windows: int = 4) -> dict:
    """组件级 walk-forward:每个窗口内算日均 IC,看符号是否稳定。"""
    days = sorted({_day(int(row["ts"])) for row in labeled if row.get("ts")})
    if len(days) < windows * 3:
        return {"error": f"days={len(days)} too few for {windows} windows"}
    per_window = max(1, len(days) // windows)
    window_days = [days[i * per_window : (i + 1) * per_window] for i in range(windows)]
    window_days[-1] = days[(windows - 1) * per_window :]

    result: dict[str, dict] = {}
    for component in COMPONENTS:
        ics = daily_ic(labeled, component)
        if not ics:
            continue
        by_day = dict(ics)
        stats = []
        for group in window_days:
            values = [by_day[d] for d in group if d in by_day]
            stats.append(
                {
                    "days": len(values),
                    "mean_ic": (sum(values) / len(values)) if values else None,
                }
            )
        signs = [1 if (s["mean_ic"] or 0) > 0 else (-1 if (s["mean_ic"] or 0) < 0 else 0) for s in stats]
        positive = sum(1 for s in signs if s > 0)
        negative = sum(1 for s in signs if s < 0)
        valid = [s["mean_ic"] for s in stats if s["mean_ic"] is not None]
        overall = sum(valid) / len(valid) if valid else None
        if positive >= 3:
            verdict = "keep_positive"
        elif negative >= 3:
            verdict = "stable_negative"
        else:
            verdict = "unstable"
        result[component] = {
            "windows": stats,
            "positive_windows": positive,
            "negative_windows": negative,
            "mean_ic": overall,
            "stable": max(positive, negative) >= 3,
            "verdict": verdict,
        }
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="成本分档 + 日块置换 + 组件 walk-forward")
    parser.add_argument("--logs", default="D:/AIDCA/AI300-fwdlib/logs")
    parser.add_argument("--months", default="2026-08,2026-09,2026-10")
    parser.add_argument("--out", default="logs/analysis/cost-walkforward/2026-10-19")
    parser.add_argument("--iters", type=int, default=5000)
    args = parser.parse_args(argv)

    log_root = Path(args.logs)
    paths: list[str] = []
    for month in args.months.split(","):
        paths.extend(str(p) for p in sorted((log_root / month.strip()).glob("*/decisions.jsonl")))
    decisions = load_decisions(paths, profile="any", include_v2=False)
    labeled, _b, _p, _i, _q = run_labeling(decisions, exit_mode="barrier", cfg=LabelConfig())
    print(f"decisions={len(decisions)} labeled={len(labeled)}", flush=True)

    tiers = assign_cost_tiers(decisions)
    cost = rerun_cost_variants(labeled, tiers)

    total_ic = daily_ic(labeled, "score")
    total_test = sign_flip_test([ic for _, ic in total_ic], iters=args.iters)

    components = walk_forward(labeled, windows=4)

    report = OrderedDict(
        {
            "window": args.months,
            "cost": {
                "assumption_bps": COST_TIERS_BPS,
                "note": "分档映射是敏感性假设,不是实测标定;结论只在方向上有意义",
                **cost,
            },
            "score_ic": {
                "daily": total_test,
                "series": [{"day": d, "ic": v} for d, v in total_ic],
            },
            "components": components,
            "delete_candidates": sorted(
                name for name, row in components.items() if row.get("verdict") == "stable_negative"
            ),
        }
    )

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "metrics.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "report.md").write_text(render(report), encoding="utf-8")
    print(json.dumps({"out": str(out_dir), "delete_candidates": report["delete_candidates"]}, ensure_ascii=False))
    return 0


def render(report: dict) -> str:
    cost = report["cost"]
    ic = report["score_ic"]["daily"]
    lines = [
        "# 成本分档 + 日块显著性 + 组件 walk-forward",
        "",
        f"- 窗口:{report['window']}",
        f"- 成本假设:{cost['assumption_bps']}(高/中/低流动性);**这是敏感性假设,不是标定值**",
        f"- 标的档位分布:{cost['tier_counts']}",
        f"- 高流动性:{', '.join(cost['tier_symbols']['high']) or '-'}",
        f"- 低流动性:{', '.join(cost['tier_symbols']['low']) or '-'}",
        "",
        "## 1. 成本分档 vs 固定 20bps",
        "",
        "| 分数档 | n | E[R_net] 固定 20bps | E[R_net] 分档 | Δ |",
        "|---|---:|---:|---:|---:|",
    ]
    for bucket, row in cost["by_score"].items():
        flat = row["flat_20bps"]["mean"]
        tier = row["tiered"]["mean"]
        delta = (tier - flat) if (flat is not None and tier is not None) else None
        lines.append(
            f"| {bucket} | {row['flat_20bps']['n']} | "
            f"{format(flat, '.4f') if flat is not None else '-'} | "
            f"{format(tier, '.4f') if tier is not None else '-'} | "
            f"{format(delta, '+.4f') if delta is not None else '-'} |"
        )
    flat_all = cost["overall"]["flat_20bps"]["mean"]
    tier_all = cost["overall"]["tiered"]["mean"]
    lines += [
        f"| **全体** | {cost['overall']['flat_20bps']['n']} | {format(flat_all, '.4f')} | {format(tier_all, '.4f')} | "
        f"{format(tier_all - flat_all, '+.4f')} |",
        "",
        "## 2. 总分的截面 IC(以 UTC 日为独立单元)",
        "",
        f"- 有效天数:{ic['n_days']}(每日 ≥20 条)",
        f"- 日均 IC:{format(ic['mean_ic'], '.4f') if ic['mean_ic'] is not None else '-'}",
        f"- 正/负天数:{ic.get('positive_days')} / {ic.get('negative_days')}",
        f"- 符号翻转置换 p 值:{format(ic['p_value'], '.4f') if ic['p_value'] is not None else '-'}({report['score_ic'].get('iters', 5000)} 次)",
        "",
        "> 与 `symbol|utc_date` bootstrap 的区别:这里每天只贡献一个观测,"
        "同日多标的截面相关不会被当成独立样本。p 值变大是预期结果。",
        "",
        "## 3. 组件级 walk-forward(4 个连续窗口)",
        "",
        "| 组件 | W1 | W2 | W3 | W4 | 均值 IC | 同号窗口 | 判定 |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for name, row in report["components"].items():
        cells = []
        for window in row["windows"]:
            value = window["mean_ic"]
            cells.append(format(value, "+.4f") if value is not None else "-")
        mean_ic = row.get("mean_ic")
        lines.append(
            f"| {name} | {' | '.join(cells)} | "
            f"{format(mean_ic, '+.4f') if mean_ic is not None else '-'} | "
            f"{max(row['positive_windows'], row['negative_windows'])}/4 | **{row['verdict']}** |"
        )
    lines += [
        "",
        f"**稳定为负(应反转或删除)**:{', '.join(report['delete_candidates']) or '无'}",
        "",
        "> 判据:4 个窗口中至少 3 个窗口日均 IC 同号 → 稳定。"
        "`keep_positive` = 稳定为正,保留;`stable_negative` = 稳定为负,"
        "意味着**分数越高未来 R 越低**——处理方式是反转该组件或从权重表移除,"
        "不是把权重调小(调小只是减弱噪声,仍然占着预算);`unstable` = 方向不稳,"
        "下一轮用更长窗口再判,暂不动。",
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
