# Dry-Run SCOUT Near-Miss Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a dry-run-only SCOUT / near-miss observation layer that records high-score rejected signals and provides an offline MFE/MAE replay path without changing PROBE/DIRECT entry decisions.

**Architecture:** Keep the existing trading decision path unchanged. Add a side-channel audit file `near_misses.jsonl`, summary counters, and a standalone replay script that reads historical audit logs to calculate hypothetical post-signal MFE/MAE. The first implementation is data collection only; it does not submit orders, open paper positions, or relax risk gates.

**Tech Stack:** Python 3.12, stdlib `json/csv/pathlib/argparse`, pytest, existing `DecisionAuditWriter`, `DryRunSummary`, and `scripts/run_live_dry_run.py`.

## Global Constraints

- This is dry-run instrumentation only; do not change PROBE/DIRECT thresholds or live execution behavior.
- Never introduce lookahead into live entry logic. MFE/MAE replay is offline and reads only past log files after the run.
- SCOUT / near-miss records must not create order requests, approved drafts, paper positions, or main PnL.
- Keep changes surgical and follow existing JSONL logging style.
- Preserve the dirty worktree; do not revert unrelated existing modifications.
- Verification command: `pytest tests/test_decision_audit.py tests/test_dry_run_summary.py tests/test_live_dry_run.py tests/test_replay_near_miss_mfe_mae.py -q`.

---

## File Structure

- Modify `src/observability/decision_audit.py`
  - Add `near_misses.jsonl` writer and `write_near_miss(row)`.
- Modify `src/observability/dry_run_summary.py`
  - Track `near_miss_count`, `near_miss_by_reason`, and `recent_near_misses`.
- Modify `scripts/run_live_dry_run.py`
  - Add CLI args for near-miss threshold.
  - Build near-miss payloads after `decision_payload` is complete.
  - Write near-miss payloads and update summary only when action is `WATCH` or `NO_TRADE` and score is high enough.
- Create `scripts/replay_near_miss_mfe_mae.py`
  - Offline script that reads near misses and decisions, then writes CSV metrics for 0.5h, 1h, 2h, and 4h windows.
- Modify `tests/test_decision_audit.py`
  - Cover near-miss JSONL output.
- Modify `tests/test_dry_run_summary.py`
  - Cover near-miss summary counters.
- Modify `tests/test_live_dry_run.py`
  - Cover `near_misses.jsonl` existence and high-score rejected decision capture.
- Create `tests/test_replay_near_miss_mfe_mae.py`
  - Cover replay MFE/MAE for LONG and SHORT examples.

---

### Task 1: Add Near-Miss Audit Writer

**Files:**
- Modify: `src/observability/decision_audit.py`
- Modify: `tests/test_decision_audit.py`

**Interfaces:**
- Produces: `DecisionAuditWriter.write_near_miss(row: Mapping[str, object]) -> None`
- Produces: `near_misses.jsonl` in the same output directory as `decisions.jsonl`

- [ ] **Step 1: Add failing test**

Add to `tests/test_decision_audit.py`:

```python
def test_decision_audit_writer_outputs_near_misses(tmp_path):
    writer = DecisionAuditWriter(tmp_path)
    writer.write_near_miss(
        {
            "timestamp": 1,
            "symbol": "SOLUSDT",
            "action": "WATCH",
            "score": 86.5,
            "scout_candidate": True,
            "reasons": ["PROBE_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_2.0"],
        }
    )
    writer.close()

    rows = [json.loads(line) for line in (tmp_path / "near_misses.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows == [
        {
            "action": "WATCH",
            "reasons": ["PROBE_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_2.0"],
            "score": 86.5,
            "scout_candidate": True,
            "symbol": "SOLUSDT",
            "timestamp": 1,
        }
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_decision_audit.py::test_decision_audit_writer_outputs_near_misses -q`

Expected: FAIL with `AttributeError: 'DecisionAuditWriter' object has no attribute 'write_near_miss'`.

- [ ] **Step 3: Implement writer**

In `DecisionAuditWriter.__init__`, open the file:

```python
self._near_misses = (self.output_dir / "near_misses.jsonl").open("a", encoding="utf-8")
```

Add method:

```python
def write_near_miss(self, row: Mapping[str, object]) -> None:
    self._near_misses.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")
    self._near_misses.flush()
```

In `close`, close it:

```python
self._near_misses.close()
```

- [ ] **Step 4: Run test**

Run: `pytest tests/test_decision_audit.py::test_decision_audit_writer_outputs_near_misses -q`

Expected: PASS.

---

### Task 2: Track Near-Miss Summary Counts

**Files:**
- Modify: `src/observability/dry_run_summary.py`
- Modify: `tests/test_dry_run_summary.py`

**Interfaces:**
- Produces: `DryRunSummary.record_near_miss(row: Mapping[str, object]) -> None`
- Adds summary keys: `near_miss_count`, `near_miss_by_reason`, `recent_near_misses`

- [ ] **Step 1: Add failing test**

Add to `tests/test_dry_run_summary.py`:

```python
def test_summary_tracks_near_misses():
    summary = DryRunSummary(target_tier="aggressive")
    summary.record_near_miss(
        {
            "timestamp": 1,
            "symbol": "CCUSDT",
            "action": "WATCH",
            "score": 90.59,
            "primary_reason": "HIGH_BETA_PROBE_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_3.0",
        }
    )

    payload = summary.to_dict(orders_submitted=0, data_health="OK")

    assert payload["near_miss_count"] == 1
    assert payload["near_miss_by_reason"] == {"HIGH_BETA_PROBE_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_3.0": 1}
    assert payload["recent_near_misses"] == [
        {
            "timestamp": 1,
            "symbol": "CCUSDT",
            "action": "WATCH",
            "score": 90.59,
            "primary_reason": "HIGH_BETA_PROBE_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_3.0",
        }
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_dry_run_summary.py::test_summary_tracks_near_misses -q`

Expected: FAIL with missing `record_near_miss`.

- [ ] **Step 3: Implement summary fields**

Add dataclass fields:

```python
near_miss_count: int = 0
near_miss_by_reason: Counter = field(default_factory=Counter)
recent_near_misses: deque = field(default_factory=lambda: deque(maxlen=10))
```

Add method:

```python
def record_near_miss(self, row: Mapping[str, object]) -> None:
    primary_reason = str(row.get("primary_reason") or "")
    self.near_miss_count += 1
    if primary_reason:
        self.near_miss_by_reason[primary_reason] += 1
    self.recent_near_misses.append(
        {
            "timestamp": row.get("timestamp"),
            "symbol": row.get("symbol"),
            "action": row.get("action"),
            "score": row.get("score"),
            "primary_reason": primary_reason,
        }
    )
```

Add to `to_dict`:

```python
"near_miss_count": self.near_miss_count,
"near_miss_by_reason": dict(self.near_miss_by_reason),
"recent_near_misses": list(self.recent_near_misses),
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_dry_run_summary.py -q`

Expected: PASS.

---

### Task 3: Integrate Near-Miss Recording Into Dry-Run

**Files:**
- Modify: `scripts/run_live_dry_run.py`
- Modify: `tests/test_live_dry_run.py`

**Interfaces:**
- Produces: `build_near_miss_payload(decision_payload: Mapping[str, Any], *, min_score: float) -> dict[str, Any] | None`
- Adds CLI arg: `--near-miss-min-score`, default `82.0`

- [ ] **Step 1: Add failing unit test**

Add to `tests/test_live_dry_run.py` imports:

```python
    build_near_miss_payload,
```

Add test:

```python
def test_build_near_miss_payload_captures_high_score_rejected_signal():
    payload = build_near_miss_payload(
        {
            "timestamp": 1782992705,
            "symbol": "CCUSDT",
            "action": "WATCH",
            "side": "NONE",
            "score": 90.59,
            "reasons": [
                "FIB_PA_ARCHITECTURE_WEIGHTS",
                "HIGH_BETA_PROBE_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_3.0",
            ],
            "component_points": {
                "risk_reward_geometry": 2.0,
                "fibonacci_location": 18.0,
                "price_action_structure": 21.0,
            },
            "score_detail": {
                "diagnostics": {"risk_reward_geometry": {"net_tp1_r": 1.02}},
            },
            "entry_context": {"atr_pct": 0.01, "side": "SHORT"},
            "kline": {"close": 100.0, "high": 101.0, "low": 99.0, "timestamp": 1782991800},
        },
        min_score=82.0,
    )

    assert payload is not None
    assert payload["scout_candidate"] is True
    assert payload["primary_reason"] == "HIGH_BETA_PROBE_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_3.0"
    assert payload["intended_side"] == "SHORT"
    assert payload["entry_price"] == 100.0
    assert payload["component_points"]["risk_reward_geometry"] == 2.0
    assert payload["diagnostics"]["risk_reward_geometry"]["net_tp1_r"] == 1.02
```

Add test:

```python
def test_build_near_miss_payload_ignores_tradable_or_low_score_decisions():
    assert build_near_miss_payload({"action": "PROBE", "score": 90}, min_score=82.0) is None
    assert build_near_miss_payload({"action": "WATCH", "score": 81.99}, min_score=82.0) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_live_dry_run.py::test_build_near_miss_payload_captures_high_score_rejected_signal tests/test_live_dry_run.py::test_build_near_miss_payload_ignores_tradable_or_low_score_decisions -q`

Expected: FAIL with missing import.

- [ ] **Step 3: Implement payload builder**

Add to `scripts/run_live_dry_run.py`:

```python
def build_near_miss_payload(decision_payload: Mapping[str, Any], *, min_score: float) -> dict[str, Any] | None:
    action = str(decision_payload.get("action") or "").upper()
    if action in {"PROBE", "DIRECT"}:
        return None
    score = float(decision_payload.get("score") or 0.0)
    if score < min_score:
        return None
    reasons = decision_payload.get("reasons", [])
    reason_list = [str(item) for item in reasons] if isinstance(reasons, list) else [str(reasons)]
    primary_reason = next((item for item in reason_list if item != "FIB_PA_ARCHITECTURE_WEIGHTS"), reason_list[0] if reason_list else "")
    kline = decision_payload.get("kline", {}) if isinstance(decision_payload.get("kline"), Mapping) else {}
    entry_context = decision_payload.get("entry_context", {}) if isinstance(decision_payload.get("entry_context"), Mapping) else {}
    score_detail = decision_payload.get("score_detail", {}) if isinstance(decision_payload.get("score_detail"), Mapping) else {}
    return {
        "timestamp": decision_payload.get("timestamp"),
        "symbol": decision_payload.get("symbol"),
        "action": action,
        "score": score,
        "reasons": reason_list,
        "primary_reason": primary_reason,
        "scout_candidate": True,
        "intended_side": str(entry_context.get("side") or decision_payload.get("side") or "NONE").upper(),
        "entry_price": kline.get("close"),
        "kline_timestamp": kline.get("timestamp"),
        "component_points": dict(decision_payload.get("component_points", {})),
        "diagnostics": dict(score_detail.get("diagnostics", {})),
        "entry_context": dict(entry_context),
    }
```

- [ ] **Step 4: Wire it into `run`**

After `summary.record_decision(decision_payload)`, add:

```python
near_miss = build_near_miss_payload(decision_payload, min_score=args.near_miss_min_score)
if near_miss is not None:
    audit.write_near_miss(near_miss)
    summary.record_near_miss(near_miss)
```

In `parse_args`, add:

```python
parser.add_argument("--near-miss-min-score", type=float, default=82.0)
```

- [ ] **Step 5: Add subprocess test**

Add to `tests/test_live_dry_run.py`:

```python
def test_live_dry_run_records_near_miss_jsonl_and_summary(tmp_path):
    subprocess.run(
        [
            sys.executable,
            "scripts/run_live_dry_run.py",
            "--config",
            "configs/entry_chain.dry_run_fib_pa_v1.json",
            "--target-tier",
            "aggressive",
            "--market-data-source",
            "synthetic",
            "--once",
            "--output-dir",
            str(tmp_path),
            "--symbols",
            "SOLUSDT",
            "--near-miss-min-score",
            "0",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    rows = [json.loads(line) for line in (tmp_path / "near_misses.jsonl").read_text(encoding="utf-8").splitlines()]
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert len(rows) == 1
    assert rows[0]["scout_candidate"] is True
    assert rows[0]["action"] in {"WATCH", "NO_TRADE"}
    assert "component_points" in rows[0]
    assert summary["near_miss_count"] == 1
```

- [ ] **Step 6: Run tests**

Run: `pytest tests/test_live_dry_run.py::test_build_near_miss_payload_captures_high_score_rejected_signal tests/test_live_dry_run.py::test_build_near_miss_payload_ignores_tradable_or_low_score_decisions tests/test_live_dry_run.py::test_live_dry_run_records_near_miss_jsonl_and_summary -q`

Expected: PASS.

---

### Task 4: Add Offline MFE/MAE Replay Script

**Files:**
- Create: `scripts/replay_near_miss_mfe_mae.py`
- Create: `tests/test_replay_near_miss_mfe_mae.py`

**Interfaces:**
- Produces CLI:
  - `python scripts/replay_near_miss_mfe_mae.py --near-misses path --decisions path --output path`
- Produces functions:
  - `replay_near_misses(near_misses: list[dict[str, Any]], decisions: list[dict[str, Any]], windows_minutes: Sequence[int]) -> list[dict[str, Any]]`
  - `write_csv(path: str | Path, rows: Sequence[Mapping[str, Any]]) -> None`

- [ ] **Step 1: Add failing tests**

Create `tests/test_replay_near_miss_mfe_mae.py`:

```python
import csv
import json
import subprocess
import sys

from scripts.replay_near_miss_mfe_mae import replay_near_misses


def test_replay_near_misses_calculates_long_mfe_mae():
    near = [{"timestamp": 1000, "symbol": "SOLUSDT", "intended_side": "LONG", "entry_price": 100.0}]
    decisions = [
        {"timestamp": 1000, "symbol": "SOLUSDT", "kline": {"timestamp": 1000, "high": 100.5, "low": 99.5}},
        {"timestamp": 1900, "symbol": "SOLUSDT", "kline": {"timestamp": 1900, "high": 103.0, "low": 98.0}},
        {"timestamp": 2800, "symbol": "SOLUSDT", "kline": {"timestamp": 2800, "high": 104.0, "low": 97.0}},
    ]

    rows = replay_near_misses(near, decisions, windows_minutes=[30])

    assert rows[0]["mfe_30m_pct"] == 0.03
    assert rows[0]["mae_30m_pct"] == -0.02
    assert rows[0]["bars_30m"] == 1


def test_replay_near_misses_calculates_short_mfe_mae():
    near = [{"timestamp": 1000, "symbol": "BNBUSDT", "intended_side": "SHORT", "entry_price": 100.0}]
    decisions = [
        {"timestamp": 1900, "symbol": "BNBUSDT", "kline": {"timestamp": 1900, "high": 102.0, "low": 96.0}},
    ]

    rows = replay_near_misses(near, decisions, windows_minutes=[30])

    assert rows[0]["mfe_30m_pct"] == 0.04
    assert rows[0]["mae_30m_pct"] == -0.02


def test_replay_near_miss_cli_writes_csv(tmp_path):
    near_path = tmp_path / "near_misses.jsonl"
    decisions_path = tmp_path / "decisions.jsonl"
    output_path = tmp_path / "mfe.csv"
    near_path.write_text(json.dumps({"timestamp": 1000, "symbol": "SOLUSDT", "intended_side": "LONG", "entry_price": 100.0}) + "\n", encoding="utf-8")
    decisions_path.write_text(json.dumps({"timestamp": 1900, "symbol": "SOLUSDT", "kline": {"timestamp": 1900, "high": 101.0, "low": 99.0}}) + "\n", encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            "scripts/replay_near_miss_mfe_mae.py",
            "--near-misses",
            str(near_path),
            "--decisions",
            str(decisions_path),
            "--output",
            str(output_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    rows = list(csv.DictReader(output_path.open(newline="", encoding="utf-8")))
    assert rows[0]["symbol"] == "SOLUSDT"
    assert rows[0]["mfe_30m_pct"] == "0.01"
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_replay_near_miss_mfe_mae.py -q`

Expected: FAIL because script is missing.

- [ ] **Step 3: Implement script**

Create `scripts/replay_near_miss_mfe_mae.py` with:

```python
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence


DEFAULT_WINDOWS_MINUTES = (30, 60, 120, 240)


def main() -> None:
    args = parse_args()
    near_misses = read_jsonl(args.near_misses)
    decisions = read_jsonl(args.decisions)
    rows = replay_near_misses(near_misses, decisions, windows_minutes=args.windows_minutes)
    write_csv(args.output, rows)
    print(json.dumps({"status": "ok", "rows": len(rows)}, ensure_ascii=False))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay dry-run near misses and calculate hypothetical MFE/MAE.")
    parser.add_argument("--near-misses", required=True)
    parser.add_argument("--decisions", required=True, nargs="+")
    parser.add_argument("--output", required=True)
    parser.add_argument("--windows-minutes", type=int, nargs="+", default=list(DEFAULT_WINDOWS_MINUTES))
    return parser.parse_args()


def read_jsonl(paths: str | Path | Sequence[str | Path]) -> list[dict[str, Any]]:
    if isinstance(paths, (str, Path)):
        path_list = [paths]
    else:
        path_list = list(paths)
    rows: list[dict[str, Any]] = []
    for path_item in path_list:
        path = Path(path_item)
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                rows.append(json.loads(line))
    return rows


def replay_near_misses(
    near_misses: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    *,
    windows_minutes: Sequence[int] = DEFAULT_WINDOWS_MINUTES,
) -> list[dict[str, Any]]:
    by_symbol: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for decision in decisions:
        symbol = str(decision.get("symbol") or "").upper()
        kline = decision.get("kline")
        if symbol and isinstance(kline, Mapping):
            by_symbol[symbol].append(decision)
    for symbol_rows in by_symbol.values():
        symbol_rows.sort(key=lambda row: int(_timestamp(row)))

    output: list[dict[str, Any]] = []
    for near in near_misses:
        symbol = str(near.get("symbol") or "").upper()
        side = str(near.get("intended_side") or near.get("side") or "").upper()
        entry_price = _float(near.get("entry_price"))
        entry_ts = int(_timestamp(near))
        row = {
            "timestamp": entry_ts,
            "symbol": symbol,
            "side": side,
            "entry_price": entry_price,
            "score": near.get("score"),
            "primary_reason": near.get("primary_reason"),
        }
        if side not in {"LONG", "SHORT"} or entry_price <= 0:
            output.append(row)
            continue
        symbol_decisions = by_symbol.get(symbol, [])
        for minutes in windows_minutes:
            metrics = _window_metrics(symbol_decisions, entry_ts, side, entry_price, minutes)
            suffix = f"{minutes}m"
            row[f"mfe_{suffix}_pct"] = metrics["mfe_pct"]
            row[f"mae_{suffix}_pct"] = metrics["mae_pct"]
            row[f"bars_{suffix}"] = metrics["bars"]
        output.append(row)
    return output


def _window_metrics(decisions: Sequence[Mapping[str, Any]], entry_ts: int, side: str, entry_price: float, minutes: int) -> dict[str, Any]:
    end_ts = entry_ts + minutes * 60
    mfe = 0.0
    mae = 0.0
    bars = 0
    for decision in decisions:
        ts = int(_timestamp(decision))
        if ts <= entry_ts or ts > end_ts:
            continue
        kline = decision.get("kline")
        if not isinstance(kline, Mapping):
            continue
        high = _float(kline.get("high"))
        low = _float(kline.get("low"))
        if high <= 0 or low <= 0:
            continue
        if side == "LONG":
            favorable = (high - entry_price) / entry_price
            adverse = (low - entry_price) / entry_price
        else:
            favorable = (entry_price - low) / entry_price
            adverse = (entry_price - high) / entry_price
        mfe = max(mfe, favorable)
        mae = min(mae, adverse)
        bars += 1
    return {"mfe_pct": round(mfe, 6), "mae_pct": round(mae, 6), "bars": bars}


def write_csv(path: str | Path, rows: Sequence[Mapping[str, Any]]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _timestamp(row: Mapping[str, Any]) -> int:
    kline = row.get("kline")
    if isinstance(kline, Mapping) and kline.get("timestamp") is not None:
        return int(kline.get("timestamp") or 0)
    return int(row.get("timestamp") or row.get("kline_timestamp") or 0)


def _float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run script tests**

Run: `pytest tests/test_replay_near_miss_mfe_mae.py -q`

Expected: PASS.

---

### Task 5: Full Verification

**Files:**
- All files from Tasks 1-4

- [ ] **Step 1: Run targeted tests**

Run:

```powershell
pytest tests/test_decision_audit.py tests/test_dry_run_summary.py tests/test_live_dry_run.py tests/test_replay_near_miss_mfe_mae.py -q
```

Expected: PASS.

- [ ] **Step 2: Run a one-shot dry-run smoke test**

Run:

```powershell
python scripts/run_live_dry_run.py --config configs/entry_chain.dry_run_fib_pa_v1.json --target-tier aggressive --market-data-source synthetic --once --output-dir reports/dry_run/scout_smoke --symbols SOLUSDT --near-miss-min-score 0
```

Expected:

- stdout contains `dry_run_completed`.
- `reports/dry_run/scout_smoke/near_misses.jsonl` exists.
- `reports/dry_run/scout_smoke/summary.json` contains `near_miss_count`.

- [ ] **Step 3: Run replay smoke test**

Run:

```powershell
python scripts/replay_near_miss_mfe_mae.py --near-misses reports/dry_run/scout_smoke/near_misses.jsonl --decisions reports/dry_run/scout_smoke/decisions.jsonl --output reports/dry_run/scout_smoke/near_miss_mfe_mae.csv
```

Expected:

- stdout contains `"status": "ok"`.
- CSV file exists.

