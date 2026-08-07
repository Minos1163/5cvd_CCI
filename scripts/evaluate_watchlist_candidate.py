# -*- coding: utf-8 -*-
"""evaluate_watchlist_candidate.py — 显式白名单准入评估(评审 7.2/8.2 规格)。

基于候选的回放/回测统计,按准入标准决策:
  - 样本数 < min_samples(默认 20) → REJECT(样本不足,继续积累)
  - PF < pf_min(默认 1.0)       → REJECT(无正期望)
  - 通过                          → APPROVE(首次一律 scout_only)

用法:
  python scripts/evaluate_watchlist_candidate.py --symbol ATOMUSDT \
      --candidates 12 --win-rate 0.42 --pf 1.35
  python scripts/evaluate_watchlist_candidate.py --symbol ATOMUSDT --input logs/analysis/atom_stats.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def evaluate(
    symbol: str,
    candidates: int,
    win_rate: float,
    pf: float,
    min_samples: int = 20,
    pf_min: float = 1.0,
) -> dict:
    reasons: list[str] = []
    if candidates < min_samples:
        reasons.append(f"样本不足({candidates} < {min_samples})")
    if pf < pf_min:
        reasons.append(f"PF {pf:.3f} < {pf_min}")
    approved = not reasons
    return {
        "symbol": symbol,
        "candidates": candidates,
        "win_rate": round(win_rate, 4),
        "pf": round(pf, 4),
        "min_samples": min_samples,
        "pf_min": pf_min,
        "decision": "APPROVE" if approved else "REJECT",
        "scan_scope": "scout_only" if approved else None,
        "reasons": reasons,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--candidates", type=int, default=0)
    parser.add_argument("--win-rate", type=float, default=0.0)
    parser.add_argument("--pf", type=float, default=0.0)
    parser.add_argument("--min-samples", type=int, default=20)
    parser.add_argument("--pf-min", type=float, default=1.0)
    parser.add_argument("--input", default="")
    args = parser.parse_args()

    if args.input:
        stats = json.loads(Path(args.input).read_text(encoding="utf-8"))
        candidates = int(stats.get("candidates") or stats.get("candidate_count") or 0)
        win_rate = float(stats.get("win_rate") or 0.0)
        pf = float(stats.get("pf") or stats.get("profit_factor") or 0.0)
        result = evaluate(
            args.symbol, candidates, win_rate, pf,
            min_samples=args.min_samples, pf_min=args.pf_min,
        )
    else:
        result = evaluate(
            args.symbol, args.candidates, args.win_rate, args.pf,
            min_samples=args.min_samples, pf_min=args.pf_min,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["decision"] == "APPROVE" else 1


if __name__ == "__main__":
    sys.exit(main())
