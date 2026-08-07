# -*- coding: utf-8 -*-
"""analyze_baseline_window.py — 用 08-02~08-07 实际运行日志(decisions.jsonl /
near_misses.jsonl / paper_trades.jsonl)统计现状基线:决策数、象限分布、平均分、
高分样本、near-miss、主账本开仓。比重跑离线回测引擎更贴近线上真实表现。

用法: python scripts/analyze_baseline_window.py --start 2026-08-02 --end 2026-08-07
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2026-08-02")
    parser.add_argument("--end", default="2026-08-07")
    parser.add_argument("--log-root", default="logs")
    args = parser.parse_args()

    log_root = PROJECT_ROOT / args.log_root
    days = []
    import datetime as dt

    d = dt.date.fromisoformat(args.start)
    end = dt.date.fromisoformat(args.end)
    while d <= end:
        days.append(d.strftime("%Y-%m-%d"))
        d += dt.timedelta(days=1)

    decisions: list[dict] = []
    near_misses: list[dict] = []
    paper_trades: list[dict] = []
    for day in days:
        day_dir = log_root / "2026-08" / day
        decisions += load_jsonl(day_dir / "decisions.jsonl")
        near_misses += load_jsonl(day_dir / "near_misses.jsonl")
        paper_trades += load_jsonl(day_dir / "paper_trades.jsonl")

    quadrant_counts = Counter(str(d.get("quadrant")) for d in decisions)
    actions = Counter(str(d.get("action")) for d in decisions)
    scores = [float(d.get("score") or 0) for d in decisions]
    high80 = [d for d in decisions if (d.get("score") or 0) >= 80]
    high85 = [d for d in decisions if (d.get("score") or 0) >= 85]

    summary = {
        "window": f"{args.start}~{args.end}",
        "decisions": len(decisions),
        "quadrant_counts": dict(quadrant_counts),
        "actions": dict(actions),
        "avg_score": round(sum(scores) / len(scores), 2) if scores else None,
        "max_score": round(max(scores), 2) if scores else None,
        "score_ge80": len(high80),
        "score_ge85": len(high85),
        "near_misses": len(near_misses),
        "near_miss_quadrants": dict(Counter(str(n.get("quadrant")) for n in near_misses)),
        "near_miss_avg_score": round(sum(float(n.get("score") or 0) for n in near_misses) / len(near_misses), 2) if near_misses else None,
        "paper_trades_opens": len([t for t in paper_trades if "OPEN" in str(t.get("event", ""))]),
        "paper_trades_events": len(paper_trades),
        "high85_symbols": Counter(str(d.get("symbol")) for d in high85),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
