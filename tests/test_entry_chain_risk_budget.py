# -*- coding: utf-8 -*-
"""Single-trade risk budget tests."""
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import src.signals.entry_chain as entry_chain  # noqa: E402
from src.signals.entry_chain import EntryChainContext, _decision, _notional_cap_diagnostics, _notional_hint, evaluate_entry_chain  # noqa: E402
from src.signals.entry_chain_config import EntryChainConfig, load_entry_chain_config  # noqa: E402


EQUITY = 10_000.0
DIRECT_SCORE_COMPONENTS = {
    "background_4h": 0.86,
    "direction_1h": 0.86,
    "quality_30m": 0.86,
    "trigger_15m": 1.0,
    "cvd_flow": 0.86,
    "volatility_stop": 0.86,
    "liquidity_execution": 0.86,
    "market_regime": 0.86,
}


def _ctx(
    *,
    stop_pct: float | None,
    symbol_exposure_pct: float = 0.0,
    atr_pct: float = 0.01,
    account_equity: float = EQUITY,
    component_scores: dict[str, float] | None = None,
) -> EntryChainContext:
    return EntryChainContext(
        symbol="TESTUSDT",
        timestamp=0,
        side="SHORT",
        component_scores=component_scores or {},
        quote_volume_24h=1e9,
        atr_pct=atr_pct,
        expected_order_size=1_000.0,
        account_equity=account_equity,
        available_margin=EQUITY,
        stop_pct=stop_pct,
        symbol_exposure_pct=symbol_exposure_pct,
    )


def test_fib_pa_config_parses_single_trade_risk_cap():
    config = load_entry_chain_config("configs/entry_chain.dry_run_fib_pa_v1.json")

    assert config.max_single_trade_risk_pct == 0.0075
    assert config.direct_risk_pct == 0.006
    assert config.probe_risk_pct == 0.0025


@pytest.mark.parametrize(
    ("selected_leverage", "expected"),
    [(1, 3_750.0), (4, 937.5)],
)
def test_leveraged_cap_uses_selected_leverage(selected_leverage: int, expected: float):
    cfg = EntryChainConfig(direct_risk_pct=0.02)
    ctx = _ctx(stop_pct=0.02)

    assert _notional_hint("DIRECT", 85.0, ctx, cfg, 0.5, selected_leverage) == expected


@pytest.mark.parametrize(
    ("stop_pct", "expected", "binding_cap"),
    [(0.03, 625.0, "leveraged_cap_notional"), (0.012, 1_562.5, "leveraged_cap_notional")],
)
def test_raw_and_leveraged_caps_apply_to_wide_and_tight_stops(
    stop_pct: float, expected: float, binding_cap: str
):
    cfg = EntryChainConfig(direct_risk_pct=0.006)
    diagnostics = _notional_cap_diagnostics("DIRECT", 85.0, _ctx(stop_pct=stop_pct), cfg, 0.2, 4)

    assert diagnostics["raw_notional"] == round(EQUITY * 0.006 / stop_pct, 4)
    assert diagnostics["leveraged_cap_notional"] == round(EQUITY * 0.0075 / (stop_pct * 4), 4)
    assert diagnostics["final_notional"] == expected
    assert diagnostics["binding_cap"] == binding_cap


def test_evaluate_entry_chain_uses_actual_selected_leverage_for_final_notional(monkeypatch):
    selected_leverages = iter((4, 1))

    def select_leverage(*args, **kwargs):
        return next(selected_leverages)

    monkeypatch.setattr(entry_chain, "_select_leverage", select_leverage)
    cfg = EntryChainConfig(direct_risk_pct=0.02)
    decision = evaluate_entry_chain(
        _ctx(stop_pct=0.02, component_scores=DIRECT_SCORE_COMPONENTS), cfg
    )

    assert decision.action == "DIRECT"
    assert decision.leverage == 4
    assert decision.notional_hint == 937.5
    assert decision.metadata["risk_budget"]["selected_leverage"] == 4


def test_decision_reapplies_cap_when_given_a_notional_hint():
    cfg = EntryChainConfig(direct_risk_pct=0.006)
    ctx = _ctx(stop_pct=0.03)
    decision = _decision(
        ctx,
        cfg,
        "DIRECT",
        85.0,
        {},
        {},
        [],
        0.2,
        100.0,
        leverage=4,
        notional_hint=9_999.0,
    )

    assert decision.notional_hint == 625.0


def test_remaining_symbol_exposure_is_a_final_cap():
    cfg = EntryChainConfig(direct_risk_pct=0.006)
    diagnostics = _notional_cap_diagnostics(
        "DIRECT", 85.0, _ctx(stop_pct=0.012, symbol_exposure_pct=0.099), cfg, 0.1, 4
    )

    assert diagnostics["remaining_exposure_notional"] == 10.0
    assert diagnostics["final_notional"] == 10.0
    assert diagnostics["binding_cap"] == "remaining_exposure_notional"


def test_direct_and_probe_risk_percentages_remain_distinct():
    cfg = EntryChainConfig(direct_risk_pct=0.002, probe_risk_pct=0.001)
    ctx = _ctx(stop_pct=0.03)

    direct = _notional_cap_diagnostics("DIRECT", 85.0, ctx, cfg, 0.2, 1)
    probe = _notional_cap_diagnostics("PROBE", 85.0, ctx, cfg, 0.2, 1)

    assert direct["raw_notional"] == 666.6667
    assert probe["raw_notional"] == 333.3333
    assert direct["final_notional"] == 666.6667
    assert probe["final_notional"] == 333.3333


@pytest.mark.parametrize("stop_pct", [0.0, -0.01, math.nan, math.inf])
def test_invalid_stop_returns_zero_without_division_error(stop_pct: float):
    cfg = EntryChainConfig()
    ctx = _ctx(stop_pct=stop_pct)

    assert _notional_hint("DIRECT", 85.0, ctx, cfg, 0.2, 4) == 0.0


def test_invalid_equity_and_non_executable_action_return_zero():
    cfg = EntryChainConfig()

    assert _notional_hint("DIRECT", 85.0, _ctx(stop_pct=0.012, account_equity=0.0), cfg, 0.2, 4) == 0.0
    assert _notional_hint("DIRECT", 85.0, _ctx(stop_pct=0.012, account_equity=-1.0), cfg, 0.2, 4) == 0.0
    assert _notional_hint("NO_TRADE", 50.0, _ctx(stop_pct=0.012), cfg, 0.2, 4) == 0.0
    assert _notional_hint("WATCH", 50.0, _ctx(stop_pct=0.012), cfg, 0.2, 4) == 0.0
