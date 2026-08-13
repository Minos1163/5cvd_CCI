# -*- coding: utf-8 -*-
"""summarize_experiment_pnl.py — 统计 four_quadrant_navigation_v1 实验账本累计 PnL,
判定 experiment_entry_circuit_active 是否触发(war_fund ≤ -150 / daily ≤ -200)。

用法: python scripts/summarize_experiment_pnl.py [--start 2026-08-02 --end 2026-08-13]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT_ID = "four_quadrant_navigation_v1"


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
    parser.add_argument("--end", default="2026-08-13")
    parser.add_argument("--log-root", default="logs")
    args = parser.parse_args()

    log_root = PROJECT_ROOT / args.log_root
    import datetime as dt

    d = dt.date.fromisoformat(args.start)
    end = dt.date.fromisoformat(args.end)
    days = []
    while d <= end:
        days.append(d.strftime("%Y-%m-%d"))
        d += dt.timedelta(days=1)

    total = 0.0
    daily: dict[str, float] = {}
    event_count = 0
    for day in days:
        day_total = 0.0
        for rel in ("scout_micro/paper_trades.jsonl", "paper_ab/legacy/paper_trades.jsonl", "paper_ab/trend_capture/paper_trades.jsonl"):
            for row in load_jsonl(log_root / "2026-08" / day / rel):
                if str(row.get("experiment_id") or "") != EXPERIMENT_ID:
                    continue
                pnl = float(row.get("margin_pnl") or 0.0)
                total += pnl
                day_total += pnl
                event_count += 1
        daily[day] = round(day_total, 4)

    out = {
        "experiment_id": EXPERIMENT_ID,
        "window": f"{args.start}~{args.end}",
        "events": event_count,
        "cumulative_pnl": round(total, 4),
        "war_fund_limit": -150.0,
        "war_fund_triggered": total <= -150.0,
        "worst_day": min(daily, key=daily.get),
        "worst_day_pnl": daily[min(daily, key=daily.get)],
        "daily_limit": -200.0,
        "daily_triggered_any": any(v <= -200.0 for v in daily.values()),
        "daily_by_day": daily,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
