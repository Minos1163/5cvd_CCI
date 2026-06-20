# Market Universe Gap Report

Date: 2026-06-19

Scope: reread the refreshed `docs/02_market_universe.md` and compare it with the current universe-related scripts, configuration, tests, and describe output. This report is documentation only. No strategy code, live execution code, or Binance client code is changed by this report.

---

## 1. Executive Summary

`docs/02_market_universe.md` now defines Market Universe as the system's first risk-control layer, not as a static config list. The current implementation still treats it mostly as a lightweight symbol filter. The largest gap is that the refreshed document requires a versioned, auditable, historically reproducible universe process, while the existing code only supports simple USDT filtering, market-cap rank/volume/listing-day checks, a meme exclusion flag, and a small static config.

The next safe step is to turn section 02 into a testable contract module before changing signal, risk, execution, or backtest behavior.

---

## 2. Files Reviewed

- `docs/02_market_universe.md`
- `src/data/universe_filter.py`
- `tests/test_market_universe.py`
- `configs/universe.yaml`
- `scripts/describe_project_rules.py`
- `src/config/config_schema.py`
- `src/data/data_contract.py`
- `src/data/database_schema.py`

---

## 3. Document Cleanliness Issue

The refreshed `docs/02_market_universe.md` is not yet a clean canonical markdown file. It starts with ChatGPT wrapper text and an outer markdown code fence:

- It begins with a sentence recommending overwrite.
- It includes an outer ````md wrapper.
- It ends with extra guidance about rewriting later docs.

This is useful source material, but the file should be normalized so line 1 is `# Market Universe` and the content contains only the section 02 spec.

---

## 4. Current Implementation Snapshot

`src/data/universe_filter.py` currently provides:

- `UniverseCandidate`
- `normalize_symbol()`
- `filter_symbols()`
- `filter_universe()`
- `get_risk_tier()`
- `max_position_multiplier()`
- `choose_by_correlation_preference()`

Current filtering supports:

- USDT suffix check.
- `market_cap_rank <= max_symbols`.
- Minimum 24h volume.
- Minimum listed days.
- Delisting flag.
- Meme exclusion.
- Rank sorting.

Current config in `configs/universe.yaml` supports:

- Exchange and quote asset.
- `max_symbols: 20`.
- 24-hour refresh interval.
- Static starter symbol list.

Current tests cover:

- Valid USDT filtering.
- Meme/new/non-USDT exclusion.
- Basic risk tiers.
- BTC preference over ETH in correlation helper.

---

## 5. Major Gaps

### 5.1 Universe Is Not Yet Treated As First-Layer Risk

The document says Universe is the first risk-control layer and higher priority than signals. Current code does not provide an explicit decision object like `UniverseDecision` with allow/block/suspend/remove semantics. Signal, risk, execution, and backtest modules also do not yet have a shared contract saying "no symbol outside active universe may generate new entries."

### 5.2 Entry Conditions Are Incomplete

The document requires all entry conditions:

- Market cap rank threshold.
- 24h quote volume threshold.
- USDT perpetual availability.
- Minimum listing age.
- Complete 15m/30m/1h/4h history.
- Missing-bar ratio limit.
- Average spread limit.
- Abnormal wick/spike filtering.
- Binance monitoring/delisting risk filtering.

Current `UniverseCandidate` lacks fields for:

- Contract type or perpetual availability.
- Quote asset.
- Volume rank.
- Spread percentage.
- Missing-bar percentage.
- Required timeframe history coverage.
- Abnormal wick/spike count or flag.
- Monitoring tag.
- Suspended/removed status.
- Added/removed timestamps.
- Version.
- Reason.

### 5.3 Thresholds Do Not Match V1 Recommendation

The document recommends:

- `max_symbols: 20`
- `min_market_cap_rank: 20`
- `max_market_cap_rank: 30`
- `min_24h_volume_usd: 300000000`
- `min_listing_days: 365`
- `max_spread_pct: 0.05`
- `update_frequency: weekly`

Current defaults are looser:

- `min_volume_24h = 50_000_000`
- `min_listed_days = 60`
- update interval is daily in config
- no spread threshold
- no weekly/monthly cadence constant

### 5.4 Versioning And Historical Snapshots Are Missing

The document requires:

- `universe_version`
- historical universe snapshots
- update logs
- fields like `symbol`, `market_cap_rank`, `volume_rank`, `added_time`, `removed_time`, `reason`, `version`

Current code does not define:

- `UniverseMember`
- `UniverseSnapshot`
- `UniverseVersion`
- snapshot validation
- update log structure
- active/suspended/removed lifecycle transitions

### 5.5 Backtest Consistency And Survivorship Bias Are Not Enforced

The document explicitly forbids using today's universe for historical backtests. Current backtest request/result contracts do not clearly require `universe_version` or historical universe selection per period. This creates a future risk of survivorship bias.

### 5.6 Config Schema Is Too Thin

`src/config/config_schema.py` only requires:

- `version`
- `universe.refresh_interval_hours`
- `universe.max_symbols`

It does not require the V1 filter thresholds, versioning policy, update cadence, or audit fields.

### 5.7 Describe Output Is Not Authoritative For Universe

`scripts/describe_project_rules.py` still exports only a small hardcoded universe section:

- `max_symbols`
- `max_simultaneous_positions`
- `recommended_positions`
- `single_symbol_exposure`
- `refresh_time_utc`

It does not expose the refreshed 02 contract.

### 5.8 Database Contract Partially Covers Symbols But Not Universe History

`src/data/database_schema.py` has a `symbols` table, but there is no explicit `universe_snapshots` or `universe_update_logs` table contract. If universe is versioned and auditable, it needs a persistent historical representation.

### 5.9 Existing Meme Policy Conflicts With Example Top20

The document's example Top20 includes `DOGE` and `SHIB`, while current `DEFAULT_EXCLUDED_MEME` excludes `DOGEUSDT` and `SHIBUSDT`. This is a real policy decision, not a code typo:

- Option A: keep meme exclusion as a system non-goal and treat doc list as illustrative only.
- Option B: allow high-cap meme assets if they pass liquidity/age/spread filters.

The future implementation plan should make this explicit rather than leaving it implicit.

---

## 6. Recommended Priority

### P0: Contract And Documentation

1. Clean `docs/02_market_universe.md`.
2. Expand `src/data/universe_filter.py` into a proper universe contract module.
3. Update `tests/test_market_universe.py` with failing tests for V1 thresholds, status lifecycle, snapshot fields, and historical consistency.

### P1: Config And Describe Sync

1. Expand `configs/universe.yaml` with V1 thresholds.
2. Update `src/config/config_schema.py` required fields.
3. Update `scripts/describe_project_rules.py` or add `scripts/describe_market_universe.py`.
4. Add describe tests.

### P2: Persistence And Backtest Hooks

1. Add database schema contracts for universe snapshots/update logs.
2. Require `universe_version` in backtest request/result artifacts.
3. Add guard tests preventing use of current universe for historical periods.

### P3: Cross-Layer Enforcement

1. Signal layer must refuse symbols outside active universe.
2. Execution layer must reject new entries for non-active symbols.
3. Existing positions for removed symbols may be managed until exit.

---

## 7. Risk Notes

- Do not change live execution paths while implementing this contract.
- Do not modify `src/api/binance_client.py`.
- Do not add network calls to market-cap APIs in the first implementation pass.
- Do not hardcode today's Top20 as the backtest universe.
- Do not introduce survivorship bias by using current symbols for historical tests.
- Treat thresholds as research defaults, not performance guarantees.

---

## 8. Proposed Next Plan

Implement the follow-up in `docs/superpowers/plans/2026-06-19-market-universe-gap-fill.md`.

Recommended execution mode: `superpowers:subagent-driven-development`, task-by-task, with review after each task.

