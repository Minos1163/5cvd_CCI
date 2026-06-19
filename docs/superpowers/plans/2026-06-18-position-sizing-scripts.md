# Position Sizing Scripts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the scripts required by `docs/06_position_sizing.md` as deterministic position-sizing utilities.

**Architecture:** Extend `src/risk/position_sizer.py` from two helper functions into a small pure sizing module with typed inputs/results and explicit approval reasons. The module calculates standard notional from risk, applies DIRECT/PROBE sizing, checks minimum notional, margin, and total exposure, and never calls Binance or mutates live state.

**Tech Stack:** Python standard library, dataclasses, pytest.

---

## Scope Notes

`docs/06_position_sizing.md` currently ends at the formula `position_notional = risk_amount / stop_pct` and leaves the Markdown code fence open. This plan implements only the rules that are explicit in the available document:

- Standard position is risk-derived: `equity * risk_pct / stop_pct`.
- DIRECT uses 100% of standard notional.
- PROBE uses 25% of standard notional.
- Minimum notional failures reject the trade instead of inflating size.
- Inputs include account equity, available margin, price, leverage, stop distance, ATR, target risk, market tier, open exposure, and portfolio correlation.

This plan does not invent volatility targeting, correlation math, exchange precision rounding, or live order routing.

## File Structure

- Modify: `src/risk/position_sizer.py` - add typed input/result models, multiplier helpers, and `calculate_position_size`.
- Create: `scripts/describe_position_sizing.py` - prints sizing policy and sample DIRECT/PROBE outputs as JSON.
- Create: `tests/test_position_sizing.py` - tests standard formula, DIRECT/PROBE ratio, minimum-notional rejection, invalid inputs, margin rejection, and exposure rejection.
- Create: `tests/test_describe_position_sizing.py` - tests CLI JSON output.
- Modify: `scripts/scaffold_ai300_framework.py` - keep generated framework template aligned with the new position-sizing files and tests.
- Preserve: `src/api/binance_client.py` - do not modify the stable Binance client.

---

### Task 1: Typed Sizing Result and Formula

**Files:**

- Modify: `src/risk/position_sizer.py`
- Create: `tests/test_position_sizing.py`

- [ ] **Step 1: Write failing tests for standard formula and DIRECT/PROBE ratio**

```python
import pytest

from src.risk.position_sizer import (
    PositionSizingInput,
    calculate_position_size,
    size_notional,
)


def test_size_notional_preserves_direct_probe_ratio():
    direct = size_notional(10_000, 0.01, 0.02, "DIRECT")
    probe = size_notional(10_000, 0.01, 0.02, "PROBE")
    assert direct == 5_000
    assert probe == 1_250


def test_calculate_direct_standard_notional_from_risk():
    result = calculate_position_size(
        PositionSizingInput(
            symbol="BTCUSDT",
            signal_type="DIRECT",
            equity=10_000,
            available_margin=5_000,
            price=50_000,
            leverage=5,
            stop_pct=0.02,
            atr=800,
            risk_pct=0.01,
            market_tier="A",
            current_open_exposure=0,
            portfolio_correlation=0.2,
            min_notional=5,
            max_total_exposure_pct=0.75,
        )
    )
    assert result.approved is True
    assert result.standard_notional == 5_000
    assert result.notional == 5_000
    assert result.quantity == pytest.approx(0.1)
    assert result.required_margin == 1_000
    assert result.reason == "approved"


def test_calculate_probe_is_quarter_standard_notional():
    result = calculate_position_size(
        PositionSizingInput(
            symbol="BTCUSDT",
            signal_type="PROBE",
            equity=10_000,
            available_margin=5_000,
            price=50_000,
            leverage=5,
            stop_pct=0.02,
            atr=800,
            risk_pct=0.01,
            market_tier="A",
            current_open_exposure=0,
            portfolio_correlation=0.2,
            min_notional=5,
            max_total_exposure_pct=0.75,
        )
    )
    assert result.approved is True
    assert result.standard_notional == 5_000
    assert result.signal_multiplier == 0.25
    assert result.notional == 1_250
    assert result.quantity == pytest.approx(0.025)
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_position_sizing.py -q`

Expected: FAIL because `PositionSizingInput` and `calculate_position_size` do not exist.

- [ ] **Step 3: Implement typed inputs/results and formula**

```python
from dataclasses import dataclass


SIGNAL_MULTIPLIERS = {"DIRECT": 1.0, "PROBE": 0.25}


@dataclass(frozen=True)
class PositionSizingInput:
    symbol: str
    signal_type: str
    equity: float
    available_margin: float
    price: float
    leverage: float
    stop_pct: float
    atr: float
    risk_pct: float
    market_tier: str
    current_open_exposure: float
    portfolio_correlation: float
    min_notional: float
    max_total_exposure_pct: float


@dataclass(frozen=True)
class PositionSizingResult:
    approved: bool
    reason: str
    symbol: str
    signal_type: str
    standard_notional: float
    notional: float
    quantity: float
    required_margin: float
    risk_amount: float
    signal_multiplier: float
    market_tier: str
    market_tier_multiplier: float


def signal_multiplier(signal_type: str) -> float:
    value = signal_type.strip().upper()
    if value not in SIGNAL_MULTIPLIERS:
        raise ValueError("signal_type must be DIRECT or PROBE")
    return SIGNAL_MULTIPLIERS[value]


def calculate_position_size(request: PositionSizingInput) -> PositionSizingResult:
    _validate_request(request)
    normalized_signal = request.signal_type.strip().upper()
    multiplier = signal_multiplier(normalized_signal)
    risk_amount = request.equity * request.risk_pct
    standard_notional = risk_amount / request.stop_pct
    notional = standard_notional * multiplier
    required_margin = notional / request.leverage
    return PositionSizingResult(
        approved=True,
        reason="approved",
        symbol=request.symbol.strip().upper(),
        signal_type=normalized_signal,
        standard_notional=standard_notional,
        notional=notional,
        quantity=notional / request.price,
        required_margin=required_margin,
        risk_amount=risk_amount,
        signal_multiplier=multiplier,
        market_tier=request.market_tier.strip().upper(),
        market_tier_multiplier=1.0,
    )
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_position_sizing.py -q`

Expected: PASS for formula and ratio tests.

---

### Task 2: Rejection Gates

**Files:**

- Modify: `src/risk/position_sizer.py`
- Modify: `tests/test_position_sizing.py`

- [ ] **Step 1: Add failing tests for validation and rejection behavior**

Append to `tests/test_position_sizing.py`:

```python
def base_request(**overrides):
    values = {
        "symbol": "BTCUSDT",
        "signal_type": "DIRECT",
        "equity": 10_000,
        "available_margin": 5_000,
        "price": 50_000,
        "leverage": 5,
        "stop_pct": 0.02,
        "atr": 800,
        "risk_pct": 0.01,
        "market_tier": "A",
        "current_open_exposure": 0,
        "portfolio_correlation": 0.2,
        "min_notional": 5,
        "max_total_exposure_pct": 0.75,
    }
    values.update(overrides)
    return PositionSizingInput(**values)


def test_probe_below_min_notional_rejects_instead_of_inflating():
    result = calculate_position_size(
        base_request(
            signal_type="PROBE",
            equity=100,
            price=100,
            risk_pct=0.01,
            stop_pct=0.10,
            min_notional=5,
        )
    )
    assert result.approved is False
    assert result.notional == 2.5
    assert result.quantity == 0
    assert "skip instead of inflating" in result.reason


def test_margin_shortfall_rejects_without_resizing():
    result = calculate_position_size(base_request(available_margin=100))
    assert result.approved is False
    assert result.notional == 5_000
    assert result.required_margin == 1_000
    assert "available margin" in result.reason


def test_total_exposure_limit_rejects_without_resizing():
    result = calculate_position_size(
        base_request(current_open_exposure=7_000, max_total_exposure_pct=0.75)
    )
    assert result.approved is False
    assert result.notional == 5_000
    assert "total exposure" in result.reason


def test_invalid_stop_pct_raises():
    with pytest.raises(ValueError, match="stop_pct must be positive"):
        calculate_position_size(base_request(stop_pct=0))
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_position_sizing.py -q`

Expected: FAIL because rejection gates are not implemented.

- [ ] **Step 3: Implement validation and rejection gates**

```python
def _reject(request, reason, standard_notional, notional, required_margin, risk_amount, multiplier):
    return PositionSizingResult(
        approved=False,
        reason=reason,
        symbol=request.symbol.strip().upper(),
        signal_type=request.signal_type.strip().upper(),
        standard_notional=standard_notional,
        notional=notional,
        quantity=0.0,
        required_margin=required_margin,
        risk_amount=risk_amount,
        signal_multiplier=multiplier,
        market_tier=request.market_tier.strip().upper(),
        market_tier_multiplier=1.0,
    )
```

Update `calculate_position_size` to check in this order:

1. Validate positive numeric fields.
2. Reject `notional < min_notional` with `notional below exchange minimum; skip instead of inflating size`.
3. Reject `required_margin > available_margin` with `required margin exceeds available margin`.
4. Reject `(current_open_exposure + notional) / equity > max_total_exposure_pct` with `total exposure limit exceeded`.
5. Approve unchanged notional if all gates pass.

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_position_sizing.py -q`

Expected: PASS.

---

### Task 3: Market Tier Metadata and Describe Script

**Files:**

- Modify: `src/risk/position_sizer.py`
- Create: `scripts/describe_position_sizing.py`
- Create: `tests/test_describe_position_sizing.py`

- [ ] **Step 1: Add failing tests for tier metadata and describe script**

Append to `tests/test_position_sizing.py`:

```python
from src.risk.position_sizer import market_tier_multiplier


def test_market_tier_multiplier_is_metadata_not_probe_inflation():
    assert market_tier_multiplier("A") == 2.0
    assert market_tier_multiplier("B") == 1.0
    assert market_tier_multiplier("C") == 0.75
    result = calculate_position_size(base_request(signal_type="PROBE", market_tier="C"))
    assert result.signal_multiplier == 0.25
    assert result.market_tier_multiplier == 0.75
    assert result.notional == 1_250
```

Create `tests/test_describe_position_sizing.py`:

```python
import json
import subprocess
import sys


def test_describe_position_sizing_outputs_policy_json():
    completed = subprocess.run(
        [sys.executable, "scripts/describe_position_sizing.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["formula"] == "position_notional = risk_amount / stop_pct"
    assert payload["signal_multipliers"]["DIRECT"] == 1.0
    assert payload["signal_multipliers"]["PROBE"] == 0.25
    assert payload["minimum_notional_policy"] == "reject; never inflate"
    assert payload["sample"]["probe"]["notional"] == payload["sample"]["direct"]["notional"] * 0.25
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_position_sizing.py tests/test_describe_position_sizing.py -q`

Expected: FAIL because the script and tier helper are missing.

- [ ] **Step 3: Implement tier helper and describe script**

In `src/risk/position_sizer.py`:

```python
MARKET_TIER_MULTIPLIERS = {"A": 2.0, "B": 1.0, "C": 0.75}


def market_tier_multiplier(market_tier: str) -> float:
    value = market_tier.strip().upper()
    if value not in MARKET_TIER_MULTIPLIERS:
        raise ValueError("market_tier must be A, B, or C")
    return MARKET_TIER_MULTIPLIERS[value]
```

Use the helper in `PositionSizingResult.market_tier_multiplier`. Keep it as metadata for now; do not multiply notional by tier until a later document explicitly defines cap behavior.

Create `scripts/describe_position_sizing.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.risk.position_sizer import PositionSizingInput, calculate_position_size


def _sample(signal_type: str) -> dict:
    result = calculate_position_size(
        PositionSizingInput(
            symbol="BTCUSDT",
            signal_type=signal_type,
            equity=10_000,
            available_margin=5_000,
            price=50_000,
            leverage=5,
            stop_pct=0.02,
            atr=800,
            risk_pct=0.01,
            market_tier="A",
            current_open_exposure=0,
            portfolio_correlation=0.2,
            min_notional=5,
            max_total_exposure_pct=0.75,
        )
    )
    return {"notional": result.notional, "quantity": result.quantity}


def main() -> None:
    payload = {
        "formula": "position_notional = risk_amount / stop_pct",
        "signal_multipliers": {"DIRECT": 1.0, "PROBE": 0.25},
        "minimum_notional_policy": "reject; never inflate",
        "required_inputs": [
            "account equity",
            "available margin",
            "symbol price",
            "leverage",
            "stop distance",
            "ATR",
            "target risk per trade",
            "market tier",
            "current open exposure",
            "current portfolio correlation",
        ],
        "sample": {"direct": _sample("DIRECT"), "probe": _sample("PROBE")},
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_position_sizing.py tests/test_describe_position_sizing.py -q`

Expected: PASS.

---

### Task 4: Scaffold Sync and Verification

**Files:**

- Modify: `scripts/scaffold_ai300_framework.py`

- [ ] **Step 1: Update scaffold templates**

Copy the final contents of these files into the matching string templates in `scripts/scaffold_ai300_framework.py`:

- `src/risk/position_sizer.py`
- `scripts/describe_position_sizing.py`
- `tests/test_position_sizing.py`
- `tests/test_describe_position_sizing.py`
- `tests/test_framework_scaffold.py` if its position-sizing smoke tests need imports adjusted.

- [ ] **Step 2: Run targeted tests**

Run: `pytest tests/test_position_sizing.py tests/test_describe_position_sizing.py tests/test_framework_scaffold.py -q`

Expected: PASS.

- [ ] **Step 3: Run full tests**

Run: `pytest -q`

Expected: PASS.

- [ ] **Step 4: Run compile checks**

Run: `python -m compileall src scripts tests`

Expected: completes successfully.

- [ ] **Step 5: Run describe script manually**

Run: `python scripts/describe_position_sizing.py`

Expected: JSON includes `minimum_notional_policy: reject; never inflate` and sample probe notional equal to one quarter of direct.

- [ ] **Step 6: Verify Binance client untouched**

Run: `git diff -- src/api/binance_client.py`

Expected: no output.

---

## Self-Review

- Spec coverage: covers risk-derived standard position, DIRECT/PROBE sizing, no-trade for below minimum notional, required inputs, and no probe inflation.
- Placeholder scan: no `TBD`, `TODO`, `implement later`, or unspecified test steps.
- Type consistency: `PositionSizingInput`, `PositionSizingResult`, `calculate_position_size`, `signal_multiplier`, and `market_tier_multiplier` are named consistently across tasks.
