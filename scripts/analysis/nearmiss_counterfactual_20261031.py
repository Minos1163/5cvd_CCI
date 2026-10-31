"""对 2026-10B 的 190 条 near_miss 做反事实评估.

问题:被 gate 拒掉的信号,如果按账本同一套规则执行(同止损、同 TP 三档、同 32 根
最大持仓、同 20bps 往返成本),结果如何?

数据:logs/2026-10B/2026-10-2*/near_misses.jsonl 的 entry_price / stop_pct /
intended_side / kline_timestamp;15m K 线来自 Binance USDT 永续公开接口(经本地代理)。

规则严格对齐 src/observability/paper_trading.py:
  stop = entry*(1 -/+ stop_pct)
  TPi  = entry +/- level_i*risk,  level = (1.2, 2.0, 3.0), fraction = (0.40, 0.35, 0.25)
  TP1 成交后止损移到成本价(近似 _apply_post_tp_stop)
  同一根 K 线内止损优先(保守)
  MAX_HOLD_BARS = 32
  成本 = 20bps of 每段名义(FEE 5 + SLIP 5,进出各一次)
"""
from __future__ import annotations

import json
import os
import subprocess
from collections import defaultdict
from pathlib import Path
from statistics import mean, pstdev

ROOT = Path(__file__).resolve().parents[2]
LOGS = ROOT / "logs" / "2026-10B"
CACHE = ROOT / "reports" / "_klines_cache"
DAYS = ["2026-10-26", "2026-10-27", "2026-10-28", "2026-10-29", "2026-10-30", "2026-10-31"]

FEE_BPS = 5.0
SLIP_BPS = 5.0
COST_RT = (FEE_BPS + SLIP_BPS) * 2 / 1e4  # 20 bps 往返
TP_LEVELS = (1.2, 2.0, 3.0)
TP_FRACTIONS = (0.40, 0.35, 0.25)
MAX_HOLD_BARS = 32


def fetch_klines(symbol: str, start_ms: int) -> list[list]:
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{symbol}_15m.json"
    if path.exists():
        return json.loads(path.read_text())
    url = (
        f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}"
        f"&interval=15m&startTime={start_ms}&limit=1500"
    )
    env = dict(os.environ)
    env["HTTPS_PROXY"] = env["HTTP_PROXY"] = "http://127.0.0.1:12334"
    env["https_proxy"] = env["http_proxy"] = "http://127.0.0.1:12334"
    out = subprocess.run(
        ["curl", "-s", "--max-time", "40", url],
        capture_output=True, text=True, check=True, env=env,
    ).stdout
    data = json.loads(out)
    path.write_text(json.dumps(data))
    return data


def simulate(bars: list[list], entry_ts: int, entry: float, side: str, stop_pct: float) -> tuple[float, str, float, int] | None:
    """返回 (R 倍数, 出场原因, MFE_R, 持仓根数)."""
    risk = entry * stop_pct
    if risk <= 0:
        return None
    sign = 1.0 if side == "LONG" else -1.0
    stop = entry - sign * risk
    tps = [entry + sign * lvl * risk for lvl in TP_LEVELS]
    remaining = 1.0
    realized = 0.0
    consumed = [False, False, False]
    mfe = 0.0
    start = None
    for i, b in enumerate(bars):
        if b[0] // 1000 == entry_ts:
            start = i + 1
            break
    if start is None:
        return None
    for j in range(start, min(len(bars), start + MAX_HOLD_BARS)):
        b = bars[j]
        high, low = float(b[2]), float(b[3])
        best = (high - entry) / risk if side == "LONG" else (entry - low) / risk
        mfe = max(mfe, best)
        hit_stop = low <= stop if side == "LONG" else high >= stop
        if hit_stop:  # 同根 K 线止损优先(保守)
            px = stop
            pnl = (px - entry) / entry if side == "LONG" else (entry - px) / entry
            realized += remaining * (pnl - COST_RT)
            remaining = 0.0
            return realized / stop_pct, "STOP", mfe, j - start + 1
        for k, tp in enumerate(tps):
            if consumed[k]:
                continue
            hit = high >= tp if side == "LONG" else low <= tp
            if not hit:
                continue
            frac = min(remaining, TP_FRACTIONS[k])
            pnl = (tp - entry) / entry if side == "LONG" else (entry - tp) / entry
            realized += frac * (pnl - COST_RT)
            remaining -= frac
            consumed[k] = True
            if k == 0:  # TP1 后止损上移到成本价
                stop = entry
            break
        if remaining <= 1e-9:
            return realized / stop_pct, "TP_FULL", mfe, j - start + 1
    # 超时按最后一根收盘
    b = bars[min(len(bars) - 1, start + MAX_HOLD_BARS - 1)]
    px = float(b[4])
    pnl = (px - entry) / entry if side == "LONG" else (entry - px) / entry
    realized += remaining * (pnl - COST_RT)
    return realized / stop_pct, "TIMEOUT", mfe, MAX_HOLD_BARS


def agg(rows: list[dict]) -> dict:
    rs = [r["R"] for r in rows]
    if not rs:
        return {}
    wins = [x for x in rs if x > 0]
    return dict(
        n=len(rs),
        mean_R=round(mean(rs), 3),
        sum_R=round(sum(rs), 1),
        t=round(mean(rs) / (pstdev(rs) / len(rs) ** 0.5), 2) if len(rs) > 1 and pstdev(rs) > 0 else None,
        win_rate=round(len(wins) / len(rs), 3),
        median_R=round(sorted(rs)[len(rs) // 2], 3),
    )


def main() -> None:
    rows = []
    for d in DAYS:
        p = LOGS / d / "near_misses.jsonl"
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    rows.append(json.loads(line))

    symbols = sorted({r["symbol"] for r in rows})
    start_ms = 1792972800000  # 2026-10-26T00:00Z
    bars = {}
    for s in symbols:
        try:
            bars[s] = fetch_klines(s, start_ms)
        except Exception as exc:  # noqa: BLE001
            print("fetch failed", s, exc)
    print("symbols", len(bars), {k: len(v) for k, v in bars.items()})

    out = []
    for r in rows:
        side = r.get("intended_side")
        stop_pct = (r.get("entry_context") or {}).get("stop_pct")
        entry = r.get("entry_price")
        b = bars.get(r["symbol"])
        if not b or not side or not stop_pct or not entry:
            continue
        res = simulate(b, r["kline_timestamp"], float(entry), side, float(stop_pct))
        if res is None:
            continue
        R, reason, mfe, hold = res
        out.append(dict(symbol=r["symbol"], side=side, quad=r.get("quadrant"), reason_bucket=r.get("primary_reason"),
                        score=r.get("score"), R=R, exit=reason, mfe=mfe, hold=hold, ts=r["kline_timestamp"],
                        scout=r.get("scout_candidate")))

    print("evaluated", len(out), "of", len(rows))
    by_reason: dict[str, list[dict]] = defaultdict(list)
    for o in out:
        by_reason[o["reason_bucket"]].append(o)
    summary = {k: agg(v) for k, v in sorted(by_reason.items(), key=lambda kv: -len(kv[1]))}

    by_side: dict[str, list[dict]] = defaultdict(list)
    for o in out:
        by_side[o["side"]].append(o)
    by_quad: dict[str, list[dict]] = defaultdict(list)
    for o in out:
        by_quad[o["quad"]] .append(o)

    report = dict(
        overall=agg(out),
        by_reason=summary,
        by_side={k: agg(v) for k, v in by_side.items()},
        by_quad={k: agg(v) for k, v in by_quad.items()},
        long_only=[dict(o) for o in out if o["side"] == "LONG" and o["reason_bucket"] == "SIDE_THRESHOLD_OFFSET_LONG_10.00"],
        rows=out,
    )
    (ROOT / "reports" / "2026-10B_nearmiss_counterfactual.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({k: v for k, v in report.items() if k not in ("rows", "long_only")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
