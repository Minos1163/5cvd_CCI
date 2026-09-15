# -*- coding: utf-8 -*-
"""regime_conditional_short_offset_shadow 单测(08-24 DEEPSEEK 3.3 节 shadow 反事实)。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.regime_conditional_short_offset_shadow import (  # noqa: E402
    completed_15m_candle_timestamp,
    regime_evidence,
    reversal_confirmation_score,
    shadow_blocked,
    shadow_rows,
)


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


def _decision(*, score=90.0, breadth=None, decision_ts=1900, candle_ts=1000):
    snapshot = {} if breadth is None else {"breadth_5h": breadth[0], "breadth_6h": breadth[1]}
    return {
        "symbol": "SOLUSDT",
        "timestamp": decision_ts,
        "score": score,
        "action": "PROBE",
        "quadrant": "Q1",
        "entry_context": {"side": "SHORT"},
        "component_points": {
            "price_action_structure": 18.0,
            "flow_cvd_confirmation": 14.0,
            "cci_momentum_quality": 7.0,
        },
        "market_snapshot": snapshot,
        "kline": {"timeframe": "15m", "timestamp": candle_ts},
    }


def test_completed_candle_requires_full_15m_delay():
    row = _decision(decision_ts=1899)
    assert completed_15m_candle_timestamp(row) is None
    row["timestamp"] = 1900
    assert completed_15m_candle_timestamp(row) == 1000


def test_completed_candle_rejects_missing_timeframe():
    row = _decision()
    del row["kline"]["timeframe"]
    assert completed_15m_candle_timestamp(row) is None


def test_regime_evidence_distinguishes_breadth_confirmation_and_missing_data():
    assert regime_evidence(_decision(breadth=(0.7, 0.8)), 900)["status"] == "BULLISH_CONFIRMED"
    assert regime_evidence(_decision(), 900)["status"] == "BULLISH_TIME_WINDOW_PROXY"
    assert regime_evidence(_decision(breadth=(0.4, 0.8)), 900)["status"] == "NOT_BULLISH"


def test_shadow_rows_excludes_outside_regime_window():
    rows, counts = shadow_rows([_decision(breadth=(0.7, 0.8))], 1100, 80.0, 0.6)
    assert rows == []
    assert counts["outside_regime_window"] == 1


def test_shadow_rows_only_select_q1_short_and_record_reversal_score():
    rows, counts = shadow_rows([_decision(breadth=(0.7, 0.8)), _decision(score=70.0)], 900, 80.0, 0.6)
    assert len(rows) == 1
    assert rows[0]["regime_status"] == "BULLISH_CONFIRMED"
    assert 0.0 <= rows[0]["reversal_confirmation_score"] <= 1.0
    assert counts["breadth_confirmed"] == 1
    assert counts["breadth_missing"] == 1
