# Position Sizing Full Scripts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the scripts required by the completed `docs/06_position_sizing.md`.

**Architecture:** Extend the existing pure `src/risk/position_sizer.py` module instead of adding a parallel sizing engine. Keep the existing public names (`PositionSizingInput`, `PositionSizingResult`, `calculate_position_size`, `size_notional`) compatible, while adding the completed 06 contract: entry-mode sizing, tier/account/portfolio/volatility factors, no-trade gates, precision flooring, and audit payload fields. The module must not call Binance, place orders, mutate live state, or let execution recalculate size.

**Tech Stack:** Python standard library, dataclasses, pytest.

---

## Scope Notes

The previous 06 implementation covered the truncated document: `risk_amount / stop_pct`, `DIRECT` = 100%, `PROBE` = 25%, minimum-notional rejection, margin rejection, and total exposure rejection. The completed `docs/06_position_sizing.md` adds:

- Stable terms for `entry_mode`, `position_side`, `symbol_tier`, `volatility_state`, `correlation_group`, and portfolio/account risk factors.
- Required position sizing steps and audit log fields.
- Explicit `NO_TRADE` result semantics.
- Tier, account, portfolio, volatility, margin, leverage, exposure, cooldown, data-quality, and state-machine gates.
- Precision flooring and a second minimum-notional check after flooring.
- Probe/direct separation: probe must never be inflated or promoted into direct.

This plan implements deterministic contract utilities only. It does not implement exchange metadata fetching, live order placement, leverage API calls, database persistence, or strategy signal generation.

## File Structure

- Modify: `src/risk/position_sizer.py` - add completed 06 constants, dataclass fields, gate helpers, precision flooring, and audit payload.
- Modify: `scripts/describe_position_sizing.py` - expose completed 06 policy, gates, log fields, and samples.
- Modify: `tests/test_position_sizing.py` - add completed 06 behavioral coverage while preserving core legacy expectations where still valid.
- Modify: `tests/test_describe_position_sizing.py` - assert completed 06 describe output.
- Modify: `scripts/scaffold_ai300_framework.py` - sync templates for the modified module, script, and tests.
- Preserve: `src/api/binance_client.py` - do not modify the stable Binance client.

---

### Task 1: Completed 06 Contract Constants and Input Compatibility

**Files:**

- Modify: `src/risk/position_sizer.py`
- Modify: `tests/test_position_sizing.py`

- [ ] **Step 1: Add failing tests for completed 06 constants and aliases**

Append to `tests/test_position_sizing.py`:

```python
from src.risk.position_sizer import (
    ENTRY_MODE_MULTIPLIERS,
    NO_TRADE,
    POSITION_DECISION_STEPS,
    POSITION_LOG_FIELDS,
    POSITION_REQUIRED_INPUTS,
    STATE_POSITION_POLICY,
    normalize_entry_mode,
)


def test_completed_position_sizing_contract_lists_doc_inputs_steps_and_logs():
    assert POSITION_REQUIRED_INPUTS == [
        "account_equity",
        "available_margin",
        "symbol_price",
        "leverage",
        "stop_pct",
        "risk_per_trade_pct",
        "symbol_tier",
        "open_exposure",
        "portfolio_exposure",
        "correlation_group",
        "position_side",
        "entry_mode",
        "volatility_state",
    ]
    assert POSITION_DECISION_STEPS == [
        "read_account_equity_and_available_margin",
        "read_entry_mode",
        "read_stop_pct",
        "calculate_standard_notional",
        "apply_symbol_tier_factor",
        "apply_portfolio_exposure_limit",
        "apply_account_risk_factor",
        "check_min_notional",
        "check_min_margin",
        "output_final_executable_size",
    ]
    assert POSITION_LOG_FIELDS == [
        "symbol",
        "entry_mode",
        "account_equity",
        "available_margin",
        "risk_amount",
        "stop_pct",
        "standard_notional",
        "probe_notional",
        "direct_notional",
        "tier_factor",
        "account_risk_factor",
        "portfolio_risk_factor",
        "final_notional",
        "final_qty",
        "min_notional_check",
        "leverage",
        "decision",
    ]


def test_entry_mode_alias_preserves_existing_signal_type_interface():
    legacy = base_request(signal_type="PROBE")
    explicit = base_request(signal_type="DIRECT", entry_mode="probe")
    assert normalize_entry_mode(legacy) == "PROBE"
    assert normalize_entry_mode(explicit) == "PROBE"
    assert ENTRY_MODE_MULTIPLIERS["DIRECT"] == 1.0
    assert ENTRY_MODE_MULTIPLIERS["PROBE"] == 0.25
    assert NO_TRADE == "NO_TRADE"
    assert STATE_POSITION_POLICY["WATCH"] == "prepare_only"
    assert STATE_POSITION_POLICY["EXIT"] == "close_only"
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_position_sizing.py -q`

Expected: FAIL because completed 06 constants and alias helper are missing.

- [ ] **Step 3: Implement constants and alias helper**

Add to `src/risk/position_sizer.py` near the existing constants:

```python
NO_TRADE = "NO_TRADE"
ENTRY_MODE_MULTIPLIERS = {"DIRECT": 1.0, "PROBE": 0.25}
SIGNAL_MULTIPLIERS = ENTRY_MODE_MULTIPLIERS
POSITION_REQUIRED_INPUTS = [
    "account_equity",
    "available_margin",
    "symbol_price",
    "leverage",
    "stop_pct",
    "risk_per_trade_pct",
    "symbol_tier",
    "open_exposure",
    "portfolio_exposure",
    "correlation_group",
    "position_side",
    "entry_mode",
    "volatility_state",
]
POSITION_DECISION_STEPS = [
    "read_account_equity_and_available_margin",
    "read_entry_mode",
    "read_stop_pct",
    "calculate_standard_notional",
    "apply_symbol_tier_factor",
    "apply_portfolio_exposure_limit",
    "apply_account_risk_factor",
    "check_min_notional",
    "check_min_margin",
    "output_final_executable_size",
]
POSITION_LOG_FIELDS = [
    "symbol",
    "entry_mode",
    "account_equity",
    "available_margin",
    "risk_amount",
    "stop_pct",
    "standard_notional",
    "probe_notional",
    "direct_notional",
    "tier_factor",
    "account_risk_factor",
    "portfolio_risk_factor",
    "final_notional",
    "final_qty",
    "min_notional_check",
    "leverage",
    "decision",
]
STATE_POSITION_POLICY = {
    "WATCH": "prepare_only",
    "PROBE": "probe_size",
    "DIRECT": "direct_size",
    "MANAGE": "manage_only",
    "EXIT": "close_only",
}
VOLATILITY_FACTORS = {"NORMAL": 1.0, "HIGH": 0.5, "EXTREME": 0.0}
```

Extend `PositionSizingInput` with defaulted completed-06 fields, keeping existing constructor compatibility:

```python
    entry_mode: str | None = None
    risk_per_trade_pct: float | None = None
    symbol_tier: str | None = None
    position_side: str = "BOTH"
    volatility_state: str = "NORMAL"
    account_risk_factor: float = 1.0
    portfolio_risk_factor: float = 1.0
    min_margin: float = 0.0
    max_leverage: float = 5.0
    symbol_exposure: float = 0.0
    max_symbol_exposure_pct: float = 0.20
    side_exposure: float = 0.0
    max_side_exposure_pct: float = 0.75
    correlation_group: str = ""
    correlation_group_exposure: float = 0.0
    max_correlation_group_exposure_pct: float = 0.50
    open_positions_count: int = 0
    max_open_positions: int = 5
    quantity_step: float = 0.0
    data_quality_ok: bool = True
    state_allows_entry: bool = True
    cooldown_active: bool = False
    leverage_set: bool = True
```

Add helper functions:

```python
def normalize_entry_mode(request: PositionSizingInput) -> str:
    value = request.entry_mode if request.entry_mode is not None else request.signal_type
    normalized = value.strip().upper()
    if normalized in {"NO_TRADE", "NONE", "WAIT"}:
        return NO_TRADE
    if normalized not in ENTRY_MODE_MULTIPLIERS:
        raise ValueError("entry_mode must be DIRECT, PROBE, or NO_TRADE")
    return normalized


def normalized_symbol_tier(request: PositionSizingInput) -> str:
    value = request.symbol_tier if request.symbol_tier is not None else request.market_tier
    return value.strip().upper()


def effective_risk_pct(request: PositionSizingInput) -> float:
    return request.risk_per_trade_pct if request.risk_per_trade_pct is not None else request.risk_pct
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_position_sizing.py -q`

Expected: PASS for the completed 06 constant and alias tests.

---

### Task 2: Risk Factors, No-Trade Gates, and Audit Payload

**Files:**

- Modify: `src/risk/position_sizer.py`
- Modify: `tests/test_position_sizing.py`

- [ ] **Step 1: Add failing tests for factors, gates, and audit payload**

Append to `tests/test_position_sizing.py`:

```python
def test_direct_size_applies_tier_account_portfolio_and_volatility_factors():
    result = calculate_position_size(
        base_request(
            market_tier="B",
            symbol_tier="B",
            account_risk_factor=0.8,
            portfolio_risk_factor=0.5,
            volatility_state="HIGH",
        )
    )
    assert result.approved is True
    assert result.standard_notional == 5_000
    assert result.notional == 1_000
    assert result.final_notional == 1_000
    assert result.quantity == pytest.approx(0.02)
    assert result.decision == "DIRECT"
    assert result.audit["account_risk_factor"] == 0.8
    assert result.audit["portfolio_risk_factor"] == 0.5
    assert result.audit["decision"] == "DIRECT"


def test_no_trade_mode_returns_clean_no_trade_without_sizing():
    result = calculate_position_size(base_request(entry_mode="NO_TRADE"))
    assert result.approved is False
    assert result.decision == "NO_TRADE"
    assert result.notional == 0
    assert result.quantity == 0
    assert "entry mode is NO_TRADE" in result.reason


def test_state_cooldown_quality_and_leverage_gates_return_no_trade():
    assert calculate_position_size(base_request(data_quality_ok=False)).decision == "NO_TRADE"
    assert calculate_position_size(base_request(state_allows_entry=False)).decision == "NO_TRADE"
    assert calculate_position_size(base_request(cooldown_active=True)).decision == "NO_TRADE"
    assert calculate_position_size(base_request(leverage_set=False)).decision == "NO_TRADE"
    assert calculate_position_size(base_request(leverage=10, max_leverage=5)).decision == "NO_TRADE"


def test_symbol_side_correlation_and_position_count_limits_return_no_trade():
    assert calculate_position_size(
        base_request(symbol_exposure=2_000, max_symbol_exposure_pct=0.20)
    ).decision == "NO_TRADE"
    assert calculate_position_size(
        base_request(side_exposure=7_000, max_side_exposure_pct=0.75)
    ).decision == "NO_TRADE"
    assert calculate_position_size(
        base_request(correlation_group_exposure=4_500, max_correlation_group_exposure_pct=0.50)
    ).decision == "NO_TRADE"
    assert calculate_position_size(
        base_request(open_positions_count=5, max_open_positions=5)
    ).decision == "NO_TRADE"
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_position_sizing.py -q`

Expected: FAIL because factors, decision fields, and new gates are missing.

- [ ] **Step 3: Extend result dataclass and calculation flow**

Extend `PositionSizingResult` with defaulted completed-06 fields:

```python
    decision: str = NO_TRADE
    entry_mode: str = NO_TRADE
    final_notional: float = 0.0
    final_qty: float = 0.0
    tier_factor: float = 1.0
    account_risk_factor: float = 1.0
    portfolio_risk_factor: float = 1.0
    volatility_factor: float = 1.0
    min_notional_check: bool = False
    min_margin_check: bool = False
    leverage_value: float = 0.0
    position_side: str = "BOTH"
    correlation_group: str = ""
    audit: dict | None = None
```

Add helpers:

```python
def volatility_factor(volatility_state: str) -> float:
    value = volatility_state.strip().upper()
    if value not in VOLATILITY_FACTORS:
        raise ValueError("volatility_state must be NORMAL, HIGH, or EXTREME")
    return VOLATILITY_FACTORS[value]


def _gate_no_trade(request: PositionSizingInput, entry_mode: str) -> str | None:
    if entry_mode == NO_TRADE:
        return "entry mode is NO_TRADE"
    if not request.data_quality_ok:
        return "data quality is not tradable"
    if not request.state_allows_entry:
        return "state machine does not allow new position"
    if request.cooldown_active:
        return "cooldown is active"
    if not request.leverage_set:
        return "leverage must be set before sizing"
    if request.leverage > request.max_leverage:
        return "leverage exceeds system maximum"
    if request.open_positions_count >= request.max_open_positions:
        return "max simultaneous positions reached"
    return None
```

Update `calculate_position_size` to:

1. Normalize `entry_mode`, `symbol_tier`, and risk pct.
2. Return `NO_TRADE` with zero size for `entry_mode=NO_TRADE`.
3. Calculate `risk_amount = equity * effective_risk_pct`.
4. Calculate `standard_notional = risk_amount / stop_pct`.
5. Calculate `mode_notional = standard_notional * ENTRY_MODE_MULTIPLIERS[entry_mode]`.
6. Calculate `final_notional = mode_notional * market_tier_multiplier(tier) * account_risk_factor * portfolio_risk_factor * volatility_factor`.
7. Reject without resizing when available margin, total exposure, symbol exposure, side exposure, correlation exposure, or min margin fails.
8. Return an audit dict containing exactly the keys in `POSITION_LOG_FIELDS`.

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_position_sizing.py -q`

Expected: PASS.

---

### Task 3: Precision Flooring and Minimum Recheck

**Files:**

- Modify: `src/risk/position_sizer.py`
- Modify: `tests/test_position_sizing.py`

- [ ] **Step 1: Add failing tests for precision flooring**

Append to `tests/test_position_sizing.py`:

```python
def test_quantity_step_floors_without_inflating_notional():
    result = calculate_position_size(
        base_request(
            market_tier="B",
            quantity_step=0.03,
            price=10_000,
        )
    )
    assert result.approved is True
    assert result.quantity == pytest.approx(0.48)
    assert result.notional == pytest.approx(4_800)
    assert result.notional < result.standard_notional


def test_precision_floor_rechecks_min_notional_and_skips():
    result = calculate_position_size(
        base_request(
            signal_type="PROBE",
            market_tier="B",
            equity=100,
            price=100,
            risk_pct=0.01,
            stop_pct=0.10,
            min_notional=2.4,
            quantity_step=0.02,
        )
    )
    assert result.approved is False
    assert result.decision == "NO_TRADE"
    assert result.notional == pytest.approx(2.0)
    assert result.quantity == pytest.approx(0.02)
    assert "precision floor" in result.reason
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_position_sizing.py -q`

Expected: FAIL because precision flooring is missing.

- [ ] **Step 3: Implement flooring helper and second minimum check**

Add to `src/risk/position_sizer.py`:

```python
def floor_quantity(quantity: float, quantity_step: float) -> float:
    if quantity_step <= 0:
        return quantity
    steps = int(quantity / quantity_step)
    return steps * quantity_step
```

Update `calculate_position_size` after final notional is computed:

```python
raw_quantity = final_notional / request.price
final_quantity = floor_quantity(raw_quantity, request.quantity_step)
final_notional = final_quantity * request.price
```

Then re-run `reject_if_below_min_notional(final_notional, request.min_notional)`. If it fails after flooring, return `NO_TRADE` with reason `notional below exchange minimum after precision floor; skip instead of inflating size`.

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_position_sizing.py -q`

Expected: PASS.

---

### Task 4: Describe Script for Completed 06

**Files:**

- Modify: `scripts/describe_position_sizing.py`
- Modify: `tests/test_describe_position_sizing.py`

- [ ] **Step 1: Add failing describe-output assertions**

Append to `tests/test_describe_position_sizing.py`:

```python
def test_describe_position_sizing_outputs_completed_06_sections():
    completed = subprocess.run(
        [sys.executable, "scripts/describe_position_sizing.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["required_inputs"][0] == "account_equity"
    assert payload["decision_steps"][0] == "read_account_equity_and_available_margin"
    assert payload["log_fields"][-1] == "decision"
    assert payload["state_policy"]["PROBE"] == "probe_size"
    assert payload["volatility_factors"]["HIGH"] == 0.5
    assert payload["no_trade_policy"] == "return NO_TRADE; never inflate or promote"
    assert payload["sample"]["probe"]["decision"] == "PROBE"
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_describe_position_sizing.py -q`

Expected: FAIL because completed 06 sections are missing from JSON.

- [ ] **Step 3: Update describe script imports and payload**

Modify `scripts/describe_position_sizing.py` imports:

```python
from src.risk.position_sizer import (
    ENTRY_MODE_MULTIPLIERS,
    MARKET_TIER_MULTIPLIERS,
    POSITION_DECISION_STEPS,
    POSITION_LOG_FIELDS,
    POSITION_REQUIRED_INPUTS,
    STATE_POSITION_POLICY,
    VOLATILITY_FACTORS,
    PositionSizingInput,
    calculate_position_size,
)
```

Update `_sample` to use `entry_mode=signal_type` and return:

```python
return {
    "decision": result.decision,
    "notional": result.notional,
    "quantity": result.quantity,
    "required_margin": result.required_margin,
}
```

Update payload:

```python
payload = {
    "formula": "position_notional = risk_amount / stop_pct",
    "signal_multipliers": ENTRY_MODE_MULTIPLIERS,
    "entry_mode_multipliers": ENTRY_MODE_MULTIPLIERS,
    "market_tier_multipliers": MARKET_TIER_MULTIPLIERS,
    "volatility_factors": VOLATILITY_FACTORS,
    "minimum_notional_policy": "reject; never inflate",
    "no_trade_policy": "return NO_TRADE; never inflate or promote",
    "required_inputs": POSITION_REQUIRED_INPUTS,
    "decision_steps": POSITION_DECISION_STEPS,
    "log_fields": POSITION_LOG_FIELDS,
    "state_policy": STATE_POSITION_POLICY,
    "sample": {"direct": _sample("DIRECT"), "probe": _sample("PROBE")},
}
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_position_sizing.py tests/test_describe_position_sizing.py -q`

Expected: PASS.

---

### Task 5: Scaffold Sync and Verification

**Files:**

- Modify: `scripts/scaffold_ai300_framework.py`

- [ ] **Step 1: Sync scaffold templates**

Copy final contents of these files into the matching templates in `scripts/scaffold_ai300_framework.py`:

- `src/risk/position_sizer.py`
- `scripts/describe_position_sizing.py`
- `tests/test_position_sizing.py`
- `tests/test_describe_position_sizing.py`

- [ ] **Step 2: Run targeted tests**

Run: `pytest tests/test_position_sizing.py tests/test_describe_position_sizing.py tests/test_framework_scaffold.py -q`

Expected: PASS.

- [ ] **Step 3: Run full verification**

Run:

```bash
pytest -q
python -m compileall src scripts tests
python scripts/describe_position_sizing.py
git diff -- src/api/binance_client.py
```

Expected: all tests pass, compile succeeds, describe JSON includes completed 06 sections, and Binance diff has no output.

- [ ] **Step 4: Clean generated caches**

Run:

```powershell
$root=(Resolve-Path '.').Path; $targets=Get-ChildItem -Path . -Recurse -Directory -Filter '__pycache__' | Where-Object { $_.FullName.StartsWith($root) }; foreach($target in $targets){ Remove-Item -LiteralPath $target.FullName -Recurse -Force }; Get-ChildItem -Path . -Recurse -Directory -Filter '__pycache__' | Select-Object -ExpandProperty FullName
```

Expected: no remaining `__pycache__` directories in the workspace.

---

## Self-Review

- Spec coverage: covers direct/probe/no-trade, risk-derived standard notional, stop linkage, ATR-derived input contract, tier factors, account and portfolio factors, exposure gates, minimum notional, minimum margin, leverage, precision flooring, probe/direct upgrade separation via no promotion, state-machine policy, execution boundary, audit log fields, and forbidden floor/promotion behavior.
- Placeholder scan: no `TBD`, `TODO`, `implement later`, or unspecified test steps.
- Type consistency: `PositionSizingInput`, `PositionSizingResult`, `calculate_position_size`, `normalize_entry_mode`, `ENTRY_MODE_MULTIPLIERS`, `POSITION_REQUIRED_INPUTS`, and `POSITION_LOG_FIELDS` are named consistently across tasks.
