# P0 Paper Ledger Data Integrity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the P0 dry-run data integrity bugs before using paper results to judge strategy quality.

**Architecture:** Keep strategy logic changes minimal. Patch only the dry-run paper accounting path and the highest-win dry-run config. Paper state becomes persistent under a stable state directory, daily log folders remain diagnostic snapshots, TP levels become single-use, and PnL output explicitly labels notional and margin views.

**Tech Stack:** Python stdlib dataclasses/JSON/pathlib, existing dry-run runner, pytest.

---

## Files

- Modify: `src/observability/paper_trading.py`
- Modify: `scripts/run_live_dry_run.py`
- Modify: `configs/entry_chain.dry_run_highest_win.json`
- Modify: `tests/test_paper_trading.py`
- Modify: `tests/test_live_dry_run.py`
- Modify: `tests/test_dry_run_configs.py`

---

## Task 1: TP Level Consumption

- [ ] Add `tp_consumed: list[int]` to `PaperPosition`.
- [ ] On TP hit, skip already consumed indices and append the consumed index before writing the reduce/close event.
- [ ] Process at most one TP level per completed bar so logs map one bar to one paper exit action.
- [ ] Persist `tp_consumed` in `paper_positions.json` and load older positions with an empty list.
- [ ] Verify with a test that two later bars at TP1 price do not reduce 40%, then 40%, then 20% at the same TP1.

## Task 2: Persistent Paper State

- [ ] Add `state_dir` support to `PaperTradingLedger`.
- [ ] Store the canonical `paper_positions.json`, `paper_equity.json`, and `paper_trades.jsonl` under `state/paper` by default.
- [ ] Continue writing daily snapshots to the daily output directory for operator review.
- [ ] Add `--paper-state-dir` to `scripts/run_live_dry_run.py`.
- [ ] When omitted, derive the default state path from `--log-root`: `<log-root>/../state/paper`.
- [ ] Verify a second `PaperTradingLedger` instance with a different daily output directory can load the first day position/equity from the shared state dir.

## Task 3: PnL Labeling

- [ ] Keep current PnL as notional-based PnL for backward compatibility.
- [ ] Add explicit `notional_pnl`, `margin_pnl`, `margin_used`, and `pnl_accounting_mode` fields to trade events and summaries.
- [ ] Define `margin_pnl` as `notional_pnl * leverage` for reporting only.
- [ ] Do not change exchange mutation behavior or introduce live order submission.
- [ ] Verify paper trade rows and paper summary include the new fields.

## Task 4: ZEC Temporary Blacklist

- [ ] Add `ZECUSDT` to `blacklist_symbols` in `configs/entry_chain.dry_run_highest_win.json`.
- [ ] Keep `dry_run_symbols` unchanged so ZEC remains visible in the universe and can show blacklist rejection diagnostics.
- [ ] Update config tests to expect `("XRPUSDT", "ZECUSDT")`.

## Task 5: Verification

- [ ] Run `pytest tests/test_paper_trading.py -q`.
- [ ] Run `pytest tests/test_live_dry_run.py tests/test_dry_run_configs.py -q`.
- [ ] Run `python scripts/run_live_dry_run.py --config configs/entry_chain.dry_run_highest_win.json --target-tier aggressive --market-data-source synthetic --once --output-dir <tmp> --symbols ZECUSDT`.
- [ ] Confirm output has `orders_submitted=0`, paper files, and no exchange mutation calls.
