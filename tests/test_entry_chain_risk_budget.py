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
    assert config.probe_risk_pct == 0.0015


def test_probe_risk_pct_linear_scaling():
    """Task P-RISK:`probe_risk_pct` 只作用于 `raw_notional`,与另两个 cap 解耦。

    验证下调该参数(0.0025→0.0015)不会意外影响 `leveraged_cap_notional`
    或 `remaining_exposure_notional` 的计算路径——即方向明确的风险收紧。
    """
    ctx = _ctx(stop_pct=0.02, symbol_exposure_pct=0.0)
    low = EntryChainConfig(probe_risk_pct=0.0015, max_single_trade_risk_pct=0.0075)
    high = EntryChainConfig(probe_risk_pct=0.0030, max_single_trade_risk_pct=0.0075)

    low_diag = _notional_cap_diagnostics("PROBE", 70.0, ctx, low, 0.2, 1)
    high_diag = _notional_cap_diagnostics("PROBE", 70.0, ctx, high, 0.2, 1)

    # raw_notional 与 probe_risk_pct 线性正比(偏导数为正)
    assert high_diag["raw_notional"] > low_diag["raw_notional"]
    assert high_diag["raw_notional"] == pytest.approx(low_diag["raw_notional"] * 2.0)

    # 另两个 cap 与 probe_risk_pct 完全无关
    assert high_diag["leveraged_cap_notional"] == low_diag["leveraged_cap_notional"]
    assert high_diag["remaining_exposure_notional"] == low_diag["remaining_exposure_notional"]

    # 本组参数下 raw 即生效上限,故最终名义仓位同样随之下调
    assert low_diag["binding_cap"] == "raw_notional"
    assert high_diag["final_notional"] == pytest.approx(low_diag["final_notional"] * 2.0)


def test_binding_cap_attribution_logged():
    """Task P:`binding_cap` 来源须可从 decision 结构直接读出,无需重算三公式。

    实证背景:跨两窗口 59 条可执行记录全部在 `metadata.risk_budget.binding_cap`
    带值,故诊断脚本无需额外补字段即可归因(修正 2026-10-04 报告的初判)。
    """
    config = EntryChainConfig()
    context = EntryChainContext(
        symbol="TESTUSDT",
        timestamp=0,
        side="LONG",
        component_scores={
            "background_4h": 1.0,
            "direction_1h": 1.0,
            "quality_30m": 1.0,
            "trigger_15m": 1.0,
            "cvd_flow": 1.0,
        },
        quote_volume_24h=1e9,
        atr_pct=0.01,
        expected_order_size=1_000.0,
        account_equity=EQUITY,
        available_margin=EQUITY,
        stop_pct=0.012,
        symbol_exposure_pct=0.0,
    )
    budget = evaluate_entry_chain(context, config).to_dict()["metadata"]["risk_budget"]

    for key in (
        "binding_cap",
        "raw_notional",
        "leveraged_cap_notional",
        "remaining_exposure_notional",
        "final_notional",
        "selected_leverage",
        "stop_pct",
    ):
        assert key in budget, key
    assert budget["binding_cap"] in {
        "raw_notional",
        "leveraged_cap_notional",
        "remaining_exposure_notional",
        "none",
    }


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
