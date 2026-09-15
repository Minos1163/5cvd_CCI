# Fix Round 1 Task 2 Report

## Scope

Updated only `task-2-report.md` to correct the description of Q1 policy-rejection handling.

## Change

The report now states that `_add_decision_reasons()` records the distinct Q1 policy reason and metadata additively for auditability while preserving the underlying action, `risk_allowed`, leverage, and notional semantics.

## Verification

Confirmed the diff is limited to the required Task 2 report wording plus this documentation-only fix report. No code or tests were changed.

## Concerns

No outstanding concerns.
