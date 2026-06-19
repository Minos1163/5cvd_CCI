# Risk Exit and Backtest Protocol Scripts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the scripts required by `docs/07_risk_and_exit+08.md` as deterministic risk-exit and backtest-protocol utilities.

**Architecture:** Add pure, side-effect-free modules for exit planning and backtest protocol validation. The risk module creates auditable exit actions from explicit market/portfolio flags, while the backtest module validates data quality, fixed bar processing order, required costs, and required output fields without introducing live execution or a full historical matching engine.

**Tech Stack:** Python standard library, dataclasses, enums, pytest.

---

## Scope Notes

`docs/07_risk_and_exit+08.md` contains two specs: risk/exit rules and backtest protocol rules. This plan implements their explicit contracts as scriptable utilities:

- ATR is the only initial stop source.
- Exit action priority is fixed: forced stop, portfolio risk, direction reversal, volatility anomaly, trailing stop, partial take profit.
- Take profit levels are R-based and partial.
- Breakeven/trailing stop planning is deterministic and includes fee/slippage/safety buffer.
- Cooldown can be computed after stop events.
- Backtest protocol validates completed-bar sequencing, data continuity, no duplicate timestamps, cost presence, position-model requirements, trade journal fields, performance fields, and fixed processing order.

This plan does not implement a full backtest fill engine, exchange precision, real order placement, parameter optimization, or walk-forward orchestration. Those belong to later docs or larger implementation slices.

## File Structure

- Modify: `src/risk/stop_engine.py` - keep `atr_stop`, add initial stop detail and breakeven stop helpers.
- Create: `src/risk/exit_engine.py` - add `ExitAction`, exit priority constants, TP planning, trailing-stop planning, forced-exit selection, and cooldown helper.
- Create: `src/backtest/protocol.py` - add data quality validation, bar processing order, required output fields, and protocol validation.
- Create: `scripts/describe_risk_exit_rules.py` - prints 07 risk/exit policy as JSON.
- Create: `scripts/describe_backtest_protocol.py` - prints 08 backtest protocol as JSON.
- Create: `tests/test_risk_exit_engine.py` - tests ATR stop, TP levels, trailing stop, priority, forced exit, cooldown.
- Create: `tests/test_backtest_protocol.py` - tests data continuity, duplicates, fixed processing order, cost requirements, required outputs.
- Create: `tests/test_describe_risk_exit_rules.py` - tests 07 describe script JSON.
- Create: `tests/test_describe_backtest_protocol.py` - tests 08 describe script JSON.
- Modify: `scripts/scaffold_ai300_framework.py` - keep generated framework template aligned with the new modules, scripts, and tests.
- Preserve: `src/api/binance_client.py` - do not modify the stable Binance client.

---

### Task 1: Initial Stop and Exit Action Priority

**Files:**

- Modify: `src/risk/stop_engine.py`
- Create: `src/risk/exit_engine.py`
- Create: `tests/test_risk_exit_engine.py`

- [ ] **Step 1: Write failing tests for ATR stop detail and exit priority**

```python
import pytest

from src.risk.exit_engine import (
    EXIT_PRIORITY,
    ExitAction,
    ExitActionType,
    select_highest_priority_action,
)
from src.risk.stop_engine import initial_atr_stop


def test_initial_atr_stop_uses_atr_distance_for_long():
    stop = initial_atr_stop(entry_price=100, atr=2, atr_mult=1.5, side="LONG")
    assert stop.stop_price == 97
    assert stop.stop_distance == 3
    assert stop.stop_pct == pytest.approx(0.03)
    assert stop.reason == "initial ATR stop"


def test_initial_atr_stop_uses_atr_distance_for_short():
    stop = initial_atr_stop(entry_price=100, atr=2, atr_mult=1.5, side="SHORT")
    assert stop.stop_price == 103
    assert stop.stop_distance == 3
    assert stop.stop_pct == pytest.approx(0.03)


def test_exit_priority_matches_spec_order():
    assert EXIT_PRIORITY == [
        ExitActionType.FORCED_STOP,
        ExitActionType.PORTFOLIO_RISK,
        ExitActionType.DIRECTION_REVERSAL,
        ExitActionType.VOLATILITY_ANOMALY,
        ExitActionType.TRAILING_STOP,
        ExitActionType.PARTIAL_TAKE_PROFIT,
    ]


def test_select_highest_priority_action_prevents_lower_priority_override():
    actions = [
        ExitAction(ExitActionType.PARTIAL_TAKE_PROFIT, "take tp1", reduce_pct=0.30),
        ExitAction(ExitActionType.FORCED_STOP, "stop hit", reduce_pct=1.0),
    ]
    selected = select_highest_priority_action(actions)
    assert selected.action_type == ExitActionType.FORCED_STOP
    assert selected.reason == "stop hit"
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_risk_exit_engine.py -q`

Expected: FAIL because `initial_atr_stop` and `exit_engine` do not exist.

- [ ] **Step 3: Implement ATR stop detail and priority selection**

In `src/risk/stop_engine.py`:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class StopPlan:
    stop_price: float
    stop_distance: float
    stop_pct: float
    reason: str


def initial_atr_stop(entry_price: float, atr: float, atr_mult: float, side: str) -> StopPlan:
    stop_price = atr_stop(entry_price, atr, atr_mult, side)
    stop_distance = abs(entry_price - stop_price)
    return StopPlan(
        stop_price=stop_price,
        stop_distance=stop_distance,
        stop_pct=stop_distance / entry_price,
        reason="initial ATR stop",
    )
```

Create `src/risk/exit_engine.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ExitActionType(str, Enum):
    FORCED_STOP = "FORCED_STOP"
    PORTFOLIO_RISK = "PORTFOLIO_RISK"
    DIRECTION_REVERSAL = "DIRECTION_REVERSAL"
    VOLATILITY_ANOMALY = "VOLATILITY_ANOMALY"
    TRAILING_STOP = "TRAILING_STOP"
    PARTIAL_TAKE_PROFIT = "PARTIAL_TAKE_PROFIT"


EXIT_PRIORITY = [
    ExitActionType.FORCED_STOP,
    ExitActionType.PORTFOLIO_RISK,
    ExitActionType.DIRECTION_REVERSAL,
    ExitActionType.VOLATILITY_ANOMALY,
    ExitActionType.TRAILING_STOP,
    ExitActionType.PARTIAL_TAKE_PROFIT,
]


@dataclass(frozen=True)
class ExitAction:
    action_type: ExitActionType
    reason: str
    reduce_pct: float = 1.0
    target_price: float | None = None
    stop_price: float | None = None


def select_highest_priority_action(actions: list[ExitAction]) -> ExitAction | None:
    if not actions:
        return None
    rank = {action_type: index for index, action_type in enumerate(EXIT_PRIORITY)}
    return sorted(actions, key=lambda action: rank[action.action_type])[0]
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_risk_exit_engine.py -q`

Expected: PASS for initial stop and priority tests.

---

### Task 2: Take Profit, Trailing Stop, Forced Exit, Cooldown

**Files:**

- Modify: `src/risk/exit_engine.py`
- Modify: `src/risk/stop_engine.py`
- Modify: `tests/test_risk_exit_engine.py`

- [ ] **Step 1: Add failing tests for TP levels, trailing stop, forced exit, cooldown**

Append to `tests/test_risk_exit_engine.py`:

```python
from src.risk.exit_engine import (
    breakeven_stop,
    cooldown_until,
    forced_exit_actions,
    plan_take_profit_actions,
    trailing_stop_from_structure,
)


def test_plan_take_profit_actions_are_r_based_partials_for_long():
    actions = plan_take_profit_actions(entry_price=100, stop_price=95, side="LONG")
    assert [action.target_price for action in actions] == [105, 110, 115]
    assert [action.reduce_pct for action in actions] == [0.30, 0.40, 0.30]
    assert all(action.action_type == ExitActionType.PARTIAL_TAKE_PROFIT for action in actions)


def test_plan_take_profit_actions_are_r_based_partials_for_short():
    actions = plan_take_profit_actions(entry_price=100, stop_price=105, side="SHORT", r_levels=(1, 2, 4))
    assert [action.target_price for action in actions] == [95, 90, 80]


def test_breakeven_stop_covers_fee_slippage_and_safety_buffer():
    stop = breakeven_stop(entry_price=100, side="LONG", fee_bps=5, slippage_bps=5, safety_bps=10)
    assert stop == pytest.approx(100.2)


def test_trailing_stop_uses_structure_without_widening_long_stop():
    action = trailing_stop_from_structure(
        side="LONG",
        current_stop=100,
        structure_price=103,
        buffer_pct=0.01,
    )
    assert action.stop_price == pytest.approx(101.97)
    assert action.action_type == ExitActionType.TRAILING_STOP


def test_trailing_stop_returns_none_when_it_would_widen_stop():
    action = trailing_stop_from_structure(
        side="LONG",
        current_stop=100,
        structure_price=99,
        buffer_pct=0.01,
    )
    assert action is None


def test_forced_exit_actions_use_highest_priority_flags():
    actions = forced_exit_actions(
        stop_hit=True,
        portfolio_risk=True,
        direction_reversal=True,
        volatility_anomaly=True,
    )
    selected = select_highest_priority_action(actions)
    assert selected.action_type == ExitActionType.FORCED_STOP


def test_cooldown_until_counts_completed_bars():
    assert cooldown_until(now_ts=1_000, bars=4, timeframe_seconds=900) == 4_600
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_risk_exit_engine.py -q`

Expected: FAIL because the planning helpers are missing.

- [ ] **Step 3: Implement the planning helpers**

In `src/risk/exit_engine.py`:

```python
def _risk_unit(entry_price: float, stop_price: float) -> float:
    if entry_price <= 0 or stop_price <= 0:
        raise ValueError("entry_price and stop_price must be positive")
    distance = abs(entry_price - stop_price)
    if distance <= 0:
        raise ValueError("stop distance must be positive")
    return distance


def plan_take_profit_actions(
    entry_price: float,
    stop_price: float,
    side: str,
    r_levels: tuple[float, ...] = (1.0, 2.0, 3.0),
    reduce_pcts: tuple[float, ...] = (0.30, 0.40, 0.30),
) -> list[ExitAction]:
    if len(r_levels) != len(reduce_pcts):
        raise ValueError("r_levels and reduce_pcts must have the same length")
    risk = _risk_unit(entry_price, stop_price)
    normalized_side = side.strip().upper()
    actions = []
    for r_level, reduce_pct in zip(r_levels, reduce_pcts):
        if normalized_side == "LONG":
            target = entry_price + risk * r_level
        elif normalized_side == "SHORT":
            target = entry_price - risk * r_level
        else:
            raise ValueError("side must be LONG or SHORT")
        actions.append(
            ExitAction(
                ExitActionType.PARTIAL_TAKE_PROFIT,
                f"take profit {r_level:g}R",
                reduce_pct=reduce_pct,
                target_price=target,
            )
        )
    return actions


def breakeven_stop(entry_price: float, side: str, fee_bps: float, slippage_bps: float, safety_bps: float) -> float:
    if entry_price <= 0:
        raise ValueError("entry_price must be positive")
    total_bps = fee_bps + slippage_bps + safety_bps
    if total_bps < 0:
        raise ValueError("buffers must be non-negative")
    buffer = entry_price * total_bps / 10000
    normalized_side = side.strip().upper()
    if normalized_side == "LONG":
        return entry_price + buffer
    if normalized_side == "SHORT":
        return entry_price - buffer
    raise ValueError("side must be LONG or SHORT")


def trailing_stop_from_structure(side: str, current_stop: float, structure_price: float, buffer_pct: float) -> ExitAction | None:
    if current_stop <= 0 or structure_price <= 0 or buffer_pct < 0:
        raise ValueError("prices must be positive and buffer_pct must be non-negative")
    normalized_side = side.strip().upper()
    if normalized_side == "LONG":
        candidate = structure_price * (1 - buffer_pct)
        if candidate <= current_stop:
            return None
    elif normalized_side == "SHORT":
        candidate = structure_price * (1 + buffer_pct)
        if candidate >= current_stop:
            return None
    else:
        raise ValueError("side must be LONG or SHORT")
    return ExitAction(ExitActionType.TRAILING_STOP, "structure trailing stop", stop_price=candidate)


def forced_exit_actions(
    stop_hit: bool = False,
    portfolio_risk: bool = False,
    direction_reversal: bool = False,
    volatility_anomaly: bool = False,
) -> list[ExitAction]:
    actions = []
    if stop_hit:
        actions.append(ExitAction(ExitActionType.FORCED_STOP, "initial stop hit", reduce_pct=1.0))
    if portfolio_risk:
        actions.append(ExitAction(ExitActionType.PORTFOLIO_RISK, "portfolio risk limit exceeded", reduce_pct=1.0))
    if direction_reversal:
        actions.append(ExitAction(ExitActionType.DIRECTION_REVERSAL, "direction reversal confirmed", reduce_pct=1.0))
    if volatility_anomaly:
        actions.append(ExitAction(ExitActionType.VOLATILITY_ANOMALY, "volatility anomaly protection", reduce_pct=0.50))
    return actions


def cooldown_until(now_ts: int, bars: int, timeframe_seconds: int = 900) -> int:
    if bars < 0 or timeframe_seconds <= 0:
        raise ValueError("bars must be non-negative and timeframe_seconds must be positive")
    return now_ts + bars * timeframe_seconds
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_risk_exit_engine.py -q`

Expected: PASS.

---

### Task 3: Backtest Protocol Validation

**Files:**

- Create: `src/backtest/protocol.py`
- Create: `tests/test_backtest_protocol.py`

- [ ] **Step 1: Write failing tests for data and protocol checks**

```python
from src.backtest.protocol import (
    BACKTEST_PROCESSING_ORDER,
    REQUIRED_PERFORMANCE_FIELDS,
    REQUIRED_TRADE_FIELDS,
    ProtocolCheck,
    validate_backtest_protocol,
    validate_candle_continuity,
    validate_processing_order,
)
from src.core.models import Candle


def candle(open_time: int, close_time: int, volume: float = 10) -> Candle:
    return Candle(
        symbol="BTCUSDT",
        timeframe="15m",
        open_time=open_time,
        close_time=close_time,
        open=100,
        high=105,
        low=95,
        close=101,
        volume=volume,
    )


def test_processing_order_is_exit_before_entry():
    assert BACKTEST_PROCESSING_ORDER == [
        "update_history",
        "update_indicators",
        "update_multi_timeframe_context",
        "update_state",
        "check_exit",
        "check_reduce",
        "check_add",
        "check_entry",
        "record_events",
    ]
    assert validate_processing_order(BACKTEST_PROCESSING_ORDER).passed is True


def test_processing_order_rejects_entry_before_exit():
    wrong = list(BACKTEST_PROCESSING_ORDER)
    wrong[4], wrong[7] = wrong[7], wrong[4]
    result = validate_processing_order(wrong)
    assert result.passed is False
    assert "fixed processing order" in result.reason


def test_validate_candle_continuity_detects_duplicates_and_gaps():
    candles = [candle(0, 900), candle(900, 1800), candle(900, 1800), candle(2700, 3600)]
    results = validate_candle_continuity(candles, timeframe_seconds=900)
    failed = [result.reason for result in results if not result.passed]
    assert any("duplicate" in reason for reason in failed)
    assert any("gap" in reason for reason in failed)


def test_validate_backtest_protocol_requires_costs_outputs_and_position_model():
    results = validate_backtest_protocol(
        fee_bps=5,
        slippage_bps=5,
        fill_model="next_bar_open",
        uses_position_sizer=True,
        trade_fields=set(REQUIRED_TRADE_FIELDS),
        performance_fields=set(REQUIRED_PERFORMANCE_FIELDS),
    )
    assert all(result.passed for result in results)


def test_validate_backtest_protocol_rejects_missing_costs():
    results = validate_backtest_protocol(
        fee_bps=0,
        slippage_bps=0,
        fill_model="next_bar_open",
        uses_position_sizer=True,
        trade_fields=set(REQUIRED_TRADE_FIELDS),
        performance_fields=set(REQUIRED_PERFORMANCE_FIELDS),
    )
    assert any((not result.passed and "fee" in result.reason) for result in results)
    assert any((not result.passed and "slippage" in result.reason) for result in results)
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_backtest_protocol.py -q`

Expected: FAIL because `src/backtest/protocol.py` does not exist.

- [ ] **Step 3: Implement protocol validators**

Create `src/backtest/protocol.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

from src.core.models import Candle


BACKTEST_PROCESSING_ORDER = [
    "update_history",
    "update_indicators",
    "update_multi_timeframe_context",
    "update_state",
    "check_exit",
    "check_reduce",
    "check_add",
    "check_entry",
    "record_events",
]

REQUIRED_TRADE_FIELDS = [
    "symbol",
    "side",
    "entry_time",
    "entry_price",
    "exit_time",
    "exit_price",
    "size",
    "leverage",
    "stop_price",
    "take_profit_price",
    "pnl",
    "pnl_pct",
    "reason_enter",
    "reason_exit",
    "state_before",
    "state_after",
]

REQUIRED_PERFORMANCE_FIELDS = [
    "total_return",
    "annualized_return",
    "max_drawdown",
    "win_rate",
    "profit_factor",
    "sharpe",
    "sortino",
    "average_rr",
    "average_holding_time",
    "symbol_performance",
    "portfolio_performance",
    "probe_vs_direct",
    "long_vs_short",
]


@dataclass(frozen=True)
class ProtocolCheck:
    name: str
    passed: bool
    reason: str


def validate_processing_order(order: list[str]) -> ProtocolCheck:
    if order == BACKTEST_PROCESSING_ORDER:
        return ProtocolCheck("processing_order", True, "fixed processing order approved")
    return ProtocolCheck("processing_order", False, "must use fixed processing order with exits before entries")


def validate_candle_continuity(candles: list[Candle], timeframe_seconds: int) -> list[ProtocolCheck]:
    if timeframe_seconds <= 0:
        raise ValueError("timeframe_seconds must be positive")
    results = []
    seen = set()
    sorted_candles = sorted(candles, key=lambda item: item.open_time)
    for index, item in enumerate(sorted_candles):
        if item.open_time in seen:
            results.append(ProtocolCheck("duplicate_timestamp", False, f"duplicate timestamp {item.open_time}"))
        seen.add(item.open_time)
        if item.volume <= 0:
            results.append(ProtocolCheck("zero_volume", False, f"zero volume at {item.open_time}"))
        if item.high < max(item.open, item.close) or item.low > min(item.open, item.close):
            results.append(ProtocolCheck("ohlc_integrity", False, f"invalid OHLC at {item.open_time}"))
        if index > 0:
            expected = sorted_candles[index - 1].open_time + timeframe_seconds
            if item.open_time != expected:
                results.append(ProtocolCheck("time_gap", False, f"gap before {item.open_time}"))
    if not results:
        results.append(ProtocolCheck("candle_continuity", True, "candles are continuous"))
    return results


def validate_backtest_protocol(
    fee_bps: float,
    slippage_bps: float,
    fill_model: str,
    uses_position_sizer: bool,
    trade_fields: set[str],
    performance_fields: set[str],
) -> list[ProtocolCheck]:
    checks = [
        ProtocolCheck("fee", fee_bps > 0, "fee bps must be included"),
        ProtocolCheck("slippage", slippage_bps > 0, "slippage bps must be included"),
        ProtocolCheck("fill_model", fill_model in {"next_bar_open", "trigger_price", "conservative_limit"}, "approved fill model required"),
        ProtocolCheck("position_model", uses_position_sizer, "backtest must use live position sizing model"),
    ]
    missing_trade = sorted(set(REQUIRED_TRADE_FIELDS) - trade_fields)
    checks.append(ProtocolCheck("trade_fields", not missing_trade, f"missing trade fields: {missing_trade}" if missing_trade else "trade fields complete"))
    missing_perf = sorted(set(REQUIRED_PERFORMANCE_FIELDS) - performance_fields)
    checks.append(ProtocolCheck("performance_fields", not missing_perf, f"missing performance fields: {missing_perf}" if missing_perf else "performance fields complete"))
    checks.append(validate_processing_order(BACKTEST_PROCESSING_ORDER))
    return checks
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_backtest_protocol.py -q`

Expected: PASS.

---

### Task 4: Describe Scripts

**Files:**

- Create: `scripts/describe_risk_exit_rules.py`
- Create: `scripts/describe_backtest_protocol.py`
- Create: `tests/test_describe_risk_exit_rules.py`
- Create: `tests/test_describe_backtest_protocol.py`

- [ ] **Step 1: Write failing tests for describe scripts**

Create `tests/test_describe_risk_exit_rules.py`:

```python
import json
import subprocess
import sys


def test_describe_risk_exit_rules_outputs_policy_json():
    completed = subprocess.run(
        [sys.executable, "scripts/describe_risk_exit_rules.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["initial_stop_source"] == "ATR only"
    assert payload["exit_priority"][0] == "FORCED_STOP"
    assert payload["take_profit"]["r_levels"] == [1.0, 2.0, 3.0]
    assert payload["forbidden"][0] == "multiple active stop systems"
```

Create `tests/test_describe_backtest_protocol.py`:

```python
import json
import subprocess
import sys


def test_describe_backtest_protocol_outputs_policy_json():
    completed = subprocess.run(
        [sys.executable, "scripts/describe_backtest_protocol.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["base_timeframe"] == "15m"
    assert payload["processing_order"][4] == "check_exit"
    assert payload["processing_order"][7] == "check_entry"
    assert "sharpe" in payload["required_performance_fields"]
    assert payload["costs_required"] == ["fee", "slippage"]
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_describe_risk_exit_rules.py tests/test_describe_backtest_protocol.py -q`

Expected: FAIL because the scripts do not exist.

- [ ] **Step 3: Implement describe scripts**

Create `scripts/describe_risk_exit_rules.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.risk.exit_engine import EXIT_PRIORITY


def main() -> None:
    payload = {
        "initial_stop_source": "ATR only",
        "exit_priority": [item.value for item in EXIT_PRIORITY],
        "take_profit": {"r_levels": [1.0, 2.0, 3.0], "reduce_pcts": [0.30, 0.40, 0.30]},
        "breakeven_buffer": ["fee", "slippage", "safety"],
        "cooldown": {"default_timeframe": "15m", "normal_stop_bars": [3, 6]},
        "forbidden": [
            "multiple active stop systems",
            "execution layer rewriting risk model",
            "lower-priority exit overriding higher-priority exit",
            "loss averaging",
        ],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
```

Create `scripts/describe_backtest_protocol.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.backtest.protocol import BACKTEST_PROCESSING_ORDER, REQUIRED_PERFORMANCE_FIELDS, REQUIRED_TRADE_FIELDS


def main() -> None:
    payload = {
        "base_timeframe": "15m",
        "higher_timeframes": ["30m", "1h", "4h"],
        "processing_order": BACKTEST_PROCESSING_ORDER,
        "approved_fill_models": ["next_bar_open", "trigger_price", "conservative_limit"],
        "costs_required": ["fee", "slippage"],
        "required_trade_fields": REQUIRED_TRADE_FIELDS,
        "required_performance_fields": REQUIRED_PERFORMANCE_FIELDS,
        "forbidden": [
            "future data",
            "unfinished candle final values",
            "ignoring fees or slippage",
            "inflating probe into direct",
        ],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_describe_risk_exit_rules.py tests/test_describe_backtest_protocol.py -q`

Expected: PASS.

---

### Task 5: Scaffold Sync and Verification

**Files:**

- Modify: `scripts/scaffold_ai300_framework.py`

- [ ] **Step 1: Update scaffold templates**

Copy the final contents of these files into the matching string templates in `scripts/scaffold_ai300_framework.py`:

- `src/risk/stop_engine.py`
- `src/risk/exit_engine.py`
- `src/backtest/protocol.py`
- `scripts/describe_risk_exit_rules.py`
- `scripts/describe_backtest_protocol.py`
- `tests/test_risk_exit_engine.py`
- `tests/test_backtest_protocol.py`
- `tests/test_describe_risk_exit_rules.py`
- `tests/test_describe_backtest_protocol.py`

- [ ] **Step 2: Run targeted tests**

Run: `pytest tests/test_risk_exit_engine.py tests/test_backtest_protocol.py tests/test_describe_risk_exit_rules.py tests/test_describe_backtest_protocol.py tests/test_framework_scaffold.py -q`

Expected: PASS.

- [ ] **Step 3: Run full tests**

Run: `pytest -q`

Expected: PASS.

- [ ] **Step 4: Run compile checks**

Run: `python -m compileall src scripts tests`

Expected: completes successfully.

- [ ] **Step 5: Run describe scripts manually**

Run:

```bash
python scripts/describe_risk_exit_rules.py
python scripts/describe_backtest_protocol.py
```

Expected: JSON outputs include ATR-only initial stop, exit priority order, fixed backtest processing order, and fee/slippage requirements.

- [ ] **Step 6: Verify Binance client untouched**

Run: `git diff -- src/api/binance_client.py`

Expected: no output.

---

## Self-Review

- Spec coverage: covers ATR-only initial stop, TP ladder, breakeven/trailing stop, forced exit priority, cooldown, backtest data integrity, fixed processing order, costs, position model, trade fields, performance fields, and forbidden backtest shortcuts.
- Placeholder scan: no `TBD`, `TODO`, `implement later`, or unspecified test steps.
- Type consistency: `ExitAction`, `ExitActionType`, `ProtocolCheck`, `BACKTEST_PROCESSING_ORDER`, `REQUIRED_TRADE_FIELDS`, and `REQUIRED_PERFORMANCE_FIELDS` are named consistently across tasks.
