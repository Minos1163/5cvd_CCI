# -*- coding: utf-8 -*-
"""channel_cumulative_tracker.py — 通道累计样本追踪器(08-18 评审 6.2 节 + 10.2 节)。

按 entry_channel 累计各账本(主账本/scout/mirror)的开仓样本与 PnL,
输出"四通道平等对比表"(评审 4.3 节格式):累计样本/累计 PnL/距 20 笔评估门槛。
固化 SAMPLE_SIZE_DECISION_RULES(评审 5.2 节):
  <10 样本:不"证明有效/提炼特征"(仅陈述结果)
  <20 样本:不调参数/不资源倾斜
  负信号 2 窗口一致:可停用/降级(如 mirror 三轮一致)

用法: python scripts/channel_cumulative_tracker.py [--start 2026-08-02 --end 2026-08-18]
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# 评审 5.2 节:小样本决策规则(统一纪律)
SAMPLE_SIZE_DECISION_RULES = {
    "min_samples_for_any_narrative": 10,
    "min_samples_for_parameter_adjustment": 20,
    "min_samples_for_priority_boost": 20,
    "negative_signal_special_case_windows": 2,
}

# 四通道(08-18 评审 4.3 节:平等对比,不突出"唯一正")
TRACKED_CHANNELS = (
    "q1_trend_launch",
    "scout_q2_pending_momentum",
    "scout_q3_to_q1_confirmation",
    "scout_high_score_long_offset_probe",
    "scout_bnb_trend_continuation_after_pullback",
    "scout_bull_regime_breakout_v1",
    "mirror_ab_sample",
)

LEDGER_PATHS = (
    "paper_trades.jsonl",                     # 主账本
    "scout_micro/paper_trades.jsonl",         # scout
    "paper_ab/legacy/paper_trades.jsonl",     # mirror legacy
    "paper_ab/trend_capture/paper_trades.jsonl",  # mirror trend
)

# 通道 → 限定账本路径(避免 mirror 镜像记录混入主账本通道统计,08-18 追踪器修正)
CHANNEL_LEDGER_SCOPE = {
    "q1_trend_launch": ("paper_trades.jsonl",),
    "scout_q2_pending_momentum": ("scout_micro/paper_trades.jsonl",),
    "scout_q3_to_q1_confirmation": ("scout_micro/paper_trades.jsonl",),
    "scout_high_score_long_offset_probe": ("scout_micro/paper_trades.jsonl",),
    "scout_bnb_trend_continuation_after_pullback": ("scout_micro/paper_trades.jsonl",),
    "scout_bull_regime_breakout_v1": ("scout_micro/paper_trades.jsonl",),
    "mirror_ab_sample": ("paper_ab/legacy/paper_trades.jsonl", "paper_ab/trend_capture/paper_trades.jsonl"),
}


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
    parser.add_argument("--end", default="2026-08-18")
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

    stats: dict[str, dict] = defaultdict(lambda: {"opens": 0, "pnl": 0.0, "first": None, "last": None, "events": 0})
    for day in days:
        for channel in TRACKED_CHANNELS:
            for rel in CHANNEL_LEDGER_SCOPE.get(channel, LEDGER_PATHS):
                for row in load_jsonl(log_root / "2026-08" / day / rel):
                    if str(row.get("entry_channel") or "unknown") != channel:
                        continue
                    event = str(row.get("event") or "")
                    s = stats[channel]
                    if "OPEN" in event:
                        s["opens"] += 1
                    s["events"] += 1
                    s["pnl"] += float(row.get("margin_pnl") or 0.0)
                    ts = int(row.get("timestamp") or 0)
                    if ts:
                        s["first"] = s["first"] or ts
                        s["last"] = max(s["last"] or 0, ts)
                    s["day"] = day

    print("| 通道 | 累计样本 | 累计PnL | 距20笔 | 判定 |")
    print("|---|---:|---:|---:|---|")
    for ch in TRACKED_CHANNELS:
        s = stats[ch]
        remaining = max(0, 20 - s["opens"])
        if s["opens"] < SAMPLE_SIZE_DECISION_RULES["min_samples_for_any_narrative"]:
            verdict = "仅记录(不提炼/不优先)"
        elif s["opens"] < 20:
            verdict = "观察中(距评估门槛)"
        else:
            verdict = "达20笔,可评估"
        print(f"| {ch} | {s['opens']} | {round(s['pnl'], 3)} | {remaining} | {verdict} |")

    out = {
        "window": f"{args.start}~{args.end}",
        "sample_size_rules": SAMPLE_SIZE_DECISION_RULES,
        "channels": {ch: stats[ch] for ch in TRACKED_CHANNELS},
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
