# Four Quadrant Gap Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the dry-run gaps found after the 2026-07-21 19:45 run: A/B auto reports, dry-run paper exit auto-switch, mission-level three-stop circuit, and explicit Q1 long-offset scout gating.

**Architecture:** Keep all changes inside dry-run/paper infrastructure. Persist small JSON state files under the paper state directory so long-running VPS dry-run resumes decisions across process restarts. Do not touch exchange API or live execution modules.

**Tech Stack:** Python stdlib, existing `EntryChainConfig`, existing `PaperTradingLedger`, pytest.

## Global Constraints

- Do not modify `src/api` or live execution order submission behavior.
- Auto-switch only changes the dry-run main paper ledger effective exit mode; it must not rewrite config files or affect real exchange orders.
- All new experiment controls must be explicit in `summary.json` assumptions or paper A/B report artifacts.
- Mission stop circuit must key by `scout_mission`, not only by symbol.
- Tests must cover each new control before claiming completion.

---

### Task 1: A/B Auto Report And Dry-Run Exit Override

**Files:**
- Modify: `src/signals/entry_chain_config.py`
- Modify: `configs/entry_chain.dry_run_fib_pa_v1.json`
- Modify: `scripts/run_live_dry_run.py`
- Modify: `tests/test_entry_chain_config.py`
- Modify: `tests/test_dry_run_configs.py`
- Modify: `tests/test_live_dry_run.py`

**Interfaces:**
- Produces: `paper_ab_auto_report(...) -> dict[str, Any] | None`
- Produces: `load_paper_ab_switch_state(path: Path) -> dict[str, Any]`
- Produces: `effective_paper_exit_mode(config: EntryChainConfig, paper_state_dir: Path) -> str`

- [ ] Add config fields for A/B report interval and auto-switch thresholds.
- [ ] Generate a persisted A/B report every 20 closed trades once both ledgers reach the same closed trade count batch.
- [ ] Persist `paper_exit_mode_override=trend_capture` after at least two reports and 40 closed trades where trend_capture payoff ratio is at least 1.3x legacy.
- [ ] Use the persisted override when constructing the main paper ledger.
- [ ] Add tests for report generation and effective mode override.

### Task 2: Mission-Level Three Initial-Stop Circuit

**Files:**
- Modify: `src/signals/entry_chain_config.py`
- Modify: `configs/entry_chain.dry_run_fib_pa_v1.json`
- Modify: `scripts/run_live_dry_run.py`
- Modify: `tests/test_entry_chain_config.py`
- Modify: `tests/test_dry_run_configs.py`
- Modify: `tests/test_live_dry_run.py`

**Interfaces:**
- Produces: `_scout_micro_mission_stop_cooldown_reason(mission: str, config: EntryChainConfig, scout_paper: PaperTradingLedger, timestamp: int | None) -> str | None`

- [ ] Add config fields: enabled flag, stop count, cooldown hours.
- [ ] Before opening SCOUT, block the mission when its latest N closed trades are all `INITIAL_STOP_HIT` within the cooldown window.
- [ ] Keep existing symbol-level cooldown unchanged.
- [ ] Add tests proving mission-level blocking across different symbols.

### Task 3: Explicit Q1 Long Offset Rule And Audit Fields

**Files:**
- Modify: `scripts/run_live_dry_run.py`
- Modify: `tests/test_live_dry_run.py`

**Interfaces:**
- Modifies: `_high_score_long_offset_probe_eligible(...)`

- [ ] Require `decision_quadrant(near_miss, config) == "Q1"` for `HIGH_SCORE_LONG_OFFSET_PROBE`.
- [ ] Add `LONG_OFFSET_Q1_PROBE` as an audit alias in SCOUT reasons/tags while preserving existing mission name for compatibility.
- [ ] Add tests that Q1 passes and non-Q1 fails.

### Task 4: Runtime Log Analysis Report

**Files:**
- Create: `docs/superpowers/reports/2026-07-22-after-1945-gap-analysis.md`

**Interfaces:**
- Consumes: logs under `logs/2026-07/2026-07-21` and `logs/2026-07/2026-07-22`.

- [ ] Summarize run behavior since 2026-07-21 19:45 Asia/Shanghai.
- [ ] Record which missing controls explain observed behavior.
- [ ] Record implementation verification commands and results.
