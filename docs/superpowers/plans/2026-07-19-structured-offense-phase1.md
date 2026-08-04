# Structured Offense Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add dry-run observability and controlled SCOUT missions needed to move from coarse aggressive mode to structured offense experiments.

**Architecture:** Keep live exchange mutation untouched. Add a static net beta observation model, add parallel paper A/B ledgers for legacy versus trend_capture exits, and replace the broad SCOUT `NON_RR_HIGH_SCORE` mission with named hypothesis-driven missions.

**Tech Stack:** Python 3, dataclasses, JSONL paper ledgers, pytest, existing `EntryChainConfig`, `PaperTradingLedger`, and `run_live_dry_run.py`.

## Global Constraints

- This is dry-run / paper infrastructure only; do not submit real orders or touch exchange mutation logic.
- Do not introduce lookahead bias or same-bar optimism into live decision logic.
- `trend_capture` A/B must use the exact same entry signal stream as the main paper ledger, with independent state dirs.
- Net beta is observational only in this phase; it must not block entries.
- SCOUT mission changes must be explicit and testable; remove broad `NON_RR_HIGH_SCORE` opening behavior.
- Preserve existing fee, slippage, TP ladder, and paper ledger accounting.

---

### Task 1: Static Net Beta Observation Model

**Files:**
- Create: `src/risk/net_beta_exposure_model.py`
- Create: `tests/test_net_beta_exposure_model.py`
- Modify: `scripts/run_live_dry_run.py`
- Modify: `tests/test_live_dry_run.py`

**Interfaces:**
- Produces: `compute_net_beta_exposure(open_positions, equity=10000.0) -> float`
- Produces: `net_beta_exposure_within_limit(value: float, limit: float) -> bool`
- Produces: `NET_BETA_EXPOSURE_CAP_PCT`
- Consumes: `PaperTradingLedger.positions` mapping values with `symbol`, `side`, `notional`, and `remaining_fraction`.

- [ ] **Step 1: Add failing tests for signed beta exposure**

Add tests that build simple open-position objects or mappings:

```python
def test_compute_net_beta_exposure_sums_signed_remaining_notional():
    positions = {
        "BTCUSDT": {"symbol": "BTCUSDT", "side": "LONG", "notional": 1000.0, "remaining_fraction": 1.0},
        "HYPEUSDT": {"symbol": "HYPEUSDT", "side": "SHORT", "notional": 500.0, "remaining_fraction": 0.5},
    }
    assert compute_net_beta_exposure(positions, equity=10_000.0) == -0.005
```

- [ ] **Step 2: Implement static model**

Create a static beta table by category:

```python
STATIC_BTC_BETA = {
    "BTCUSDT": 1.0,
    "ETHUSDT": 1.05,
    "BNBUSDT": 0.90,
    "SOLUSDT": 1.25,
    "ADAUSDT": 1.20,
    "LINKUSDT": 1.15,
    "DOGEUSDT": 1.30,
    "XRPUSDT": 1.10,
    "TRXUSDT": 0.85,
    "BCHUSDT": 1.10,
    "XLMUSDT": 1.15,
    "XMRUSDT": 0.75,
    "ZECUSDT": 1.35,
    "TONUSDT": 1.05,
    "HYPEUSDT": 1.80,
    "LABUSDT": 1.80,
    "CCUSDT": 1.80,
}
DEFAULT_BTC_BETA = 1.20
NET_BETA_EXPOSURE_CAP_PCT = 0.50
```

- [ ] **Step 3: Wire summary observation**

In `run_live_dry_run.py`, import the model and change `dry_run_assumptions()` / `portfolio_exposure_snapshot()` so summary outputs:

```json
"net_beta_exposure_model": "static_v1_observation_only"
```

and current beta values instead of `null`.

- [ ] **Step 4: Verify**

Run:

```bash
pytest tests/test_net_beta_exposure_model.py tests/test_live_dry_run.py -q
```

Expected: pass.

---

### Task 2: Main Paper Exit A/B Ledgers

**Files:**
- Modify: `scripts/run_live_dry_run.py`
- Modify: `tests/test_live_dry_run.py`
- Optionally create: `tests/test_paper_exit_ab.py`

**Interfaces:**
- Produces: `build_paper_exit_ab_ledgers(output_dir, state_dir) -> dict[str, PaperTradingLedger]`
- Produces: `paper_exit_ab_summary(ab_ledgers, timestamp) -> dict`
- Produces: `write_paper_summary_with_ab(output_dir, paper, ab_ledgers, timestamp) -> None`

- [ ] **Step 1: Add failing tests for A/B summary**

Test that a dry-run cycle writes `paper_summary.json` with:

```json
"ab_ledger": {
  "legacy": {"exit_mode": "legacy", ...},
  "trend_capture": {"exit_mode": "trend_capture", ...}
}
```

- [ ] **Step 2: Instantiate independent ledgers**

When `output_dir` changes, create:

```python
paper_exit_ab_ledgers = {
    "legacy": PaperTradingLedger(output_dir / "paper_ab" / "legacy", state_dir=paper_state_dir / "paper_ab" / "legacy", exit_config=PaperExitConfig(mode="legacy")),
    "trend_capture": PaperTradingLedger(output_dir / "paper_ab" / "trend_capture", state_dir=paper_state_dir / "paper_ab" / "trend_capture", exit_config=PaperExitConfig(mode="trend_capture", trend_trigger_r=config.paper_exit_trend_trigger_r, trailing_r_mult=config.paper_exit_trailing_r_mult)),
}
```

- [ ] **Step 3: Feed the same main signal stream**

After `paper.on_decision(...)`, call `on_decision(...)` on both A/B ledgers with the same `decision_payload`, `draft_payload`, `kline`, and `timestamp`.

- [ ] **Step 4: Add A/B summary to main paper summary**

At cycle end, overwrite the main `paper_summary.json` with `paper.summary(...)` plus `ab_ledger`.

- [ ] **Step 5: Verify**

Run:

```bash
pytest tests/test_live_dry_run.py -q
```

Expected: pass.

---

### Task 3: Structured SCOUT Missions

**Files:**
- Modify: `src/signals/entry_chain_config.py`
- Modify: `scripts/run_live_dry_run.py`
- Modify: `configs/entry_chain.dry_run_fib_pa_v1.json`
- Modify: `tests/test_entry_chain_config.py`
- Modify: `tests/test_dry_run_configs.py`
- Modify: `tests/test_live_dry_run.py`

**Interfaces:**
- Produces mission: `HIGH_SCORE_LONG_OFFSET_PROBE`
- Produces mission: `FIB_CONTINUATION_SCOUT`
- Produces mission: `WATCH_ONLY_SYMBOL_PROMOTION_TEST`
- Removes broad mission: `NON_RR_HIGH_SCORE`

- [ ] **Step 1: Add config fields**

Add fields with defaults:

```python
scout_micro_high_score_long_offset_min_score: float = 85.0
scout_micro_high_score_long_offset_min_pa_score: float = 18.0
scout_micro_high_score_long_offset_min_fib_score: float = 15.0
scout_micro_high_score_long_offset_min_cvd_score: float = 14.0
scout_micro_high_score_long_offset_min_rr_score: float = 2.0
scout_micro_fib_continuation_min_score: float = 82.0
scout_micro_fib_continuation_min_ema_score: float = 16.0
scout_micro_fib_continuation_min_cvd_score: float = 14.0
scout_micro_fib_continuation_min_pa_score: float = 18.0
scout_micro_watch_only_promotion_min_score: float = 87.0
```

- [ ] **Step 2: Replace mission routing**

Change `scout_micro_mission()` order to:

```python
HIGH_SCORE_LONG_OFFSET_PROBE
FIB_CONTINUATION_SCOUT
WATCH_ONLY_SYMBOL_PROMOTION_TEST
SCOUT_ONLY_HIGH_SCORE
```

Do not return `NON_RR_HIGH_SCORE`.

- [ ] **Step 3: Add mission helpers**

Implement helper predicates using only current candle decision payload fields:

```python
_high_score_long_offset_probe_eligible(...)
_fib_continuation_scout_eligible(...)
_watch_only_symbol_promotion_eligible(...)
```

- [ ] **Step 4: Configure dry-run mission pools**

Update `configs/entry_chain.dry_run_fib_pa_v1.json`:

```json
"scout_micro_symbols": ["XLMUSDT", "CCUSDT", "XMRUSDT", "ADAUSDT", "LINKUSDT", "LABUSDT", "HYPEUSDT", "DOGEUSDT", "SOLUSDT", "BNBUSDT", "BCHUSDT"],
"scout_micro_targeted_long_symbols": ["LINKUSDT", "LABUSDT", "HYPEUSDT", "DOGEUSDT", "CCUSDT", "XLMUSDT", "SOLUSDT", "BNBUSDT", "BCHUSDT"],
"scout_micro_scout_only_symbols": ["XMRUSDT", "ADAUSDT"]
```

- [ ] **Step 5: Verify**

Run:

```bash
pytest tests/test_entry_chain_config.py tests/test_dry_run_configs.py tests/test_live_dry_run.py -q
```

Expected: pass.

---

### Task 4: Focused Verification

**Files:**
- No new production files expected.

- [ ] **Step 1: Run targeted suite**

Run:

```bash
pytest tests/test_net_beta_exposure_model.py tests/test_paper_trading.py tests/test_live_dry_run.py tests/test_entry_chain_config.py tests/test_dry_run_configs.py -q
```

- [ ] **Step 2: Run one dry-run smoke test**

Run:

```bash
python scripts/run_live_dry_run.py --config configs/entry_chain.dry_run_fib_pa_v1.json --once --output-dir reports/dry_run/phase1-smoke --symbols BCHUSDT --market-data-source synthetic --target-tier aggressive
```

Expected:

```json
{"status": "dry_run_completed", "orders_submitted": 0}
```

- [ ] **Step 3: Inspect summary fields**

Verify `reports/dry_run/phase1-smoke/summary.json` contains static beta observation and `reports/dry_run/phase1-smoke/paper_summary.json` contains `ab_ledger`.

---

## Self-Review

Spec coverage:

- Task C static beta observation is covered by Task 1.
- Task E paper A/B ledger is covered by Task 2.
- SCOUT mission restructuring and `NON_RR_HIGH_SCORE` removal are covered by Task 3.
- Production live order mutation is deliberately out of scope.
- Rolling 30-day beta calculation, dynamic symbol panel, and new hard-block risk circuits are not included in Phase 1 because they require additional historical data and separate validation.

Placeholder scan: no TBD/TODO placeholders remain.

Type consistency: all new interfaces consume existing `PaperTradingLedger`, `EntryChainConfig`, and JSON summary patterns.
