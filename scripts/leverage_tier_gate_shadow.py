# -*- coding: utf-8 -*-
"""leverage_tier_gate_shadow.py — 4x 杠杆质量门控 shadow 反事实(08-31 评审 5.2)。

对窗口内 action=DIRECT 的决策应用 4x 质量门控(评审规格:fib≥10/pa≥7/rr≥5),
统计会降档的样本数与方向/象限分布;并单独核对三笔大额亏损样本是否达标。
SHADOW ONLY——不修改 live 杠杆选择。

用法: python scripts/leverage_tier_gate_shadow.py --start 2026-08-24 --end 2026-08-31
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# 评审 5.2 规格
GATE_4X = {"fibonacci_location": 10.0, "price_action_structure": 7.0, "risk_reward_geometry": 5.0}
# 三笔大额亏损样本(响应评审 6.3:归因审查)
TARGET_TRADES = (("2026-08-24", "BCHUSDT"), ("2026-08-24", "DOGEUSDT"), ("2026-08-28", "SOLUSDT"))


def load_decisions(log_root: Path, start: str, end: str) -> list[tuple[str, dict]]:
    rows: list[tuple[str, dict]] = []
    import datetime as dt

    day = dt.date.fromisoformat(start)
    final = dt.date.fromisoformat(end)
    while day <= final:
        path = log_root / day.strftime("%Y-%m") / day.strftime("%Y-%m-%d") / "decisions.jsonl"
        if path.exists():
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict):
                    rows.append((day.strftime("%Y-%m-%d"), payload))
        day += dt.timedelta(days=1)
    return rows


def gate_pass(component_points: dict, gates: dict) -> bool:
    return all(float(component_points.get(k) or 0.0) >= v for k, v in gates.items())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log-root", default="logs")
    parser.add_argument("--start", default="2026-08-24")
    parser.add_argument("--end", default="2026-08-31")
    parser.add_argument("--output-dir", default="logs/analysis/2026-08-31-leverage-gate")
    args = parser.parse_args()

    rows = load_decisions(PROJECT_ROOT / args.log_root, args.start, args.end)

    direct_rows = []
    for day, payload in rows:
        if str(payload.get("action") or "").upper() != "DIRECT":
            continue
        context = payload.get("entry_context") if isinstance(payload.get("entry_context"), dict) else {}
        direct_rows.append(
            {
                "day": day,
                "symbol": str(payload.get("symbol") or ""),
                "side": str(context.get("side") or payload.get("side") or "").upper(),
                "quadrant": str(payload.get("quadrant") or ""),
                "score": float(payload.get("score") or 0.0),
                "component_points": payload.get("component_points") or {},
            }
        )

    downgraded = [r for r in direct_rows if not gate_pass(r["component_points"], GATE_4X)]
    by_side = Counter(r["side"] for r in downgraded)
    by_quadrant = Counter(r["quadrant"] for r in downgraded)

    # 三笔大额亏损样本核对
    targets = []
    for day, payload in rows:
        symbol = str(payload.get("symbol") or "")
        if (day, symbol) in TARGET_TRADES:
            context = payload.get("entry_context") if isinstance(payload.get("entry_context"), dict) else {}
            if str(context.get("side") or payload.get("side") or "").upper() != "SHORT":
                continue
            cp = payload.get("component_points") or {}
            targets.append(
                {
                    "day": day, "symbol": symbol,
                    "quadrant": str(payload.get("quadrant") or ""),
                    "score": float(payload.get("score") or 0.0),
                    "rr_points": float(cp.get("risk_reward_geometry") or 0.0),
                    "fib_points": float(cp.get("fibonacci_location") or 0.0),
                    "pa_points": float(cp.get("price_action_structure") or 0.0),
                    "gate_4x_pass": gate_pass(cp, GATE_4X),
                }
            )

    out = {
        "assumptions": {
            "window": f"{args.start}~{args.end}",
            "gate_4x": GATE_4X,
            "scope": "SHADOW ONLY - live leverage selection unchanged",
        },
        "direct_decisions": len(direct_rows),
        "downgraded_by_4x_gate": len(downgraded),
        "downgrade_rate": round(len(downgraded) / max(1, len(direct_rows)), 4),
        "downgraded_by_side": dict(by_side),
        "downgraded_by_quadrant": dict(by_quadrant),
        "target_trades_review": targets,
    }
    out_dir = PROJECT_ROOT / args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "leverage_tier_gate_shadow.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
