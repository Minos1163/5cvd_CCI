# Scout Micro And Probe Quality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the low-quality PROBE backdoor while adding an isolated XLMUSDT SCOUT micro paper ledger for dry-run offense experiments.

**Architecture:** Keep PROBE/DIRECT live-order semantics unchanged and add offense exploration only inside the dry-run runner. Tighten `check_probe_conditions()` with configurable quality gates, enrich near-miss records with targeted LONG tags, and feed eligible XLMUSDT near-misses into a separate `scout_micro/` `PaperTradingLedger` using 50 USDT notional at 1x leverage.

**Tech Stack:** Python, pytest, JSON config, existing `PaperTradingLedger`, existing dry-run audit JSONL files.

## Global Constraints

- This is crypto strategy research: do not introduce lookahead bias, future candle data, repaint signals, or same-bar live fill assumptions.
- Entry and exit logic must stay live-executable with explicit fee, slippage, latency, and candle-close assumptions.
- This task is DRY-RUN only; do not modify real exchange submission semantics.
- Strategy hypothesis: low-score PROBE trades without either EMA trend context or CCI momentum are low-quality cost/time drains.
- Expected market regime: mixed or choppy markets where strict main entries remain sparse and SCOUT collects data for expansion candidates.
- Failure mode: over-tightening may reduce main-trade count further; SCOUT micro may collect too few samples when data health is degraded.
- Verification command: `pytest tests/test_entry_chain_probe_conditions.py tests/test_entry_chain_config.py tests/test_dry_run_configs.py tests/test_live_dry_run.py -q`

---

### Task 1: Tighten PROBE Quality Gates

**Files:**
- Modify: `src/signals/entry_chain.py`
- Modify: `configs/entry_chain.dry_run_fib_pa_v1.json`
- Test: `tests/test_entry_chain_probe_conditions.py`
- Test: `tests/test_dry_run_configs.py`

**Interfaces:**
- Consumes: `check_probe_conditions(score, side, component_points, rr_detail, config) -> tuple[bool, str]`
- Produces: two new rejection reasons: `PROBE_BELOW_TREND_OR_CCI_QUALITY_GATE` and `PROBE_LOW_SCORE_QUALITY_VETO`

- [ ] **Step 1: Add failing tests for the quality gate**

Add tests that prove a PROBE is rejected when both trend and momentum are weak, and when a low score lacks quality compensation.

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_entry_chain_probe_conditions.py -q`

Expected: FAIL because the new reasons are not implemented.

- [ ] **Step 3: Implement the quality gate**

Read thresholds from `probe_conditions` with these defaults:

```python
trend_or_cci_min_ema_score = float(config.get("trend_or_cci_min_ema_score", 10.0))
trend_or_cci_min_cci_score = float(config.get("trend_or_cci_min_cci_score", 9.0))
low_score_quality_veto_score = float(config.get("low_score_quality_veto_score", 75.0))
low_score_quality_min_ema_score = float(config.get("low_score_quality_min_ema_score", 10.0))
low_score_quality_min_cci_score = float(config.get("low_score_quality_min_cci_score", 7.0))
```

Reject if `trend_ema_context < 10` and `cci_momentum_quality < 9`; reject low-score PROBE if `score < 75` and either EMA `< 10` or CCI `< 7`.

- [ ] **Step 4: Add config transparency**

Add the five threshold keys to `configs/entry_chain.dry_run_fib_pa_v1.json` under `probe_conditions`, and update `tests/test_dry_run_configs.py`.

- [ ] **Step 5: Verify**

Run: `pytest tests/test_entry_chain_probe_conditions.py tests/test_dry_run_configs.py -q`

Expected: PASS.

### Task 2: Add Targeted LONG Near-Miss Tags

**Files:**
- Modify: `scripts/run_live_dry_run.py`
- Test: `tests/test_live_dry_run.py`

**Interfaces:**
- Consumes: `build_near_miss_payload(decision_payload, min_score=...)`
- Produces: `targeted_long_offset: true` and `scout_tags: ["TARGETED_LONG_OFFSET"]` on qualifying near-misses

- [ ] **Step 1: Add failing near-miss tests**

Test that a WATCH/NO_TRADE LONG signal with reason `SIDE_THRESHOLD_OFFSET_LONG_10.00`, score `>= 80`, and `price_action_structure >= 18` receives the targeted tag.

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_live_dry_run.py::test_build_near_miss_payload_tags_targeted_long_offset_candidate -q`

Expected: FAIL because the tag is absent.

- [ ] **Step 3: Implement tagging**

Add a small helper in `scripts/run_live_dry_run.py` that checks reason, side, score, and PA points after the base near-miss payload is built.

- [ ] **Step 4: Verify**

Run: `pytest tests/test_live_dry_run.py::test_build_near_miss_payload_tags_targeted_long_offset_candidate tests/test_live_dry_run.py::test_build_near_miss_payload_does_not_tag_short_or_weak_pa_offset -q`

Expected: PASS.

### Task 3: Add Isolated XLMUSDT SCOUT Micro Paper Ledger

**Files:**
- Modify: `src/signals/entry_chain_config.py`
- Modify: `configs/entry_chain.dry_run_fib_pa_v1.json`
- Modify: `scripts/run_live_dry_run.py`
- Test: `tests/test_entry_chain_config.py`
- Test: `tests/test_dry_run_configs.py`
- Test: `tests/test_live_dry_run.py`

**Interfaces:**
- Consumes: `near_miss` payloads and existing `PaperTradingLedger`
- Produces: independent `scout_micro/paper_trades.jsonl`, `scout_micro/paper_positions.json`, `scout_micro/paper_summary.json`, and `scout_micro/paper_equity.json`

- [ ] **Step 1: Add config tests**

Add `scout_micro_symbols`, `scout_micro_min_score`, `scout_micro_notional`, and `scout_micro_leverage` parsing assertions. Configure `XLMUSDT` as the first scout micro symbol while keeping it observation-only for the main ledger.

- [ ] **Step 2: Add helper tests**

Test that SCOUT micro opens are blocked when `data_health != "OK"`, and that a qualifying XLM near-miss builds an approved 50 USDT 1x draft.

- [ ] **Step 3: Implement config fields**

Add dataclass fields:

```python
scout_micro_symbols: tuple[str, ...] = ()
scout_micro_min_score: float = 82.0
scout_micro_notional: float = 50.0
scout_micro_leverage: int = 1
```

Normalize `scout_micro_symbols` in `EntryChainConfig.from_mapping()`.

- [ ] **Step 4: Implement dry-run SCOUT helpers**

Add helper functions in `scripts/run_live_dry_run.py`:

```python
def should_open_scout_micro(...): ...
def build_scout_micro_payloads(...): ...
def update_scout_micro_ledger(...): ...
```

The helper opens only when symbol is configured, data health is OK, a near-miss exists, score is at least `scout_micro_min_score`, intended side is LONG/SHORT, and no scout position is already open. Existing scout positions still receive kline updates each cycle.

- [ ] **Step 5: Wire the helper into the run loop**

Instantiate `PaperTradingLedger(output_dir / "scout_micro", state_dir=resolve_paper_state_dir(args) / "scout_micro")` beside the main paper ledger and call the SCOUT helper after main paper handling.

- [ ] **Step 6: Verify**

Run: `pytest tests/test_entry_chain_config.py tests/test_dry_run_configs.py tests/test_live_dry_run.py -q`

Expected: PASS.

### Task 4: End-To-End Verification

**Files:**
- No new files.

**Interfaces:**
- Consumes: all previous tasks.
- Produces: test evidence and a dry-run smoke artifact.

- [ ] **Step 1: Run targeted full test set**

Run: `pytest tests/test_entry_chain_probe_conditions.py tests/test_entry_chain_config.py tests/test_dry_run_configs.py tests/test_live_dry_run.py -q`

Expected: PASS.

- [ ] **Step 2: Run a synthetic XLM smoke scan**

Run: `python scripts/run_live_dry_run.py --config configs/entry_chain.dry_run_fib_pa_v1.json --target-tier aggressive --market-data-source synthetic --once --output-dir reports/dry_run/scout_micro_smoke --symbols XLMUSDT --near-miss-min-score 0`

Expected: command exits `0`, main `orders_submitted` remains `0`, and SCOUT artifacts exist under `reports/dry_run/scout_micro_smoke/scout_micro/`.

- [ ] **Step 3: Inspect git diff**

Run: `git diff --stat && git diff --check`

Expected: no whitespace errors; changed files are limited to the plan, config, entry-chain quality gate, dry-run runner, and tests.
