# -*- coding: utf-8 -*-
"""SCOUT mission 可达性诊断 — 逐 mission 计算窗口内候选的可达率与最紧条件。

结论定位(基于代码 L1071-1107 路由):
  - Q2_PENDING_MOMENTUM / Q3_TO_Q1_CONFIRMATION 为纯标签依赖型(eligible 只查 scout_tags),
    其 0 触发的根因与 q1_trend_launch 同源: 确认标签生成链路(confirm_q2_to_q1 /
    confirm_q3_to_q1)依赖 pending 状态建立, 窗口内标签 0 次出现。
  - 其余 mission(REVERSAL_PIVOT / FIB_CONTINUATION / WATCH_ONLY_PROMOTION /
    SCOUT_ONLY_HIGH_SCORE / HIGH_SCORE_LONG_OFFSET)逐条件判定, 输出最紧条件。

用法: python scripts/diagnose_scout_mission_reachability.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.signals.entry_chain_config import load_entry_chain_config  # noqa: E402

LOGS = Path("logs/2026-08")
DAYS = ["2026-08-02", "2026-08-03", "2026-08-04"]
WINDOW_START = 1785678305
WINDOW_END = 1785841205


def load_near_misses():
    rows = []
    for day in DAYS:
        p = LOGS / day / "near_misses.jsonl"
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
                if isinstance(d, dict) and WINDOW_START <= int(d.get("timestamp") or 0) <= WINDOW_END:
                    rows.append(d)
    return rows


def component(nm, key):
    pts = nm.get("component_points") or {}
    return float(pts.get(key) or 0.0)


def quadrant_of(nm, cfg):
    """按 quadrant_axes 判定(与 decision_quadrant 一致), 复刻于脚本避免依赖符号策略。"""
    trend_ok = (component(nm, "trend_ema_context") >= float(cfg.quadrant_trend_ema_min)
                and component(nm, "price_action_structure") >= float(cfg.quadrant_price_action_min))
    flow_ok = (component(nm, "flow_cvd_confirmation") >= float(cfg.quadrant_flow_cvd_min)
               and component(nm, "cci_momentum_quality") >= float(cfg.quadrant_cci_min))
    if trend_ok and flow_ok:
        return "Q1"
    if trend_ok:
        return "Q2"
    if flow_ok:
        return "Q3"
    return "Q4"


def reasons_of(nm):
    return [str(r) for r in (nm.get("reasons") or [])]


def tags_of(nm):
    return [str(t) for t in (nm.get("scout_tags") or [])]


def main() -> int:
    cfg = load_entry_chain_config("configs/entry_chain.dry_run_fib_pa_v1.json")
    nms = load_near_misses()
    print(f"窗口 near-miss 总数: {len(nms)}")
    print()

    # mission 定义: (名称, [条件列表]) — 每个条件 (说明, 判定函数)
    missions = {
        "REVERSAL_PIVOT_SCOUT": [
            ("enabled", lambda n: bool(cfg.scout_micro_reversal_pivot_enabled)),
            ("side∈LONG/SHORT", lambda n: str(n.get("intended_side") or "").upper() in {"LONG", "SHORT"}),
            ("score>=70", lambda n: float(n.get("score") or 0.0) >= float(cfg.scout_micro_reversal_pivot_min_score)),
            ("Q∈Q1/Q2/Q3", lambda n: quadrant_of(n, cfg) in {"Q1", "Q2", "Q3"}),
            ("衰竭/对立警示", lambda n: "FIB_EXTENSION_EXHAUSTION_BLOCK" in reasons_of(n)
                 or str((n.get("diagnostics") or {}).get("risk_reward_geometry", {}).get("rr_zero_reason") or "").upper() == "OPPOSITION_STRUCTURE_TOO_CLOSE"),
            ("cvd<=16 或 cci<=10", lambda n: component(n, "flow_cvd_confirmation") <= float(cfg.scout_micro_reversal_pivot_max_cvd_score)
                 or component(n, "cci_momentum_quality") <= float(cfg.scout_micro_reversal_pivot_max_cci_score)),
        ],
        "Q2_PENDING_MOMENTUM(标签依赖)": [
            ("enabled", lambda n: bool(cfg.scout_micro_q2_pending_enabled)),
            ("标签 Q2_PENDING_MOMENTUM_CONFIRMED", lambda n: "Q2_PENDING_MOMENTUM_CONFIRMED" in tags_of(n)),
        ],
        "Q3_TO_Q1_CONFIRMATION(标签依赖)": [
            ("enabled", lambda n: bool(cfg.scout_micro_q3_to_q1_enabled)),
            ("标签 Q3_TO_Q1_CONFIRMED", lambda n: "Q3_TO_Q1_CONFIRMED" in tags_of(n)),
        ],
        "Q1_RR_GAP_SCOUT": [
            ("enabled", lambda n: bool(cfg.scout_micro_q1_rr_gap_enabled)),
        ],
        "HIGH_SCORE_LONG_OFFSET_PROBE": [
            ("symbol∈targeted_long", lambda n: str(n.get("symbol") or "").upper() in set(cfg.scout_micro_targeted_long_symbols or ())),
            ("Q∈配置quadrants", lambda n: quadrant_of(n, cfg) in (cfg.scout_micro_high_score_long_offset_quadrants or ("Q1",))),
            ("side==LONG", lambda n: str(n.get("intended_side") or "").upper() == "LONG"),
            ("SIDE阈值原因", lambda n: "SIDE_THRESHOLD_OFFSET_LONG_10.00" in reasons_of(n) or "TARGETED_LONG_OFFSET" in tags_of(n)),
            ("score>=82", lambda n: float(n.get("score") or 0.0) >= float(cfg.scout_micro_high_score_long_offset_min_score)),
            ("PA>=18", lambda n: component(n, "price_action_structure") >= float(cfg.scout_micro_high_score_long_offset_min_pa_score)),
            ("Fib>=15", lambda n: component(n, "fibonacci_location") >= float(cfg.scout_micro_high_score_long_offset_min_fib_score)),
            ("CVD>=14", lambda n: component(n, "flow_cvd_confirmation") >= float(cfg.scout_micro_high_score_long_offset_min_cvd_score)),
            ("RR>=2.0", lambda n: component(n, "risk_reward_geometry") >= float(cfg.scout_micro_high_score_long_offset_min_rr_score)),
        ],
        "FIB_CONTINUATION_SCOUT": [
            ("FIB衰竭原因", lambda n: "FIB_EXTENSION_EXHAUSTION_BLOCK" in reasons_of(n)),
            ("side∈LONG/SHORT", lambda n: str(n.get("intended_side") or "").upper() in {"LONG", "SHORT"}),
            ("score>=82", lambda n: float(n.get("score") or 0.0) >= float(cfg.scout_micro_fib_continuation_min_score)),
            ("EMA>=16", lambda n: component(n, "trend_ema_context") >= float(cfg.scout_micro_fib_continuation_min_ema_score)),
            ("CVD>=14", lambda n: component(n, "flow_cvd_confirmation") >= float(cfg.scout_micro_fib_continuation_min_cvd_score)),
            ("PA>=18", lambda n: component(n, "price_action_structure") >= float(cfg.scout_micro_fib_continuation_min_pa_score)),
        ],
        "WATCH_ONLY_SYMBOL_PROMOTION_TEST": [
            ("symbol∈watch_only", lambda n: str(n.get("symbol") or "").upper() in set(cfg.watch_only_symbols or ())),
            ("WATCH_ONLY原因", lambda n: "SYMBOL_WATCH_ONLY" in reasons_of(n)),
            ("score>=87", lambda n: float(n.get("score") or 0.0) >= float(cfg.scout_micro_watch_only_promotion_min_score)),
            ("Fib/PA/RR 门槛", lambda n: component(n, "fibonacci_location") >= float(cfg.scout_micro_scout_only_min_fib_score)
                 and component(n, "price_action_structure") >= float(cfg.scout_micro_scout_only_min_pa_score)
                 and component(n, "risk_reward_geometry") >= float(cfg.scout_micro_scout_only_min_rr_score)),
        ],
        "SCOUT_ONLY_HIGH_SCORE": [
            ("symbol∈scout_only", lambda n: str(n.get("symbol") or "").upper() in set(cfg.scout_micro_scout_only_symbols or ())),
            ("score>=85", lambda n: float(n.get("score") or 0.0) >= float(cfg.scout_micro_scout_only_min_score)),
            ("Fib>=12/PA>=10/RR>=4", lambda n: component(n, "fibonacci_location") >= float(cfg.scout_micro_scout_only_min_fib_score)
                 and component(n, "price_action_structure") >= float(cfg.scout_micro_scout_only_min_pa_score)
                 and component(n, "risk_reward_geometry") >= float(cfg.scout_micro_scout_only_min_rr_score)),
        ],
    }

    report = {}
    for name, conds in missions.items():
        matched = list(nms)
        funnel = []
        for label, fn in conds:
            before = len(matched)
            matched = [n for n in matched if fn(n)]
            funnel.append((label, before, len(matched)))
        report[name] = {"reachable": len(matched), "funnel": funnel}
        print(f"=== {name} ===")
        print(f"  可达候选: {len(matched)}")
        for label, before, after in funnel:
            dropped = before - after
            mark = " ← 最紧条件" if dropped == max((f[2] for f in funnel), default=0) and dropped > 0 else ""
            print(f"    {label:<28} 前{before:>3} → 后{after:>3} (拦截{dropped:>2}){mark}")
        if matched:
            for n in matched[:5]:
                print(f"      样例: {n.get('timestamp')} {n.get('symbol')} {n.get('intended_side')} score={n.get('score')}")
        print()

    # 汇总表
    print("=== 汇总 ===")
    print(f"{'mission':<34} {'可达':>4} {'结论'}")
    for name, r in report.items():
        if r["reachable"] > 0:
            verdict = "可触发"
        elif any(l[0].startswith("标签") for l in r["funnel"]):
            verdict = "标签依赖(确认链未发生)"
        else:
            verdict = "门槛不可达(见最紧条件)"
        print(f"{name:<34} {r['reachable']:>4}  {verdict}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
