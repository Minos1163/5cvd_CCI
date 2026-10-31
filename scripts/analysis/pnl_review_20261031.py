"""2026-10B 六日 paper 账本核算与归因.

只读 logs/2026-10B/2026-10-26..31(主运行实例).
排除:01/(10-26 的重复副本)、02/2026-10-26/regime(独立 regime 实验).
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "logs" / "2026-10B"
DAYS = ["2026-10-26", "2026-10-27", "2026-10-28", "2026-10-29", "2026-10-30", "2026-10-31"]


def utc(ts: int) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%m-%d %H:%M")


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def load_ledger(kind: str) -> list[dict]:
    """kind: main | legacy | trend_capture | scout"""
    ev = []
    for day in DAYS:
        if kind == "main":
            p = ROOT / day / "paper_trades.jsonl"
        elif kind == "scout":
            p = ROOT / day / "scout_micro" / "paper_trades.jsonl"
        else:
            p = ROOT / day / "paper_ab" / kind / "paper_trades.jsonl"
        ev.extend(load_jsonl(p))
    return ev


def positions(events: list[dict]) -> list[dict]:
    """把 OPEN/REDUCE/CLOSE 事件拼成按 position_id 的完整仓位."""
    by_id: dict[str, dict] = {}
    for e in events:
        pid = e.get("position_id") or f"{e.get('symbol')}:{e.get('timestamp')}"
        rec = by_id.setdefault(pid, {"position_id": pid, "symbol": e.get("symbol"), "events": []})
        rec["events"].append(e)
        if e["event"] == "PAPER_OPEN":
            rec.update(
                entry_time=e["timestamp"],
                entry_price=e["entry_price"],
                side=e["side"],
                leverage=e.get("leverage") or 1,
                notional=e.get("notional") or 0.0,
                margin_used=e.get("margin_used") or 0.0,
                score=e.get("score"),
                quadrant=e.get("source_quadrant"),
                channel=e.get("entry_channel"),
                exit_mode=e.get("exit_mode"),
                stop_pct=e.get("stop_pct"),
                reasons=e.get("reasons") or [],
                experiment=e.get("experiment_id"),
            )
    out = []
    for rec in by_id.values():
        closes = [e for e in rec["events"] if e["event"] in ("PAPER_CLOSE", "PAPER_REDUCE")]
        opens = [e for e in rec["events"] if e["event"] == "PAPER_OPEN"]
        if not opens:
            continue
        rec["closed"] = bool(closes) and any(e["event"] == "PAPER_CLOSE" for e in closes)
        rec["net_pnl"] = sum(e.get("net_pnl") or 0.0 for e in closes)
        rec["margin_pnl"] = sum(e.get("margin_pnl") or 0.0 for e in closes)
        rec["gross_pnl"] = sum(e.get("gross_pnl") or 0.0 for e in closes)
        rec["costs"] = sum((e.get("fee") or 0.0) + (e.get("slippage") or 0.0) for e in closes) + sum(
            (e.get("fee") or 0.0) + (e.get("slippage") or 0.0) for e in opens
        )
        rec["mfe_r"] = max([e.get("max_favorable_r_observed") or 0.0 for e in rec["events"]] or [0.0])
        rec["last_reason"] = closes[-1].get("reason") if closes else "OPEN_AT_END"
        rec["last_ts"] = closes[-1]["timestamp"] if closes else None
        rec["hold_bars"] = ((rec["last_ts"] - rec["entry_time"]) // 900) if rec["last_ts"] else None
        rec["entry_fee"] = opens[0].get("fee") or 0.0
        out.append(rec)
    out.sort(key=lambda r: r["entry_time"])
    return out


def equity_series() -> list[dict]:
    rows = []
    for day in DAYS:
        p = ROOT / day / "paper_equity.json"
        if not p.exists():
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        rows.append(
            dict(
                day=day,
                ts=d["timestamp"],
                equity=d["equity"],
                margin_equity=d.get("margin_equity"),
                realized=d.get("realized_notional_pnl"),
                realized_margin=d.get("realized_margin_pnl"),
                peak=d.get("equity_peak"),
                dd=d.get("max_drawdown"),
                open_positions=d.get("open_positions"),
            )
        )
    return rows


def stats(nets: list[float]) -> dict:
    wins = [x for x in nets if x > 0]
    losses = [x for x in nets if x < 0]
    gp = sum(wins)
    gl = abs(sum(losses))
    return dict(
        n=len(nets),
        win_rate=round(len(wins) / len(nets), 4) if nets else 0.0,
        gross_profit=round(gp, 2),
        gross_loss=round(gl, 2),
        net=round(sum(nets), 2),
        avg_win=round(gp / len(wins), 3) if wins else 0.0,
        avg_loss=round(-gl / len(losses), 3) if losses else 0.0,
        pf=round(gp / gl, 3) if gl else None,
        payoff=round((gp / len(wins)) / (gl / len(losses)), 3) if wins and losses else None,
        expectancy=round(sum(nets) / len(nets), 3) if nets else 0.0,
    )


def group(ps: list[dict], key: str) -> dict:
    buckets: dict[str, list[dict]] = defaultdict(list)
    for p in ps:
        buckets[str(p.get(key))].append(p)
    return {k: dict(stats([p["net_pnl"] for p in v]), n_open=sum(1 for p in v if not p["closed"])) for k, v in sorted(buckets.items())}


def main() -> None:
    report: dict = {}
    main_ps = positions(load_ledger("main"))
    legacy_ps = positions(load_ledger("legacy"))
    trend_ps = positions(load_ledger("trend_capture"))
    scout_ps = positions(load_ledger("scout"))

    report["equity"] = equity_series()

    # --- 主账本 ---
    closed_main = [p for p in main_ps if p["closed"]]
    report["main"] = dict(
        n_positions=len(main_ps),
        n_closed=len(closed_main),
        stats=stats([p["net_pnl"] for p in closed_main]),
        total_costs=round(sum(p["costs"] for p in closed_main), 2),
        total_gross=round(sum(p["gross_pnl"] for p in closed_main), 2),
        by_reason=group(closed_main, "last_reason"),
        by_symbol=group(closed_main, "symbol"),
        by_side=group(closed_main, "side"),
        by_quadrant=group(closed_main, "quadrant"),
        by_channel=group(closed_main, "channel"),
        trades=[
            dict(
                symbol=p["symbol"],
                side=p["side"],
                q=p["quadrant"],
                ch=p["channel"],
                score=round(p["score"] or 0, 1),
                lev=p["leverage"],
                entry=utc(p["entry_time"]),
                hold_h=round((p["hold_bars"] or 0) / 4, 1),
                net=round(p["net_pnl"], 2),
                margin=round(p["margin_pnl"], 2),
                mfe_r=round(p["mfe_r"], 2),
                reason=p["last_reason"],
                mode=p["exit_mode"],
            )
            for p in main_ps
        ],
    )

    # --- AB ledger ---
    closed_legacy = [p for p in legacy_ps if p["closed"]]
    closed_trend = [p for p in trend_ps if p["closed"]]
    report["ab"] = dict(
        legacy=dict(
            n_positions=len(legacy_ps),
            n_closed=len(closed_legacy),
            stats=stats([p["net_pnl"] for p in closed_legacy]),
            total_costs=round(sum(p["costs"] for p in closed_legacy), 2),
            total_gross=round(sum(p["gross_pnl"] for p in closed_legacy), 2),
            by_reason=group(closed_legacy, "last_reason"),
            by_symbol=group(closed_legacy, "symbol"),
            by_side=group(closed_legacy, "side"),
            by_quadrant=group(closed_legacy, "quadrant"),
            by_channel=group(closed_legacy, "channel"),
            margin_stats=stats([p["margin_pnl"] for p in closed_legacy]),
        ),
        trend_capture=dict(
            n_positions=len(trend_ps),
            n_closed=len(closed_trend),
            stats=stats([p["net_pnl"] for p in closed_trend]),
            total_costs=round(sum(p["costs"] for p in closed_trend), 2),
            total_gross=round(sum(p["gross_pnl"] for p in closed_trend), 2),
            by_reason=group(closed_trend, "last_reason"),
            margin_stats=stats([p["margin_pnl"] for p in closed_trend]),
        ),
    )
    # 同仓位 A/B 配对差
    pairs = []
    tmap = {p["position_id"]: p for p in trend_ps}
    for p in legacy_ps:
        t = tmap.get(p["position_id"])
        if t:
            pairs.append(dict(pid=p["position_id"], legacy=round(p["net_pnl"], 3), trend=round(t["net_pnl"], 3),
                              diff=round(t["net_pnl"] - p["net_pnl"], 3), mfe=round(p["mfe_r"], 2),
                              l_reason=p["last_reason"], t_reason=t["last_reason"]))
    report["ab"]["pairs"] = pairs
    report["ab"]["paired_summary"] = dict(
        n=len(pairs),
        sum_legacy=round(sum(x["legacy"] for x in pairs), 2),
        sum_trend=round(sum(x["trend"] for x in pairs), 2),
        sum_diff=round(sum(x["diff"] for x in pairs), 2),
        trend_better=sum(1 for x in pairs if x["diff"] > 1e-9),
        legacy_better=sum(1 for x in pairs if x["diff"] < -1e-9),
    )

    # --- MFE 分布:赢家给了多少 R 又还回去 ---
    def mfe_bucket(ps: list[dict]) -> dict:
        buckets = Counter()
        for p in ps:
            r = p["mfe_r"]
            key = ">=2.0R" if r >= 2 else "1.5-2.0R" if r >= 1.5 else "1.0-1.5R" if r >= 1.0 else "0.5-1.0R" if r >= 0.5 else "<0.5R"
            buckets[key] += 1
        return dict(buckets)

    report["mfe_dist"] = dict(main=mfe_bucket(closed_main), legacy=mfe_bucket(closed_legacy), trend=mfe_bucket(closed_trend))

    # 达到 1R 却最终亏损的仓位
    def giveback(ps: list[dict]) -> dict:
        reach1 = [p for p in ps if p["mfe_r"] >= 1.0]
        lost = [p for p in reach1 if p["net_pnl"] < 0]
        return dict(reached_1r=len(reach1), still_lost=len(lost),
                    lost_pnl=round(sum(p["net_pnl"] for p in lost), 2),
                    reasons=dict(Counter(p["last_reason"] for p in lost)))

    report["giveback"] = dict(main=giveback(closed_main), legacy=giveback(closed_legacy), trend=giveback(closed_trend))

    # --- 主账本 vs AB 账本覆盖差异 ---
    main_ids = {p["position_id"] for p in main_ps}
    ab_ids = {p["position_id"] for p in legacy_ps}
    report["coverage"] = dict(main_only=sorted(main_ids - ab_ids), ab_only=len(ab_ids - main_ids), overlap=len(main_ids & ab_ids))

    # --- scout ---
    if scout_ps:
        cs = [p for p in scout_ps if p["closed"]]
        report["scout"] = dict(n_positions=len(scout_ps), n_closed=len(cs), stats=stats([p["net_pnl"] for p in cs]))

    # --- 漏斗 ---
    funnel = {}
    for day in DAYS:
        s = ROOT / day / "summary.json"
        if not s.exists():
            continue
        d = json.loads(s.read_text(encoding="utf-8"))
        funnel[day] = dict(
            decision_counts=d.get("decision_counts"),
            gate_by_layer=d.get("gate_rejections_by_layer"),
            near_miss_count=d.get("near_miss_count"),
            near_miss_by_reason=d.get("near_miss_by_reason"),
        )
    report["funnel"] = funnel

    out = Path(__file__).resolve().parents[2] / "reports" / "2026-10B_pnl_pack.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("written", out)


if __name__ == "__main__":
    main()
