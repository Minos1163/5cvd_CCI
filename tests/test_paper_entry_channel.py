# -*- coding: utf-8 -*-
"""主账本 entry_channel 可观测性单测(08-31 评审 6.2)。

背景:三笔大额亏损 `entry_channel=null` 造成归因盲区。
`_resolve_entry_channel` 在主账本无显式通道时按 action 标注 main_direct / main_probe。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.observability.paper_trading import _resolve_entry_channel  # noqa: E402


def test_explicit_entry_channel_wins():
    assert _resolve_entry_channel({"entry_channel": "q1_trend_launch", "action": "PROBE"}) == "q1_trend_launch"


def test_direct_maps_to_main_direct():
    assert _resolve_entry_channel({"action": "DIRECT"}) == "main_direct"


def test_probe_maps_to_main_probe():
    assert _resolve_entry_channel({"action": "PROBE"}) == "main_probe"


def test_non_executable_returns_none():
    assert _resolve_entry_channel({"action": "WATCH"}) is None
    assert _resolve_entry_channel({"action": "NO_TRADE"}) is None
    assert _resolve_entry_channel({}) is None
