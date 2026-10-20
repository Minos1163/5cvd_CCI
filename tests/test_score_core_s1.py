"""S1 影子核的契约测试。

守三件事:
1. 纯函数判定正确(趋势向上/向下/数据不足);
2. ``legacy`` 模式下**不产生任何字段**(历史行为逐字段不变);
3. 影子只写 ``s1_core``,不碰 ``score`` / ``action`` / ``notional_hint`` / ``leverage``。
"""

from __future__ import annotations

import pytest

from src.signals.entry_chain_config import EntryChainConfig
from src.signals.score_core import SCHEMA_VERSION, s1_regime, s1_shadow


def _rising(n: int = 260, start: float = 100.0, step: float = 0.5) -> list[float]:
    return [start + step * i for i in range(n)]


def _falling(n: int = 260, start: float = 300.0, step: float = 0.5) -> list[float]:
    return [start - step * i for i in range(n)]


def test_insufficient_history_reports_state_not_flat_only() -> None:
    payload = s1_regime([100.0] * 10)
    assert payload["ready"] is False
    assert payload["state"] == "INSUFFICIENT"
    assert payload["direction"] == 0
    assert payload["required_bars"] == 201


def test_rising_series_is_long() -> None:
    payload = s1_regime(_rising())
    assert payload["ready"] is True
    assert payload["state"] == "LONG"
    assert payload["direction"] == 1
    assert payload["sma_fast"] > payload["sma_slow"]
    assert payload["spread_pct"] > 0


def test_falling_series_is_flat() -> None:
    payload = s1_regime(_falling())
    assert payload["ready"] is True
    assert payload["state"] == "FLAT"
    assert payload["direction"] == 0
    assert payload["spread_pct"] < 0


def test_flat_series_is_flat_not_long() -> None:
    payload = s1_regime([100.0] * 260)
    assert payload["state"] == "FLAT"
    assert payload["spread_pct"] == 0.0


def test_schema_version_is_stable() -> None:
    assert s1_regime(_rising())["schema_version"] == SCHEMA_VERSION


def test_legacy_mode_returns_none() -> None:
    assert s1_shadow(_rising(), mode="legacy") is None


def test_unknown_mode_raises() -> None:
    with pytest.raises(ValueError):
        s1_shadow(_rising(), mode="s9")


def test_config_defaults_to_legacy() -> None:
    assert EntryChainConfig().score_core == "legacy"


def test_config_accepts_shadow_mode_and_rejects_unknown_key() -> None:
    cfg = EntryChainConfig.from_mapping({"score_core": "s1_shadow"})
    assert cfg.score_core == "s1_shadow"
    with pytest.raises(ValueError):
        EntryChainConfig.from_mapping({"score_coree": "s1_shadow"})


def test_shadow_helper_only_adds_one_key() -> None:
    """attach_s1_core_shadow 只往 debug 里加 `s1_core`,不改别的键。"""

    class _Bar:
        def __init__(self, close: float) -> None:
            self.close = close

    from scripts.run_live_dry_run import attach_s1_core_shadow

    # legacy:什么都不加
    debug_legacy: dict = {"warmup": {"ready": True}}
    attach_s1_core_shadow(debug_legacy, {"4h": [_Bar(c) for c in _rising()]},
                          EntryChainConfig())
    assert set(debug_legacy) == {"warmup"}

    # s1_shadow:只多一个键
    debug_shadow: dict = {"warmup": {"ready": True}}
    attach_s1_core_shadow(debug_shadow, {"4h": [_Bar(c) for c in _rising()]},
                          EntryChainConfig(score_core="s1_shadow"))
    assert set(debug_shadow) == {"warmup", "s1_core"}
    assert debug_shadow["warmup"] == {"ready": True}
    assert debug_shadow["s1_core"]["state"] == "LONG"
