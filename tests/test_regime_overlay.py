"""`regime_overlay` 契约测试:目标仓位判定 + cap 只降级不误伤。

守四件事:
1. 纯函数判定正确(趋势上/下/数据不足);
2. `off` 模式不产生字段(历史行为不变);
3. `cap` 只在目标为 0 时拦截,目标为 1 时不动;
4. 非法模式报错。
"""

from __future__ import annotations

import pytest

from src.portfolio.regime_overlay import (
    MA_FAST,
    MA_SLOW,
    REBALANCE_BARS,
    SCHEMA_VERSION,
    overlay_payload,
    regime_target,
    should_block_entry,
)
from src.signals.entry_chain_config import EntryChainConfig


def _rising(n: int = 260) -> list[float]:
    return [100.0 + 0.5 * i for i in range(n)]


def _falling(n: int = 260) -> list[float]:
    return [300.0 - 0.5 * i for i in range(n)]


def test_insufficient_history_targets_zero_but_marks_state() -> None:
    payload = regime_target([100.0] * 10)
    assert payload["ready"] is False
    assert payload["state"] == "INSUFFICIENT"
    assert payload["target"] == 0
    assert payload["required_bars"] == MA_SLOW + 1


def test_rising_is_risk_on() -> None:
    payload = regime_target(_rising())
    assert payload["ready"] is True
    assert payload["state"] == "RISK_ON"
    assert payload["target"] == 1
    assert payload["spread_pct"] > 0


def test_falling_is_risk_off() -> None:
    payload = regime_target(_falling())
    assert payload["state"] == "RISK_OFF"
    assert payload["target"] == 0
    assert payload["spread_pct"] < 0


def test_flat_is_risk_off_not_risk_on() -> None:
    assert regime_target([100.0] * 260)["target"] == 0


def test_schema_and_rebalance_bars_are_exposed() -> None:
    payload = regime_target(_rising())
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["rebalance_bars"] == REBALANCE_BARS
    assert (MA_FAST, MA_SLOW) == (50, 200)


def test_off_mode_returns_none() -> None:
    assert overlay_payload(_rising(), mode="off") is None


def test_shadow_payload_carries_mode() -> None:
    payload = overlay_payload(_rising(), mode="shadow")
    assert payload is not None
    assert payload["mode"] == "shadow"
    assert payload["target"] == 1


def test_should_block_entry_only_in_cap_mode_and_target_zero() -> None:
    assert should_block_entry("cap", 0) is True
    assert should_block_entry("cap", 1) is False
    assert should_block_entry("shadow", 0) is False
    assert should_block_entry("off", 0) is False


def test_should_block_entry_rejects_unknown_mode() -> None:
    with pytest.raises(ValueError):
        should_block_entry("enforce", 0)


def test_config_default_is_off_and_accepts_cap() -> None:
    assert EntryChainConfig().regime_overlay == "off"
    assert EntryChainConfig.from_mapping({"regime_overlay": "cap"}).regime_overlay == "cap"


def test_cap_decision_blocks_new_entries_only() -> None:
    from src.portfolio.regime_overlay import BLOCK_REASON, cap_decision

    # cap + 目标 0 + DIRECT → 降级并归零名义
    action, notional, reasons, blocked = cap_decision(
        mode="cap", target=0, action="DIRECT", notional_hint=1200.0, reasons=("A",))
    assert (action, notional, blocked) == ("NO_TRADE", 0.0, True)
    assert reasons[-1] == BLOCK_REASON

    # PROBE 同样被拦
    assert cap_decision(mode="cap", target=0, action="PROBE", notional_hint=50.0,
                        reasons=())[3] is True

    # 目标为 1 不拦
    assert cap_decision(mode="cap", target=1, action="DIRECT", notional_hint=1200.0,
                        reasons=())[3] is False

    # shadow 模式只记录,不拦
    assert cap_decision(mode="shadow", target=0, action="DIRECT", notional_hint=1200.0,
                        reasons=())[3] is False

    # 已经是 NO_TRADE/WATCH 的不动(不重复追加 reason)
    action, notional, reasons, blocked = cap_decision(
        mode="cap", target=0, action="WATCH", notional_hint=0.0, reasons=("A",))
    assert (action, blocked, reasons) == ("WATCH", False, ("A",))
