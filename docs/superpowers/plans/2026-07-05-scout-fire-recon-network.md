# Scout Fire Recon Network Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade DRY-RUN SCOUT from single-symbol micro testing into a disciplined multi-mission reconnaissance network.

**Architecture:** Keep main `PROBE/DIRECT` and live-order semantics unchanged. Extend only the dry-run near-miss and `scout_micro` paper path with mission tagging, per-mission entry criteria, symbol/direction cooldowns, and a small configurable symbol matrix.

**Tech Stack:** Python, pytest, JSON config, existing `PaperTradingLedger`, existing dry-run JSONL audit files.

## Global Constraints

- This is crypto strategy research: do not introduce lookahead bias, future candle data, repaint signals, or same-bar live fill assumptions.
- Entry and exit logic must stay live-executable with explicit fee, slippage, latency, and candle-close assumptions.
- This task is DRY-RUN only; do not modify real exchange submission semantics.
- Strategy hypothesis: SCOUT should collect isolated evidence for separate missions instead of retesting generic RR-gap noise.
- Expected market regime: sparse main entries with many high-score near-misses blocked by RR, LONG offset, watch-only, or blacklist rules.
- Failure mode: SCOUT over-expansion can collect correlated noise; cooldowns and mission criteria must keep samples independent.
- Verification command: `pytest tests/test_entry_chain_config.py tests/test_dry_run_configs.py tests/test_live_dry_run.py -q`

---

### Task 1: Add SCOUT Mission Config

**Files:**
- Modify: `src/signals/entry_chain_config.py`
- Modify: `configs/entry_chain.dry_run_fib_pa_v1.json`
- Test: `tests/test_entry_chain_config.py`
- Test: `tests/test_dry_run_configs.py`

**Interfaces:**
- Consumes: `EntryChainConfig.from_mapping(data)`
- Produces: parsed config fields for `scout_micro_rr_gap_block_symbols`, `scout_micro_targeted_long_symbols`, `scout_micro_scout_only_symbols`, `scout_micro_same_side_cooldown_hours`, `scout_micro_initial_stop_cooldown_hours`, and per-mission thresholds.

- [ ] **Step 1: Write failing config tests**

Add assertions that new fields parse and normalize symbols:

```python
assert config.scout_micro_rr_gap_block_symbols == ("XLMUSDT",)
assert config.scout_micro_targeted_long_symbols == ("CCUSDT",)
assert config.scout_micro_scout_only_symbols == ("XMRUSDT", "ZECUSDT")
assert config.scout_micro_same_side_cooldown_hours == 2
assert config.scout_micro_initial_stop_cooldown_hours == 6
```

- [ ] **Step 2: Implement dataclass fields**

Add defaults in `EntryChainConfig` and normalize the new symbol tuple fields in `from_mapping()`.

- [ ] **Step 3: Update fib/pa dry-run config**

Set:

```json
"scout_micro_symbols": ["XLMUSDT", "CCUSDT", "XMRUSDT", "ZECUSDT"],
"scout_micro_rr_gap_block_symbols": ["XLMUSDT"],
"scout_micro_targeted_long_symbols": ["CCUSDT"],
"scout_micro_scout_only_symbols": ["XMRUSDT", "ZECUSDT"],
"scout_micro_same_side_cooldown_hours": 2,
"scout_micro_initial_stop_cooldown_hours": 6
```

- [ ] **Step 4: Verify config tests**

Run: `pytest tests/test_entry_chain_config.py tests/test_dry_run_configs.py -q`

Expected: PASS.

### Task 2: Decouple Targeted LONG Near-Miss Recording

**Files:**
- Modify: `scripts/run_live_dry_run.py`
- Test: `tests/test_live_dry_run.py`

**Interfaces:**
- Consumes: `build_near_miss_payload(decision_payload, min_score=...)`
- Produces: targeted LONG near-misses at `score >= 80` even when global `min_score` is higher.

- [ ] **Step 1: Add failing tests**

Add a test where a `WATCH` LONG decision has `score=80.5`, `min_score=82`, reason `SIDE_THRESHOLD_OFFSET_LONG_10.00`, and PA `18`; expect a payload with `TARGETED_LONG_OFFSET`.

- [ ] **Step 2: Implement mission-aware score gate**

Change `build_near_miss_payload()` so tradable actions are still ignored, but a targeted LONG candidate can bypass the global min score using the existing targeted rule threshold.

- [ ] **Step 3: Verify near-miss tests**

Run: `pytest tests/test_live_dry_run.py::test_build_near_miss_payload_records_targeted_long_below_global_min_score -q`

Expected: PASS.

### Task 3: Add SCOUT Mission Eligibility And Cooldowns

**Files:**
- Modify: `scripts/run_live_dry_run.py`
- Test: `tests/test_live_dry_run.py`

**Interfaces:**
- Consumes: `should_open_scout_micro(...)` and `PaperTradingLedger.recent_closed_trades(...)`
- Produces: mission-gated SCOUT opens with reasons `SCOUT_MISSION_*`, no RR-gap XLM opens, 2h same-side cooldown, and 6h post-initial-stop cooldown.

- [ ] **Step 1: Add failing tests**

Add tests for:
- XLM RR-gap near-miss returns `False`.
- XLM non-RR high-score near-miss returns `True`.
- CC targeted LONG with score `82`, PA `18`, RR `3` returns `True`.
- CC targeted LONG with RR `2` returns `False`.
- XMR/ZEC scout-only high-score signal with PROBE component minima returns `True`.
- same symbol/same side closed trade within 2h returns `False`.
- initial stop within 6h returns `False`.

- [ ] **Step 2: Implement helpers**

Add helper functions in `scripts/run_live_dry_run.py`:

```python
def scout_micro_mission(symbol, near_miss, config) -> str | None: ...
def _scout_micro_rr_gap_blocked(symbol, near_miss, config) -> bool: ...
def _scout_micro_cooldown_active(symbol, side, config, scout_paper, timestamp) -> str | None: ...
```

- [ ] **Step 3: Include mission in payloads**

Add `scout_mission` to SCOUT decision payloads and prefix reasons with the mission-specific reason.

- [ ] **Step 4: Verify helper tests**

Run: `pytest tests/test_live_dry_run.py -q`

Expected: PASS.

### Task 4: Smoke Verification

**Files:**
- No new code files.

**Interfaces:**
- Consumes: all previous tasks.
- Produces: verified DRY-RUN smoke behavior.

- [ ] **Step 1: Run targeted tests**

Run: `pytest tests/test_entry_chain_config.py tests/test_dry_run_configs.py tests/test_live_dry_run.py -q`

Expected: PASS.

- [ ] **Step 2: Run synthetic smoke**

Run: `python scripts/run_live_dry_run.py --config configs/entry_chain.dry_run_fib_pa_v1.json --target-tier aggressive --market-data-source synthetic --once --output-dir reports/dry_run/scout_fire_recon_smoke --symbols XLMUSDT,CCUSDT,XMRUSDT,ZECUSDT --near-miss-min-score 82`

Expected: command exits `0`, main `orders_submitted=0`, and any SCOUT files remain under `scout_micro/`.

- [ ] **Step 3: Clean smoke output and inspect diff**

Run: `Remove-Item -LiteralPath "D:\AIDCA\AI300\reports\dry_run\scout_fire_recon_smoke" -Recurse -Force` and `git diff --check`.

Expected: no whitespace errors except possible Windows line-ending warnings.
