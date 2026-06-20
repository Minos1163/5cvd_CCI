from __future__ import annotations

import argparse
import csv
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


COINGECKO_MARKETS_URL = "https://api.coingecko.com/api/v3/coins/markets"
BINANCE_EXCHANGE_INFO_URL = "https://fapi.binance.com/fapi/v1/exchangeInfo"
BINANCE_KLINES_URL = "https://fapi.binance.com/fapi/v1/klines"
DEFAULT_TIMEFRAMES = ("15m", "30m", "1h", "4h")
STABLE_SYMBOLS = {
    "USDT",
    "USDC",
    "USDS",
    "DAI",
    "USD1",
    "USDE",
    "TUSD",
    "FDUSD",
    "PYUSD",
    "BUSD",
    "USDP",
    "FRAX",
}
STABLE_IDS = {
    "tether",
    "usd-coin",
    "usds",
    "dai",
    "usd1-wlfi",
    "ethena-usde",
    "true-usd",
    "first-digital-usd",
    "paypal-usd",
    "binance-usd",
    "paxos-standard",
    "frax",
}
COINGECKO_BASE_OVERRIDES = {
    "binancecoin": "BNB",
    "the-open-network": "TON",
}
TIMEFRAME_MS = {"15m": 900_000, "30m": 1_800_000, "1h": 3_600_000, "4h": 14_400_000}
KLINE_FIELDS = [
    "symbol",
    "timeframe",
    "open_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "close_time",
    "quote_volume",
    "trade_count",
    "taker_buy_base_volume",
    "taker_buy_quote_volume",
]


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    universe = select_universe(session, args.rank_start, args.rank_end)
    end_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    start_ms = end_ms - args.days * 24 * 60 * 60 * 1000

    written: dict[str, dict[str, Any]] = {}
    for item in universe:
        symbol = item["symbol"]
        written[symbol] = {"market_cap_rank": item["market_cap_rank"], "base_asset": item["base_asset"], "files": {}}
        for timeframe in args.timeframes:
            rows = fetch_klines(session, symbol, timeframe, start_ms, end_ms, sleep_seconds=args.sleep_seconds)
            file_path = output_dir / symbol / f"{timeframe}.csv"
            write_klines(file_path, symbol, timeframe, rows)
            written[symbol]["files"][timeframe] = {
                "path": str(file_path),
                "rows": len(rows),
                "first_open_time": rows[0][0] if rows else None,
                "last_open_time": rows[-1][0] if rows else None,
            }

    manifest = {
        "source": "binance_futures_public_klines",
        "universe_source": "coingecko_market_cap_rank",
        "rank_start": args.rank_start,
        "rank_end": args.rank_end,
        "stable_symbols_excluded": sorted(STABLE_SYMBOLS),
        "days": args.days,
        "start_time_ms": start_ms,
        "end_time_ms": end_ms,
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "timeframes": list(args.timeframes),
        "symbols": [item["symbol"] for item in universe],
        "assets": universe,
        "files": written,
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"manifest": str(manifest_path), "symbols": manifest["symbols"]}, ensure_ascii=False, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download latest Binance Futures OHLCV data for market-cap ranks.")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--rank-start", type=int, default=3)
    parser.add_argument("--rank-end", type=int, default=25)
    parser.add_argument("--timeframes", nargs="+", default=list(DEFAULT_TIMEFRAMES), choices=sorted(TIMEFRAME_MS))
    parser.add_argument("--output-dir", default="data/raw/binance_futures/latest_30d")
    parser.add_argument("--sleep-seconds", type=float, default=0.05)
    return parser.parse_args()


def select_universe(session: requests.Session, rank_start: int, rank_end: int) -> list[dict[str, Any]]:
    markets = session.get(
        COINGECKO_MARKETS_URL,
        params={"vs_currency": "usd", "order": "market_cap_desc", "per_page": max(rank_end, 30), "page": 1, "sparkline": "false"},
        timeout=30,
    )
    markets.raise_for_status()
    assets = markets.json()

    exchange_info = session.get(BINANCE_EXCHANGE_INFO_URL, timeout=30)
    exchange_info.raise_for_status()
    tradable = {
        item["baseAsset"].upper(): item["symbol"]
        for item in exchange_info.json()["symbols"]
        if item.get("quoteAsset") == "USDT" and item.get("contractType") == "PERPETUAL" and item.get("status") == "TRADING"
    }

    selected: list[dict[str, Any]] = []
    for asset in assets:
        rank = int(asset.get("market_cap_rank") or 0)
        if rank < rank_start or rank > rank_end:
            continue
        coin_id = str(asset.get("id", ""))
        base = COINGECKO_BASE_OVERRIDES.get(coin_id, str(asset.get("symbol", "")).upper())
        if coin_id in STABLE_IDS or base in STABLE_SYMBOLS:
            continue
        symbol = tradable.get(base)
        if symbol is None:
            continue
        selected.append(
            {
                "market_cap_rank": rank,
                "id": coin_id,
                "name": asset.get("name"),
                "base_asset": base,
                "symbol": symbol,
            }
        )
    selected.sort(key=lambda item: item["market_cap_rank"])
    return selected


def fetch_klines(
    session: requests.Session,
    symbol: str,
    timeframe: str,
    start_ms: int,
    end_ms: int,
    *,
    sleep_seconds: float,
) -> list[list[Any]]:
    interval_ms = TIMEFRAME_MS[timeframe]
    cursor = align_down(start_ms, interval_ms)
    closed_before = end_ms
    rows: list[list[Any]] = []
    while cursor < end_ms:
        response = session.get(
            BINANCE_KLINES_URL,
            params={"symbol": symbol, "interval": timeframe, "startTime": cursor, "endTime": end_ms, "limit": 1500},
            timeout=30,
        )
        response.raise_for_status()
        batch = response.json()
        if not batch:
            break
        for row in batch:
            if int(row[6]) < closed_before:
                rows.append(row)
        next_cursor = int(batch[-1][0]) + interval_ms
        if next_cursor <= cursor:
            break
        cursor = next_cursor
        time.sleep(sleep_seconds)
    deduped = {int(row[0]): row for row in rows}
    return [deduped[key] for key in sorted(deduped)]


def write_klines(path: Path, symbol: str, timeframe: str, rows: list[list[Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=KLINE_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "open_time": int(row[0]),
                    "open": row[1],
                    "high": row[2],
                    "low": row[3],
                    "close": row[4],
                    "volume": row[5],
                    "close_time": int(row[6]),
                    "quote_volume": row[7],
                    "trade_count": int(row[8]),
                    "taker_buy_base_volume": row[9],
                    "taker_buy_quote_volume": row[10],
                }
            )


def align_down(value: int, step: int) -> int:
    return value - (value % step)


if __name__ == "__main__":
    main()
