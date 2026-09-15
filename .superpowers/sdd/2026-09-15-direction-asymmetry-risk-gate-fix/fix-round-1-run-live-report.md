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
