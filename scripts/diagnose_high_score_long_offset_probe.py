# -*- coding: utf-8 -*-
"""诊断 HIGH_SCORE_LONG_OFFSET_PROBE 通道 0 触发根因。

对窗口(08-02 13:45 UTC ~ 08-04 11:00 UTC)内所有 near-miss 逐条件核对:
  A. symbol ∈ scout_micro_targeted_long_symbols
  B. quadrant == Q1
  C. intended_side == LONG
  D. reasons 含 SIDE_THRESHOLD_OFFSET_LONG_10.00 或 tags 含 TARGETED_LONG_OFFSET
  E. score >= scout_micro_high_score_long_offset_min_score
  F. PA >= min_pa_score
  G. Fib >= min_fib_score
  H. CVD >= min_cvd_score
  I. RR >= min_rr_score
定位最紧条件(候选在哪个条件被挡), 并输出校准建议。

用法: python scripts/diagnose_high_score_long_offset_probe.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
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


def main() -> int:
    config = load_entry_chain_config("configs/entry_chain.dry_run_fib_pa_v1.json")
    nm_all = load_near_misses()
    targeted = set(config.scout_micro_targeted_long_symbols or ())
    min_score = float(config.scout_micro_high_score_long_offset_min_score)
    min_pa = float(config.scout_micro_high_score_long_offset_min_pa_score)
    min_fib = float(config.scout_micro_high_score_long_offset_min_fib_score)
    min_cvd = float(config.scout_micro_high_score_long_offset_min_cvd_score)
    min_rr = float(config.scout_micro_high_score_long_offset_min_rr_score)

    print("probe 触发条件(当前配置):")
    print(f"  min_score={min_score} min_pa={min_pa} min_fib={min_fib} min_cvd={min_cvd} min_rr={min_rr}")
    print(f"  targeted_long_symbols={sorted(targeted)}")
    print()

    # 逐条件漏斗
    stage_names = ["A.symbol∈targeted", "B.quadrant==Q1", "C.side==LONG", "D.SIDE阈值原因", "E.score达标", "F.PA达标", "G.Fib达标", "H.CVD达标", "I.RR达标"]
    stage_count = Counter()
    stage_samples = defaultdict(list)
    for nm in nm_all:
        sym = str(nm.get("symbol") or "").upper()
        q = str(nm.get("quadrant") or "").upper()
        side = str(nm.get("intended_side") or nm.get("side") or "").upper()
        reasons = [str(r) for r in (nm.get("reasons") or [])]
        tags = [str(t) for t in (nm.get("scout_tags") or [])]
        score = float(nm.get("score") or 0.0)
        pa = component(nm, "price_action_structure")
        fib = component(nm, "fibonacci_location")
        cvd = component(nm, "flow_cvd_confirmation")
        rr = component(nm, "risk_reward_geometry")

        ok_symbol = sym in targeted
        ok_q1 = q in (config.scout_micro_high_score_long_offset_quadrants or ("Q1",))
        ok_long = side == "LONG"
        ok_reason = "SIDE_THRESHOLD_OFFSET_LONG_10.00" in reasons or "TARGETED_LONG_OFFSET" in tags
        ok_score = score >= min_score
        ok_pa = pa >= min_pa
        ok_fib = fib >= min_fib
        ok_cvd = cvd >= min_cvd
        ok_rr = rr >= min_rr

        checks = [ok_symbol, ok_q1, ok_long, ok_reason, ok_score, ok_pa, ok_fib, ok_cvd, ok_rr]
        # 记录通过到第 k 个条件的样本
        k = 0
        for idx, ok in enumerate(checks):
            if not ok:
                break
            k = idx + 1
        stage_count[k] += 1
        for i in range(k):
            stage_samples[stage_names[i]].append(nm)

    print(f"窗口 near-miss 总数: {len(nm_all)}")
    print("逐条件通过漏斗(通过到第 k 个条件的样本数):")
    for i, name in enumerate(stage_names):
        passed = stage_count[i + 1] if i + 1 <= max(stage_count) else 0
        print(f"  第{i+1}关 {name}: 通过 {stage_count[i+1]}")

    # 列出靠近 D 条件(LONG+SIDE阈值原因)的样本
    print()
    print("LONG + SIDE阈值原因 样本明细(通过 A-D 的候选):")
    near = stage_samples.get("D.SIDE阈值原因", [])
    for nm in sorted(near, key=lambda x: -float(x.get("score") or 0)):
        print("  %s %s %s score=%s %s pa=%s fib=%s cvd=%s rr=%s" % (
            nm.get("timestamp"), nm.get("symbol"), nm.get("intended_side"),
            nm.get("score"), nm.get("quadrant"),
            component(nm, "price_action_structure"), component(nm, "fibonacci_location"),
            component(nm, "flow_cvd_confirmation"), component(nm, "risk_reward_geometry")))

    print()
    print("诊断结论:")
    print("  全窗口 LONG 高分样本极少(see above); 若 RR(或 score)为最紧条件, "
          "建议按分布校准(如 min_rr 2.0→1.0, min_score 85→82 试点), 并保持 SCOUT-only。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
