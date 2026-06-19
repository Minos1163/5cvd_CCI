# AI300 Framework Scaffold Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a minimal, importable Python framework around the existing stable Binance client without changing `src/binance_client.py`.

**Architecture:** The framework is organized as typed boundaries: core DTO/events, data, indicators, context, signals, state machine, risk, execution adapters, backtest, reporting, and utilities. Live execution remains isolated behind adapters, while strategy, risk, and backtest share the same DTOs and event names.

**Tech Stack:** Python standard library first, optional PyYAML for config loading, pytest for verification.

---

## File Structure

- Create: `scripts/scaffold_ai300_framework.py` - idempotent scaffold generator.
- Create: `configs/*.yaml` - default research/backtest/dry-run configuration files.
- Create: `src/core/*.py` - shared events, DTOs, protocols, and constants.
- Create: `src/data/*.py` - candle normalization, resampling, CVD placeholder, universe filter.
- Create: `src/indicators/*.py` - indicator interfaces and minimal pure-Python indicator functions.
- Create: `src/context/*.py` - multi-timeframe context DTO builder.
- Create: `src/signals/*.py` - signal decision boundary.
- Create: `src/state_machine/*.py` - entry state enum and transition helper.
- Create: `src/risk/*.py` - position sizing, stops, portfolio guard, cooldown guard.
- Create: `src/execution/*.py` - order intent routing and Binance adapter boundary.
- Create: `src/backtest/*.py` - fill, fee, slippage, metrics, runner skeleton.
- Create: `src/reporting/*.py` - trade journal and summary helpers.
- Create: `src/utils/*.py` - time, validation, logging helpers.
- Create: `tests/test_framework_scaffold.py` - smoke tests for core behavior.
- Preserve: `src/binance_client.py` - must not be modified.

---

### Task 1: Write Scaffold Script

**Files:**

- Create: `scripts/scaffold_ai300_framework.py`

- [ ] **Step 1: Define a no-overwrite file writer**

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def write_file(path: str, content: str) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        return
    target.write_text(content.strip() + "\n", encoding="utf-8")
```

- [ ] **Step 2: Add a protected path check**

```python
PROTECTED = {ROOT / "src" / "binance_client.py"}

def ensure_not_protected(path: str) -> None:
    target = ROOT / path
    if target in PROTECTED:
        raise RuntimeError("scaffold must not modify src/binance_client.py")
```

- [ ] **Step 3: Add templates and main loop**

```python
FILES = {
    "src/core/events.py": "...",
    "src/core/models.py": "...",
}

def main() -> None:
    for path, content in FILES.items():
        ensure_not_protected(path)
        write_file(path, content)
```

- [ ] **Step 4: Run script**

Run: `python scripts/scaffold_ai300_framework.py`

Expected: missing framework files are created and existing files are skipped.

---

### Task 2: Create Core DTOs and Events

**Files:**

- Create: `src/core/events.py`
- Create: `src/core/models.py`
- Create: `src/core/constants.py`
- Create: `src/core/protocols.py`

- [ ] **Step 1: Define event names**

```python
from enum import Enum

class EventType(str, Enum):
    MARKET_CANDLE_CLOSED = "MARKET_CANDLE_CLOSED"
    SIGNAL_CREATED = "SIGNAL_CREATED"
    RISK_APPROVED = "RISK_APPROVED"
    ORDER_INTENT_CREATED = "ORDER_INTENT_CREATED"
    ORDER_FILLED = "ORDER_FILLED"
```

- [ ] **Step 2: Define candle and signal DTOs**

```python
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

@dataclass(frozen=True)
class Signal:
    symbol: str
    side: str
    signal_type: str
    reason: str
    close_time: int
```

- [ ] **Step 3: Verify imports**

Run: `python -c "from src.core.events import EventType; from src.core.models import Candle, Signal; print(EventType.SIGNAL_CREATED.value)"`

Expected: prints `SIGNAL_CREATED`.

---

### Task 3: Create Strategy and Risk Skeleton

**Files:**

- Create: `src/signals/signal_engine.py`
- Create: `src/state_machine/entry_state_machine.py`
- Create: `src/risk/position_sizer.py`
- Create: `src/risk/stop_engine.py`

- [ ] **Step 1: Signal engine only emits decisions**

```python
def generate_signal(context: dict) -> dict:
    if context.get("permission") == "LONG_ALLOWED" and context.get("trigger") == "LONG":
        return {"signal_type": "DIRECT", "side": "LONG", "reason": "1H and 15m aligned"}
    return {"signal_type": "WAIT", "side": "NONE", "reason": "conditions not aligned"}
```

- [ ] **Step 2: Position sizer preserves probe meaning**

```python
def size_notional(equity: float, risk_pct: float, stop_pct: float, signal_type: str) -> float:
    base = equity * risk_pct / stop_pct
    if signal_type == "PROBE":
        return base * 0.25
    return base
```

- [ ] **Step 3: Verify smoke behavior**

Run: `python -c "from src.risk.position_sizer import size_notional; print(round(size_notional(10000, .01, .02, 'PROBE'), 2))"`

Expected: prints `1250.0`.

---

### Task 4: Create Execution and Backtest Boundaries

**Files:**

- Create: `src/execution/binance_adapter.py`
- Create: `src/execution/order_router.py`
- Create: `src/backtest/fill_model.py`
- Create: `src/backtest/engine.py`

- [ ] **Step 1: Keep Binance adapter thin**

```python
class BinanceAdapter:
    def __init__(self, client):
        self.client = client

    def get_klines(self, *args, **kwargs):
        return self.client.get_klines(*args, **kwargs)
```

- [ ] **Step 2: Backtest fill uses next-bar default**

```python
def next_bar_market_fill(next_open: float, side: str, slippage_bps: float) -> float:
    adjustment = next_open * slippage_bps / 10000
    return next_open + adjustment if side == "BUY" else next_open - adjustment
```

- [ ] **Step 3: Verify no protected file changed**

Run: `git diff -- src/binance_client.py`

Expected: no output.

---

### Task 5: Add Smoke Tests

**Files:**

- Create: `tests/test_framework_scaffold.py`

- [ ] **Step 1: Test probe sizing**

```python
from src.risk.position_sizer import size_notional

def test_probe_is_quarter_direct():
    direct = size_notional(10000, 0.01, 0.02, "DIRECT")
    probe = size_notional(10000, 0.01, 0.02, "PROBE")
    assert probe == direct * 0.25
```

- [ ] **Step 2: Test fill slippage direction**

```python
from src.backtest.fill_model import next_bar_market_fill

def test_buy_slippage_increases_price():
    assert next_bar_market_fill(100.0, "BUY", 10) == 100.1
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/test_framework_scaffold.py -q`

Expected: tests pass.

---

## Verification

Run these commands:

```powershell
python scripts/scaffold_ai300_framework.py
python -m compileall src tests
pytest tests/test_framework_scaffold.py -q
git diff -- src/binance_client.py
```

Expected:

- compile succeeds
- smoke tests pass
- `src/binance_client.py` diff is empty

