# Project Overview Philosophy Universe Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the scripts required by `docs/00_project_overview.md`, `docs/01_strategy_philosophy.md`, and `docs/02_market_universe.md` without adding live trading behavior.

**Architecture:** Add small, testable modules for project-level constants, strategy philosophy constraints, and market universe filtering. These modules are pure Python and do not call Binance or place orders; they provide deterministic building blocks for later backtest/live layers.

**Tech Stack:** Python standard library, dataclasses, pytest.

---

## File Structure

- Create: `src/core/project_spec.py` - project objective, allowed timeframes, layer order, success criteria, and banned features from `00_project_overview.md`.
- Create: `src/core/strategy_philosophy.py` - regime mapping, timeframe roles, indicator responsibilities, and philosophy guard checks from `01_strategy_philosophy.md`.
- Modify: `src/data/universe_filter.py` - expand simple symbol cleanup into deterministic market-universe candidate filtering, risk tiering, exposure limits, and correlation tie-breaks from `02_market_universe.md`.
- Create: `scripts/describe_project_rules.py` - prints a JSON summary of project spec, philosophy roles, and default universe rules for manual inspection.
- Create: `tests/test_project_spec.py` - tests project overview constants and guard rules.
- Create: `tests/test_strategy_philosophy.py` - tests regime actions, timeframe roles, indicator responsibilities, and banned design checks.
- Create: `tests/test_market_universe.py` - tests symbol filtering, tier assignment, exposure multipliers, max positions, and BTC/ETH correlation preference.
- Preserve: `src/api/binance_client.py` - do not modify the stable Binance client.

---

### Task 1: Project Overview Contract

**Files:**

- Create: `src/core/project_spec.py`
- Create: `tests/test_project_spec.py`

- [ ] **Step 1: Write failing tests for project spec**

```python
from src.core.project_spec import (
    BANNED_FEATURES,
    CORE_TIMEFRAMES,
    LAYER_ORDER,
    PROJECT_PRIORITY,
    REFERENCE_TIMEFRAMES,
    SUCCESS_CRITERIA,
    validate_feature_allowed,
)


def test_project_priority_matches_docs():
    assert PROJECT_PRIORITY == ("stability", "explainability", "profitability")


def test_timeframes_match_docs():
    assert CORE_TIMEFRAMES == ("15m", "30m", "1h")
    assert REFERENCE_TIMEFRAMES == ("4h",)


def test_banned_watchlist_promotion_is_rejected():
    ok, reason = validate_feature_allowed("watchlist promotion")
    assert ok is False
    assert "Watchlist Promotion" in reason


def test_layer_order_has_risk_before_execution():
    assert LAYER_ORDER.index("risk") < LAYER_ORDER.index("execution")


def test_success_criteria_contains_core_metrics():
    assert SUCCESS_CRITERIA["max_drawdown_lt"] == 0.20
    assert SUCCESS_CRITERIA["profit_factor_gt"] == 1.5
    assert "Watchlist Promotion" in BANNED_FEATURES
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_project_spec.py -q`

Expected: FAIL because `src.core.project_spec` does not exist.

- [ ] **Step 3: Implement project spec**

```python
from __future__ import annotations

PROJECT_PRIORITY = ("stability", "explainability", "profitability")
CORE_TIMEFRAMES = ("15m", "30m", "1h")
REFERENCE_TIMEFRAMES = ("4h",)
TRADING_VENUE = "binance_usdt_perpetual"

BANNED_FEATURES = (
    "black box model",
    "AI direct decision",
    "complex scorer",
    "multi-layer gate nesting",
    "Watchlist Promotion",
)

LAYER_ORDER = (
    "data",
    "indicator",
    "market_context",
    "signal",
    "state_machine",
    "risk",
    "execution",
    "reporting",
)

SUCCESS_CRITERIA = {
    "annual_return_gt": 0.30,
    "max_drawdown_lt": 0.20,
    "profit_factor_gt": 1.5,
    "sharpe_gt": 1.5,
    "win_rate_min": 0.40,
    "win_rate_max": 0.60,
    "reward_risk_gt": 2.0,
}


def validate_feature_allowed(feature_name: str) -> tuple[bool, str]:
    normalized = feature_name.casefold()
    for banned in BANNED_FEATURES:
        if banned.casefold() in normalized or normalized in banned.casefold():
            return False, f"{banned} is banned by project overview"
    return True, "allowed"
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_project_spec.py -q`

Expected: PASS.

---

### Task 2: Strategy Philosophy Guards

**Files:**

- Create: `src/core/strategy_philosophy.py`
- Create: `tests/test_strategy_philosophy.py`

- [ ] **Step 1: Write failing tests for strategy philosophy**

```python
from src.core.strategy_philosophy import (
    INDICATOR_RESPONSIBILITIES,
    REGIME_ACTIONS,
    TIMEFRAME_ROLES,
    validate_decision_chain_depth,
    validate_indicator_role,
)


def test_regime_actions_are_simple():
    assert REGIME_ACTIONS["up"] == "long"
    assert REGIME_ACTIONS["down"] == "short"
    assert REGIME_ACTIONS["range"] == "wait"


def test_timeframe_roles_match_docs():
    assert TIMEFRAME_ROLES["4h"] == "background"
    assert TIMEFRAME_ROLES["1h"] == "trend_confirmation"
    assert TIMEFRAME_ROLES["30m"] == "trend_quality"
    assert TIMEFRAME_ROLES["15m"] == "execution_trigger"


def test_indicator_has_single_responsibility():
    ok, reason = validate_indicator_role("ATR", "direction")
    assert ok is False
    assert "risk_control" in reason


def test_decision_chain_depth_limit():
    assert validate_decision_chain_depth(["trend", "quality", "trigger"])[0] is True
    assert validate_decision_chain_depth(["a", "b", "c", "d"])[0] is False


def test_indicator_responsibility_map():
    assert INDICATOR_RESPONSIBILITIES["MACD"] == "trend"
    assert INDICATOR_RESPONSIBILITIES["ATR"] == "risk_control"
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_strategy_philosophy.py -q`

Expected: FAIL because `src.core.strategy_philosophy` does not exist.

- [ ] **Step 3: Implement philosophy module**

```python
from __future__ import annotations

REGIME_ACTIONS = {
    "up": "long",
    "down": "short",
    "range": "wait",
}

TIMEFRAME_ROLES = {
    "4h": "background",
    "1h": "trend_confirmation",
    "30m": "trend_quality",
    "15m": "execution_trigger",
}

INDICATOR_RESPONSIBILITIES = {
    "MACD": "trend",
    "CCI": "trend_strength",
    "RSI": "pullback_quality",
    "BOLL": "volatility_structure",
    "CVD": "fund_flow",
    "ATR": "risk_control",
}


def validate_indicator_role(indicator: str, requested_role: str) -> tuple[bool, str]:
    key = indicator.upper()
    actual = INDICATOR_RESPONSIBILITIES.get(key)
    if actual is None:
        return False, f"unknown indicator: {indicator}"
    if actual != requested_role:
        return False, f"{key} is responsible for {actual}, not {requested_role}"
    return True, "allowed"


def validate_decision_chain_depth(chain: list[str], max_depth: int = 3) -> tuple[bool, str]:
    if len(chain) > max_depth:
        return False, "decision chain exceeds 3 layers"
    return True, "allowed"
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_strategy_philosophy.py -q`

Expected: PASS.

---

### Task 3: Market Universe Filtering and Tiering

**Files:**

- Modify: `src/data/universe_filter.py`
- Create: `tests/test_market_universe.py`

- [ ] **Step 1: Write failing tests for universe logic**

```python
from src.data.universe_filter import (
    UniverseCandidate,
    choose_by_correlation_preference,
    filter_universe,
    get_risk_tier,
    max_position_multiplier,
)


def test_filter_universe_keeps_valid_usdt_perps_only():
    candidates = [
        UniverseCandidate("BTCUSDT", 1, 2_000_000_000, 500, 365, False, False),
        UniverseCandidate("DOGEUSDT", 9, 500_000_000, 0.25, 365, True, False),
        UniverseCandidate("NEWUSDT", 18, 100_000_000, 10, 10, False, False),
        UniverseCandidate("ETHBTC", 2, 1_000_000_000, 1, 365, False, False),
    ]
    selected = filter_universe(candidates, max_symbols=20, min_volume_24h=50_000_000)
    assert [item.symbol for item in selected] == ["BTCUSDT"]


def test_risk_tiers_and_multipliers():
    assert get_risk_tier("BTCUSDT") == "A"
    assert max_position_multiplier("ETHUSDT") == 2.0
    assert max_position_multiplier("SOLUSDT") == 1.0
    assert max_position_multiplier("LINKUSDT") == 0.75


def test_correlation_preference_prefers_btc_over_eth():
    selected = choose_by_correlation_preference(["ETHUSDT", "BTCUSDT"])
    assert selected == ["BTCUSDT"]
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_market_universe.py -q`

Expected: FAIL because `UniverseCandidate` and tier helpers do not exist.

- [ ] **Step 3: Implement market universe module**

```python
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
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_market_universe.py -q`

Expected: PASS.

---

### Task 4: Inspection CLI

**Files:**

- Create: `scripts/describe_project_rules.py`
- Create: `tests/test_describe_project_rules.py`

- [ ] **Step 1: Write CLI smoke test**

```python
import json
import subprocess
import sys


def test_describe_project_rules_outputs_json():
    result = subprocess.run(
        [sys.executable, "scripts/describe_project_rules.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    assert payload["project"]["priority"][0] == "stability"
    assert payload["philosophy"]["timeframe_roles"]["4h"] == "background"
    assert payload["universe"]["max_simultaneous_positions"] == 5
```

- [ ] **Step 2: Run test to verify failure**

Run: `pytest tests/test_describe_project_rules.py -q`

Expected: FAIL because CLI does not exist.

- [ ] **Step 3: Implement CLI**

```python
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.project_spec import CORE_TIMEFRAMES, PROJECT_PRIORITY, REFERENCE_TIMEFRAMES, SUCCESS_CRITERIA
from src.core.strategy_philosophy import INDICATOR_RESPONSIBILITIES, TIMEFRAME_ROLES


def main() -> None:
    payload = {
        "project": {
            "priority": PROJECT_PRIORITY,
            "core_timeframes": CORE_TIMEFRAMES,
            "reference_timeframes": REFERENCE_TIMEFRAMES,
            "success_criteria": SUCCESS_CRITERIA,
        },
        "philosophy": {
            "timeframe_roles": TIMEFRAME_ROLES,
            "indicator_responsibilities": INDICATOR_RESPONSIBILITIES,
        },
        "universe": {
            "max_symbols": 20,
            "max_simultaneous_positions": 5,
            "recommended_positions": 3,
            "single_symbol_exposure": 0.20,
            "refresh_time_utc": "00:00",
        },
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify pass**

Run: `pytest tests/test_describe_project_rules.py -q`

Expected: PASS.

---

## Verification

Run:

```powershell
pytest tests/test_project_spec.py tests/test_strategy_philosophy.py tests/test_market_universe.py tests/test_describe_project_rules.py -q
pytest tests/test_framework_scaffold.py -q
python -m compileall src scripts tests
python scripts/describe_project_rules.py
git diff -- src/api/binance_client.py
```

Expected:

- all tests pass
- compile succeeds
- CLI prints valid JSON
- `src/api/binance_client.py` diff is empty

