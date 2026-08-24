# -*- coding: utf-8 -*-
"""regime_conditional_short_offset_shadow 单测(08-24 DEEPSEEK 3.3 节 shadow 反事实)。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.regime_conditional_short_offset_shadow import shadow_blocked  # noqa: E402


def _short(score: float) -> dict:
    return {"score": score, "side": "SHORT", "executable": True, "action": "PROBE"}


def test_shadow_blocked_below_threshold():
    rows = [_short(84.75), _short(90.1), _short(95.0)]
    blocked = shadow_blocked(rows, 92.0)
    assert [r["score"] for r in blocked] == [84.75, 90.1]


def test_shadow_blocked_none_when_all_above():
    rows = [_short(92.5), _short(95.0)]
    assert shadow_blocked(rows, 92.0) == []


def test_shadow_blocked_all_when_threshold_high():
    rows = [_short(84.75), _short(90.1)]
    assert len(shadow_blocked(rows, 92.0)) == 2
