"""probe 成本超时自适应（P1-4）守卫。

## 问题（有直接证据）

2026-11-14 起 47 笔里 `main_probe` 占 19 笔、净 −129.23、胜率 10.5%，其中 **12 笔**由
`COST_BREAKEVEN_TIMEOUT` 平掉。probe 的风险预算只有 15 USDT，而 20bps 往返成本占
**0.19R**（stop_pct≈1.05%）；超时规则却是固定的 `max_hold_bars // 4 = 8` 根。
于是"仓位越小 → 成本占比越高 → 越容易被固定窗口扫平"，这是**规则对仓位规模不公平**，
不是 probe 信号差。

## 修法

`adaptive_cost_timeout_bars` 按成本占 R 的比例放大窗口：

    cost_R     = (20bps) / stop_pct
    extra_bars = round((cost_R / 0.19 − 1) × 8)
    timeout    = clamp(8 + extra_bars, 8, 16)

**只对 `action == "PROBE"` 生效，且开关默认关闭**。关闭时仓位落 `cost_timeout_bars=0`，
调用方回落到 `max_hold_bars // 4` —— 与引入本功能之前逐位一致。

本文件锁四件事：
1. 公式边界（0.19 → 8 根、0.38 → 16 根、宽止损 → 8 根下限，绝不收紧）；
2. 只对 PROBE 生效（DIRECT 不动）；
3. 默认关闭时仓位不带自适应值（向后兼容：旧状态文件没有该字段也一样）；
4. 端到端：同一段平坦行情下，关闭时第 8 根被 `COST_BREAKEVEN_TIMEOUT` 平掉，
   打开后 probe 仓位挺到第 16 根。
"""

from __future__ import annotations

import json

import pytest

from src.observability.paper_trading import (
    COST_BREAKEVEN_CHECK_BARS,
    PaperTradingLedger,
    _position_cost_timeout_bars,
    _resolve_cost_timeout_bars,
    adaptive_cost_timeout_bars,
)
from src.signals.entry_chain_config import EntryChainConfig, load_entry_chain_config


# ---------------------------------------------------------------- 公式


@pytest.mark.parametrize(
    ("stop_pct", "expected_cost_r", "expected_bars"),
    [
        (0.010526, 0.19, 8),   # probe 典型（20bps/0.0105 = 0.19）→ 不变
        (0.005, 0.40, 16),     # 窄止损：成本占 0.4R → 顶到 16 根上限
        (0.0105, 0.1905, 8),
        (0.008, 0.25, 11),     # 0.25/0.19 → +2.5 根 → 8+2=10? 见下（四舍五入到 11）
        (0.020, 0.10, 8),      # 宽止损 → 低于典型值，但**只会放宽**，仍 8 根
        (0.040, 0.05, 8),
    ],
)
def test_adaptive_timeout_formula(stop_pct: float, expected_cost_r: float, expected_bars: int) -> None:
    cost_r = (20.0 / 10000.0) / stop_pct
    assert cost_r == pytest.approx(expected_cost_r, abs=5e-3)
    assert adaptive_cost_timeout_bars(stop_pct) == expected_bars


def test_adaptive_timeout_never_shrinks_below_default() -> None:
    """只会放宽：任何宽止损（cost_R 很小）都不得低于默认 8 根。"""
    for stop_pct in (0.02, 0.03, 0.04, 0.1, 0.5):
        assert adaptive_cost_timeout_bars(stop_pct) == COST_BREAKEVEN_CHECK_BARS


def test_adaptive_timeout_is_monotone_non_increasing_in_stop_pct() -> None:
    """止损越窄（成本占比越高）→ 允许的根数越多。"""
    bars = [adaptive_cost_timeout_bars(0.030 - i * 0.001) for i in range(26)]
    assert all(later >= earlier for earlier, later in zip(bars, bars[1:])), "单调性被破坏"


def test_adaptive_timeout_caps_at_sixteen_bars() -> None:
    assert adaptive_cost_timeout_bars(0.001) == 16
    assert adaptive_cost_timeout_bars(0.0001) == 16


def test_adaptive_timeout_degenerate_stop_pct_falls_back_to_default() -> None:
    for stop_pct in (0.0, -0.01, None):
        assert adaptive_cost_timeout_bars(stop_pct) == COST_BREAKEVEN_CHECK_BARS


# ---------------------------------------------------------------- 只对 PROBE 生效


def test_resolution_only_applies_to_probe_and_only_when_enabled() -> None:
    assert _resolve_cost_timeout_bars(action="PROBE", stop_pct=0.005, adaptive_enabled=True) == 16
    assert _resolve_cost_timeout_bars(action="DIRECT", stop_pct=0.005, adaptive_enabled=True) == 0
    assert _resolve_cost_timeout_bars(action="PROBE", stop_pct=0.005, adaptive_enabled=False) == 0
    assert _resolve_cost_timeout_bars(action="", stop_pct=0.005, adaptive_enabled=True) == 0


def test_position_level_timeout_falls_back_to_global_default() -> None:
    class _Pos:
        def __init__(self, bars: int) -> None:
            self.cost_timeout_bars = bars

    assert _position_cost_timeout_bars(_Pos(0), 32) == 8       # 未设置 → max_hold//4
    assert _position_cost_timeout_bars(_Pos(16), 32) == 16     # 仓位自带值优先
    assert _position_cost_timeout_bars(_Pos(0), 4) == 1        # 下限保护（max_hold 太小时）


def test_default_config_switch_is_off() -> None:
    assert EntryChainConfig().probe_cost_timeout_adaptive is False
    assert load_entry_chain_config("configs/entry_chain.dry_run_regime_shadow.json").probe_cost_timeout_adaptive is False


# ---------------------------------------------------------------- 端到端


def _payload(action: str, *, adaptive: bool) -> tuple[dict, dict]:
    decision = {
        "action": action,
        "side": "LONG",
        "score": 80,
        "leverage": 2,
        # atr_pct × ATR_STOP_MULT(1.5) = 0.005 → 成本占 R = 0.4 → 自适应 16 根
        "entry_context": {"atr_pct": 0.005 / 1.5},
        "reasons": ["TEST"],
    }
    if adaptive:
        decision["probe_cost_timeout_adaptive"] = True
    draft = {"approved": True, "request": {"position_side": "LONG", "quantity": 10, "price": 100}}
    return decision, draft


def _flat_kline() -> dict:
    return {"close": 100, "high": 100, "low": 100}


def _drive(ledger: PaperTradingLedger, action: str, *, adaptive: bool, bars: int = 20) -> list[str]:
    decision, draft = _payload(action, adaptive=adaptive)
    ledger.on_decision(symbol="XUSDT", decision_payload=decision, draft_payload=draft, kline=_flat_kline(), timestamp=1000)
    fired: list[str] = []
    for step in range(1, bars + 1):
        events = ledger.on_decision(
            symbol="XUSDT",
            decision_payload={"action": "NO_TRADE"},
            draft_payload={"approved": False},
            kline=_flat_kline(),
            timestamp=1000 + step * 900,
        )
        fired.extend(events)
        if not ledger.positions:
            break
    return fired


def test_adaptive_off_keeps_default_eight_bars(tmp_path) -> None:
    ledger = PaperTradingLedger(tmp_path)
    events = _drive(ledger, "PROBE", adaptive=False)
    assert ledger.positions == {}
    assert events and events[-1].startswith("PAPER_CLOSE:XUSDT:COST_BREAKEVEN_TIMEOUT")
    # 第 8 根触发（open 之后第 8 次更新）
    row = [json.loads(line) for line in (tmp_path / "paper_trades.jsonl").read_text(encoding="utf-8").splitlines()][-1]
    assert row["event"] == "PAPER_CLOSE"
    assert (row["timestamp"] - 1000) // 900 == 8


def test_adaptive_on_extends_probe_timeout_to_sixteen_bars(tmp_path) -> None:
    ledger = PaperTradingLedger(tmp_path)
    events = _drive(ledger, "PROBE", adaptive=True)
    assert ledger.positions == {}
    assert events and events[-1].startswith("PAPER_CLOSE:XUSDT:COST_BREAKEVEN_TIMEOUT")
    position_rows = [json.loads(line) for line in (tmp_path / "paper_trades.jsonl").read_text(encoding="utf-8").splitlines()]
    close_row = position_rows[-1]
    assert (close_row["timestamp"] - 1000) // 900 == 16, "自适应没有把窗口拉到 16 根"


def test_adaptive_switch_does_not_touch_direct_positions(tmp_path) -> None:
    """DIRECT 即使打开开关也按默认 8 根走（没有"被固定窗口扫平"的证据）。"""
    ledger = PaperTradingLedger(tmp_path)
    events = _drive(ledger, "DIRECT", adaptive=True)
    assert events and events[-1].startswith("PAPER_CLOSE:XUSDT:COST_BREAKEVEN_TIMEOUT")
    position_rows = [json.loads(line) for line in (tmp_path / "paper_trades.jsonl").read_text(encoding="utf-8").splitlines()]
    assert (position_rows[-1]["timestamp"] - 1000) // 900 == 8


def test_legacy_state_file_without_new_fields_still_loads(tmp_path) -> None:
    """向后兼容：旧 `paper_positions.json` 没有 `action` / `cost_timeout_bars`，
    加载后必须回落到"全局默认 8 根"而不是崩掉或变成 0 根。"""
    state = {
        "XUSDT": {
            "symbol": "XUSDT",
            "side": "LONG",
            "entry_time": 1000,
            "entry_price": 100.0,
            "quantity": 10.0,
            "notional": 1000.0,
            "leverage": 2,
            "stop_price": 99.5,
            "tp_prices": [100.6, 101.0, 101.5],
            "tp_fractions": [0.4, 0.35, 0.25],
            "tp_consumed": [],
            "remaining_fraction": 1.0,
            "realized_pnl": 0.0,
            "realized_margin_pnl": 0.0,
            "entry_fee": 0.0,
            "entry_slippage": 0.0,
            "last_price": 100.0,
            "best_price": 100.0,
            "max_favorable_r_observed": 0.0,
            "hold_bars": 0,
            "last_processed_kline_ts": 1000,
            "score": 80.0,
            "reasons": [],
            "position_id": "XUSDT:1000:LONG",
        }
    }
    (tmp_path / "paper_positions.json").write_text(json.dumps(state), encoding="utf-8")
    ledger = PaperTradingLedger(tmp_path)
    position = ledger.positions["XUSDT"]
    assert position.action == ""
    assert position.cost_timeout_bars == 0
    assert _position_cost_timeout_bars(position, 32) == 8
