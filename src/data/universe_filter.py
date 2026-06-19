from __future__ import annotations

from dataclasses import dataclass


TIER_A = {"BTCUSDT", "ETHUSDT"}
TIER_B = {"BNBUSDT", "SOLUSDT", "XRPUSDT"}
DEFAULT_EXCLUDED_MEME = {"DOGEUSDT", "SHIBUSDT", "PEPEUSDT", "FLOKIUSDT"}


@dataclass(frozen=True)
class UniverseCandidate:
    symbol: str
    market_cap_rank: int
    volume_24h: float
    price: float
    listed_days: int
    is_meme: bool = False
    delisting: bool = False


def normalize_symbol(symbol: str) -> str:
    return symbol.strip().upper()


def filter_symbols(symbols: list[str], max_symbols: int = 20) -> list[str]:
    cleaned = []
    for symbol in symbols:
        value = normalize_symbol(symbol)
        if value.endswith("USDT") and value not in cleaned:
            cleaned.append(value)
    return cleaned[:max_symbols]


def filter_universe(
    candidates: list[UniverseCandidate],
    max_symbols: int = 20,
    min_volume_24h: float = 50_000_000,
    min_listed_days: int = 60,
) -> list[UniverseCandidate]:
    valid = []
    for candidate in candidates:
        symbol = normalize_symbol(candidate.symbol)
        if not symbol.endswith("USDT"):
            continue
        if candidate.market_cap_rank > max_symbols:
            continue
        if candidate.volume_24h < min_volume_24h:
            continue
        if candidate.listed_days < min_listed_days:
            continue
        if candidate.delisting:
            continue
        if candidate.is_meme or symbol in DEFAULT_EXCLUDED_MEME:
            continue
        valid.append(candidate)
    return sorted(valid, key=lambda item: item.market_cap_rank)[:max_symbols]


def get_risk_tier(symbol: str) -> str:
    value = normalize_symbol(symbol)
    if value in TIER_A:
        return "A"
    if value in TIER_B:
        return "B"
    return "C"


def max_position_multiplier(symbol: str) -> float:
    tier = get_risk_tier(symbol)
    if tier == "A":
        return 2.0
    if tier == "B":
        return 1.0
    return 0.75


def choose_by_correlation_preference(symbols: list[str]) -> list[str]:
    normalized = filter_symbols(symbols, max_symbols=len(symbols))
    if "BTCUSDT" in normalized and "ETHUSDT" in normalized:
        normalized = [symbol for symbol in normalized if symbol != "ETHUSDT"]
    return normalized
