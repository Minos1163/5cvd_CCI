from __future__ import annotations

from src.core.models import Candle


class MarketDataLoader:
    def __init__(self, client=None):
        self.client = client

    def get_klines(self, symbol: str, timeframe: str, limit: int = 500) -> list[Candle]:
        if self.client is None:
            return []
        rows = self.client.get_klines(symbol, timeframe, limit=limit)
        candles: list[Candle] = []
        for row in rows:
            candles.append(
                Candle(
                    symbol=symbol,
                    timeframe=timeframe,
                    open_time=int(row[0]),
                    open=float(row[1]),
                    high=float(row[2]),
                    low=float(row[3]),
                    close=float(row[4]),
                    volume=float(row[5]),
                    close_time=int(row[6]),
                    quote_volume=float(row[7]) if len(row) > 7 else 0.0,
                    trade_count=int(row[8]) if len(row) > 8 else 0,
                    taker_buy_volume=float(row[9]) if len(row) > 9 else 0.0,
                )
            )
        return candles
