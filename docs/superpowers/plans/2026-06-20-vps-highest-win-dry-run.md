# VPS Highest-Win Dry-Run Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the current highest-win research entry configuration on VPS as a dry-run observer using live public market data, with zero exchange mutation.

**Architecture:** Keep the existing entry-chain decision and live order-draft adapter unchanged. Add a dry-run config alias for the current highest-win V5 combined entry profile, extend `scripts/run_live_dry_run.py` to build no-lookahead entry contexts from completed public Binance Futures klines, and update VPS docs/systemd to run that config in dry-run mode. The runner writes decisions and order drafts only; it never submits, cancels, amends, or syncs orders.

**Tech Stack:** Python stdlib, Binance Futures public klines, existing entry-chain modules, existing decision audit files, pytest.

---

## Safety Assumptions

- "实盘 DRY-RUN" means real public market data, no real orders.
- No API keys are required or stored.
- `orders_submitted` must remain `0`.
- `src/api/binance_client.py` must remain untouched.
- V7 time-reduce is not implemented in the live dry-run runner because the current runner observes entry decisions and order drafts only; exit lifecycle dry-run is a later module.

## Current Highest-Win Strategy

The highest latest-30D win-rate entry configuration is:

```text
configs/entry_chain.dry_run_v5_symbol_bucket_long_context.json
```

It produced `76.99%` win rate in V5 combined and remains the entry layer used by V6/V7. V6/V7 leverage/exit experiments do not change the entry config win-rate source.

## Tasks

### Task 1: Highest-Win Config Alias

**Files:**
- Create: `configs/entry_chain.dry_run_highest_win.json`
- Modify: `tests/test_dry_run_configs.py`

- [ ] Copy the V5 combined config exactly into `entry_chain.dry_run_highest_win.json`.
- [ ] Add a test that the highest-win config is parseable, disables probe, blacklists XRP, watch-only buckets ADA/XMR, and enables long context discounts.
- [ ] Verify with `pytest tests/test_dry_run_configs.py -q`.

### Task 2: Public Market Data Dry-Run Context

**Files:**
- Modify: `scripts/run_live_dry_run.py`
- Modify: `tests/test_live_dry_run.py`

- [ ] Add `--market-data-source synthetic|public-binance`, defaulting to `synthetic` for test stability.
- [ ] Add `--public-kline-limit`, default `240`, enough for EMA200 on 15m.
- [ ] Fetch public Binance Futures 15m/30m/1h/4h klines using stdlib `urllib`.
- [ ] Convert only closed candles into `BacktestBar`.
- [ ] Build `EntryChainContext` from completed bars using existing feature helpers.
- [ ] If public data is unavailable or warmup is insufficient, write `data_health = DEGRADED` and produce a non-executable decision instead of crashing.
- [ ] Verify one-shot synthetic dry-run still passes and source still has no mutation calls.

### Task 3: VPS Deployment Wiring

**Files:**
- Modify: `deploy/systemd/ai300-dry-run.service`
- Modify: `docs/runbooks/vps_dry_run.md`

- [ ] Change the service to use `configs/entry_chain.dry_run_highest_win.json`.
- [ ] Add `--market-data-source public-binance`.
- [ ] Document one-shot VPS smoke with highest-win config.
- [ ] Keep the safety checks requiring `orders_submitted = 0`.

### Task 4: Verification

Run:

```powershell
python -m compileall scripts tests
pytest tests/test_dry_run_configs.py tests/test_live_dry_run.py tests/test_live_entry_chain_adapter.py -q
python scripts/vps_dry_run_healthcheck.py --config configs/entry_chain.dry_run_highest_win.json --output-dir reports/dry_run/highest_win_healthcheck
python scripts/run_live_dry_run.py --config configs/entry_chain.dry_run_highest_win.json --target-tier aggressive --market-data-source synthetic --once --output-dir reports/dry_run/highest_win_local_smoke --symbols BNBUSDT,SOLUSDT
git diff -- src/api/binance_client.py
```

Expected:

- compile succeeds
- tests pass
- healthcheck returns `dry_run_safe = true`
- dry-run smoke writes decisions, order drafts, health, summary
- `orders_submitted = 0`
- Binance client diff is empty
