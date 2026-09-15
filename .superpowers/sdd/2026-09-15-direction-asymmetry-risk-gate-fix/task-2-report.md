# Task 2 Report: Q1 Symbol-Policy Enforcement

## Changes

- Added a shared Q1 symbol-policy reason helper in `scripts/run_live_dry_run.py`.
- Q1 specialized eligibility now rejects blacklist, watch-only, and observation-only symbols.
- Rejections use distinct auditable reasons: `Q1_SYMBOL_BLACKLISTED`, `Q1_SYMBOL_WATCH_ONLY`, and `Q1_SYMBOL_OBSERVATION_ONLY`.
- The main dry-run loop records a policy rejection as a controlled WATCH decision with the reason, so the specialized path cannot silently promote a blocked symbol and cannot crash the loop.
- The Q1 custom PROBE notional is re-constrained with the existing centralized `_notional_cap_diagnostics` helper using the same stop, equity, exposure, and leverage=1 inputs; cap diagnostics and the pre-cap custom notional are included in decision metadata.
- Preserved the existing `build_q1_green_channel_decision` rejected-candidate `None` contract and ordinary DIRECT/PROBE/WATCH behavior.
- Added focused tests for all three rejected policy classes, an allowed symbol, and reason auditability.

## Test Results

- `python -m pytest -q --basetemp .pytest_tmp_task2 tests/test_q1_trend_launch_fix.py tests/test_live_dry_run.py`: **110 passed**
- After the Task 1 cap integration: `python -m pytest -q --basetemp .pytest_tmp_task2 tests/test_q1_trend_launch_fix.py tests/test_live_dry_run.py`: **111 passed**
- `python -m pytest -q --basetemp .pytest_tmp_task2 tests/test_q1_trend_launch_fix.py`: **27 passed**
- An initial combined run without `--basetemp` hit Windows permission errors while pytest tried to enumerate `C:\Users\Huang\AppData\Local\Temp\pytest-of-Huang`; no test body failure was involved. The repository-local basetemp rerun passed.

## Assumptions

- Q1 policy reason precedence is blacklist, then watch-only, then observation-only, matching the strongest existing centralized symbol gate precedence.
- Existing ADA/XMR watch-only handling remains available to non-Q1/scout paths; this change only blocks the Q1 specialized entry channel.
- No risk-cap or live-execution code requires modification for this policy gate.
- The Q1 cap test uses a deliberately oversized custom notional and verifies it is reduced to the centralized PROBE cap.

## Concerns

- The task-specific Q1 policy reasons are additive audit reasons; existing centralized reasons may also remain on the underlying decision payload.
