from __future__ import annotations

from typing import Protocol

from src.core.models import OrderIntent


class ExecutionAdapter(Protocol):
    def submit(self, intent: OrderIntent) -> dict:
        ...

    def cancel(self, symbol: str, order_id: int | str) -> dict:
        ...

    def sync(self, symbol: str | None = None) -> dict:
        ...
