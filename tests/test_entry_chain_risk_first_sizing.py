"""风险优先仓位(risk_first_sizing_enabled)的行为契约。

旧口径:名义 = equity×risk_pct/stop_pct,再被 equity×max_single_trade_risk_pct/(stop_pct×杠杆)
封顶 —— 杠杆越低名义越小,单笔风险与杠杆成反比。
新口径:单笔风险定额 = min(risk_pct, max_single_trade_risk_pct),杠杆只影响保证金占用。
"""

from __future__ import annotations

import dataclasses

from src.signals.entry_chain import EntryChainContext, _notional_cap_diagnostics
from src.signals.entry_chain_config import load_entry_chain_config

CONFIG = "configs/entry_chain.dry_run_fib_pa_v1.json"


def _context(**overrides) -> EntryChainContext:
    scores = {
        "trend_ema_context": 1.0,
        "flow_cvd_confirmation": 1.0,
        "cci_momentum_quality": 1.0,
        "price_action_structure": 1.0,
        "fibonacci_location": 1.0,
        "risk_reward_geometry": 1.0,
        "background_4h": 1.0,
        "direction_1h": 1.0,
        "quality_30m": 1.0,
        "trigger_15m": 1.0,
        "cvd_flow": 1.0,
        "volatility_stop": 1.0,
        "liquidity_execution": 1.0,
        "market_regime": 1.0,
        "ema_200_gate": 1.0,
        "ema_50_quality": 1.0,
        "ema_momentum": 1.0,
    }
    base = dict(
        symbol="BTCUSDT",
        timestamp=1_800_000_000,
        side="LONG",
        component_scores=scores,
        quote_volume_24h=1_000_000_000.0,
        atr_pct=0.02,
        expected_order_size=1000.0,
        account_equity=10_000.0,
        available_margin=8_000.0,
        stop_pct=0.02,
        symbol_exposure_pct=0.0,
    )
    base.update(overrides)
    return EntryChainContext(**base)


def _cfg(**changes):
    base = load_entry_chain_config(CONFIG)
    return dataclasses.replace(base, **changes)


def test_default_mode_keeps_leverage_dependent_notional() -> None:
    """旧口径的既有行为不能被改动:杠杆越低,名义越小。"""
    cfg = _cfg(risk_first_sizing_enabled=False)
    notional_by_leverage = {
        leverage: _notional_cap_diagnostics(
            "DIRECT", 95.0, _context(), cfg, 0.30, selected_leverage=leverage
        )["final_notional"]
        for leverage in (2, 3, 4, 5)
    }
    assert notional_by_leverage[2] > notional_by_leverage[3] > notional_by_leverage[4] > notional_by_leverage[5]
    # 旧公式:equity×0.0075/(stop×leverage) = 3750/leverage
    assert notional_by_leverage[5] == 750.0


def test_risk_first_sizing_is_leverage_invariant() -> None:
    cfg = _cfg(risk_first_sizing_enabled=True)
    diagnostics = {
        leverage: _notional_cap_diagnostics(
            "DIRECT", 95.0, _context(), cfg, 0.30, selected_leverage=leverage
        )
        for leverage in (2, 3, 4, 5)
    }
    notionals = {round(row["final_notional"], 6) for row in diagnostics.values()}
    assert len(notionals) == 1, f"杠杆不应改变名义: {notionals}"
    # 风险定额 0.006 × 10000 = 60,stop 0.02 → 名义 3000(与剩余敞口上限 0.30×10000=3000 打平)
    assert notionals == {3000.0}
    assert diagnostics[3]["binding_cap"] in {"raw_notional", "remaining_exposure_notional"}


def test_risk_first_caps_risk_at_hard_limit() -> None:
    cfg = _cfg(risk_first_sizing_enabled=True, direct_risk_pct=0.02)
    row = _notional_cap_diagnostics(
        "DIRECT", 95.0, _context(symbol_exposure_pct=-10.0), cfg, 0.30, selected_leverage=4
    )
    risk_amount = row["final_notional"] * row["stop_pct"]
    assert risk_amount == 10_000.0 * 0.0075  # 被 max_single_trade_risk_pct 截断


def test_risk_first_uses_margin_cap_when_margin_is_thin() -> None:
    cfg = _cfg(risk_first_sizing_enabled=True)
    row = _notional_cap_diagnostics(
        "DIRECT",
        95.0,
        _context(available_margin=3_500.0, symbol_exposure_pct=-10.0),
        cfg,
        0.30,
        selected_leverage=3,
    )
    # 保证金余量 = 3500 − 10000×0.30 = 500,×3 = 1500 名义 < 风险定额名义 3000
    assert row["leveraged_cap_notional"] == 1500.0
    assert row["binding_cap"] == "leveraged_cap_notional"


def test_risk_first_probe_uses_probe_risk_pct() -> None:
    cfg = _cfg(risk_first_sizing_enabled=True)
    row = _notional_cap_diagnostics(
        "PROBE", 75.0, _context(symbol_exposure_pct=-10.0), cfg, 0.30, selected_leverage=3
    )
    risk_amount = row["final_notional"] * row["stop_pct"]
    assert risk_amount == 10_000.0 * cfg.probe_risk_pct
