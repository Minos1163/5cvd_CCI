# VPS Dry Run Strategy Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the hardened entry-chain strategy safe and observable enough to run continuously on a VPS in dry-run mode.

**Architecture:** Keep `src.signals.entry_chain` as the public compatibility facade, then move configuration, gate evaluation, scoring, portfolio state, feature derivation, audit logging, and dry-run orchestration into focused modules. VPS dry-run will produce decisions, rejected gate records, and order drafts only; it will not submit, cancel, or amend exchange orders.

**Tech Stack:** Python dataclasses, stdlib JSON/CSV/YAML-compatible config parsing, pytest, existing Binance data access, existing execution pre-check contract.

---

## Safety Assumptions

- Dry-run means no real orders and no exchange mutation.
- Do not modify `src/api/binance_client.py`.
- Do not store API keys, tokens, or secrets in repo files.
- Dry-run can run with public market data only; if private account snapshots are later needed, credentials must be supplied by VPS environment variables outside the repo.
- The first VPS deployment target is observability and decision quality, not live profitability.

## Current Problems To Fix Before VPS Dry-Run

- `src/signals/entry_chain.py` is already becoming a mixed-responsibility module.
- Portfolio state is implicit in `scripts/run_offline_backtest.py`.
- Gate rejection reasons are buried in signal payloads and are not exported as first-class CSV/JSONL artifacts.
- Live-safe order drafts exist, but there is no dry-run runner that loops, evaluates, logs, and health-checks continuously.
- Configuration is hard-coded in dataclass defaults, making VPS tuning risky.
- The current backtest engine is symbol-sequential; this limitation must be logged in reports until a time-synchronized engine is implemented.

## File Structure

- Modify: `src/signals/entry_chain.py`
  - Keep public imports stable: `EntryChainConfig`, `EntryChainContext`, `EntryChainDecision`, `evaluate_entry_chain`, `dynamic_weights`.
  - Delegate implementation to focused modules.
- Create: `src/signals/entry_chain_config.py`
  - Owns config dataclass and `from_mapping` / `from_json_file`.
- Create: `src/signals/entry_chain_scoring.py`
  - Owns score components, base weights, dynamic weights, component point calculation.
- Create: `src/signals/entry_chain_gates.py`
  - Owns hard gate and downgrade decisions.
- Create: `src/signals/portfolio_state.py`
  - Owns explicit dry-run/backtest state: daily trade counts, symbol cooldowns, active symbol count, exposures, rolling trade returns.
- Create: `src/signals/entry_chain_features.py`
  - Owns no-lookahead OHLCV feature derivation for backtest/dry-run.
- Create: `src/observability/decision_audit.py`
  - Owns JSONL audit writer and gate rejection CSV writer.
- Create: `configs/entry_chain.dry_run.json`
  - Conservative VPS dry-run config.
- Modify: `scripts/run_offline_backtest.py`
  - Use `PortfolioState`, `entry_chain_features`, and `decision_audit`.
  - Write `gate_rejections.csv`.
- Create: `scripts/run_live_dry_run.py`
  - Continuous dry-run loop; evaluates symbols, builds live order drafts, logs JSONL, never submits orders.
- Create: `scripts/vps_dry_run_healthcheck.py`
  - Validates config, writable log dirs, importability, and dry-run safety flags.
- Create: `deploy/systemd/ai300-dry-run.service`
  - Example systemd unit with no secrets embedded.
- Create: `docs/runbooks/vps_dry_run.md`
  - VPS deployment and rollback instructions.
- Create/Modify Tests:
  - `tests/test_entry_chain_config.py`
  - `tests/test_entry_chain_scoring.py`
  - `tests/test_entry_chain_gates.py`
  - `tests/test_portfolio_state.py`
  - `tests/test_entry_chain_features.py`
  - `tests/test_decision_audit.py`
  - `tests/test_live_dry_run.py`

## Acceptance Criteria

- `pytest tests/test_entry_chain.py tests/test_entry_chain_config.py tests/test_entry_chain_scoring.py tests/test_entry_chain_gates.py tests/test_portfolio_state.py tests/test_entry_chain_features.py tests/test_decision_audit.py tests/test_live_dry_run.py -q` passes.
- `python -m compileall src scripts tests` passes.
- `python scripts/vps_dry_run_healthcheck.py --config configs/entry_chain.dry_run.json` exits `0`.
- `python scripts/run_live_dry_run.py --config configs/entry_chain.dry_run.json --once --output-dir reports/dry_run/local_smoke` writes:
  - `decisions.jsonl`
  - `order_drafts.jsonl`
  - `gate_rejections.csv`
  - `health.json`
- No dry-run path calls `ExecutionEngine.submit_order`.
- `git diff -- src/api/binance_client.py` is empty.

## Task 1: Config Extraction

**Files:**
- Create: `src/signals/entry_chain_config.py`
- Modify: `src/signals/entry_chain.py`
- Create: `configs/entry_chain.dry_run.json`
- Test: `tests/test_entry_chain_config.py`

- [ ] **Step 1: Write failing config tests**

```python
from pathlib import Path

from src.signals.entry_chain_config import EntryChainConfig, load_entry_chain_config


def test_load_entry_chain_config_from_json(tmp_path):
    path = tmp_path / "entry_chain.json"
    path.write_text('{"direct_threshold": 86, "daily_max_trades_base": 2}', encoding="utf-8")

    config = load_entry_chain_config(path)

    assert isinstance(config, EntryChainConfig)
    assert config.direct_threshold == 86
    assert config.daily_max_trades_base == 2
    assert config.probe_threshold == 70.0


def test_dry_run_config_is_conservative_and_parseable():
    config = load_entry_chain_config(Path("configs/entry_chain.dry_run.json"))

    assert config.direct_threshold >= 85
    assert config.daily_max_trades_base <= 3
    assert config.max_active_symbols <= 5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_entry_chain_config.py -q`

Expected: FAIL because `entry_chain_config.py` does not exist.

- [ ] **Step 3: Implement config module**

Move `EntryChainConfig` into `src/signals/entry_chain_config.py` and expose:

```python
from __future__ import annotations

import json
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class EntryChainConfig:
    direct_threshold: float = 82.0
    probe_threshold: float = 70.0
    watch_threshold: float = 60.0
    min_direction_direct_score: float = 0.64
    min_quality_direct_score: float = 0.73
    min_trigger_direct_score: float = 0.92
    min_cvd_direct_score: float = 0.61
    min_direction_probe_score: float = 0.56
    min_quality_probe_score: float = 0.45
    min_trigger_probe_score: float = 0.67
    min_cvd_probe_score: float = 0.45
    high_vol_atr_pct: float = 0.035
    low_vol_atr_pct: float = 0.010
    macro_daily_drop_block_pct: float = -0.05
    macro_weekly_drop_block_pct: float = -0.15
    direct_liquidity_ratio: float = 20.0
    probe_liquidity_ratio: float = 8.0
    max_active_symbols: int = 5
    daily_max_trades_base: int = 4
    max_symbol_trades_per_day: int = 1
    max_same_direction_exposure_pct: float = 1.20
    max_total_exposure_pct: float = 1.50
    margin_buffer_pct: float = 0.20
    base_direct_exposure_pct: float = 0.20
    max_large_cap_exposure_pct: float = 0.30
    max_mainstream_exposure_pct: float = 0.20
    max_high_beta_exposure_pct: float = 0.10
    probe_fraction: float = 0.25
    direct_risk_pct: float = 0.008
    probe_risk_pct: float = 0.003
    min_stop_pct: float = 0.005
    max_stop_pct: float = 0.04

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "EntryChainConfig":
        allowed = {item.name for item in fields(cls)}
        unknown = sorted(set(data) - allowed)
        if unknown:
            raise ValueError(f"unknown entry-chain config keys: {unknown}")
        return cls(**{key: data[key] for key in data if key in allowed})


def load_entry_chain_config(path: str | Path) -> EntryChainConfig:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("entry-chain config must be a JSON object")
    return EntryChainConfig.from_mapping(payload)
```

- [ ] **Step 4: Add dry-run config**

Create `configs/entry_chain.dry_run.json`:

```json
{
  "direct_threshold": 86.0,
  "probe_threshold": 74.0,
  "watch_threshold": 62.0,
  "daily_max_trades_base": 3,
  "max_symbol_trades_per_day": 1,
  "max_active_symbols": 5,
  "direct_risk_pct": 0.006,
  "probe_risk_pct": 0.0025,
  "max_total_exposure_pct": 1.2,
  "max_same_direction_exposure_pct": 0.9,
  "margin_buffer_pct": 0.30
}
```

- [ ] **Step 5: Preserve compatibility**

`src/signals/entry_chain.py` must import and re-export `EntryChainConfig`:

```python
from src.signals.entry_chain_config import EntryChainConfig
```

- [ ] **Step 6: Verify**

Run: `pytest tests/test_entry_chain.py tests/test_entry_chain_config.py -q`

Expected: PASS.

## Task 2: Scoring And Gate Split

**Files:**
- Create: `src/signals/entry_chain_scoring.py`
- Create: `src/signals/entry_chain_gates.py`
- Modify: `src/signals/entry_chain.py`
- Test: `tests/test_entry_chain_scoring.py`
- Test: `tests/test_entry_chain_gates.py`

- [ ] **Step 1: Write scoring tests**

```python
from src.signals.entry_chain_config import EntryChainConfig
from src.signals.entry_chain_scoring import component_points, dynamic_weights


def test_dynamic_weight_boundaries_do_not_switch_at_exact_thresholds():
    config = EntryChainConfig()

    high_edge, high_reasons = dynamic_weights(config.high_vol_atr_pct, config)
    low_edge, low_reasons = dynamic_weights(config.low_vol_atr_pct, config)

    assert high_edge["volatility_stop"] == 10.0
    assert low_edge["trigger_15m"] == 12.0
    assert high_reasons == []
    assert low_reasons == []


def test_component_points_clamps_inputs_and_weights_sum_to_100():
    weights, _ = dynamic_weights(0.04, EntryChainConfig())
    points = component_points({"direction_1h": 2.0, "quality_30m": -1.0}, weights)

    assert round(sum(weights.values()), 6) == 100.0
    assert points["direction_1h"] == weights["direction_1h"]
    assert points["quality_30m"] == 0.0
```

- [ ] **Step 2: Write gate interaction tests**

```python
from src.signals.entry_chain import EntryChainContext
from src.signals.entry_chain_config import EntryChainConfig
from src.signals.entry_chain_gates import hard_block_reason


def context(**overrides):
    values = {
        "symbol": "HYPEUSDT",
        "timestamp": 100,
        "side": "LONG",
        "component_scores": {},
        "quote_volume_24h": 10_000_000,
        "atr_pct": 0.04,
        "expected_order_size": 1_000,
        "account_equity": 10_000,
        "available_margin": 8_000,
        "macro_weekly_drop_pct": -0.16
    }
    values.update(overrides)
    return EntryChainContext(**values)


def test_weekly_risk_overrides_other_conditions():
    assert hard_block_reason(context(), EntryChainConfig()) == "MACRO_WEEKLY_RISK"
```

- [ ] **Step 3: Run tests to verify failure**

Run: `pytest tests/test_entry_chain_scoring.py tests/test_entry_chain_gates.py -q`

Expected: FAIL because modules do not exist.

- [ ] **Step 4: Implement split modules**

Move these functions out of `entry_chain.py`:

- `dynamic_weights`
- `component_points`
- `hard_block_reason`
- `daily_max_trades`
- `liquidity_ratio`
- `symbol_exposure_cap`
- `score_to_action`
- `apply_component_minimums`
- `select_leverage`
- `notional_hint`

Keep wrapper names in `entry_chain.py` only if needed for compatibility.

- [ ] **Step 5: Verify**

Run: `pytest tests/test_entry_chain.py tests/test_entry_chain_scoring.py tests/test_entry_chain_gates.py -q`

Expected: PASS.

## Task 3: Explicit Portfolio State

**Files:**
- Create: `src/signals/portfolio_state.py`
- Modify: `scripts/run_offline_backtest.py`
- Test: `tests/test_portfolio_state.py`

- [ ] **Step 1: Write state tests**

```python
from src.signals.portfolio_state import PortfolioState


def test_portfolio_state_tracks_daily_and_symbol_budget_by_utc_day():
    state = PortfolioState()
    ts = 1_766_000_000

    state.record_entry("SOLUSDT", ts, "LONG", 500)

    assert state.portfolio_trades_today(ts) == 1
    assert state.symbol_trades_today("SOLUSDT", ts) == 1
    assert state.symbol_trades_today("BNBUSDT", ts) == 0


def test_symbol_cooldown_is_timestamp_based_and_symbol_specific():
    state = PortfolioState()
    state.start_cooldown("SOLUSDT", until_ts=1_000)

    assert state.cooldown_until("SOLUSDT") == 1_000
    assert state.cooldown_until("BNBUSDT") is None
    assert state.is_cooldown_active("SOLUSDT", 999) is True
    assert state.is_cooldown_active("SOLUSDT", 1_000) is False


def test_rolling_sharpe_defaults_to_none_until_enough_trades():
    state = PortfolioState()
    for pnl in [1, -1, 2]:
        state.record_trade_return(pnl)

    assert state.rolling_sharpe_20() is None
```

- [ ] **Step 2: Run test to verify failure**

Run: `pytest tests/test_portfolio_state.py -q`

Expected: FAIL because `PortfolioState` does not exist.

- [ ] **Step 3: Implement state object**

Implement:

```python
@dataclass
class PortfolioState:
    trades_by_day: dict[int, int] = field(default_factory=dict)
    symbol_trades_by_day: dict[tuple[str, int], int] = field(default_factory=dict)
    cooldown_until_by_symbol: dict[str, int] = field(default_factory=dict)
    active_symbols: set[str] = field(default_factory=set)
    same_direction_exposure: dict[str, float] = field(default_factory=dict)
    symbol_exposure: dict[str, float] = field(default_factory=dict)
    trade_returns: list[float] = field(default_factory=list)
```

Methods:

- `day_key(ts) -> int`
- `record_entry(symbol, ts, side, notional) -> None`
- `portfolio_trades_today(ts) -> int`
- `symbol_trades_today(symbol, ts) -> int`
- `start_cooldown(symbol, until_ts) -> None`
- `cooldown_until(symbol) -> int | None`
- `is_cooldown_active(symbol, ts) -> bool`
- `rolling_sharpe_20() -> float | None`

- [ ] **Step 4: Replace script-local dicts**

In `scripts/run_offline_backtest.py`, replace local `state: dict[str, Any]` with `PortfolioState`.

- [ ] **Step 5: Verify**

Run: `pytest tests/test_portfolio_state.py tests/test_entry_chain.py -q`

Expected: PASS.

## Task 4: No-Lookahead Feature Module

**Files:**
- Create: `src/signals/entry_chain_features.py`
- Modify: `scripts/run_offline_backtest.py`
- Test: `tests/test_entry_chain_features.py`

- [ ] **Step 1: Write feature tests**

```python
from src.backtest.engine import BacktestBar
from src.signals.entry_chain_features import completed_bars, direction_from_history, trigger_score


def bar(ts, close, open_=None):
    return BacktestBar("SOLUSDT", ts, open_ if open_ is not None else close, close + 1, close - 1, close, 10)


def test_completed_bars_never_returns_future_timestamp():
    bars = [bar(100, 10), bar(200, 11), bar(300, 12)]

    result = completed_bars(bars, 200)

    assert [item.timestamp for item in result] == [100, 200]


def test_direction_from_history_uses_completed_history_only():
    bars = [bar(100, 100), bar(200, 100.2), bar(300, 100.5), bar(400, 101.0)]

    assert direction_from_history(bars) == "LONG"


def test_trigger_score_is_side_symmetric():
    long_bars = [bar(100, 100), bar(200, 100.1), bar(300, 100.4)]
    short_bars = [bar(100, 100), bar(200, 99.9), bar(300, 99.5)]

    assert trigger_score("LONG", long_bars) == 1.0
    assert trigger_score("SHORT", short_bars) == 1.0
```

- [ ] **Step 2: Run test to verify failure**

Run: `pytest tests/test_entry_chain_features.py -q`

Expected: FAIL because module does not exist.

- [ ] **Step 3: Move feature helpers**

Move these helpers out of `scripts/run_offline_backtest.py`:

- `_completed_bars`
- `_direction_from_history`
- `_component_scores`
- `_agreement_score`
- `_trigger_score`
- `_volume_flow_score`
- `_atr_pct`
- `_quote_volume`
- `_wick_anomaly`

Expose public names without leading underscores.

- [ ] **Step 4: Verify**

Run: `pytest tests/test_entry_chain_features.py -q`

Expected: PASS.

## Task 5: Decision Audit And Gate Rejection Report

**Files:**
- Create: `src/observability/decision_audit.py`
- Modify: `scripts/run_offline_backtest.py`
- Test: `tests/test_decision_audit.py`

- [ ] **Step 1: Write audit tests**

```python
import csv
import json

from src.observability.decision_audit import DecisionAuditWriter


def test_decision_audit_writer_outputs_jsonl_and_gate_csv(tmp_path):
    writer = DecisionAuditWriter(tmp_path)
    writer.write_decision({
        "timestamp": 1,
        "symbol": "SOLUSDT",
        "action": "NO_TRADE",
        "score": 58,
        "reasons": ["PROBE_COMPONENT_MINIMUM_FAILED"],
    })
    writer.close()

    json_rows = [json.loads(line) for line in (tmp_path / "decisions.jsonl").read_text().splitlines()]
    csv_rows = list(csv.DictReader((tmp_path / "gate_rejections.csv").open(newline="", encoding="utf-8")))

    assert json_rows[0]["symbol"] == "SOLUSDT"
    assert csv_rows[0]["primary_reason"] == "PROBE_COMPONENT_MINIMUM_FAILED"
```

- [ ] **Step 2: Run test to verify failure**

Run: `pytest tests/test_decision_audit.py -q`

Expected: FAIL because module does not exist.

- [ ] **Step 3: Implement audit writer**

Implement:

```python
class DecisionAuditWriter:
    def __init__(self, output_dir: str | Path) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._decisions = (self.output_dir / "decisions.jsonl").open("a", encoding="utf-8")
        self._drafts = (self.output_dir / "order_drafts.jsonl").open("a", encoding="utf-8")
        self._gate_rows: list[dict[str, object]] = []

    def write_decision(self, row: Mapping[str, object]) -> None:
        ...

    def write_order_draft(self, row: Mapping[str, object]) -> None:
        ...

    def close(self) -> None:
        ...
```

CSV fields:

- `timestamp`
- `symbol`
- `action`
- `score`
- `primary_reason`
- `reasons`

- [ ] **Step 4: Integrate backtest artifact**

In `scripts/run_offline_backtest.py`, after result creation, export `gate_rejections.csv` from `signal_events` / `failed_samples` payloads when `entry_chain` metadata exists.

- [ ] **Step 5: Verify**

Run: `pytest tests/test_decision_audit.py -q`

Expected: PASS.

## Task 6: Live Dry-Run Runner

**Files:**
- Create: `scripts/run_live_dry_run.py`
- Test: `tests/test_live_dry_run.py`

- [ ] **Step 1: Write dry-run tests**

```python
import json
import subprocess
import sys
from pathlib import Path


def test_live_dry_run_once_writes_audit_files(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_live_dry_run.py",
            "--config",
            "configs/entry_chain.dry_run.json",
            "--once",
            "--output-dir",
            str(tmp_path),
            "--symbols",
            "BNBUSDT",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "dry_run_completed" in result.stdout
    assert (tmp_path / "decisions.jsonl").exists()
    assert (tmp_path / "order_drafts.jsonl").exists()
    assert (tmp_path / "gate_rejections.csv").exists()
    health = json.loads((tmp_path / "health.json").read_text(encoding="utf-8"))
    assert health["mode"] == "dry_run"
    assert health["orders_submitted"] == 0
```

- [ ] **Step 2: Run test to verify failure**

Run: `pytest tests/test_live_dry_run.py -q`

Expected: FAIL because script does not exist.

- [ ] **Step 3: Implement dry-run script**

The script must:

- parse `--config`, `--output-dir`, `--symbols`, `--interval-seconds`, `--once`;
- load `EntryChainConfig`;
- create a conservative synthetic/public-data fallback candidate when live market fetch is not configured;
- call `evaluate_entry_chain`;
- call `build_live_entry_order_draft`;
- write `decisions.jsonl`, `order_drafts.jsonl`, `gate_rejections.csv`, `health.json`;
- never instantiate `ExecutionEngine`;
- never call `submit_order`, `cancel_order`, or `sync_position`.

Minimal script behavior for `--once`:

```python
print(json.dumps({"status": "dry_run_completed", "orders_submitted": 0}, ensure_ascii=False))
```

- [ ] **Step 4: Verify no exchange mutation path**

Add test assertion:

```python
source = Path("scripts/run_live_dry_run.py").read_text(encoding="utf-8")
assert "submit_order(" not in source
assert "cancel_order(" not in source
```

- [ ] **Step 5: Verify**

Run: `pytest tests/test_live_dry_run.py -q`

Expected: PASS.

## Task 7: VPS Healthcheck And Systemd Deployment Files

**Files:**
- Create: `scripts/vps_dry_run_healthcheck.py`
- Create: `deploy/systemd/ai300-dry-run.service`
- Create: `docs/runbooks/vps_dry_run.md`
- Test: `tests/test_live_dry_run.py`

- [ ] **Step 1: Write healthcheck test**

Extend `tests/test_live_dry_run.py`:

```python
def test_vps_healthcheck_accepts_dry_run_config():
    result = subprocess.run(
        [
            sys.executable,
            "scripts/vps_dry_run_healthcheck.py",
            "--config",
            "configs/entry_chain.dry_run.json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["dry_run_safe"] is True
```

- [ ] **Step 2: Implement healthcheck**

The healthcheck must validate:

- config parses;
- `src.api.binance_client` is importable but not modified by this task;
- `scripts/run_live_dry_run.py` source does not contain `submit_order(` or `cancel_order(`;
- output directory can be created when supplied.

- [ ] **Step 3: Add systemd unit**

Create `deploy/systemd/ai300-dry-run.service`:

```ini
[Unit]
Description=AI300 dry-run strategy observer
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/opt/ai300
Environment=PYTHONUNBUFFERED=1
ExecStart=/opt/ai300/.venv/bin/python scripts/run_live_dry_run.py --config configs/entry_chain.dry_run.json --output-dir reports/dry_run/vps --interval-seconds 60
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 4: Add runbook**

Create `docs/runbooks/vps_dry_run.md` with:

- clone/update repo;
- create venv;
- install project dependencies;
- run healthcheck;
- run one-shot dry-run;
- install systemd service;
- view logs;
- stop service;
- confirm no real orders are submitted.

- [ ] **Step 5: Verify**

Run:

```powershell
pytest tests/test_live_dry_run.py -q
python scripts/vps_dry_run_healthcheck.py --config configs/entry_chain.dry_run.json
```

Expected: PASS and JSON `{"status": "ok", "dry_run_safe": true, ...}`.

## Task 8: Re-Run Backtest And Dry-Run Smoke

**Files:**
- Inspect: `reports/backtests/latest_30d_round2_entry_chain`
- Create: `reports/dry_run/local_smoke`

- [ ] **Step 1: Run focused tests**

Run:

```powershell
pytest tests/test_entry_chain.py tests/test_entry_chain_config.py tests/test_entry_chain_scoring.py tests/test_entry_chain_gates.py tests/test_portfolio_state.py tests/test_entry_chain_features.py tests/test_decision_audit.py tests/test_live_entry_chain_adapter.py tests/test_live_dry_run.py -q
```

Expected: PASS.

- [ ] **Step 2: Run compile verification**

Run:

```powershell
python -m compileall src scripts tests
```

Expected: PASS.

- [ ] **Step 3: Run offline backtest with dry-run config**

Run:

```powershell
python scripts/run_offline_backtest.py --data-dir data/raw/binance_futures/latest_30d --timeframe 15m --strategy entry-chain --run-id latest_30d_round3_entry_chain_refined
```

Expected: completes and writes `reports/backtests/latest_30d_round3_entry_chain_refined`.

- [ ] **Step 4: Run one-shot dry-run smoke**

Run:

```powershell
python scripts/run_live_dry_run.py --config configs/entry_chain.dry_run.json --once --output-dir reports/dry_run/local_smoke --symbols BNBUSDT,SOLUSDT
```

Expected: writes all dry-run audit files and reports `orders_submitted = 0`.

- [ ] **Step 5: Verify Binance client untouched**

Run:

```powershell
git diff -- src/api/binance_client.py
```

Expected: no output.

## VPS Deployment Commands After Implementation

Run on VPS after code is pushed:

```bash
cd /opt
git clone https://github.com/Minos1163/5cvd_CCI.git ai300
cd /opt/ai300
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
python scripts/vps_dry_run_healthcheck.py --config configs/entry_chain.dry_run.json
python scripts/run_live_dry_run.py --config configs/entry_chain.dry_run.json --once --output-dir reports/dry_run/vps_smoke --symbols BNBUSDT,SOLUSDT
```

Install service only after smoke passes:

```bash
sudo cp deploy/systemd/ai300-dry-run.service /etc/systemd/system/ai300-dry-run.service
sudo systemctl daemon-reload
sudo systemctl enable ai300-dry-run
sudo systemctl start ai300-dry-run
sudo systemctl status ai300-dry-run --no-pager
```

Stop service:

```bash
sudo systemctl stop ai300-dry-run
```

## Self-Review

- Spec coverage: The new review's concerns are mapped to module split, explicit state, no-lookahead features, audit logs, config loading, dry-run safety, and VPS deployment.
- Placeholder scan: Each task has concrete files, tests, commands, and expected output.
- Type consistency: The plan keeps `EntryChainConfig`, `EntryChainContext`, `EntryChainDecision`, and `evaluate_entry_chain` as stable public names.
- Risk review: The plan does not modify `src/api/binance_client.py`, does not add real order submission to dry-run, and requires `orders_submitted = 0` in smoke tests.
