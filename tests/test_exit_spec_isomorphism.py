from __future__ import annotations

import pytest

from src.backtest.lifecycle_exit import AtrTpExitConfig as BacktestExitConfig
from src.observability import paper_trading
from src.observability.exit_spec import (
    CANONICAL_EXIT_SPEC,
    LEGACY_BACKTEST_EXIT_SPEC,
    ExitSpec,
)


def test_canonical_matches_paper_constants():
    assert CANONICAL_EXIT_SPEC.tp_levels == paper_trading.TP_LEVELS
    assert CANONICAL_EXIT_SPEC.tp_fractions == paper_trading.TP_FRACTIONS
    assert CANONICAL_EXIT_SPEC.max_hold_bars == paper_trading.MAX_HOLD_BARS


def test_legacy_spec_is_visibly_different():
    assert LEGACY_BACKTEST_EXIT_SPEC.tp_levels != CANONICAL_EXIT_SPEC.tp_levels
    assert LEGACY_BACKTEST_EXIT_SPEC.max_hold_bars != CANONICAL_EXIT_SPEC.max_hold_bars


def test_backtest_default_is_canonical():
    """2026-11-09（P1-E8）已把回测默认值收敛到 canonical，与 paper 主账本同构。"""
    config = BacktestExitConfig()
    assert config.tp_levels == CANONICAL_EXIT_SPEC.tp_levels
    assert config.tp_fractions == CANONICAL_EXIT_SPEC.tp_fractions
    assert config.max_hold_bars == CANONICAL_EXIT_SPEC.max_hold_bars


def test_legacy_spec_still_reproducible():
    """legacy spec 保留，用于复现 2026-10-31 之前的离线结论。"""
    config = BacktestExitConfig.from_spec(LEGACY_BACKTEST_EXIT_SPEC)
    assert config.tp_levels == (1.0, 2.0, 3.0)
    assert config.max_hold_bars == 16


def test_canonical_requires_explicit_opt_in():
    config = BacktestExitConfig.from_spec(CANONICAL_EXIT_SPEC)
    assert config.tp_levels == CANONICAL_EXIT_SPEC.tp_levels
    assert config.max_hold_bars == CANONICAL_EXIT_SPEC.max_hold_bars


def test_spec_rejects_bad_fractions():
    with pytest.raises(ValueError, match="fractions"):
        ExitSpec(tp_fractions=(0.5, 0.5, 0.5))


def test_spec_requires_ascending_levels():
    with pytest.raises(ValueError, match="ascending"):
        ExitSpec(tp_levels=(2.0, 1.0, 3.0))


def test_paper_exit_config_defaults_to_canonical():
    config = paper_trading.PaperExitConfig()
    assert config.tp_levels == CANONICAL_EXIT_SPEC.tp_levels
    assert config.max_hold_bars == CANONICAL_EXIT_SPEC.max_hold_bars


def test_position_exit_config_preserves_new_fields(tmp_path):
    from src.observability.exit_spec import CANONICAL_EXIT_SPEC
    from src.observability.paper_trading import PaperExitConfig, PaperTradingLedger

    ledger = PaperTradingLedger(
        tmp_path,
        exit_config=PaperExitConfig(tp_levels=(1.5, 2.5, 3.5), max_hold_bars=48),
    )
    position = type("P", (), {"exit_mode": "trend_capture"})()
    derived = ledger._position_exit_config(position)
    assert derived.tp_levels == (1.5, 2.5, 3.5)
    assert derived.max_hold_bars == 48
    assert derived.mode == "trend_capture"
    assert CANONICAL_EXIT_SPEC.tp_levels == (1.2, 2.0, 3.0)


def test_timeout_bar_is_derived_from_max_hold():
    from src.observability import paper_trading

    config = paper_trading.PaperExitConfig()
    assert paper_trading.COST_BREAKEVEN_CHECK_BARS == max(1, config.max_hold_bars // 4)
