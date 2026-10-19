"""并行 paper 对比:两条纸面账本的单笔风险分布与最大回撤。

背景
----
``risk_first_sizing_enabled=true`` 把名义上限从

    equity × risk_pct / (stop_pct × leverage)      (旧口径)

换成"保证金约束 + 敞口约束",同样的 ``risk_pct`` 语义下名义会放大。放大的**尾部**
(薄保证金、宽止损的标的)才是风险所在,中位数可能几乎不变。

这份脚本读两个并行 paper 的状态目录,回答两件事:

1. 单笔风险(名义 × stop_pct / 权益)的分位数:中位数 / P90 / 最大值各放大几倍;
2. 最大回撤放大几倍。

用法
----
    python scripts/analysis/paper_parallel_compare_20261019.py \
        --a D:/AIDCA/AI300-fwdlib/logs_parallel/fib_pa_v1/paper \
        --b D:/AIDCA/AI300-fwdlib/logs_parallel/risk_first/paper

局限
----
- 权益曲线只用**已实现**盈亏重建(逐笔累加 net_pnl),不含未实现浮盈;
  因此回撤是"已实现口径",会比账本自带的 ``max_drawdown``(含浮亏)偏小。
  两个口径都输出,以账本自带值为主。
- 两路必须钉住同一份 ``--symbols``,否则入场机会不同,对比无意义。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import median

REPORTS_ROOT = Path(__file__).resolve().parents[2] / "logs" / "analysis" / "paper-parallel"


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, int(round(q * (len(ordered) - 1)))))
    return ordered[idx]


def _max_drawdown(curve: list[float]) -> float:
    if not curve:
        return 0.0
    peak = curve[0]
    worst = 0.0
    for value in curve:
        peak = max(peak, value)
        worst = max(worst, (peak - value) / peak if peak > 0 else 0.0)
    return worst


def _load_events(state_dir: Path) -> list[dict]:
    path = state_dir / "paper_trades.jsonl"
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    rows.sort(key=lambda item: (int(item.get("timestamp") or 0), item.get("event") or ""))
    return rows


def _summary(state_dir: Path) -> dict:
    path = state_dir / "paper_summary.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def profile(state_dir: Path, initial_equity: float = 10_000.0) -> dict:
    events = _load_events(state_dir)
    summary = _summary(state_dir)
    initial = float(summary.get("initial_equity") or initial_equity)

    equity = initial
    risk_pcts: list[float] = []
    notionals: list[float] = []
    equity_curve = [initial]
    open_positions: dict[str, dict] = {}
    closes = 0

    for row in events:
        event = row.get("event")
        if event == "PAPER_OPEN":
            notional = float(row.get("notional") or 0.0)
            stop_pct = float(row.get("stop_pct") or 0.0)
            if notional > 0 and stop_pct > 0:
                risk_pcts.append(notional * stop_pct / equity if equity > 0 else 0.0)
                notionals.append(notional)
            position_id = str(row.get("position_id") or f'{row.get("symbol")}:{row.get("timestamp")}')
            open_positions[position_id] = row
        elif event in {"PAPER_CLOSE", "PAPER_REDUCE"}:
            net = float(row.get("net_pnl") or row.get("notional_pnl") or 0.0)
            equity += net
            equity_curve.append(equity)
            if event == "PAPER_CLOSE":
                closes += 1

    return {
        "state_dir": str(state_dir),
        "opens": len(risk_pcts),
        "closes": closes,
        "risk_pct_mean": (sum(risk_pcts) / len(risk_pcts)) if risk_pcts else 0.0,
        "risk_pct_median": median(risk_pcts) if risk_pcts else 0.0,
        "risk_pct_p90": _percentile(risk_pcts, 0.90),
        "risk_pct_max": max(risk_pcts) if risk_pcts else 0.0,
        "risk_pct_total": sum(risk_pcts),
        "notional_median": median(notionals) if notionals else 0.0,
        "notional_max": max(notionals) if notionals else 0.0,
        "final_equity": equity,
        "return_pct": (equity - initial) / initial if initial else 0.0,
        "max_drawdown_realized": _max_drawdown(equity_curve),
        "max_drawdown_ledger": float(summary.get("max_drawdown") or 0.0),
        "ledger_trade_count": int(summary.get("trade_count") or 0),
        "open_positions": len(open_positions),
    }


def _ratio(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return float("nan") if numerator else 1.0
    return numerator / denominator


def build_report(name_a: str, arm_a: dict, name_b: str, arm_b: dict) -> str:
    lines: list[str] = []
    lines.append("# 并行 paper 对比:单笔风险与最大回撤\n")
    lines.append(f"- 对照组:{name_a} → `{arm_a['state_dir']}`")
    lines.append(f"- 实验组:{name_b} → `{arm_b['state_dir']}`")
    lines.append("- 口径:单笔风险 = 名义 × stop_pct / 开仓时权益(已实现口径重建)\n")

    rows = [
        ("开仓笔数", "opens", "{:.0f}"),
        ("平仓笔数", "closes", "{:.0f}"),
        ("单笔风险 均值", "risk_pct_mean", "{:.4%}"),
        ("单笔风险 中位数", "risk_pct_median", "{:.4%}"),
        ("单笔风险 P90", "risk_pct_p90", "{:.4%}"),
        ("单笔风险 最大值", "risk_pct_max", "{:.4%}"),
        ("风险累计", "risk_pct_total", "{:.3%}"),
        ("名义 中位数", "notional_median", "{:.0f}"),
        ("名义 最大值", "notional_max", "{:.0f}"),
        ("期末权益", "final_equity", "{:.1f}"),
        ("区间收益", "return_pct", "{:+.2%}"),
        ("最大回撤(已实现)", "max_drawdown_realized", "{:.2%}"),
        ("最大回撤(账本含浮亏)", "max_drawdown_ledger", "{:.2%}"),
    ]
    lines.append("| 指标 | " + name_a + " | " + name_b + " | 倍数 |")
    lines.append("|---|---:|---:|---:|")
    for label, key, fmt in rows:
        value_a = arm_a[key]
        value_b = arm_b[key]
        ratio = _ratio(value_b, value_a) if isinstance(value_a, (int, float)) else float("nan")
        ratio_text = "-" if ratio != ratio else f"{ratio:.3f}×"
        lines.append(f"| {label} | {fmt.format(value_a)} | {fmt.format(value_b)} | {ratio_text} |")

    trades = min(arm_a["opens"], arm_b["opens"])
    dd_ratio = _ratio(arm_b["max_drawdown_ledger"] or arm_b["max_drawdown_realized"],
                      arm_a["max_drawdown_ledger"] or arm_a["max_drawdown_realized"])
    risk_ratio = _ratio(arm_b["risk_pct_max"], arm_a["risk_pct_max"])

    lines.append("")
    if trades < 20:
        verdict = "insufficient_sample"
        lines.append(f"**判定**:`{verdict}` —— 开仓笔数 {trades} < 20。")
        lines.append("")
        lines.append("> 线上入场频率约 1-2 笔/天,要做出可比的回撤结论需要数周样本。"
                     "在此之前的即时答案来自 `logs/analysis/risk-first/2026-10-19/report.md` 的反事实回放"
                     "(同一批真实入场意图,只换仓控)。")
    elif dd_ratio <= 1.25:
        verdict = "risk_increase_small"
        lines.append(f"**判定**:`{verdict}` —— 回撤放大 {dd_ratio:.2f}× ≤ 1.25×。")
    elif dd_ratio <= 1.60:
        verdict = "risk_increase_material"
        lines.append(f"**判定**:`{verdict}` —— 回撤放大 {dd_ratio:.2f}×,需要配熔断或降 risk_pct 再上。")
    else:
        verdict = "risk_increase_unacceptable"
        lines.append(f"**判定**:`{verdict}` —— 回撤放大 {dd_ratio:.2f}×,不可直接上线。")
    lines.append(f"\n- 尾部单笔风险倍数(P99/max):{risk_ratio:.2f}×")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="并行 paper 账本对比")
    parser.add_argument("--a", default="D:/AIDCA/AI300-fwdlib/logs_parallel/fib_pa_v1/paper", help="对照组状态目录")
    parser.add_argument("--b", default="D:/AIDCA/AI300-fwdlib/logs_parallel/risk_first/paper", help="实验组状态目录")
    parser.add_argument("--name-a", default="fib_pa_v1(旧口径)")
    parser.add_argument("--name-b", default="risk_first(风险优先)")
    parser.add_argument("--date", default="2026-10-19")
    args = parser.parse_args()

    arm_a = profile(Path(args.a))
    arm_b = profile(Path(args.b))
    report = build_report(args.name_a, arm_a, args.name_b, arm_b)

    out_dir = REPORTS_ROOT / args.date
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.md").write_text(report, encoding="utf-8")
    (out_dir / "metrics.json").write_text(
        json.dumps({"a": arm_a, "b": arm_b}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(report)
    print(f"[written] {out_dir / 'report.md'}")


if __name__ == "__main__":
    main()
