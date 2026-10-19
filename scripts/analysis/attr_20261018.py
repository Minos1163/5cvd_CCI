"""Attribute paper-trading losses 2026-10-04 .. 2026-10-18.

Reads only local log files. Writes JSON + CSV summaries into
reports/analysis/2026-10-18-restart-attribution/.

P&L basis: `position_realized_pnl` (the only field the ledger books).
R basis  : price move / per-symbol median stop_pct from attribution.jsonl.
"""
from __future__ import annotations

import csv
import json
import os
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone

LOG_ROOT = r"D:/AIDCA/AI300/logs/2026-10"
OUT = r"D:/AIDCA/AI300/reports/analysis/2026-10-18-restart-attribution"
START, END = "2026-10-04", "2026-10-18"
# ledger snapshot boundaries used to align trade records with equity deltas
LO, HI = 1791156600, 1792328405


def day_dirs():
    out = []
    for name in sorted(os.listdir(LOG_ROOT)):
        d = os.path.join(LOG_ROOT, name)
        if os.path.isdir(d) and START <= name <= END:
            out.append((name, d))
    return out


def load_closes():
    rows = []
    for day, d in day_dirs():
        p = os.path.join(d, "paper_trades.jsonl")
        if not os.path.exists(p):
            continue
        with open(p, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("event") != "PAPER_CLOSE":
                    continue
                if not (LO <= rec["timestamp"] <= HI):
                    continue
                rec["_day"] = day
                rows.append(rec)
    return rows


def load_stops():
    """Per-symbol median stop distance from decision logs."""
    buckets = defaultdict(list)
    for _, d in day_dirs():
        p = os.path.join(d, "attribution.jsonl")
        if not os.path.exists(p):
            continue
        with open(p, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                dec = rec.get("decision") or {}
                ec = (dec.get("metadata") or {}).get("entry_context") or {}
                s, sym = ec.get("stop_pct"), dec.get("symbol")
                if s and sym:
                    buckets[sym].append(s)
    return {k: statistics.median(v) for k, v in buckets.items()}


def load_equity():
    out = []
    for day, d in day_dirs():
        p = os.path.join(d, "paper_equity.json")
        if not os.path.exists(p):
            continue
        with open(p, "r", encoding="utf-8") as fh:
            eq = json.load(fh)
        eq["_day"] = day
        out.append(eq)
    return out


def load_rejections():
    rows = []
    for _, d in day_dirs():
        p = os.path.join(d, "gate_rejections.jsonl")
        if not os.path.exists(p):
            continue
        with open(p, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return rows


def enrich(rows, stops):
    for r in rows:
        r["_p"] = r.get("position_realized_pnl", 0.0)
        qty = r.get("quantity", 0) or 0
        direction = 1 if r["side"] == "LONG" else -1
        gross = r.get("gross_pnl", 0.0)
        r["_entry"] = r["price"] - gross / (qty * direction) if qty else None
        r["_mv"] = (r["price"] - r["_entry"]) / r["_entry"] * direction if r["_entry"] else 0.0
        stop = stops.get(r["symbol"], 0.006)
        r["_stop"] = stop
        r["_r"] = r["_mv"] / stop if stop else 0.0
    return rows


def agg(rows):
    n = len(rows)
    p = [r["_p"] for r in rows]
    w = [x for x in p if x > 0]
    l = [x for x in p if x <= 0]
    rw = [r["_r"] for r in rows if r["_p"] > 0]
    rl = [r["_r"] for r in rows if r["_p"] <= 0]
    return {
        "trades": n,
        "net_pnl": round(sum(p), 2),
        "win_rate": round(len(w) / n, 4) if n else None,
        "avg_win": round(statistics.mean(w), 2) if w else None,
        "avg_loss": round(statistics.mean(l), 2) if l else None,
        "payoff_usd": round(statistics.mean(w) / abs(statistics.mean(l)), 3) if w and l else None,
        "avg_r_win": round(statistics.mean(rw), 2) if rw else None,
        "avg_r_loss": round(statistics.mean(rl), 2) if rl else None,
        "median_r_win": round(statistics.median(rw), 2) if rw else None,
        "payoff_r": round(statistics.mean(rw) / abs(statistics.mean(rl)), 3) if rw and rl else None,
        "avg_move_pct": round(statistics.mean([r["_mv"] for r in rows]) * 100, 3) if n else None,
    }


def group(rows, fn):
    b = defaultdict(list)
    for r in rows:
        b[str(fn(r))].append(r)
    return dict(sorted(((k, agg(v)) for k, v in b.items()), key=lambda kv: kv[1]["net_pnl"]))


def main():
    stops = load_stops()
    rows = enrich(load_closes(), stops)
    equity = load_equity()
    rej = load_rejections()

    summary = {
        "window": {"start": START, "end": END, "lo_ts": LO, "hi_ts": HI},
        "pnl_basis": "position_realized_pnl",
        "symbol_stop_pct": {k: round(v, 4) for k, v in sorted(stops.items())},
        "equity_curve": [
            {
                "day": e["_day"],
                "equity": round(e["equity"], 2),
                "realized_notional_pnl": round(e["realized_notional_pnl"], 2),
                "max_drawdown": round(e["max_drawdown"], 4),
                "open_positions": e.get("open_positions"),
            }
            for e in equity
        ],
        "overall": agg(rows),
        "by_exit_reason": group(rows, lambda r: r.get("reason")),
        "by_channel": group(rows, lambda r: r.get("entry_channel")),
        "by_leverage": group(rows, lambda r: r.get("leverage")),
        "by_symbol": group(rows, lambda r: r.get("symbol")),
        "by_side": group(rows, lambda r: r.get("side")),
        "by_quadrant": group(rows, lambda r: r.get("source_quadrant")),
        "by_day": group(rows, lambda r: r.get("_day")),
        "by_hour_utc": group(
            rows, lambda r: datetime.fromtimestamp(r["timestamp"], tz=timezone.utc).hour
        ),
        "accounting_gap": {
            "net_pnl": round(sum(r.get("net_pnl", 0) for r in rows), 2),
            "gross_pnl": round(sum(r.get("gross_pnl", 0) for r in rows), 2),
            "position_realized_pnl": round(sum(r.get("position_realized_pnl", 0) for r in rows), 2),
            "position_margin_realized_pnl": round(
                sum(r.get("position_margin_realized_pnl", 0) for r in rows), 2
            ),
            "records_with_gap_gt_0_5": sum(
                1
                for r in rows
                if abs((r.get("position_realized_pnl") or 0) - r.get("net_pnl", 0)) > 0.5
            ),
        },
        "costs": {
            "fee": round(sum(abs(r.get("fee", 0)) for r in rows), 2),
            "slippage": round(sum(abs(r.get("slippage", 0)) for r in rows), 2),
        },
    }

    reasons, actions = Counter(), Counter()
    for r in rej:
        for x in str(r.get("reasons", "")).split("|"):
            if x:
                reasons[x] += 1
        actions[r.get("action")] += 1
    summary["gate_rejections"] = {
        "records": len(rej),
        "by_action": dict(actions.most_common()),
        "top_reasons": dict(reasons.most_common(15)),
    }

    with open(os.path.join(OUT, "attribution_summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)

    with open(os.path.join(OUT, "trades.csv"), "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(
            [
                "day", "ts_utc", "symbol", "side", "quadrant", "channel", "lev",
                "entry", "exit", "stop_pct", "move_pct", "R",
                "pnl_realized", "net_pnl", "fee", "slip", "mfe_r", "reason",
            ]
        )
        for r in sorted(rows, key=lambda x: x["timestamp"]):
            w.writerow(
                [
                    r["_day"],
                    datetime.fromtimestamp(r["timestamp"], tz=timezone.utc).strftime("%Y-%m-%d %H:%M"),
                    r.get("symbol"), r.get("side"), r.get("source_quadrant"),
                    r.get("entry_channel"), r.get("leverage"),
                    round(r["_entry"], 6) if r["_entry"] else "",
                    r.get("price"), round(r["_stop"], 4), round(r["_mv"] * 100, 3),
                    round(r["_r"], 2), round(r["_p"], 2), round(r.get("net_pnl", 0), 2),
                    round(abs(r.get("fee", 0)), 4), round(abs(r.get("slippage", 0)), 4),
                    round(r.get("max_favorable_r_observed", 0), 2), r.get("reason"),
                ]
            )

    o = summary["overall"]
    lines = [
        f"window {START}..{END}  basis=position_realized_pnl",
        f"trades={o['trades']} net={o['net_pnl']} win_rate={o['win_rate']} "
        f"payoff_usd={o['payoff_usd']} payoff_r={o['payoff_r']}",
        "",
    ]
    for key in ["by_exit_reason", "by_channel", "by_leverage", "by_symbol", "by_side", "by_quadrant", "by_day"]:
        lines.append(f"## {key}")
        for k, v in summary[key].items():
            lines.append(
                f"  {k:<24} n={v['trades']:<3} net={v['net_pnl']:>9} win={v['win_rate']} "
                f"payoffR={v['payoff_r']} avgR={v['avg_r_win']}/{v['avg_r_loss']}"
            )
        lines.append("")
    lines.append("## accounting_gap")
    lines.append(json.dumps(summary["accounting_gap"], ensure_ascii=False))
    with open(os.path.join(OUT, "digest.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
