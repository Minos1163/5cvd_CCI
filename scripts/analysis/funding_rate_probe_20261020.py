"""资金费成本探针:多头/空头持有 1 年的资金费拖累(8h 结算)。

为什么必须先算这个
------------------
4h/日线的趋势过滤必然长期持仓,而永续的资金费按 8h 结算。多头在牛市里通常
**付**资金费,年化经常是 5–15% 量级 —— 足以把"趋势过滤年化 +11.6%"抹平。
之前 15m 的所有成本口径都只算了 20bps 往返,没算资金费,这是同一类错误的重演。

产出:每个品种的 8h 费率均值/中位/分位,以及"永远做多"与"永远做空"的年化成本。
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
BASE = "https://fapi.binance.com/fapi/v1/fundingRate"
OUT = ROOT / "logs" / "analysis" / "long-history"
START_MS = 1_634_832_000_000  # 2021-10-21


def fetch(symbol: str, *, timeout: float = 30.0) -> list[dict]:
    rows: dict[int, dict] = {}
    cursor = START_MS
    now_ms = int(time.time() * 1000)
    while cursor < now_ms:
        url = f"{BASE}?" + urlencode({"symbol": symbol, "startTime": cursor, "limit": 1000})
        with urlopen(url, timeout=timeout) as response:
            batch = json.loads(response.read().decode())
        if not batch:
            break
        for item in batch:
            rows[int(item["fundingTime"])] = item
        last = int(batch[-1]["fundingTime"])
        if last <= cursor:
            break
        cursor = last + 1
        time.sleep(0.1)
    return [rows[k] for k in sorted(rows)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default="BTCUSDT,SOLUSDT,DOGEUSDT,BNBUSDT")
    ap.add_argument("--date", default="2026-10-20")
    args = ap.parse_args()

    out: dict[str, dict] = {}
    for symbol in [s.strip().upper() for s in args.symbols.split(",") if s.strip()]:
        rows = fetch(symbol)
        if not rows:
            print(f"[skip] {symbol}: no funding rows")
            continue
        rates = [float(r["fundingRate"]) for r in rows]
        mean = statistics.fmean(rates)
        med = statistics.median(rates)
        per_year = 3 * 365  # 8h 结算 → 每年 1,095 次
        out[symbol] = {
            "n": len(rates),
            "first": time.strftime("%Y-%m-%d", time.gmtime(rows[0]["fundingTime"] / 1000)),
            "last": time.strftime("%Y-%m-%d", time.gmtime(rows[-1]["fundingTime"] / 1000)),
            "mean_8h": mean,
            "median_8h": med,
            "p10": statistics.quantiles(rates, n=10)[0],
            "p90": statistics.quantiles(rates, n=10)[-1],
            "share_positive": sum(1 for r in rates if r > 0) / len(rates),
            "annual_long_cost_pct": mean * per_year * 100,
            "annual_short_income_pct": mean * per_year * 100,
        }
        print(f"[{symbol}] n={len(rates)} {out[symbol]['first']}→{out[symbol]['last']} "
              f"mean8h={mean*100:+.4f}% 多头年化成本={mean*per_year*100:+.2f}% "
              f"正费率占比={out[symbol]['share_positive']:.1%}")

    if out:
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / args.date).mkdir(parents=True, exist_ok=True)
        (OUT / args.date / "funding.json").write_text(
            json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        avg = statistics.fmean([v["annual_long_cost_pct"] for v in out.values()])
        print(f"[pooled] 多头年化资金费(等权)={avg:+.2f}%  → 2026-10-20/funding.json")


if __name__ == "__main__":
    main()
