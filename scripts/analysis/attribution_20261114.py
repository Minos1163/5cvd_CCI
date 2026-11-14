"""2026-11-08 → 2026-11-14 主账本盈亏归因。

口径（与 2026-10-31 评审裁定一致）：
- 仓位级净额 = Σ(PAPER_CLOSE + PAPER_REDUCE 的 net_pnl_full)
- net_pnl_full 已含出场成本并摊分建仓成本，是本项目唯一权威口径
- 不使用 net_pnl（close-only，少一笔建仓成本）
- 不使用 margin_pnl（deprecated，net×leverage 双计）
- 不跨日累加 summary 计数器

输出：reports/2026-11-14_attribution/ 下的 JSON 与 Markdown。
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median, pstdev

ROOT = Path(__file__).resolve().parents[2]
LOGS = ROOT / "logs" / "2026-11"
OUT = ROOT / "reports" / "2026-11-14_attribution"

START = int(datetime(2026, 11, 8, 0, 0, tzinfo=timezone.utc).timestamp())
RESTART_TS = int(datetime(2026, 11, 9, 12, 54, 31, tzinfo=timezone.utc).timestamp())


def fmt(ts: int) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%m-%d %H:%M")


def load_events(paths) -> list[dict]:
    out: list[dict] = []
    for p in paths:
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def build_positions(events: list[dict]) -> list[dict]:
    """按 position_id 重建仓位级记录。"""
    by_pos: dict[str, dict] = {}
    for e in events:
        pid = e.get("position_id")
        if not pid:
            continue
        rec = by_pos.setdefault(
            pid,
            {
                "position_id": pid,
                "net_full": 0.0,
                "gross": 0.0,
                "entry_cost": 0.0,
                "exit_cost": 0.0,
                "closed": False,
                "reduces": 0,
                "exit_reasons": [],
            },
        )
        if e["event"] == "PAPER_OPEN":
            rec.update(
                {
                    "symbol": e.get("symbol"),
                    "side": e.get("side"),
                    "entry_time": e.get("entry_time") or e.get("timestamp"),
                    "entry_price": e.get("entry_price"),
                    "notional": e.get("notional"),
                    "stop_pct": (e.get("risk_distance") or 0) / (e.get("entry_price") or 1) or None,
                    "risk_distance": e.get("risk_distance"),
                    "leverage": e.get("leverage"),
                    "score": e.get("score"),
                    "source_quadrant": e.get("source_quadrant"),
                    "entry_channel": e.get("entry_channel"),
                    "exit_mode": e.get("exit_mode"),
                    "scout_mission": e.get("scout_mission"),
                    "entry_fee": (e.get("fee") or 0) + (e.get("slippage") or 0),
                }
            )
            rec["entry_cost"] += (e.get("fee") or 0) + (e.get("slippage") or 0)
        else:
            rec["net_full"] += e.get("net_pnl_full") or 0.0
            rec["gross"] += e.get("gross_pnl") or 0.0
            rec["exit_cost"] += (e.get("fee") or 0) + (e.get("slippage") or 0)
            rec["exit_reasons"].append(e.get("reason"))
            if e["event"] == "PAPER_CLOSE":
                rec["closed"] = True
                rec["exit_time"] = e.get("timestamp")
                rec["exit_reason"] = e.get("reason")
                rec["mfe"] = e.get("max_favorable_r_observed")
            else:
                rec["reduces"] += 1
                rec["mfe"] = e.get("max_favorable_r_observed")
    return [r for r in by_pos.values() if r.get("symbol")]


def summarize(rows: list[dict]) -> dict:
    nets = [r["net_full"] for r in rows]
    wins = [v for v in nets if v > 0]
    losses = [v for v in nets if v < 0]
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    risks = [
        (r.get("notional") or 0.0) * (r.get("stop_pct") or 0.0)
        for r in rows
        if r.get("notional") and r.get("stop_pct")
    ]
    valid_risk = [x for x in risks if x > 0]
    return {
        "n": len(rows),
        "net_total": round(sum(nets), 6),
        "gross_total": round(sum(r["gross"] for r in rows), 6),
        "cost_total": round(sum(r["entry_cost"] + r["exit_cost"] for r in rows), 6),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(len(wins) / len(rows), 4) if rows else None,
        "avg_win": round(mean(wins), 4) if wins else None,
        "avg_loss": round(mean(losses), 4) if losses else None,
        "payoff": round(mean(wins) / abs(mean(losses)), 3) if wins and losses else None,
        "profit_factor": round(gross_win / gross_loss, 3) if gross_loss else None,
        "expectancy": round(mean(nets), 4) if rows else None,
        "sd": round(pstdev(nets), 4) if len(nets) > 1 else None,
        "median": round(median(nets), 4) if rows else None,
        "avg_risk_usdt": round(mean(valid_risk), 4) if valid_risk else None,
    }


def group(rows: list[dict], key: str) -> dict:
    buckets: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        buckets[str(r.get(key))].append(r)
    return {k: summarize(v) for k, v in sorted(buckets.items(), key=lambda kv: -sum(x["net_full"] for x in kv[1]))}


def main() -> None:
    per_day = sorted(p for p in LOGS.glob("*/paper_trades.jsonl"))
    events = load_events(per_day)
    positions_all = build_positions(events)
    closed_all = [p for p in positions_all if p.get("closed")]

    # 分窗口：11-08 起 / 11-09 重启后
    win_a = [p for p in closed_all if (p.get("exit_time") or 0) >= START]
    win_b = [p for p in closed_all if (p.get("exit_time") or 0) >= RESTART_TS]

    report = {
        "meta": {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "window_start_utc": datetime(2026, 11, 8, tzinfo=timezone.utc).isoformat(),
            "restart_point_utc": datetime(2026, 11, 9, 12, 54, 31, tzinfo=timezone.utc).isoformat(),
            "log_days": len(per_day),
            "events": len(events),
            "positions_all": len(positions_all),
            "positions_closed": len(closed_all),
            "pnl_basis": "sum(net_pnl_full) per position_id; full-cost",
        },
        "window_11_08_onward": summarize(win_a),
        "window_after_restart": summarize(win_b),
        "all_november": summarize(closed_all),
        "by_symbol": group(win_a, "symbol"),
        "by_side": group(win_a, "side"),
        "by_quadrant": group(win_a, "source_quadrant"),
        "by_channel": group(win_a, "entry_channel"),
        "by_exit_reason": group(win_a, "exit_reason"),
        "positions": [
            {
                "position_id": p["position_id"],
                "symbol": p.get("symbol"),
                "side": p.get("side"),
                "entry_utc": fmt(p["entry_time"]) if p.get("entry_time") else None,
                "exit_utc": fmt(p["exit_time"]) if p.get("exit_time") else None,
                "hold_min": round((p["exit_time"] - p["entry_time"]) / 60, 1)
                if p.get("exit_time") and p.get("entry_time")
                else None,
                "net_pnl_full": round(p["net_full"], 6),
                "gross": round(p["gross"], 6),
                "cost": round(p["entry_cost"] + p["exit_cost"], 6),
                "notional": p.get("notional"),
                "risk_usdt": round((p.get("notional") or 0) * (p.get("stop_pct") or 0), 4),
                "stop_pct": round(p["stop_pct"] * 100, 3) if p.get("stop_pct") else None,
                "leverage": p.get("leverage"),
                "score": p.get("score"),
                "quadrant": p.get("source_quadrant"),
                "channel": p.get("entry_channel"),
                "exit_reason": p.get("exit_reason"),
                "reduces": p.get("reduces"),
                "mfe_r": p.get("mfe"),
                "r_multiple": round(p["net_full"] / ((p.get("notional") or 0) * (p.get("stop_pct") or 1)), 3)
                if p.get("notional") and p.get("stop_pct")
                else None,
            }
            for p in sorted(win_a, key=lambda x: -(x["net_full"]))
        ],
    }

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "attribution.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    s = report["window_11_08_onward"]
    print("=== 11-08 起已平仓 ===")
    print(json.dumps(s, ensure_ascii=False, indent=1))
    print("\n=== 逐笔 ===")
    print(f"{'symbol':10s}{'side':7s}{'entry':12s}{'exit':12s}{'hold':>7s}{'net':>9s}{'R':>7s}{'stop%':>7s}{'q':>4s}{'reason':22s}")
    for p in report["positions"]:
        print(
            f"{p['symbol']:10s}{p['side'] or '':7s}{p['entry_utc'] or '':12s}{p['exit_utc'] or '':12s}"
            f"{(p['hold_min'] or 0):7.0f}{p['net_pnl_full']:9.3f}{(p['r_multiple'] or 0):7.2f}"
            f"{(p['stop_pct'] or 0):7.2f}{(p['quadrant'] or ''):>4s}  {p['exit_reason'] or '':22s}"
        )
    print("\n=== 按退出原因 ===")
    for k, v in report["by_exit_reason"].items():
        print(f"{k:26s} n={v['n']:2d} net={v['net_total']:+8.3f} exp={v['expectancy']:+.3f}")
    print("\n=== 按象限 ===")
    for k, v in report["by_quadrant"].items():
        print(f"{k:8s} n={v['n']:2d} net={v['net_total']:+8.3f} exp={v['expectancy']:+.3f}")
    print("\n=== 按通道 ===")
    for k, v in report["by_channel"].items():
        print(f"{k:22s} n={v['n']:2d} net={v['net_total']:+8.3f} exp={v['expectancy']:+.3f}")
    print("\n=== 按方向 ===")
    for k, v in report["by_side"].items():
        print(f"{k:8s} n={v['n']:2d} net={v['net_total']:+8.3f} exp={v['expectancy']:+.3f}")
    print("\n=== 按符号 ===")
    for k, v in report["by_symbol"].items():
        print(f"{k:10s} n={v['n']:2d} net={v['net_total']:+8.3f} exp={v['expectancy']:+.3f}")
    print(f"\n输出 → {OUT/'attribution.json'}")


if __name__ == "__main__":
    main()
