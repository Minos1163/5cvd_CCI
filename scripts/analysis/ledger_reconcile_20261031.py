"""T1 口径对账:把 2026-10B 的成交事件重建成两个口径,并验证一致性。

背景(2026-10-31 评审 P0-1):
  PAPER_CLOSE / PAPER_REDUCE 事件里的 net_pnl = gross - 出场成本,
  **不含建仓成本**;建仓成本在 PAPER_OPEN 时一次性记入 position.realized_pnl,
  不出现在任何平仓行里。于是:
    分维度表(用 net_pnl 求和) 与 权益变动(用 realized_pnl) 差一个建仓成本。
  本脚本同时给出两套口径,并断言:
    Σ net_pnl_full == 账本 realized_notional_pnl(容差 0.01 USDT)

用法:
  python scripts/analysis/ledger_reconcile_20261031.py
  python scripts/analysis/ledger_reconcile_20261031.py --selftest
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

LOGS = ROOT / "logs" / "2026-10B"
DAYS = ["2026-10-26", "2026-10-27", "2026-10-28", "2026-10-29", "2026-10-30", "2026-10-31"]
EPS = 0.02


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def rebuild(ledger: str) -> list[dict]:
    """把事件流重建成仓位级记录,同时给出 close-only 与 full-cost 两个口径。"""
    if ledger == "main":
        files = [LOGS / d / "paper_trades.jsonl" for d in DAYS]
    else:
        files = [LOGS / d / "paper_ab" / ledger / "paper_trades.jsonl" for d in DAYS]
    events: list[dict] = []
    for f in files:
        events.extend(load_jsonl(f))

    by_id: dict[str, dict] = {}
    for e in events:
        pid = e.get("position_id")
        if not pid:
            continue
        rec = by_id.setdefault(pid, {"events": []})
        rec["events"].append(e)
        if e["event"] == "PAPER_OPEN":
            rec.update(
                symbol=e["symbol"],
                side=e.get("side"),
                quadrant=e.get("source_quadrant"),
                channel=e.get("entry_channel"),
                exit_mode=e.get("exit_mode"),
                leverage=e.get("leverage") or 1,
                notional=e.get("notional") or 0.0,
                stop_pct=e.get("stop_pct") or 0.0,
                score=e.get("score"),
                entry_time=e["timestamp"],
                entry_cost=(e.get("fee") or 0.0) + (e.get("slippage") or 0.0),
                entry_channel_fee=e.get("fee") or 0.0,
            )

    out = []
    for pid, rec in by_id.items():
        if "symbol" not in rec:
            continue
        closes = [e for e in rec["events"] if e["event"] in ("PAPER_CLOSE", "PAPER_REDUCE")]
        closed = any(e["event"] == "PAPER_CLOSE" for e in closes)
        close_net = sum(e.get("net_pnl") or 0.0 for e in closes)
        exit_cost = sum((e.get("fee") or 0.0) + (e.get("slippage") or 0.0) for e in closes)
        gross = sum(e.get("gross_pnl") or 0.0 for e in closes)
        rec.update(
            position_id=pid,
            closed=closed,
            gross=gross,
            exit_cost=exit_cost,
            close_net=close_net,                      # 旧口径:不含建仓成本
            net_full=close_net - rec["entry_cost"],   # 新口径:全成本
            risk_usdt=rec["notional"] * rec["stop_pct"],
            last_reason=closes[-1].get("reason") if closes else "OPEN_AT_END",
            mfe_r=max([e.get("max_favorable_r_observed") or 0.0 for e in rec["events"]] or [0.0]),
        )
        rec["R_close"] = rec["close_net"] / rec["risk_usdt"] if rec["risk_usdt"] else 0.0
        rec["R_full"] = rec["net_full"] / rec["risk_usdt"] if rec["risk_usdt"] else 0.0
        out.append(rec)
    out.sort(key=lambda r: r["entry_time"])
    return out


def stats(rows: list[dict], key: str) -> dict:
    vals = [r[key] for r in rows]
    wins = [v for v in vals if v > 0]
    losses = [v for v in vals if v < 0]
    gp, gl = sum(wins), abs(sum(losses))
    return dict(
        n=len(vals),
        sum=round(sum(vals), 2),
        win_rate=round(len(wins) / len(vals), 4) if vals else 0.0,
        pf=round(gp / gl, 3) if gl else None,
        avg=round(sum(vals) / len(vals), 3) if vals else 0.0,
    )


def by_dim(rows: list[dict], dim: str) -> dict:
    buckets: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        buckets[str(r.get(dim))].append(r)
    return {
        k: dict(close_only=stats(v, "close_net"), full_cost=stats(v, "net_full"), close_only_R=round(
            sum(x["R_close"] for x in v) / len(v), 3), full_R=round(sum(x["R_full"] for x in v) / len(v), 3))
        for k, v in sorted(buckets.items())
    }


def reported_equity(ledger: str) -> dict:
    if ledger == "main":
        p = LOGS / DAYS[-1] / "paper_equity.json"
        d = json.loads(p.read_text(encoding="utf-8"))
        return dict(realized=d.get("realized_notional_pnl"), equity=d.get("equity"))
    p = LOGS / DAYS[-1] / "paper_ab" / ledger / "paper_equity.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    return dict(realized=d.get("realized_notional_pnl"), equity=d.get("equity"))


def selftest() -> None:
    """开仓->平仓一笔,验证 Σnet_pnl_full 等于权益变动,且比 close-only 少一个建仓成本。"""
    from src.observability.paper_trading import PaperTradingLedger

    tmp = Path(tempfile.mkdtemp())
    led = PaperTradingLedger(tmp, initial_equity=10_000.0)
    decision = {
        "action": "PROBE",
        "side": "LONG",
        "leverage": 3,
        "score": 80.0,
        "reasons": ["SELFTEST"],
        "stop_pct": 0.01,
    }
    draft = {
        "approved": True,
        "request": {"quantity": 10.0, "price": 100.0, "position_side": "LONG"},
    }
    k_open = {"open": 100.0, "high": 100.2, "low": 99.9, "close": 100.0, "timestamp": 1_000_000}
    led.on_decision(symbol="TESTUSDT", decision_payload=decision, draft_payload=draft, kline=k_open, timestamp=1_000_000)

    k_exit = {"open": 101.0, "high": 101.5, "low": 100.9, "close": 101.2, "timestamp": 1_000_900}
    for i in range(1, 40):
        ts = 1_000_000 + i * 900
        py = 101.2 if i > 3 else 100.1
        kline = {"open": py, "high": py * 1.001, "low": py * 0.999, "close": py, "timestamp": ts}
        led.on_decision(symbol="TESTUSDT", decision_payload=decision, draft_payload={"approved": False}, kline=kline, timestamp=ts)

    events = [json.loads(l) for l in (tmp / "paper_trades.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    closes = [e for e in events if e["event"] in ("PAPER_CLOSE", "PAPER_REDUCE")]
    opens = [e for e in events if e["event"] == "PAPER_OPEN"]
    assert closes, "未产生平仓事件"
    assert all("net_pnl_full" in e for e in closes), "平仓事件缺 net_pnl_full"
    assert all(e.get("pnl_schema_version") == 2 for e in closes), "缺 pnl_schema_version"
    full = sum(e["net_pnl_full"] for e in closes)
    close_only = sum(e["net_pnl"] for e in closes)
    entry_cost = sum((e.get("fee") or 0.0) + (e.get("slippage") or 0.0) for e in opens)
    realized = led.realized_pnl
    print(f"[selftest] closes={len(closes)} full={full:.4f} close_only={close_only:.4f} "
          f"entry_cost={entry_cost:.4f} realized={realized:.4f}")
    assert abs(full - realized) < 1e-6, f"net_pnl_full 合计({full}) != 权益已实现({realized})"
    assert abs((close_only - entry_cost) - full) < 1e-9, "full != close_only - entry_cost"
    s = led.summary(1_000_000)
    assert s["pnl_schema_version"] == 2
    assert s["margin_pnl_status"] == "deprecated_leverage_double_count"
    print("[selftest] PASS: 三处一致,净额 = close_only - 建仓成本")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        selftest()
        return

    result: dict = {"window": DAYS, "ledgers": {}}
    checks = []
    for ledger in ("main", "legacy", "trend_capture"):
        rows = rebuild(ledger)
        closed = [r for r in rows if r["closed"]]
        rep = reported_equity(ledger)
        total_full = sum(r["net_full"] for r in rows)
        total_close = sum(r["close_net"] for r in rows)
        entry_costs = sum(r["entry_cost"] for r in rows)
        gap = total_full - (rep["realized"] or 0.0)
        checks.append(dict(ledger=ledger, reported=rep["realized"], rebuilt_full=round(total_full, 4),
                           diff=round(gap, 4), ok=abs(gap) < EPS))
        result["ledgers"][ledger] = dict(
            n_positions=len(rows),
            n_closed=len(closed),
            entry_cost_total=round(entry_costs, 2),
            close_only_total=round(total_close, 2),
            full_cost_total=round(total_full, 2),
            reported_realized=rep["realized"],
            reconcile_diff=round(gap, 4),
            closed_stats=dict(close_only=stats(closed, "close_net"), full_cost=stats(closed, "net_full")),
            by_quadrant=by_dim(closed, "quadrant"),
            by_side=by_dim(closed, "side"),
            by_channel=by_dim(closed, "channel") if any(r.get("channel") for r in closed) else {},
            by_reason=by_dim(closed, "last_reason"),
        )

    result["reconcile_checks"] = checks
    out = ROOT / "reports" / "2026-10B_ledger_reconcile.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=== 对账(Σ net_pnl_full vs 账本 realized_notional_pnl) ===")
    for c in checks:
        flag = "OK " if c["ok"] else "FAIL"
        print(f"  {flag} {c['ledger']:14s} 重建={c['rebuilt_full']:9.2f} 账本={c['reported']:9.2f} 差={c['diff']:+.4f}")
    for ledger, d in result["ledgers"].items():
        print(f"\n=== {ledger}: {d['n_positions']} 笔(已平 {d['n_closed']}),建仓成本合计 {d['entry_cost_total']} ===")
        print(f"  close-only 合计 {d['close_only_total']:+.2f} | full-cost 合计 {d['full_cost_total']:+.2f}")
        for dim in ("by_quadrant", "by_side", "by_reason"):
            for k, v in d[dim].items():
                print(f"  {dim[3:12]:12s} {k:24s} n={v['close_only']['n']:2d} "
                      f"close={v['close_only']['sum']:+8.2f} full={v['full_cost']['sum']:+8.2f} "
                      f"R_full={v['full_R']:+.3f}")
    print(f"\nwritten {out}")
    if not all(c["ok"] for c in checks):
        raise SystemExit("对账失败:存在口径差额超过容差")


if __name__ == "__main__":
    main()
