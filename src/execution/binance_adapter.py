from __future__ import annotations

from src.core.models import OrderIntent


class BinanceAdapter:
    def __init__(self, client):
        self.client = client

    def get_klines(self, *args, **kwargs):
        return self.client.get_klines(*args, **kwargs)

    def submit(self, intent: OrderIntent) -> dict:
        raise NotImplementedError("live order submission must be wired explicitly after dry-run validation")

    def cancel(self, symbol: str, order_id: int | str) -> dict:
        return self.client.cancel_order(symbol, int(order_id))

    def sync(self, symbol: str | None = None) -> dict:
        if symbol:
            return {"position": self.client.get_position(symbol)}
        return {"positions": self.client.get_all_positions()}
