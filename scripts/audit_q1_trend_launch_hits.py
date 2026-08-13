# -*- coding: utf-8 -*-
"""audit_q1_trend_launch_hits.py — 审计 q1_trend_launch 0 转化根因(08-13 审查 Phase 2)。

对 48H(08-12~08-13)near_misses 逐条运行真实 _q1_trend_launch_eligible 判定,
并分解各条件达标矩阵,定位"卡在哪一步"(象限/extreme/组件/方向防追单)。

用法: python scripts/audit_q1_trend_launch_hits.py [--start 2026-08-12 --end 2026-08-13]
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
from scripts.run_live_dry_run import (  # noqa: E402
    _component_point,
    _q1_trend_launch_eligible,
    decision_quadrant,
)


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
    parser.add_argument("--start", default="2026-08-12")
    parser.add_argument("--end", default="2026-08-13")
    parser.add_argument("--log-root", default="logs")
    parser.add_argument("--config", default=str(PROJECT_ROOT / "configs" / "entry_chain.dry_run_fib_pa_v1.json"))
    args = parser.parse_args()

    cfg = load_entry_chain_config(args.config)
    log_root = PROJECT_ROOT / args.log_root
    import datetime as dt

    d = dt.date.fromisoformat(args.start)
    end = dt.date.fromisoformat(args.end)
    days = []
    while d <= end:
        days.append(d.strftime("%Y-%m-%d"))
        d += dt.timedelta(days=1)

    near_misses: list[dict] = []
    for day in days:
        near_misses += load_jsonl(log_root / "2026-08" / day / "near_misses.jsonl")

    rows: list[dict] = []
    step_counter: Counter = Counter()
    for nm in near_misses:
        symbol = str(nm.get("symbol") or "").strip().upper()
        side = str(nm.get("intended_side") or "").upper()
        score = float(nm.get("score") or 0.0)
        quadrant = decision_quadrant(nm, cfg)
        entry_ctx = dict(nm.get("entry_context") or {})
        raw_extreme = entry_ctx.get("extreme_position_ratio")
        try:
            extreme = float(raw_extreme) if raw_extreme is not None else 0.5
        except (TypeError, ValueError):
            extreme = 0.5

        steps = {
            "q1": quadrant == "Q1",
            "side_ok": side in {"LONG", "SHORT"},
            "not_blacklisted": symbol not in cfg.blacklist_symbols,
            "extreme_range": float(cfg.dry_run_q1_trend_launch_extreme_ratio_min) <= extreme <= float(cfg.dry_run_q1_trend_launch_extreme_ratio_max),
            "score_min": score >= float(cfg.dry_run_q1_trend_launch_min_score),
            "pa_min": _component_point(nm, "price_action_structure") >= float(cfg.dry_run_q1_trend_launch_min_pa_score),
            "fib_min": _component_point(nm, "fibonacci_location") >= float(cfg.dry_run_q1_trend_launch_min_fib_score),
            "cvd_min": _component_point(nm, "flow_cvd_confirmation") >= float(cfg.dry_run_q1_trend_launch_min_cvd_score),
            "rr_min": _component_point(nm, "risk_reward_geometry") >= float(cfg.dry_run_q1_trend_launch_min_rr_score),
            "no_overext": not (
                side == "LONG"
                and (
                    entry_ctx.get("long_overextension_active")
                    or entry_ctx.get("long_upper_wick_risk_active")
                    or entry_ctx.get("long_chase_risk_active")
                )
            ),
        }
        # 首个不满足的步骤(定位卡点)
        order = ["q1", "side_ok", "not_blacklisted", "extreme_range", "score_min", "pa_min", "fib_min", "cvd_min", "rr_min", "no_overext"]
        first_fail = next((k for k in order if not steps[k]), "ALL_PASS")
        step_counter[first_fail] += 1
        eligible = _q1_trend_launch_eligible(nm, cfg, "OK")
        rows.append(
            {
                "symbol": symbol, "side": side, "quadrant": quadrant, "score": round(score, 1),
                "extreme": round(extreme, 3), "first_fail": first_fail, "eligible": eligible,
                "steps": {k: v for k, v in steps.items() if k in ("extreme_range", "score_min", "pa_min", "fib_min", "cvd_min", "rr_min", "no_overext")},
            }
        )

    hits = [r for r in rows if r["eligible"]]
    out = {
        "window": f"{args.start}~{args.end}",
        "near_misses_total": len(near_misses),
        "q1_trend_launch_eligible_hits": len(hits),
        "first_fail_distribution": dict(step_counter),
        "top_samples_by_score": sorted(rows, key=lambda r: -r["score"])[:8],
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
