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

    def to_dict(self) -> dict:
        """序列化到可落盘的 JSON 结构。

        修复点:cooldown_until_by_symbol 之前只在内存里,进程重启后冷却全部丢失,
        同一标的会在冷却窗口内被重复开仓(见 run_live_dry_run 的 SYMBOL_POST_INITIAL_STOP_COOLDOWN)。
        """
        return {
            "schema_version": 1,
            "trades_by_day": {str(k): int(v) for k, v in self.trades_by_day.items()},
            "symbol_trades_by_day": {
                f"{symbol}|{day}": int(count)
                for (symbol, day), count in self.symbol_trades_by_day_map.items()
            },
            "cooldown_until_by_symbol": {str(k): int(v) for k, v in self.cooldown_until_by_symbol.items()},
            "active_symbols": sorted(self.active_symbols),
            "same_direction_exposure": {str(k): float(v) for k, v in self.same_direction_exposure.items()},
            "symbol_exposure": {str(k): float(v) for k, v in self.symbol_exposure.items()},
            "trade_returns": [float(v) for v in self.trade_returns[-200:]],
            "simulated_positions": [
                {
                    "symbol": p.symbol,
                    "side": p.side,
                    "notional": float(p.notional),
                    "expires_at_ts": p.expires_at_ts,
                }
                for p in self.simulated_positions
            ],
        }

    @classmethod
    def from_dict(cls, payload: dict | None) -> "PortfolioState":
        if not isinstance(payload, dict):
            return cls()
        trades_by_day = {}
        for key, value in (payload.get("trades_by_day") or {}).items():
            try:
                trades_by_day[int(key)] = int(value)
            except (TypeError, ValueError):
                continue
        symbol_trades = {}
        for key, value in (payload.get("symbol_trades_by_day") or {}).items():
            symbol, _, day = str(key).partition("|")
            try:
                symbol_trades[(symbol.strip().upper(), int(day))] = int(value)
            except (TypeError, ValueError):
                continue
        cooldowns = {}
        for key, value in (payload.get("cooldown_until_by_symbol") or {}).items():
            try:
                cooldowns[str(key).strip().upper()] = int(value)
            except (TypeError, ValueError):
                continue
        positions = []
        for item in payload.get("simulated_positions") or ():
            if not isinstance(item, dict):
                continue
            expires = item.get("expires_at_ts")
            positions.append(
                SimulatedPosition(
                    symbol=str(item.get("symbol") or "").strip().upper(),
                    side=str(item.get("side") or "").strip().upper(),
                    notional=float(item.get("notional") or 0.0),
                    expires_at_ts=int(expires) if expires is not None else None,
                )
            )
        return cls(
            trades_by_day=trades_by_day,
            symbol_trades_by_day_map=symbol_trades,
            cooldown_until_by_symbol=cooldowns,
            active_symbols={str(s).strip().upper() for s in (payload.get("active_symbols") or ())},
            same_direction_exposure={
                str(k): float(v) for k, v in (payload.get("same_direction_exposure") or {}).items()
            },
            symbol_exposure={str(k): float(v) for k, v in (payload.get("symbol_exposure") or {}).items()},
            trade_returns=[float(v) for v in (payload.get("trade_returns") or ())],
            simulated_positions=positions,
        )
