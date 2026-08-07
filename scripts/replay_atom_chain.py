# -*- coding: utf-8 -*-
"""replay_atom_chain.py — 将 ATOMUSDT 纳入扫描,用系统评分链(entry_chain_features +
entry_chain_scoring + run_live_dry_run 象限判定)离线回放 08-02~08-05 每 15m 周期,
输出:方向/总分/四象限组件点/象限/action,定位"该开多却未开"的周期与原因。

用法: python scripts/replay_atom_chain.py
"""
from __future__ import annotations

import csv
import json
import sys
from bisect import bisect_left
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

CSV_PATH = PROJECT_ROOT / "data" / "raw" / "binance_futures" / "latest_30d" / "ATOMUSDT" / "15m.csv"
CONFIG_PATH = PROJECT_ROOT / "configs" / "entry_chain.dry_run_fib_pa_v1.json"
BEIJING_OFFSET_S = 8 * 3600


def load_bars(path: Path) -> list[BacktestBar]:
    bars: list[BacktestBar] = []
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            bars.append(
                BacktestBar(
                    symbol=row["symbol"],
                    timestamp=int(row["open_time"]),
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
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
                symbol=prev.symbol, timestamp=prev.timestamp,
                open=prev.open, high=max(prev.high, b.high),
                low=min(prev.low, b.low), close=b.close,
                volume=prev.volume + b.volume,
            )
        else:
            out.append(
                BacktestBar(
                    symbol=b.symbol, timestamp=aligned,
                    open=b.open, high=b.high, low=b.low, close=b.close, volume=b.volume,
                )
            )
    return out


def bj_str(ts_ms: int) -> str:
    import datetime as dt

    return (dt.datetime.fromtimestamp(ts_ms / 1000, dt.timezone.utc) + dt.timedelta(seconds=BEIJING_OFFSET_S)).strftime("%m-%d %H:%M")


def main() -> int:
    cfg = load_entry_chain_config(str(CONFIG_PATH))
    bars15 = load_bars(CSV_PATH)
    bars30 = resample(bars15, 30 * 60 * 1000)
    bars1h = resample(bars15, 60 * 60 * 1000)
    bars4h = resample(bars15, 4 * 60 * 60 * 1000)
    series = {"15m": bars15, "30m": bars30, "1h": bars1h, "4h": bars4h}

    direct_threshold = float(cfg.direct_threshold)
    watch_threshold = float(cfg.watch_threshold)
    long_offset = float(cfg.long_threshold_offset or 0.0)

    # 回放窗口:08-02 00:00 北京 ~ 08-06 00:00 北京
    import datetime as dt

    start_ts = int((dt.datetime(2026, 8, 2, 0, 0, tzinfo=dt.timezone.utc) - dt.timedelta(seconds=BEIJING_OFFSET_S)).timestamp() * 1000)
    end_ts = int((dt.datetime(2026, 8, 6, 0, 0, tzinfo=dt.timezone.utc) - dt.timedelta(seconds=BEIJING_OFFSET_S)).timestamp() * 1000)

    rows: list[dict] = []
    for i, bar in enumerate(bars15):
        t = bar.timestamp
        if t < start_ts or t >= end_ts:
            continue
        if i < 120:  # 指标 warmup
            continue
        completed = {
            tf: s[: bisect_left(s, t, key=lambda x: x.timestamp)] if hasattr(s, "__getitem__") else [x for x in s if x.timestamp < t]
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
            side, completed, atr,
            use_ema_architecture=False, use_fib_pa_architecture=True,
            ema200_gate_mode="soft",
        )
        weights, _reasons = dynamic_weights(atr, cfg)
        points = component_points(scores, weights)
        total = round(sum(points.values()), 2)

        t_ok = points.get("trend_ema_context", 0.0) >= float(cfg.quadrant_trend_ema_min)
        p_ok = points.get("price_action_structure", 0.0) >= float(cfg.quadrant_price_action_min)
        c_ok = points.get("flow_cvd_confirmation", 0.0) >= float(cfg.quadrant_flow_cvd_min)
        cci_ok = points.get("cci_momentum_quality", 0.0) >= float(cfg.quadrant_cci_min)
        trend_axis = t_ok and p_ok
        flow_axis = c_ok and cci_ok
        if trend_axis and flow_axis:
            quadrant = "Q1"
        elif trend_axis:
            quadrant = "Q2"
        elif flow_axis:
            quadrant = "Q3"
        else:
            quadrant = "Q4"

        th = direct_threshold + (long_offset if side == "LONG" else 0.0)
        if total >= th:
            action = "DIRECT_OPEN"
        elif total >= watch_threshold + (long_offset if side == "LONG" else 0.0):
            action = "WATCH"
        else:
            action = "NO_TRADE"

        rows.append(
            {
                "bj": bj_str(t), "side": side, "score": total, "quadrant": quadrant,
                "action": action,
                "trend_ema": points.get("trend_ema_context"), "pa": points.get("price_action_structure"),
                "cvd": points.get("flow_cvd_confirmation"), "cci": points.get("cci_momentum_quality"),
                "fib": points.get("fibonacci_location"), "rr": points.get("risk_reward_geometry"),
            }
        )

    out = {
        "config": str(CONFIG_PATH),
        "direct_threshold": direct_threshold,
        "long_offset": long_offset,
        "rows": len(rows),
        "by_quadrant": {},
        "by_action": {},
        "samples": rows,
    }
    from collections import Counter

    out["by_quadrant"] = dict(Counter(r["quadrant"] for r in rows))
    out["by_action"] = dict(Counter(r["action"] for r in rows))
    # 高分区间(score>=80)汇总
    high = [r for r in rows if r["score"] >= 80]
    out["score_ge80"] = len(high)
    out["score_ge85"] = len([r for r in rows if r["score"] >= 85])
    # 用户描述的牛市段:08-02 04:00 ~ 08-05 11:00(北京)
    bull_start = "08-02 04:00"
    bull_end = "08-05 11:00"
    bull = [r for r in rows if bull_start <= r["bj"] <= bull_end and r["side"] == "LONG"]
    out["bull_long_window"] = {"start": bull_start, "end": bull_end, "bars": len(bull)}
    out["bull_long_by_quadrant"] = dict(Counter(r["quadrant"] for r in bull))
    out["bull_long_by_action"] = dict(Counter(r["action"] for r in bull))
    out["bull_long_max_score"] = max((r["score"] for r in bull), default=None)
    out["bull_long_best"] = max(bull, key=lambda r: r["score"]) if bull else None

    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
