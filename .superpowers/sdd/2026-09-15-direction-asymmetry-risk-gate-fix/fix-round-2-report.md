# Fix Round 2 Report

## Implemented

- Normalized paper-ledger symbol, total, and same-direction exposure from the initial-equity basis to the current-equity basis before hydration into `EntryChainContext`.
- Retained the existing invalid-equity fallback behavior.
- Made SHORT shadow offset filtering action-aware: `DIRECT` uses `82 + offset`; `PROBE` uses `70 + offset`.
- Reported both thresholds in the JSON assumptions and each offset result.

## Verification

- `tests/test_live_dry_run.py` now proves a realized drawdown scales a remaining 18% initial-equity LONG position above a 20% current-equity cap and rejects a new same-side entry.
- `tests/test_regime_short_offset_shadow.py` now proves PROBE and DIRECT candidates are each compared with their corresponding threshold.

## Scope

- No changes to `src/observability/paper_trading.py`, scout/mirror eligibility policy, live order behavior, leverage-tier selection, or shadow-only status.
