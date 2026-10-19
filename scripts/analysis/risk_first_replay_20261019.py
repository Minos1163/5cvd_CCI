"""风险优先 vs 旧口径:同一批真实入场意图的反事实回放。

问题
----
旧口径把名义压到 ``equity × max_single_trade_risk_pct / (stop_pct × leverage)``,
于是 ``risk_first_sizing_enabled=true`` 会让同名 ``risk_pct`` 下的名义放大约 3.2 倍。
放大本身不是问题,问题是:单笔风险分布与最大回撤变成什么样,是否还能接受。

做法
----
1. 从真实 ``decisions.jsonl`` 取出**已通过的入场意图**(action ∈ {DIRECT, PROBE});
2. 用 ``fwdlib`` 的 barrier 标注给每笔意图一个净 R(32 根、20bps、next_open);
3. 对同一批意图分别用两份配置算 ``_notional_cap_diagnostics`` → 单笔风险 = 名义×stop/权益;
4. 按时间顺序复利累加 ``权益 × 单笔风险 × R_net``,比较风险分布与最大回撤。

注意:这是**反事实回放**,不是实盘并行。它只回答「同样的入场、同样的 R,换仓控后
风险和回撤会变成什么样」,不回答「换仓控后收益会不会更好」——入场集没变。
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import OrderedDict
from dataclasses import replace
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fwdlib.config import LabelConfig
from fwdlib.features import load_decisions
from fwdlib.labeler import run_labeling  # noqa: E402
from src.signals.entry_chain import (  # noqa: E402
    EntryChainContext,
    _notional_cap_diagnostics,
    _select_leverage,
)
from src.signals.entry_chain_config import load_entry_chain_config  # noqa: E402
from src.signals.entry_chain_gates import symbol_exposure_cap  # noqa: E402

EQUITY = 10_000.0
AVAILABLE_MARGIN = 8_000.0


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, int(round(q * (len(ordered) - 1)))))
    return ordered[idx]


def _max_drawdown(equity_curve: list[float]) -> tuple[float, int]:
    peak = equity_curve[0]
    worst = 0.0
    worst_at = 0
    for i, value in enumerate(equity_curve):
        peak = max(peak, value)
        dd = value / peak - 1.0
        if dd < worst:
            worst = dd
            worst_at = i
    return worst, worst_at


def _context(decision: dict) -> EntryChainContext:
    scores = {
        key: float(value)
        for key, value in (decision.get("feat") or {}).items()
        if isinstance(value, (int, float))
    }
    return EntryChainContext(
        symbol=str(decision["symbol"]).upper(),
        timestamp=int(decision["ts"]),
        side=str(decision["side"]).upper(),
        component_scores=scores,
        quote_volume_24h=10 ** float((decision.get("feat") or {}).get("log_qv", 6.0)),
        atr_pct=float(decision.get("atr_pct") or 0.01),
        expected_order_size=1000.0,
        account_equity=EQUITY,
        available_margin=AVAILABLE_MARGIN,
        stop_pct=decision.get("stop_pct"),
        symbol_exposure_pct=0.0,
    )


def replay(decisions: list[dict], cfg, labeled_by_key: dict[tuple[str, int], dict]) -> dict:
    trades = []
    for decision in decisions:
        if str(decision.get("action") or "") not in {"DIRECT", "PROBE"}:
            continue
        key = (str(decision["symbol"]).upper(), int(decision["ts"]))
        label = labeled_by_key.get(key)
        if label is None:
            continue
        ctx = _context(decision)
        cap = symbol_exposure_cap(ctx.symbol, cfg)
        leverage = _select_leverage(str(decision["action"]), float(decision.get("score") or 0.0), ctx, cfg, [])
        diag = _notional_cap_diagnostics(
            str(decision["action"]), float(decision.get("score") or 0.0), ctx, cfg, cap, selected_leverage=leverage
        )
        stop_pct = float(diag["stop_pct"] or 0.0)
        if stop_pct <= 0:
            continue
        notional = float(diag["final_notional"])
        trades.append(
            {
                "ts": int(decision["ts"]),
                "symbol": ctx.symbol,
                "action": decision["action"],
                "leverage": leverage,
                "stop_pct": stop_pct,
                "notional": notional,
                "risk_pct": notional * stop_pct / EQUITY,
                "R_net": float(label.get("R_net") or 0.0),
                "binding_cap": diag["binding_cap"],
            }
        )
    trades.sort(key=lambda t: t["ts"])

    equity = [EQUITY]
    for trade in trades:
        pnl = equity[-1] * trade["risk_pct"] * trade["R_net"]
        equity.append(equity[-1] + pnl)
    dd, dd_at = _max_drawdown(equity)
    risks = [t["risk_pct"] for t in trades]
    return {
        "trades": len(trades),
        "risk_pct_median": median(risks) if risks else 0.0,
        "risk_pct_p90": _percentile(risks, 0.9),
        "risk_pct_max": max(risks) if risks else 0.0,
        "risk_pct_total": sum(risks),
        "notional_median": median([t["notional"] for t in trades]) if trades else 0.0,
        "final_equity": equity[-1],
        "return_pct": equity[-1] / EQUITY - 1.0,
        "max_drawdown_pct": dd,
        "max_drawdown_at_trade": dd_at,
        "sum_R_net": sum(t["R_net"] for t in trades),
        "binding_caps": _count([t["binding_cap"] for t in trades]),
    }


def _count(values: list[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for value in values:
        out[value] = out.get(value, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="风险优先 vs 旧口径的反事实回放")
    parser.add_argument("--logs", default=str(Path("D:/AIDCA/AI300-fwdlib/logs")))
    parser.add_argument("--months", default="2026-08,2026-09,2026-10")
    parser.add_argument("--config", default="configs/entry_chain.dry_run_fib_pa_v1.json")
    parser.add_argument("--out", default="logs/analysis/risk-first/2026-10-19")
    args = parser.parse_args(argv)

    log_root = Path(args.logs)
    paths: list[str] = []
    for month in args.months.split(","):
        paths.extend(str(p) for p in sorted((log_root / month.strip()).glob("*/decisions.jsonl")))
    decisions = load_decisions(paths, profile="any", include_v2=False)
    print(f"decisions loaded: {len(decisions)}", flush=True)

    cfg = LabelConfig()
    labeled, _bars, _per, _idx, _quad = run_labeling(decisions, exit_mode="barrier", cfg=cfg)
    labeled_by_key = {(str(row["symbol"]).upper(), int(row["ts"])): row for row in labeled}
    print(f"labeled: {len(labeled_by_key)}", flush=True)

    base_cfg = load_entry_chain_config(args.config)
    risk_first_cfg = replace(base_cfg, risk_first_sizing_enabled=True)

    baseline = replay(decisions, base_cfg, labeled_by_key)
    risk_first = replay(decisions, risk_first_cfg, labeled_by_key)

    ratio_median = (
        risk_first["risk_pct_median"] / baseline["risk_pct_median"]
        if baseline["risk_pct_median"]
        else None
    )
    report = OrderedDict(
        {
            "window": args.months,
            "config": args.config,
            "baseline": baseline,
            "risk_first": risk_first,
            "risk_ratio_median": round(ratio_median, 4) if ratio_median else None,
            "dd_ratio": (
                round(risk_first["max_drawdown_pct"] / baseline["max_drawdown_pct"], 4)
                if baseline["max_drawdown_pct"]
                else None
            ),
            "verdict": _verdict(baseline, risk_first, ratio_median),
        }
    )

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "metrics.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "report.md").write_text(render(report), encoding="utf-8")
    print(json.dumps({"out": str(out_dir), "verdict": report["verdict"]}, ensure_ascii=False))
    return 0


def _verdict(baseline: dict, risk_first: dict, ratio: float | None) -> str:
    """只做可接受性判断,不做收益判断(入场集相同,R 相同)。"""
    if not baseline["trades"]:
        return "no_trades"
    if ratio is None or ratio < 1.5:
        return "risk_increase_small"
    dd = risk_first["max_drawdown_pct"]
    if dd <= -0.10:
        return "risk_increase_large_and_dd_beyond_10pct"
    if dd <= -0.05:
        return "risk_increase_large_dd_5_to_10pct"
    return "risk_increase_large_dd_within_5pct"


def render(report: dict) -> str:
    b = report["baseline"]
    r = report["risk_first"]

    def row(name: str, key: str, fmt: str) -> str:
        return f"| {name} | {format(b[key], fmt)} | {format(r[key], fmt)} |"

    lines = [
        "# 风险优先 vs 旧口径:反事实回放",
        "",
        f"- 窗口:{report['window']}",
        f"- 配置:{report['config']}(risk_first 仅切换 `risk_first_sizing_enabled`)",
        f"- 回放口径:真实入场意图 + barrier 标注(32 根 / 20bps / next_open),权益按单笔风险复利",
        "",
        "| 指标 | 旧口径 | 风险优先 |",
        "|---|---:|---:|",
        row("入场意图数", "trades", "d"),
        row("单笔风险 中位数", "risk_pct_median", ".4%"),
        row("单笔风险 P90", "risk_pct_p90", ".4%"),
        row("单笔风险 最大值", "risk_pct_max", ".4%"),
        row("名义 中位数", "notional_median", ".0f"),
        row("ΣR_net", "sum_R_net", ".2f"),
        row("期末权益", "final_equity", ".0f"),
        row("区间收益", "return_pct", ".2%"),
        row("最大回撤", "max_drawdown_pct", ".2%"),
        "",
        f"- 单笔风险倍数(中位数):**{report['risk_ratio_median']}×**",
        f"- 回撤倍数:**{report['dd_ratio']}×**(回撤为负,倍数取绝对值)",
        f"- 旧口径 binding caps:{b['binding_caps']}",
        f"- 风险优先 binding caps:{r['binding_caps']}",
        "",
        f"**判定**:`{report['verdict']}`",
        "",
        "> 这份回放**不能**回答「换仓控后是否更赚钱」——入场集与 R 都相同,只放大/缩小了每笔的权益暴露。"
        "它只用于判断 3.2 倍风险放大是否可接受;收益结论必须来自 paper 并行或独立回测。",
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
