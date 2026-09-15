# Fix Round 1 Run-Live Report

## Scope

- Updated `scripts/run_live_dry_run.py`.
- Updated `tests/test_live_dry_run.py`.

## Result

- Scout micro and mirror A/B experimental drafts now calculate `PROBE` cap diagnostics from their own paper ledger's current equity and symbol exposure, the near-miss stop/ATR context, configured symbol cap, and selected leverage.
- Draft quantities and `notional_hint` use the final capped notional, while small configured notionals remain unchanged.
- Mirror A/B calculates a separate capped payload for each ledger.
- Decision payloads retain their existing experimental metadata and now expose `risk_budget` diagnostics.

## Verification

`pytest -q tests/test_live_dry_run.py`

Result: `86 passed in 8.02s`.

## Reviewer Follow-Up

- Fixed exposure-unit consistency by converting ledger snapshot exposure from initial-equity normalization to current-equity normalization before applying the remaining symbol cap.
- Restored `max_symbol_exposure_pct` to `0.0` for scout and mirror custom payloads; the configured cap is retained in `risk_budget.symbol_exposure_cap_pct` and remains an input to diagnostics.
- Added regression coverage for an existing position after equity drawdown, plus assertions for risk-budget leverage, stop/ATR-derived stop, configured cap, and final capped notional.

## Follow-Up Verification

Implementation commit: `73a39455f312ac4274c664d8cd3077743a20aec5`

`pytest -q tests/test_live_dry_run.py`

Result: `87 passed in 8.34s`.
