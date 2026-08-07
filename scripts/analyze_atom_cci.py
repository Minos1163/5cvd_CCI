# -*- coding: utf-8 -*-
"""analyze_atom_cci.py — 重建 ATOMUSDT 08-02~08-05 15m 序列,用系统 CCI(period=20)
核对用户描述的关键节点:08-02 04:00(北京)起涨、08-04 00:00(北京)CCI 顶、
08-05 11:00(北京)跌穿 -100。输出全区间 CCI 概览与关键节点前后各 8 根。
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
CSV_PATH = PROJECT_ROOT / "data" / "raw" / "binance_futures" / "latest_30d" / "ATOMUSDT" / "15m.csv"
BEIJING_OFFSET_S = 8 * 3600

from src.indicators.cci import cci  # noqa: E402
from src.core.models import Candle  # noqa: E402


def load_rows(path: Path) -> list[Candle]:
    candles: list[Candle] = []
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            candles.append(
                Candle(
                    symbol=row["symbol"],
                    timeframe=row["timeframe"],
                    open_time=int(row["open_time"]),
                    close_time=int(row["close_time"]),
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row["volume"]),
                    quote_volume=float(row["quote_volume"]),
                    trade_count=int(row["trade_count"]),
                    taker_buy_volume=float(row["taker_buy_base_volume"]),
                )
            )
    return candles


def bj_str(open_time_ms: int) -> str:
    import datetime as dt

    return (dt.datetime.fromtimestamp(open_time_ms / 1000, dt.timezone.utc) + dt.timedelta(seconds=BEIJING_OFFSET_S)).strftime("%m-%d %H:%M")


def main() -> int:
    candles = load_rows(CSV_PATH)
    # CCI 需要 warmup(period=20),逐根滑动计算
    cci_series: list[float | None] = [None] * len(candles)
    for i in range(len(candles)):
        if i + 20 <= len(candles):
            cci_series[i] = cci(candles[i : i + 20])
    # 只保留 08-02 00:00 北京 ~ 08-06 00:00 北京
    start_ms = None
    out = []
    for i, c in enumerate(candles):
        ts_s = c.open_time / 1000 + BEIJING_OFFSET_S
        # 北京 08-02 00:00 ~ 08-06 00:00
        import datetime as dt

        d = dt.datetime.fromtimestamp(ts_s, dt.timezone.utc)
        if dt.datetime(2026, 8, 2, 0, 0, tzinfo=dt.timezone.utc) <= d < dt.datetime(2026, 8, 6, 0, 0, tzinfo=dt.timezone.utc):
            out.append({"open_time": c.open_time, "bj": bj_str(c.open_time), "close": c.close, "cci": cci_series[i]})

    if not out:
        print("RESULT: 窗口内无数据", file=sys.stderr)
        return 1

    # 关键节点:用户描述(北京)
    nodes = {
        "起涨 08-02 04:00": dt.datetime(2026, 8, 2, 4, 0, tzinfo=dt.timezone.utc),
        "CCI 顶 08-04 00:00": dt.datetime(2026, 8, 4, 0, 0, tzinfo=dt.timezone.utc),
        "跌穿 -100 08-05 11:00": dt.datetime(2026, 8, 5, 11, 0, tzinfo=dt.timezone.utc),
    }

    # CCI 峰值与谷值
    valid = [o for o in out if o["cci"] is not None]
    peak = max(valid, key=lambda o: o["cci"])
    trough = min(valid, key=lambda o: o["cci"])

    # 跌穿 -100 的首根
    cross = next((o for o in valid if o["cci"] is not None and o["cci"] < -100), None)

    summary = {
        "window": f"{out[0]['bj']} ~ {out[-1]['bj']}",
        "bars": len(out),
        "cci_peak": {"bj": peak["bj"], "close": peak["close"], "cci": round(peak["cci"], 2)},
        "cci_trough": {"bj": trough["bj"], "close": trough["close"], "cci": round(trough["cci"], 2)},
        "first_cross_below_minus100": (
            {"bj": cross["bj"], "close": cross["close"], "cci": round(cross["cci"], 2)} if cross else None
        ),
        "user_nodes_vs_data": {},
    }
    for name, bj_dt in nodes.items():
        # 找数据中离该时刻最近的 bar
        target_ts = int((bj_dt - dt.timedelta(seconds=BEIJING_OFFSET_S)).timestamp() * 1000)
        nearest = min(out, key=lambda o: abs(o["open_time"] - target_ts))
        summary["user_nodes_vs_data"][name] = {
            "data_nearest": nearest["bj"],
            "close": nearest["close"],
            "cci": round(nearest["cci"], 2) if nearest["cci"] is not None else None,
        }
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    # 峰值附近 8 根明细
    print("\n=== CCI 峰值附近 8 根(北京) ===")
    pi = out.index(peak)
    for o in out[max(0, pi - 8) : pi + 1]:
        print(f"  {o['bj']} close={o['close']} cci={round(o['cci'],2) if o['cci'] is not None else None}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
