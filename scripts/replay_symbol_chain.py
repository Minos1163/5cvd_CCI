# -*- coding: utf-8 -*-
"""replay_symbol_chain.py — 通用单币离线回放:对指定 symbol 的 15m 序列,
逐周期用系统评分链(entry_chain_features + scoring)算总分,并模拟真实闸门链
(DIRECT minimums: pa>=6/fib>=9/rr>=4 → 降级;PROBE minimums: score>=72/fib>=12/pa>=6),
输出 DIRECT_OPEN/PROBE_OPEN/WATCH/NO_TRADE 分布。

用法: python scripts/replay_symbol_chain.py --symbol ATOMUSDT [--start 2026-08-02 --end 2026-08-05]
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from bisect import bisect_left
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.backtest.engine import BacktestBar  # noqa: E402
from src.signals.entry_chain_config import load_entry_chain_config  # noqa: E402
from src.signals.entry_chain_features import (  # noqa: E402
    atr_pct,
    component_scores,
    direction_from_history,
)
from src.signals.entry_chain_scoring import component_points, dynamic_weights  # noqa: E402

DATA_ROOT = PROJECT_ROOT / "data" / "raw" / "binance_futures" / "latest_30d"
CONFIG_PATH = PROJECT_ROOT / "configs" / "entry_chain.dry_run_fib_pa_v1.json"
BEIJING_OFFSET_S = 8 * 3600


def load_bars(path: Path) -> list[BacktestBar]:
    bars: list[BacktestBar] = []
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            bars.append(
                BacktestBar(
                    symbol=row["symbol"], timestamp=int(row["open_time"]),
                    open=float(row["open"]), high=float(row["high"]),
                    low=float(row["low"]), close=float(row["close"]),
                    volume=float(row["volume"]),
                )
            )
    return bars


def resample(bars: list[BacktestBar], target_ms: int) -> list[BacktestBar]:
    out: list[BacktestBar] = []
    for b in bars:
        aligned = (b.timestamp // target_ms) * target_ms
        if out and out[-1].timestamp == aligned:
            prev = out[-1]
            out[-1] = BacktestBar(
                symbol=prev.symbol, timestamp=prev.timestamp, open=prev.open,
                high=max(prev.high, b.high), low=min(prev.low, b.low),
                close=b.close, volume=prev.volume + b.volume,
            )
        else:
            out.append(
                BacktestBar(
                    symbol=b.symbol, timestamp=aligned, open=b.open,
                    high=b.high, low=b.low, close=b.close, volume=b.volume,
                )
            )
    return out


def bj_str(ts_ms: int) -> str:
    import datetime as dt

    return (dt.datetime.fromtimestamp(ts_ms / 1000, dt.timezone.utc) + dt.timedelta(seconds=BEIJING_OFFSET_S)).strftime("%m-%d %H:%M")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="ATOMUSDT")
    parser.add_argument("--start", default="2026-08-02")
    parser.add_argument("--end", default="2026-08-05")
    parser.add_argument("--config", default=str(CONFIG_PATH))
    args = parser.parse_args()

    cfg = load_entry_chain_config(args.config)
    csv_path = DATA_ROOT / args.symbol / "15m.csv"
    if not csv_path.exists():
        print(json.dumps({"symbol": args.symbol, "error": "no data"}, ensure_ascii=False))
        return 1
    bars15 = load_bars(csv_path)
    bars30 = resample(bars15, 30 * 60 * 1000)
    bars1h = resample(bars15, 60 * 60 * 1000)
    bars4h = resample(bars15, 4 * 60 * 60 * 1000)
    series = {"15m": bars15, "30m": bars30, "1h": bars1h, "4h": bars4h}

    direct_threshold = float(cfg.direct_threshold)
    watch_threshold = float(cfg.watch_threshold)
    long_offset = float(cfg.long_threshold_offset or 0.0)

    import datetime as dt

    start_ts = int((dt.datetime.fromisoformat(args.start + "T00:00:00+08:00")).timestamp() * 1000)
    end_ts = int((dt.datetime.fromisoformat(args.end + "T23:59:00+08:00")).timestamp() * 1000)

    rows: list[dict] = []
    for i, bar in enumerate(bars15):
        t = bar.timestamp
        if t < start_ts or t >= end_ts or i < 120:
            continue
        completed = {
            tf: s[: bisect_left(s, t, key=lambda x: x.timestamp)]
            for tf, s in series.items()
        }
        completed["15m"] = bars15[:i]
        if len(completed["15m"]) < 60 or len(completed["4h"]) < 8:
            continue
        side = direction_from_history(completed["15m"])
        if side == "NONE":
            continue
        atr = atr_pct(completed["15m"])
        scores = component_scores(
            side, completed, atr, use_ema_architecture=False,
            use_fib_pa_architecture=True, ema200_gate_mode="soft",
        )
        weights, _ = dynamic_weights(atr, cfg)
        points = component_points(scores, weights)
        total = round(sum(points.values()), 2)

        th = direct_threshold + (long_offset if side == "LONG" else 0.0)
        # 闸门模拟:DIRECT minimums(pa>=6, fib>=9, rr>=4)→ 降级 PROBE;PROBE minimums(score>=72, fib>=12, pa>=6)
        if total >= th:
            action = "DIRECT_OPEN"
            if points.get("price_action_structure", 0) < 6.0 or points.get("fibonacci_location", 0) < 9.0 or points.get("risk_reward_geometry", 0) < 4.0:
                action = "PROBE_OPEN" if (total >= 72.0 and points.get("fibonacci_location", 0) >= 12.0 and points.get("price_action_structure", 0) >= 6.0) else "NO_TRADE"
        elif total >= watch_threshold + (long_offset if side == "LONG" else 0.0):
            action = "WATCH"
        else:
            action = "NO_TRADE"

        t_ok = points.get("trend_ema_context", 0) >= float(cfg.quadrant_trend_ema_min)
        p_ok = points.get("price_action_structure", 0) >= float(cfg.quadrant_price_action_min)
        c_ok = points.get("flow_cvd_confirmation", 0) >= float(cfg.quadrant_flow_cvd_min)
        cci_ok = points.get("cci_momentum_quality", 0) >= float(cfg.quadrant_cci_min)
        trend_axis, flow_axis = (t_ok and p_ok), (c_ok and cci_ok)
        quadrant = "Q1" if (trend_axis and flow_axis) else "Q2" if trend_axis else "Q3" if flow_axis else "Q4"

        rows.append(
            {
                "bj": bj_str(t), "side": side, "score": total, "quadrant": quadrant,
                "action": action,
                "trend_ema": points.get("trend_ema_context"), "pa": points.get("price_action_structure"),
                "cvd": points.get("flow_cvd_confirmation"), "cci": points.get("cci_momentum_quality"),
                "fib": points.get("fibonacci_location"), "rr": points.get("risk_reward_geometry"),
            }
        )

    opens = [r for r in rows if r["action"] in ("DIRECT_OPEN", "PROBE_OPEN")]
    out = {
        "symbol": args.symbol,
        "window": f"{args.start}~{args.end}",
        "rows": len(rows),
        "by_action": dict(Counter(r["action"] for r in rows)),
        "by_quadrant": dict(Counter(r["quadrant"] for r in rows)),
        "open_samples": sorted(opens, key=lambda r: -r["score"])[:6],
    }
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
