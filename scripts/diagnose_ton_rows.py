# -*- coding: utf-8 -*-
"""diagnose_ton_rows.py — 排查 TONUSDT 在 08-02~08-05 回放 rows=0 的原因:
① 数据完整性(窗口内 bar 数/时间戳连续性)② 4 根变化率分布(direction_from_history
阈值 0.3%)③ 各周期(15m/1h)方向 NONE 比例。
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = PROJECT_ROOT / "data" / "raw" / "binance_futures" / "latest_30d" / "TONUSDT" / "15m.csv"
BEIJING_OFFSET_S = 8 * 3600


def main() -> int:
    rows = []
    with CSV_PATH.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append(
                {
                    "open_time": int(row["open_time"]),
                    "close": float(row["close"]),
                    "volume": float(row["volume"]),
                }
            )
    if not rows:
        print(json.dumps({"error": "TONUSDT 无数据文件"}, ensure_ascii=False))
        return 1

    import datetime as dt

    start_ts = int((dt.datetime(2026, 8, 2, 0, 0, tzinfo=dt.timezone.utc) - dt.timedelta(seconds=BEIJING_OFFSET_S)).timestamp() * 1000)
    end_ts = int((dt.datetime(2026, 8, 6, 0, 0, tzinfo=dt.timezone.utc) - dt.timedelta(seconds=BEIJING_OFFSET_S)).timestamp() * 1000)
    window = [r for r in rows if start_ts <= r["open_time"] < end_ts]

    # 时间戳连续性
    gaps = []
    for a, b in zip(window, window[1:]):
        gap = b["open_time"] - a["open_time"]
        if gap != 900_000:
            gaps.append((a["open_time"], gap))
    # 4 根变化率(方向判定:direction_from_history 用 close[i] vs close[i-3])
    changes = []
    for i in range(3, len(window)):
        prev = window[i - 3]["close"]
        if prev > 0:
            changes.append((window[i]["close"] - prev) / prev)
    long_n = sum(1 for c in changes if c > 0.003)
    short_n = sum(1 for c in changes if c < -0.003)
    none_n = len(changes) - long_n - short_n

    # 15m 单根变化率分布(整体波动特征)
    all_changes = [(rows[i]["close"] - rows[i - 1]["close"]) / rows[i - 1]["close"] for i in range(1, len(rows)) if rows[i - 1]["close"] > 0]
    out = {
        "csv_rows_total": len(rows),
        "csv_first": rows[0]["open_time"],
        "csv_last": rows[-1]["open_time"],
        "window_bars": len(window),
        "window_gaps_non_15m": gaps[:5],
        "window_gap_count": len(gaps),
        "dir_4bar_changes": len(changes),
        "dir_long": long_n,
        "dir_short": short_n,
        "dir_none": none_n,
        "dir_none_pct": round(none_n / len(changes) * 100, 1) if changes else None,
        "overall_1bar_abs_change_p50": round(sorted(abs(c) for c in all_changes)[len(all_changes) // 2], 5) if all_changes else None,
        "overall_1bar_abs_change_p90": round(sorted(abs(c) for c in all_changes)[int(len(all_changes) * 0.9)], 5) if all_changes else None,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
