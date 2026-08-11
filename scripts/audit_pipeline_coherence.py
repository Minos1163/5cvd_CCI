# -*- coding: utf-8 -*-
"""audit_pipeline_coherence.py — 管道一致性审计(08-11 报告 3.2 规格 + 象限增强)。

检查每个 SCOUT mission 的自身 min_score 是否会被上游 near_miss 采样阈值
(--near-miss-min-score, 默认 82)截断:
  - 象限特定 mission(Q2/Q3 pending):象限分数天花板 < 82 → BLOCKING(永久 0 触发,
    第二次"管道未对齐"缺陷,Q2 已核实);
  - 非象限特定 mission(如 REVERSAL_PIVOT):min_score < 82 但候选来自高分 near_miss,
    门槛冗余无实际截断 → WARNING(仅提示)。

用法: python scripts/audit_pipeline_coherence.py [--config configs/...] [--near-miss-min-score 82]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.signals.entry_chain_config import load_entry_chain_config  # noqa: E402

# mission 名 → 配置键(min_score)
MISSION_MIN_SCORE_KEYS = {
    "REVERSAL_PIVOT_SCOUT": "scout_micro_reversal_pivot_min_score",
    "Q2_PENDING_MOMENTUM": "scout_micro_q2_pending_min_score",
    "Q3_TO_Q1_CONFIRMATION": "scout_micro_q3_to_q1_min_score",
    "Q1_RR_GAP_SCOUT": "scout_micro_q1_rr_gap_min_score",
    "HIGH_SCORE_LONG_OFFSET_PROBE": "scout_micro_high_score_long_offset_min_score",
    "FIB_CONTINUATION_SCOUT": "scout_micro_fib_continuation_min_score",
    "WATCH_ONLY_SYMBOL_PROMOTION_TEST": "scout_micro_watch_only_promotion_min_score",
    "SCOUT_ONLY_HIGH_SCORE": "scout_micro_scout_only_min_score",
}
# 象限特定 mission:候选象限的分数天花板低于全局阈值 → 被上游永久截断
QUADRANT_SPECIFIC = {
    "Q2_PENDING_MOMENTUM": "Q2(资金动能轴不过,分数天花板 <82)",
    "Q3_TO_Q1_CONFIRMATION": "Q3(趋势结构轴不过,分数天花板 <82)",
}


def audit_pipeline_coherence(config: object, near_miss_min_score: float = 82.0) -> dict:
    issues: list[dict] = []
    for mission, key in MISSION_MIN_SCORE_KEYS.items():
        mission_min = float(getattr(config, key, 0.0) or 0.0)
        if mission_min >= near_miss_min_score:
            issues.append(
                {
                    "mission": mission,
                    "mission_min_score": mission_min,
                    "upstream_near_miss_min_score": near_miss_min_score,
                    "severity": "OK",
                    "explanation": "mission 门槛 >= 上游采样阈值,不受截断",
                }
            )
            continue
        if mission in QUADRANT_SPECIFIC:
            issues.append(
                {
                    "mission": mission,
                    "mission_min_score": mission_min,
                    "upstream_near_miss_min_score": near_miss_min_score,
                    "severity": "BLOCKING",
                    "explanation": (
                        f"{mission} 门槛({mission_min}) < 上游 near_miss_min_score({near_miss_min_score});"
                        f"候选象限 {QUADRANT_SPECIFIC[mission]} 的分数天花板低于全局阈值,"
                        "候选在到达 mission 评估前被上游采样永久截断(第二次'管道未对齐')"
                    ),
                }
            )
        else:
            issues.append(
                {
                    "mission": mission,
                    "mission_min_score": mission_min,
                    "upstream_near_miss_min_score": near_miss_min_score,
                    "severity": "WARNING",
                    "explanation": (
                        f"{mission} 门槛({mission_min}) < 上游({near_miss_min_score}),"
                        "但非象限特定——候选来自高分 near_miss(>=82),门槛冗余,无实际截断"
                    ),
                }
            )
    return {
        "coherent": not any(i["severity"] == "BLOCKING" for i in issues),
        "near_miss_min_score": near_miss_min_score,
        "issues": issues,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(PROJECT_ROOT / "configs" / "entry_chain.dry_run_fib_pa_v1.json"))
    parser.add_argument("--near-miss-min-score", type=float, default=82.0)
    args = parser.parse_args()

    cfg = load_entry_chain_config(args.config)
    result = audit_pipeline_coherence(cfg, args.near_miss_min_score)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if not result["coherent"] else 0


if __name__ == "__main__":
    sys.exit(main())
