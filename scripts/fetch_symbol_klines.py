# -*- coding: utf-8 -*-
"""fetch_symbol_klines.py — 从 Binance USDT-M 期货公开 API 拉取单币 K 线到
data/raw/binance_futures/latest_30d/<SYMBOL>/<interval>.csv,格式与
download_latest_30d_market_data.py 完全一致(12 列 CSV + 表头)。

用法:
  python scripts/fetch_symbol_klines.py --symbol ATOMUSDT --interval 15m --days 30

仅依赖 requests;公开端点无需鉴权。
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "https://fapi.binance.com/fapi/v1/klines"
INTERVAL_MS = {"15m": 15 * 60 * 1000, "1h": 60 * 60 * 1000, "4h": 4 * 60 * 60 * 1000}
MAX_LIMIT = 1500

HEADERS = {
    "User-Agent": "Mozilla/5.0 (AI300 market-data fetch)",
    "Accept": "application/json",
}


def fetch_klines(symbol: str, interval: str, start_ms: int, end_ms: int) -> list[list]:
    rows: list[list] = []
    cursor = start_ms
    while cursor < end_ms:
        params = {
            "symbol": symbol,
            "interval": interval,
            "startTime": cursor,
            "endTime": end_ms,
            "limit": MAX_LIMIT,
        }
        for attempt in range(3):
            try:
                resp = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=20)
                resp.raise_for_status()
                batch = resp.json()
                break
            except (requests.RequestException, ValueError) as exc:
                if attempt == 2:
                    raise RuntimeError(f"fetch {symbol} {interval} @ {cursor}: {exc}") from exc
                time.sleep(2 * (attempt + 1))
        if not batch:
            break
        rows.extend(batch)
        last_open = batch[-1][0]
        cursor = last_open + INTERVAL_MS.get(interval, 900_000)
        time.sleep(0.15)
    return rows


def write_klines(path: Path, symbol: str, interval: str, rows: list[list]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "symbol", "timeframe", "open_time", "open", "high", "low", "close",
                "volume", "close_time", "quote_volume", "trade_count",
                "taker_buy_base_volume", "taker_buy_quote_volume",
            ]
        )
        for r in rows:
            writer.writerow(
                [symbol, interval, r[0], r[1], r[2], r[3], r[4], r[5], r[6],
                 r[7], r[8], r[9], r[10]]
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="拉取单币 Binance USDT-M K 线")
    parser.add_argument("--symbol", default="ATOMUSDT")
    parser.add_argument("--interval", default="15m")
    parser.add_argument("--days", type=int, default=30)
    args = parser.parse_args()

    now_ms = int(time.time() * 1000)
    start_ms = now_ms - args.days * 24 * 60 * 60 * 1000
    out_dir = PROJECT_ROOT / "data" / "raw" / "binance_futures" / "latest_30d" / args.symbol
    out_path = out_dir / f"{args.interval}.csv"

    rows = fetch_klines(args.symbol, args.interval, start_ms, now_ms)
    if not rows:
        print(f"RESULT: 空数据 {args.symbol} {args.interval}", file=sys.stderr)
        return 1
    write_klines(out_path, args.symbol, args.interval, rows)
    summary = {
        "symbol": args.symbol,
        "interval": args.interval,
        "rows": len(rows),
        "first_open": rows[0][0],
        "last_open": rows[-1][0],
        "file": str(out_path),
    }
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
