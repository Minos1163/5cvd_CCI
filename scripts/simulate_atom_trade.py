# -*- coding: utf-8 -*-
"""simulate_atom_trade.py — 模拟"08-02 09:45(北京)LONG 开多 ATOM"按系统出场规则
(paper_trading.py: stop=ATR*1.5 clamp[0.5%,3%]、TP 1.2/2/3R 分批 40/35/25%、
MAX_HOLD_BARS=32、8 根未达 TP 移成本)的盈亏。

用法: python scripts/simulate_atom_trade.py
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.backtest.engine import BacktestBar  # noqa: E402
from src.signals.entry_chain_features import atr_pct  # noqa: E402

CSV_PATH = PROJECT_ROOT / "data" / "raw" / "binance_futures" / "latest_30d" / "ATOMUSDT" / "15m.csv"
ENTRY_BJ = "2026-08-02 09:45"  # 北京,系统最优信号(score=87.3)
BEIJING_OFFSET_S = 8 * 3600
FEE_BPS = 5.0
ATR_STOP_MULT = 1.5
MIN_STOP_PCT = 0.005
MAX_STOP_PCT = 0.03
TP_LEVELS = (1.2, 2.0, 3.0)
TP_FRACTIONS = (0.40, 0.35, 0.25)
MAX_HOLD_BARS = 32


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


def main() -> int:
    import datetime as dt

    bars = load_bars(CSV_PATH)
    entry_ts = int((dt.datetime.fromisoformat(ENTRY_BJ).replace(tzinfo=dt.timezone.utc) - dt.timedelta(seconds=BEIJING_OFFSET_S)).timestamp() * 1000)
    idx = next((i for i, b in enumerate(bars) if b.timestamp >= entry_ts), None)
    if idx is None:
        print("RESULT: 入场时刻不在数据内", file=sys.stderr)
        return 1
    entry_bar = bars[idx]
    entry_price = entry_bar.close
    # 入场时刻的 ATR(用截至入场的 bars)
    atr = atr_pct(bars[: idx + 1])
    stop_pct = max(MIN_STOP_PCT, min(MAX_STOP_PCT, atr * ATR_STOP_MULT))
    risk = entry_price * stop_pct
    tp_prices = [entry_price + risk * r for r in TP_LEVELS]
    stop_price = entry_price - risk
    breakeven_price = entry_price

    position = {"remaining": 1.0, "tp_consumed": False, "realized_pnl": 0.0, "exit_reason": None, "exit_time": None, "exit_price": None, "bars_held": 0}
    result = {"entry": {"bj": ENTRY_BJ, "price": entry_price, "atr_pct": round(atr * 100, 3), "stop_pct": round(stop_pct * 100, 3), "risk": round(risk, 5)}}

    for j in range(idx + 1, min(idx + 1 + MAX_HOLD_BARS + 8, len(bars))):
        bar = bars[j]
        position["bars_held"] += 1
        held = position["bars_held"]
        # 止损
        if bar.low <= stop_price:
            position["realized_pnl"] += position["remaining"] * (stop_price - entry_price) / risk
            position.update(exit_reason="INITIAL_STOP_HIT", exit_time=bar.timestamp, exit_price=stop_price)
            break
        # breakeven:8 根未达 TP1 → 止损移至成本
        if not position["tp_consumed"] and held >= 8:
            position["tp_consumed"] = True  # breakeven 生效(用成本止损)
            # 若继续跌破成本,按成本平
            if bar.low <= breakeven_price:
                position["realized_pnl"] += position["remaining"] * (breakeven_price - entry_price) / risk
                position.update(exit_reason="COST_BREAKEVEN_HIT", exit_time=bar.timestamp, exit_price=breakeven_price)
                break
        # TP 阶梯(逐根判断 high)
        if position["remaining"] > 0 and bar.high >= tp_prices[0]:
            frac = TP_FRACTIONS[0]
            position["realized_pnl"] += frac * (tp_prices[0] - entry_price) / risk
            position["remaining"] -= frac
            position["tp_consumed"] = True
        if position["remaining"] > 0 and bar.high >= tp_prices[1]:
            frac = TP_FRACTIONS[1]
            position["realized_pnl"] += frac * (tp_prices[1] - entry_price) / risk
            position["remaining"] -= frac
        if position["remaining"] > 0 and bar.high >= tp_prices[2]:
            frac = TP_FRACTIONS[2]
            position["realized_pnl"] += frac * (tp_prices[2] - entry_price) / risk
            position["remaining"] -= frac
        if position["remaining"] <= 0:
            position.update(exit_reason="ALL_TP_HIT", exit_time=bar.timestamp, exit_price=tp_prices[2])
            break
        # 移动止损(简化:trailing 1R)
        trail = max(stop_price, bar.close - risk)
        stop_price = max(stop_price, trail)
    else:
        # 到 32 根上限未平:按最后 close 平
        last = bars[min(idx + 1 + MAX_HOLD_BARS, len(bars) - 1)]
        position["realized_pnl"] += position["remaining"] * (last.close - entry_price) / risk
        position.update(exit_reason="MAX_HOLD_EXIT", exit_time=last.timestamp, exit_price=last.close)

    fees = (entry_price + (position["exit_price"] or entry_price)) * FEE_BPS / 10000 * 1.0  # 简化单边费率*2
    pnl_r = position["realized_pnl"] - fees / risk * 0  # 费率在 R 中近似
    pnl_pct = position["realized_pnl"] * risk / entry_price
    result["exit"] = {
        "reason": position["exit_reason"],
        "exit_time": (dt.datetime.fromtimestamp(position["exit_time"] / 1000, dt.timezone.utc) + dt.timedelta(seconds=BEIJING_OFFSET_S)).strftime("%m-%d %H:%M") if position["exit_time"] else None,
        "exit_price": position["exit_price"],
        "bars_held": position["bars_held"],
    }
    result["pnl"] = {"R": round(position["realized_pnl"], 3), "pct": round(pnl_pct * 100, 3)}
    # 参考:持有到 08-05 11:00(用户描述段末)的收益
    ref_ts = int((dt.datetime(2026, 8, 5, 11, 0, tzinfo=dt.timezone.utc) - dt.timedelta(seconds=BEIJING_OFFSET_S)).timestamp() * 1000)
    ref = next((b for b in bars if b.timestamp >= ref_ts), None)
    result["hold_to_0805_1100_pct"] = round((ref.close / entry_price - 1) * 100, 2) if ref else None
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
