from __future__ import annotations

from dataclasses import dataclass, replace


UNIVERSE_SCOPE = "binance_usdt_perpetual"
MAX_SYMBOLS = 20
MAX_SYMBOLS_HARD_CAP = 30
RECOMMENDED_MIN_24H_VOLUME_USD = 300_000_000
MIN_LISTING_DAYS = 365
MAX_SPREAD_PCT = 0.05
MAX_MISSING_BAR_RATIO = 0.005
UPDATE_FREQUENCY = "weekly"
REQUIRED_TIMEFRAMES = ("15m", "30m", "1h", "4h")
UNIVERSE_STATUSES = ("ACTIVE", "SUSPENDED", "REMOVED")
MEME_POLICY = "exclude_by_default_even_if_large_cap"


TIER_A = {"BTCUSDT", "ETHUSDT"}
TIER_B = {"BNBUSDT", "SOLUSDT", "XRPUSDT"}
DEFAULT_EXCLUDED_MEME = {"DOGEUSDT", "SHIBUSDT", "PEPEUSDT", "FLOKIUSDT"}


@dataclass(frozen=True)
class UniverseCheck:
    passed: bool
    reason: str


@dataclass(frozen=True)
class UniverseCandidate:
    symbol: str
    market_cap_rank: int
    volume_24h: float
    price: float
    listed_days: int
    is_meme: bool = False
    delisting: bool = False
    contract_type: str = "USDT_PERPETUAL"
    quote_asset: str = "USDT"
    volume_rank: int = 0
    spread_pct: float = 0.0
    missing_bar_ratio: float = 0.0
    timeframes: tuple[str, ...] = REQUIRED_TIMEFRAMES
    monitoring_tag: bool = False
    abnormal_wick_count: int = 0

    def with_updates(self, **updates) -> "UniverseCandidate":
        return replace(self, **updates)


@dataclass(frozen=True)
class UniverseMember:
    symbol: str
    market_cap_rank: int
    volume_rank: int
    status: str
    added_time: int
    removed_time: int | None
    version: str
    reason: str


@dataclass(frozen=True)
class UniverseSnapshot:
    version: str
    members: list[UniverseMember]
    created_at: int
    effective_from: int
    effective_to: int | None
    update_reason: str

    def active_symbols(self) -> list[str]:
        return [member.symbol for member in self.members if member.status == "ACTIVE"]


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
        adjusted = candidate.with_updates(symbol=symbol)
        check = validate_candidate(adjusted)
        if not check.passed:
            continue
        if adjusted.market_cap_rank > max_symbols:
            continue
        if adjusted.volume_24h < min_volume_24h:
            continue
        if adjusted.listed_days < min_listed_days:
            continue
        valid.append(adjusted)
    return sorted(valid, key=lambda item: item.market_cap_rank)[:max_symbols]


def validate_candidate(candidate: UniverseCandidate) -> UniverseCheck:
    symbol = normalize_symbol(candidate.symbol)
    if not symbol.endswith("USDT") or candidate.quote_asset != "USDT":
        return UniverseCheck(False, "only USDT symbols are allowed")
    if candidate.contract_type != "USDT_PERPETUAL":
        return UniverseCheck(False, "only USDT perpetual contracts are allowed")
    if candidate.market_cap_rank > MAX_SYMBOLS_HARD_CAP:
        return UniverseCheck(False, "market cap rank outside hard cap")
    if candidate.volume_24h < RECOMMENDED_MIN_24H_VOLUME_USD:
        return UniverseCheck(False, "24h volume below V1 threshold")
    if candidate.listed_days < MIN_LISTING_DAYS:
        return UniverseCheck(False, "listing age below V1 threshold")
    if candidate.spread_pct > MAX_SPREAD_PCT:
        return UniverseCheck(False, "spread too wide")
    if candidate.missing_bar_ratio > MAX_MISSING_BAR_RATIO:
        return UniverseCheck(False, "missing bar ratio too high")
    if set(REQUIRED_TIMEFRAMES) - set(candidate.timeframes):
        return UniverseCheck(False, "missing required timeframe history")
    if candidate.delisting or candidate.monitoring_tag:
        return UniverseCheck(False, "delisting or monitoring risk")
    if candidate.is_meme or symbol in DEFAULT_EXCLUDED_MEME:
        return UniverseCheck(False, MEME_POLICY)
    if candidate.abnormal_wick_count > 0:
        return UniverseCheck(False, "abnormal wick risk")
    return UniverseCheck(True, "candidate approved")


def build_universe_snapshot(version: str, members: list[UniverseMember], created_at: int) -> UniverseSnapshot:
    return UniverseSnapshot(
        version=version,
        members=members,
        created_at=created_at,
        effective_from=created_at,
        effective_to=None,
        update_reason="weekly_refresh",
    )


def validate_snapshot_for_backtest(snapshot: UniverseSnapshot, backtest_start: int) -> UniverseCheck:
    if snapshot.effective_from > backtest_start:
        return UniverseCheck(False, "snapshot starts after backtest period")
    if snapshot.effective_to is not None and snapshot.effective_to < backtest_start:
        return UniverseCheck(False, "snapshot ended before backtest period")
    return UniverseCheck(True, "historical universe snapshot approved")


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
