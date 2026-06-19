# Backtest Engine Scripts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the section 19 backtest engine contract and a minimal deterministic runner that enforces live-isomorphic order, data integrity, costs, audit events, and no-lookahead fills.

**Architecture:** Extend the existing `src/backtest/engine.py` placeholder into the public section 19 engine module while leaving `src/backtest/protocol.py` as the older section 08 protocol contract. The runner accepts in-memory completed bars and optional strategy/risk callbacks, simulates conservative fills without network calls, records standardized events and artifacts, and reports degraded assumptions when funding data is absent.

**Tech Stack:** Python dataclasses, standard library collections/statistics/json, existing `src.backtest.fee_model`, `src.backtest.fill_model`, and `src.backtest.metrics`, pytest, subprocess-based describe-script tests.

---

### Task 1: Backtest Engine Contract and Validation

**Files:**
- Modify: `src/backtest/engine.py`
- Create: `tests/test_backtest_engine.py`

- [ ] **Step 1: Write failing contract tests**

Add tests that import the public constants, dataclasses, validation helpers, and fill helpers from `src.backtest.engine`. The tests must assert:

```python
def test_backtest_engine_contract_matches_19_doc():
    assert BACKTEST_REQUIRED_INPUTS == [
        "run_id",
        "strategy_name",
        "strategy_version",
        "config_version",
        "data_version",
        "symbols",
        "timeframes",
        "start_time",
        "end_time",
        "initial_capital",
        "fee_model",
        "slippage_model",
        "funding_model",
        "fill_model",
        "capital_constraints",
        "risk_constraints",
        "entry_modes",
        "source",
    ]
    assert BACKTEST_STEP_ORDER == [
        "update_current_time_step_data",
        "update_indicators",
        "update_multi_timeframe_context",
        "update_current_position_state",
        "check_exits",
        "check_reductions",
        "check_additions",
        "check_entries",
        "simulate_order_submit_and_fill",
        "write_events_logs_snapshots",
        "advance",
    ]
    assert BACKTEST_FILL_MODELS == ["NEXT_BAR_OPEN", "TRIGGER_PRICE", "CONSERVATIVE_LIMIT_FILL"]
    assert "ORDER_FILLED" in BACKTEST_REQUIRED_EVENTS
    assert "performance_summary.html" in BACKTEST_ARTIFACTS
    assert "use_future_bar" in BACKTEST_FORBIDDEN_ACTIONS


def test_validate_backtest_request_rejects_missing_duplicate_and_gap_data():
    request = valid_request()
    missing = validate_backtest_request(request, {})
    assert missing.status == "rejected"
    assert any("missing bars" in item for item in missing.issues)

    duplicate_bars = [
        bar(0, close=100),
        bar(900, close=101),
        bar(900, close=102),
    ]
    duplicate = validate_backtest_request(request, {"BTCUSDT": duplicate_bars})
    assert duplicate.status == "rejected"
    assert any("duplicate timestamp" in item for item in duplicate.issues)

    gap_bars = [bar(0, close=100), bar(1800, close=101)]
    gap = validate_backtest_request(request, {"BTCUSDT": gap_bars})
    assert gap.status == "rejected"
    assert any("gap before" in item for item in gap.issues)


def test_assert_no_lookahead_blocks_future_data():
    assert_no_lookahead(900, 900)
    with pytest.raises(ValueError, match="future"):
        assert_no_lookahead(900, 1800)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_backtest_engine.py -q`

Expected: FAIL because the new constants and helpers do not exist.

- [ ] **Step 3: Implement constants, dataclasses, and validation helpers**

Replace the placeholder engine module with focused definitions:

```python
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Mapping, Sequence

from src.backtest.fee_model import fee
from src.backtest.fill_model import next_bar_market_fill
from src.backtest.metrics import profit_factor, win_rate
from src.core.models import Candle


BACKTEST_REQUIRED_INPUTS = [...]
BACKTEST_RESULT_FIELDS = [...]
BACKTEST_STEP_ORDER = [...]
BACKTEST_FILL_MODELS = ["NEXT_BAR_OPEN", "TRIGGER_PRICE", "CONSERVATIVE_LIMIT_FILL"]
BACKTEST_REQUIRED_EVENTS = [...]
BACKTEST_ARTIFACTS = [...]
BACKTEST_FORBIDDEN_ACTIONS = [...]
BACKTEST_ANALYSIS_DIMENSIONS = [...]
BACKTEST_FAILURE_SAMPLE_TYPES = [...]


@dataclass(frozen=True)
class BacktestRequest:
    run_id: str
    strategy_name: str
    strategy_version: str
    config_version: str
    data_version: str
    symbols: list[str]
    timeframes: list[str]
    start_time: int
    end_time: int
    initial_capital: float
    fee_model: Mapping[str, Any] = field(default_factory=dict)
    slippage_model: Mapping[str, Any] = field(default_factory=dict)
    funding_model: Mapping[str, Any] = field(default_factory=dict)
    fill_model: str = "NEXT_BAR_OPEN"
    capital_constraints: Mapping[str, Any] = field(default_factory=dict)
    risk_constraints: Mapping[str, Any] = field(default_factory=dict)
    entry_modes: list[str] = field(default_factory=lambda: ["PROBE", "DIRECT"])
    source: str = "historical"


@dataclass(frozen=True)
class BacktestValidation:
    status: str
    issues: list[str]
    degraded: list[str]


@dataclass(frozen=True)
class BacktestBar:
    symbol: str
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class BacktestTrade:
    symbol: str
    side: str
    entry_mode: str
    entry_time: int
    entry_price: float
    exit_time: int
    exit_price: float
    quantity: float
    gross_pnl: float
    fees: float
    slippage: float
    funding: float
    net_pnl: float
    reason_enter: str
    reason_exit: str


@dataclass(frozen=True)
class BacktestStepRecord:
    timestamp: int
    symbol: str
    step_order: list[str]
    events: list[str]
    equity: float


@dataclass(frozen=True)
class BacktestResult:
    run_id: str
    status: str
    final_equity: float
    total_return: float
    annual_return: float
    max_drawdown: float
    profit_factor: float | None
    sharpe: float | None
    sortino: float | None
    win_rate: float | None
    avg_win: float | None
    avg_loss: float | None
    expectancy: float | None
    trade_count: int
    symbol_breakdown: dict[str, dict[str, Any]]
    side_breakdown: dict[str, dict[str, Any]]
    entry_mode_breakdown: dict[str, dict[str, Any]]
    summary_json: dict[str, Any]
    report_path: str
    events: list[dict[str, Any]] = field(default_factory=list)
    trades: list[BacktestTrade] = field(default_factory=list)
    equity_curve: list[dict[str, Any]] = field(default_factory=list)
    drawdown_curve: list[dict[str, Any]] = field(default_factory=list)
    state_transitions: list[dict[str, Any]] = field(default_factory=list)
    risk_events: list[dict[str, Any]] = field(default_factory=list)
    signal_events: list[dict[str, Any]] = field(default_factory=list)
    failed_samples: list[dict[str, Any]] = field(default_factory=list)
    artifacts: dict[str, str] = field(default_factory=dict)
    degraded_assumptions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
```

Implement `validate_backtest_request`, `assert_no_lookahead`, `_normalize_bar`, `_bar_timestamp`, and `_expected_step_seconds` with no network or exchange dependency. Validation must reject missing symbols, duplicate timestamps, gaps, invalid OHLCV, invalid fill models, non-positive capital, and end times not greater than start times. Funding data absence should be a degraded assumption, not a silent pass.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_backtest_engine.py -q`

Expected: PASS for the new contract tests.

### Task 2: Deterministic Runner, Costs, Events, and Metrics

**Files:**
- Modify: `src/backtest/engine.py`
- Modify: `tests/test_backtest_engine.py`

- [ ] **Step 1: Write failing runner tests**

Add tests that assert:

```python
def test_next_bar_open_fill_uses_next_bar_and_not_same_bar():
    request = valid_request(fill_model="NEXT_BAR_OPEN")
    bars = {"BTCUSDT": [bar(0, open=100, close=101), bar(900, open=110, close=111), bar(1800, open=120, close=121)]}
    result = run_backtest(request, bars, strategy_callback=always_long_direct)
    assert result.status == "completed"
    assert result.trades[0].entry_time == 900
    assert result.trades[0].entry_price > 110
    assert result.summary_json["fill_model"] == "NEXT_BAR_OPEN"


def test_runner_records_required_events_breakdowns_and_costs():
    request = valid_request(symbols=["BTCUSDT", "ETHUSDT"])
    bars = {
        "BTCUSDT": [bar(0, symbol="BTCUSDT"), bar(900, symbol="BTCUSDT", open=102), bar(1800, symbol="BTCUSDT", open=105)],
        "ETHUSDT": [bar(0, symbol="ETHUSDT"), bar(900, symbol="ETHUSDT", open=50), bar(1800, symbol="ETHUSDT", open=49)],
    }
    result = run_backtest(request, bars, strategy_callback=alternating_strategy)
    event_names = [item["event_type"] for item in result.events]
    assert "SIGNAL_CREATED" in event_names
    assert "ORDER_SUBMITTED" in event_names
    assert "ORDER_FILLED" in event_names
    assert "BACKTEST_STEP_COMPLETED" in event_names
    assert result.symbol_breakdown["BTCUSDT"]["trade_count"] >= 1
    assert "LONG" in result.side_breakdown
    assert "DIRECT" in result.entry_mode_breakdown
    assert result.trades[0].fees > 0
    assert result.trades[0].slippage > 0
    assert "funding_missing_approximate" in result.degraded_assumptions


def test_risk_block_and_signal_rejection_are_failed_samples():
    result = run_backtest(valid_request(), {"BTCUSDT": [bar(0), bar(900), bar(1800)]}, strategy_callback=blocked_strategy)
    assert any(item["type"] == "risk_blocked" for item in result.failed_samples)
    assert any(item["event_type"] == "RISK_BLOCKED" for item in result.risk_events)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_backtest_engine.py -q`

Expected: FAIL because `run_backtest` and metric/event behavior are incomplete.

- [ ] **Step 3: Implement runner and metrics**

Add:

```python
StrategyCallback = Callable[[BacktestRequest, str, BacktestBar, Mapping[str, Any]], Mapping[str, Any] | None]


class BacktestEngine:
    def __init__(self, request: BacktestRequest | None = None):
        self.request = request

    def run(self, bars_by_symbol: Mapping[str, Sequence[Any]] | None = None, strategy_callback: StrategyCallback | None = None) -> BacktestResult | dict[str, Any]:
        if self.request is None or bars_by_symbol is None:
            return {"status": "not_implemented", "fill_model": "NEXT_BAR_OPEN"}
        return run_backtest(self.request, bars_by_symbol, strategy_callback=strategy_callback)
```

Implement `run_backtest` using this minimal deterministic rule:

- Validate request and bars first.
- Iterate symbols in `request.symbols` order.
- Iterate bars by timestamp order.
- At each step append `BACKTEST_STEP_COMPLETED`.
- Call the optional strategy callback with only the current completed bar and previous context.
- Treat `None`, `NO_TRADE`, `WAIT`, and `entry_mode == "NONE"` as signal-rejected failed samples.
- Treat `risk_allowed is False` or `allow_trade is False` as `RISK_BLOCKED`.
- For an accepted signal, fill at the next bar open for `NEXT_BAR_OPEN`, at the current close for `TRIGGER_PRICE`, and only fill conservative limit orders when the next bar crosses the supplied limit price.
- Never use next bar high/low/close for signal decisions; next bar data is only used by the explicit fill model.
- Close the minimal one-bar trade at the following bar open when available so metrics are deterministic.
- Apply fee bps, slippage bps, and funding bps if present. If funding model is missing, include `funding_missing_approximate`.
- Record `SIGNAL_CREATED`, `ORDER_SUBMITTED`, `ORDER_FILLED`, `POSITION_OPENED`, `POSITION_CLOSED`, `BACKTEST_STEP_COMPLETED` and risk/signal failure events as appropriate.
- Build `symbol_breakdown`, `side_breakdown`, and `entry_mode_breakdown`.
- Build `equity_curve`, `drawdown_curve`, `summary_json`, `artifacts`, and `degraded_assumptions`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_backtest_engine.py -q`

Expected: PASS for contract and runner tests.

### Task 3: Describe Script and Scaffold Sync

**Files:**
- Create: `scripts/describe_backtest_engine.py`
- Create: `tests/test_describe_backtest_engine.py`
- Modify: `scripts/scaffold_ai300_framework.py`
- Modify: `tests/test_framework_scaffold.py`

- [ ] **Step 1: Write failing describe and scaffold tests**

Add:

```python
def test_describe_backtest_engine_outputs_completed_19_sections():
    completed = subprocess.run(
        [sys.executable, "scripts/describe_backtest_engine.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["engine"] == "backtest_engine"
    assert payload["request_fields"][0] == "run_id"
    assert payload["result_fields"][0] == "run_id"
    assert payload["step_order"][4] == "check_exits"
    assert payload["fill_models"] == ["NEXT_BAR_OPEN", "TRIGGER_PRICE", "CONSERVATIVE_LIMIT_FILL"]
    assert "funding" in payload["required_costs"]
    assert "use_future_bar" in payload["forbidden_actions"]
    assert "backtest_result.json" in payload["artifacts"]
    assert payload["sample_result"]["status"] == "completed"
```

Append to `tests/test_framework_scaffold.py`:

```python
def test_scaffold_includes_backtest_engine_19_templates():
    assert "src/backtest/engine.py" in FILES
    assert "scripts/describe_backtest_engine.py" in FILES
    assert "tests/test_backtest_engine.py" in FILES
    assert "tests/test_describe_backtest_engine.py" in FILES
    assert "BacktestRequest" in FILES["src/backtest/engine.py"]
    assert "BACKTEST_STEP_ORDER" in FILES["src/backtest/engine.py"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_describe_backtest_engine.py tests/test_framework_scaffold.py -q`

Expected: FAIL because the script and scaffold templates do not exist yet.

- [ ] **Step 3: Implement describe script**

Create `scripts/describe_backtest_engine.py` that imports the new engine constants and runs a tiny deterministic sample with three bars. JSON output must include:

- `engine`
- `request_fields`
- `result_fields`
- `step_order`
- `fill_models`
- `required_events`
- `artifacts`
- `analysis_dimensions`
- `failure_sample_types`
- `required_costs`
- `forbidden_actions`
- `sample_result`

- [ ] **Step 4: Sync scaffold templates**

Update `scripts/scaffold_ai300_framework.py` `FILES` with:

- `src/backtest/engine.py`
- `scripts/describe_backtest_engine.py`
- `tests/test_backtest_engine.py`
- `tests/test_describe_backtest_engine.py`

Use compact templates that preserve the same public names. Do not modify protected Binance client entries.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_describe_backtest_engine.py tests/test_framework_scaffold.py -q`

Expected: PASS.

### Task 4: Final Verification and Clean Workspace Artifacts

**Files:**
- No source edits expected unless verification exposes a defect.

- [ ] **Step 1: Run targeted backtest verification**

Run:

```powershell
pytest tests\test_backtest_engine.py tests\test_describe_backtest_engine.py tests\test_backtest_protocol.py tests\test_describe_backtest_protocol.py tests\test_framework_scaffold.py -q
```

Expected: PASS.

- [ ] **Step 2: Run full verification**

Run:

```powershell
pytest -q
python -m compileall src scripts tests
python scripts\describe_backtest_engine.py
```

Expected: all commands exit 0.

- [ ] **Step 3: Confirm Binance client untouched**

Run:

```powershell
git diff -- src\api\binance_client.py
```

Expected: no output.

- [ ] **Step 4: Remove generated Python cache directories**

Run:

```powershell
$root=(Resolve-Path '.').Path
$targets=Get-ChildItem -Path . -Recurse -Directory -Filter '__pycache__' | Where-Object { $_.FullName.StartsWith($root) }
foreach($target in $targets){ Remove-Item -LiteralPath $target.FullName -Recurse -Force }
Get-ChildItem -Path . -Recurse -Directory -Filter '__pycache__' | Select-Object -First 5 -ExpandProperty FullName
```

Expected: no output from the final command.

---

## Self-Review

Spec coverage:
- Inputs, outputs, execution order, fill models, costs, funding degradation, events, artifacts, analysis dimensions, failed samples, and no-lookahead boundaries are each covered by a task.
- This plan intentionally implements a minimal deterministic in-memory runner, not a production historical-data downloader or exchange-connected simulator.

Placeholder scan:
- No TBD/TODO/fill-later placeholders remain.

Type consistency:
- `BacktestRequest`, `BacktestResult`, `BacktestTrade`, `BacktestStepRecord`, `validate_backtest_request`, `assert_no_lookahead`, `run_backtest`, and `build_artifact_manifest` are used consistently across tasks.
