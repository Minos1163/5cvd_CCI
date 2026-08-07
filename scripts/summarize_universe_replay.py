# -*- coding: utf-8 -*-
"""summarize_universe_replay.py — 汇总全宇宙回放结果:每币 DIRECT/PROBE/WATCH/NO_TRADE
候选数,与基线(实际运行 6 天主账本 2 笔开仓)对比,输出 Markdown 表格片段(供 MD 引用)。

用法: python scripts/summarize_universe_replay.py [--in logs/analysis/universe_replay_opt.json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_IN = PROJECT_ROOT / "logs" / "analysis" / "universe_replay_opt.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--in", dest="in_path", default=str(DEFAULT_IN))
    args = parser.parse_args()

    data = json.loads(Path(args.in_path).read_text(encoding="utf-8"))
    print("| symbol | rows | DIRECT_OPEN | PROBE_OPEN | WATCH | NO_TRADE |")
    print("|---|---:|---:|---:|---:|---:|")
    total = {"DIRECT_OPEN": 0, "PROBE_OPEN": 0, "WATCH": 0}
    for item in data["per_symbol"]:
        sym = item.get("symbol", "?")
        if "error" in item:
            print(f"| {sym} | error: {item['error'][:40]} | | | | |")
            continue
        ba = item.get("by_action", {})
        total["DIRECT_OPEN"] += ba.get("DIRECT_OPEN", 0)
        total["PROBE_OPEN"] += ba.get("PROBE_OPEN", 0)
        total["WATCH"] += ba.get("WATCH", 0)
        print(
            f"| {sym} | {item.get('rows', 0)} | {ba.get('DIRECT_OPEN', 0)} | "
            f"{ba.get('PROBE_OPEN', 0)} | {ba.get('WATCH', 0)} | {ba.get('NO_TRADE', 0)} |"
        )
    print("|---|---:|---:|---:|---:|---:|")
    print(
        f"| **合计** | | **{total['DIRECT_OPEN']}** | **{total['PROBE_OPEN']}** | "
        f"**{total['WATCH']}** | |"
    )
    # 开仓样本(前 3 币 × 前 3)
    print("\n=== 各币 PROBE_OPEN 样本(时间/分数/象限) ===")
    for item in data["per_symbol"]:
        opens = item.get("open_samples", [])
        for s in opens[:2]:
            print(f"  {item['symbol']}: {s['bj']} {s['side']} score={s['score']} {s['quadrant']} {s['action']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
