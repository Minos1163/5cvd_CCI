# -*- coding: utf-8 -*-
"""counterfactual_q2_pending.py — Task A 反事实验证(08-11 方法论:部署前先证明修复有意义)。

统计历史 decisions 中"修复后能成为 Q2 pending 候选"的样本数:
Q2 象限、action ∈ {NO_TRADE, WATCH}、score >= scout_micro_q2_pending_min_score(70)、
price_action_structure >= 18(PA 门槛)——对照 08-11 报告反事实预测(36 pending 创建)。

用法: python scripts/counterfactual_q2_pending.py [--start 2026-08-02 --end 2026-08-11]
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

from src.signals.entry_chain_config import load_entry_chain_config  # noqa: E402


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
    parser.add_argument("--end", default="2026-08-11")
    parser.add_argument("--log-root", default="logs")
    parser.add_argument("--config", default=str(PROJECT_ROOT / "configs" / "entry_chain.dry_run_fib_pa_v1.json"))
    args = parser.parse_args()

    cfg = load_entry_chain_config(args.config)
    q2_pending_min = float(cfg.scout_micro_q2_pending_min_score)
    q2_pending_min_pa = float(cfg.scout_micro_q2_pending_min_pa_score)

    log_root = PROJECT_ROOT / args.log_root
    import datetime as dt

    d = dt.date.fromisoformat(args.start)
    end = dt.date.fromisoformat(args.end)
    days = []
    while d <= end:
        days.append(d.strftime("%Y-%m-%d"))
        d += dt.timedelta(days=1)

    q2_ge70 = 0
    q2_pending_eligible = 0  # score>=70 且 PA>=18 且 action 非 PROBE/DIRECT
    q2_all = 0
    by_symbol: Counter = Counter()
    for day in days:
        for row in load_jsonl(log_root / "2026-08" / day / "decisions.jsonl"):
            if str(row.get("quadrant") or "") != "Q2":
                continue
            q2_all += 1
            score = float(row.get("score") or 0.0)
            action = str(row.get("action") or "").upper()
            if score < q2_pending_min:
                continue
            q2_ge70 += 1
            if action in {"PROBE", "DIRECT"}:
                continue
            pa = float((row.get("component_points") or {}).get("price_action_structure") or 0.0)
            if pa < q2_pending_min_pa:
                continue
            q2_pending_eligible += 1
            by_symbol[str(row.get("symbol"))] += 1

    out = {
        "window": f"{args.start}~{args.end}",
        "q2_all_decisions": q2_all,
        "q2_score_ge70": q2_ge70,
        "q2_pending_eligible_created": q2_pending_eligible,  # 修复后能建 pending 的候选数
        "prediction_from_0811_report": 36,
        "match_prediction": q2_pending_eligible >= 30,
        "by_symbol_top": by_symbol.most_common(6),
        "note": "对照 08-11 报告反事实预测 36 pending 创建(±窗口差异);MFE/确认数引用报告口径",
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
