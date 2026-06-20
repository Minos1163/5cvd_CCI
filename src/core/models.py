from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Candle:
    symbol: str
    timeframe: str
    open_time: int
    close_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    quote_volume: float = 0.0
    trade_count: int = 0
    taker_buy_volume: float = 0.0


@dataclass(frozen=True)
class IndicatorSnapshot:
    symbol: str
    timeframe: str
    close_time: int
    macd: float | None = None
    macd_signal: float | None = None
    macd_hist: float | None = None
    cci: float | None = None
    rsi: float | None = None
    ema_9: float | None = None
    ema_21: float | None = None
    ema_50: float | None = None
    ema_200: float | None = None
    ema50_slope: float | None = None
    ema9_21_gap: float | None = None
    bars_since_ema50_cross: int | None = None
    bars_since_ema200_cross: int | None = None
    boll_mid: float | None = None
    boll_upper: float | None = None
    boll_lower: float | None = None
    atr: float | None = None
    cvd: float | None = None
    cvd_delta: float | None = None


@dataclass(frozen=True)
class Signal:
    symbol: str
    side: str
    signal_type: str
    reason: str
    close_time: int


@dataclass(frozen=True)
class RiskDecision:
    approved: bool
    reason: str
    symbol: str
    side: str
    quantity: float = 0.0
    notional: float = 0.0
    stop_price: float | None = None


@dataclass(frozen=True)
class OrderIntent:
    symbol: str
    side: str
    position_side: str
    quantity: float
    order_type: str
    correlation_id: str
    price: float | None = None
    reduce_only: bool = False
