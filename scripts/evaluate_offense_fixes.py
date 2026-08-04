# -*- coding: utf-8 -*-
"""evaluate_offense_fixes.py — Phase 3-4 综合评估与验收脚本。

在部署修复并运行一段时间后执行(建议 24h 后跑第一次, 20 笔/30 笔样本时跑第二次),
评估三项修复的在线效果:

1) q1_trend_launch 通道: 是否产生转化(DRY_RUN_Q1_TREND_LAUNCH 标记)与实验账本 PnL
2) HIGH_SCORE_LONG_OFFSET_PROBE: SCOUT 开/平/PnL(是否收集满 20 笔; 满后 PF>1 → offset 可校准)
3) Payoff A/B: trend_capture_mirror(试点) vs legacy(对照) 的 PF/payoff/胜率

用法:
  python scripts/evaluate_offense_fixes.py --log-root logs --days 2
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

TREND_LAUNCH_MARKERS = ("DRY_RUN_Q1_TREND_LAUNCH",)
PROBE_CHANNEL = "high_score_long_offset_probe"
MIN_PROBE_SAMPLES = 20
MIN_PAYOFF_SAMPLES = 30


def load_window(log_root: Path, relpaths: list[str], start_day: str, end_day: str) -> dict[str, list[dict]]:
    import datetime as dt

    out: dict[str, list[dict]] = defaultdict(list)
    day = dt.date.fromisoformat(start_day)
    end = dt.date.fromisoformat(end_day)
    while day <= end:
        for rel in relpaths:
            p = log_root / day.strftime("%Y-%m") / day.strftime("%Y-%m-%d") / rel
            if not p.exists():
                continue
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        d = json.loads(line)
                    except Exception:
                        continue
                    if isinstance(d, dict):
                        out[rel].append(d)
        day += dt.timedelta(days=1)
    return out


def trades_pf(rows: list[dict], pnl_key: str = "margin_pnl") -> dict:
    # 仅整仓平仓(PAPER_CLOSE)计入; PAPER_REDUCE 是 TP 分档减仓, 计入会造成同一交易重复计数
    closes = [r for r in rows if r.get("event") == "PAPER_CLOSE"]
    pnl = sum(float(r.get(pnl_key) or 0.0) for r in closes)
    wins = [r for r in closes if float(r.get(pnl_key) or 0.0) > 0]
    losses = [r for r in closes if float(r.get(pnl_key) or 0.0) <= 0]
    gross_win = sum(float(r.get(pnl_key) or 0.0) for r in wins)
    gross_loss = abs(sum(float(r.get(pnl_key) or 0.0) for r in losses))
    avg_win = gross_win / len(wins) if wins else 0.0
    avg_loss = gross_loss / len(losses) if losses else 0.0
    return {
        "opens": sum(1 for r in rows if r.get("event") == "PAPER_OPEN"),
        "closes": len(closes),
        "pnl": round(pnl, 4),
        "win_rate": round(len(wins) / len(closes), 4) if closes else None,
        "pf": round(gross_win / gross_loss, 4) if gross_loss > 0 else None,
        "payoff_ratio": round(avg_win / avg_loss, 4) if avg_loss > 0 else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 3-4 综合评估")
    parser.add_argument("--log-root", default="logs")
    parser.add_argument("--days", type=int, default=2)
    args = parser.parse_args()

    import datetime as dt

    log_root = Path(args.log_root)
    end_day = dt.date.today()
    start_day = end_day - dt.timedelta(days=args.days)
    rels = [
        "decisions.jsonl",
        "near_misses.jsonl",
        "scout_micro/paper_trades.jsonl",
        "paper_ab/legacy/paper_trades.jsonl",
        "paper_ab/trend_capture/paper_trades.jsonl",
        "paper_trades.jsonl",
    ]
    data = load_window(log_root, rels, start_day.strftime("%Y-%m-%d"), end_day.strftime("%Y-%m-%d"))

    # 1) q1_trend_launch 转化
    tl_rows = [d for d in data["decisions.jsonl"] if any(m in (d.get("reasons") or []) for m in TREND_LAUNCH_MARKERS)]
    tl_main = [r for r in data["paper_trades.jsonl"] if "q1_trend_launch" in str(r.get("entry_channel") or "")]
    print("== 1) q1_trend_launch 通道 ==")
    print(f"   决策标记数: {len(tl_rows)} | 主账本开仓: {trades_pf(tl_main)['opens']}")
    if tl_main:
        print(f"   主账本事件: {trades_pf(tl_main)}")
    verdict1 = "PASS(有转化)" if tl_rows else "WAIT(样本未积累, 需继续运行)"

    # 2) LONG probe
    probe_rows = [r for r in data["scout_micro/paper_trades.jsonl"] if PROBE_CHANNEL in str(r.get("entry_channel") or "")]
    probe_stats = trades_pf(probe_rows)
    print("\n== 2) HIGH_SCORE_LONG_OFFSET_PROBE ==")
    print(f"   开仓: {probe_stats['opens']} | 平仓: {probe_stats['closes']} | PnL: {probe_stats['pnl']} | PF: {probe_stats['pf']}")
    if probe_stats["closes"] >= MIN_PROBE_SAMPLES:
        if probe_stats["pf"] is not None and probe_stats["pf"] > 1.0:
            verdict2 = f"PASS({probe_stats['closes']} 笔, PF>1 → offset 可按分布校准)"
        else:
            verdict2 = f"FAIL({probe_stats['closes']} 笔但 PF={probe_stats['pf']} ≤1 → offset 不调整)"
    else:
        verdict2 = f"WAIT(平仓 {probe_stats['closes']}/{MIN_PROBE_SAMPLES} 笔)"

    # 3) Payoff A/B
    legacy = trades_pf(data["paper_ab/legacy/paper_trades.jsonl"])
    trend = trades_pf(data["paper_ab/trend_capture/paper_trades.jsonl"])
    print("\n== 3) Payoff A/B(trend_capture_mirror 试点 vs legacy 对照) ==")
    print(f"   legacy:  {legacy}")
    print(f"   trend:   {trend}")
    if legacy["closes"] >= MIN_PAYOFF_SAMPLES and trend["closes"] >= MIN_PAYOFF_SAMPLES:
        trend_better = (trend["pf"] or 0) > (legacy["pf"] or 0)
        verdict3 = f"PASS(样本满, trend PF {trend['pf']} vs legacy {legacy['pf']})" if trend_better else \
            f"FAIL(样本满但 trend PF {trend['pf']} ≤ legacy {legacy['pf']})"
    else:
        verdict3 = f"WAIT(legacy {legacy['closes']}/trend {trend['closes']} / {MIN_PAYOFF_SAMPLES} 笔)"

    print("\n== 验收汇总 ==")
    print(f"   q1_trend_launch: {verdict1}")
    print(f"   LONG probe:      {verdict2}")
    print(f"   Payoff A/B:      {verdict3}")
    failed = any(v.startswith("FAIL") for v in (verdict1, verdict2, verdict3))
    print(f"   退出码: {1 if failed else 0}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
