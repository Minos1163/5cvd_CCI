# P0 Paper Stop Cooldown Observation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix dry-run paper data quality and immediate repeated-loss controls before judging strategy quality.

**Architecture:** Keep changes scoped to dry-run and paper observability. The paper ledger classifies stop exits from existing position state; the live dry-run runner applies paper-only post-decision controls before creating order drafts, so live execution code remains untouched.

**Tech Stack:** Python dataclasses, JSON/JSONL paper state, pytest.

---

## Files

- Modify: `src/observability/paper_trading.py` for stop subtypes and recent trade lookup.
- Modify: `scripts/run_live_dry_run.py` for dry-run decision post-processing.
- Modify: `src/signals/entry_chain_config.py` for observation/cooldown/weak-edge config knobs.
- Modify: `configs/entry_chain.dry_run_highest_win.json` to put `XLMUSDT` into observation mode.
- Modify tests in `tests/test_paper_trading.py`, `tests/test_entry_chain_config.py`, `tests/test_dry_run_configs.py`, and `tests/test_live_dry_run.py`.

## Tasks

### Task 1: Stop Subtype Classification

- [ ] Add failing tests that a pre-TP stop records `INITIAL_STOP_HIT` and a TP1-then-stop records `BREAKEVEN_STOP_HIT`.
- [ ] Implement minimal classification based on `position.tp_consumed`.
- [ ] Verify `pytest tests/test_paper_trading.py -q`.

### Task 2: Config Knobs

- [ ] Add config fields for `observation_only_symbols`, weak-edge score bounds, and rolling cooldown settings.
- [ ] Normalize symbol lists and update highest-win config with `XLMUSDT` in observation mode.
- [ ] Verify config tests.

### Task 3: Dry-Run Post-Decision Controls

- [ ] Add a small post-processor in `scripts/run_live_dry_run.py` that can cap DIRECT/PROBE to WATCH before draft creation.
- [ ] Implement observation-only cap, weak-edge DIRECT demotion without positive local paper history, and rolling 48h cooldown after two `INITIAL_STOP_HIT` closes.
- [ ] Verify no exchange mutation code exists and existing dry-run tests pass.

### Task 4: Full Verification

- [ ] Run focused pytest suite.
- [ ] Run dry-run healthcheck if available.
- [ ] Report exact files changed and verification results.

