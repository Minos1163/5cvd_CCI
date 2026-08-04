# Structured Offense Diagnostics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the offline "intelligence post" from DeepSeek review #8: replay high-score intercepted signals, quantify LONG/Fib/RR rule false-negative risk, and produce a rolling symbol panel without changing live entry behavior.

**Architecture:** Add one standalone analysis script that reads existing `decisions.jsonl` logs, reconstructs future 15m bars from later decisions, and calculates hypothetical MFE/MAE/TP/SL outcomes for intercepted high-score signals. The script writes JSON plus Markdown reports so future strategy changes can be reviewed from evidence rather than threshold intuition.

**Tech Stack:** Python standard library, existing log JSONL format, pytest for unit tests.

## Global Constraints

- Do not modify live execution, live risk, or production config paths in this plan.
- Offline replay may use future bars only for post-trade attribution; it must be clearly labeled as non-live-executable analysis.
- Entry assumptions must be explicit: entry at logged closed 15m candle close, stop from logged `entry_context.stop_pct`, TP ladder from paper ledger `1.2R/2.0R/3.0R`.
- Report missing Sharpe, funding, tail risk, and net beta if unavailable.
- Do not revert unrelated dirty worktree changes.

---

### Task 1: High-Score Intercept Replay Script

**Files:**
- Create: `scripts/replay_high_score_intercepts.py`
- Test: `tests/test_replay_high_score_intercepts.py`

**Interfaces:**
- Produces: `load_decision_rows(log_root: Path, start: str, end: str) -> list[DecisionRow]`
- Produces: `select_intercepts(rows: list[DecisionRow], min_score: float) -> list[DecisionRow]`
- Produces: `replay_intercept(row: DecisionRow, future_rows: list[DecisionRow], horizon_bars: int) -> ReplayResult | None`
- Produces CLI: `python scripts/replay_high_score_intercepts.py --log-root logs --start 2026-06-30 --end 2026-07-13 --min-score 85 --output-dir reports/structured_offense/2026-07-13`

- [ ] **Step 1: Write failing tests for selection and replay**

Create `tests/test_replay_high_score_intercepts.py` with fixtures that cover:

```python
from pathlib import Path

from scripts.replay_high_score_intercepts import (
    DecisionRow,
    group_future_rows,
    replay_intercept,
    select_intercepts,
    summarize_results,
)


def row(ts, symbol="LINKUSDT", side="LONG", action="WATCH", score=86.0, close=100.0, high=101.0, low=99.0, reasons=None, stop_pct=0.01):
    return DecisionRow(
        day="2026-07-01",
        timestamp=ts,
        symbol=symbol,
        side=side,
        action=action,
        score=score,
        reasons=tuple(reasons or ("SIDE_THRESHOLD_OFFSET_LONG_10.00",)),
        close=close,
        high=high,
        low=low,
        stop_pct=stop_pct,
        component_points={"price_action_structure": 20.0, "risk_reward_geometry": 4.0},
    )


def test_select_intercepts_excludes_live_actions_and_low_scores():
    rows = [
        row(1, action="WATCH", score=85.0),
        row(2, action="NO_TRADE", score=90.0, reasons=("FIB_EXTENSION_EXHAUSTION_BLOCK",)),
        row(3, action="DIRECT", score=91.0),
        row(4, action="WATCH", score=84.9),
    ]

    selected = select_intercepts(rows, min_score=85.0)

    assert [item.timestamp for item in selected] == [1, 2]


def test_replay_long_hits_tp2_before_horizon():
    entry = row(100, close=100.0, stop_pct=0.01)
    future = [
        row(200, close=100.8, high=101.0, low=99.7),
        row(300, close=102.1, high=102.2, low=100.5),
    ]

    result = replay_intercept(entry, future, horizon_bars=4)

    assert result is not None
    assert result.max_tp_hit == 2
    assert result.stop_hit is False
    assert result.mfe_r >= 2.0
    assert result.mae_r <= 0.3


def test_replay_short_stop_hit():
    entry = row(100, side="SHORT", close=100.0, stop_pct=0.01)
    future = [row(200, side="SHORT", close=100.9, high=101.2, low=99.8)]

    result = replay_intercept(entry, future, horizon_bars=4)

    assert result is not None
    assert result.stop_hit is True
    assert result.final_r <= -1.0


def test_summarize_results_by_reason_and_symbol():
    entry = row(100, symbol="LINKUSDT")
    future = [row(200, symbol="LINKUSDT", close=102.5, high=102.5, low=99.9)]
    result = replay_intercept(entry, future, horizon_bars=4)

    summary = summarize_results([result])

    assert summary["total"] == 1
    assert summary["by_primary_reason"]["SIDE_THRESHOLD_OFFSET_LONG_10.00"]["count"] == 1
    assert summary["by_symbol"]["LINKUSDT"]["count"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_replay_high_score_intercepts.py -q`

Expected: FAIL because `scripts.replay_high_score_intercepts` does not exist.

- [ ] **Step 3: Implement minimal script**

Create `scripts/replay_high_score_intercepts.py` with:

```python
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path
from statistics import mean
from typing import Any, Iterable

TP_LEVELS = (1.2, 2.0, 3.0)


@dataclass(frozen=True)
class DecisionRow:
    day: str
    timestamp: int
    symbol: str
    side: str
    action: str
    score: float
    reasons: tuple[str, ...]
    close: float
    high: float
    low: float
    stop_pct: float
    component_points: dict[str, float]


@dataclass(frozen=True)
class ReplayResult:
    day: str
    timestamp: int
    symbol: str
    side: str
    action: str
    score: float
    primary_reason: str
    reasons: tuple[str, ...]
    entry: float
    stop_pct: float
    horizon_bars: int
    bars_seen: int
    mfe_r: float
    mae_r: float
    final_r: float
    max_tp_hit: int
    stop_hit: bool
    first_terminal: str
    component_points: dict[str, float]


def date_range(start: str, end: str) -> Iterable[str]:
    current = date.fromisoformat(start)
    final = date.fromisoformat(end)
    while current <= final:
        yield current.isoformat()
        current += timedelta(days=1)


def decision_path(log_root: Path, day: str) -> Path:
    month = day[:7]
    return log_root / month / day / "decisions.jsonl"


def load_decision_rows(log_root: Path, start: str, end: str) -> list[DecisionRow]:
    rows: list[DecisionRow] = []
    for day in date_range(start, end):
        path = decision_path(log_root, day)
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            row = parse_decision(day, payload)
            if row is not None:
                rows.append(row)
    return sorted(rows, key=lambda item: (item.timestamp, item.symbol))


def parse_decision(day: str, payload: dict[str, Any]) -> DecisionRow | None:
    kline = payload.get("kline") if isinstance(payload.get("kline"), dict) else {}
    context = payload.get("entry_context") if isinstance(payload.get("entry_context"), dict) else {}
    close = _float(kline.get("close"))
    high = _float(kline.get("high"))
    low = _float(kline.get("low"))
    timestamp = _int(kline.get("timestamp") or payload.get("timestamp"))
    symbol = str(payload.get("symbol") or "").strip().upper()
    side = str(context.get("side") or payload.get("side") or "").strip().upper()
    if not symbol or side not in {"LONG", "SHORT"} or close <= 0 or high <= 0 or low <= 0 or timestamp <= 0:
        return None
    reasons = payload.get("reasons", [])
    if not isinstance(reasons, list):
        reasons = [str(reasons)]
    component_points = payload.get("component_points")
    if not isinstance(component_points, dict):
        component_points = {}
    return DecisionRow(
        day=day,
        timestamp=timestamp,
        symbol=symbol,
        side=side,
        action=str(payload.get("action") or "").strip().upper(),
        score=_float(payload.get("score")),
        reasons=tuple(str(item) for item in reasons),
        close=close,
        high=high,
        low=low,
        stop_pct=max(0.0001, _float(context.get("stop_pct"), default=0.01)),
        component_points={str(key): _float(value) for key, value in component_points.items()},
    )


def select_intercepts(rows: list[DecisionRow], min_score: float) -> list[DecisionRow]:
    return [
        row
        for row in rows
        if row.score >= min_score
        and row.action not in {"PROBE", "DIRECT"}
        and primary_reason(row.reasons)
    ]


def group_future_rows(rows: list[DecisionRow]) -> dict[str, list[DecisionRow]]:
    grouped: dict[str, list[DecisionRow]] = defaultdict(list)
    for row in rows:
        grouped[row.symbol].append(row)
    return {symbol: sorted(items, key=lambda item: item.timestamp) for symbol, items in grouped.items()}


def replay_intercept(row: DecisionRow, future_rows: list[DecisionRow], horizon_bars: int) -> ReplayResult | None:
    future = [item for item in future_rows if item.timestamp > row.timestamp][:horizon_bars]
    if not future:
        return None
    risk = row.close * row.stop_pct
    if risk <= 0:
        return None
    mfe = 0.0
    mae = 0.0
    final_r = 0.0
    max_tp_hit = 0
    stop_hit = False
    first_terminal = "HORIZON_END"
    for bar in future:
        if row.side == "LONG":
            favorable = (bar.high - row.close) / risk
            adverse = (row.close - bar.low) / risk
            close_r = (bar.close - row.close) / risk
            hit_stop = bar.low <= row.close - risk
        else:
            favorable = (row.close - bar.low) / risk
            adverse = (bar.high - row.close) / risk
            close_r = (row.close - bar.close) / risk
            hit_stop = bar.high >= row.close + risk
        mfe = max(mfe, favorable)
        mae = max(mae, adverse)
        final_r = close_r
        for index, level in enumerate(TP_LEVELS, start=1):
            if mfe >= level:
                max_tp_hit = max(max_tp_hit, index)
        if hit_stop and first_terminal == "HORIZON_END":
            stop_hit = True
            first_terminal = "INITIAL_STOP_HIT"
            final_r = -1.0
            break
    if max_tp_hit > 0 and first_terminal == "HORIZON_END":
        first_terminal = f"TP{max_tp_hit}_TOUCHED"
    return ReplayResult(
        day=row.day,
        timestamp=row.timestamp,
        symbol=row.symbol,
        side=row.side,
        action=row.action,
        score=row.score,
        primary_reason=primary_reason(row.reasons),
        reasons=row.reasons,
        entry=row.close,
        stop_pct=row.stop_pct,
        horizon_bars=horizon_bars,
        bars_seen=len(future),
        mfe_r=round(mfe, 4),
        mae_r=round(mae, 4),
        final_r=round(final_r, 4),
        max_tp_hit=max_tp_hit,
        stop_hit=stop_hit,
        first_terminal=first_terminal,
        component_points=dict(row.component_points),
    )


def primary_reason(reasons: tuple[str, ...]) -> str:
    return next((reason for reason in reasons if reason != "FIB_PA_ARCHITECTURE_WEIGHTS"), "")


def replay_all(rows: list[DecisionRow], min_score: float, horizon_bars: int) -> list[ReplayResult]:
    grouped = group_future_rows(rows)
    results: list[ReplayResult] = []
    for row in select_intercepts(rows, min_score):
        result = replay_intercept(row, grouped.get(row.symbol, []), horizon_bars)
        if result is not None:
            results.append(result)
    return results


def summarize_results(results: list[ReplayResult]) -> dict[str, Any]:
    return {
        "total": len(results),
        "overall": summarize_bucket(results),
        "by_primary_reason": summarize_group(results, lambda item: item.primary_reason),
        "by_symbol": summarize_group(results, lambda item: item.symbol),
        "by_side": summarize_group(results, lambda item: item.side),
    }


def summarize_group(results: list[ReplayResult], key_fn) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[ReplayResult]] = defaultdict(list)
    for item in results:
        grouped[str(key_fn(item))].append(item)
    return {key: summarize_bucket(items) for key, items in sorted(grouped.items())}


def summarize_bucket(items: list[ReplayResult]) -> dict[str, Any]:
    if not items:
        return {"count": 0}
    tp2 = [item for item in items if item.max_tp_hit >= 2]
    stopped = [item for item in items if item.stop_hit]
    return {
        "count": len(items),
        "avg_mfe_r": round(mean(item.mfe_r for item in items), 4),
        "avg_mae_r": round(mean(item.mae_r for item in items), 4),
        "avg_final_r": round(mean(item.final_r for item in items), 4),
        "tp1_touch_rate": round(sum(item.max_tp_hit >= 1 for item in items) / len(items), 4),
        "tp2_touch_rate": round(len(tp2) / len(items), 4),
        "stop_hit_rate": round(len(stopped) / len(items), 4),
        "false_negative_rate_tp2": round(len(tp2) / len(items), 4),
    }


def write_outputs(results: list[ReplayResult], output_dir: Path, *, start: str, end: str, min_score: float, horizon_bars: int) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary = summarize_results(results)
    payload = {
        "assumptions": {
            "start": start,
            "end": end,
            "min_score": min_score,
            "horizon_bars": horizon_bars,
            "entry": "logged closed 15m kline close",
            "stop": "logged entry_context.stop_pct",
            "tp_levels_r": list(TP_LEVELS),
            "mode": "offline replay; not live-executable and intentionally uses future bars",
        },
        "summary": summary,
        "results": [asdict(item) for item in results],
    }
    (output_dir / "high_score_intercept_replay.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "high_score_intercept_replay.md").write_text(render_markdown(payload), encoding="utf-8")


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    assumptions = payload["assumptions"]
    lines = [
        "# High-Score Intercept Replay Report",
        "",
        f"Window: {assumptions['start']} to {assumptions['end']}",
        f"Min score: {assumptions['min_score']}",
        f"Horizon bars: {assumptions['horizon_bars']} closed 15m bars",
        "",
        "This is offline attribution and intentionally uses future bars. It must not be used as live entry logic.",
        "",
        "## Overall",
        "",
        markdown_table(summary["overall"]),
        "",
        "## By Primary Reason",
        "",
        markdown_group(summary["by_primary_reason"]),
        "",
        "## By Symbol",
        "",
        markdown_group(summary["by_symbol"]),
        "",
        "## By Side",
        "",
        markdown_group(summary["by_side"]),
        "",
    ]
    return "\n".join(lines)


def markdown_group(group: dict[str, dict[str, Any]]) -> str:
    rows = []
    for name, stats in group.items():
        row = {"name": name, **stats}
        rows.append(row)
    return markdown_rows(rows)


def markdown_table(stats: dict[str, Any]) -> str:
    return markdown_rows([stats])


def markdown_rows(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "_No rows._"
    keys = list(rows[0].keys())
    lines = ["| " + " | ".join(keys) + " |", "| " + " | ".join("---" for _ in keys) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(key, "")) for key in keys) + " |")
    return "\n".join(lines)


def _float(value: Any, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _int(value: Any, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay high-score intercepted entry-chain signals.")
    parser.add_argument("--log-root", default="logs")
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--min-score", type=float, default=85.0)
    parser.add_argument("--horizon-bars", type=int, default=96)
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = load_decision_rows(Path(args.log_root), args.start, args.end)
    results = replay_all(rows, args.min_score, args.horizon_bars)
    write_outputs(results, Path(args.output_dir), start=args.start, end=args.end, min_score=args.min_score, horizon_bars=args.horizon_bars)
    print(json.dumps({"rows": len(rows), "replayed": len(results), "output_dir": args.output_dir}, ensure_ascii=False))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_replay_high_score_intercepts.py -q`

Expected: PASS.

- [ ] **Step 5: Run real 14-day replay**

Run:

```powershell
python scripts/replay_high_score_intercepts.py --log-root logs --start 2026-06-30 --end 2026-07-13 --min-score 85 --horizon-bars 96 --output-dir reports/structured_offense/2026-07-13
```

Expected: command prints JSON with nonzero `rows` and `replayed`, and writes:
- `reports/structured_offense/2026-07-13/high_score_intercept_replay.json`
- `reports/structured_offense/2026-07-13/high_score_intercept_replay.md`

### Task 2: DeepSeek Report Addendum

**Files:**
- Modify: `docs/superpowers/reports/2026-07-13-last14d-offense-effect-attribution-deepseek-review.md`

**Interfaces:**
- Consumes: `reports/structured_offense/2026-07-13/high_score_intercept_replay.md`
- Produces: a short addendum section that points DeepSeek to the new replay artifact.

- [ ] **Step 1: Add an addendum section**

Append a section titled `## 11. 第八次评审后新增证据包` with:

```markdown
## 11. 第八次评审后新增证据包

根据 DeepSeek 第八次评审，已新增离线“高分拦截信号回放器”。该回放器只用于事后归因，明确使用未来 K 线，不参与实盘决策。

输出文件：

- `reports/structured_offense/2026-07-13/high_score_intercept_replay.md`
- `reports/structured_offense/2026-07-13/high_score_intercept_replay.json`

该证据包用于回答三个问题：

1. `SIDE_THRESHOLD_OFFSET_LONG_10.00` 是否误伤高分 LONG 趋势延续；
2. `FIB_EXTENSION_EXHAUSTION_BLOCK` 是否误伤顺势突破；
3. RR gap 拦截后的真实 MFE/MAE 是否支持继续硬拦截。
```

- [ ] **Step 2: Verify links and generated artifacts**

Run:

```powershell
Test-Path reports/structured_offense/2026-07-13/high_score_intercept_replay.md
Test-Path reports/structured_offense/2026-07-13/high_score_intercept_replay.json
rg -n "第八次评审后新增证据包|high_score_intercept_replay" docs/superpowers/reports/2026-07-13-last14d-offense-effect-attribution-deepseek-review.md
```

Expected: both `Test-Path` calls print `True`; `rg` finds the addendum.

---

## Deferred Tasks Requiring Separate Review

- Main-account `trend_capture` A/B: requires behavior/config change and should be reviewed before deployment.
- Dynamic symbol pool mutation: requires explicit promotion/demotion policy approval.
- `net_beta_exposure_model`: should be a separate risk-model implementation plan with tests and stress fixtures.
