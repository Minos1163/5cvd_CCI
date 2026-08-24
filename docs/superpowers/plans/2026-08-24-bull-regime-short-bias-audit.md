# Bull Regime Short Bias Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add offline evidence tooling and report updates for the 2026-08-18 12:00 bull-regime short-bias review without changing live trading behavior.

**Architecture:** Implement a standalone read-only audit script that parses existing `decisions.jsonl` rows and summarizes LONG/SHORT executable asymmetry after a known bullish-regime start. Extend the existing cumulative channel tracker to include the two proposed continuation/regime channels as zero-sample tracked channels. Update the 08-24 attribution report with the required prior-recommendation review, short-bias audit output, and clarified mission priority.

**Tech Stack:** Python standard library, pytest, existing JSONL log format under `logs/YYYY-MM/YYYY-MM-DD/`, Markdown reports.

## Global Constraints

- Do not modify live execution, live risk, or production config paths.
- Do not introduce lookahead bias, future candle data, repaint signals, or same-bar fill assumptions into live logic.
- The audit script is offline attribution only; it must not create entry signals or alter paper/live ledgers.
- Use `kline.timestamp` as the market timestamp for `decisions.jsonl`; fall back to row `timestamp` only when the kline timestamp is absent.
- Treat `PROBE` and `DIRECT` as executable actions; treat `WATCH` and `NO_TRADE` as non-executable.
- Preserve existing untracked files unrelated to this plan.

---

### Task 1: Bullish-Regime LONG/SHORT Asymmetry Audit Script

**Files:**
- Create: `scripts/audit_bullish_regime_short_bias.py`
- Create: `tests/test_audit_bullish_regime_short_bias.py`

**Interfaces:**
- Produces: `load_decisions(log_root: Path, start: str, end: str) -> list[DecisionAuditRow]`
- Produces: `filter_rows(rows: list[DecisionAuditRow], start_ts: int, end_ts: int | None) -> list[DecisionAuditRow]`
- Produces: `summarize_asymmetry(rows: list[DecisionAuditRow], min_score: float = 80.0) -> dict[str, Any]`
- Produces: CLI command:
  `python scripts/audit_bullish_regime_short_bias.py --log-root logs --start 2026-08-18 --end 2026-08-24 --regime-start "2026-08-19 19:15" --min-score 80 --output-dir reports/analysis/2026-08-24-short-bias`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_audit_bullish_regime_short_bias.py` with these tests:

```python
import json

from scripts.audit_bullish_regime_short_bias import load_decisions, summarize_asymmetry, write_outputs


def _decision(symbol, side, quadrant, score, action, ts, reasons=None):
    return {
        "symbol": symbol,
        "quadrant": quadrant,
        "score": score,
        "action": action,
        "reasons": reasons or ["FIB_PA_ARCHITECTURE_WEIGHTS"],
        "entry_context": {"side": side},
        "kline": {"timestamp": ts, "close": 100.0, "high": 101.0, "low": 99.0},
    }


def test_summary_counts_high_score_executable_rate_by_quadrant_and_side():
    rows = [
        _decision("BNBUSDT", "LONG", "Q1", 85.0, "WATCH", 1),
        _decision("BNBUSDT", "LONG", "Q1", 86.0, "PROBE", 2),
        _decision("BNBUSDT", "SHORT", "Q1", 87.0, "DIRECT", 3),
        _decision("SOLUSDT", "SHORT", "Q1", 79.0, "DIRECT", 4),
        _decision("SOLUSDT", "SHORT", "Q2", 82.0, "NO_TRADE", 5),
        _decision("DOGEUSDT", "SHORT", "Q2", 83.0, "PROBE", 6),
    ]

    summary = summarize_asymmetry(rows, min_score=80.0)

    assert summary["overall"]["LONG"]["high_score_count"] == 2
    assert summary["overall"]["LONG"]["executable_count"] == 1
    assert summary["overall"]["LONG"]["executable_rate"] == 0.5
    assert summary["overall"]["SHORT"]["high_score_count"] == 3
    assert summary["overall"]["SHORT"]["executable_count"] == 2
    assert summary["by_quadrant"]["Q1"]["SHORT"]["executable_count"] == 1
    assert summary["by_quadrant"]["Q2"]["SHORT"]["executable_count"] == 1
    assert summary["short_bias"]["executable_count_delta"] == 1


def test_load_decisions_uses_kline_timestamp_and_filters_invalid_sides(tmp_path):
    day_dir = tmp_path / "logs" / "2026-08" / "2026-08-19"
    day_dir.mkdir(parents=True)
    payloads = [
        _decision("BNBUSDT", "LONG", "Q1", 85.0, "WATCH", 1787138100),
        {"symbol": "XRPUSDT", "side": "NONE", "kline": {"timestamp": 1787138100}},
    ]
    (day_dir / "decisions.jsonl").write_text("\n".join(json.dumps(item) for item in payloads) + "\n", encoding="utf-8")

    rows = load_decisions(tmp_path / "logs", "2026-08-19", "2026-08-19")

    assert len(rows) == 1
    assert rows[0].timestamp == 1787138100
    assert rows[0].side == "LONG"


def test_write_outputs_writes_json_and_markdown(tmp_path):
    summary = summarize_asymmetry([_decision("BNBUSDT", "SHORT", "Q1", 88.0, "DIRECT", 1)], min_score=80.0)

    write_outputs(summary, tmp_path, start="2026-08-19", end="2026-08-19", regime_start="2026-08-19 19:15", min_score=80.0)

    assert (tmp_path / "bullish_regime_short_bias_audit.json").exists()
    markdown = (tmp_path / "bullish_regime_short_bias_audit.md").read_text(encoding="utf-8")
    assert "Bullish Regime Short-Bias Audit" in markdown
    assert "Q1" in markdown
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_audit_bullish_regime_short_bias.py -q`

Expected: FAIL because `scripts.audit_bullish_regime_short_bias` does not exist.

- [ ] **Step 3: Implement the minimal script**

Create `scripts/audit_bullish_regime_short_bias.py` with:

```python
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

TZ_CST = timezone(timedelta(hours=8))
EXECUTABLE_ACTIONS = {"DIRECT", "PROBE"}
SIDES = ("LONG", "SHORT")
QUADRANTS = ("Q1", "Q2", "Q3", "Q4")


@dataclass(frozen=True)
class DecisionAuditRow:
    day: str
    timestamp: int
    symbol: str
    side: str
    quadrant: str
    score: float
    action: str
    reasons: tuple[str, ...]


def date_range(start: str, end: str) -> Iterable[str]:
    current = date.fromisoformat(start)
    final = date.fromisoformat(end)
    while current <= final:
        yield current.isoformat()
        current += timedelta(days=1)


def load_decisions(log_root: Path, start: str, end: str) -> list[DecisionAuditRow]:
    rows: list[DecisionAuditRow] = []
    for day in date_range(start, end):
        path = log_root / day[:7] / day / "decisions.jsonl"
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            row = parse_decision(day, payload)
            if row is not None:
                rows.append(row)
    return sorted(rows, key=lambda item: (item.timestamp, item.symbol, item.side))


def parse_decision(day: str, payload: dict[str, Any]) -> DecisionAuditRow | None:
    context = payload.get("entry_context") if isinstance(payload.get("entry_context"), dict) else {}
    kline = payload.get("kline") if isinstance(payload.get("kline"), dict) else {}
    side = str(context.get("side") or payload.get("side") or "").strip().upper()
    if side not in SIDES:
        return None
    symbol = str(payload.get("symbol") or "").strip().upper()
    timestamp = _int(kline.get("timestamp") or payload.get("kline_timestamp") or payload.get("timestamp"))
    if not symbol or timestamp <= 0:
        return None
    reasons = payload.get("reasons", [])
    if not isinstance(reasons, list):
        reasons = [str(reasons)]
    return DecisionAuditRow(
        day=day,
        timestamp=timestamp,
        symbol=symbol,
        side=side,
        quadrant=str(payload.get("quadrant") or "UNKNOWN").strip().upper(),
        score=_float(payload.get("score")),
        action=str(payload.get("action") or "").strip().upper(),
        reasons=tuple(str(item) for item in reasons),
    )
```

Also implement `filter_rows`, `summarize_asymmetry`, `write_outputs`, Markdown rendering, CLI parsing, and `main()` using the same patterns as `scripts/replay_high_score_intercepts.py` and `scripts/summarize_scout_trend_capture_diagnostics.py`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_audit_bullish_regime_short_bias.py -q`

Expected: PASS.

- [ ] **Step 5: Run the real audit**

Run:

```powershell
python scripts\audit_bullish_regime_short_bias.py --log-root logs --start 2026-08-18 --end 2026-08-24 --regime-start "2026-08-19 19:15" --min-score 80 --output-dir reports\analysis\2026-08-24-short-bias
```

Expected: JSON and Markdown are written under `reports/analysis/2026-08-24-short-bias/`.

### Task 2: Extend Channel Cumulative Tracker for Proposed Channels

**Files:**
- Modify: `scripts/channel_cumulative_tracker.py`
- Create: `tests/test_channel_cumulative_tracker.py`

**Interfaces:**
- Produces: `TRACKED_CHANNELS` includes:
  - `scout_bnb_trend_continuation_after_pullback`
  - `scout_bull_regime_breakout_v1`
- Produces: `CHANNEL_LEDGER_SCOPE` maps both new channels to `("scout_micro/paper_trades.jsonl",)`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_channel_cumulative_tracker.py`:

```python
import scripts.channel_cumulative_tracker as tracker


def test_tracker_includes_proposed_shadow_channels():
    assert "scout_bnb_trend_continuation_after_pullback" in tracker.TRACKED_CHANNELS
    assert "scout_bull_regime_breakout_v1" in tracker.TRACKED_CHANNELS


def test_proposed_shadow_channels_are_scoped_to_scout_ledger():
    assert tracker.CHANNEL_LEDGER_SCOPE["scout_bnb_trend_continuation_after_pullback"] == ("scout_micro/paper_trades.jsonl",)
    assert tracker.CHANNEL_LEDGER_SCOPE["scout_bull_regime_breakout_v1"] == ("scout_micro/paper_trades.jsonl",)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_channel_cumulative_tracker.py -q`

Expected: FAIL because the proposed channels are not tracked yet.

- [ ] **Step 3: Extend tracked channel constants**

Add the two channel names to `TRACKED_CHANNELS` and add their scout ledger scopes to `CHANNEL_LEDGER_SCOPE`. Do not change ledger parsing or PnL semantics.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_channel_cumulative_tracker.py -q`

Expected: PASS.

- [ ] **Step 5: Run tracker over the current audit window**

Run:

```powershell
python scripts\channel_cumulative_tracker.py --start 2026-08-18 --end 2026-08-24
```

Expected: Existing channels show their counts; the two proposed channels show zero samples and remain under the sample-size discipline.

### Task 3: Update 08-24 Report With Review Findings and Audit Evidence

**Files:**
- Modify: `docs/superpowers/reports/2026-08-24-after-0818-1200-offense-failure-attribution.md`

**Interfaces:**
- Consumes: Markdown output from `reports/analysis/2026-08-24-short-bias/bullish_regime_short_bias_audit.md`
- Produces: Report sections:
  - `## 1. 上轮建议实施回顾`
  - `## 4. SHORT 偏向审计`
  - A revised priority section stating P0 is short-bias audit and P1 is `BULL_REGIME_BREAKOUT_V1` shadow/scout.

- [ ] **Step 1: Insert prior recommendation review table**

Add a section near the top:

```markdown
## 1. 上轮建议实施回顾

| 08-18 建议 | 状态 | 证据 |
|---|---|---|
| mirror A/B 降级为 shadow-only | 已在配置中保持 `mirror_ab_mode=shadow_only` | `configs/entry_chain.dry_run_fib_pa_v1.json` |
| ChannelCumulativeTracker 建立 | 已建立,本轮继续扩展候选通道 | `scripts/channel_cumulative_tracker.py` |
| 20 笔评估门槛纪律 | 继续执行 | `<10 不提炼; <20 不调参/不资源倾斜` |
| REVERSAL_PIVOT_SCOUT 停用 | 已保持停用 | `scout_micro_reversal_pivot_enabled=false` |
```

- [ ] **Step 2: Insert short-bias audit evidence**

Add a section summarizing the new audit command output:

```markdown
## SHORT 偏向审计

本轮新增 `scripts/audit_bullish_regime_short_bias.py`,以 08-19 19:15 作为 confirmed bullish regime 起点,统计高分 LONG/SHORT 的可执行率。

| 维度 | 结论 |
|---|---|
| high-score 门槛 | score >= 80 |
| executable 定义 | `DIRECT` 或 `PROBE` |
| 核心问题 | confirmed bullish regime 下 SHORT 仍需单独审计,不能只优化 LONG 放行 |
```

Fill the final numbers from the real audit output.

- [ ] **Step 3: Clarify route priority**

Revise the candidate rule section so it says:

```markdown
P0: first audit and control confirmed-bullish SHORT execution asymmetry.
P1: deploy `BULL_REGIME_BREAKOUT_V1` only as shadow/scout after route-priority and sample-tracking are explicit.
```

- [ ] **Step 4: Run verification commands**

Run:

```powershell
pytest tests/test_audit_bullish_regime_short_bias.py tests/test_channel_cumulative_tracker.py -q
python scripts\audit_bullish_regime_short_bias.py --log-root logs --start 2026-08-18 --end 2026-08-24 --regime-start "2026-08-19 19:15" --min-score 80 --output-dir reports\analysis\2026-08-24-short-bias
python scripts\channel_cumulative_tracker.py --start 2026-08-18 --end 2026-08-24
```

Expected: tests pass; both scripts run without exceptions.

- [ ] **Step 5: Final diff check**

Run: `git diff --check`

Expected: no whitespace errors.
