from __future__ import annotations

import pytest

from src.backtest.lifecycle_exit import AtrTpExitConfig as BacktestExitConfig
from src.observability import paper_trading
from src.observability.exit_spec import (
    CANONICAL_EXIT_SPEC,
    KNOWN_EXIT_SPEC_DIVERGENCE,
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


def test_backtest_default_stays_legacy():
    """P0 阶段**故意不切**回测默认值。

    切默认会让所有历史离线结论静默换口径（tests/test_lifecycle_exit.py
    有 6 处用例隐式依赖 (1.0,2.0,3.0) 默认值）。P0 只登记差异，P1 重跑后才切。
    """
    config = BacktestExitConfig()
    assert config.tp_levels == LEGACY_BACKTEST_EXIT_SPEC.tp_levels
    assert config.max_hold_bars == LEGACY_BACKTEST_EXIT_SPEC.max_hold_bars


def test_divergence_is_registered_not_hidden():
    assert "paper" in KNOWN_EXIT_SPEC_DIVERGENCE
    assert "backtest" in KNOWN_EXIT_SPEC_DIVERGENCE
    assert "P1" in KNOWN_EXIT_SPEC_DIVERGENCE


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
