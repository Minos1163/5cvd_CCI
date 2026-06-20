from __future__ import annotations

from dataclasses import dataclass, field
from math import sqrt
from statistics import mean, pstdev


@dataclass(frozen=True)
class SimulatedPosition:
    symbol: str
    side: str
    notional: float
    expires_at_ts: int | None = None


@dataclass
class PortfolioState:
    trades_by_day: dict[int, int] = field(default_factory=dict)
    symbol_trades_by_day_map: dict[tuple[str, int], int] = field(default_factory=dict)
    cooldown_until_by_symbol: dict[str, int] = field(default_factory=dict)
    active_symbols: set[str] = field(default_factory=set)
    same_direction_exposure: dict[str, float] = field(default_factory=dict)
    symbol_exposure: dict[str, float] = field(default_factory=dict)
    trade_returns: list[float] = field(default_factory=list)
    simulated_positions: list[SimulatedPosition] = field(default_factory=list)

    @staticmethod
    def day_key(timestamp: int) -> int:
        return timestamp // 86_400

    def record_entry(
        self,
        symbol: str,
        timestamp: int,
        side: str,
        notional: float,
        expires_at_ts: int | None = None,
    ) -> None:
        normalized_symbol = symbol.strip().upper()
        normalized_side = side.strip().upper()
        day = self.day_key(timestamp)
        self.trades_by_day[day] = self.trades_by_day.get(day, 0) + 1
        key = (normalized_symbol, day)
        self.symbol_trades_by_day_map[key] = self.symbol_trades_by_day_map.get(key, 0) + 1
        self.active_symbols.add(normalized_symbol)
        self.symbol_exposure[normalized_symbol] = self.symbol_exposure.get(normalized_symbol, 0.0) + notional
        self.same_direction_exposure[normalized_side] = self.same_direction_exposure.get(normalized_side, 0.0) + notional
        if expires_at_ts is not None:
            self.simulated_positions.append(
                SimulatedPosition(
                    symbol=normalized_symbol,
                    side=normalized_side,
                    notional=max(0.0, float(notional)),
                    expires_at_ts=expires_at_ts,
                )
            )

    def release_position(self, symbol: str, side: str, notional: float) -> None:
        normalized_symbol = symbol.strip().upper()
        normalized_side = side.strip().upper()
        released = max(0.0, float(notional))
        self.symbol_exposure[normalized_symbol] = max(
            0.0,
            self.symbol_exposure.get(normalized_symbol, 0.0) - released,
        )
        if self.symbol_exposure[normalized_symbol] == 0.0:
            self.symbol_exposure.pop(normalized_symbol, None)
            self.active_symbols.discard(normalized_symbol)
        self.same_direction_exposure[normalized_side] = max(
            0.0,
            self.same_direction_exposure.get(normalized_side, 0.0) - released,
        )
        if self.same_direction_exposure[normalized_side] == 0.0:
            self.same_direction_exposure.pop(normalized_side, None)

    def expire_positions(self, timestamp: int) -> None:
        remaining: list[SimulatedPosition] = []
        for position in self.simulated_positions:
            if position.expires_at_ts is not None and position.expires_at_ts <= timestamp:
                self.release_position(position.symbol, position.side, position.notional)
            else:
                remaining.append(position)
        self.simulated_positions = remaining

    def portfolio_trades_today(self, timestamp: int) -> int:
        return self.trades_by_day.get(self.day_key(timestamp), 0)

    def symbol_trades_today(self, symbol: str, timestamp: int) -> int:
        return self.symbol_trades_by_day_map.get((symbol.strip().upper(), self.day_key(timestamp)), 0)

    def start_cooldown(self, symbol: str, until_ts: int) -> None:
        self.cooldown_until_by_symbol[symbol.strip().upper()] = until_ts

    def cooldown_until(self, symbol: str) -> int | None:
        return self.cooldown_until_by_symbol.get(symbol.strip().upper())

    def is_cooldown_active(self, symbol: str, timestamp: int) -> bool:
        until_ts = self.cooldown_until(symbol)
        return until_ts is not None and timestamp < until_ts

    def active_symbol_count(self) -> int:
        return len(self.active_symbols)

    def symbol_exposure_pct(self, symbol: str, equity: float) -> float:
        if equity <= 0:
            return 0.0
        return self.symbol_exposure.get(symbol.strip().upper(), 0.0) / equity

    def same_direction_exposure_pct(self, side: str, equity: float) -> float:
        if equity <= 0:
            return 0.0
        return self.same_direction_exposure.get(side.strip().upper(), 0.0) / equity

    def total_exposure_pct(self, equity: float) -> float:
        if equity <= 0:
            return 0.0
        return sum(self.symbol_exposure.values()) / equity

    def record_trade_return(self, value: float) -> None:
        self.trade_returns.append(value)

    def rolling_sharpe_20(self) -> float | None:
        if len(self.trade_returns) < 20:
            return None
        window = self.trade_returns[-20:]
        deviation = pstdev(window)
        if deviation == 0:
            return None
        return mean(window) / deviation * sqrt(len(window))
