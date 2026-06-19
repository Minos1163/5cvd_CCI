# Data Contract Full Scripts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the scripts required by the completed `docs/09_data_contract.md`.

**Architecture:** Extend the existing `src/data/data_contract.py` module from basic OHLCV/CVD checks into a full data-contract catalog with typed dataclasses, required field lists, quality policy, cache/version/storage contracts, and validation helpers. Keep these utilities pure and reusable by backtest/live layers; do not fetch exchange data, place orders, or modify the stable Binance client.

**Tech Stack:** Python standard library, dataclasses, pytest.

---

## Scope Notes

The previous 09 pass implemented the truncated document requirements: base data types, basic candle fields, timeframe roles, UTC alignment, indicator input, and CVD points. The completed `docs/09_data_contract.md` adds full system-wide data contracts:

- Five data layers and expanded data sources.
- Standard `MarketCandle` with quality/source fields and taker-buy base/quote volumes.
- Indicator output contract and per-indicator required fields.
- Strategy context contract.
- Strategy event contract.
- Execution, account snapshot, position snapshot, and universe item contracts.
- Quality flag policy.
- Cache, version, storage contracts.
- Broader forbidden items.

This plan implements the above as dataclasses, constants, and validation helpers. It does not implement persistence, cache stores, live exchange sync, or database schemas.

## File Structure

- Modify: `src/data/data_contract.py` - add completed 09 constants, dataclasses, and validators while preserving existing functions.
- Modify: `scripts/describe_data_contract.py` - expose completed 09 contract fields in JSON output.
- Modify: `tests/test_data_contract.py` - add coverage for completed 09 dataclasses and validators.
- Modify: `tests/test_describe_data_contract.py` - assert completed 09 fields appear in describe output.
- Modify: `scripts/scaffold_ai300_framework.py` - sync templates for modified module, script, and tests.
- Preserve: `src/api/binance_client.py` - do not modify the stable Binance client.

---

### Task 1: Full Market Candle Contract and Quality Policy

**Files:**

- Modify: `src/data/data_contract.py`
- Modify: `tests/test_data_contract.py`

- [ ] **Step 1: Add failing tests for full candle fields, data layers, sources, and quality flags**

Append to `tests/test_data_contract.py`:

```python
from src.data.data_contract import (
    DATA_LAYERS,
    DATA_SOURCES,
    FULL_CANDLE_FIELDS,
    QUALITY_FLAGS,
    MarketCandle,
    validate_market_candle,
    quality_allows_direct_entry,
)


def test_completed_doc_data_layers_and_sources():
    assert DATA_LAYERS == [
        "raw_market_data",
        "normalized_market_data",
        "multi_timeframe_data",
        "indicator_result_data",
        "strategy_context_data",
    ]
    assert DATA_SOURCES == [
        "kline",
        "volume",
        "active_buy_sell",
        "funding_rate",
        "open_interest",
        "universe",
        "execution",
        "account_position_snapshot",
    ]


def test_full_market_candle_fields_match_completed_doc():
    assert FULL_CANDLE_FIELDS == [
        "symbol",
        "timeframe",
        "open_time",
        "close_time",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "quote_volume",
        "trade_count",
        "taker_buy_base_volume",
        "taker_buy_quote_volume",
        "is_closed",
        "source",
        "quality_flag",
    ]


def test_validate_market_candle_requires_closed_quality_true_data():
    market_candle = MarketCandle(
        symbol="BTCUSDT",
        timeframe="15m",
        open_time=0,
        close_time=900,
        open=100,
        high=105,
        low=95,
        close=101,
        volume=10,
        quote_volume=1_000,
        trade_count=20,
        taker_buy_base_volume=6,
        taker_buy_quote_volume=600,
        is_closed=True,
        source="binance",
        quality_flag=True,
    )
    assert validate_market_candle(market_candle).passed is True
    assert quality_allows_direct_entry(market_candle.quality_flag) is True
    assert quality_allows_direct_entry("degraded") is False
    assert quality_allows_direct_entry("stale") is False


def test_validate_market_candle_rejects_unclosed_or_bad_quality_data():
    market_candle = MarketCandle(
        symbol="BTCUSDT",
        timeframe="15m",
        open_time=0,
        close_time=900,
        open=100,
        high=105,
        low=95,
        close=101,
        volume=10,
        quote_volume=1_000,
        trade_count=20,
        taker_buy_base_volume=6,
        taker_buy_quote_volume=600,
        is_closed=False,
        source="binance",
        quality_flag=True,
    )
    result = validate_market_candle(market_candle)
    assert result.passed is False
    assert "closed" in result.reason
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_data_contract.py -q`

Expected: FAIL because completed 09 symbols are missing.

- [ ] **Step 3: Implement market candle contract**

Add to `src/data/data_contract.py`:

```python
DATA_LAYERS = [
    "raw_market_data",
    "normalized_market_data",
    "multi_timeframe_data",
    "indicator_result_data",
    "strategy_context_data",
]
DATA_SOURCES = [
    "kline",
    "volume",
    "active_buy_sell",
    "funding_rate",
    "open_interest",
    "universe",
    "execution",
    "account_position_snapshot",
]
FULL_CANDLE_FIELDS = [
    "symbol",
    "timeframe",
    "open_time",
    "close_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "quote_volume",
    "trade_count",
    "taker_buy_base_volume",
    "taker_buy_quote_volume",
    "is_closed",
    "source",
    "quality_flag",
]
QUALITY_FLAGS = [True, False, "degraded", "stale"]


@dataclass(frozen=True)
class MarketCandle:
    symbol: str
    timeframe: str
    open_time: int
    close_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    quote_volume: float
    trade_count: int
    taker_buy_base_volume: float
    taker_buy_quote_volume: float
    is_closed: bool
    source: str
    quality_flag: bool | str = True


def market_candle_to_candle(market_candle: MarketCandle) -> Candle:
    return Candle(
        symbol=market_candle.symbol,
        timeframe=market_candle.timeframe,
        open_time=market_candle.open_time,
        close_time=market_candle.close_time,
        open=market_candle.open,
        high=market_candle.high,
        low=market_candle.low,
        close=market_candle.close,
        volume=market_candle.volume,
        quote_volume=market_candle.quote_volume,
        trade_count=market_candle.trade_count,
        taker_buy_volume=market_candle.taker_buy_base_volume,
    )


def validate_market_candle(market_candle: MarketCandle) -> ContractCheck:
    if not market_candle.is_closed:
        return ContractCheck("market_candle", False, "market candle must be closed")
    if market_candle.quality_flag not in QUALITY_FLAGS:
        return ContractCheck("market_candle", False, "unsupported quality_flag")
    if not market_candle.source:
        return ContractCheck("market_candle", False, "source must be present")
    return validate_ohlcv_contract(market_candle_to_candle(market_candle))


def quality_allows_direct_entry(quality_flag: bool | str) -> bool:
    return quality_flag is True
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_data_contract.py -q`

Expected: PASS for new market candle tests.

---

### Task 2: Indicator Result and Strategy Context Contracts

**Files:**

- Modify: `src/data/data_contract.py`
- Modify: `tests/test_data_contract.py`

- [ ] **Step 1: Add failing tests for indicator and context contracts**

Append to `tests/test_data_contract.py`:

```python
from src.data.data_contract import (
    INDICATOR_CONTRACT_FIELDS,
    INDICATOR_REQUIRED_OUTPUTS,
    STRATEGY_CONTEXT_FIELDS,
    IndicatorResult,
    StrategyContext,
    validate_indicator_result,
    validate_strategy_context,
)


def test_indicator_contract_fields_and_required_outputs_match_doc():
    assert INDICATOR_CONTRACT_FIELDS == [
        "name",
        "symbol",
        "timeframe",
        "value",
        "signal",
        "trend",
        "strength",
        "timestamp",
        "metadata",
        "quality_flag",
    ]
    assert INDICATOR_REQUIRED_OUTPUTS["MACD"] == ["macd_line", "signal_line", "histogram", "histogram_slope", "cross_state"]
    assert INDICATOR_REQUIRED_OUTPUTS["ATR"] == ["atr", "atr_pct", "volatility_state"]


def test_validate_indicator_result_blocks_false_or_stale_quality():
    result = IndicatorResult(
        name="MACD",
        symbol="BTCUSDT",
        timeframe="15m",
        value={"macd_line": 1, "signal_line": 0, "histogram": 1, "histogram_slope": 0.1, "cross_state": "GOLDEN"},
        signal="LONG",
        trend="UP",
        strength=0.8,
        timestamp=900,
        metadata={},
        quality_flag=True,
    )
    assert validate_indicator_result(result).passed is True
    stale = IndicatorResult(**{**result.__dict__, "quality_flag": "stale"})
    assert validate_indicator_result(stale).passed is False


def test_strategy_context_fields_and_validation_match_doc():
    assert STRATEGY_CONTEXT_FIELDS[0] == "symbol"
    context = StrategyContext(
        symbol="BTCUSDT",
        timestamp=900,
        market_state_4h="BULL",
        trend_state_1h="LONG_ALLOWED",
        confirm_state_30m="CONFIRMED",
        trigger_state_15m="DIRECT",
        indicators_15m={},
        indicators_30m={},
        indicators_1h={},
        indicators_4h={},
        risk_snapshot={},
        position_snapshot={},
        cooldown_state={},
        signal_candidate={},
        quality_flag=True,
    )
    assert validate_strategy_context(context).passed is True
    bad = StrategyContext(**{**context.__dict__, "quality_flag": False})
    assert validate_strategy_context(bad).passed is False
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_data_contract.py -q`

Expected: FAIL because indicator/context contracts are missing.

- [ ] **Step 3: Implement indicator and context contracts**

Add to `src/data/data_contract.py`:

```python
INDICATOR_CONTRACT_FIELDS = ["name", "symbol", "timeframe", "value", "signal", "trend", "strength", "timestamp", "metadata", "quality_flag"]
INDICATOR_REQUIRED_OUTPUTS = {
    "MACD": ["macd_line", "signal_line", "histogram", "histogram_slope", "cross_state"],
    "RSI": ["rsi", "rsi_slope", "overbought_flag", "oversold_flag", "midline_state"],
    "CCI": ["cci", "cci_slope", "extreme_flag", "recovery_flag"],
    "BOLL": ["middle_band", "upper_band", "lower_band", "band_width", "band_expansion_flag", "band_contraction_flag", "price_position"],
    "CVD": ["cvd", "cvd_delta", "cvd_slope", "cvd_divergence_flag", "buy_pressure", "sell_pressure"],
    "ATR": ["atr", "atr_pct", "volatility_state"],
}
STRATEGY_CONTEXT_FIELDS = [
    "symbol",
    "timestamp",
    "market_state_4h",
    "trend_state_1h",
    "confirm_state_30m",
    "trigger_state_15m",
    "indicators_15m",
    "indicators_30m",
    "indicators_1h",
    "indicators_4h",
    "risk_snapshot",
    "position_snapshot",
    "cooldown_state",
    "signal_candidate",
    "quality_flag",
]


@dataclass(frozen=True)
class IndicatorResult:
    name: str
    symbol: str
    timeframe: str
    value: dict
    signal: str
    trend: str
    strength: float
    timestamp: int
    metadata: dict
    quality_flag: bool | str = True


@dataclass(frozen=True)
class StrategyContext:
    symbol: str
    timestamp: int
    market_state_4h: str
    trend_state_1h: str
    confirm_state_30m: str
    trigger_state_15m: str
    indicators_15m: dict
    indicators_30m: dict
    indicators_1h: dict
    indicators_4h: dict
    risk_snapshot: dict
    position_snapshot: dict
    cooldown_state: dict
    signal_candidate: dict
    quality_flag: bool | str = True


def validate_indicator_result(result: IndicatorResult) -> ContractCheck:
    if result.quality_flag in {False, "stale"}:
        return ContractCheck("indicator_result", False, "indicator quality does not allow main-chain use")
    missing = sorted(set(INDICATOR_REQUIRED_OUTPUTS.get(result.name.upper(), [])) - set(result.value))
    if missing:
        return ContractCheck("indicator_result", False, f"missing indicator fields: {missing}")
    return ContractCheck("indicator_result", True, "indicator result approved")


def validate_strategy_context(context: StrategyContext) -> ContractCheck:
    if context.quality_flag in {False, "stale"}:
        return ContractCheck("strategy_context", False, "strategy context quality does not allow direct entry")
    if not context.symbol or context.timestamp <= 0:
        return ContractCheck("strategy_context", False, "symbol and positive timestamp are required")
    return ContractCheck("strategy_context", True, "strategy context approved")
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_data_contract.py -q`

Expected: PASS.

---

### Task 3: Event, Execution, Account, Position, Universe Contracts

**Files:**

- Modify: `src/data/data_contract.py`
- Modify: `tests/test_data_contract.py`

- [ ] **Step 1: Add failing tests for field lists and validation helpers**

Append to `tests/test_data_contract.py`:

```python
from src.data.data_contract import (
    ACCOUNT_SNAPSHOT_FIELDS,
    EXECUTION_FIELDS,
    POSITION_SNAPSHOT_FIELDS,
    STRATEGY_EVENT_FIELDS,
    STRATEGY_EVENT_TYPES,
    UNIVERSE_ITEM_FIELDS,
    validate_required_fields,
)


def test_event_execution_account_position_and_universe_fields_match_doc():
    assert STRATEGY_EVENT_FIELDS == ["event_id", "symbol", "timeframe", "event_type", "state_before", "state_after", "reason", "score", "timestamp", "metadata"]
    assert "DATA_INVALID" in STRATEGY_EVENT_TYPES
    assert EXECUTION_FIELDS[:4] == ["order_id", "client_order_id", "symbol", "side"]
    assert ACCOUNT_SNAPSHOT_FIELDS[:3] == ["account_equity", "available_margin", "used_margin"]
    assert POSITION_SNAPSHOT_FIELDS[:4] == ["symbol", "side", "position_qty", "entry_price"]
    assert UNIVERSE_ITEM_FIELDS[-1] == "correlation_group"


def test_validate_required_fields_reports_missing_fields():
    check = validate_required_fields({"symbol": "BTCUSDT"}, ["symbol", "side"], "execution")
    assert check.passed is False
    assert "side" in check.reason
    ok = validate_required_fields({"symbol": "BTCUSDT", "side": "LONG"}, ["symbol", "side"], "execution")
    assert ok.passed is True
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_data_contract.py -q`

Expected: FAIL because field constants and validation helper are missing.

- [ ] **Step 3: Implement field constants and generic validator**

Add to `src/data/data_contract.py`:

```python
STRATEGY_EVENT_FIELDS = ["event_id", "symbol", "timeframe", "event_type", "state_before", "state_after", "reason", "score", "timestamp", "metadata"]
STRATEGY_EVENT_TYPES = ["SIGNAL_CREATED", "WATCH_ENTERED", "PROBE_ENTERED", "DIRECT_ENTERED", "POSITION_MANAGED", "EXIT_TRIGGERED", "RISK_BLOCKED", "DATA_INVALID"]
EXECUTION_FIELDS = ["order_id", "client_order_id", "symbol", "side", "order_type", "quantity", "price", "reduce_only", "position_side", "status", "filled_qty", "avg_price", "commission", "latency_ms", "reject_reason", "raw_response"]
ACCOUNT_SNAPSHOT_FIELDS = ["account_equity", "available_margin", "used_margin", "unrealized_pnl", "realized_pnl", "max_drawdown", "daily_pnl", "weekly_pnl"]
POSITION_SNAPSHOT_FIELDS = ["symbol", "side", "position_qty", "entry_price", "mark_price", "unrealized_pnl", "leverage", "stop_price", "take_profit_price", "position_age"]
UNIVERSE_ITEM_FIELDS = ["symbol", "base_asset", "quote_asset", "market_cap_rank", "volume_rank", "tier", "tradable", "listed_time", "delisting_flag", "correlation_group"]


def validate_required_fields(payload: dict, required_fields: list[str], name: str) -> ContractCheck:
    missing = sorted(field for field in required_fields if field not in payload)
    if missing:
        return ContractCheck(name, False, f"missing required fields: {missing}")
    return ContractCheck(name, True, f"{name} fields approved")
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_data_contract.py -q`

Expected: PASS.

---

### Task 4: Cache, Version, Storage, Forbidden Contract and Describe Output

**Files:**

- Modify: `src/data/data_contract.py`
- Modify: `scripts/describe_data_contract.py`
- Modify: `tests/test_data_contract.py`
- Modify: `tests/test_describe_data_contract.py`

- [ ] **Step 1: Add failing tests for cache/version/storage/forbidden and describe output**

Append to `tests/test_data_contract.py`:

```python
from src.data.data_contract import CACHE_CONTRACT_FIELDS, DATA_CONTRACT_FORBIDDEN, STORAGE_CONTRACT, VERSION_FIELDS


def test_cache_version_storage_and_forbidden_contracts_match_doc():
    assert CACHE_CONTRACT_FIELDS == ["ttl", "update_frequency", "hit_condition", "no_future_cache"]
    assert VERSION_FIELDS == ["raw_data_version", "aggregation_version", "indicator_version", "strategy_version", "risk_version", "execution_version"]
    assert STORAGE_CONTRACT["hot"] == ["recent_market", "current_position", "current_signal", "current_risk_state"]
    assert "let backtest and live use different field sets" in DATA_CONTRACT_FORBIDDEN
```

Append to `tests/test_describe_data_contract.py`:

```python
def test_describe_data_contract_outputs_completed_09_sections():
    completed = subprocess.run(
        [sys.executable, "scripts/describe_data_contract.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["data_layers"][0] == "raw_market_data"
    assert payload["full_candle_fields"][0] == "symbol"
    assert payload["indicator_required_outputs"]["ATR"] == ["atr", "atr_pct", "volatility_state"]
    assert "DATA_INVALID" in payload["strategy_event_types"]
    assert payload["storage_contract"]["cold"] == ["historical_backtest_data", "long_term_trade_audit", "historical_performance_report"]
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_data_contract.py tests/test_describe_data_contract.py -q`

Expected: FAIL because new constants and describe output are missing.

- [ ] **Step 3: Implement remaining constants**

Add to `src/data/data_contract.py`:

```python
CACHE_CONTRACT_FIELDS = ["ttl", "update_frequency", "hit_condition", "no_future_cache"]
VERSION_FIELDS = ["raw_data_version", "aggregation_version", "indicator_version", "strategy_version", "risk_version", "execution_version"]
STORAGE_CONTRACT = {
    "hot": ["recent_market", "current_position", "current_signal", "current_risk_state"],
    "warm": ["recent_trades", "recent_strategy_events", "recent_execution_logs"],
    "cold": ["historical_backtest_data", "long_term_trade_audit", "historical_performance_report"],
}
DATA_CONTRACT_FORBIDDEN = [
    "mix timezones",
    "reuse same field name with different meaning",
    "let indicators read raw exchange responses",
    "let strategy bypass normalized objects",
    "use presentation data as strategy data",
    "use patch fields in main decisions",
    "let backtest and live use different field sets",
]
```

- [ ] **Step 4: Update describe script**

Modify `scripts/describe_data_contract.py` imports and payload to include:

```python
ACCOUNT_SNAPSHOT_FIELDS,
CACHE_CONTRACT_FIELDS,
DATA_CONTRACT_FORBIDDEN,
DATA_LAYERS,
DATA_SOURCES,
EXECUTION_FIELDS,
FULL_CANDLE_FIELDS,
INDICATOR_CONTRACT_FIELDS,
INDICATOR_REQUIRED_OUTPUTS,
POSITION_SNAPSHOT_FIELDS,
QUALITY_FLAGS,
STORAGE_CONTRACT,
STRATEGY_CONTEXT_FIELDS,
STRATEGY_EVENT_FIELDS,
STRATEGY_EVENT_TYPES,
UNIVERSE_ITEM_FIELDS,
VERSION_FIELDS,
```

Payload additions:

```python
"data_layers": DATA_LAYERS,
"data_sources": DATA_SOURCES,
"full_candle_fields": FULL_CANDLE_FIELDS,
"indicator_contract_fields": INDICATOR_CONTRACT_FIELDS,
"indicator_required_outputs": INDICATOR_REQUIRED_OUTPUTS,
"strategy_context_fields": STRATEGY_CONTEXT_FIELDS,
"strategy_event_fields": STRATEGY_EVENT_FIELDS,
"strategy_event_types": STRATEGY_EVENT_TYPES,
"execution_fields": EXECUTION_FIELDS,
"account_snapshot_fields": ACCOUNT_SNAPSHOT_FIELDS,
"position_snapshot_fields": POSITION_SNAPSHOT_FIELDS,
"universe_item_fields": UNIVERSE_ITEM_FIELDS,
"quality_flags": QUALITY_FLAGS,
"cache_contract_fields": CACHE_CONTRACT_FIELDS,
"version_fields": VERSION_FIELDS,
"storage_contract": STORAGE_CONTRACT,
"forbidden": DATA_CONTRACT_FORBIDDEN,
```

- [ ] **Step 5: Run tests to verify pass**

Run: `pytest tests/test_data_contract.py tests/test_describe_data_contract.py -q`

Expected: PASS.

---

### Task 5: Scaffold Sync and Verification

**Files:**

- Modify: `scripts/scaffold_ai300_framework.py`

- [ ] **Step 1: Update scaffold templates**

Copy final contents of these files into `scripts/scaffold_ai300_framework.py`:

- `src/data/data_contract.py`
- `scripts/describe_data_contract.py`
- `tests/test_data_contract.py`
- `tests/test_describe_data_contract.py`

- [ ] **Step 2: Run targeted tests**

Run: `pytest tests/test_data_contract.py tests/test_describe_data_contract.py tests/test_framework_scaffold.py -q`

Expected: PASS.

- [ ] **Step 3: Run full verification**

Run:

```bash
pytest -q
python -m compileall src scripts tests
python scripts/describe_data_contract.py
git diff -- src/api/binance_client.py
```

Expected: all tests pass, compile succeeds, describe JSON includes completed 09 sections, and Binance diff has no output.

---

## Self-Review

- Spec coverage: covers full 09 data layers, sources, MarketCandle, aggregation, missing/quality semantics, indicator outputs, StrategyContext, strategy events, execution data, account/position snapshots, universe items, quality flags, cache, versions, storage, forbidden items, and existing CVD/timeframe contracts.
- Placeholder scan: no `TBD`, `TODO`, `implement later`, or unspecified test steps.
- Type consistency: `MarketCandle`, `IndicatorResult`, `StrategyContext`, `ContractCheck`, and all field constants are named consistently across tasks.
