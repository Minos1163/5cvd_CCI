# -*- coding: utf-8 -*-
"""summarize_atom_replay.py — 读 replay_atom_chain.py 输出,做门槛敏感性分析:
牛市段 LONG 周期在不同 direct 门槛(82/85/88/90/92)下可开仓数,
并输出最高分周期 TOP10 明细(供 MD 引用)。

用法: python scripts/summarize_atom_replay.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPLAY = PROJECT_ROOT / "logs" / "analysis" / "atom_replay.json"


def main() -> int:
    data = json.loads(REPLAY.read_text(encoding="utf-8"))
    rows = data["samples"]
    bull = [r for r in rows if r["bj"] <= "08-05 11:00" and r["bj"] >= "08-02 04:00" and r["side"] == "LONG"]
    # 全部 LONG 周期(回放窗口内)
    longs = [r for r in rows if r["side"] == "LONG"]

    print("=== 牛市段 LONG 周期(%d 根)门槛敏感性 ===" % len(bull))
    for th in (82, 85, 88, 90, 92):
        n = len([r for r in bull if r["score"] >= th])
        print(f"  direct_threshold={th}: 可开 {n} 笔")

    print("\n=== 牛市段 LONG 周期按象限 ===")
    q = {}
    for r in bull:
        q.setdefault(r["quadrant"], []).append(r)
    for k in ("Q1", "Q2", "Q3", "Q4"):
        v = q.get(k, [])
        if v:
            scores = sorted((r["score"] for r in v), reverse=True)
            print(f"  {k}: n={len(v)} max={max(scores)} p90={scores[max(0, int(len(scores)*0.1)-1)] if len(scores)>=10 else max(scores)}")
        else:
            print(f"  {k}: n=0")

    print("\n=== 牛市段 TOP10 高分 LONG(时间/分数/象限/action/组件) ===")
    for r in sorted(bull, key=lambda x: -x["score"])[:10]:
        print(
            f"  {r['bj']} score={r['score']} {r['quadrant']} {r['action']} "
            f"trend_ema={r['trend_ema']} pa={r['pa']} cvd={r['cvd']} cci={r['cci']} fib={r['fib']} rr={r['rr']}"
        )

    print("\n=== 趋势轴差距(trend_ema 距 15)分布(牛市段 LONG) ===")
    import collections

    gaps = collections.Counter()
    for r in bull:
        gap = 15.0 - r["trend_ema"]
        if gap <= 0:
            gaps["达标(>=15)"] += 1
        elif gap <= 2:
            gaps["差0-2分"] += 1
        elif gap <= 5:
            gaps["差2-5分"] += 1
        else:
            gaps["差>5分"] += 1
    for k, v in gaps.items():
        print(f"  {k}: {v}")

    # 08-04 00:00 前后(用户描述的 CCI 顶)的 LONG 周期
    print("\n=== 08-03 20:00 ~ 08-04 04:00(北京,CCI 顶附近) LONG 周期 ===")
    for r in rows:
        if "08-03 20:00" <= r["bj"] <= "08-04 04:00" and r["side"] == "LONG":
            print(f"  {r['bj']} score={r['score']} {r['quadrant']} {r['action']} trend_ema={r['trend_ema']} pa={r['pa']} cvd={r['cvd']} cci={r['cci']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
