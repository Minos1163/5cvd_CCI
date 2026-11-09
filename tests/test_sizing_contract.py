from __future__ import annotations

import pytest

from src.signals.sizing_contract import (
    SIZING_TRACE_KEYS,
    assert_sizing_trace,
    summarize_sizing_trace,
)


def _trace(**overrides):
    base = {
        "raw_notional": 1200.0,
        "leveraged_cap_notional": 900.0,
        "remaining_exposure_notional": 1500.0,
        "final_notional": 900.0,
        "binding_cap": "leveraged_cap_notional",
        "leverage": 4,
        "leverage_reason": "DIRECT_ATR_MID",
    }
    base.update(overrides)
    return base


def test_trace_keys_are_exactly_declared():
    assert set(SIZING_TRACE_KEYS) == set(_trace())


def test_assert_passes_on_consistent_trace():
    assert_sizing_trace(_trace())


def test_assert_rejects_final_not_equal_to_min():
    with pytest.raises(AssertionError, match="final_notional"):
        assert_sizing_trace(_trace(final_notional=1000.0))


def test_assert_rejects_wrong_binding_cap():
    with pytest.raises(AssertionError, match="binding_cap"):
        assert_sizing_trace(_trace(binding_cap="raw_notional"))


def test_assert_rejects_missing_key():
    broken = _trace()
    broken.pop("remaining_exposure_notional")
    with pytest.raises(AssertionError, match="missing"):
        assert_sizing_trace(broken)


def test_none_binding_is_exempt():
    # 非入场路径（entry_chain.py:685/710/720）只有 binding_cap="none"，
    # 三 cap 不存在，不得触发断言。
    assert_sizing_trace({"binding_cap": "none", "selected_leverage": 0})


def test_summary_is_compact_and_deterministic():
    summary = summarize_sizing_trace(_trace())
    assert summary["binding_cap"] == "leveraged_cap_notional"
    assert summary["capped_by_ratio"] == pytest.approx(900.0 / 1200.0)
    assert list(summary) == [
        "raw_notional",
        "leveraged_cap_notional",
        "remaining_exposure_notional",
        "final_notional",
        "binding_cap",
        "capped_by_ratio",
    ]


def test_summary_tolerates_zero_raw():
    """raw_notional=0 时不能 ZeroDivisionError。

    真实路径上 action 非 PROBE/DIRECT 会返回 all-zero 诊断（binding_cap="none"），
    主循环仍会去 summarize 它。
    """
    summary = summarize_sizing_trace(
        {
            "raw_notional": 0.0,
            "leveraged_cap_notional": 0.0,
            "remaining_exposure_notional": 0.0,
            "final_notional": 0.0,
            "binding_cap": "none",
        }
    )
    assert summary["capped_by_ratio"] == 0.0


def test_production_diagnostics_shape_passes():
    """真实 `_notional_cap_diagnostics` 的输出带 selected_leverage / stop_pct 两个多余键。

    契约只要求"7 个键都在"，不要求"只有 7 个键"——否则每次诊断加一个字段就红。
    """
    from src.signals.entry_chain import _notional_cap_diagnostics
    from src.signals.entry_chain_config import EntryChainConfig

    class _Ctx:
        stop_pct = 0.01
        atr_pct = 0.01
        account_equity = 10000.0
        available_margin = 10000.0
        symbol_exposure_pct = 0.0

    diag = _notional_cap_diagnostics(
        "DIRECT", 95.0, _Ctx(), EntryChainConfig(), 0.05, selected_leverage=4
    )
    trace = {**diag, "leverage": int(diag["selected_leverage"]), "leverage_reason": "TEST"}
    assert set(SIZING_TRACE_KEYS) <= set(trace)
    assert_sizing_trace(trace)
    summary = summarize_sizing_trace(trace)
    assert summary["final_notional"] == diag["final_notional"]
    assert summary["binding_cap"] == diag["binding_cap"]
