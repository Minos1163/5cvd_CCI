"""Stage 3:ladder 出场口径与线上账本的一致性校验(G3 门禁)。

做法:取 paper_trades.jsonl 的 233 笔 PAPER_OPEN,按线上 1.2/2.0/3.0R 阶梯重放
decisions.jsonl 内嵌的 K 线,与同一笔的 REDUCE/CLOSE 腿对照:
  - 出场原因一致率(把线上 reason 归一为 3 类:止损 / 止盈阶梯 / 超时或最大持仓)
  - 单笔 R 的差(中位数与均值)

门禁:一致率 >= 90% 且 |均值 R 差| <= 0.05R,否则 ladder 结果标为「未验证」。
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fwd_label_20261019 as L  # noqa: E402

REASON_CLASS = {
    "INITIAL_STOP_HIT": "stop",
    "BREAKEVEN_STOP_HIT": "stop",
    "STOP_HIT": "stop",
    "Q2_STOP_TIGHTEN": "stop",
    "TP1_HIT": "tp",
    "TP2_HIT": "tp",
    "TP3_HIT": "tp",
    "TARGET_HIT": "tp",
    "MAX_HOLD_EXIT": "time",
    "MAX_HOLD": "time",
    "COST_BREAKEVEN_TIMEOUT": "time",
    "COST_BREAKEVEN_EXIT": "time",
    "Q3_DEFENSIVE_REDUCE": "defense",
    "Q4_DEFENSIVE_EXIT": "defense",
    "Q4_DEFENSIVE_FLATTEN": "defense",
}


def cls(reason: str) -> str:
    return REASON_CLASS.get(str(reason or "").upper(), "other")


def load_ledger(logs: str):
    trades = []
    pending = {}
    for p in sorted(Path(logs).glob("2026-*/*/paper_trades.jsonl")):
        for line in open(p, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            ev = r.get("event")
            sym = r.get("symbol")
            if ev == "PAPER_OPEN":
                trade = {
                    "symbol": sym, "ts": int(r["timestamp"]), "side": r["side"],
                    "entry_price": float(r["price"]), "notional": float(r["notional"]),
                    "quantity": float(r["quantity"]), "legs": [],
                    "exit_mode": r.get("exit_mode"), "experiment_id": r.get("experiment_id"),
                    "open_cost": float(r.get("fee") or 0.0) + float(r.get("slippage") or 0.0),
                }
                trades.append(trade)
                pending[sym] = trade
            elif ev in {"PAPER_REDUCE", "PAPER_CLOSE"} and sym in pending:
                pending[sym]["legs"].append({
                    "reason": r.get("reason"), "price": float(r["price"]),
                    "quantity": float(r["quantity"]), "fraction": float(r.get("fraction") or 0.0),
                    "fee": float(r.get("fee") or 0.0) + float(r.get("slippage") or 0.0),
                    "ts": int(r["timestamp"]),
                })
                if ev == "PAPER_CLOSE":
                    pending.pop(sym, None)
    return trades


def realized_R(trade, stop_pct):
    sign = 1.0 if trade["side"] == "LONG" else -1.0
    gross = sum((leg["price"] - trade["entry_price"]) * sign * leg["quantity"] for leg in trade["legs"])
    cost = trade["open_cost"] + sum(leg["fee"] for leg in trade["legs"])
    risk = trade["notional"] * stop_pct
    return (gross - cost) / risk, gross / risk


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--logs", default="logs")
    ap.add_argument("--out", default="reports/analysis/stop-floor-20261019")
    ap.add_argument("--months", default="2026-06,2026-07,2026-08,2026-09,2026-10")
    ap.add_argument("--quadrant-defense", action="store_true",
                    help="把 Q3 减半 / Q4 防御全平纳入重放(线上仅在 experiment_id 非空时生效)")
    ap.add_argument("--q2-tighten", action="store_true",
                    help="把 Q2 止损收紧到成本纳入重放(线上仅在 experiment_id 非空时生效)")
    args = ap.parse_args()

    months = [m.strip() for m in args.months.split(",") if m.strip()]
    paths = []
    for m in months:
        paths += sorted(Path(args.logs).glob(f"{m}/*/decisions.jsonl"))
    decisions = L.load_decisions([str(p) for p in paths], profile="any")
    stop_map = {(d["symbol"], d["ts"]): d["stop_pct"] for d in decisions if d.get("stop_pct")}
    bars, per_symbol, index = L.build_bars(decisions)
    quad_map = L.build_quadrant_map(decisions)

    trades = load_ledger(args.logs)
    closed = [t for t in trades if t["legs"]]
    rows = []
    missing_stop = 0
    for t in closed:
        stop = stop_map.get((t["symbol"], t["ts"]))
        if not stop:
            missing_stop += 1
            continue
        d = {"symbol": t["symbol"], "ts": t["ts"], "side": t["side"], "stop_pct": stop}
        has_exp = bool(t.get("experiment_id"))
        sim = L.label_ladder(
            bars, per_symbol, index, d, float(stop), entry_mode="bar_close",
            quad_map=quad_map,
            quadrant_defense=args.quadrant_defense and has_exp,
            q2_tighten=args.q2_tighten and has_exp,
            post_tp_mode="trend_capture" if str(t.get("exit_mode") or "").lower() == "trend_capture" else "legacy",
        )
        if sim is None:
            continue
        r_net, r_gross = realized_R(t, float(stop))
        ledger_class = cls(t["legs"][-1]["reason"])
        sim_class = cls(sim["reason"])
        rows.append({
            "symbol": t["symbol"], "ts": t["ts"], "side": t["side"], "stop_pct": float(stop),
            "ledger_reason": t["legs"][-1]["reason"], "sim_reason": sim["reason"],
            "ledger_class": ledger_class, "sim_class": sim_class,
            "ledger_R_net": round(r_net, 4), "sim_R_net": round(sim["R"], 4),
            "ledger_R_gross": round(r_gross, 4), "sim_R_gross": round(sim["gross_R"], 4),
            "ledger_bars": (t["legs"][-1]["ts"] - t["ts"]) // 900,
            "sim_bars": sim["bars"], "match_class": ledger_class == sim_class,
            "match_reason": str(t["legs"][-1]["reason"]).upper() == sim["reason"],
        })

    if not rows:
        raise SystemExit("no comparable trades")
    agree = sum(r["match_class"] for r in rows) / len(rows)
    agree_exact = sum(r["match_reason"] for r in rows) / len(rows)
    diffs = [r["sim_R_net"] - r["ledger_R_net"] for r in rows]
    d_gross = [r["sim_R_gross"] - r["ledger_R_gross"] for r in rows]
    result = {
        "matched_trades": len(rows),
        "missing_stop_pct": missing_stop,
        "class_agreement": round(agree, 4),
        "exact_reason_agreement": round(agree_exact, 4),
        "median_R_diff": round(statistics.median(diffs), 4),
        "mean_R_diff": round(statistics.fmean(diffs), 4),
        "mean_gross_R_diff": round(statistics.fmean(d_gross), 4),
        "ledger_mean_R_net": round(statistics.fmean([r["ledger_R_net"] for r in rows]), 4),
        "sim_mean_R_net": round(statistics.fmean([r["sim_R_net"] for r in rows]), 4),
        "ledger_reasons": dict(Counter(r["ledger_reason"] for r in rows).most_common()),
        "sim_reasons": dict(Counter(r["sim_reason"] for r in rows).most_common()),
        "gate_pass": bool(agree >= 0.90 and abs(statistics.fmean(diffs)) <= 0.05),
    }
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "ladder_consistency.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "ladder_consistency_trades.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if not isinstance(v, dict)}, ensure_ascii=False, indent=2))
    print("ledger_reasons:", result["ledger_reasons"])
    print("sim_reasons:", result["sim_reasons"])


if __name__ == "__main__":
    main()
