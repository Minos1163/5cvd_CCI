# -*- coding: utf-8 -*-
"""summarize_channel_stats.py — 按 entry_channel 统计 SCOUT/A-B paper_trades 的
开仓数/事件数/margin_pnl 累计(用于基线核对:REVERSAL_PIVOT_SCOUT 累计、LONG offset 等)。

用法: python scripts/summarize_channel_stats.py --channel scout_reversal_pivot_scout
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
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
    parser.add_argument("--channel", required=True)
    parser.add_argument("--start", default="2026-08-02")
    parser.add_argument("--end", default="2026-08-11")
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

    opens, closes, margin_total, notional_total = 0, 0, 0.0, 0.0
    for day in days:
        for rel in ("scout_micro/paper_trades.jsonl", "paper_ab/legacy/paper_trades.jsonl", "paper_ab/trend_capture/paper_trades.jsonl"):
            for row in load_jsonl(log_root / "2026-08" / day / rel):
                if str(row.get("entry_channel") or "") != args.channel:
                    continue
                event = str(row.get("event") or "")
                if "OPEN" in event:
                    opens += 1
                if "CLOSE" in event or "REDUCE" in event:
                    closes += 1
                margin_total += float(row.get("margin_pnl") or 0.0)
                notional_total += float(row.get("notional") or 0.0)

    print(
        json.dumps(
            {
                "channel": args.channel,
                "window": f"{args.start}~{args.end}",
                "opens": opens,
                "close_reduce_events": closes,
                "margin_pnl_total": round(margin_total, 4),
                "avg_margin_pnl_per_event": round(margin_total / max(1, opens + closes), 4),
                "notional_total": round(notional_total, 2),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
