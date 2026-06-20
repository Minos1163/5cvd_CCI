# Paper Trading Ledger Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a dry-run-only paper trading ledger that records simulated positions, opens, exits, equity, and summary metrics.

**Architecture:** Keep the ledger isolated under observability so it cannot mutate exchange state. The dry-run runner feeds each cycle's decision, order draft, and completed kline snapshot into the ledger; the ledger writes append-only trade events and JSON snapshots. Exits are evaluated only from already fetched completed kline high/low/close data.

**Tech Stack:** Python stdlib JSON/dataclasses, existing dry-run runner, pytest.

---

### Task 1: Paper Ledger Model

**Files:**
- Create: `src/observability/paper_trading.py`
- Test: `tests/test_paper_trading.py`

- [ ] Define `PaperTradingLedger` with `on_decision(symbol, decision_payload, draft_payload, kline, timestamp)`.
- [ ] Persist `paper_positions.json`, `paper_trades.jsonl`, `paper_equity.json`, and `paper_summary.json`.
- [ ] Simulate entry only when order draft is approved.
- [ ] Simulate one active position per symbol.
- [ ] Use conservative exit ordering: stop first if TP and SL both hit in the same completed candle.
- [ ] Compute realized/unrealized PnL, win rate, return, max drawdown, profit factor, and trade count.

### Task 2: Dry-Run Integration

**Files:**
- Modify: `scripts/run_live_dry_run.py`
- Test: `tests/test_live_dry_run.py`

- [ ] Create ledger alongside `DecisionAuditWriter`.
- [ ] Feed each symbol's decision, draft, price kline, and timestamp into the ledger.
- [ ] Add runtime log lines summarizing paper state.
- [ ] Preserve `orders_submitted = 0`.

### Task 3: Verification

**Files:**
- Modify: `tests/test_live_dry_run.py`
- Modify: `tests/test_paper_trading.py`

- [ ] Verify one-shot dry-run creates all four paper files.
- [ ] Verify approved draft creates an open paper position.
- [ ] Verify later kline can close position and write a trade event.
- [ ] Verify no exchange mutation tokens are introduced.

