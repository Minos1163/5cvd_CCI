# Multi Timeframe Rules Scripts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the scripts required by `docs/04_multi_timeframe_rules.md` as pure multi-timeframe context and decision utilities.

**Architecture:** Add typed multi-timeframe rule objects in `src/context/multi_tf_rules.py`, keep compatibility in `src/context/multi_tf_context.py`, and keep final signal generation in `src/signals/signal_engine.py`. The layer outputs `DIRECT`, `PROBE`, `WAIT`, or `NO_TRADE`; it does not size positions, submit orders, or modify Binance access code.

**Tech Stack:** Python standard library, dataclasses, pytest.

---

## File Structure

- Create: `src/context/multi_tf_rules.py` - timeframe role constants, per-timeframe evaluators, conflict checks, and final decision combiner.
- Modify: `src/context/multi_tf_context.py` - preserve `build_context` and add typed context builder from snapshots.
- Modify: `src/signals/signal_engine.py` - accept the typed context output while keeping the existing dict behavior compatible.
- Create: `scripts/describe_multi_tf_rules.py` - prints 04 multi-timeframe roles and decision outputs as JSON.
- Create: `tests/test_multi_tf_rules.py` - tests 4H reference behavior, 1H permission, 30m quality, 15m trigger, direct/probe/wait/no-trade outcomes.
- Create: `tests/test_describe_multi_tf_rules.py` - tests CLI JSON output.
- Preserve: `src/api/binance_client.py` - do not modify the stable Binance client.

---

### Task 1: Timeframe Evaluators

**Files:**

- Create: `src/context/multi_tf_rules.py`
- Create: `tests/test_multi_tf_rules.py`

- [ ] **Step 1: Write failing tests for per-timeframe outputs**

```python
from src.context.multi_tf_rules import (
    TimeframeDecision,
    evaluate_15m_trigger,
    evaluate_1h_permission,
    evaluate_30m_quality,
    evaluate_4h_context,
)
from src.core.models import IndicatorSnapshot


def snap(timeframe: str, **kwargs) -> IndicatorSnapshot:
    return IndicatorSnapshot(symbol="BTCUSDT", timeframe=timeframe, close_time=1, **kwargs)


def test_4h_is_reference_context_only():
    assert evaluate_4h_context(snap("4h", macd=1, cci=120, cvd_delta=10)).value == "BULL"
    assert evaluate_4h_context(snap("4h", macd=-1, cci=-120, cvd_delta=-10)).value == "BEAR"
    assert evaluate_4h_context(snap("4h", macd=0, cci=0, cvd_delta=0)).value == "NEUTRAL"


def test_1h_permission_uses_macd_cci_cvd():
    assert evaluate_1h_permission(snap("1h", macd=1, cci=120, cvd_delta=5)).value == "LONG_ALLOWED"
    assert evaluate_1h_permission(snap("1h", macd=-1, cci=-120, cvd_delta=-5)).value == "SHORT_ALLOWED"
    assert evaluate_1h_permission(snap("1h", macd=1, cci=-120, cvd_delta=5)).value == "NO_TRADE"


def test_30m_quality_uses_cci():
    assert evaluate_30m_quality(snap("30m", cci=120)).value == "LONG_CONFIRM"
    assert evaluate_30m_quality(snap("30m", cci=-120)).value == "SHORT_CONFIRM"
    assert evaluate_30m_quality(snap("30m", cci=0)).value == "WEAK"


def test_15m_trigger_uses_rsi_reclaim_and_cvd():
    assert evaluate_15m_trigger(snap("15m", rsi=55, cvd_delta=5), previous_rsi=45).value == "LONG_TRIGGER"
    assert evaluate_15m_trigger(snap("15m", rsi=45, cvd_delta=-5), previous_rsi=55).value == "SHORT_TRIGGER"
    assert evaluate_15m_trigger(snap("15m", rsi=50, cvd_delta=0), previous_rsi=50).value == "WAIT"
```

- [ ] **Step 2: Run test to verify failure**

Run: `pytest tests/test_multi_tf_rules.py -q`

Expected: FAIL because `src.context.multi_tf_rules` does not exist.

- [ ] **Step 3: Implement per-timeframe evaluators**

```python
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from src.core.models import IndicatorSnapshot


class TimeframeDecision(str, Enum):
    BULL = "BULL"
    BEAR = "BEAR"
    NEUTRAL = "NEUTRAL"
    LONG_ALLOWED = "LONG_ALLOWED"
    SHORT_ALLOWED = "SHORT_ALLOWED"
    NO_TRADE = "NO_TRADE"
    LONG_CONFIRM = "LONG_CONFIRM"
    SHORT_CONFIRM = "SHORT_CONFIRM"
    WEAK = "WEAK"
    LONG_TRIGGER = "LONG_TRIGGER"
    SHORT_TRIGGER = "SHORT_TRIGGER"
    WAIT = "WAIT"


def evaluate_4h_context(snapshot: IndicatorSnapshot) -> TimeframeDecision:
    if (snapshot.macd or 0) > 0 and (snapshot.cci or 0) > 100 and (snapshot.cvd_delta or 0) >= 0:
        return TimeframeDecision.BULL
    if (snapshot.macd or 0) < 0 and (snapshot.cci or 0) < -100 and (snapshot.cvd_delta or 0) <= 0:
        return TimeframeDecision.BEAR
    return TimeframeDecision.NEUTRAL


def evaluate_1h_permission(snapshot: IndicatorSnapshot) -> TimeframeDecision:
    if (snapshot.macd or 0) > 0 and (snapshot.cci or 0) > 100 and (snapshot.cvd_delta or 0) > 0:
        return TimeframeDecision.LONG_ALLOWED
    if (snapshot.macd or 0) < 0 and (snapshot.cci or 0) < -100 and (snapshot.cvd_delta or 0) < 0:
        return TimeframeDecision.SHORT_ALLOWED
    return TimeframeDecision.NO_TRADE


def evaluate_30m_quality(snapshot: IndicatorSnapshot) -> TimeframeDecision:
    if (snapshot.cci or 0) > 100:
        return TimeframeDecision.LONG_CONFIRM
    if (snapshot.cci or 0) < -100:
        return TimeframeDecision.SHORT_CONFIRM
    return TimeframeDecision.WEAK


def evaluate_15m_trigger(snapshot: IndicatorSnapshot, previous_rsi: float | None = None) -> TimeframeDecision:
    rsi = snapshot.rsi
    cvd_delta = snapshot.cvd_delta or 0
    if rsi is None or previous_rsi is None:
        return TimeframeDecision.WAIT
    if previous_rsi <= 50 < rsi and cvd_delta > 0:
        return TimeframeDecision.LONG_TRIGGER
    if previous_rsi >= 50 > rsi and cvd_delta < 0:
        return TimeframeDecision.SHORT_TRIGGER
    return TimeframeDecision.WAIT
```

- [ ] **Step 4: Run tests to verify evaluator pass**

Run: `pytest tests/test_multi_tf_rules.py -q`

Expected: PASS for evaluator tests; remaining combiner tests will be added in Task 2.

---

### Task 2: Context Builder and Decision Combiner

**Files:**

- Modify: `src/context/multi_tf_rules.py`
- Modify: `src/context/multi_tf_context.py`
- Modify: `tests/test_multi_tf_rules.py`

- [ ] **Step 1: Add failing tests for direct/probe/wait/no-trade**

```python
from src.context.multi_tf_rules import build_multi_tf_decision


def test_direct_long_requires_all_confirmations():
    decision = build_multi_tf_decision(
        tf_4h=snap("4h", macd=-1, cci=-120, cvd_delta=-10),
        tf_1h=snap("1h", macd=1, cci=120, cvd_delta=5),
        tf_30m=snap("30m", cci=130),
        tf_15m=snap("15m", rsi=55, cvd_delta=5),
        previous_15m_rsi=45,
    )
    assert decision.signal_type == "DIRECT"
    assert decision.side == "LONG"
    assert decision.context_4h == "BEAR"


def test_probe_when_15m_trigger_is_missing_but_higher_tfs_confirm():
    decision = build_multi_tf_decision(
        tf_4h=snap("4h", macd=0, cci=0, cvd_delta=0),
        tf_1h=snap("1h", macd=1, cci=120, cvd_delta=5),
        tf_30m=snap("30m", cci=130),
        tf_15m=snap("15m", rsi=52, cvd_delta=1),
        previous_15m_rsi=52,
    )
    assert decision.signal_type == "PROBE"
    assert decision.side == "LONG"


def test_no_trade_on_direction_conflict():
    decision = build_multi_tf_decision(
        tf_4h=snap("4h", macd=1, cci=120, cvd_delta=5),
        tf_1h=snap("1h", macd=1, cci=120, cvd_delta=5),
        tf_30m=snap("30m", cci=-130),
        tf_15m=snap("15m", rsi=55, cvd_delta=5),
        previous_15m_rsi=45,
    )
    assert decision.signal_type == "NO_TRADE"
    assert "direction conflict" in decision.reason
```

- [ ] **Step 2: Implement decision dataclass and combiner**

```python
@dataclass(frozen=True)
class MultiTimeframeDecision:
    symbol: str
    signal_type: str
    side: str
    context_4h: str
    permission_1h: str
    quality_30m: str
    trigger_15m: str
    reason: str


def build_multi_tf_decision(
    tf_4h: IndicatorSnapshot,
    tf_1h: IndicatorSnapshot,
    tf_30m: IndicatorSnapshot,
    tf_15m: IndicatorSnapshot,
    previous_15m_rsi: float | None = None,
) -> MultiTimeframeDecision:
    context = evaluate_4h_context(tf_4h)
    permission = evaluate_1h_permission(tf_1h)
    quality = evaluate_30m_quality(tf_30m)
    trigger = evaluate_15m_trigger(tf_15m, previous_rsi=previous_15m_rsi)

    if permission == TimeframeDecision.LONG_ALLOWED:
        if quality == TimeframeDecision.SHORT_CONFIRM:
            return _decision(tf_15m.symbol, "NO_TRADE", "NONE", context, permission, quality, trigger, "direction conflict")
        if quality == TimeframeDecision.LONG_CONFIRM and trigger == TimeframeDecision.LONG_TRIGGER:
            return _decision(tf_15m.symbol, "DIRECT", "LONG", context, permission, quality, trigger, "long direct confirmed")
        if quality == TimeframeDecision.LONG_CONFIRM:
            return _decision(tf_15m.symbol, "PROBE", "LONG", context, permission, quality, trigger, "long higher timeframes confirmed")
        return _decision(tf_15m.symbol, "WAIT", "NONE", context, permission, quality, trigger, "waiting for 30m/15m confirmation")

    if permission == TimeframeDecision.SHORT_ALLOWED:
        if quality == TimeframeDecision.LONG_CONFIRM:
            return _decision(tf_15m.symbol, "NO_TRADE", "NONE", context, permission, quality, trigger, "direction conflict")
        if quality == TimeframeDecision.SHORT_CONFIRM and trigger == TimeframeDecision.SHORT_TRIGGER:
            return _decision(tf_15m.symbol, "DIRECT", "SHORT", context, permission, quality, trigger, "short direct confirmed")
        if quality == TimeframeDecision.SHORT_CONFIRM:
            return _decision(tf_15m.symbol, "PROBE", "SHORT", context, permission, quality, trigger, "short higher timeframes confirmed")
        return _decision(tf_15m.symbol, "WAIT", "NONE", context, permission, quality, trigger, "waiting for 30m/15m confirmation")

    return _decision(tf_15m.symbol, "NO_TRADE", "NONE", context, permission, quality, trigger, "1h direction not allowed")
```

- [ ] **Step 3: Add typed context adapter**

```python
from src.context.multi_tf_rules import MultiTimeframeDecision, build_multi_tf_decision
from src.core.models import IndicatorSnapshot


def build_context_from_snapshots(
    tf_4h: IndicatorSnapshot,
    tf_1h: IndicatorSnapshot,
    tf_30m: IndicatorSnapshot,
    tf_15m: IndicatorSnapshot,
    previous_15m_rsi: float | None = None,
) -> MultiTimeframeDecision:
    return build_multi_tf_decision(tf_4h, tf_1h, tf_30m, tf_15m, previous_15m_rsi)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_multi_tf_rules.py -q`

Expected: PASS.

---

### Task 3: Signal Engine Compatibility and CLI

**Files:**

- Modify: `src/signals/signal_engine.py`
- Create: `scripts/describe_multi_tf_rules.py`
- Create: `tests/test_describe_multi_tf_rules.py`

- [ ] **Step 1: Add failing tests for typed signal compatibility and CLI**

```python
import json
import subprocess
import sys

from src.context.multi_tf_rules import build_multi_tf_decision
from src.signals.signal_engine import generate_signal
from tests.test_multi_tf_rules import snap


def test_signal_engine_accepts_multi_tf_decision():
    decision = build_multi_tf_decision(
        tf_4h=snap("4h", macd=0, cci=0, cvd_delta=0),
        tf_1h=snap("1h", macd=1, cci=120, cvd_delta=5),
        tf_30m=snap("30m", cci=130),
        tf_15m=snap("15m", rsi=55, cvd_delta=5),
        previous_15m_rsi=45,
    )
    signal = generate_signal(decision)
    assert signal["signal_type"] == "DIRECT"
    assert signal["side"] == "LONG"


def test_describe_multi_tf_rules_outputs_json():
    result = subprocess.run(
        [sys.executable, "scripts/describe_multi_tf_rules.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    assert payload["roles"]["4h"] == "background"
    assert "DIRECT" in payload["outputs"]
```

- [ ] **Step 2: Update signal engine**

```python
def generate_signal(context) -> dict:
    if hasattr(context, "signal_type") and hasattr(context, "side"):
        return {"signal_type": context.signal_type, "side": context.side, "reason": context.reason}
    ...
```

- [ ] **Step 3: Implement CLI**

```python
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.strategy_philosophy import TIMEFRAME_ROLES


def main() -> None:
    payload = {
        "roles": TIMEFRAME_ROLES,
        "outputs": ["DIRECT", "PROBE", "WAIT", "NO_TRADE"],
        "rule": "4h is reference only; 1h permission controls direction",
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_describe_multi_tf_rules.py tests/test_multi_tf_rules.py -q`

Expected: PASS.

---

## Verification

Run:

```powershell
pytest tests/test_multi_tf_rules.py tests/test_describe_multi_tf_rules.py -q
pytest tests/test_indicator_spec_rules.py tests/test_indicator_engine.py tests/test_describe_indicator_rules.py tests/test_project_spec.py tests/test_strategy_philosophy.py tests/test_market_universe.py tests/test_describe_project_rules.py tests/test_framework_scaffold.py -q
python -m compileall src scripts tests
python scripts/describe_multi_tf_rules.py
git diff -- src/api/binance_client.py
```

Expected:

- all tests pass
- compile succeeds
- CLI prints valid JSON
- `src/api/binance_client.py` diff is empty

