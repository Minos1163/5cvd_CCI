# Project Overview Gap Report

Date: 2026-06-19

Scope: compare the refreshed `docs/00_project_overview.md` against the current project-level scripts and contracts. This report is documentation only. No code, tests, configs, or live-execution modules are changed by this report.

---

## 1. Executive Summary

`docs/00_project_overview.md` has become the project-wide strategy and architecture entrance, but several scripts and core contract modules still encode an older, narrower version of the project. The main gap is not a single bug in trading logic. It is contract drift: the total project document now defines goals, layers, contracts, forbidden patterns, implementation order, operational success standards, and final system traits, while the executable project contract only exposes a small subset of that information.

The next safe step is to update project-level contract modules and their describe/scaffold tests first, without touching live execution behavior or the stable Binance client.

---

## 2. Investigation Method

Skills applied:

- `superpowers:writing-plans`: used to structure the future implementation plan before touching code.
- `superpowers:systematic-debugging`: used to identify root cause instead of patching symptoms.
- `superpowers:subagent-driven-development`: reserved as the recommended future execution workflow for the generated implementation plan.

Files inspected:

- `docs/00_project_overview.md`
- `src/core/project_spec.py`
- `src/core/module_spec.py`
- `scripts/describe_project_rules.py`
- `tests/test_project_spec.py`
- `tests/test_python_module_spec.py`
- `tests/test_describe_project_rules.py`
- `scripts/scaffold_ai300_framework.py`
- Current `docs/`, `src/`, `scripts/`, and `tests/` file inventory

No source code was modified during this investigation.

---

## 3. Root Cause

The project has been implemented document-by-document. Many individual contracts now exist, but the top-level overview contract was expanded after the original project-level Python contracts were written. As a result:

- `docs/00_project_overview.md` now defines the full system boundary.
- `src/core/project_spec.py` still exposes only priority, timeframes, venue, a small banned-feature list, a short layer order, and numeric success metrics.
- `src/core/module_spec.py` still has an incomplete strict dependency chain and older responsibility names.
- `scripts/describe_project_rules.py` does not export the refreshed project overview as a machine-readable contract.
- Tests assert the old minimal contract, so they would pass even when the expanded `00` requirements are missing.

This is a synchronization problem between documentation, contract constants, describe scripts, scaffold templates, and tests.

---

## 4. Evidence

### 4.1 `00_project_overview.md` Is Richer Than the Current Scripted Contract

The overview now defines:

- Project name and English name.
- Project objective and rebuild background.
- Ten core design goals.
- Binance USDT perpetual top-20 mainstream coin universe.
- Four timeframe roles: `15m`, `30m`, `1H`, `4H`.
- Indicator responsibilities for `MACD`, `CCI`, `BOLL`, `RSI`, `CVD`, `ATR`.
- Trading decision principles and forbidden patterns.
- Only two entry forms: `Probe` and `Direct`.
- Risk, position, backtest, and live trading goals.
- System layers from data through monitoring.
- One-way dependency flow.
- Ten unified contracts.
- Operational success standards.
- Coding principles.
- Recommended development order.
- Final system traits.

The current scripted project contract does not expose most of these sections.

### 4.2 `docs/00_project_overview.md` Has Formatting Contamination

The current file starts with wrapper text and a code fence:

- Line 1: "下面是重新生成的 `docs/00_project_overview.md` 完整版本..."
- Line 3: ````md
- Line 314: closing ```` after the dependency-flow block

That means the file is not a clean project document yet. It is usable as source material, but before long-term documentation use it should be normalized so the file begins directly with `# Project Overview` and does not wrap the full document in an outer code fence.

### 4.3 `src/core/project_spec.py` Is Still a Narrow Contract

Current `src/core/project_spec.py` only includes:

- `PROJECT_PRIORITY`
- `CORE_TIMEFRAMES`
- `REFERENCE_TIMEFRAMES`
- `TRADING_VENUE`
- `BANNED_FEATURES`
- `LAYER_ORDER`
- `SUCCESS_CRITERIA`
- `validate_feature_allowed()`

Missing from this contract:

- Project identity and objective.
- Design goals.
- Rebuild rationale.
- Market universe constraints.
- Explicit timeframe role contract.
- Indicator responsibility contract.
- Decision principles.
- `Probe` / `Direct` entry-form semantics and ratios.
- Non-goals.
- Risk, position, backtest, and live trading goals.
- Full system layer list.
- Full dependency flow.
- Unified contract list.
- Operational success standards.
- Implementation principles.
- Recommended development order.
- Final system traits.
- Expanded forbidden patterns.

### 4.4 `src/core/module_spec.py` Does Not Match the New Layer Boundary

Current `FINAL_MODULE_STRUCTURE` contains:

- `config`
- `data`
- `indicators`
- `context`
- `signals`
- `state_machine`
- `risk`
- `execution`
- `portfolio`
- `backtest`
- `reporting`
- `utils`

Gaps against the refreshed overview:

- No explicit `observability` / monitoring layer in `FINAL_MODULE_STRUCTURE`, even though `src/observability` exists and `00` requires monitoring.
- No explicit `deployment` module in `FINAL_MODULE_STRUCTURE`, even though `src/deployment` exists and `20_deployment_architecture.md` was implemented.
- `ALLOWED_DEPENDENCY_CHAIN` stops at `execution`; it omits `position_sizing`, `backtest`, `reporting`, and `monitoring`.
- `risk` currently owns `position_sizing`, but `00` separates risk layer and position layer conceptually.
- `ENGINE_NAMES` omits backtest, monitoring, and deployment concepts.
- `EVENT_TYPES` is much smaller than the event bus and execution/backtest contracts already created.

### 4.5 `scripts/describe_project_rules.py` Does Not Export the Full Overview

The script currently exports:

- Project priority.
- Core and reference timeframes.
- Numeric success criteria.
- Expanded strategy philosophy.
- Basic universe limits.

Missing from the describe output:

- Project objective.
- Design goals.
- System layers.
- Module dependency flow.
- Unified contracts.
- Operational success standards.
- Implementation principles.
- Recommended development order.
- Final system traits.
- Expanded forbidden patterns.
- `Probe` / `Direct` ratios and semantics.
- Risk, position, backtest, and live goals from `00`.

This means downstream tools cannot use `describe_project_rules.py` as the authoritative machine-readable view of the project overview.

### 4.6 Tests Lock In the Old Contract

Current tests verify the old limited shape:

- `tests/test_project_spec.py` checks priority, timeframes, one banned pattern, short layer order, and numeric metrics.
- `tests/test_python_module_spec.py` expects the old dependency chain ending at `execution`.
- `tests/test_describe_project_rules.py` only checks a few high-level fields and the already-expanded strategy philosophy.

These tests should be updated before implementation so the new project overview is protected by failing tests first.

### 4.7 Scaffold Templates May Reintroduce Drift

`scripts/scaffold_ai300_framework.py` contains templates for many project files. If `project_spec.py`, `module_spec.py`, describe scripts, or tests are updated manually but the scaffold template remains stale, a future scaffold run can recreate the older contract shape in a new checkout.

The scaffold already protects `src/api/binance_client.py`. That protection must remain unchanged.

---

## 5. Gap Matrix

| Area | Current State | Required State | Follow-up Files |
| --- | --- | --- | --- |
| Document cleanliness | `00` includes wrapper text and outer code fence | `00` should be a clean canonical markdown document | `docs/00_project_overview.md` |
| Project identity | Not scripted | Name, English name, objective, rebuild rationale scripted | `src/core/project_spec.py`, tests, describe script |
| Design goals | Not scripted | Ten design goals exposed as stable tuple/list | `src/core/project_spec.py`, `scripts/describe_project_rules.py` |
| Market scope | Partly in universe modules, not in project contract | Binance USDT perpetual top-20 mainstream scope linked to project overview | `src/core/project_spec.py`, `src/data/universe_filter.py` tests if needed |
| Timeframe roles | Only core/reference tuples | Explicit role map: `15m` execution, `30m` confirmation, `1h` direction, `4h` background only | `src/core/project_spec.py`, `tests/test_project_spec.py` |
| Indicator responsibilities | Exists in philosophy, not project overview contract | Project-level indicator role list aligned with `03` | `src/core/project_spec.py`, `src/core/strategy_philosophy.py` cross-check tests |
| Decision principles | Not scripted | Multi-timeframe, structure, CVD, volatility, data, risk, executable position priorities | `src/core/project_spec.py`, describe script |
| Entry forms | Present elsewhere, not top-level project contract | Only `PROBE` and `DIRECT`, with `0.25` and `1.0` ratios | `src/core/project_spec.py`, state/position tests |
| Non-goals | In philosophy, not project contract | No HFT, arbitrage, market making, black-box ML, complex promotion | `src/core/project_spec.py` |
| Risk goals | Distributed across risk modules | Top-level risk goals scripted and described | `src/core/project_spec.py`, `src/risk/risk_engine.py` tests if needed |
| Position goals | Distributed in position sizing | Top-level position goals and forbidden floor/cap distortion listed | `src/core/project_spec.py`, `src/risk/position_sizer.py` tests if needed |
| Backtest goals | Implemented partly in backtest docs/scripts | Top-level backtest goals linked into project contract | `src/core/project_spec.py`, `src/backtest/engine.py` consistency tests |
| Live goals | Implemented partly in execution/deployment | Top-level live goals linked into project contract | `src/core/project_spec.py`, execution/deployment describe tests |
| System layers | Short old `LAYER_ORDER` | Full `data -> indicator -> context -> signal -> state_machine -> risk -> position -> execution -> backtest -> reporting -> monitoring` | `src/core/project_spec.py`, `src/core/module_spec.py` |
| Dependency flow | `module_spec` chain stops at execution | Full conceptual flow with reporting/monitoring and explicit no reverse dependencies | `src/core/module_spec.py`, tests |
| Unified contracts | Not scripted | Data, indicator, event, state machine, risk, position, execution, backtest, config, logging | `src/core/project_spec.py`, describe script |
| Success standards | Numeric metrics only | Operational stability standards plus numeric performance metrics if kept as research targets | `src/core/project_spec.py`, tests |
| Coding principles | Not scripted | Contract-first, data-structure-first, backtest-before-live, tests-first, isomorphism, explainability, reproducibility, stability | `src/core/project_spec.py`, describe script |
| Development order | Not scripted | 12-step recommended development order | `src/core/project_spec.py`, describe script |
| Final traits | Not scripted | Simple, clear, explainable, reproducible, backtestable, auditable, low maintenance | `src/core/project_spec.py`, describe script |
| Scaffold sync | Likely stale templates | Scaffold emits the same project overview contract and tests | `scripts/scaffold_ai300_framework.py`, `tests/test_framework_scaffold.py` |

---

## 6. Priority Order

### P0: Must Fix Before More Strategy Logic

1. Clean or normalize `docs/00_project_overview.md`.
2. Expand `src/core/project_spec.py` into the authoritative project overview contract.
3. Add failing tests for the expanded project overview contract.
4. Update `scripts/describe_project_rules.py` to export the expanded contract.

### P1: Must Fix Before Cross-Module Integration

1. Align `src/core/module_spec.py` with the full system layer boundary.
2. Decide the naming bridge between conceptual `position_sizing` and current code location `src/risk/position_sizer.py`.
3. Add module/dependency tests for full one-way flow.
4. Update describe outputs to reflect monitoring and deployment concepts where relevant.

### P2: Must Fix Before Future Scaffold Reuse

1. Sync `scripts/scaffold_ai300_framework.py` templates.
2. Update scaffold tests to verify the expanded contract is emitted.
3. Ensure scaffold protection for `src/api/binance_client.py` remains unchanged.

---

## 7. Risk Notes

- Do not modify `src/api/binance_client.py`. It is stable and explicitly protected by user instruction.
- Do not change live execution behavior while aligning overview contracts.
- Do not convert aspirational performance metrics into hard live-trading promises.
- Do not add same-bar fill assumptions or lookahead behavior while touching backtest contract references.
- Keep project-overview updates contract-only until tests define the expected shape.
- Keep changes surgical: project contract, describe script, scaffold template, and tests first.

---

## 8. Recommended Next Plan

Implement the follow-up in `docs/superpowers/plans/2026-06-19-project-overview-gap-fill.md`.

Execution should use `superpowers:subagent-driven-development` because the work can be split into independent tasks:

1. Clean the project overview document.
2. Expand project spec and tests.
3. Align module spec and tests.
4. Expand describe script and tests.
5. Sync scaffold templates and scaffold tests.
6. Run targeted and full verification.

