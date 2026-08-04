# Trend Capture Exit Diagnostics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add dry-run-only support for testing "抓大趋势" exits by making TP1 breakeven behavior configurable and adding payoff-ratio diagnostics.

**Architecture:** Keep existing paper-trading behavior as the default. Add a small `PaperExitConfig` to `src/observability/paper_trading.py` so the dry-run runner can enable a conditional trend-capture trailing stop only for the isolated `scout_micro` ledger first. Add summary diagnostics that expose actual win/loss payoff ratio and breakeven-required payoff ratio, so future reports can judge whether exits are moving toward "let profits run".

**Tech Stack:** Python dataclasses, JSON config, pytest, existing dry-run runner and paper ledger.

## Global Constraints

- This is DRY-RUN strategy research; do not modify exchange submission or production live execution behavior.
- Do not increase leverage, position size, or max concurrency.
- Do not lower `SIDE_THRESHOLD_OFFSET_LONG_10.00` in this change.
- Do not loosen `FIB_EXTENSION_EXHAUSTION_BLOCK` in this change.
- Preserve legacy paper ledger behavior unless an explicit dry-run paper exit config enables the new mode.
- Strategy hypothesis: the recent 7-day negative expectancy is driven by "TP1 then immediate breakeven" capping winners while losers run to initial stop.
- Expected market regime: sparse signals with occasional trend continuation after TP1.
- Failure mode: trailing mode can hold remainder longer or give back more unrealized profit; therefore it must be tested first in SCOUT micro, not by increasing main-book risk.
- Verification command: `pytest tests/test_paper_trading.py tests/test_entry_chain_config.py tests/test_dry_run_configs.py tests/test_dry_run_summary.py tests/test_live_dry_run.py -q`.
- Keep changes surgical: no new dependencies, no broad refactors.

---

## File Structure

- Modify `src/observability/paper_trading.py`: add `PaperExitConfig`, optional trend-capture trailing stop, and payoff diagnostics in `paper_summary.json`.
- Modify `src/signals/entry_chain_config.py`: add dry-run paper exit config fields.
- Modify `configs/entry_chain.dry_run_fib_pa_v1.json`: keep main ledger legacy, enable trend-capture exit for `scout_micro` only.
- Modify `scripts/run_live_dry_run.py`: pass exit configs into main and scout `PaperTradingLedger`, and include assumptions in `summary.json`.
- Modify `tests/test_paper_trading.py`: cover default legacy breakeven and enabled trend-capture trailing behavior.
- Modify `tests/test_entry_chain_config.py`, `tests/test_dry_run_configs.py`, `tests/test_dry_run_summary.py`, `tests/test_live_dry_run.py`: cover config parsing and diagnostics.

---

### Task 1: Configurable Trend-Capture Exit In Paper Ledger

**Files:**
- Modify: `src/observability/paper_trading.py`
- Test: `tests/test_paper_trading.py`

**Interfaces:**
- Produces: `PaperExitConfig`
- `PaperTradingLedger(..., exit_config: PaperExitConfig | None = None)` defaults to legacy behavior.
- Summary gains:
  - `avg_win`
  - `avg_loss`
  - `actual_payoff_ratio`
  - `breakeven_payoff_ratio`
  - `payoff_ratio_health`
  - `exit_mode`

- [x] **Step 1: Add failing tests**

Add tests proving:

```python
from src.observability.paper_trading import PaperExitConfig, PaperTradingLedger


def test_paper_trading_ledger_defaults_to_legacy_breakeven_after_tp1(tmp_path):
    ledger = PaperTradingLedger(tmp_path)
    decision, draft = approved_decision()
    ledger.on_decision(symbol="SOLUSDT", decision_payload=decision, draft_payload=draft, kline={"close": 100, "high": 100, "low": 100}, timestamp=1000)
    ledger.on_decision(symbol="SOLUSDT", decision_payload={"action": "NO_TRADE"}, draft_payload={"approved": False}, kline={"close": 101.8, "high": 101.8, "low": 100.5}, timestamp=1900)
    assert round(ledger.positions["SOLUSDT"].stop_price, 4) == 100.1
```

and:

```python
def test_paper_trading_ledger_trend_capture_trails_after_trigger_r(tmp_path):
    ledger = PaperTradingLedger(
        tmp_path,
        exit_config=PaperExitConfig(mode="trend_capture", trend_trigger_r=1.5, trailing_r_mult=1.0),
    )
    decision, draft = approved_decision()
    ledger.on_decision(symbol="SOLUSDT", decision_payload=decision, draft_payload=draft, kline={"close": 100, "high": 100, "low": 100}, timestamp=1000)
    ledger.on_decision(symbol="SOLUSDT", decision_payload={"action": "NO_TRADE"}, draft_payload={"approved": False}, kline={"close": 102.8, "high": 102.8, "low": 101.6}, timestamp=1900)
    assert round(ledger.positions["SOLUSDT"].stop_price, 4) == 101.3
    rows = [json.loads(line) for line in (tmp_path / "paper_trades.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows[-1]["exit_mode"] == "trend_capture"
```

- [x] **Step 2: Run failing tests**

Run: `pytest tests/test_paper_trading.py::test_paper_trading_ledger_trend_capture_trails_after_trigger_r -q`
Expected: FAIL because `PaperExitConfig` does not exist.

- [x] **Step 3: Implement minimal paper exit config**

Add dataclass:

```python
@dataclass(frozen=True)
class PaperExitConfig:
    mode: str = "legacy"
    trend_trigger_r: float = 1.5
    trailing_r_mult: float = 1.0
```

Add `best_price` and `exit_mode` to `PaperPosition`, defaulting old loaded positions with `best_price=last_price` and `exit_mode="legacy"`.

After TP1:

```python
if self.exit_config.mode == "trend_capture":
    _apply_trend_capture_stop(position, self.exit_config)
else:
    position.stop_price = position.entry_price * (1.001 if position.side == "LONG" else 0.999)
```

The trend-capture helper derives initial R from TP1 distance:

```python
risk_distance = abs(position.tp_prices[0] - position.entry_price) / TP_LEVELS[0]
favorable_r = abs(position.best_price - position.entry_price) / risk_distance
if favorable_r < config.trend_trigger_r:
    breakeven stop
else:
    long trailing = best_price - risk_distance * trailing_r_mult
    short trailing = best_price + risk_distance * trailing_r_mult
```

- [x] **Step 4: Verify paper tests**

Run: `pytest tests/test_paper_trading.py -q`
Expected: PASS.

---

### Task 2: Dry-Run Config Wiring

**Files:**
- Modify: `src/signals/entry_chain_config.py`
- Modify: `configs/entry_chain.dry_run_fib_pa_v1.json`
- Modify: `scripts/run_live_dry_run.py`
- Test: `tests/test_entry_chain_config.py`
- Test: `tests/test_dry_run_configs.py`
- Test: `tests/test_live_dry_run.py`

**Interfaces:**
- `EntryChainConfig` gains:
  - `paper_exit_mode: str = "legacy"`
  - `paper_exit_trend_trigger_r: float = 1.5`
  - `paper_exit_trailing_r_mult: float = 1.0`
  - `scout_micro_exit_mode: str = "legacy"`
  - `scout_micro_exit_trend_trigger_r: float = 1.5`
  - `scout_micro_exit_trailing_r_mult: float = 1.0`
- `scripts.run_live_dry_run.paper_exit_config(config, scout: bool) -> PaperExitConfig`

- [x] **Step 1: Add config tests**

Add assertions:

```python
assert config.paper_exit_mode == "legacy"
assert config.scout_micro_exit_mode == "trend_capture"
assert config.scout_micro_exit_trend_trigger_r == 1.5
assert config.scout_micro_exit_trailing_r_mult == 1.0
```

- [x] **Step 2: Implement config fields**

Add the six fields to `EntryChainConfig`.

- [x] **Step 3: Update dry-run Fib/PA config**

Set:

```json
"paper_exit_mode": "legacy",
"paper_exit_trend_trigger_r": 1.5,
"paper_exit_trailing_r_mult": 1.0,
"scout_micro_exit_mode": "trend_capture",
"scout_micro_exit_trend_trigger_r": 1.5,
"scout_micro_exit_trailing_r_mult": 1.0
```

- [x] **Step 4: Wire ledgers**

When constructing ledgers in `scripts/run_live_dry_run.py`:

```python
paper = PaperTradingLedger(output_dir, state_dir=paper_state_dir, exit_config=paper_exit_config(config, scout=False))
scout_paper = PaperTradingLedger(output_dir / "scout_micro", state_dir=paper_state_dir / "scout_micro", exit_config=paper_exit_config(config, scout=True))
```

- [x] **Step 5: Verify config and runner tests**

Run: `pytest tests/test_entry_chain_config.py tests/test_dry_run_configs.py tests/test_live_dry_run.py -q`
Expected: PASS.

---

### Task 3: Payoff Diagnostics In Summary

**Files:**
- Modify: `src/observability/paper_trading.py`
- Modify: `scripts/run_live_dry_run.py`
- Modify: `tests/test_paper_trading.py`
- Modify: `tests/test_dry_run_summary.py`
- Modify: `tests/test_live_dry_run.py`

**Interfaces:**
- `paper_summary.json` includes payoff diagnostics from Task 1.
- `summary.json["dry_run_assumptions"]` includes:
  - `paper_exit_mode`
  - `paper_exit_trend_trigger_r`
  - `paper_exit_trailing_r_mult`
  - `scout_micro_exit_mode`
  - `scout_micro_exit_trend_trigger_r`
  - `scout_micro_exit_trailing_r_mult`

- [x] **Step 1: Add payoff summary test**

Add a test that creates one winning and one losing closed trade, then asserts:

```python
assert "actual_payoff_ratio" in summary
assert "breakeven_payoff_ratio" in summary
assert "payoff_ratio_health" in summary
```

- [x] **Step 2: Implement diagnostics**

Compute:

```python
avg_win = gross_profit / len(wins) if wins else 0.0
avg_loss = gross_loss / len(losses) if losses else 0.0
actual_payoff_ratio = avg_win / avg_loss if avg_loss > 0 else 0.0
breakeven_payoff_ratio = (1 - win_rate) / win_rate if win_rate > 0 else 0.0
payoff_ratio_health = actual_payoff_ratio / breakeven_payoff_ratio if breakeven_payoff_ratio > 0 else 0.0
```

- [x] **Step 3: Extend assumptions**

Add the six exit config fields to `dry_run_assumptions(config)`.

- [x] **Step 4: Verify**

Run: `pytest tests/test_paper_trading.py tests/test_dry_run_summary.py tests/test_live_dry_run.py -q`
Expected: PASS.

---

### Task 4: Final Verification

**Files:**
- No additional files.

- [x] **Step 1: Run focused suite**

Run:

```powershell
pytest tests/test_paper_trading.py tests/test_entry_chain_config.py tests/test_dry_run_configs.py tests/test_dry_run_summary.py tests/test_live_dry_run.py -q
```

Expected: PASS.

- [x] **Step 2: One-shot smoke**

Run:

```powershell
python scripts/run_live_dry_run.py --config configs/entry_chain.dry_run_fib_pa_v1.json --target-tier aggressive --market-data-source synthetic --once --output-dir tmp_trend_capture_exit_smoke --symbols XMRUSDT --near-miss-min-score 0
```

Expected:

```text
summary.json dry_run_assumptions shows scout_micro_exit_mode=trend_capture
paper_summary.json and scout_micro/paper_summary.json include actual_payoff_ratio and payoff_ratio_health
```

- [x] **Step 3: Clean smoke output**

Remove only `tmp_trend_capture_exit_smoke` after verifying it is inside the workspace.
