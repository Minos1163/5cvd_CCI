from __future__ import annotations

from math import floor
from typing import Protocol

from src.signals.entry_chain_config import EntryChainConfig


LARGE_CAP_SYMBOLS = {"BTCUSDT", "ETHUSDT", "BNBUSDT"}
MAINSTREAM_SYMBOLS = {"SOLUSDT", "ADAUSDT", "LINKUSDT"}
HIGH_BETA_SYMBOLS = {"HYPEUSDT", "LABUSDT", "CCUSDT"}


class EntryGateContext(Protocol):
    symbol: str
    timestamp: int
    side: str
    macro_weekly_drop_pct: float
    wick_anomaly_active: bool
    polluted_until_ts: int | None
    active_symbols: int
    portfolio_trades_today: int
    symbol_trades_today: int
    cooldown_until_ts: int | None
    total_exposure_pct: float
    same_direction_exposure_pct: float
    available_margin: float
    account_equity: float
    normal_volatility_scale: float
    current_volatility_scale: float
    daily_profit_pct: float
    quote_volume_24h: float
    atr_pct: float
    expected_order_size: float


def hard_block_reason(context: EntryGateContext, cfg: EntryChainConfig) -> str | None:
    symbol = context.symbol.strip().upper()
    if symbol in cfg.blacklist_symbols:
        return "SYMBOL_BLACKLISTED"
    if symbol in cfg.watch_only_symbols:
        return "SYMBOL_WATCH_ONLY"
    if context.macro_weekly_drop_pct <= cfg.macro_weekly_drop_block_pct:
        return "MACRO_WEEKLY_RISK"
    if context.wick_anomaly_active:
        return "DATA_WICK_ANOMALY"
    if context.polluted_until_ts is not None and context.timestamp <= context.polluted_until_ts:
        return "DATA_POLLUTION_COOLDOWN"
    if context.active_symbols >= cfg.max_active_symbols:
        return "MAX_ACTIVE_SYMBOLS"
    if context.portfolio_trades_today >= daily_max_trades(context, cfg):
        return "DAILY_TRADE_BUDGET_USED"
    if context.symbol_trades_today >= cfg.max_symbol_trades_per_day:
        return "SYMBOL_DAILY_TRADE_BUDGET_USED"
    if context.cooldown_until_ts is not None and context.timestamp < context.cooldown_until_ts:
        return "SYMBOL_COOLDOWN_ACTIVE"
    if context.total_exposure_pct >= cfg.max_total_exposure_pct:
        return "TOTAL_EXPOSURE_CAP"
    if context.same_direction_exposure_pct >= cfg.max_same_direction_exposure_pct:
        return "SAME_DIRECTION_EXPOSURE_CAP"
    if context.available_margin < context.account_equity * cfg.margin_buffer_pct:
        return "MARGIN_BUFFER_TOO_LOW"
    if context.account_equity <= 0:
        return "ACCOUNT_EQUITY_INVALID"
    if context.side.strip().upper() not in {"LONG", "SHORT"}:
        return "SIDE_NOT_ALLOWED"
    return None


def daily_max_trades(context: EntryGateContext, cfg: EntryChainConfig) -> int:
    normal = max(context.normal_volatility_scale, 1e-9)
    dynamic_limit = max(1, floor(cfg.daily_max_trades_base * (context.current_volatility_scale / normal)))
    if context.daily_profit_pct > 0.03:
        return max(1, dynamic_limit // 2)
    return dynamic_limit


def liquidity_ratio(context: EntryGateContext) -> float:
    volatility_multiplier = max(1.0, context.atr_pct * 100.0)
    base = volatility_multiplier * context.expected_order_size
    if base <= 0:
        return 0.0
    return context.quote_volume_24h / base


def symbol_exposure_cap(symbol: str, cfg: EntryChainConfig) -> float:
    normalized = symbol.strip().upper()
    if normalized in LARGE_CAP_SYMBOLS:
        return cfg.max_large_cap_exposure_pct
    if normalized in MAINSTREAM_SYMBOLS:
        return cfg.max_mainstream_exposure_pct
    if normalized in HIGH_BETA_SYMBOLS:
        return cfg.max_high_beta_exposure_pct
    return cfg.max_mainstream_exposure_pct
